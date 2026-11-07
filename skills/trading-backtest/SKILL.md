---
name: trading-backtest
description: Backtest and walk-forward test trading strategies honestly with fees, slippage, funding and leverage, then apply the promotion gate. Use when the user says "backtest this", "run the tournament", "which strategy is best", "is this profitable", "test my strategy", or "what are the odds".
---

# Backtest and tournament

## Run
- All strategies, all coins: `python -m tradedesk tournament`
- Some of them: `python -m tradedesk tournament --symbols ETH,SOL --strategies donchian_1h,mtf_trend`
- Output: `reports/tournament-latest.md` (read it), `reports/tournament-latest.json`, `state/ladder.json`.

## How it scores (tell the user this)
- **Walk-forward:** parameters are picked on 180 days, then scored on the next 60 days the strategy has not seen, stepping forward each time. Only these out-of-sample (OOS) trades count.
- **Costs on every trade:** 0.06% fee and 0.02% slippage each side, plus funding of 0.001% per hour.
- **Fills:** at the next bar's open. If the stop and the target are both inside one bar, the stop wins. A gap past the stop fills at the open.
- **Leverage:** capped at the overnight limits the live desk uses on Coinbase (BTC 3.9x, ETH 3.3x, SOL 1.8x). Liquidation is modeled.
- **Bootstrap:** 2,000 random resamples of the OOS trades give a 5th-percentile return.
- **Gate to move to forward testing (all must pass):**
  - at least 100 OOS trades
  - profit factor of 1.20 or more
  - max drawdown of 20% or less at 1% risk
  - at least 60% of windows profitable
  - bootstrap 5th-percentile return above 0

## Reporting
- Lead with whether anything passed.
- For each near miss, say which check failed and by how much.
- Compare in-sample to OOS results. A big gap means the parameters were curve-fit.
- The backtest uses spot candles because perp history only starts in mid-2025. Say so.

## Never
Edit gates, costs or windows to make a result pass. If the user asks you to, explain why that defeats the test. Record any change they still want in `docs/DECISIONS.md`.
