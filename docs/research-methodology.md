# Research methodology

## Evidence labels (never interchanged)
| Label | Meaning |
|---|---|
| **VERIFIED RUN** | Actual code from this repo, on real documented data. Reproducible with the stated command. |
| **SIMULATED / SYNTHETIC TEST** | Correctness test on made-up data. Says nothing about profitability. |
| **HISTORICAL LEGACY RESULT** | Produced by the pre-correction engine (`reports/legacy/`). Needs recomputation. |
| **RESEARCH HYPOTHESIS** | Idea or rule set not yet tested on real data. |
| **LIVE RESULT** | Executed with real money. None exist. |

## Data
- **Source:** Coinbase Exchange public candles, spot. BTC-USD and ETH-USD hourly from 2018-12-29;
  SOL-USD from 2021-06-17. 5-minute bars from 2024-11-07. All series run to 2026-11-07.
  Downloaded with `python -m tradedesk data`. Files are hashed in each registry record.
- **Gaps:** Coinbase publishes no bar for an interval with no trades. Gaps are counted; resampling keeps
  only complete buckets.
- **Spot stands in for perps:** perp history starts in mid-2025, so backtests use spot prices for futures.
  Basis is ignored and funding is assumed.

## Look-ahead and leakage controls
- A higher-timeframe value becomes visible only after its bar closes (`Market.at`). A unit test checks
  every strategy: entries computed on truncated data equal entries computed on full data.
- Orders fill at the next bar's open. Stops fill at the stop, or at the open when price gaps through it.
  When the stop and target are both inside one bar, the stop is assumed hit first.
- **Walk-forward:** rolling 1,095-day training, 180-day non-overlapping test windows.
  - Parameter selection scores only trades that **entered and exited** inside the training window.
  - The out-of-sample ledger is one continuous account; the parameters allowed to open trades change at
    each boundary.
  - Positions that span a boundary are managed by the variant that opened them.

## Accounting
- One ledger for all symbols, processed in time order: exits first, then entries.
- Spot buys spend cash; futures post no cash but pay fees and signed funding.
- Equity is marked at every hourly close. Max drawdown is reported on hourly and on daily marks.
- **Sizing:** risk fraction of marked equity at the stop, capped by
  - per-position and gross leverage
  - available cash (spot)
  - whole contracts (futures)
  - venue minimum notional

## Statistics and multiple testing
- **Sharpe, Sortino, Calmar, expected shortfall (worst 5% of days), underwater duration, exposure.**
- **Block bootstrap:** 10-day blocks of daily returns, 2,000 paths. Reports the 5th/50th/95th
  percentile CAGR and the 95th percentile drawdown.
- **Deflated Sharpe ratio:** compared against the expected maximum Sharpe of **all registered trials**
  (77 as of 2026-11-09). The trial-to-trial variance comes from each fixed parameter set's OOS Sharpe.
- **Parameter neighborhoods:** every fixed parameter set is reported over the OOS span. A family where only
  one setting works is rejected.
- **Registry:** every evaluation appends a record to `evidence/experiment-registry/registry.jsonl` with the
  commit, grid, costs, windows, data hashes and command.

## Verdict rules (from `research/summarize_corrected.py`)
| Verdict | Condition |
|---|---|
| **Insufficient evidence** | fewer than 60 OOS trades |
| **Reject** | Sharpe ≤ 0 |
| **Paper candidate: not statistically proven** | deflated Sharpe < 0.95, or bootstrap 5th-percentile CAGR ≤ 0 |
| **Cost-fragile** | CAGR ≤ 0 at 3x costs (checked only once the statistical bar is met) |
| **Paper priority** | everything above passes |

## Known limits
- **Funding is assumed** at 0.001% per hour against longs; there is no historical CFM funding.
- **No order-book model:** partial fills, queue position and market depth aren't modeled. Limit orders
  are never assumed filled just because a candle touched the price.
- **Survivorship:** BTC, ETH and SOL were chosen in 2026 knowing they survived. This biases results upward.
- **Data reuse:** the years 2019–2026 have now been examined many times; they are not a pristine holdout.
  Only shadow, forward and paper results from now on are truly unseen.
