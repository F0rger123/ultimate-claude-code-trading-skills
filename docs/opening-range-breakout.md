# MNQ opening-range breakout (RESEARCH HYPOTHESIS)

**Separate from the Coinbase strategies.**
- **Files:**
  - `pine/mnq_opening_range_915_930.pine` (TradingView Pine v6)
  - `research/mnq_opening_range.py` (Python parity)
  - `tests/test_mnq_orb.py` (synthetic correctness tests)
- **Status:**
  - The Pine script has been reviewed by eye but **not compiled in TradingView** yet.
  - **No historical results:** the project has no licensed CME 15-minute MNQ data.
  - No live trading. That would need a US futures broker, an account, margin and the owner's authorization.

## Rules
1. **Reference range:** the high and low of the 15-minute candle that opens at 9:15 New York time,
   complete at 9:30. The clock follows US daylight time.
2. **Long:** a later completed candle closes strictly above the range high. Buy at the next bar's open.
   The stop is the breakout candle's low.
3. **Short:** the mirror image. Sell at the next bar's open; the stop is the breakout candle's high.
4. **Target:** fill ± 0.5 x (fill − stop), computed from the **actual fill** and rounded to the tick.
5. **Session limits:**
   - one filled trade per session; no pyramiding or reversal
   - an opening gap that invalidates the stop ends the session's trading
   - entries only before 12:00
   - flatten at 15:45
6. **Filters** (each tested alone against the baseline):
   - A: 1h EMA50 vs EMA200
   - B: session VWAP (reset at 9:30)
   - C: range-width percentile vs prior sessions
   - D: max overnight gap
   - E: ADX(14) ≥ 20

## Why it is hard
With a 0.5R target and a 1R stop, break-even is a 66.7% win rate before costs. Costs push it higher.
**Cost in R** = (2 × commission + 2 × slippage ticks × $0.50) / (stop points × $2).
- *Hypothetical:* $0.62 commission per side, 1 tick of slippage per side and an 8-point stop
  ≈ 0.14R per trade, which needs about a 76% win rate.

## Registered trials (to count in multiple testing)
- 6 models: the baseline plus filters A–E, one at a time
- × 3 targets: 0.5R, 0.75R and 1R
- = 18 trials

Any combination of filters is a new trial.
