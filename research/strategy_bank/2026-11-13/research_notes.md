# Crypto paper-trading research bank — November 13, 2026

## Contents and reading order

1. `strategies_40.json`: exactly 40 ranked machine-readable strategy objects, 34 executable using only OHLCV and 6 explicitly parked pending more data. Every object has the exact 18 requested keys. Rank is **research priority**, NOT measured expected performance.
2. `winner_improvements_10.json`: exactly 10 one-change-at-a-time hypothesis variants, five per user-reported early winner, using the same 18-key schema.
3. `ranked_index.csv`: short sortable catalog.
4. This file: design conventions, evidence assessment, performance honesty, rejection ledger, and testing protocol.

## Evidentiary status — read before deployment

- The 40 rules were DESIGNED for this request. They were not backtested by this research and have **no measured gross edge** or measured weekly signal frequency. The `expected_trades_per_week` entries are **rough, unverified planning estimates**, not historical results. Their 1%-risk account position sizing, 1.5x leverage ceiling, and 10/15% account drawdown controls are preserved unchanged.
- The sources linked in each `evidence` array support a *market mechanism or strategy family* and do NOT generally test that object's precise indicators or parameters. `evidence_quality` classifies the strongest *relevant literature*, NOT a replication of the precise strategy. `none` marks a documented negative-control hypothesis.
- User-reported paper results (November 9–13, 2026) and user-reported backtests are **unverified user-provided observations**, not new measurements produced here.
- A large target, a wide stop, a high ATR, or a literature citation is NOT evidence of positive expected gross return. Therefore **none of the proposals is yet eligible to be described as an edge**, despite a price move large enough to cover fees being plausible.

## Data, indicator and fill conventions

- All timestamps are UTC except explicit America/New_York calendar restrictions and CFM maintenance windows. Aggregate spot 5-minute OHLCV into 15m/30m/1h/4h/daily bars anchored 00:00 UTC (hourly history supplies 1h/4h/daily for long years). Never forward-fill missing 5m or daily bar intervals into signals; time-based windows use complete contiguous observations.
- **Signal:** evaluate only after the relevant last closed bar; multi-timeframe filters use only the most recently **completed** higher-timeframe bar, not the one still forming. Price channels exclude the current bar unless explicitly called current, while entries use the just-closed signal bar. A fixed-time window or event timestamp is determined before signal evaluation. All rolling percentile, ranking, regression and ADF training windows exclude the current bar.
- **Execution:** paper enter/exit at the **next available CFM futures opening trade/marketable fill** after the signal, not at the signal-bar close. A minimum paper simulation can approximate next spot 5m/1h open plus costs but must be flagged a **spot-proxy backtest**, not a CFM futures replication. Portfolio drawdown and stops should mark to actual futures, if available.
- Use one position per coin per strategy, one entry only on false→true transition of full entry predicate, no additional positions while signal remains true, no same-bar flip. Pair legs open and flatten together, at realized execution prices; sum of gross absolute notionals is subject to the fixed 1.5x cap and stop-loss budget.
- **Stops and targets:** initial ATR or R distances calculated using last closed signal bar and actual filled entry, then held fixed unless explicit tighten-only trail. Resting orders can trigger intrabar in real time using the price actually available; backtests using OHLCV with stop and target touched in the same bar must conservatively assume **stop first**. Apply stops before any bar-close signal. Gaps after Friday maintenance or outages can exceed the designated risk, so stop-based 1% risk is a planned cap, not guaranteed realized maximum.
- EMA: recursively smoothed closing price alpha=2/(N+1), seed with first N-bar SMA. SMA: ordinary trailing mean. RSI: Wilder smoothing of gains/losses (length named in rule). ATR: Wilder true range smoothing; ADX/+DI/-DI: Wilder directional movement (14-period unless specified). MACD: EMA12−EMA26 with EMA9 signal unless individual values vary. Bollinger: SMA20 ± 2 * sample std of 20 closed closes; 4h squeeze width percentile is trailing, computed on prior bars. SuperTrend: Wilder ATR10 with multiplier 3 by default. Raw upper/lower = (high+low)/2 ± multiplier * ATR. For bar t, final upper=raw upper if raw upper<previous final upper OR prior close>previous final upper, otherwise previous final upper; final lower=raw lower if raw lower>previous final lower OR prior close<previous final lower, otherwise previous final lower. Trend flips bullish when a bar closes above prior final upper, bearish when closes below prior final lower, otherwise retain preceding trend; use final lower as bullish trend band and final upper as bearish band. Initialize trend neutral until ATR10 is available and first close relative to raw midpoint determines direction. All four timeframes must use identical unit-tested logic (some libraries differ). Volume SMA20 includes just-closed bar unless explicitly prior.
- `params` are **candidate grids**. The numerical value embedded in each rule is the reference configuration; it may be in the middle of the grid. Change **one parameter at a time** in first screening, recording all trials. The portfolio's fixed risk constraints are **not** tunable. If a rule names two thresholds without a param (e.g., EMA50 and EMA200), those values are fixed.
- Some strategy descriptions operate on synthetic ratio close values and specify close-only exits; no false synthetic intrabar high/low is inferred. For pair strategies, confirm actual exchange contract sizes/minimums and ensure both legs can be executed under the fixed risk, leverage and funding rules.
- Friday CFM U.S. crypto derivatives have a published 5–6 p.m. Eastern maintenance closure; spot trading continues. Reject signals whose planned execution falls in a closed market and re-evaluate at next open. The futures venue's additional special closures should be read from its current calendar. Source: https://help.coinbase.com/en/prime/derivatives/us-derivatives-products-and-trading-hours
- SOL's historical hourly data only starts in 2021 per user; do not run its 2019–2021 walk-forward as though SOL existed in this sample. Avoid implicit look-back contamination near inception. For time-based signals use point-in-time market availability.

## Cost math, gross-edge viability test

**User baseline assumption, NOT verified history:** 0.06% taker fee + 0.02% slippage per side = **0.08% per side / 0.16% per single-leg round trip** in price-notional terms. Spot assumption 0.9% per side = **1.8% spot round trip**. Two independent futures legs each incur their own 0.16% round-trip on their individual notional; *do not* simply charge 0.16% to a spread and forget the short leg.

**User funding stress scenario (not actual historical funding):** cost 0.001% × h against the long notional. 24-hour hold=0.024%, 7 days=0.168%, 30 days=0.72% of long notional. Actual CFM funding rates are hourly, bidirectional, paid or received by both long and short sides depending on sign; they are derived from futures–spot differences. Source: https://help.coinbase.com/en/derivatives/perpetual-style-futures/funding-rate

At a hypothetical standalone trade with initial stop distance 1.0% of underlying and 2R win target, its single-leg **gross price change to target is 2.0%**, ~12.5x the nominal 0.16% fee hurdle. This checks *possible excursion*, not positive expectancy. For a binary 2R outcome with 1R stop and a constant 0.16%-of-notional fee, the break-even win rate is `(1%+0.16%)/(3% )=38.67%` (gross win=2%, gross loss=1%, minus 0.16% each); with no costs 33.33%. Actual stops depend on price/ATR and slippage; real win/loss distributions are not binary.

**Required evidence gate, per candidate and per coin:** historical gross average trading P&L / traded notional must exceed `0.16%` plus modeled carry and conditional slippage; net OOS mean must be positive with confidence intervals and a minimum number of genuinely independent trades. With 1.5x cap and actual sizing, calculate P&L, score, fee and drawdown on **account equity**, not confuse notional % with account return. A strategy without verified gross >0.16% is research-only. A fixed exit target or large ATR only makes such an edge *plausible*, never proves it.

**Specific hypothesis screens:**
- Daily/4h trend and Donchian: extended holding and 3+ ATR stops make economically meaningful wins possible, at low turnover, but funding may be larger than taker fees. Must test negative gross after long funding stress.
- 1h EMA pullback and 4-timeframe: 2R/3R payoffs can exceed 0.16% when ATR is sizable. Positive per-trade gross must be established separately; an elevated win count on three paper trades cannot do that.
- 5m/15m momentum/breakout: reject a configuration when its filled target distance on either side is <0.48% of notional (3x nominal friction), and require OOS gross mean >0.16% under actual holding times. This target-distance gate is a *pretest feasibility filter*, not a new account risk setting and not proof of edge.
- Daily/weekly seasonality: even when excursions dwarf friction, the very few independent events provide insufficient power to verify positive gross expectancy. Treat as negative controls.
- Pairs: total legs, per-leg fees, differential funding, and hedge error all matter; do not compare a raw spot ratio movement directly to a one-leg 0.16% cost.
- Six parked data-dependent strategies: no OHLCV-only backtest is valid. Funding, OI, liquidation, on-chain and FOMC event data must be added point-in-time and with known publication delays.

## B. Ranking rationale and overlap

Rank 1–10 primarily prioritizes multi-hour/daily trend continuation, whose **family-level** evidence is strongest and aligns with the user's previous longer walk-forward work. The 5m multi-timeframe strategy is elevated only due to **user-reported early paper observations**, not published evidence of the exact indicator. The last six are parked for missing data. Many strategies are closely correlated; the 40 records are **NOT 40 independent bets**. Overlap references and similarity of underlying price trends should be used to cluster strategies before portfolio selection. Cross-sectional and calendar rules remain low priority because recent research is much less encouraging for those sources of alpha.

## C. Why the user's early paper winners might be winning (not proven)

**EMA pullback, 1h:** Three successes over three days could arise from a favorable one-hour trend regime, a timely dip/reclaim entry, and positively skewed trend payoffs. Published crypto time-series momentum research makes that mechanism plausible but does not demonstrate a 1h EMA50/200 edge. Five separate single-change tests are ADX gate, ATR floor, daily confirmation, larger target, and weekday entry filter. Compare each with a frozen unchanged baseline on identical signal opportunities and cost scenarios, including the false-positive cost of excluded trades.

**4-timeframe SuperTrend alignment:** Three winners of thirteen trades can still make money if profit per winner is much larger than loss per loser. But observed SOL outperformance and ETH losses over four days cannot establish asset-specific trend strength; scale and volatility, trending regime, different fill quality or chance are all possible. The five single-change tests are SOL-only, hourly ADX gate, two-bar exit confirmation, no-weekend-entry filter, and higher relative volume. Do not combine gates before their isolated OOS incremental value is measured.

## D. Why reported losers likely failed — hypotheses, not causal findings

- **RSI2 dip (15m):** User reports 25/36 wins but -1.0% equity P&L. This is entirely compatible with small average wins, relatively few large losing trades, fees and overnight carry. The weekday/weekend split may be a small-sample coincidence, not a stable return seasonality. Analyze average gross winner/loser by coin, day and market regime before rescuing it; the catalog's slower RSI2 test is intentionally low ranked.
- **VWAP reclaim (5m):** Session VWAP breaks may be noisy in a 24/7 market with arbitrary reset time; the available OHLCV proxy does not contain futures order-flow information. The observed negative paper result supports retiring that implementation, not declaring every VWAP strategy impossible.
- **10-minute EMA scalper:** 159 trades/day imply enormous fee turnover. Even an optimistic scenario of 159 completed single-leg round trips × 0.16% = 25.44% of per-trade notional **summed across trades**, not 25.44% of account equity. Actual account fees depend on gross notional of every trade divided by equity. Repeated false starts with small price excursions face a structural hurdle; do not reinstate at these taker costs.
- **5m/15m backtest families:** User reports all prior historical variants lost after costs. Put fresh 5m candidates under a high burden of proof; do not extrapolate pre-cost significance into tradable expectancy.

## Rejection ledger — do not silently research again

1. **10-minute 9/21 EMA scalper / unrestricted high-turnover crossover:** direct paper failure, user-reported fees overwhelming average excursion; reject as-is.
2. **Existing 5m US-session VWAP reclaim:** failed user paper test; no new evidence warrants reactivation.
3. **Existing 15m RSI2 dip-buy without regime and payoff change:** 25 wins / 36 yet negative; no rescue by win rate alone.
4. **Unfiltered five-minute and fifteen-minute alpha searches:** user's longer after-cost research says these failed; any new variant needs a pre-registered specific mechanism and hard cost test.
5. **Sub-minute turn-of-candle, market making, latency arbitrage:** cannot execute from five-minute OHLCV; even published anomalies may not survive this execution model. Source: https://pmc.ncbi.nlm.nih.gov/articles/PMC10015199/
6. **Order-book imbalance, bid-ask microstructure, tape/footprint, liquidation front-running:** prohibited speed/order-book dependence or unavailable raw data; do not include as live strategies.
7. **Naive BTC/ETH/SOL cross-sectional long-winner/short-loser without regime / costs:** very small and correlated universe; recent peer-reviewed study finds virtually no robust cross-sectional crypto momentum when realistic liquidation is considered. Source: https://doi.org/10.1093/rapstu/raag011
8. **Standalone Monday/January/weekend directional trades:** literature finds return seasonality largely nonpersistent. Only explicit low-priority falsification controls remain. Source: https://doi.org/10.1016/j.frl.2024.105429
9. **ETH/BTC and SOL/ETH unconditional z-score reversion without cointegration testing:** ratios may trend for years, pairs have two-leg cost and changing hedge beta; condition on rolling tests, no blanket pairs claim. Source: https://doi.org/10.1080/14697688.2026.2653663
10. **Backtests filling the signal close, intrabar best-case stop/target, or future high-timeframe candles:** invalid look-ahead or fill optimism; reject universally.
11. **Funding arbitrage/short-premium bets built on assumed 0.001% hourly long-only payments:** actual CFM funding changes sign and is not known retrospectively from spot bars; park until hourly history. Source: https://help.coinbase.com/en/derivatives/perpetual-style-futures/funding-rate
12. **A model trained/selected on the same 21d or 365d period used as its claimed validation:** selection bias; out-of-sample testing must use data after selection.

## Weekly selection and validation protocol

1. Freeze `params`, baselines, instrumentation, family, and code hash before OOS testing. Maintain a **ledger of all attempted strategies/parameter variants** including rejected trials; do not just publish winners. The published Deflated Sharpe Ratio and reality-check literature highlight this bias: https://doi.org/10.3905/jpm.2014.40.5.094 ; https://doi.org/10.1111/0022-1082.00163
2. Data preparation: strict UTC aggregation, only fully closed higher timeframes, missing-bar exclusions, simulated fills at next tradable futures open, robust spot-futures basis sensitivity scenarios, continuous per-contract funding stress, contract multiplier/minimum trade rounding, fee and slippage scenarios (base 0.08% per side, 1.5× and 2× slippage, and a longer-hold adverse funding case).
3. Walk forward: use purged time splits with embargo at least max holding period for overlapping trade labels, train strictly before each OOS block. Apply proposed weekly selection only on its prescribed **past** 21d fast or 365d slow score `return_% - 0.5*max_drawdown_%`, then evaluate completely untouched following-week outcomes. Do not pool top-in-training as though it is unselected.
4. Compare family-level OOS trade expectancy after friction, block-bootstrapped CIs (time blocks span at least the longest typical trade), drawdown and tail events, turnover, short-vs-long carry, net profit factor, consistency by coin, weekend, trend/sideways and vol regimes. Use deflated Sharpe or reality-check controls against all trials. Never infer SOL superiority from four days.
5. Score additionally with loss probability, sample size, average gross P&L per trade, conditional costs per trade, funding per trade, expected holding hours, market/portfolio exposures, worst contiguous-loss sequence, and interval estimates. `21d fast` and `365d slow` are *selection windows*, not sufficient proof of a positive edge. Some slow strategies have fewer than 10 annual signals and should be marked `insufficient sample` rather than artificially ranked as profitable.
6. Weekly paper retirement introduces a **winner's curse**: keeping recent winners concentrates on chance positives, and retrospective evaluation must replay the full choose-retire-replace process, including warm-up, unfilled signals, capital constraints, and inactive candidates. Preserve a never-touched shadow benchmark cohort for comparison.
7. Preserve fixed risk exactly: risk budget per trade at most 1% of equity from stop distance, gross notional at most 1.5× equity, block new trades at 10% drawdown and flatten at 15%. If exchange contract size means minimum fill exceeds allowed risk/leverage, **skip the trade**, never increase risk. Kill switches and stops must be tested on simulated outages, gaps and partial fills.
8. Nothing moves from simulated to live trading without a **separate owner approval action**. This bank is hypothesis generation and experimental design, not a production-safe autonomous execution license.

## Primary research to prioritize reading

- Han, Kang, Ryu, 2026, Review of Asset Pricing Studies: https://doi.org/10.1093/rapstu/raag011 — realistic crypto TSM vs cross-sectional results.
- Moskowitz, Ooi, Pedersen, 2012, Journal of Financial Economics: https://doi.org/10.1016/j.jfineco.2011.11.003 — liquid futures TSM foundation.
- Liu, Tsyvinski, Wu, 2022, Journal of Finance: https://doi.org/10.1111/jofi.13119 — crypto factor exposure including momentum.
- Technical trading rules study, 2020, Finance Research Letters: https://doi.org/10.1016/j.frl.2019.101396 — earlier simple MA test; beware period dependence.
- Moreira & Muir, 2017, Journal of Finance: https://doi.org/10.1111/jofi.12513 — volatility management in conventional factors.
- Zaremba et al., 2021, International Review of Financial Analysis: https://doi.org/10.1016/j.irfa.2021.101908 — reversal in illiquid coins, momentum in liquid majors.
- Jasiak & Zhong, 2024, International Review of Economics & Finance: https://doi.org/10.1016/j.iref.2024.103658 — daily and intraday periodicity; not automatic return forecast.
- Hansen, Kim, Kimbrough, 2024, Journal of Financial Econometrics: https://doi.org/10.1093/jjfinec/nbac034 — systematic crypto volatility and volume timing.
- 2024 seasonality non-replication: https://doi.org/10.1016/j.frl.2024.105429
- 2026 day-of-week intraday-only effects: https://doi.org/10.1016/j.frl.2026.110634
- 2026 cointegrating pair study, includes many pairs and conditional out-of-sample findings: https://doi.org/10.1080/14697688.2026.2653663
- 2026 macro event risk: https://doi.org/10.1016/j.frl.2026.110073
- Coinbase US funding formula: https://help.coinbase.com/en/derivatives/perpetual-style-futures/funding-rate
- DSR / selection bias: https://doi.org/10.3905/jpm.2014.40.5.094
