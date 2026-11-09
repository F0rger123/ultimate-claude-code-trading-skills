# Sources

Verification status as of 2026-11-09. "Not read" means the page refused automated access during this build.
Facts that depend on these pages are labeled assumptions in the code and reports.

| Source | Used for | Status |
|---|---|---|
| Moskowitz, Ooi, Pedersen (2012), "Time series momentum", J. Financial Economics, doi:10.1016/j.jfineco.2011.11.003 | trend ensemble rationale | cited; general finding is well known; applicability to 3 coins is **not** implied |
| Moreira, Muir (2017), "Volatility-managed portfolios", J. Finance, doi:10.1111/jofi.12513 | vol targeting | cited; our test did not reproduce an improvement |
| Liu, Tsyvinski, Wu (2022), "Common risk factors in cryptocurrency", J. Finance, doi:10.1111/jofi.13119 | rotation rationale | cited |
| Bailey, López de Prado (2014), "The deflated Sharpe ratio", J. Portfolio Management, doi:10.3905/jpm.2014.40.5.094 | multiple-testing correction | **not read** (paywall); formulas as widely reproduced |
| Coinbase Advanced Trade fees (help.coinbase.com) | spot fees | **not read** (HTTP 403); 0.90% taker / 0.50% maker used as a conservative assumption |
| Coinbase US perpetual futures overview (help.coinbase.com) | perp fees, funding | **not read** (HTTP 403) |
| Coinbase public product endpoint `api.coinbase.com/api/v3/brokerage/market/products?product_type=FUTURE` | contract sizes, margin rates, funding interval | **read** 2026-11-07 (`docs/VERIFIED_APIS.md`) |
| Coinbase Advanced Trade API docs (docs.cdp.coinbase.com) | order types, endpoints | **read** 2026-11-07 |
| CME MNQ contract specs (cmegroup.com) | $2/point, 0.25 tick | **not read** (timeout); values from the owner's brief, to verify |
| TradingView Pine v6 docs (strategies, time, sessions) | Pine script | not re-read in this build; script not yet compiled in TradingView |
