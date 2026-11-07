# Strategy tournament

Generated 2026-11-07 19:05 UTC. Out-of-sample (walk-forward: train 365 days, test 90 days) results only. Base bars: 60 min.
Costs: 0.06% fee and 0.02% slippage per side, funding 0.001%/hour. Sizing: 1.0% risk per trade, leverage capped at the live desk's per-coin cap (BTC 3.9x, ETH 3.3x, SOL 1.8x). Data: Coinbase spot candles (perp history is too short), so perp basis and real funding are approximated.

Not financial advice. Past results do not predict future results.

| Symbol | Strategy | OOS trades | Win rate | Avg R | Profit factor | Return | Max DD | Bootstrap 5th-pct return | Gate |
|---|---|---|---|---|---|---|---|---|---|
| BTC | turtle_daily | 51 | 41% | +1.473 | 3.95 | +83.1% | 6.7% | +0.2% | fail |
| BTC | ema_cross_4h | 108 | 28% | +0.795 | 2.79 | +94.5% | 9.0% | -7.5% | fail |
| SOL | turtle_daily | 36 | 31% | +0.665 | 2.54 | +23.7% | 5.5% | -7.4% | fail |
| ETH | ema_cross_4h | 120 | 25% | +0.614 | 2.15 | +85.5% | 18.1% | -5.5% | fail |
| ETH | donchian_1h | 470 | 27% | +0.389 | 1.55 | +314.8% | 24.5% | +25.5% | fail |
| BTC | donchian_4h | 230 | 28% | +0.366 | 1.56 | +96.1% | 23.6% | -9.8% | fail |
| SOL | ema_cross_4h | 101 | 35% | +0.328 | 1.80 | +33.2% | 11.4% | -12.2% | fail |
| ETH | donchian_4h | 261 | 28% | +0.270 | 1.42 | +80.9% | 17.5% | -11.2% | fail |
| BTC | tsmom_daily | 112 | 27% | +0.242 | 2.48 | +24.4% | 8.0% | -0.7% | fail |
| ETH | tsmom_daily | 94 | 32% | +0.196 | 2.11 | +15.9% | 7.0% | -3.9% | fail |
| BTC | donchian_1h | 566 | 26% | +0.178 | 1.24 | +105.2% | 28.6% | -34.0% | fail |
| SOL | donchian_4h | 129 | 30% | +0.142 | 1.23 | +16.1% | 12.5% | -20.7% | fail |
| ETH | turtle_daily | 45 | 33% | +0.107 | 1.22 | -1.4% | 12.0% | -16.3% | fail |
| SOL | donchian_1h | 411 | 31% | +0.074 | 1.12 | +21.6% | 26.1% | -39.3% | fail |
| BTC | mtf_trend | 1019 | 30% | +0.047 | 1.08 | +28.7% | 38.0% | -55.6% | fail |
| ETH | mtf_trend | 1242 | 29% | +0.042 | 1.07 | +28.0% | 44.8% | -59.5% | fail |
| SOL | mtf_trend | 705 | 32% | +0.030 | 1.06 | +11.3% | 24.6% | -45.5% | fail |
| SOL | tsmom_daily | 74 | 23% | -0.037 | 0.78 | -2.8% | 5.9% | -9.7% | fail |

## Gate detail

### BTC / tsmom_daily (Time-series momentum, daily)
Idea source: Moskowitz, Ooi and Pedersen (2012), time-series momentum. Latest parameters: `{"long_only": 0, "n": 20, "stop_atr": 5.0}`. In-sample best (for comparison, not used): 64 trades, avg R +1.218.

- [x] OOS trades >= 100: 112
- [x] profit factor >= 1.20: 2.48
- [x] max drawdown <= 20% at 1% risk: 8.0%
- [ ] >= 60% of OOS windows profitable: 48%
- [ ] bootstrap 5th-pct return > 0: -0.7%

### BTC / turtle_daily (Turtle breakout, daily)
Idea source: Turtle trading rules (20/55-day breakouts, 2N stops) as published by Curtis Faith. Latest parameters: `{"long_only": 0, "n": 20, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 39 trades, avg R +2.399.

- [ ] OOS trades >= 100: 51
- [x] profit factor >= 1.20: 3.95
- [x] max drawdown <= 20% at 1% risk: 6.7%
- [x] >= 60% of OOS windows profitable: 70%
- [x] bootstrap 5th-pct return > 0: 0.2%

### BTC / ema_cross_4h (EMA cross, 4h)
Idea source: Classic moving-average crossover trend following. Latest parameters: `{"fast": 30, "long_only": 0, "stop_atr": 5.0}`. In-sample best (for comparison, not used): 79 trades, avg R +2.054.

- [x] OOS trades >= 100: 108
- [x] profit factor >= 1.20: 2.79
- [x] max drawdown <= 20% at 1% risk: 9.0%
- [ ] >= 60% of OOS windows profitable: 35%
- [ ] bootstrap 5th-pct return > 0: -7.5%

### BTC / donchian_4h (Trend breakout, 4h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 55, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 224 trades, avg R +0.496.

- [x] OOS trades >= 100: 230
- [x] profit factor >= 1.20: 1.56
- [ ] max drawdown <= 20% at 1% risk: 23.6%
- [ ] >= 60% of OOS windows profitable: 59%
- [ ] bootstrap 5th-pct return > 0: -9.8%

### BTC / donchian_1h (Trend breakout, 1h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 24, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 546 trades, avg R +0.333.

- [x] OOS trades >= 100: 566
- [x] profit factor >= 1.20: 1.24
- [ ] max drawdown <= 20% at 1% risk: 28.6%
- [ ] >= 60% of OOS windows profitable: 56%
- [ ] bootstrap 5th-pct return > 0: -34.0%

### BTC / mtf_trend (4h + 1h alignment (trend))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 3.5}`. In-sample best (for comparison, not used): 1159 trades, avg R +0.113.

- [x] OOS trades >= 100: 1019
- [ ] profit factor >= 1.20: 1.08
- [ ] max drawdown <= 20% at 1% risk: 38.0%
- [ ] >= 60% of OOS windows profitable: 48%
- [ ] bootstrap 5th-pct return > 0: -55.6%

### ETH / tsmom_daily (Time-series momentum, daily)
Idea source: Moskowitz, Ooi and Pedersen (2012), time-series momentum. Latest parameters: `{"long_only": 0, "n": 20, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 55 trades, avg R +0.878.

- [ ] OOS trades >= 100: 94
- [x] profit factor >= 1.20: 2.11
- [x] max drawdown <= 20% at 1% risk: 7.0%
- [ ] >= 60% of OOS windows profitable: 42%
- [ ] bootstrap 5th-pct return > 0: -3.9%

### ETH / turtle_daily (Turtle breakout, daily)
Idea source: Turtle trading rules (20/55-day breakouts, 2N stops) as published by Curtis Faith. Latest parameters: `{"long_only": 0, "n": 20, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 18 trades, avg R +2.298.

- [ ] OOS trades >= 100: 45
- [x] profit factor >= 1.20: 1.22
- [x] max drawdown <= 20% at 1% risk: 12.0%
- [ ] >= 60% of OOS windows profitable: 55%
- [ ] bootstrap 5th-pct return > 0: -16.3%

### ETH / ema_cross_4h (EMA cross, 4h)
Idea source: Classic moving-average crossover trend following. Latest parameters: `{"fast": 30, "long_only": 0, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 65 trades, avg R +2.032.

- [x] OOS trades >= 100: 120
- [x] profit factor >= 1.20: 2.15
- [x] max drawdown <= 20% at 1% risk: 18.1%
- [ ] >= 60% of OOS windows profitable: 46%
- [ ] bootstrap 5th-pct return > 0: -5.5%

### ETH / donchian_4h (Trend breakout, 4h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 20, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 226 trades, avg R +0.385.

- [x] OOS trades >= 100: 261
- [x] profit factor >= 1.20: 1.42
- [x] max drawdown <= 20% at 1% risk: 17.5%
- [ ] >= 60% of OOS windows profitable: 59%
- [ ] bootstrap 5th-pct return > 0: -11.2%

### ETH / donchian_1h (Trend breakout, 1h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 24, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 523 trades, avg R +0.363.

- [x] OOS trades >= 100: 470
- [x] profit factor >= 1.20: 1.55
- [ ] max drawdown <= 20% at 1% risk: 24.5%
- [x] >= 60% of OOS windows profitable: 78%
- [x] bootstrap 5th-pct return > 0: 25.5%

### ETH / mtf_trend (4h + 1h alignment (trend))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 1201 trades, avg R +0.086.

- [x] OOS trades >= 100: 1242
- [ ] profit factor >= 1.20: 1.07
- [ ] max drawdown <= 20% at 1% risk: 44.8%
- [ ] >= 60% of OOS windows profitable: 48%
- [ ] bootstrap 5th-pct return > 0: -59.5%

### SOL / tsmom_daily (Time-series momentum, daily)
Idea source: Moskowitz, Ooi and Pedersen (2012), time-series momentum. Latest parameters: `{"long_only": 0, "n": 20, "stop_atr": 5.0}`. In-sample best (for comparison, not used): 100 trades, avg R +0.292.

- [ ] OOS trades >= 100: 74
- [ ] profit factor >= 1.20: 0.78
- [x] max drawdown <= 20% at 1% risk: 5.9%
- [ ] >= 60% of OOS windows profitable: 35%
- [ ] bootstrap 5th-pct return > 0: -9.7%

### SOL / turtle_daily (Turtle breakout, daily)
Idea source: Turtle trading rules (20/55-day breakouts, 2N stops) as published by Curtis Faith. Latest parameters: `{"long_only": 0, "n": 20, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 12 trades, avg R +3.476.

- [ ] OOS trades >= 100: 36
- [x] profit factor >= 1.20: 2.54
- [x] max drawdown <= 20% at 1% risk: 5.5%
- [ ] >= 60% of OOS windows profitable: 50%
- [ ] bootstrap 5th-pct return > 0: -7.4%

### SOL / ema_cross_4h (EMA cross, 4h)
Idea source: Classic moving-average crossover trend following. Latest parameters: `{"fast": 30, "long_only": 0, "stop_atr": 5.0}`. In-sample best (for comparison, not used): 56 trades, avg R +2.006.

- [x] OOS trades >= 100: 101
- [x] profit factor >= 1.20: 1.8
- [x] max drawdown <= 20% at 1% risk: 11.4%
- [ ] >= 60% of OOS windows profitable: 47%
- [ ] bootstrap 5th-pct return > 0: -12.2%

### SOL / donchian_4h (Trend breakout, 4h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 20, "stop_atr": 3.0}`. In-sample best (for comparison, not used): 160 trades, avg R +0.429.

- [x] OOS trades >= 100: 129
- [x] profit factor >= 1.20: 1.23
- [x] max drawdown <= 20% at 1% risk: 12.5%
- [ ] >= 60% of OOS windows profitable: 59%
- [ ] bootstrap 5th-pct return > 0: -20.7%

### SOL / donchian_1h (Trend breakout, 1h (Donchian))
Idea source: Classic channel breakout (Turtle-style). Latest parameters: `{"n": 72, "stop_atr": 2.0}`. In-sample best (for comparison, not used): 344 trades, avg R +0.196.

- [x] OOS trades >= 100: 411
- [ ] profit factor >= 1.20: 1.12
- [ ] max drawdown <= 20% at 1% risk: 26.1%
- [ ] >= 60% of OOS windows profitable: 59%
- [ ] bootstrap 5th-pct return > 0: -39.3%

### SOL / mtf_trend (4h + 1h alignment (trend))
Idea source: Owner's TradingView method; SuperTrend stands in for the unnamed indicator. Latest parameters: `{"st_mult": 3.0, "stop_atr": 3.5}`. In-sample best (for comparison, not used): 689 trades, avg R +0.070.

- [x] OOS trades >= 100: 705
- [ ] profit factor >= 1.20: 1.06
- [ ] max drawdown <= 20% at 1% risk: 24.6%
- [ ] >= 60% of OOS windows profitable: 47%
- [ ] bootstrap 5th-pct return > 0: -45.5%

