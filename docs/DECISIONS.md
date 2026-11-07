# Decisions

Newest first. Each entry says what was decided, why, and who decided it.

## 2026-11-07
- **The learning loop judges ideas only on later trades.** Proposals come from the first half of the OOS trades and
  are scored on the second half. The first version found and scored ideas on the same trades and "promoted" five,
  including "skip Tuesdays". Under the split, all five were rejected. (Claude's call, after catching the bias.)
- **Venue: Coinbase Financial Markets.** This is the only US-regulated perp venue where official docs confirm API
  trading with brackets. BloFin and Hyperliquid bar US persons, so we won't build for them, VPNs included. (Owner
  agreed to a US-regulated venue; Claude picked Coinbase from the verified docs.)
- **Leverage cap = Coinbase overnight margin, for sizing and in backtests.** Positions held past 4pm ET then never
  need extra margin. Risk per trade comes from the stop, so the cap mostly affects margin use, not risk. (Claude's call.)
- **Backtests on spot candles.** Perp history only starts in mid-2025, too short for walk-forward. Every report says
  so. (Claude's call.)
- **Costs: 0.06% fee + 0.02% slippage per side, 0.001%/h funding.** Coinbase's docs mention a 0.05% introductory
  fee; rounding up keeps the results conservative. (Claude's call.)
- **Monte Carlo is a bootstrap with replacement, not a shuffle.** With compounding, shuffling the order can't change
  the final return. (Claude's call, after catching the problem in the first run.)
- **SuperTrend(10, 3) stands in for the owner's TradingView indicator** until it's named. (Claude's call; owner to supply.)
- **Standard library only for the engine.** Zero install on any PC. The live broker adds the official Coinbase SDK.
  (Claude's call.)
- **Guardrails always on; their values are set in the app.** The owner said they are "not worried about hard
  stoppers". The floors exist so a slider can never switch a guardrail off. (Claude's call; values are the owner's.)
