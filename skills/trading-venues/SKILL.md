---
name: trading-venues
description: Which exchanges a US trader can automate perpetual futures on, with verified API features and leverage limits. Use when the user asks "which exchange", "can I use BloFin / Hyperliquid", "how much leverage can I get", "does it have an API", or "add another exchange".
---

# Venues

Facts, with their sources and dates, are in `docs/VERIFIED_APIS.md`. Re-check anything older than 90 days against the official docs or the public product list: `GET https://api.coinbase.com/api/v3/brokerage/market/products?product_type=FUTURE`.

- **Coinbase Financial Markets (used):**
  - 29 US perp-style products, with funding charged hourly.
  - The API supports bracket orders, positions and close-position.
  - Leverage: about 10x on BTC and ETH during the intraday window (weekdays 8am-4pm ET), and about 3-5x overnight. Alts get 4-5x intraday.
  - No futures sandbox, so paper trading runs on the desk's own simulator.
- **Kraken Derivatives US (Bitnomial):** the product exists. API trading for US clients is unconfirmed.
- **Offshore venues (BloFin, Hyperliquid and similar):** their terms bar US persons. Do not build automation for them, and do not suggest VPNs or other workarounds. Explain that an account frozen with open leveraged positions can mean losing everything in it.

When the user asks for more leverage, explain that leverage doesn't change the risk per trade when size comes from the stop. It only changes how much margin a trade uses.
