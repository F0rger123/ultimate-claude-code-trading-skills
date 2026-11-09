"""Live paper trading: separate simulated accounts ("books"), each running one strategy on the SAME
portfolio engine as the research.

How it works (forward-only, no look-ahead):
- Each book gets a fixed start time the first time it runs (state/paper/start.json).
- Slow books update every hour on hourly candles; fast books update every 5 minutes on 5-minute candles.
  Each update replays the book from its start to the latest closed bar. Signals only see past bars and fill
  at the next bar's open, so a replay reproduces the same history and adds the new bars on top: the same
  code for backtest and paper.
- Results go to state/paper/<book>.json (one file per account, for the app's account switcher) and an
  aggregate of all books goes into the journal (mode "paper"). Nothing here can place a real order.

Assumptions (label them in anything you publish):
- Prices are Coinbase SPOT candles. Perp books use the perp cost model on those prices
  (basis ignored; funding ASSUMED 0.001%/h against longs).
- Spot fees 0.90% taker per side (assumed entry tier). Perp 0.06% + 0.02% per side.
- The fast books LOST MONEY after costs in the backtests (reports/legacy/tournament-latest.md). They run so
  the owner can watch fast trading on live prices, not because the evidence supports them.
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
     "mode": "perp", "equity": 10000.0, "cadence": "slow", "note": "Best corrected backtest; daily signals"},
    {"id": "pb_vmt_perp", "name": "Vol-managed trend (perp)", "cls": C.VolManagedTrend, "report": "vol_managed_trend-perp",
     "mode": "perp", "equity": 10000.0, "cadence": "slow", "note": "Daily signals, volatility-scaled size"},
    {"id": "pb_breakout_perp", "name": "Vol-filtered breakout (perp)", "cls": C.VolFilteredBreakout,
     "report": "vol_filtered_breakout-perp", "mode": "perp", "equity": 10000.0, "cadence": "slow",
     "note": "Daily channel breakouts"},
    {"id": "pb_rotation_spot", "name": "Weekly rotation (spot)", "cls": C.WeeklyStrengthRotation,
     "report": "weekly_strength_rotation-spot", "mode": "spot", "equity": 10000.0, "cadence": "slow",
     "note": "Holds the strongest coin, rebalanced Mondays"},
    {"id": "pb_pilot_spot50", "name": "$50 spot pilot mirror", "cls": S.TrendEnsemble, "report": "trend_ensemble-spot",
     "mode": "spot", "equity": 50.0, "extra": {"long_only": 1}, "cadence": "slow",
     "note": "What the real $50 pilot would do (buys only, spot fees)"},
    {"id": "pb_fast_mtf", "name": "Fast: 4-timeframe alignment (5m)", "cls": S.MTFQuick, "mode": "perp",
     "equity": 10000.0, "cadence": "fast", "note": "Your 1h/30m/15m/5m method. Lost money after costs in backtests"},
    {"id": "pb_fast_vwap", "name": "Fast: VWAP reclaim (5m)", "cls": S.VWAPReclaim, "mode": "perp",
     "equity": 10000.0, "cadence": "fast", "note": "US-session VWAP reclaims. Lost money after costs in backtests"},
    {"id": "pb_fast_rsi2", "name": "Fast: RSI(2) dip-buy (15m)", "cls": S.RSI2Reversion, "mode": "perp",
     "equity": 10000.0, "cadence": "fast", "note": "Short-term mean reversion. Lost money after costs in backtests"},
]
NAMES = {b["id"]: b["name"] for b in BOOKS}
BY_ID = {b["id"]: b for b in BOOKS}
FAST_WARMUP_DAYS = 30


def latest_params(report):
    """Parameters chosen by the most recent walk-forward window of the corrected tournament."""
    if not report:
        return {}, None
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


def _cfg(book):
    if book["mode"] == "spot":
        return P.Config("spot", equity=book["equity"], risk=RISK, pos_lev=1.0, gross_lev=1.0, dd_policy=True,
                        resume_days=10 ** 6, min_notional=1.0)
    return P.Config("perp", equity=book["equity"], risk=RISK, pos_lev=1.5, gross_lev=1.5, dd_policy=True,
                    resume_days=10 ** 6, funding_per_h=FUNDING)


def _variants(markets, book, params):
    if book["cls"] is C.WeeklyStrengthRotation:
        coord = C.RotationCoordinator(markets, params.get("lookback", 90))
        return {s: [book["cls"](m, coordinator=coord, **params)] for s, m in markets.items()}
    p = dict(book.get("extra", {}), **params)
    return {s: [book["cls"](m, **p)] for s, m in markets.items()}


def _state(pdir, now, rules):
    sp = os.path.join(pdir, "start.json")
    st = {}
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            st = json.load(f)
    books = st.setdefault("books", {})
    for b in BOOKS:  # the first five books started together; new books start now
        if b["id"] not in books:
            books[b["id"]] = st.get("start") if (st.get("start") and b["cadence"] == "slow") else now - now % 300
    if rules.get("kill_switch") and not st.get("kill_at"):
        st["kill_at"] = now - now % 300
    elif not rules.get("kill_switch") and st.get("kill_at"):
        st.pop("kill_at")  # owner resumed: new entries allowed from now on
        st.setdefault("resumes", []).append(now)
    with open(sp, "w", encoding="utf-8") as f:
        json.dump(st, f)
    return st


_CACHE = {}  # (symbol, gran) -> bars kept in memory between updates; the file is rewritten at most hourly
_SAVED = {}


def _bars(s, gran, now, fetch):
    root = os.path.join(ROOT, "data")
    key = (s, gran)
    path = D.cache_path(root, D.PERPS[s]["spot"], gran)
    if key not in _CACHE:
        _CACHE[key] = D.load(path) if os.path.exists(path) else \
            D.update_cache(root, D.PERPS[s]["spot"], gran, days=730, log=lambda *a: None)
        _SAVED[key] = now
    bars = _CACHE[key]
    if fetch:
        end = now - now % gran
        if bars[-1][0] + gran < end:
            new = D.fetch_spot(D.PERPS[s]["spot"], gran, bars[-1][0] + gran, end)
            if new:
                bars.extend(b for b in new if b[0] > bars[-1][0])
        if now - _SAVED.get(key, 0) >= 3600:
            D.save(path, bars)
            _SAVED[key] = now
    return bars


def _markets(gran, now, fetch, since=None):
    markets, stale = {}, []
    for s in SYMS:
        bars = _bars(s, gran, now, fetch)
        if since is not None:
            bars = [b for b in bars if b[0] >= since]
        markets[s] = Market(bars, s, gran)
        if bars and now - (bars[-1][0] + gran) > 3 * max(gran, 3600):
            stale.append(s)
    return markets, stale


def update(state_dir, journal, rules, log=print, now=None, fetch=True, cadence="slow"):
    """Refresh data and replay the books of one cadence; then rebuild the aggregate. Returns the summary."""
    now = int(now or time.time())
    pdir = os.path.join(state_dir, "paper")
    os.makedirs(pdir, exist_ok=True)
    st = _state(pdir, now, rules)
    books = [b for b in BOOKS if b["cadence"] == cadence]
    gran = 3600 if cadence == "slow" else 300
    first = min(st["books"][b["id"]] for b in books)
    since = None if cadence == "slow" else first - FAST_WARMUP_DAYS * 86400
    markets, stale = _markets(gran, now, fetch, since)
    step = 1 if cadence == "slow" else 3  # stored curve resolution: hourly, or every 15 minutes
    for book in books:
        params, bt = latest_params(book.get("report"))
        start = st["books"][book["id"]]
        r = P.run(markets, _variants(markets, book, params), _cfg(book), start_t=start, close_at_end=False,
                  kill_at=st.get("kill_at"))
        curve = r["curve"] or [(start, book["equity"])]
        eq = curve[-1][1]
        res = {"id": book["id"], "name": book["name"], "mode": book["mode"], "cadence": cadence,
               "note": book.get("note", ""), "params": params, "backtest": bt, "start": start,
               "start_equity": book["equity"], "equity": eq, "pnl": eq - book["equity"], "updated": now,
               "closed": len(r["trades"]), "open": r["open"], "pending": r.get("pending", []), "stale": stale,
               "events": [list(e) for e in r["events"] if e[1] != "skip"][-20:],
               "skips": [list(e) for e in r["events"] if e[1] == "skip"][-10:],
               "curve": [[t, round(e, 2)] for t, e in curve[::step]] + [[curve[-1][0], round(curve[-1][1], 2)]],
               "trades": r["trades"]}
        with open(os.path.join(pdir, book["id"] + ".json"), "w", encoding="utf-8") as f:
            json.dump(res, f, default=str)
    if stale:
        journal.event("warn", "paper (%s): stale data for %s; signals wait" % (cadence, ",".join(stale)))
    return rebuild(state_dir, journal, rules, now)


def load_book(state_dir, book_id):
    p = os.path.join(state_dir, "paper", book_id + ".json")
    if book_id not in BY_ID or not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rebuild(state_dir, journal, rules, now=None):
    """Aggregate all books into the journal (the app's 'All accounts' view) and the paper drawdown halt."""
    now = int(now or time.time())
    books = [x for x in (load_book(state_dir, b["id"]) for b in BOOKS) if x]
    agg, rows = {}, []
    for bk in books:
        for t, e in bk["curve"]:
            agg.setdefault(int(t) - int(t) % 3600, {})[bk["id"]] = e
        rows += [("closed", bk, x) for x in bk["trades"]] + [("open", bk, x) for x in bk["open"]]
    last = {bk["id"]: bk["start_equity"] for bk in books}
    series = []
    for t in sorted(agg):
        last.update(agg[t])
        series.append((t, sum(last.values())))
    total0 = sum(bk["start_equity"] for bk in books)
    total = sum(bk["equity"] for bk in books)
    peak = max([total0] + [e for _, e in series] + [total])
    out = {"t": now, "books": [{k: v for k, v in bk.items() if k not in ("curve", "trades")} for bk in books],
           "total_start": total0, "total_equity": total, "drawdown": (peak - total) / peak if peak else 0.0}
    _write_journal(journal, series, rows)
    with open(os.path.join(state_dir, "paper", "summary.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
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


# ---------------- per-account views for the phone API
def _row(bk, x, status, k):
    lev = (x["qty"] * x["entry"]) / bk["start_equity"] if bk["start_equity"] else 0.0
    base = {"id": k, "mode": "paper", "strategy": bk["id"], "strategy_name": bk["name"], "symbol": x["sym"],
            "side": x["side"], "contracts": x["qty"], "entry": x["entry"], "stop": x["stop"], "target": x.get("target"),
            "t0": int(x["t0"]), "leverage": round(lev, 2), "status": status}
    if status == "closed":
        base.update(exit=x["exit"], t1=int(x["t1"]), why=x["why"], pnl_usd=x["pnl"], R=x["R"])
    else:
        base.update(exit=None, t1=None, why=None, pnl_usd=x["unrealized"],
                    R=x["unrealized"] / x["risk_usd"] if x["risk_usd"] else 0.0)
    return base


def account_trades(bk, status):
    if status == "open":
        return [_row(bk, x, "open", 100000 + k) for k, x in enumerate(bk["open"])]
    rows = [_row(bk, x, "closed", k + 1) for k, x in enumerate(bk["trades"])]
    return sorted(rows, key=lambda r: -r["t1"])[:200]


def account_summary(bk, kill_switch):
    closed = bk["trades"]
    now = int(time.time())
    day0 = now - now % 86400
    prior = [e for t, e in bk["curve"] if t < day0]
    eq = bk["equity"]
    wins = [x for x in closed if x["pnl"] > 0]
    gl = -sum(x["pnl"] for x in closed if x["pnl"] <= 0)
    peak, mdd = bk["start_equity"], 0.0
    for _, e in bk["curve"]:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak else 0)
    return {"mode": "paper", "account": bk["id"], "account_name": bk["name"], "note": bk.get("note", ""),
            "balance": eq, "pnl_all": eq - bk["start_equity"],
            "pnl_all_pct": (eq - bk["start_equity"]) / bk["start_equity"] if bk["start_equity"] else 0,
            "pnl_today": eq - (prior[-1] if prior else bk["start_equity"]),
            "win_rate": len(wins) / len(closed) if closed else None,
            "profit_factor": (sum(x["pnl"] for x in wins) / gl) if gl > 0 else None, "max_drawdown": mdd,
            "open_trades": account_trades(bk, "open"), "strategies_running": 1, "kill_switch": kill_switch,
            "updated": bk.get("updated"), "events": []}


def account_equity(bk, secs):
    cut = int(time.time()) - secs
    pts = [{"t": int(t), "equity": e} for t, e in bk["curve"] if t >= cut]
    step = max(1, len(pts) // 300)
    return pts[::step] + (pts[-1:] if pts and (len(pts) - 1) % step else [])


def accounts(state_dir):
    out = []
    for b in BOOKS:
        bk = load_book(state_dir, b["id"])
        if not bk:
            continue
        out.append({"id": b["id"], "name": b["name"], "mode": b["mode"], "cadence": b["cadence"],
                    "note": b.get("note", ""), "start_equity": bk["start_equity"], "equity": bk["equity"],
                    "pnl": bk["pnl"], "open": len(bk["open"]), "closed": bk["closed"], "updated": bk.get("updated")})
    return out
