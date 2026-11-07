---
name: trading-go-live
description: The checklist for moving a strategy from paper to real money on Coinbase US perp-style futures, with the read-only connection check. Use when the user says "go live", "trade real money", "connect my Coinbase", "automate it for real", or "scale up".
---

# Going live

Only the owner can take these steps. Walk them through it, and never take any of the steps for them.

## Preconditions (check each and report it)
- [ ] The strategy is at stage `paper` and has passed the paper gate in `tradedesk/ladder.py`: 60 days or 100 trades, profit factor of 1.15 or more, drawdown of 10% or less, and zero rule breaches.
- [ ] The Coinbase account is verified and has futures (Coinbase Financial Markets) enabled.

## Owner steps
1. Create a CDP API key on the Coinbase Developer Platform with **view and trade** permissions, never transfer. If an IP allowlist is offered, add the PC's public IP.
2. On the PC, set the user environment variables `COINBASE_API_KEY` and `COINBASE_API_SECRET`. Never paste them in chat.
3. Install the official SDK (Apache-2.0): `pip install coinbase-advanced-py`.
4. Run `python -m tradedesk check-live`. It reads the balance and positions, and previews a 1-contract order without placing it.
5. In the app, open Rules > Live and type the confirmation sentence.
6. On the PC, set `TRADEDESK_LIVE=1` for the desk task, then restart the task.

## How live works
- Each entry is a market order with a bracket attached, so the stop rests on Coinbase from the start.
- Strategies without a target get a far take-profit at 10R, so the bracket still exists.
- When a strategy exits on its own signal, the desk closes the position and then cancels the leftover bracket orders.
- Leverage is set to the per-coin cap, with isolated margin. Size comes from the stop.
- Start at the smallest size. Size can at most double per month, and only after 90 days with a profit factor of 1.15 or more and the owner's approval.

## Say plainly
Paper results are better than live results will be, because of slippage and outages. Most traders who use leverage lose money. This is not financial advice.
