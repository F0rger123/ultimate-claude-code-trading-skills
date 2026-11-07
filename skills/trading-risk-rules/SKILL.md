---
name: trading-risk-rules
description: Read and change the desk's risk rules and use the kill switch. Explains what each guardrail does and which ones can never be switched off. Use when the user says "change my max loss", "set a daily limit", "more leverage", "stop everything", "kill switch", or "what are my rules".
---

# Risk rules

The rules live in `state/rules.json`. The app edits the same file through the API, and `normalize()` in `tradedesk/risk.py` enforces the floors and ceilings.

| Rule | Default | Note |
|---|---|---|
| max_loss_per_trade_usd | 30 | loss at the stop, after rounding to whole contracts |
| risk_pct | 1% | of equity; the smaller of this and the max loss wins |
| daily_loss_cap_usd | 150 | today's realized loss + open risk + the new trade must fit under it; minimum $1 |
| max_leverage | 5 | also capped per coin by the exchange's overnight limit |
| max_open_positions / max_trades_per_day | 3 / 12 | |
| news_filter + news_blackout | on, [] | UTC windows, for example `{"start":"2026-12-10T18:55:00Z","end":"2026-12-10T19:30:00Z","label":"FOMC"}` |
| kill_switch | off | on = close every trade and block new entries |
| live_enabled | off | needs the typed confirmation in the app |

These stay on whatever the values are:
- a stop on every order (resting on the exchange in live)
- the daily loss cap
- the loss cap per trade
- the leverage cap
- the kill switch
- stale-data protection

If the user asks to remove a guardrail, say which ones cannot be removed and why, and offer to change its value instead.
