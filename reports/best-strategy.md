# Best candidate so far: regime-filtered trend ensemble (daily)

Generated 2026-11-09 by `python research/best_strategy.py` (raw numbers: `best-strategy.json`) and
`python -m tradedesk tournament --gran 3600 --train-days 365 --test-days 90 --tag ensemble --min-train-trades 8 --strategies trend_ensemble`.
Data: Coinbase spot hourly candles, resampled to daily. Costs: 0.06% fee + 0.02% slippage per side, 0.001%/h funding.
Sizing: 1% of equity at risk per trade times the regime multiplier, leverage capped at 3x. Not financial advice.

## The strategy
- **Edge:** trends in crypto persist for weeks to months (herding, slow information spread, leveraged momentum
  flows). Time-series momentum is documented across asset classes over a century. The other side of the trade is
  traders who fade trends early, and late sellers who capitulate into them.
- **Signal:** 5 votes, one per look-back of 20, 40, 60, 90 and 120 days. Each vote is +1 if today's close is above
  the close that many days ago, else -1. The trade is long when the average is ≥ +0.6, short when it is ≤ -0.6,
  and flat in between.
- **Regime filter:** no new entries in CRASH. Half size in SIDEWAYS and JUMPY. Full size in CALM_TREND.
- **Stop:** 3 x the 20-day ATR. **Exit:** when the vote drops below the threshold, or flips.
- **Fitting:** none. The look-backs are the standard 1–6 month horizons from the literature, not tuned on this data.
- **Holding period:** days to weeks. **Frequency:** about 55 trades a year across BTC, ETH and SOL.

## Results: BTC + ETH + SOL portfolio, 2022-03-25 to 2026-11-06 (daily mark-to-market)

| Variant (10 tried) | Trades | Win rate | Profit factor | Return | CAGR | Max DD | Sharpe |
|---|---|---|---|---|---|---|---|
| **Base: long/short, regime filter** | 260 | 32% | 1.90 | +33.1% | +6.4% | 9.4% | 0.70 |
| Long-only | 145 | 30% | 2.26 | +26.3% | +5.2% | 9.1% | 0.62 |
| No regime filter | 281 | 33% | 1.85 | +39.1% | +7.4% | 15.5% | 0.63 |
| Look-backs x0.75 | 289 | 32% | 1.74 | +29.1% | +5.7% | 9.9% | 0.69 |
| Look-backs x1.25 | 200 | 38% | 2.08 | +21.3% | +4.3% | 9.5% | 0.59 |
| Threshold 0.8 | 242 | 34% | 1.93 | +25.0% | +4.9% | 5.8% | 0.86 |
| Stop 2 ATR | 261 | 32% | 1.86 | +54.4% | +9.9% | 12.1% | 0.76 |
| Stop 4 ATR | 259 | 32% | 1.87 | +24.1% | +4.8% | 7.3% | 0.68 |
| Long-only, no regime filter | 147 | 31% | 2.27 | +33.0% | +6.4% | 13.3% | 0.61 |
| *Buy-and-hold, equal weight (no costs)* | – | – | – | +25% | +4.9% | 78% | 0.40 |
| *Buy-and-hold, BTC only* | – | – | – | +64% | +11.3% | 67% | 0.46 |

"Threshold 0.4" gives exactly the base result: with 5 votes the average can only be ±0.2, ±0.6 or ±1. All nearby
settings stay profitable (Sharpe 0.59–0.86), so the result doesn't hang on one exact setting.

**Base, by year:** 2022 +3.0% · 2023 +28.7% · 2024 −4.4% · 2025 +2.1% · 2026 0.0%.
Most of the gain came in 2023, and the last 2.5 years have been roughly flat. This is the weakest point.

**Cost sensitivity (base):** at 1x, 2x and 3x costs, the Sharpe ratio is 0.70, 0.56 and 0.41, and the max drawdown
is 9.4%, 10.3% and 11.7%. At 3x costs it only matches buy-and-hold's Sharpe.

**Longer test, BTC + ETH since 2019:** the strategy made +82% (CAGR 8.9%, Sharpe 0.91, max DD 11%, 248 trades).
Buy-and-hold made +1,149% (CAGR 42.8%, Sharpe 0.87, max DD 76%).
- **Raw return:** buy-and-hold wins by a mile.
- **Risk-adjusted:** they're about level on Sharpe, and the strategy is better on return per unit of drawdown.

## Gate, per coin (walk-forward, train 365 days / test 90)
| Coin | OOS trades | Profit factor | Windows profitable | Bootstrap 5th pct | Result |
|---|---|---|---|---|---|
| ETH | 119 | 3.10 | 68% | +2.3% | **PASS → forward test** |
| BTC | 100 | 4.52 | 55% | +2.1% | near miss → shadow |
| SOL | 73 | 2.49 | 40% | −6.9% | near miss → shadow |

The tournament's drawdown column only counts closed trades, so it understates drawdown (2.7–2.9% there, against
9.4% marked to market above). Fixing the gate to use mark-to-market drawdown is on the roadmap.

## Regime classifier: how often it was right over the next 10 days, against the base rate
| Coin | CALM_TREND | SIDEWAYS | JUMPY | CRASH |
|---|---|---|---|---|
| BTC | 60% vs 53% | 64% vs 69% | 56% vs 41% | 87% vs 86% |
| ETH | 60% vs 54% | 63% vs 68% | 56% vs 42% | 86% vs 82% |
| SOL | 48% vs 47% | 62% vs 66% | 47% vs 36% | 83% vs 83% |

- **JUMPY** and (on BTC and ETH) **CALM_TREND** carry real information.
- **SIDEWAYS** is worse than its base rate.
- **CRASH** adds almost nothing as a forecast. Its value is cutting exposure: the filter cut max drawdown from 15.5% to 9.4% and gave up about 6% of return.

## Kill criteria (stop paper trading this strategy if any happen)
- The portfolio drawdown reaches 15%. The desk halts automatically and needs the owner to resume.
- Profit factor over the last 50 trades falls below 0.9, which triggers a ladder demotion.
- Six months with Sharpe below 0 while buy-and-hold is positive.
