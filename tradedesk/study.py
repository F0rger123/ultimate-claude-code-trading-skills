"""Study the paper accounts: why the winners win, why the losers lose, and improved versions to test.

Paper only. Nothing here changes a running account. A running account keeps its exact rules so its record
stays clean; an improvement is a NEW candidate ("challenger") that must win a fair test before the weekly
shake-up may start it as its own paper account. Real money still needs the owner's yes.

1. Context. Every paper trade is tagged with the market around its signal, using only data available then:
   - session: asia (00-08 UTC), europe (08-13), us (13-21), late (21-24)
   - day: weekday or weekend
   - trend: with or against the 1-hour trend (EMA 50 vs EMA 200)
   - volatility: low, mid or high (1-hour ATR as % of price, ranked against the last 30 days)
   - coin and side
2. Insights. For each account with enough closed trades, the groups that made and lost the most money.
3. Challengers, for accounts that are up:
   - neighbours: the same strategy with one setting changed (from its grid)
   - filters: the same strategy skipping a group where its PAPER trades lost money
   Each challenger is judged against its parent on the period BEFORE the parent started paper trading, so an
   idea found in the paper trades is never scored on the trades that suggested it. A challenger qualifies only
   if it beats the parent's score by MIN_GAIN points and (for filters) keeps at least MIN_KEEP of its trades.
"""
import json
import os
import time

from . import indicators as I
from . import paper as PA
from . import portfolio as P

H1 = 3600
DAY = 86400
MIN_TRADES = 8      # closed paper trades before an account is studied
MIN_GROUP = 4       # trades in a group before it can produce an insight or a filter
MIN_GAIN = 1.0      # score points a challenger must add over its parent
MIN_KEEP = 0.6      # share of the parent's trades a filtered challenger must keep
MAX_FILTERS = 3
MAX_NEIGHBOURS = 4
FIELDS = ("session", "day", "trend", "volatility", "coin", "side")
LABELS = {"session": {"asia": "during Asia hours", "europe": "during Europe hours", "us": "during US hours",
                       "late": "during late US hours"},
          "day": {"weekday": "on weekdays", "weekend": "on weekends"},
          "trend": {"with": "trading with the 1h trend", "against": "trading against the 1h trend"},
          "volatility": {"low": "in calm markets", "mid": "in normal volatility", "high": "in jumpy markets"},
          "side": {"long": "on longs", "short": "on shorts"}}


def label(field, value):
    if field == "coin":
        return "on %s" % value
    return LABELS.get(field, {}).get(value, str(value))


# ---------------------------------------------------------------- 1. context
def _h1(m):
    h = m.frame(H1)
    e50 = h.memo(("ema", 50), lambda: I.ema(h.c, 50))
    e200 = h.memo(("ema", 200), lambda: I.ema(h.c, 200))
    a = h.memo(("atr", 14), lambda: I.atr(h.h, h.l, h.c, 14))
    rk = h.memo(("atrpct_rank", 720), lambda: I.percentile_rank(
        [None if a[k] is None or not h.c[k] else a[k] / h.c[k] for k in range(len(a))], 720))
    return e50, e200, rk


def context(m, i, side, sym):
    """Market context at base bar i (the signal bar), from closed bars only."""
    e50, e200, rk = _h1(m)
    t = m.b.t[i]
    hr = (t // 3600) % 24
    x50, x200, r = m.at(H1, e50, i), m.at(H1, e200, i), m.at(H1, rk, i)
    return {
        "session": "asia" if hr < 8 else "europe" if hr < 13 else "us" if hr < 21 else "late",
        "day": "weekend" if (t // DAY + 3) % 7 >= 5 else "weekday",  # 0 = Monday
        "trend": None if x50 is None or x200 is None else ("with" if (x50 > x200) == (side == 1) else "against"),
        "volatility": None if r is None else ("low" if r < 0.33 else "mid" if r < 0.67 else "high"),
        "coin": sym,
        "side": "long" if side == 1 else "short",
    }


class Filtered:
    """A strategy that skips entries whose context matches any skip rule. Same entry/exit/max_bars surface
    as the strategy it wraps, so the portfolio engine treats it like any other strategy."""

    def __init__(self, inner, skip, sym):
        self.inner, self.skip, self.sym = inner, skip, sym
        self.max_bars = inner.max_bars

    def entry(self, i):
        sig = self.inner.entry(i)
        if sig is None:
            return None
        c = context(self.inner.m, i, sig["side"], self.sym)
        if any(c.get(r["field"]) == r["value"] for r in self.skip):
            return None
        return sig

    def exit(self, i, pos):
        return self.inner.exit(i, pos)

    def __getattr__(self, k):
        return getattr(self.inner, k)


# ---------------------------------------------------------------- 2. insights
def tag_trades(bk, markets):
    """Context for each closed paper trade (signal bar = the bar before the fill)."""
    out = []
    for x in bk.get("trades", []):
        m = markets.get(x["sym"])
        if m is None:
            continue
        t = int(x["t0"])
        i = _index(m, t)
        if i is None or i < 1:
            continue
        out.append((context(m, i - 1, x["side"], x["sym"]), x["pnl"]))
    return out


def _index(m, t):
    ts = m.b.t
    lo, hi = 0, len(ts) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if ts[mid] == t:
            return mid
        if ts[mid] < t:
            lo = mid + 1
        else:
            hi = mid - 1
    return None


def groups(tagged):
    g = {}
    for ctx, pnl in tagged:
        for f in FIELDS:
            v = ctx.get(f)
            if v is None:
                continue
            s = g.setdefault((f, v), {"n": 0, "wins": 0, "pnl": 0.0})
            s["n"] += 1
            s["wins"] += pnl > 0
            s["pnl"] += pnl
    return g


def insights(bk, tagged):
    """Plain-English lines: where the account makes and loses money."""
    if len(tagged) < MIN_TRADES:
        return []
    g = [(k, v) for k, v in groups(tagged).items() if v["n"] >= MIN_GROUP]
    if not g:
        return []
    best = max(g, key=lambda kv: kv[1]["pnl"])
    worst = min(g, key=lambda kv: kv[1]["pnl"])
    out = []
    if best[1]["pnl"] > 0:
        out.append("%s makes its money %s: %+.0f dollars over %d trades, %d won." % (
            bk["name"], label(*best[0]), best[1]["pnl"], best[1]["n"], best[1]["wins"]))
    if worst[1]["pnl"] < 0 and worst[0] != best[0]:
        out.append("%s loses %s: %+.0f dollars over %d trades, %d won." % (
            bk["name"], label(*worst[0]), worst[1]["pnl"], worst[1]["n"], worst[1]["wins"]))
    return out


# ---------------------------------------------------------------- 3. challengers
def _score(cls, params, cadence, markets, start, end, skip=None):
    b = {"id": "study", "cls": cls, "mode": "perp", "equity": 10000.0, "cadence": cadence, "params": params}
    if skip:
        b["skip"] = skip
    from . import rotation as ROT  # sizes and spot-only rules live in rotation
    b["mode"] = "spot" if cls.id in ROT.SPOT_ONLY else "perp"
    b.update(ROT.SIZE.get(cls.id, {}))
    try:
        r = P.run(markets, PA._variants(markets, b, params), PA._cfg(b), start_t=start, end_t=end, close_at_end=True)
    except Exception as e:
        return {"error": str(e)[:200]}
    curve = r["curve"]
    if not curve:
        return None
    peak, mdd = b["equity"], 0.0
    for _, e in curve:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak else 0.0)
    ret = 100.0 * (curve[-1][1] - b["equity"]) / b["equity"]
    return {"ret_pct": round(ret, 2), "max_dd_pct": round(100 * mdd, 2), "trades": len(r["trades"]),
            "score": round(ret - 0.5 * 100 * mdd, 2)}


def challengers(spec, bk, tagged, markets, window_days, log=print):
    """Improved versions of one account, judged on the period before it started paper trading."""
    cls, cadence = spec["cls"], spec["cadence"]
    params = dict(spec.get("params") or {})
    if spec.get("report"):
        params, _ = PA.latest_params(spec["report"])
    base_skip = list(spec.get("skip") or [])
    end = int(bk["start"])
    start = end - window_days * DAY
    parent = _score(cls, params, cadence, markets, start, end, base_skip)
    if not parent or "error" in parent or parent["trades"] == 0:
        return [], parent
    out = []
    # neighbours: one setting changed
    grid = {k: list(v) for k, v in (getattr(cls, "grid", {}) or {}).items()}
    for k, vs in (getattr(cls, "improve", {}) or {}).items():  # researched one-change improvements
        grid[k] = list(dict.fromkeys(grid.get(k, []) + list(vs)))
    full = dict(getattr(cls, "defaults", {}), **params)
    n, cap = 0, MAX_NEIGHBOURS + 2 * len(getattr(cls, "improve", {}) or {})
    for k in sorted(grid):
        for v in grid[k]:
            if full.get(k) == v or n >= cap:
                continue
            p2 = dict(params, **{k: v})
            s = _score(cls, p2, cadence, markets, start, end, base_skip)
            n += 1
            if s and "error" not in s and s["trades"] and s["score"] >= parent["score"] + MIN_GAIN:
                out.append({"kind": "setting", "params": p2, "skip": base_skip,
                            "why": "%s %s instead of %s" % (k.replace("_", " "), v, full.get(k)), "test": s})
    # filters: skip a group where the paper trades lost money
    if len(tagged) >= MIN_TRADES:
        bad = sorted([(k, v) for k, v in groups(tagged).items() if v["n"] >= MIN_GROUP and v["pnl"] < 0],
                     key=lambda kv: kv[1]["pnl"])[:MAX_FILTERS]
        for (f, val), st in bad:
            if f == "coin" and len({c.get("coin") for c, _ in tagged}) <= 1:
                continue
            skip = base_skip + [{"field": f, "value": val}]
            s = _score(cls, params, cadence, markets, start, end, skip)
            if (s and "error" not in s and s["score"] >= parent["score"] + MIN_GAIN
                    and s["trades"] >= MIN_KEEP * parent["trades"]):
                out.append({"kind": "filter", "params": params, "skip": skip,
                            "why": "skips %s (paper: %+.0f dollars over %d trades)" % (label(f, val), st["pnl"], st["n"]),
                            "test": s})
    for c in out:
        log("  challenger %-26s %-40s %+.2f vs parent %+.2f" % (spec["id"], c["why"][:40], c["test"]["score"], parent["score"]))
    return out, parent


# ---------------------------------------------------------------- the study run
def path(state_dir):
    return os.path.join(state_dir, "paper", "study.json")


def load(state_dir):
    p = path(state_dir)
    if not os.path.exists(p):
        return None
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def run(state_dir, now=None, log=print, markets_for=None, with_challengers=True):
    """Study every account (active and retired). Writes paper/study.json and returns it."""
    from . import rotation as ROT
    now = int(now or time.time())
    roster = {b["id"]: b for b in PA.roster(state_dir)}
    books = [PA.load_book(state_dir, i) for i in roster] + PA.retired_books(state_dir)
    books = [b for b in books if b]
    markets = {}

    def mk(cadence):
        if cadence not in markets:
            if markets_for:
                markets[cadence] = markets_for(cadence)
            else:
                gran = 300 if cadence == "fast" else 3600
                first = min([b["start"] for b in books if b.get("cadence", "slow") == cadence] or [now])
                window = ROT.SCREEN[cadence][0]
                since = first - (window + PA.FAST_WARMUP_DAYS) * DAY if cadence == "fast" else None
                markets[cadence] = PA._markets(gran, now, True, since)[0]
        return markets[cadence]

    out = {"t": now, "accounts": [], "insights": [], "challengers": []}
    for bk in books:
        cad = bk.get("cadence", "slow")
        tagged = tag_trades(bk, mk(cad)) if bk.get("trades") else []
        g = groups(tagged)
        acc = {"id": bk["id"], "name": bk["name"], "cadence": cad, "retired": bool(bk.get("retired")),
               "trades": len(bk.get("trades", [])), "pnl": round(bk["pnl"], 2),
               "groups": [{"field": f, "value": v, "label": label(f, v), "n": s["n"], "wins": s["wins"],
                           "pnl": round(s["pnl"], 2)} for (f, v), s in sorted(g.items())]}
        lines = insights(bk, tagged)
        acc["insights"] = lines
        out["accounts"].append(acc)
        if not bk.get("retired"):
            out["insights"] += lines
        spec = roster.get(bk["id"])
        if with_challengers and spec and not spec.get("protected") and bk["pnl"] > 0:
            cs, parent = challengers(spec, bk, tagged, mk(cad), ROT.SCREEN[cad][0], log)
            for c in cs:
                out["challengers"].append(dict(c, parent=bk["id"], parent_name=bk["name"], cls=spec["cls"].id,
                                               cadence=cad, parent_test=parent))
    os.makedirs(os.path.dirname(path(state_dir)), exist_ok=True)
    with open(path(state_dir) + ".tmp", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, default=str)
    os.replace(path(state_dir) + ".tmp", path(state_dir))
    for line in out["insights"]:
        log(line)
    log("%d challengers qualified" % len(out["challengers"]))
    return out
