---
name: trading-desk
description: Start here for the Ultimate Claude Trading Skill. Explains the whole desk (backtest, forward test, paper, live with guardrails, self-learning, phone dashboard), checks the setup and routes to the right skill. Use when the user says "set up the trading desk", "how does this work", "what's the status of my strategies", "trading bot", or "where do I start".
---

# Trading desk

A trading desk that runs on the user's own PC. The source of truth is `docs/BLUEPRINT.md`; progress is in `docs/ROADMAP.md`. Read both before changing anything.

## First run
1. Check Python 3.10+: `python --version`. The engine uses the standard library only.
2. From the repo root, run the offline tests: `python -m unittest discover -s tests`. All must pass.
3. Download history (public Coinbase data, no key): `python -m tradedesk data --gran 3600 --days 2870`.
4. Run `python research/corrected_tournament.py` then `python research/summarize_corrected.py`, and explain `reports/corrected/summary.md` to the user in plain words. (The older `python -m tradedesk tournament` uses the legacy closed-trade engine.)
5. Show the ladder: `python -m tradedesk status`.

## Route
| The user wants | Skill |
|---|---|
| to test or compare strategies | trading-backtest |
| to add their own strategy or TradingView indicator | trading-strategy-lab |
| paper trading, or the phone app connection | trading-paper-desk |
| the bot to learn from its trades | trading-learn |
| to change limits, or the kill switch | trading-risk-rules |
| real money | trading-go-live |
| which exchange, or leverage limits | trading-venues |

## Never
- Print, log or ask for API keys in chat. Keys live in environment variables only.
- Place a live order yourself, or set `TRADEDESK_LIVE=1` for the user.
- Lower a promotion gate so a strategy passes. Report the failure honestly.
- Call a backtest a promise. Say "not financial advice" whenever you discuss results.
