"""Same trend ensemble, same trades, different risk per trade: how return and drawdown scale.

    python research/risk_scaling.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import best_strategy as BS  # noqa: E402
from tradedesk import backtest as B  # noqa: E402
from tradedesk import data as D  # noqa: E402
from tradedesk.market import Market  # noqa: E402


def main():
    mkts, closes = {}, {}
    for s in BS.SYMS:
        mkts[s] = Market(D.load(D.cache_path("data", D.PERPS[s]["spot"], 3600)), s, 3600)
        closes[s] = BS.daily_closes(mkts[s])
    warm = 280
    windows = {
        "BTC+ETH+SOL 2022-03 to 2026-11": (BS.SYMS, max(min(closes[s]) for s in BS.SYMS) + warm),
        "BTC+ETH 2019-10 to 2026-11": (["BTC", "ETH"], min(closes["BTC"]) + warm),
    }
    day1 = min(max(closes[s]) for s in BS.SYMS)
    for label, (syms, day0) in windows.items():
        trades = []
        for s in syms:
            st = BS.S.TrendEnsemble(mkts[s], **BS.BASE)
            for t in B.run(st):
                if t["t0"] // 86400 >= day0:
                    t["sym"] = s
                    trades.append(t)
        bh = BS.stats_from_curve(*BS.buy_hold(closes, syms, day0, day1))
        print("\n%s  (%d trades)  buy-and-hold: CAGR %+.1f%%, max DD %.0f%%, Sharpe %.2f" % (
            label, len(trades), 100 * bh["cagr"], 100 * bh["max_dd"], bh["sharpe"]))
        for risk, lev in ((0.01, 3), (0.02, 3), (0.03, 4), (0.05, 5), (0.08, 8)):
            sim, _ = B.simulate(trades, equity=BS.START_EQ, risk=risk, max_lev=lev)
            st = BS.stats_from_curve(*BS.mtm_curve(sim, closes, day0, day1))
            liq = sum(1 for t in sim if t.get("liquidated"))
            print("  risk %2.0f%%/trade, lev cap %dx: CAGR %+6.1f%%  total %+7.0f%%  max DD %5.1f%%  Sharpe %.2f  liquidations %d" % (
                100 * risk, lev, 100 * st["cagr"], 100 * st["return"], 100 * st["max_dd"], st["sharpe"], liq))


if __name__ == "__main__":
    main()
