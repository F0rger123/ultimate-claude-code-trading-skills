"""Reproducible study of the regime-filtered trend ensemble against buy-and-hold.

Run from the repo root (needs the hourly data: python -m tradedesk data --gran 3600 --days 2870):
    python research/best_strategy.py
Writes reports/best-strategy.md and reports/best-strategy.json. Every number in the report comes from this file.
"""
import json
import math
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradedesk import backtest as B  # noqa: E402
from tradedesk import data as D  # noqa: E402
from tradedesk import regime as RG  # noqa: E402
from tradedesk import strategies as S  # noqa: E402
from tradedesk.market import Market  # noqa: E402

SYMS = ["BTC", "ETH", "SOL"]
RISK = 0.01
MAX_LEV = 3.0
START_EQ = 10000.0
BASE = dict(S.TrendEnsemble.defaults)

VARIANTS = [
    ("base: long/short, regime filter", {}),
    ("long-only", {"long_only": 1}),
    ("no regime filter", {"regime": 0}),
    ("look-backs x0.75", {"lookbacks": (15, 30, 45, 68, 90)}),
    ("look-backs x1.25", {"lookbacks": (25, 50, 75, 112, 150)}),
    ("threshold 0.4", {"thr": 0.4}),
    ("threshold 0.8", {"thr": 0.8}),
    ("stop 2 ATR", {"stop_atr": 2.0}),
    ("stop 4 ATR", {"stop_atr": 4.0}),
    ("long-only, no regime filter", {"long_only": 1, "regime": 0}),
]


def daily_closes(mkt):
    f = mkt.frame(86400)
    return {t // 86400: c for t, c in zip(f.t, f.c)}


def mtm_curve(sim, closes_by_sym, day0, day1, start=START_EQ):
    """Daily mark-to-market equity: realized P&L of closed trades plus open trades at each day's close."""
    days = list(range(day0, day1 + 1))
    eq = []
    for d in days:
        e = start
        for tr in sim:
            d0, d1 = tr["t0"] // 86400, tr["t1"] // 86400
            if d1 <= d:
                e += tr["pnl"]
            elif d0 <= d:
                c = closes_by_sym[tr["sym"]].get(d)
                if c is not None:
                    e += tr["notional"] * tr["side"] * (c / tr["entry"] - 1)
        eq.append(e)
    return days, eq


def stats_from_curve(days, eq):
    rets = [eq[k] / eq[k - 1] - 1 for k in range(1, len(eq)) if eq[k - 1] > 0]
    mu = sum(rets) / len(rets) if rets else 0
    sd = math.sqrt(sum((r - mu) ** 2 for r in rets) / max(1, len(rets) - 1)) if rets else 0
    peak, mdd = eq[0], 0.0
    for e in eq:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak > 0 else 0)
    yrs = max(1e-9, (days[-1] - days[0]) / 365.0)
    return {"return": eq[-1] / eq[0] - 1, "cagr": (eq[-1] / eq[0]) ** (1 / yrs) - 1 if eq[-1] > 0 else -1,
            "sharpe": mu / sd * math.sqrt(365) if sd > 0 else 0.0, "max_dd": mdd,
            "calmar": ((eq[-1] / eq[0]) ** (1 / yrs) - 1) / mdd if mdd > 0 else None}


def buy_hold(closes_by_sym, syms, day0, day1):
    """Equal-weight, rebalanced daily, no costs (flatters buy-and-hold slightly)."""
    days, eq, e = [], [], START_EQ
    for d in range(day0, day1 + 1):
        if d > day0:
            rs = [closes_by_sym[s].get(d) / closes_by_sym[s].get(d - 1) - 1 for s in syms
                  if closes_by_sym[s].get(d) and closes_by_sym[s].get(d - 1)]
            if rs:
                e *= 1 + sum(rs) / len(rs)
        days.append(d)
        eq.append(e)
    return days, eq


def run_variant(mkts, params, costs=None, syms=SYMS, day0=None):
    trades = []
    for s in syms:
        st = S.TrendEnsemble(mkts[s], **dict(BASE, **params))
        for t in B.run(st, costs=costs):
            if day0 is None or t["t0"] // 86400 >= day0:
                t["sym"] = s
                trades.append(t)
    sim, _ = B.simulate(trades, equity=START_EQ, risk=RISK, max_lev=MAX_LEV)
    return trades, sim


def by_year(days, eq):
    out = {}
    for d, e in zip(days, eq):
        y = time.gmtime(d * 86400).tm_year
        out.setdefault(y, [e, e])
        out[y][1] = e
    return {y: v[1] / v[0] - 1 for y, v in sorted(out.items())}


def main():
    t0 = time.time()
    mkts, closes = {}, {}
    for s in SYMS:
        bars = D.load(D.cache_path("data", D.PERPS[s]["spot"], 3600))
        mkts[s] = Market(bars, s, 3600)
        closes[s] = daily_closes(mkts[s])
    # Common window: from the first day every coin has a full warm-up (150 days of look-back + regime year).
    warm = 150 + 130
    day0 = max(min(closes[s]) for s in SYMS) + warm
    day1 = min(max(closes[s]) for s in SYMS)
    btc_day0 = min(closes["BTC"]) + warm

    out = {"window": [time.strftime("%Y-%m-%d", time.gmtime(day0 * 86400)),
                      time.strftime("%Y-%m-%d", time.gmtime(day1 * 86400))],
           "variants_tried": len(VARIANTS), "variants": [], "costs": [], "regime": {}}

    bh_days, bh_eq = buy_hold(closes, SYMS, day0, day1)
    out["buy_hold_equal_weight"] = stats_from_curve(bh_days, bh_eq)
    bd, be = buy_hold(closes, ["BTC"], day0, day1)
    out["buy_hold_btc"] = stats_from_curve(bd, be)

    for name, params in VARIANTS:
        trades, sim = run_variant(mkts, params, day0=day0)
        days, eq = mtm_curve(sim, closes, day0, day1)
        m = B.metrics(sim)
        row = {"name": name, "params": params, "trades": m.get("trades", 0), "win_rate": m.get("win_rate"),
               "profit_factor": m.get("profit_factor"), "avg_R": m.get("avg_R")}
        row.update(stats_from_curve(days, eq))
        if name.startswith("base"):
            row["by_year"] = by_year(days, eq)
            out["base_curve_points"] = len(eq)
        out["variants"].append(row)
        print("%-30s trades %4d  PF %5.2f  ret %+7.1f%%  DD %5.1f%%  Sharpe %.2f" % (
            name, row["trades"], row["profit_factor"] or 0, 100 * row["return"], 100 * row["max_dd"], row["sharpe"]))

    for mult in (1, 2, 3):
        k = {"fee": 0.0006 * mult, "slip": 0.0002 * mult, "funding_per_h": 0.00001 * mult}
        _, sim = run_variant(mkts, {}, costs=k, day0=day0)
        days, eq = mtm_curve(sim, closes, day0, day1)
        st = stats_from_curve(days, eq)
        st["cost_multiple"] = mult
        out["costs"].append(st)

    # Longer test where data allows: BTC and ETH from 2019 (SOL starts mid-2021).
    _, sim = run_variant(mkts, {}, syms=["BTC", "ETH"], day0=btc_day0)
    days, eq = mtm_curve(sim, closes, btc_day0, day1)
    out["btc_eth_since_2019"] = stats_from_curve(days, eq)
    out["btc_eth_since_2019"]["trades"] = len(sim)
    bd, be = buy_hold(closes, ["BTC", "ETH"], btc_day0, day1)
    out["btc_eth_buy_hold_since_2019"] = stats_from_curve(bd, be)

    for s in SYMS:
        f = mkts[s].frame(86400)
        labels = RG.classify(f.c, f.h)
        ev = RG.evaluate(f.c, labels)
        out["regime"][s] = ev
    out["secs"] = round(time.time() - t0, 1)
    os.makedirs("reports", exist_ok=True)
    with open("reports/best-strategy.json", "w", encoding="utf-8") as fh:
        json.dump(out, fh, indent=1, default=str)
    print(json.dumps({k: out[k] for k in ("window", "buy_hold_equal_weight", "buy_hold_btc", "costs",
                                           "btc_eth_since_2019", "btc_eth_buy_hold_since_2019", "regime")},
                     indent=1, default=str))


if __name__ == "__main__":
    main()
