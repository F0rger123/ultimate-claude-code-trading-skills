# Verified API facts

Each fact was checked on the date shown against the source named. "Unconfirmed" means no
official page says it. Re-check before relying on anything older than 90 days.

## Coinbase Financial Markets (CFM), US perp-style futures (checked 2026-11-07)

| Fact | Source |
|---|---|
| Advanced Trade API trades US derivatives offered by CFM, a CFTC-registered FCM | https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/guides/futures |
| 29 perpetual products live, e.g. `BIP-20DEC30-CDE` "Bitcoin Perpetual", 0.01 BTC per contract, `funding_interval` 3600s | public `GET https://api.coinbase.com/api/v3/brokerage/market/products?product_type=FUTURE` (no key) |
| Intraday margin rate BTC/ETH ≈ 0.10 (≈10x); overnight ≈ 0.21–0.30 (≈3–5x); SOL intraday 0.20 (5x); index/gold perps 0.05 (20x) | same endpoint, `future_product_details.intraday_margin_rate` / `overnight_margin_rate` |
| Intraday window: "increased leverage during weekdays (8am-4pm ET), excluding market holidays" | https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/futures/set-intraday-margin-settings.md |
| Order configs include `market_market_ioc`, `limit_limit_gtc`, `stop_limit_stop_limit_gtc`, `trigger_bracket_gtc`; `attached_order_configuration` accepts only TriggerBracketGtc, size omitted | https://docs.cdp.coinbase.com/api-reference/advanced-trade-api/rest-api/orders/create-order.md |
| Order params `leverage` (default 1.0) and `margin_type` CROSS or ISOLATED | same page |
| Balance: `GET /api/v3/brokerage/cfm/balance_summary` (scope view); positions: `GET /api/v3/brokerage/cfm/positions` (view); create order (trade); close position `POST /api/v3/brokerage/orders/close_position` | create-order page, rest-scopes page https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/rest-scopes |
| Auth: CDP API key, JWT bearer token; scopes view / trade / transfer | rest-scopes page |
| Public perp candles: `GET /api/v3/brokerage/market/products/{id}/candles`, 300 bars per call returned | tested live 2026-11-07 |
| Spot history candles: `GET https://api.exchange.coinbase.com/products/{id}/candles`, granularity 60/300/900/3600/21600/86400, max 300 per request, no auth | https://docs.cdp.coinbase.com/exchange/reference/exchangerestapi_getproductcandles |
| Futures sandbox | **none**: the Advanced Trade sandbox covers only Accounts and Orders, with static responses (https://docs.cdp.coinbase.com/coinbase-app/advanced-trade-apis/sandbox) |
| Official Python SDK `coinbase-advanced-py` 1.8.4 on PyPI | `pip index versions coinbase-advanced-py` |
| Reduce-only order flag | unconfirmed |
| Max leverage field `perpetual_details.max_leverage` | returned empty; use the margin rates instead |

## Kraken Derivatives US / Bitnomial (checked 2026-11-07)

| Fact | Source |
|---|---|
| US perps on Kraken Pro, listed on Bitnomial, cleared by NinjaTrader Clearing d/b/a Kraken Derivatives US | https://blog.kraken.com/product/kraken-derivatives/announcing-cftc-regulated-us-perps |
| API trading of US perps | **unconfirmed**: the launch post mentions only the Kraken Pro UI |
| Kraken Futures demo at demo-futures.kraken.com, "API code is identical to production" | https://docs.kraken.com/exchange/guides/futures/introduction (US perp coverage unconfirmed) |
| Bitnomial BTP: "All orders are limit orders", no stops | https://bitnomial.com/exchange/docs/api/btp/order-entry/ |

## Not usable from the US

| Venue | Reason | Source |
|---|---|---|
| BloFin | third-party guides say its Terms bar US residents; the official Terms page refused automated fetch (403) | https://www.coinperps.com/learn/blofin-restricted-countries |
| Hyperliquid | Terms define US persons as Restricted Persons (third-party summaries) | https://www.datawallet.com/crypto/is-hyperliquid-available-in-the-usa |

## Libraries

| Library | License | Note |
|---|---|---|
| ccxt 4.5.92 | MIT | `coinbase` class has fetchOHLCV, createOrder with `stopLossPrice`/`takeProfitPrice`, fetchPositions; no setLeverage. Not used by the engine (we call REST directly), kept as an option. |
