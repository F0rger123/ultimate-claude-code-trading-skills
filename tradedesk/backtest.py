"""Bar-by-bar backtester and the equity simulator.

run() produces trades in price-return terms (size-free). simulate() sizes them from equity,
risk per trade and the leverage cap, and applies liquidation. Splitting the two keeps
walk-forward fast: each parameter set is run once over the full history.
"""
import math
import random

COSTS = {"fee": 0.0006, "slip": 0.0002, "funding_per_h": 0.00001}


def run(strat, start=0, end=None, costs=None, entry_filter=None):
    """Return a list of trades. A trade's `ret` is its net return per unit of entry price:
    positive = profit. `d` is the stop distance as a fraction of entry. R = ret / d."""
    k = dict(COSTS)
    k.update(costs or {})
    b = strat.m.b
    n = len(b.t) if end is None else min(end, len(b.t))
    trades = []
    pos = None
    pending = None  # entry signal from the previous bar's close
    exit_next = False
    i = max(1, start)
    while i < n:
        o, h, l, c = b.o[i], b.h[i], b.l[i], b.c[i]
        if pending is not None and pos is None:
            sig = pending
            pending = None
            side = sig["side"]
            px = o * (1 + side * k["slip"])
            stop, tgt = sig["stop"], sig.get("target")
            if (side == 1 and stop < px and (tgt is None or tgt > px)) or \
               (side == -1 and stop > px and (tgt is None or tgt < px)):
                pos = {"side": side, "entry": px, "stop": stop, "target": tgt, "i0": i,
                       "t0": b.t[i], "mae": 0.0, "mfe": 0.0, "feat": sig.get("feat", {})}
        if pos is not None:
            side, e = pos["side"], pos["entry"]
            xp = None
            why = None
            if exit_next:
                xp, why = o, "signal"
                exit_next = False
            else:
                if side == 1:
                    if o <= pos["stop"]:
                        xp, why = o, "stop_gap"
                    elif l <= pos["stop"]:
                        xp, why = pos["stop"], "stop"
                    elif pos["target"] is not None and o >= pos["target"]:
                        xp, why = o, "target"
                    elif pos["target"] is not None and h >= pos["target"]:
                        xp, why = pos["target"], "target"
                    pos["mae"] = max(pos["mae"], (e - l) / e)
                    pos["mfe"] = max(pos["mfe"], (h - e) / e)
                else:
                    if o >= pos["stop"]:
                        xp, why = o, "stop_gap"
                    elif h >= pos["stop"]:
                        xp, why = pos["stop"], "stop"
                    elif pos["target"] is not None and o <= pos["target"]:
                        xp, why = o, "target"
                    elif pos["target"] is not None and l <= pos["target"]:
                        xp, why = pos["target"], "target"
                    pos["mae"] = max(pos["mae"], (h - e) / e)
                    pos["mfe"] = max(pos["mfe"], (e - l) / e)
            if xp is not None:
                trades.append(_close(pos, xp, why, b.t[i], k))
                pos = None
            else:
                mb = strat.max_bars
                if strat.exit(i, pos) or (mb and i - pos["i0"] >= mb):
                    exit_next = True
        if pos is None and pending is None and i < n - 1:
            sig = strat.entry(i)
            if sig is not None:
                sig["feat"] = strat.features(i)
                if entry_filter is None or entry_filter(sig["feat"], sig):
                    pending = sig
        i += 1
    return trades


def _close(pos, xp, why, t1, k):
    side, e = pos["side"], pos["entry"]
    xp_eff = xp * (1 - side * k["slip"])
    gross = side * (xp_eff - e) / e
    hours = max(0.0, (t1 - pos["t0"]) / 3600.0)
    cost = 2 * k["fee"] + hours * k["funding_per_h"]
    d = abs(e - pos["stop"]) / e
    ret = gross - cost
    return {"side": side, "t0": pos["t0"], "t1": t1, "entry": e, "exit": xp_eff, "stop": pos["stop"],
            "why": why, "d": d, "ret": ret, "R": ret / d if d > 0 else 0.0, "mae": pos["mae"],
            "mfe": pos["mfe"], "hours": hours, "feat": pos["feat"]}


def simulate(trades, equity=1000.0, risk=0.01, max_lev=10.0, mm=0.5):
    """Size each trade at `risk` of current equity at the stop, capped at max_lev x equity.
    Margin is isolated and posted at max_lev (margin = notional / max_lev), as the live desk does.
    A trade whose adverse move reaches mm / max_lev before its exit is liquidated: it loses its margin."""
    eq = equity
    curve = [(trades[0]["t0"] if trades else 0, eq)]
    out = []
    for tr in sorted(trades, key=lambda x: x["t0"]):
        notional = min(risk * eq / tr["d"], max_lev * eq) if tr["d"] > 0 else 0.0
        lev = notional / eq if eq > 0 else 0.0
        liq = notional > 0 and tr["mae"] >= mm / max_lev
        pnl = -notional / max_lev if liq else notional * tr["ret"]
        eq += pnl
        out.append(dict(tr, notional=notional, lev=lev, pnl=pnl, liquidated=liq, equity=eq))
        curve.append((tr["t1"], eq))
        if eq <= 0:
            break
    return out, curve


def metrics(trades, curve=None, start_equity=1000.0):
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    rs = [t["R"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gw, gl = sum(wins), -sum(losses)
    m = {
        "trades": n,
        "win_rate": len(wins) / n,
        "avg_R": sum(rs) / n,
        "profit_factor": gw / gl if gl > 0 else float("inf"),
        "avg_win_R": gw / len(wins) if wins else 0.0,
        "avg_loss_R": -gl / len(losses) if losses else 0.0,
        "longest_losing_streak": _streak(rs),
        "avg_hours": sum(t["hours"] for t in trades) / n,
        "long_share": sum(1 for t in trades if t["side"] == 1) / n,
    }
    if curve:
        peak = curve[0][1]
        mdd = 0.0
        for _, e in curve:
            peak = max(peak, e)
            mdd = max(mdd, (peak - e) / peak if peak > 0 else 0)
        m["return"] = curve[-1][1] / start_equity - 1
        m["max_drawdown"] = mdd
        days = max(1.0, (curve[-1][0] - curve[0][0]) / 86400)
        m["days"] = days
        m["cagr"] = (curve[-1][1] / start_equity) ** (365 / days) - 1 if curve[-1][1] > 0 else -1.0
        m["liquidations"] = sum(1 for t in trades if t.get("liquidated"))
    return m


def _streak(rs):
    best = cur = 0
    for r in rs:
        cur = cur + 1 if r <= 0 else 0
        best = max(best, cur)
    return best


def monte_carlo(trades, runs=2000, risk=0.01, max_lev=10.0, mm=0.5, seed=7):
    """Bootstrap: draw the same number of trades at random, with replacement, 2,000 times.
    Returns the 5th-percentile and median return and the 95th-percentile drawdown."""
    if len(trades) < 10:
        return {"runs": 0}
    rnd = random.Random(seed)
    rets, dds = [], []
    n = len(trades)
    for _ in range(runs):
        eq = peak = 1.0
        mdd = 0.0
        for _k in range(n):
            t = trades[rnd.randrange(n)]
            notional = min(risk * eq / t["d"], max_lev * eq) if t["d"] > 0 else 0
            liq = notional > 0 and t["mae"] >= mm / max_lev
            eq += -notional / max_lev if liq else notional * t["ret"]
            if eq <= 0:
                eq, mdd = 0.0, 1.0
                break
            peak = max(peak, eq)
            mdd = max(mdd, (peak - eq) / peak)
        rets.append(eq - 1)
        dds.append(mdd)
    rets.sort()
    dds.sort()
    return {"runs": runs, "p5_return": rets[int(0.05 * runs)], "median_return": rets[runs // 2],
            "p95_drawdown": dds[int(0.95 * runs)]}


def sharpe_daily(curve):
    if len(curve) < 3:
        return 0.0
    by_day = {}
    for t, e in curve:
        by_day[t // 86400] = e
    days = sorted(by_day)
    r = [by_day[b] / by_day[a] - 1 for a, b in zip(days, days[1:]) if by_day[a] > 0]
    if len(r) < 2:
        return 0.0
    mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
    return mu / sd * math.sqrt(365) if sd > 0 else 0.0
