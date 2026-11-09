# Funding

Coinbase US perp-style futures charge funding hourly (`funding_interval` 3600s on the public product endpoint).

## Model
- **Formula:** $FundingPnL_t = -q_t \cdot M \cdot P_t \cdot f_t$. When the rate is positive, longs pay and
  shorts receive (`tradedesk/portfolio.py`).
- **No historical series:** the public endpoint shows only the **current** rate (for example 0.000006/h on
  BTC on 2026-11-07). There is no free history, so every perp backtest uses an **assumed** 0.001%/h
  against longs, scaled with the cost stress. Reports mark this as an assumption.

## Funding carry (blocked)
- **Next step:** a collector that saves the hourly rate going forward.
- **Collecting doesn't unblock it on its own:** testing carry also needs at least 72 hourly observations
  of real data and a two-leg order executor (spot long + perp short, whole contracts, matched size).
  Until both exist, `funding_carry_research` remains a research hypothesis and is never traded.
