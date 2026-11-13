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
