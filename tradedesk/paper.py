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
import re
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
     "mode": "spot", "equity": 50.0, "extra": {"long_only": 1}, "cadence": "slow", "protected": True,
     "note": "What the real $50 pilot would do (buys only, spot fees). Never rotated out"},
    {"id": "pb_fast_mtf", "name": "Fast: 4-timeframe alignment (5m)", "cls": S.MTFQuick, "mode": "perp",
     "equity": 10000.0, "cadence": "fast",
     "note": "Your 1h/30m/15m/5m method. Checked every 5 min, trades about once a day. Lost money after costs in backtests"},
    {"id": "pb_fast_vwap", "name": "Fast: VWAP reclaim (5m)", "cls": S.VWAPReclaim, "mode": "perp",
     "equity": 10000.0, "cadence": "fast",
     "note": "US-session VWAP reclaims, 8 AM-3 PM ET only. About 1-2 trades a day. Lost money after costs in backtests"},
    {"id": "pb_fast_rsi2", "name": "Fast: RSI(2) dip-buy (15m)", "cls": S.RSI2Reversion, "mode": "perp",
     "equity": 10000.0, "cadence": "fast",
     "note": "Short-term mean reversion. About 2-3 trades a day. Lost money after costs in backtests"},
    # Small size and one position at a time, so fees drain it slowly; it still stops itself at -10% like every book.
    {"id": "pb_fast_scalp10", "name": "Fast: 10-minute scalper (5m)", "cls": S.Scalp10, "mode": "perp",
     "equity": 10000.0, "cadence": "fast", "risk": 0.0025, "pos_lev": 0.1, "gross_lev": 0.1,
     "note": "Trades about every 10 minutes, one coin at a time, small size. Fees make it lose in tests; "
             "expect it to hit its -10% stop in about a week"},
]
SEED_IDS = {b["id"] for b in BOOKS}
from . import library as LIB  # noqa: E402  strategies added from the research bank
REGISTRY = {c.id: c for c in S.ALL + [S.Scalp10] + C.ALL + LIB.ALL}
FAST_WARMUP_DAYS = 30
_SAFE_ID = re.compile(r"^pb_[a-z0-9_]{1,60}$")


# ---------------- roster: the accounts running now (BOOKS is only the first roster)
def _roster_path(state_dir):
    return os.path.join(state_dir, "paper", "roster.json")


def _spec(b):
    d = {k: v for k, v in b.items() if k != "cls"}
    d["cls"] = b["cls"].id if isinstance(b["cls"], type) else b["cls"]
    return d


def roster(state_dir):
    """Active accounts: state/paper/roster.json once the weekly shake-up has written it, else BOOKS."""
    p = _roster_path(state_dir)
    specs = [_spec(b) for b in BOOKS]
    if os.path.exists(p):
        try:
            with open(p, encoding="utf-8") as f:
                specs = json.load(f)
        except (OSError, ValueError):
            pass  # a half-written file never stops the desk; the next read gets the new one
    return [dict(d, cls=REGISTRY[d["cls"]]) for d in specs if d.get("cls") in REGISTRY]


def save_roster(state_dir, books):
    p = _roster_path(state_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump([_spec(b) for b in books], f, indent=1)
    os.replace(p + ".tmp", p)


def retired_books(state_dir):
    out = []
    for p in sorted(glob.glob(os.path.join(state_dir, "paper", "retired", "pb_*.json"))):
        try:
            with open(p, encoding="utf-8") as f:
                out.append(json.load(f))
        except (OSError, ValueError):
            continue
    return out


def retire(state_dir, book_id, reason, now=None):
    """Move an account out of the roster into paper/retired/. Its result stays in the 'All accounts' total."""
    bk = load_book(state_dir, book_id)
    if bk is None:
        return None
    bk.update(retired=int(now or time.time()), retired_reason=reason, open=[], pending=[])
    d = os.path.join(state_dir, "paper", "retired")
    os.makedirs(d, exist_ok=True)
    with open(os.path.join(d, book_id + ".json"), "w", encoding="utf-8") as f:
        json.dump(bk, f, default=str)
    os.remove(os.path.join(state_dir, "paper", book_id + ".json"))
    return bk


def names(state_dir):
    out = {b["id"]: b["name"] + " (retired)" for b in retired_books(state_dir)}
    out.update({b["id"]: b["name"] for b in roster(state_dir)})
    return out


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
    # a book may only set smaller risk or leverage than the defaults, never larger
    return P.Config("perp", equity=book["equity"], risk=min(RISK, book.get("risk", RISK)),
                    pos_lev=min(1.5, book.get("pos_lev", 1.5)), gross_lev=min(1.5, book.get("gross_lev", 1.5)),
                    dd_policy=True, resume_days=10 ** 6, funding_per_h=FUNDING)


def _variants(markets, book, params):
    if book["cls"] is C.WeeklyStrengthRotation:
        coord = C.RotationCoordinator(markets, params.get("lookback", 90))
        out = {s: [book["cls"](m, coordinator=coord, **params)] for s, m in markets.items()}
    else:
        p = dict(book.get("extra", {}), **params)
        out = {s: [book["cls"](m, **p)] for s, m in markets.items()}
    if book.get("skip"):  # an improved version from tradedesk/study.py: same rules, skips some conditions
        from .study import Filtered
        out = {s: [Filtered(v[0], book["skip"], s)] for s, v in out.items()}
    return out


def _state(pdir, now, rules, active):
    sp = os.path.join(pdir, "start.json")
    st = {}
    if os.path.exists(sp):
        with open(sp, encoding="utf-8") as f:
            st = json.load(f)
    books = st.setdefault("books", {})
    for b in active:  # the first five books started together; every later book starts when it first runs
        if b["id"] not in books:
            seed_slow = st.get("start") and b["id"] in SEED_IDS and b["cadence"] == "slow"
            books[b["id"]] = st["start"] if seed_slow else now - now % (3600 if b["cadence"] == "slow" else 300)
    ids = {b["id"] for b in active}
    for k in [k for k in books if k not in ids]:
        books.pop(k)  # retired by the weekly shake-up
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
    active = roster(state_dir)
    st = _state(pdir, now, rules, active)
    books = [b for b in active if b["cadence"] == cadence]
    if not books:
        return rebuild(state_dir, journal, rules, now)
    gran = 3600 if cadence == "slow" else 300
    first = min(st["books"][b["id"]] for b in books)
    since = None if cadence == "slow" else first - FAST_WARMUP_DAYS * 86400
    markets, stale = _markets(gran, now, fetch, since)
    step = 1 if cadence == "slow" else 3  # stored curve resolution: hourly, or every 15 minutes
    results = []
    for book in books:
        if book.get("report"):
            params, bt = latest_params(book["report"])
        else:
            params, bt = dict(book.get("params") or {}), None
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
               "trades": r["trades"], "protected": bool(book.get("protected")), "added": book.get("added"),
               "screen": book.get("screen")}
        results.append(res)
    live = {b["id"] for b in roster(state_dir)}  # the shake-up may have retired a book while this ran
    for res in results:
        if res["id"] in live:
            with open(os.path.join(pdir, res["id"] + ".json"), "w", encoding="utf-8") as f:
                json.dump(res, f, default=str)
    if stale:
        journal.event("warn", "paper (%s): stale data for %s; signals wait" % (cadence, ",".join(stale)))
    return rebuild(state_dir, journal, rules, now)


def load_book(state_dir, book_id):
    if not book_id or not _SAFE_ID.match(book_id):
        return None
    p = os.path.join(state_dir, "paper", book_id + ".json")
    if not os.path.exists(p):
        return None
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def rebuild(state_dir, journal, rules, now=None):
    """Aggregate all books into the journal (the app's 'All accounts' view) and the paper drawdown halt."""
    now = int(now or time.time())
    books = [x for x in (load_book(state_dir, b["id"]) for b in roster(state_dir)) if x]
    retired = retired_books(state_dir)
    # Owner's choice (2026-11-10): the 'All accounts' balance, chart and trade list show only the accounts
    # still running; a retired account's result is reported separately (retired_pnl). The paper drawdown
    # halt still uses the full record, retired losses included, so retiring a loser never loosens it.
    def pnl_series(group):
        agg = {}
        for bk in group:
            for t, e in bk["curve"]:
                agg.setdefault(int(t) - int(t) % 3600, {})[bk["id"]] = e - bk["start_equity"]
        last, out = {}, []
        for t in sorted(agg):
            last.update(agg[t])
            out.append((t, total0 + sum(last.values())))
        return out

    total0 = sum(bk["start_equity"] for bk in books)
    banked = sum(bk["equity"] - bk["start_equity"] for bk in retired)
    rows = [("closed", bk, x) for bk in books for x in bk["trades"]] + [("open", bk, x) for bk in books for x in bk["open"]]
    series = pnl_series(books)
    total = sum(bk["equity"] for bk in books)
    full = pnl_series(books + retired)
    peak = max([total0] + [e for _, e in full] + [total + banked])
    out = {"t": now, "books": [{k: v for k, v in bk.items() if k not in ("curve", "trades")} for bk in books],
           "total_start": total0, "total_equity": total, "retired_pnl": banked, "retired_count": len(retired),
           "total_with_retired": total + banked,
           "drawdown": (peak - (total + banked)) / peak if peak else 0.0}
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
    for b in roster(state_dir):
        bk = load_book(state_dir, b["id"])
        if not bk:
            continue
        curve = bk["curve"]
        step = max(1, len(curve) // 40)
        spark = [round(e, 2) for _, e in curve[::step]] + ([round(curve[-1][1], 2)] if curve else [])
        wins = [t for t in bk["trades"] if t["pnl"] > 0]
        out.append({"id": b["id"], "name": b["name"], "mode": b["mode"], "cadence": b["cadence"],
                    "note": b.get("note", ""), "start_equity": bk["start_equity"], "equity": bk["equity"],
                    "pnl": bk["pnl"], "pnl_pct": bk["pnl"] / bk["start_equity"] if bk["start_equity"] else 0.0,
                    "open": len(bk["open"]), "closed": bk["closed"], "updated": bk.get("updated"),
                    "unrealized": sum(o["unrealized"] for o in bk["open"]),
                    "win_rate": len(wins) / len(bk["trades"]) if bk["trades"] else None,
                    "spark": spark, "backtest": bk.get("backtest"), "protected": bool(b.get("protected")),
                    "added": b.get("added"), "start": bk.get("start")})
    return out
