# Risk management

Hard rules live in `tradedesk/risk.py` and `tradedesk/desk.py`. They are plain code; no AI output can change
them. The owner edits values (not their existence) from the phone app or `rules.json`.

| Rule | Default | Floor / ceiling | Where enforced |
|---|---|---|---|
| Risk per trade | 0.5% of equity | 0.05% / 5% | sizing (`risk.size`) |
| Max loss per trade | $30 | ≥ $1 | `risk.check` |
| Daily loss cap (realized + open risk + new trade) | $150 | ≥ $1 | `risk.check` |
| Max leverage | 5x, and never above the exchange overnight limit (BTC 3.9x, ETH 3.3x, SOL 1.8x) | 1x / 20x | sizing + `risk.check` |
| Max open positions / trades per day | 3 / 12 | ≥ 1 | `risk.check` |
| Drawdown warning | 7.5% of marked equity → new risk halved | 1% / 50% | `desk.try_enter` |
| Drawdown block | 10% → no new entries | 2% / 50% | `desk.try_enter` |
| Drawdown halt | 15% → flatten, kill switch on, only the owner resumes | 2% / 50% | `desk.drawdown_halt` |
| Stale data | no new bar for 3 bar lengths → no entries | – | `risk.check` |
| News blackout | owner-listed UTC windows | – | `risk.check` |
| Kill switch | checked before every order; flattens everything | – | `desk.step` |

## Never
- **No martingale:** never increase size after losses, never average down without a cap.
- **No money movement:** never withdraw or transfer funds. API keys must be created without transfer
  permission. The code has no withdrawal function.
- **No automatic promotion:** never promote a strategy between money stages without the owner's approval.

## Live requires all of
1. a strategy at stage `small_live` or above
2. `live_enabled` set in the app, which needs a typed confirmation
3. `TRADEDESK_LIVE=1` on the PC
4. risk checks passing, with the kill switch off

Live is off today.

## Limits of these rules
- Stops can fill worse than their price in gaps.
- Exchanges can halt.
- A PC outage stops new decisions, though stops resting on the exchange stay in place.
- The 15% halt is an operating threshold, not a maximum possible loss.
