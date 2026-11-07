---
name: trading-learn
description: The self-learning loop. Analyze the trade journal and out-of-sample trades by context (hour, weekday, volatility, trend, volume, signal age), propose filters, and test each proposal on unseen data before it can be used. Use when the user says "learn from the trades", "what's not working", "improve the strategy", "self-improve", or on a weekly schedule.
---

# Learning loop

Run `python -m tradedesk learn`, or narrow it with `--strategies donchian_1h --symbols ETH`. Results go to `reports/learn-latest.json`.

## How it decides
1. It groups trades by each context field.
2. It flags a group when the group has 30 or more trades and averages -0.2R or worse, while the strategy as a whole is positive. If the strategy is losing overall, its worst pockets are shown as diagnostics only.
3. Each flag becomes a proposal: the same strategy, skipping that group.
4. Walk-forward re-runs each proposal. It is marked PROMOTE only if its average out-of-sample result improves by 0.05R or more and it keeps at least 70% of the trades.
5. A promoted variant goes back onto the ladder at **forward**. Nothing edits live settings.

## Explain to the user
Learning from a small sample mostly learns noise, which is why every idea must win on data it never saw. Report the rejected ideas too: they are the evidence that the loop is honest.
