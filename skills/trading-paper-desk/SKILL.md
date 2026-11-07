---
name: trading-paper-desk
description: Run the forward-test and paper-trading desk on the user's PC and connect the phone dashboard over Tailscale. Use when the user says "start paper trading", "run the bot", "keep it running", "connect my phone", "the app shows demo data", or "set it up on my old PC".
---

# Paper desk and phone link

## What runs
- `python -m tradedesk desk`: every 30 seconds it pulls closed 5-minute Coinbase perp candles (public data), runs every strategy at stage forward or above, manages positions, and journals everything to `state/journal.sqlite`.
  - **forward:** signals, with simulated outcomes
  - **paper:** a simulated account funded with `rules.paper_equity_usd`
- `python -m tradedesk serve --host <tailscale-ip>`: the phone API. It needs `TRADEDESK_API_TOKEN` (24 or more random characters) in the environment.

## Always-on PC (Windows)
The private dashboard repo has `desk/setup.ps1` and `desk/install-tasks.ps1`, which do steps 2 and 4.
1. Install Python 3.10+ and clone this repo on the PC.
2. Create a random token and save it as the user environment variable `TRADEDESK_API_TOKEN`, without printing it in chat. The user reads it on the PC and types it into the app.
3. Install Tailscale on the PC and the phone, signed into the same account. MagicDNS gives the PC a name like `pc-name.tailXXXX.ts.net`.
4. Register `desk` and `serve` as scheduled tasks that run at log-on and restart if they fail.
5. In the app, open Rules > Connection and enter `http://pc-name.tailXXXX.ts.net:8787` and the token.

## Health
`python -m tradedesk status` shows the ladder, the open trades and the latest events. If data goes stale (no new bar for 15 minutes), the desk opens no new trades.
