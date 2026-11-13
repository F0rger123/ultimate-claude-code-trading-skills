# Strategy bank

Ideas waiting to be tested by the weekly shake-up. Research (for example a ChatGPT deep-research run)
produces written specs; Claude turns each usable spec into a strategy in `tradedesk/library.py`, where it
joins the candidate pool. A strategy from the bank never trades on its own: it has to win the same recent
test with costs as every other candidate, and then it only gets a **paper** account.

## What a usable spec looks like
One entry per strategy, in this shape (JSON or the same fields as a list):

```json
{
  "name": "Short plain name",
  "family": "trend | mean_reversion | breakout | volatility | carry | seasonality | relative_value | other",
  "cadence": "fast (5-minute bars, holds minutes to a day) | slow (hourly bars, holds days to weeks)",
  "markets": "BTC, ETH, SOL",
  "data_needed": "OHLCV only | other (say exactly what)",
  "entry_long": "exact rule with indicator settings",
  "entry_short": "exact rule, or 'none'",
  "exit": "exact rule",
  "stop": "exact rule (ATR multiple, fixed %, or structure)",
  "target": "exact rule or 'none'",
  "params": {"name": [2 to 3 values], "...": "at most 3 parameters"},
  "expected_trades_per_week": "number per coin",
  "why_it_should_work": "the market mechanism, in two or three sentences",
  "evidence": [{"source": "paper, book or article title", "url": "link", "what_it_found": "one line"}],
  "evidence_quality": "peer-reviewed | practitioner | anecdotal | none",
  "fails_when": "the market conditions where it loses",
  "cost_sensitivity": "low | medium | high, with the reason",
  "overlap_with": "which strategy we already run that it resembles, if any"
}
```

## What gets rejected before coding
- needs data the desk does not have (order book, funding history, on-chain flows, news, options): parked
  with a note on what it would take
- vague rules ("buy when momentum is strong")
- more than 3 tuning parameters
- expected edge smaller than costs: perp round trip is about 0.16% (0.06% taker + 0.02% slippage per side),
  spot about 1.8%
- evidence that is only a performance screenshot or a claim with no method

## What has already been learned (update as the desk learns)
- Hourly-to-daily trend following with volatility sizing was the best candidate in the corrected
  tournament (out-of-sample Sharpe about 0.93, max drawdown about 8%), but not statistically proven.
- 5-minute and 15-minute setups lose to costs in backtests unless they trade rarely.
- A 10-minute scalper lost to fees on paper in under a day (159 trades, -1.6%).
- `tradedesk/study.py` writes `state/paper/study.json`: where each paper account makes and loses money.

## Batch 2026-11-13 (ChatGPT deep research, files in `2026-11-13/`)
40 designed strategies plus 10 one-change improvements for the two early winners. The research did not
backtest them; it says so itself.
- **Coded (26):** in `tradedesk/library.py`, all OHLCV-only single-coin rules. Tests check each runs and
  never looks ahead (`tests/test_library.py`). They now compete in the weekly shake-up.
- **Improvements (10):** added as switches on the running winners (`improve` on `EMAPullback` and
  `MTFQuick`: ADX gate, ATR floor, daily trend agreement, longer target, weekday-only, delayed exit,
  higher volume). All off by default, so running accounts are unchanged (verified: identical replay). The
  daily study tests them as "v2" challengers; SOL-only comes from the study's coin filter.
- **Parked:** pair trades ETH/BTC breakout, SOL/ETH breakout, ETH/BTC residual reversion and the 3-coin
  spread (the engine trades one coin at a time); 3-coin breadth gate (needs cross-coin state);
  duplicates of running strategies (4h Donchian 55, weekly strength leader, 4-timeframe SuperTrend); and
  the six that need funding, open interest, liquidation, on-chain or FOMC data.
- **First look on real data (2026-11-13, same test as the shake-up, defaults only):** daily momentum
  with ATR stop +15.8% (26 trades, worst drop 3.1%) and the 20/60/120 return vote +15.5% (33 trades,
  2.6%) over 365 days led; most hourly, 15-minute and 5-minute rules lost. Picking the best of 26 after the
  fact flatters the winners: this is a lead for paper, not evidence of an edge.
