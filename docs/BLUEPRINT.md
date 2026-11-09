# Blueprint: Ultimate Claude Trading Skill

This is the source of truth for the whole build. Every change gets checked against it, and
`docs/ROADMAP.md` tracks progress against it. If the code and this file disagree, either the
code is wrong or this file gets updated on purpose, with the reason written in
`docs/DECISIONS.md`.

Written 2026-11-07. Not financial advice. Most people who trade with leverage lose money.

## 1. What this is

A trading desk you run on your own PC. It:

1. downloads free market data,
2. tests trading strategies honestly on years of past data (backtest),
3. tests the survivors on data they have never seen (walk-forward and forward test),
4. paper-trades the winners in real time with fake money,
5. trades real money only after you unlock it in the app, with guardrails that cannot be
   switched off, and
6. learns from its own trade journal. It proposes changes, and a change only goes live after it
   passes the same tests on unseen data.

There are two repositories:

| Repo | Visibility | Holds |
|---|---|---|
| `ultimate-claude-code-trading-skills` | public, MIT | the `tradedesk` Python engine, the Claude Code skills, the docs |
| `claude-trading-desk` | private | the Android dashboard app, your own `rules.json` and strategy settings, the run scripts for your PC |

## 2. Goals, non-goals, anti-goals

**Goals**
- One engine runs backtest, paper and live with the same strategy code, so live does what the test did.
- Every result counts trading fees, slippage and funding.
- A strategy climbs a ladder (backtest, forward, paper, small live, scaled) and drops back if it slips.
- The phone app shows balance, P&L, open and closed trades, a P&L calendar, growth charts and
  ladder status, and holds your rules and the kill switch.
- Zero-install engine: Python 3.10+ standard library only. The live broker adds one official SDK.

**Non-goals (for now)**
- High-frequency or tick-level trading. The bot works on closed 5-minute bars or slower.
- Options, and spot margin borrowing.
- Exchanges that bar US persons.

**Anti-goals (a failure even if it "works")**
- A backtest that only looks good because it was tuned on the same data it was scored on.
- Any order sent without a stop resting on the exchange.
- Any path where the bot trades live before you unlock it in the app.
- API keys in chat, in git, or in logs.

## 3. Venue: Coinbase Financial Markets (US perp-style futures)

Picked because it is the only US-regulated venue where official docs confirm API trading for perps,
with brackets, positions and close-position endpoints. Facts and sources are in `docs/VERIFIED_APIS.md`.

- **Products:** 29 perps, for example `BIP-20DEC30-CDE` (BTC, 0.01 BTC per contract),
  `ETP-20DEC30-CDE` (ETH, 0.1 ETH) and `SLP-20DEC30-CDE` (SOL, 5 SOL). Funding is charged hourly.
- **Leverage, from the live public API on 2026-11-07:**
  - BTC and ETH: 10x during the intraday window (weekdays 8am to 4pm ET), about 4–5x long and
    3–4x short overnight.
  - SOL, XRP and most alts: 4–5x intraday.
  - Index and gold perps: 20x.
- **Order types:** market, limit, stop-limit, and a trigger bracket (take-profit plus stop) that
  can be attached to the entry order.
- **No futures sandbox,** so paper trading runs on our own simulator, fed by live public candles.
- **Fallback venue:** Kraken US perps (on Bitnomial). The product exists, but US API trading
  is unconfirmed. An adapter is planned once Kraken documents it.

Why 10x is enough: risk per trade is set by stop distance times size, not by leverage. Leverage
only decides how much margin a trade ties up. The engine sizes from the stop and caps leverage at
`min(rules.max_leverage, exchange margin limit for the current window)`.

## 4. Stack

| Part | Choice | Why |
|---|---|---|
| Engine | Python 3.10+, standard library only | runs on any PC, no install trouble, the same code on both PCs |
| Data | Coinbase public candles (no key): Exchange API for spot history back to 2015, Advanced Trade API for perp candles | free, US-legal, documented |
| Storage | gzip CSV for candles, SQLite for the journal and state | one file each, easy to back up |
| Live broker | `coinbase-advanced-py` (official SDK) for signing, REST for orders | official, keys from env vars only |
| Phone API | standard-library HTTP server with a bearer token | no extra installs |
| Phone link | Tailscale (free) between PC and phone | no ports opened to the internet |
| App | Kotlin and Jetpack Compose, the same toolchain as LifeSteal | proven to build on this PC |
| Host | older always-on PC runs `paper` and `live`; gaming PC runs heavy backtests | crypto never closes; exchange-side stops cover a PC crash |

## 5. How the pieces connect

```
data.py ──> candles cache ──> strategies ──> backtest.py / walkforward.py ──> tournament.py ──> ladder.json
                                   │
                                   └──> paper.py (live candles, simulated fills) ──┐
                                   └──> live.py (Coinbase CFM, gated) ─────────────┤
                                                                                   v
                         risk.py checks every order  <── rules.json (edited from the app)
                                                                                   │
                                     journal.sqlite <──────────────────────────────┘
                                          │
                                     learn.py ──> proposals ──> walk-forward ──> promote or reject
                                          │
                                     server.py ──> phone app (Tailscale + token)
```

## 6. Strategies (the tournament)

Every strategy trades both long and short on closed bars, with the same cost model. The full
rules are in `docs/STRATEGIES.md`.

| id | Family | Source of the idea |
|---|---|---|
| `mtf_quick` | your 4-timeframe alignment (1h, 30m, 15m, 5m), exit on the 15m flip | the owner's own strategy |
| `mtf_swing` | 1h and 30m alignment, exit on the 30m flip | the owner's own strategy |
| `donchian_breakout` | 20-bar channel breakout with a trend filter | classic trend following (Turtle-style) |
| `ema_pullback` | buy pullbacks to the 20 EMA when 50 > 200 (reverse for shorts) | common day-trader setup |
| `vwap_reclaim` | trend-day reclaim of the daily VWAP | common intraday setup |
| `rsi2_reversion` | RSI(2) extremes in the direction of the 1h trend | Connors-style mean reversion |

The owner's indicator: the TradingView buy/sell indicator isn't named yet. Until it is, `mtf_*` uses
SuperTrend(10, 3) as a stand-in signal and volume above its 20-bar average as the volume check.
Swapping in the real indicator touches one function: `tradedesk/indicators.py: signal_line`.

News is a filter, not a trigger: `rules.news_blackout` holds UTC windows when no new entries
open (CPI, FOMC). A news-only strategy is a later experiment (roadmap phase 6).

## 7. Testing honestly

- **Costs:** taker fee 0.06% per side, slippage 0.02% per side, and funding charged hourly at a
  configurable rate (default 0.001% per hour against the position).
- **Fills:** entries happen at the next bar's open. If the stop and target are both inside one bar,
  the stop wins. A gap past the stop fills at the bar's open.
- **Leverage:** if the liquidation price comes before the stop, the trade is liquidated and loses
  its whole margin.
- **Walk-forward:** pick parameters on 6 months, score them on the next 2 months, step forward 2
  months, and repeat. Only the out-of-sample (OOS) results count.
- **Monte Carlo:** shuffle the OOS trades 2,000 times, and report the 5th-percentile return and
  the 95th-percentile drawdown.
- **Data:** the backtest uses spot BTC-USD, ETH-USD and SOL-USD 5m bars, because perp history
  only starts in mid-2025. That approximation is noted in every report.

## 8. The ladder (promotion gates)

| From → to | Gate (all must pass) |
|---|---|
| backtest → forward | OOS ≥ 100 trades; profit factor ≥ 1.20 after costs; max drawdown ≤ 20% at 1% risk; ≥ 60% of OOS windows profitable; Monte Carlo 5th-percentile return > 0 |
| forward → paper | ≥ 30 days and ≥ 30 signals on new data with frozen parameters; profit factor ≥ 1.10; expectancy at least half the backtest's |
| paper → small live | ≥ 60 days or 100 trades; profit factor ≥ 1.15; drawdown ≤ 10%; zero risk-rule breaches; **owner unlocks live in the app** |
| small live → scaled | ≥ 90 days live; profit factor ≥ 1.15; real slippage ≤ 1.5x modeled; **owner approves**; size at most doubles per month |
| any → one step down | profit factor over the last 50 trades < 0.90, or drawdown > the backtest's 95th-percentile drawdown |

## 9. Guardrails (always on)

You can set every value from the app. You cannot switch off the existence of these:

1. A stop resting on the exchange for every position. An order without one is refused.
2. A daily loss cap (the minimum allowed setting is $1). When it is hit, no new entries until the
   next UTC day.
3. Max loss per trade, and max leverage (never above the exchange's limit for the current window).
4. Max open positions and max trades per day.
5. A kill switch: cancel all orders, close all positions, block new entries until you resume.
6. Live mode needs three things together: `rules.live_enabled` (set in the app), the environment
   variable `TRADEDESK_LIVE=1` on the PC, and the strategy at stage `small_live` or above.
7. If data goes stale (no fresh bar for 3 bar lengths), no new entries. Existing stops stay on the exchange.
8. Keys come from environment variables only and are never logged.

## 10. Self-learning loop

1. Every trade is journaled with its context: strategy, symbol, side, UTC hour, weekday,
   volatility regime, trend regime, volume ratio, funding, and the R result.
2. `learn.py` runs weekly. It groups trades by each context field and flags a group with at least
   30 trades whose expectancy is ≤ -0.2R while the strategy overall is positive.
3. Each flag becomes a proposal: the same strategy with a filter that skips that group.
4. A proposal runs through walk-forward on OOS data. It is promoted only if it beats its parent's
   OOS score by ≥ 0.05R expectancy and keeps ≥ 70% of the trades.
5. Promoted variants re-enter the ladder at `forward`. Nothing edits live settings directly.
6. Parameters are re-fitted monthly the same way.

## 11. Phone app

Screens (mockup: Trading Bot Dashboard canvas):

- **Home:** balance, P&L, growth chart, open trades
- **Trades:** open and closed
- **Calendar:** day-by-day P&L
- **Strategies:** ladder status
- **Rules:** sliders, live lock, kill switch

The look is Agency Zero's: black, white and grays, with green only for money. The app reads
`server.py` over Tailscale with a bearer token, and has a demo mode with made-up data when no
server is set. Rules edits post back to `rules.json`. Live unlock needs a typed confirmation.

## 12. What only the owner can do

- Open and verify a Coinbase account with futures enabled.
- Create a CDP API key (view and trade permissions; never transfer) and set it as environment
  variables on the PC.
- Install Tailscale on the PC and phone.
- Unlock live in the app, and approve each scale-up.
