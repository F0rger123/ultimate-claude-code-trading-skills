# Deep-research prompt for ChatGPT

Paste everything inside the box into ChatGPT with Deep Research turned on. Paste its answer back to Claude,
which codes the usable strategies into `tradedesk/library.py`.

````text
You are a quantitative trading researcher. Do deep, source-backed research and produce a bank of crypto
trading strategies for an automated PAPER-trading system. Honesty matters more than volume: never invent
performance numbers, and label every claim with its source or as unverified.

## The system you are designing for
- Markets: BTC, ETH and SOL only, traded as US-regulated perpetual-style futures (Coinbase Financial Markets).
  Long and short are both allowed.
- Data available: OHLCV candles only (Coinbase spot prices), 5-minute bars (about 2 years) and hourly bars
  (back to 2019). Daily, 4-hour, 1-hour, 30-minute and 15-minute bars are built from those.
  NOT available: order book, trades/tape, funding-rate history, open interest, liquidations, on-chain data,
  options data, news or sentiment. If a strategy needs any of these, still include it, but mark
  data_needed accordingly so it can be parked.
- Costs used in testing: 0.06% taker fee plus 0.02% slippage per side, so about 0.16% per round trip.
  Funding is assumed at 0.001% per hour against longs. Spot versions pay about 0.9% per side.
- Risk rules (fixed, do not design around them): 1% of the account at risk per trade, position leverage
  capped at 1.5x, a 10% drawdown blocks new trades, 15% flattens everything.
- Two speeds of account:
  - "fast" accounts run on 5-minute bars and are checked every 5 minutes (holds of minutes to a day).
  - "slow" accounts run on hourly bars (holds of days to weeks).
- How strategies are chosen: every week the losing paper accounts are retired and replaced by the
  candidates that score best on recent data with costs (fast: last 21 days, slow: last 365 days). The
  score is return % minus half the worst drawdown %. Winners are kept and studied, and improved versions
  are tested against them. Nothing ever trades real money without the owner's approval.

## What has worked and what has not (real results, paper and backtest)
Paper trading started 2026-11-09; these are 1 to 4 days of results, mostly noise, but directional:
- Working on paper:
  - "EMA pullback, 1h": in a 1-hour uptrend (EMA 50 above EMA 200), buy a pullback to the EMA and exit at
    a 2R target or a 2.5 x ATR stop. +5.5% in 3 days (3 trades, 3 wins). Its 21-day test before going
    live: +17.2%, 34 trades, worst drop 7.2%.
  - "4-timeframe alignment": SuperTrend direction agrees on 1h, 30m, 15m and 5m, volume above average;
    exit when the 15m flips. +6.5% in 4 days over 13 trades, but only 3 winners: a few big wins.
    It made money on SOL and lost on ETH.
- Not working:
  - "RSI(2) dip-buy (15m)": buys RSI(2) below 10 in the 1-hour trend direction. 36 trades, 25 wins, but
    -1.0% overall; profitable on weekdays, lost on weekends.
  - "VWAP reclaim (5m)": US-session VWAP reclaims with volume. Lost, removed.
  - "10-minute scalper": EMA 9/21 direction, 10-minute holds. 159 trades in a day, lost 1.6% to fees.
    Removed. High-frequency ideas are dead at these costs.
- Not trading yet (too early): daily trend ensemble, volatility-managed trend, volatility-filtered
  breakout, weekly strength rotation, Donchian 4h breakout.
- Long-history backtests (walk-forward, 3-year train, 6-month test, 2019 onward): daily/4h trend
  following with volatility sizing was best (out-of-sample Sharpe about 0.93, max drawdown about 8%) but
  not statistically proven. All 5-minute and 15-minute strategies lost after costs.

## What to research
1. Go wide across families: trend and time-series momentum, cross-sectional momentum between the three
   coins, breakouts, pullbacks in trends, mean reversion (only where costs allow), volatility breakouts
   and squeezes, volatility-regime switching, seasonality (hour of day, day of week, month), weekend
   effects, gap or range behaviour around fixed times, relative value (ETH/BTC, SOL/ETH ratios),
   multi-timeframe confirmation, and anything else with real evidence.
2. For each family, find the strongest evidence: peer-reviewed papers, SSRN preprints, well-documented
   practitioner research, and books. Prefer crypto-specific studies, then futures or FX studies that
   plausibly transfer. Note where results did NOT replicate.
3. Explain WHY the winners above might be winning (trend persistence on the 1-hour, SOL's higher trend
   strength, and so on) and propose concrete, testable improvements to each of them: different filters,
   exits, regime gates, or position sizing. Keep each improvement to one change at a time.
4. Explain why the losers lost (costs, weekend behaviour, chop) and what that rules out.
5. Flag the classic traps for each strategy: overfitting, look-ahead bias, survivorship, regime dependence,
   cost sensitivity.

## What to deliver
A. A short summary (under 300 words): the 5 most promising directions and why.
B. 40 strategies as a JSON array, ranked best first, at least 25 needing only OHLCV. Use exactly this shape:
{
  "name": "short plain name",
  "family": "trend | mean_reversion | breakout | volatility | seasonality | relative_value | momentum | other",
  "cadence": "fast or slow (see above)",
  "markets": "which of BTC, ETH, SOL",
  "data_needed": "OHLCV only, or exactly what else",
  "entry_long": "exact rule with every indicator setting",
  "entry_short": "exact rule, or none",
  "exit": "exact rule",
  "stop": "exact rule",
  "target": "exact rule or none",
  "params": {"param_name": [2 or 3 values]},
  "expected_trades_per_week": "per coin, a number",
  "why_it_should_work": "the market mechanism in 2-3 sentences",
  "evidence": [{"source": "title", "url": "link", "what_it_found": "one line"}],
  "evidence_quality": "peer-reviewed | practitioner | anecdotal | none",
  "fails_when": "conditions where it loses",
  "cost_sensitivity": "low | medium | high, and why",
  "overlap_with": "which strategy above it resembles, or none"
}
Rules for the strategies:
- Exact, mechanical rules only. No discretion, no "strong momentum", no chart reading.
- At most 3 tunable parameters each, with 2 or 3 values per parameter.
- Expected gross edge per trade must plausibly exceed 0.16% round-trip costs; say how you judged that.
- No strategy that needs sub-minute data, an order book, or speed (latency arbitrage, market making).
- Rules must use only information available at the close of the signal bar (no look-ahead).
C. Improvements for the current winners, 3 to 5 each, in the same JSON shape with "name" set to
   "<winner name> v2: <change>".
D. A list of ideas you rejected and why (costs, data, weak evidence), so they are not researched again.

Do not include performance numbers you cannot source. If evidence is thin, say so plainly.
````
