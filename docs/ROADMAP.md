# Roadmap

Check items off as they land. Every phase ends with its check passing. Blueprint: `docs/BLUEPRINT.md`.

## Phase 0: Blueprint and verification
- [x] Venue research and verified facts (`docs/VERIFIED_APIS.md`)
- [x] Blueprint, strategies, safety docs
- [x] Dashboard mockups (Agency Zero look)

## Phase 1: Engine core (check: `python -m unittest` passes offline)
- [x] Candle download and cache (Coinbase spot and perp, public)
- [x] Resampling 5m to 15m, 30m and 1h
- [x] Indicators: EMA, SMA, ATR, RSI, SuperTrend, Donchian, daily VWAP, volume average
- [x] Six strategies, long and short
- [x] Backtester with fees, slippage, funding, leverage and liquidation, contract sizing
- [x] Metrics and Monte Carlo
- [x] Walk-forward with out-of-sample scoring
- [x] Tournament and ladder gates

## Phase 2: Real backtests (check: report written from real data)
- [x] Download 2 years of 5m BTC, ETH, SOL
- [x] Run the tournament, write `reports/tournament-latest.md`
- [ ] Owner sends the real TradingView indicator name and settings; swap the stand-in

## Phase 3: Paper trading (check: paper loop runs 24h without error)
- [x] Risk guard and `rules.json`
- [x] Journal (SQLite)
- [x] Paper loop on live Coinbase perp candles
- [x] Phone API server with token
- [ ] Run on the always-on PC as a scheduled task (owner's PC)

## Phase 4: Dashboard app (check: debug APK installs and shows demo data)
- [x] Compose app: Home, Trades, Calendar, Strategies, Rules
- [x] Demo mode, and live mode against `server.py`
- [x] Debug APK build
- [ ] Owner installs Tailscale on the PC and phone

## Phase 5: Live, small (check: owner unlock, read-only connection check passes)
- [x] Coinbase CFM adapter: balance, positions, bracket order, close, cancel (gated)
- [x] `tradedesk check-live`: read-only connection test
- [ ] Owner creates a CDP key (view and trade) and sets env vars
- [ ] A strategy passes the paper gate
- [ ] Owner unlocks live in the app

## Phase 6: Learning and growth
- [x] Journal analysis and filter proposals (`learn.py`)
- [ ] Monthly re-fit scheduled
- [ ] Funding-rate history collector (needed for a funding strategy)
- [ ] News-only strategy experiment
- [ ] Kraken US perps adapter, once Kraken documents API access
