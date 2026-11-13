# Changelog

## 2026-11-13: study and improve
- `tradedesk/study.py`: tags every paper trade with its market context (session, weekday, trend, volatility,
  coin, side), reports where each account makes and loses money, and builds improved versions of winning
  accounts (one setting changed, or skipping a losing group), judged on data the parent never paper-traded.
- The weekly run studies first; qualified improvements compete for open slots as "v2" accounts.
- Only losing accounts can be cut. Family memory now counts running accounts too.
- `tradedesk/library.py` and `research/strategy_bank/` for researched strategies; `python -m tradedesk study`.

## 2026-11-09: weekly paper shake-up
- `tradedesk/rotation.py`: every Monday the desk ranks the paper accounts, retires the bottom three
  (after a 6-day fast / 27-day slow trial; the $50 pilot mirror is protected), tests up to three
  settings of every strategy family on recent data with costs, and starts the best three as new paper
  accounts. Retired results stay in the all-accounts total and feed a per-family memory.
- Paper accounts now live in `state/paper/roster.json`; retired ones in `state/paper/retired/`.
- `python -m tradedesk rotate` (`--dry-run`, `--force`), `GET /api/rotation`, skill `trading-rotation`.
- New `pb_fast_scalp10` account (trades about every 10 minutes, small size). Fast-account notes now
  state their real trade frequency.

## 2026-11-09: paper trading started
- `tradedesk/paper.py`: five paper books on the research portfolio engine, replayed hourly from a fixed
  start (2026-11-09 07:00 UTC). Same code as the backtest.
  - perp books ($10,000 each): trend ensemble, vol-managed trend, vol-filtered breakout
  - spot books: weekly rotation ($10,000) and a $50 spot pilot mirror
- `portfolio.run`: `close_at_end=False` keeps positions open for paper; `kill_at` flattens and blocks entries.
- The desk runs the paper books every hour. The phone API shows total paper equity and each book.

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
