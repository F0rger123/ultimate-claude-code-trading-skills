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
- [x] Long-history tournament (2019+, hourly): 9 near misses moved to shadow forward-testing
- [ ] Owner sends the real TradingView indicator name and settings; swap the stand-in (optional)

## Phase 3: Paper trading (check: paper loop runs 24h without error)
- [x] Risk guard and `rules.json`
- [x] Journal (SQLite)
- [x] Paper loop on live Coinbase perp candles (one live cycle verified)
- [x] Phone API server with token
- [ ] Run on the always-on PC as a scheduled task (owner's PC)

## Phase 4: Dashboard app (check: debug APK installs and shows demo data)
- [x] Compose app: Home, Trades, Calendar, Strategies, Rules
- [x] Demo mode, and live mode against `server.py`
- [x] Debug APK build
- [ ] Owner installs Tailscale on the PC and phone

## Phase 5: Live, small (check: owner unlock, read-only connection check passes)
- [x] Coinbase CFM adapter: balance, positions, bracket order, close, cancel (gated; written against the official SDK, not yet run on a real account)
- [x] `tradedesk check-live`: read-only connection test
- [ ] Owner creates a CDP key (view and trade) and sets env vars
- [ ] A strategy passes the paper gate
- [ ] Owner unlocks live in the app

## Phase 5b: Owner's 24/7 brief (2026-11-09)
- [x] Regime classifier (CALM_TREND / SIDEWAYS / JUMPY / CRASH), tested against base rates
- [x] Regime-filtered trend ensemble; 10 variants, buy-and-hold benchmark, 3x cost test (`reports/best-strategy.md`)
- [x] 15% max-drawdown halt (kill switch on, owner resumes)
- [ ] Gate drawdown: use mark-to-market drawdown, not closed-trade drawdown
- [ ] Forward-gate minimums scaled for slow strategies (30 signals is about 6 months for one coin)
- [ ] Nightly review report (suggestions only, never auto-applied)
- [ ] API-error limit and a full decision log

## Phase 6: Learning and growth
- [x] Journal analysis and filter proposals (`learn.py`), judged only on later unseen trades. First run: 0 of 10 ideas promoted
- [ ] Monthly re-fit scheduled
- [ ] Funding-rate history collector (needed for a funding strategy)
- [ ] News-only strategy experiment
- [ ] Kraken US perps adapter, once Kraken documents API access
