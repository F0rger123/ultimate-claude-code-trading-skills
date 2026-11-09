# Corrected tournament: ranked results

Label: **VERIFIED RUN**: real Coinbase spot hourly data (BTC and ETH from 2018-12-29, SOL from 2021-06-17), this repository's code. Reproduce: `python research/corrected_tournament.py && python research/summarize_corrected.py`.

- **Engine:** shared mark-to-market ledger. Risk 1% of marked equity per trade at the stop. Next-bar-open market fills, stop-first, gap fills at open.
- **Spot:** long-only, no leverage, 0.90% taker per side + 0.05% slippage (assumed 2026 entry tier, unverified).
- **Perp:** long/short, effective leverage <= 1.5x, whole contracts, 0.06% + 0.02% per side, funding **ASSUMED** at 0.001%/h against longs (no historical CFM funding data).
- **Walk-forward:** 1,095-day train / 180-day non-overlapping OOS, with parameters picked only from trades closed inside the training window. Continuous OOS ledger 2021-12-28 to 2026-06-05. The last partial window (about 5 months) is not scored.
- **Trials registered:** 77 in total. DSR (all) = deflated Sharpe probability against all 77 trials. Bootstrap = 10-day block bootstrap, 5th percentile CAGR.

| Rank | Strategy | Market | Trials | OOS trades | CAGR | Sharpe | Max DD (daily) | Max DD (hourly) | PF | Fees | Bootstrap CAGR p5 | DSR (all) | Costs x3 CAGR | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | control: trend_ensemble (unchanged) | perp | 1 | 170 | +6.7% | 0.93 | 8.1% | 9.8% | 3.22 | $95 | +1.2% | 0.72 | +5.9% | PAPER CANDIDATE: not statistically proven |
| 2 | vol_managed_trend + halve-in-high-vol | perp | 12 | 164 | +4.9% | 0.83 | 6.3% | 6.6% | 2.43 | $109 | -0.0% | 0.65 | +3.0% | PAPER CANDIDATE: not statistically proven |
| 3 | vol_managed_trend | perp | 12 | 165 | +4.9% | 0.83 | 6.3% | 6.6% | 2.43 | $109 | -0.0% | 0.65 | +3.0% | PAPER CANDIDATE: not statistically proven |
| 4 | weekly_strength_rotation | spot | 3 | 27 | +5.8% | 0.83 | 8.2% | 9.5% | 2.91 | $460 | +0.5% | 0.65 | +3.9% | INSUFFICIENT EVIDENCE (trades) |
| 5 | vol_filtered_breakout | perp | 8 | 65 | +7.6% | 0.77 | 10.6% | 11.4% | 2.38 | $70 | -1.0% | 0.60 | +6.8% | PAPER CANDIDATE: not statistically proven |
| 6 | breakout, unfiltered baseline | perp | 4 | 65 | +7.3% | 0.71 | 12.7% | 13.4% | 2.32 | $69 | -1.3% | 0.55 | +6.3% | PAPER CANDIDATE: not statistically proven |
| 7 | breakout, unfiltered baseline | spot | 4 | 35 | +6.1% | 0.59 | 11.0% | 11.6% | 2.30 | $779 | -2.4% | 0.44 | +2.9% | INSUFFICIENT EVIDENCE (trades) |
| 8 | vol_filtered_breakout | spot | 8 | 45 | +4.4% | 0.45 | 14.2% | 14.5% | 1.68 | $858 | -4.0% | 0.33 | +0.5% | INSUFFICIENT EVIDENCE (trades) |
| 9 | control: trend_ensemble (unchanged) | spot | 1 | 137 | +3.1% | 0.42 | 11.3% | 11.9% | 1.52 | $1418 | -2.7% | 0.30 | -2.8% | PAPER CANDIDATE: not statistically proven |
| 10 | vol_managed_trend + halve-in-high-vol | spot | 12 | 135 | +2.0% | 0.32 | 12.4% | 12.7% | 1.34 | $1479 | -3.5% | 0.24 | -4.4% | PAPER CANDIDATE: not statistically proven |
| 11 | vol_managed_trend | spot | 12 | 135 | +1.9% | 0.29 | 11.4% | 11.5% | 1.31 | $1594 | -3.7% | 0.22 | -4.9% | PAPER CANDIDATE: not statistically proven |

## Benchmarks over the same OOS period (bought once, one 0.90% fee)

| Benchmark | CAGR | Sharpe | Max DD |
|---|---|---|---|
| Buy-and-hold BTC | +6.3% | 0.38 | 67.0% |
| Buy-and-hold equal weight BTC/ETH/SOL | -7.5% | 0.18 | 77.1% |

Risk-matched buy-and-hold (equal weight scaled to each strategy's own volatility, rest in cash):

| Strategy | Market | Strategy CAGR | Risk-matched B&H CAGR | Strategy max DD | Risk-matched B&H max DD |
|---|---|---|---|---|---|
| control: trend_ensemble (unchanged) | perp | +6.7% | +1.0% | 8.1% | 13.3% |
| vol_managed_trend + halve-in-high-vol | perp | +4.9% | +0.9% | 6.3% | 11.0% |
| vol_managed_trend | perp | +4.9% | +0.9% | 6.3% | 11.0% |
| weekly_strength_rotation | spot | +5.8% | +1.0% | 8.2% | 13.0% |
| vol_filtered_breakout | perp | +7.6% | +1.3% | 10.6% | 18.5% |
| breakout, unfiltered baseline | perp | +7.3% | +1.3% | 12.7% | 19.4% |
| breakout, unfiltered baseline | spot | +6.1% | +1.4% | 11.0% | 20.1% |
| vol_filtered_breakout | spot | +4.4% | +1.4% | 14.2% | 19.7% |
| control: trend_ensemble (unchanged) | spot | +3.1% | +1.1% | 11.3% | 15.0% |
| vol_managed_trend + halve-in-high-vol | spot | +2.0% | +1.0% | 12.4% | 12.6% |
| vol_managed_trend | spot | +1.9% | +1.1% | 11.4% | 14.1% |

## Stress tests (same OOS ledger)

| Strategy | Market | Base CAGR | Costs x2 | Costs x3 | Risk 0.5% CAGR / DD | Owner DD tiers (7.5/10/15%) CAGR / DD | Spot at 0.60% taker |
|---|---|---|---|---|---|---|---|
| control: trend_ensemble (unchanged) | perp | +6.7% | +6.3% | +5.9% | +2.5% / 3.8% | +6.7% / 8.1% | - |
| vol_managed_trend + halve-in-high-vol | perp | +4.9% | +4.5% | +3.0% | +1.5% / 2.8% | +4.9% / 6.3% | - |
| vol_managed_trend | perp | +4.9% | +4.5% | +3.0% | +1.5% / 2.8% | +4.9% / 6.3% | - |
| weekly_strength_rotation | spot | +5.8% | +4.8% | +3.9% | +3.1% / 4.4% | +5.5% / 7.9% | +6.1% |
| vol_filtered_breakout | perp | +7.6% | +7.1% | +6.8% | +4.1% / 5.5% | +5.5% / 9.1% | - |
| breakout, unfiltered baseline | perp | +7.3% | +6.9% | +6.3% | +3.7% / 5.9% | -0.1% / 10.0% | - |
| breakout, unfiltered baseline | spot | +6.1% | +4.5% | +2.9% | +3.3% / 6.2% | +3.1% / 8.4% | +6.6% |
| vol_filtered_breakout | spot | +4.4% | +2.4% | +0.5% | +2.4% / 7.3% | -2.4% / 10.4% | +5.0% |
| control: trend_ensemble (unchanged) | spot | +3.1% | +0.1% | -2.8% | +1.7% / 6.2% | +3.6% / 9.6% | +4.1% |
| vol_managed_trend + halve-in-high-vol | spot | +2.0% | -1.3% | -4.4% | +1.0% / 6.5% | +2.6% / 10.1% | +3.0% |
| vol_managed_trend | spot | +1.9% | -1.6% | -4.9% | +1.0% / 5.9% | +0.9% / 10.1% | +3.1% |

## Parameter neighborhoods (each fixed parameter set over the whole OOS span, no selection)

- **vol_managed_trend + halve-in-high-vol (perp):** 12 of 12 parameter sets positive; CAGR range +1.9% to +7.4%.
- **vol_managed_trend (perp):** 12 of 12 parameter sets positive; CAGR range +2.1% to +7.0%.
- **weekly_strength_rotation (spot):** 3 of 3 parameter sets positive; CAGR range +1.3% to +7.4%.
- **vol_filtered_breakout (perp):** 8 of 8 parameter sets positive; CAGR range +3.1% to +8.5%.
- **breakout, unfiltered baseline (perp):** 4 of 4 parameter sets positive; CAGR range +4.3% to +8.0%.
- **breakout, unfiltered baseline (spot):** 4 of 4 parameter sets positive; CAGR range +1.9% to +6.1%.
- **vol_filtered_breakout (spot):** 8 of 8 parameter sets positive; CAGR range +2.0% to +6.4%.
- **vol_managed_trend + halve-in-high-vol (spot):** 12 of 12 parameter sets positive; CAGR range +1.0% to +1.9%.
- **vol_managed_trend (spot):** 12 of 12 parameter sets positive; CAGR range +1.0% to +2.0%.

## Out-of-sample windows (the best candidate)

Strategy: control: trend_ensemble (unchanged) (perp).

| Test window | Params chosen on training | Trades | Return |
|---|---|---|---|
| 2021-12-28 to 2022-06-26 | {} | 11 | +3.9% |
| 2022-06-26 to 2022-12-23 | {} | 26 | -1.1% |
| 2022-12-23 to 2023-06-21 | {} | 23 | +1.1% |
| 2023-06-21 to 2023-12-18 | {} | 31 | +15.0% |
| 2023-12-18 to 2024-06-15 | {} | 12 | +7.5% |
| 2024-06-15 to 2024-12-12 | {} | 20 | -0.2% |
| 2024-12-12 to 2025-06-10 | {} | 14 | +0.4% |
| 2025-06-10 to 2025-12-07 | {} | 7 | +1.1% |
| 2025-12-07 to 2026-06-05 | {} | 26 | +2.1% |

Generated 2026-11-09 07:34 UTC.
