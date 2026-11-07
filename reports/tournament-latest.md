# Strategy tournament

Generated 2026-11-07 18:40 UTC. Out-of-sample (walk-forward: train 180 days, test 60 days) results only.
Costs: 0.06% fee and 0.02% slippage per side, funding 0.001%/hour. Sizing: 1.0% risk per trade, leverage capped at the live desk's per-coin cap (BTC 3.9x, ETH 3.3x, SOL 1.8x). Data: Coinbase spot 5-minute candles (perp history is too short), so perp basis and real funding are approximated.

Not financial advice. Past results do not predict future results.

| Symbol | Strategy | OOS trades | Win rate | Avg R | Profit factor | Return | Max DD | Bootstrap 5th-pct return | Gate |
|---|---|---|---|---|---|---|---|---|---|
| ETH | donchian_1h | 111 | 26% | +0.215 | 1.31 | +21.2% | 24.5% | -23.5% | fail |
| ETH | donchian_4h | 66 | 30% | +0.173 | 1.29 | +10.1% | 11.7% | -15.9% | fail |
| SOL | donchian_1h | 156 | 29% | +0.171 | 1.27 | +21.4% | 19.9% | -29.9% | fail |
| ETH | mtf_trend | 292 | 29% | +0.052 | 1.09 | +7.2% | 32.2% | -42.8% | fail |
| SOL | mtf_trend | 282 | 30% | +0.047 | 1.08 | +6.7% | 20.6% | -40.3% | fail |
| SOL | donchian_breakout | 419 | 27% | +0.009 | 1.01 | -5.3% | 28.4% | -56.0% | fail |
| SOL | donchian_4h | 74 | 32% | +0.000 | 1.00 | -1.2% | 14.2% | -21.1% | fail |
| BTC | mtf_trend | 224 | 33% | -0.007 | 0.99 | -4.4% | 20.8% | -34.1% | fail |
| ETH | mtf_quick | 851 | 29% | -0.039 | 0.94 | -43.1% | 65.0% | -80.1% | fail |
| ETH | donchian_breakout | 501 | 26% | -0.050 | 0.93 | -35.2% | 52.7% | -75.4% | fail |
| SOL | mtf_swing | 540 | 28% | -0.051 | 0.92 | -37.5% | 57.5% | -70.4% | fail |
| BTC | donchian_1h | 154 | 25% | -0.060 | 0.90 | -12.1% | 21.0% | -40.5% | fail |
| BTC | donchian_4h | 71 | 32% | -0.071 | 0.87 | -5.7% | 9.9% | -23.2% | fail |
| SOL | ema_pullback_1h | 389 | 34% | -0.082 | 0.88 | -30.2% | 35.4% | -55.7% | fail |
| BTC | ema_pullback_1h | 317 | 32% | -0.099 | 0.85 | -29.3% | 36.8% | -53.5% | fail |
| SOL | rsi2_reversion | 1326 | 50% | -0.111 | 0.46 | -77.1% | 77.2% | -82.5% | fail |
| ETH | mtf_swing | 512 | 28% | -0.112 | 0.84 | -48.9% | 60.9% | -74.3% | fail |
| SOL | ema_pullback | 1264 | 32% | -0.123 | 0.84 | -80.7% | 83.3% | -92.1% | fail |
| BTC | mtf_swing | 541 | 29% | -0.155 | 0.72 | -59.4% | 65.7% | -76.2% | fail |
| ETH | rsi2_reversion | 1315 | 43% | -0.158 | 0.34 | -87.5% | 87.5% | -90.6% | fail |
| ETH | ema_pullback_1h | 385 | 28% | -0.185 | 0.76 | -53.2% | 59.9% | -71.1% | fail |
| BTC | rsi2_reversion | 1309 | 35% | -0.197 | 0.24 | -92.2% | 92.2% | -94.0% | fail |
| SOL | mtf_quick | 806 | 26% | -0.207 | 0.71 | -80.2% | 81.2% | -90.4% | fail |
| ETH | ema_pullback | 1242 | 30% | -0.211 | 0.74 | -93.4% | 94.2% | -97.2% | fail |
| BTC | mtf_quick | 653 | 26% | -0.224 | 0.71 | -79.6% | 83.0% | -91.4% | fail |
| SOL | vwap_reclaim | 301 | 36% | -0.238 | 0.69 | -46.5% | 47.8% | -61.7% | fail |
| BTC | donchian_breakout | 482 | 22% | -0.247 | 0.69 | -71.0% | 71.4% | -84.7% | fail |
| BTC | vwap_reclaim | 330 | 38% | -0.322 | 0.61 | -62.3% | 62.8% | -74.4% | fail |
| ETH | vwap_reclaim | 321 | 32% | -0.332 | 0.59 | -65.6% | 65.6% | -76.5% | fail |
| BTC | ema_pullback | 1229 | 29% | -0.334 | 0.62 | -98.4% | 98.5% | -99.3% | fail |

## Gate detail

### BTC / mtf_quick (4-TF alignment (quick))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 2.5, "vol_k": 1.2}`. In-sample best (for comparison, not used): 753 trades, avg R -0.206.

- [x] OOS trades >= 100: 653
- [ ] profit factor >= 1.20: 0.71
- [ ] max drawdown <= 20% at 1% risk: 83.0%
- [ ] >= 60% of OOS windows profitable: 11%
- [ ] bootstrap 5th-pct return > 0: -91.4%

### BTC / mtf_swing (1h + 30m alignment (swing))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 3.5}`. In-sample best (for comparison, not used): 614 trades, avg R -0.108.

- [x] OOS trades >= 100: 541
- [ ] profit factor >= 1.20: 0.72
- [ ] max drawdown <= 20% at 1% risk: 65.7%
- [ ] >= 60% of OOS windows profitable: 44%
- [ ] bootstrap 5th-pct return > 0: -76.2%

### BTC / mtf_trend (4h + 1h alignment (trend))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 2.0, "stop_atr": 3.5}`. In-sample best (for comparison, not used): 270 trades, avg R -0.013.

- [x] OOS trades >= 100: 224
- [ ] profit factor >= 1.20: 0.99
- [ ] max drawdown <= 20% at 1% risk: 20.8%
- [ ] >= 60% of OOS windows profitable: 56%
- [ ] bootstrap 5th-pct return > 0: -34.1%

### BTC / donchian_breakout (Trend breakout (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 48, "stop_atr": 2.5}`. In-sample best (for comparison, not used): 597 trades, avg R -0.252.

- [x] OOS trades >= 100: 482
- [ ] profit factor >= 1.20: 0.69
- [ ] max drawdown <= 20% at 1% risk: 71.4%
- [ ] >= 60% of OOS windows profitable: 33%
- [ ] bootstrap 5th-pct return > 0: -84.7%

### BTC / donchian_1h (Trend breakout, 1h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 24, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 251 trades, avg R +0.016.

- [x] OOS trades >= 100: 154
- [ ] profit factor >= 1.20: 0.9
- [ ] max drawdown <= 20% at 1% risk: 21.0%
- [ ] >= 60% of OOS windows profitable: 44%
- [ ] bootstrap 5th-pct return > 0: -40.5%

### BTC / donchian_4h (Trend breakout, 4h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 20, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 99 trades, avg R -0.092.

- [ ] OOS trades >= 100: 71
- [ ] profit factor >= 1.20: 0.87
- [x] max drawdown <= 20% at 1% risk: 9.9%
- [ ] >= 60% of OOS windows profitable: 56%
- [ ] bootstrap 5th-pct return > 0: -23.2%

### BTC / ema_pullback (EMA pullback)
Idea source: Common day-trader pullback setup. Latest parameters: `{"stop_atr": 2.0, "tgt_r": 2.5}`. In-sample best (for comparison, not used): 1640 trades, avg R -0.296.

- [x] OOS trades >= 100: 1229
- [ ] profit factor >= 1.20: 0.62
- [ ] max drawdown <= 20% at 1% risk: 98.5%
- [ ] >= 60% of OOS windows profitable: 0%
- [ ] bootstrap 5th-pct return > 0: -99.3%

### BTC / ema_pullback_1h (EMA pullback, 1h)
Idea source: Common day-trader pullback setup. Latest parameters: `{"stop_atr": 2.5, "tgt_r": 3.0}`. In-sample best (for comparison, not used): 426 trades, avg R -0.117.

- [x] OOS trades >= 100: 317
- [ ] profit factor >= 1.20: 0.85
- [ ] max drawdown <= 20% at 1% risk: 36.8%
- [ ] >= 60% of OOS windows profitable: 44%
- [ ] bootstrap 5th-pct return > 0: -53.5%

### BTC / vwap_reclaim (VWAP reclaim)
Idea source: Common intraday VWAP setup. Latest parameters: `{"stop_atr": 2.5, "tgt_r": 2.5}`. In-sample best (for comparison, not used): 460 trades, avg R -0.325.

- [x] OOS trades >= 100: 330
- [ ] profit factor >= 1.20: 0.61
- [ ] max drawdown <= 20% at 1% risk: 62.8%
- [ ] >= 60% of OOS windows profitable: 0%
- [ ] bootstrap 5th-pct return > 0: -74.4%

### BTC / rsi2_reversion (RSI(2) reversion)
Idea source: Connors-style short-term mean reversion. Latest parameters: `{"lo": 5, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 1780 trades, avg R -0.187.

- [x] OOS trades >= 100: 1309
- [ ] profit factor >= 1.20: 0.24
- [ ] max drawdown <= 20% at 1% risk: 92.2%
- [ ] >= 60% of OOS windows profitable: 0%
- [ ] bootstrap 5th-pct return > 0: -94.0%

### ETH / mtf_quick (4-TF alignment (quick))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 1.5, "vol_k": 1.2}`. In-sample best (for comparison, not used): 1009 trades, avg R -0.053.

- [x] OOS trades >= 100: 851
- [ ] profit factor >= 1.20: 0.94
- [ ] max drawdown <= 20% at 1% risk: 65.0%
- [ ] >= 60% of OOS windows profitable: 33%
- [ ] bootstrap 5th-pct return > 0: -80.1%

### ETH / mtf_swing (1h + 30m alignment (swing))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 2.0, "stop_atr": 1.5}`. In-sample best (for comparison, not used): 603 trades, avg R -0.020.

- [x] OOS trades >= 100: 512
- [ ] profit factor >= 1.20: 0.84
- [ ] max drawdown <= 20% at 1% risk: 60.9%
- [ ] >= 60% of OOS windows profitable: 44%
- [ ] bootstrap 5th-pct return > 0: -74.3%

### ETH / mtf_trend (4h + 1h alignment (trend))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 3.5}`. In-sample best (for comparison, not used): 446 trades, avg R +0.052.

- [x] OOS trades >= 100: 292
- [ ] profit factor >= 1.20: 1.09
- [ ] max drawdown <= 20% at 1% risk: 32.2%
- [ ] >= 60% of OOS windows profitable: 56%
- [ ] bootstrap 5th-pct return > 0: -42.8%

### ETH / donchian_breakout (Trend breakout (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 48, "stop_atr": 1.5}`. In-sample best (for comparison, not used): 536 trades, avg R +0.000.

- [x] OOS trades >= 100: 501
- [ ] profit factor >= 1.20: 0.93
- [ ] max drawdown <= 20% at 1% risk: 52.7%
- [ ] >= 60% of OOS windows profitable: 44%
- [ ] bootstrap 5th-pct return > 0: -75.4%

### ETH / donchian_1h (Trend breakout, 1h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 72, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 139 trades, avg R +0.196.

- [x] OOS trades >= 100: 111
- [x] profit factor >= 1.20: 1.31
- [ ] max drawdown <= 20% at 1% risk: 24.5%
- [ ] >= 60% of OOS windows profitable: 56%
- [ ] bootstrap 5th-pct return > 0: -23.5%

### ETH / donchian_4h (Trend breakout, 4h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 20, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 94 trades, avg R +0.295.

- [ ] OOS trades >= 100: 66
- [x] profit factor >= 1.20: 1.29
- [x] max drawdown <= 20% at 1% risk: 11.7%
- [ ] >= 60% of OOS windows profitable: 56%
- [ ] bootstrap 5th-pct return > 0: -15.9%

### ETH / ema_pullback (EMA pullback)
Idea source: Common day-trader pullback setup. Latest parameters: `{"stop_atr": 2.0, "tgt_r": 2.5}`. In-sample best (for comparison, not used): 1681 trades, avg R -0.214.

- [x] OOS trades >= 100: 1242
- [ ] profit factor >= 1.20: 0.74
- [ ] max drawdown <= 20% at 1% risk: 94.2%
- [ ] >= 60% of OOS windows profitable: 0%
- [ ] bootstrap 5th-pct return > 0: -97.2%

### ETH / ema_pullback_1h (EMA pullback, 1h)
Idea source: Common day-trader pullback setup. Latest parameters: `{"stop_atr": 2.5, "tgt_r": 3.0}`. In-sample best (for comparison, not used): 579 trades, avg R -0.132.

- [x] OOS trades >= 100: 385
- [ ] profit factor >= 1.20: 0.76
- [ ] max drawdown <= 20% at 1% risk: 59.9%
- [ ] >= 60% of OOS windows profitable: 22%
- [ ] bootstrap 5th-pct return > 0: -71.1%

### ETH / vwap_reclaim (VWAP reclaim)
Idea source: Common intraday VWAP setup. Latest parameters: `{"stop_atr": 2.5, "tgt_r": 2.5}`. In-sample best (for comparison, not used): 423 trades, avg R -0.214.

- [x] OOS trades >= 100: 321
- [ ] profit factor >= 1.20: 0.59
- [ ] max drawdown <= 20% at 1% risk: 65.6%
- [ ] >= 60% of OOS windows profitable: 0%
- [ ] bootstrap 5th-pct return > 0: -76.5%

### ETH / rsi2_reversion (RSI(2) reversion)
Idea source: Connors-style short-term mean reversion. Latest parameters: `{"lo": 5, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 1791 trades, avg R -0.149.

- [x] OOS trades >= 100: 1315
- [ ] profit factor >= 1.20: 0.34
- [ ] max drawdown <= 20% at 1% risk: 87.5%
- [ ] >= 60% of OOS windows profitable: 0%
- [ ] bootstrap 5th-pct return > 0: -90.6%

### SOL / mtf_quick (4-TF alignment (quick))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 2.5, "vol_k": 0.0}`. In-sample best (for comparison, not used): 1063 trades, avg R -0.092.

- [x] OOS trades >= 100: 806
- [ ] profit factor >= 1.20: 0.71
- [ ] max drawdown <= 20% at 1% risk: 81.2%
- [ ] >= 60% of OOS windows profitable: 11%
- [ ] bootstrap 5th-pct return > 0: -90.4%

### SOL / mtf_swing (1h + 30m alignment (swing))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 1.5}`. In-sample best (for comparison, not used): 634 trades, avg R +0.022.

- [x] OOS trades >= 100: 540
- [ ] profit factor >= 1.20: 0.92
- [ ] max drawdown <= 20% at 1% risk: 57.5%
- [ ] >= 60% of OOS windows profitable: 33%
- [ ] bootstrap 5th-pct return > 0: -70.4%

### SOL / mtf_trend (4h + 1h alignment (trend))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 2.0, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 479 trades, avg R +0.030.

- [x] OOS trades >= 100: 282
- [ ] profit factor >= 1.20: 1.08
- [ ] max drawdown <= 20% at 1% risk: 20.6%
- [x] >= 60% of OOS windows profitable: 67%
- [ ] bootstrap 5th-pct return > 0: -40.3%

### SOL / donchian_breakout (Trend breakout (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 48, "stop_atr": 1.5}`. In-sample best (for comparison, not used): 550 trades, avg R +0.048.

- [x] OOS trades >= 100: 419
- [ ] profit factor >= 1.20: 1.01
- [ ] max drawdown <= 20% at 1% risk: 28.4%
- [ ] >= 60% of OOS windows profitable: 44%
- [ ] bootstrap 5th-pct return > 0: -56.0%

### SOL / donchian_1h (Trend breakout, 1h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 72, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 148 trades, avg R +0.222.

- [x] OOS trades >= 100: 156
- [x] profit factor >= 1.20: 1.27
- [x] max drawdown <= 20% at 1% risk: 19.9%
- [x] >= 60% of OOS windows profitable: 67%
- [ ] bootstrap 5th-pct return > 0: -29.9%

### SOL / donchian_4h (Trend breakout, 4h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 55, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 55 trades, avg R +0.319.

- [ ] OOS trades >= 100: 74
- [ ] profit factor >= 1.20: 1.0
- [x] max drawdown <= 20% at 1% risk: 14.2%
- [ ] >= 60% of OOS windows profitable: 44%
- [ ] bootstrap 5th-pct return > 0: -21.1%

### SOL / ema_pullback (EMA pullback)
Idea source: Common day-trader pullback setup. Latest parameters: `{"stop_atr": 2.0, "tgt_r": 2.5}`. In-sample best (for comparison, not used): 1702 trades, avg R -0.116.

- [x] OOS trades >= 100: 1264
- [ ] profit factor >= 1.20: 0.84
- [ ] max drawdown <= 20% at 1% risk: 83.3%
- [ ] >= 60% of OOS windows profitable: 22%
- [ ] bootstrap 5th-pct return > 0: -92.1%

### SOL / ema_pullback_1h (EMA pullback, 1h)
Idea source: Common day-trader pullback setup. Latest parameters: `{"stop_atr": 2.5, "tgt_r": 2.0}`. In-sample best (for comparison, not used): 412 trades, avg R -0.058.

- [x] OOS trades >= 100: 389
- [ ] profit factor >= 1.20: 0.88
- [ ] max drawdown <= 20% at 1% risk: 35.4%
- [ ] >= 60% of OOS windows profitable: 22%
- [ ] bootstrap 5th-pct return > 0: -55.7%

### SOL / vwap_reclaim (VWAP reclaim)
Idea source: Common intraday VWAP setup. Latest parameters: `{"stop_atr": 2.5, "tgt_r": 2.5}`. In-sample best (for comparison, not used): 377 trades, avg R -0.157.

- [x] OOS trades >= 100: 301
- [ ] profit factor >= 1.20: 0.69
- [ ] max drawdown <= 20% at 1% risk: 47.8%
- [ ] >= 60% of OOS windows profitable: 22%
- [ ] bootstrap 5th-pct return > 0: -61.7%

### SOL / rsi2_reversion (RSI(2) reversion)
Idea source: Connors-style short-term mean reversion. Latest parameters: `{"lo": 5, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 1756 trades, avg R -0.099.

- [x] OOS trades >= 100: 1326
- [ ] profit factor >= 1.20: 0.46
- [ ] max drawdown <= 20% at 1% risk: 77.2%
- [ ] >= 60% of OOS windows profitable: 0%
- [ ] bootstrap 5th-pct return > 0: -82.5%

