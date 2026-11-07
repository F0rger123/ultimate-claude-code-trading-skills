---
name: trading-strategy-lab
description: Add or change a trading strategy in tradedesk, including porting a TradingView indicator, without look-ahead bias. Use when the user says "add my strategy", "I use this TradingView indicator", "code this setup", "change the stop", or "try a new idea".
---

# Strategy lab

Strategies live in `tradedesk/strategies.py`. A strategy is a class with:
- `entry(i)`: returns `None` or `{"side": 1|-1, "stop": price, "target": price|None}`. It may use data only up to the close of 5-minute bar `i`.
- `exit(i, pos)`: returns `True` to exit at the next bar's open.
- `grid`: a small parameter grid for walk-forward, with 2-3 values per setting and about 8 combinations at most.
- Higher timeframes: `self.m.frame(3600)` and `self.m.at(3600, series, i)`. These only ever return higher-timeframe bars that have already closed.

## Porting a TradingView indicator
1. Ask for the exact indicator name and settings. Also ask for the Pine Script source if the indicator is open-source (TradingView shows "Source code" on open indicators).
2. Add a branch to `indicators.signal_line()` that returns +1, -1 or None for each bar.
3. Set `kind="<new>"` in the params of the `mtf_*` strategies.
4. If the source is closed, say so and approximate it with logic you document. Never claim the approximation is the same indicator.

## Checks before running the tournament
- Run `python -m unittest discover -s tests`. The `NoLookahead` test must pass for the new class.
- Add the class to `ALL`, and give it a `source` that names where the idea came from.
- Then run trading-backtest.
