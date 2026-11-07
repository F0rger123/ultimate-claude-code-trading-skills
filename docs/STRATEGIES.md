# Strategies

All of them trade long and short on closed bars, and use the same cost model. Code: `tradedesk/strategies.py`.
The entries are sorted by family. For the latest scores, see `reports/tournament-latest.md`.

## The owner's multi-timeframe alignment
The owner reads one buy/sell indicator on the 1h, 30m, 15m and 5m charts, plus volume. The higher timeframes set the
direction, the lower ones time the entry, and a fresh higher-timeframe signal counts for more. Until the real
TradingView indicator is named, SuperTrend(10, 3) stands in for it (`indicators.signal_line`).

| id | Entry | Exit | Stop |
|---|---|---|---|
| `mtf_quick` | the bar where 1h, 30m, 15m and 5m all agree; 5m volume ≥ k x its 20-bar average | the 15m signal flips | k x 15m ATR |
| `mtf_swing` | the 30m close where 1h and 30m start agreeing | the 30m signal flips | k x 30m ATR |
| `mtf_trend` | the 1h close where 4h and 1h start agreeing | the 1h signal flips | k x 1h ATR |

The context saved with every trade includes `htf_age_h`, the age of the higher-timeframe signal. The learning loop
uses it to test the owner's idea that fresh higher-timeframe signals work better.

## Trend following
| id | Rule |
|---|---|
| `donchian_breakout` / `donchian_1h` / `donchian_4h` | close beyond the prior n-bar high or low, 1h EMA50 vs EMA200 agreeing; exit on the n/2 channel; stop k x ATR |
| `ema_pullback` / `ema_pullback_1h` | trend EMA50 > EMA200; the bar dips to the 20 EMA and closes back beyond it; 2R target |

## Intraday and mean reversion
| id | Rule |
|---|---|
| `vwap_reclaim` | 13:00–20:00 UTC; with the 1h trend, the 5m close crosses back over the daily VWAP on volume; 2R target; flat at the UTC day end |
| `rsi2_reversion` | 15m RSI(2) < 10 (or > 90) in the direction of the 1h EMA200 trend; exit on the 5-bar average or after 12 bars |

## Slow trend following (daily / 4h)
| id | Rule |
|---|---|
| `tsmom_daily` | long if the daily close is above the close n days ago, short if below; flips with the sign |
| `turtle_daily` | close beyond the prior n-day high or low; exit on the n/2-day opposite channel; 2-3 ATR stop |
| `ema_cross_4h` | 4h EMA(fast) vs EMA(4 x fast); long or short with the cross |

Each also runs long-only, since crypto has tended to drift up.

## What the first tournament (2026-11-07) taught
- On 5m and 15m entries, round-trip costs (about 0.16% plus funding) are 0.2–0.5R per trade against stops near 0.5%.
  The raw edge before costs was only about +0.03R, so every fast strategy lost money after costs.
- Slower versions (1h and 4h) cut costs to under 0.1R per trade. Trend breakouts on ETH and SOL came out positive out
  of sample, but none passed every check in the gate.
- Mean reversion (RSI2) lost badly on all three coins after costs.
