# Changelog

## 2026-11-09: Ultimate Claude Trading Skill
### Added
- **Accounting:** `tradedesk/portfolio.py`, a shared mark-to-market ledger (cash, positions, fees, signed
  funding, whole contracts, gross-exposure caps, drawdown tiers).
- **Statistics:** `tradedesk/metrics.py`
  - Sharpe, Sortino, Calmar, ES5, underwater time
  - hourly and daily drawdown on marked equity
  - block bootstrap, deflated Sharpe
- **Strategies:** `tradedesk/candidates.py`: vol-managed trend, vol-filtered breakout, weekly strength rotation.
- **Research:** `research/corrected_tournament.py`
  - leak-free walk-forward (1,095-day train / 180-day test)
  - benchmarks, risk-matched buy-and-hold
  - cost, risk and drawdown-policy stress
  - experiment registry
- **Reporting:** `research/summarize_corrected.py` (ranking with a deflated Sharpe across all trials) and
  `research/make_charts.py` (SVG evidence).
- **MNQ:** opening-range experiment (Pine v6, Python parity, synthetic tests).
- **Docs:** methodology, math, risk, setup, sources, funding, ORB, security, contributing.

### Changed
- **Desk:** owner drawdown tiers (7.5% warn → half risk, 10% block, 15% flatten + halt) on **marked**
  paper equity. Default risk is 0.5% per trade.
- **Reports:** old reports moved to `reports/legacy/` as HISTORICAL LEGACY RESULTS (closed-trade drawdown).

### Results
- 77 trials registered. All candidate/market pairs were positive OOS, but none is statistically proven
  (deflated Sharpe < 0.95). Spot versions are cost-fragile.

## 2026-11-07: initial release
- tradedesk engine, 8 Claude Code skills, blueprint, first tournaments.
