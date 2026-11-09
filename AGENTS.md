# AI agent guide

If someone pasted this repo's link into Claude, ChatGPT or another assistant, read this first. It tells you how to walk them through the project safely.

## 1. What this is, in plain words
A trading "desk" that runs on the person's own computer:
- It tests trading strategies on years of past crypto prices, with fees counted (a backtest).
- It keeps testing the ones that pass, first on new data and then with pretend money (forward test, then paper trading).
- It can trade real money on Coinbase's US crypto futures only after the person unlocks it, and it always uses safety limits.
- It learns from its own trades, but a change is only used after it proves itself on data it has never seen.

The project is honest about results. As of 2026-11-09, every tested candidate was positive out of sample but none is statistically proven; the best are paper-tested.
It is not financial advice, and most people who trade with leverage lose money.

## 2. Ask the person first
1. "Which computer will run this, and is it on all the time?" Crypto trades around the clock.
2. "Do you have Python 3.10 or newer?" If they aren't sure, help them check: `python --version`.
3. "Do you just want to see the test results, or also run paper trading?"
4. "Do you have your own strategy or TradingView indicator you want tested?" If so, get the indicator name and settings.
5. Only if they ask about real money: "Do you have a verified Coinbase account with futures turned on?"

## 3. Set it up and check it worked
```bash
git clone https://github.com/F0rger123/ultimate-claude-trading-skill
cd ultimate-claude-trading-skill
python -m unittest discover -s tests      # expect: OK
python -m tradedesk data --gran 3600 --days 2870   # hourly history since 2019, free public data, no account
python research/corrected_tournament.py            # about 2 minutes
python research/summarize_corrected.py             # writes reports/corrected/summary.md
python -m tradedesk status
```
It worked if the tests say OK and `reports/corrected/summary.md` exists. Read that report to them in plain words:
what passed, what failed, and why.

In Claude Code you can also install the skills as a plugin:
```
/plugin marketplace add F0rger123/ultimate-claude-trading-skill
/plugin install ultimate-claude-trading-skill@ultimate-claude-trading-skill
```

## 4. How to use it
- **Paper trading:** `python -m tradedesk desk` keeps running and journals trades. Strategies only trade once they reach the forward stage.
- **Phone dashboard API:** `python -m tradedesk serve --host <tailscale-ip>`. It needs `TRADEDESK_API_TOKEN` set as an environment variable on the PC.
- **Learning loop:** `python -m tradedesk learn`.
- **Weekly shake-up:** the desk retires the 3 worst paper accounts every Monday and starts 3 new ones (paper only). Preview with `python -m tradedesk rotate --dry-run`.
- **Rules and kill switch:** in `state/rules.json` or the phone app.
- The skills in `skills/` hold the details for each task. `docs/BLUEPRINT.md` is the source of truth.

## 5. Never
- Never ask for, print or store API keys or secrets in chat, files or logs. Keys go only in the person's own environment variables, typed by them.
- Never place a real order, set `TRADEDESK_LIVE=1`, or unlock live trading for them. Those are their steps.
- Never spend money or move funds.
- Never lower a test bar so a strategy passes, or describe backtest results as a promise.
- Never help someone use an exchange their country is barred from, for example with a VPN.
- Never touch a live account or "production" without the person's clear yes for that exact step.
