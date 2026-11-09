# Strategy tournament

Generated 2026-11-09 06:18 UTC. Out-of-sample (walk-forward: train 365 days, test 90 days) results only. Base bars: 60 min.
Costs: 0.06% fee and 0.02% slippage per side, funding 0.001%/hour. Sizing: 1.0% risk per trade, leverage capped at the live desk's per-coin cap (BTC 3.9x, ETH 3.3x, SOL 1.8x). Data: Coinbase spot candles (perp history is too short), so perp basis and real funding are approximated.

Not financial advice. Past results do not predict future results.

| Symbol | Strategy | OOS trades | Win rate | Avg R | Profit factor | Return | Max DD | Bootstrap 5th-pct return | Gate |
|---|---|---|---|---|---|---|---|---|---|
| BTC | trend_ensemble | 100 | 34% | +0.549 | 4.52 | +56.0% | 2.7% | +2.1% | fail |
| ETH | trend_ensemble | 119 | 36% | +0.311 | 3.10 | +20.4% | 2.8% | +2.3% | **PASS** |
| SOL | trend_ensemble | 73 | 32% | +0.256 | 2.49 | +17.8% | 2.9% | -6.9% | fail |

## Gate detail

### BTC / trend_ensemble (Trend ensemble, daily (regime-filtered))
Idea source: Time-series momentum (Moskowitz, Ooi, Pedersen 2012; Hurst, Ooi, Pedersen 'A Century of Evidence on Trend-Following'). Latest parameters: `{}`. In-sample best (for comparison, not used): 126 trades, avg R +0.418.

- [x] OOS trades >= 100: 100
- [x] profit factor >= 1.20: 4.52
- [x] max drawdown <= 20% at 1% risk: 2.7%
- [ ] >= 60% of OOS windows profitable: 55%
- [x] bootstrap 5th-pct return > 0: 2.1%

### ETH / trend_ensemble (Trend ensemble, daily (regime-filtered))
Idea source: Time-series momentum (Moskowitz, Ooi, Pedersen 2012; Hurst, Ooi, Pedersen 'A Century of Evidence on Trend-Following'). Latest parameters: `{}`. In-sample best (for comparison, not used): 128 trades, avg R +0.280.

- [x] OOS trades >= 100: 119
- [x] profit factor >= 1.20: 3.1
- [x] max drawdown <= 20% at 1% risk: 2.8%
- [x] >= 60% of OOS windows profitable: 68%
- [x] bootstrap 5th-pct return > 0: 2.3%

### SOL / trend_ensemble (Trend ensemble, daily (regime-filtered))
Idea source: Time-series momentum (Moskowitz, Ooi, Pedersen 2012; Hurst, Ooi, Pedersen 'A Century of Evidence on Trend-Following'). Latest parameters: `{}`. In-sample best (for comparison, not used): 83 trades, avg R +0.252.

- [ ] OOS trades >= 100: 73
- [x] profit factor >= 1.20: 2.49
- [x] max drawdown <= 20% at 1% risk: 2.9%
- [ ] >= 60% of OOS windows profitable: 40%
- [ ] bootstrap 5th-pct return > 0: -6.9%

