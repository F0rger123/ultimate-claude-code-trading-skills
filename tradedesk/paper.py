"""Live paper trading for the tournament candidates, on the SAME portfolio engine as the research.

How it works (forward-only, no look-ahead):
- A paper start time is fixed the first time this runs (state/paper/start.json).
- Every hour the desk refreshes Coinbase hourly candles and replays each paper book from the start time to
  the latest closed bar. Signals only see past bars and fill at the next bar's open, so replaying gives the
  same history every time and adds the new hour on top: identical code for backtest and paper.
- Each book is its own simulated account. Results go to state/paper/<book>.json and into the journal
  (mode "paper") for the phone app. Nothing here can place a real order.

Assumptions (label them in anything you publish):
- Prices are Coinbase SPOT hourly candles; perp books use the perp cost model on those prices
  (basis ignored; funding ASSUMED 0.001%/h against longs).
- Spot fees 0.90% taker per side (assumed entry tier). Perp 0.06% + 0.02% per side.
"""
import glob
import json
import os
import time

from . import candidates as C
from . import data as D
from . import portfolio as P
from . import risk as RK
from . import strategies as S
from .market import Market

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SYMS = ["BTC", "ETH", "SOL"]
RISK = 0.01  # within the owner's 1% ceiling; the live target is 0.5%
FUNDING = 0.00001

BOOKS = [
    {"id": "pb_trend_perp", "name": "Trend ensemble (perp)", "cls": S.TrendEnsemble, "report": "trend_ensemble-perp",
     "mode": "perp", "equity": 10000.0},
    {"id": "pb_vmt_perp", "name": "Vol-managed trend (perp)", "cls": C.VolManagedTrend, "report": "vol_managed_trend-perp",
     "mode": "perp", "equity": 10000.0},
    {"id": "pb_breakout_perp", "name": "Vol-filtered breakout (perp)", "cls": C.VolFilteredBreakout,
     "report": "vol_filtered_breakout-perp", "mode": "perp", "equity": 10000.0},
    {"id": "pb_rotation_spot", "name": "Weekly rotation (spot)", "cls": C.WeeklyStrengthRotation,
     "report": "weekly_strength_rotation-spot", "mode": "spot", "equity": 10000.0},
    {"id": "pb_pilot_spot50", "name": "$50 spot pilot mirror (trend, long-only)", "cls": S.TrendEnsemble,
     "report": "trend_ensemble-spot", "mode": "spot", "equity": 50.0, "extra": {"long_only": 1}},
]
NAMES = {b["id"]: b["name"] for b in BOOKS}


def latest_params(report):
    """Parameters chosen by the most recent walk-forward window of the corrected tournament."""
    p = os.path.join(ROOT, "reports", "corrected", report + ".json")
    if not os.path.exists(p):
        return {}, None
    with open(p, encoding="utf-8") as f:
        r = json.load(f)
    w = [x for x in r.get("windows", []) if x.get("params") is not None]
    cs, ts = r.get("curve_stats", {}), r.get("trade_stats", {})
    bt = {"oos_trades": ts.get("trades"), "pf": ts.get("profit_factor"), "avg_R": ts.get("avg_R"),
          "max_dd": cs.get("max_dd_daily"), "cagr": cs.get("cagr"), "sharpe": cs.get("sharpe")}
    return (dict(w[-1]["params"]) if w else {}), bt


def _cfg(book, kill_at):
    if book["mode"] == "spot":
        c = P.Config("spot", equity=book["equity"], risk=RISK, pos_lev=1.0, gross_lev=1.0, dd_policy=True,
                     resume_days=10 ** 6, min_notional=1.0)
    else:
        c = P.Config("perp", equity=book["equity"], risk=RISK, pos_lev=1.5, gross_lev=1.5, dd_policy=True,
                     resume_days=10 ** 6, funding_per_h=FUNDING)
    return c


def _variants(markets, book, params):
    if book["cls"] is C.WeeklyStrengthRotation:
        coord = C.RotationCoordinator(markets, params.get("lookback", 90))
        return {s: [book["cls"](m, coordinator=coord, **params)] for s, m in markets.items()}
    p = dict(book.get("extra", {}), **params)
    return {s: [book["cls"](m, **p)] for s, m in markets.items()}


def update(state_dir, journal, rules, log=print, now=None, fetch=True):
    """Refresh data, replay every book from the paper start, write state and the journal. Returns summary."""
    now = int(now or time.time())
    pdir = os.path.join(state_dir, "paper")
    os.makedirs(pdir, exist_ok=True)
    sp = os.path.join(pdir, "start.json")
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            st = json.load(f)
    else:
        st = {"start": now - now % 3600, "created": now}
        with open(sp, "w", encoding="utf-8") as f:
            json.dump(st, f)
    start = st["start"]
    if rules.get("kill_switch") and not st.get("kill_at"):
        st["kill_at"] = now - now % 3600
    elif not rules.get("kill_switch") and st.get("kill_at"):
        st.pop("kill_at")  # owner resumed: new entries allowed from now on
        st.setdefault("resumes", []).append(now)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    markets, stale = {}, []
    for s in SYMS:
        bars = (D.update_cache(os.path.join(ROOT, "data"), D.PERPS[s]["spot"], 3600, days=2870, log=lambda *a: None)
                if fetch else D.load(D.cache_path(os.path.join(ROOT, "data"), D.PERPS[s]["spot"], 3600)))
        markets[s] = Market(bars, s, 3600)
        if now - (bars[-1][0] + 3600) > 3 * 3600:
            stale.append(s)
    out = {"t": now, "start": start, "books": [], "stale": stale}
    agg = {}
    jrows = []
    for book in BOOKS:
        params, bt = latest_params(book["report"])
        r = P.run(markets, _variants(markets, book, params), _cfg(book, st.get("kill_at")), start_t=start,
                  close_at_end=False, kill_at=st.get("kill_at"))
        curve = r["curve"] or [(start, book["equity"])]
        eq = curve[-1][1]
        res = {"id": book["id"], "name": book["name"], "mode": book["mode"], "params": params, "backtest": bt,
               "start_equity": book["equity"], "equity": eq, "pnl": eq - book["equity"],
               "closed": len(r["trades"]), "open": r["open"], "pending": r.get("pending", []),
               "events": [list(e) for e in r["events"] if e[1] != "skip"][-20:],
               "skips": [list(e) for e in r["events"] if e[1] == "skip"][-10:],
               "curve": [[t, round(e, 2)] for t, e in curve[::24]] + [[curve[-1][0], round(curve[-1][1], 2)]]}
        with open(os.path.join(pdir, book["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(dict(res, trades=r["trades"]), f, indent=1, default=str)
        out["books"].append({k: v for k, v in res.items() if k != "curve"})
        for t, e in curve:
            agg.setdefault(t, {})[book["id"]] = e
        for tr in r["trades"]:
            jrows.append(("closed", book, tr))
        for op in r["open"]:
            jrows.append(("open", book, op))
    # aggregate equity (forward-filled across books) for the app
    last, series = {b["id"]: b["equity"] for b in BOOKS}, []
    for t in sorted(agg):
        last.update(agg[t])
        series.append((t, sum(last.values())))
    total0 = sum(b["equity"] for b in BOOKS)
    out["total_start"] = total0
    out["total_equity"] = series[-1][1] if series else total0
    peak = max([total0] + [e for _, e in series])
    out["drawdown"] = (peak - out["total_equity"]) / peak if peak else 0.0
    _write_journal(journal, series, jrows)
    with open(os.path.join(pdir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    if stale:
        journal.event("warn", "paper: stale data for %s (no new hourly bar in 3h); signals wait" % ",".join(stale))
    if out["drawdown"] >= rules["max_drawdown_pct"] and not rules["kill_switch"]:
        rules["kill_switch"] = True
        RK.save_rules(os.path.join(state_dir, "rules.json"), rules)
        journal.event("warn", "PAPER MAX DRAWDOWN %.1f%%: kill switch on" % (100 * out["drawdown"]))
    return out


def _write_journal(j, series, rows):
    """Replace the paper rows with the replayed state (idempotent)."""
    with j.lock:
        db = j.db
        db.execute("DELETE FROM trades WHERE mode='paper'")
        db.execute("DELETE FROM equity WHERE mode='paper'")
        db.executemany("INSERT INTO equity(t,mode,equity) VALUES(?,?,?)", [(int(t), "paper", e) for t, e in series])
        for kind, book, x in rows:
            feat = json.dumps({"book": book["name"]})
            if kind == "closed":
                db.execute("INSERT INTO trades(mode,strategy,symbol,side,contracts,entry,stop,target,t0,exit,t1,why,pnl_usd,"
                           "fees_usd,R,risk_usd,leverage,status,feat) VALUES('paper',?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,'closed',?)",
                           (book["id"], x["sym"], x["side"], x["qty"], x["entry"], x["stop"], None, int(x["t0"]),
                            x["exit"], int(x["t1"]), x["why"], x["pnl"], x["fees"] + x["funding"], x["R"],
                            x["risk_usd"], 0.0, feat))
            else:
                r = x["unrealized"] / x["risk_usd"] if x["risk_usd"] else 0.0
                db.execute("INSERT INTO trades(mode,strategy,symbol,side,contracts,entry,stop,target,t0,pnl_usd,fees_usd,R,"
                           "risk_usd,leverage,status,feat) VALUES('paper',?,?,?,?,?,?,?,?,?,?,?,?,?,'open',?)",
                           (book["id"], x["sym"], x["side"], x["qty"], x["entry"], x["stop"], x["target"], int(x["t0"]),
                            x["unrealized"], x["fees"] + x["funding"], r, x["risk_usd"], 0.0, feat))
        db.commit()


def load_summary(state_dir):
    p = os.path.join(state_dir, "paper", "summary.json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def book_files(state_dir):
    return sorted(glob.glob(os.path.join(state_dir, "paper", "pb_*.json")))
