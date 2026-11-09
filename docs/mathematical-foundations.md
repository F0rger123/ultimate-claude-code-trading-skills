# Mathematical foundations

Examples marked *hypothetical* are illustrations, not results.

## Returns and compounding
- Simple return $r_t = P_t/P_{t-1} - 1$. Log return $r^{\log}_t = \ln(P_t/P_{t-1})$.
- Compounding: $E_T = E_0 \prod_t (1 + r_t)$. CAGR $= (E_T/E_0)^{365/days} - 1$.
- *Hypothetical:* +50% then −50% leaves 75% of the start. Losses hurt more than equal gains help.

## Expectancy and the 0.5R problem
- $E[R] = pW - (1-p)L - C$, with W and L in R units and C the cost per trade in R.
- *Hypothetical:* with W = 0.5 and L = 1, $E[R] = 1.5p - 1 - C$.
  - Before costs the break-even win rate is 66.7%.
  - With C = 0.10R it rises to $(1 + 0.10)/1.5 = 73.3\%$.
- Small targets need very high win rates, and costs eat most of the edge.

## Fees in R
- $FeeCost_R = (fee_{entry} + fee_{exit}) / StopDistanceFraction$.
- *Hypothetical:* 0.90% taker each way with a 5% stop costs $0.018/0.05 = 0.36R$ per trade, before slippage.
  This is why the spot versions trail the futures versions in the corrected tournament.

## Position sizing
- $Notional = \min\left(\frac{Equity \cdot RiskFraction}{StopDistanceFraction},\ LeverageCap \cdot Equity\right)$.
- Then capped by:
  - cash (spot)
  - whole contracts (futures): $qty = \lfloor qty / contract \rfloor \cdot contract$
  - venue minimum notional
  - total gross exposure across all open positions
- **Minimum equity for one futures contract:** $E_{min} \ge N(d + c)/r$, where N = contract notional,
  d = stop distance fraction, c = round-trip cost fraction, r = allowed account loss fraction.
  - *Hypothetical:* one $757 BTC contract with a 10% stop, 0.16% costs and 1% risk needs about $7,700.

## Volatility targeting
- 20-day annualized volatility: $\sigma_{20} = \text{stdev}(r^{\log}_{t-19..t})\sqrt{365}$.
- Multiplier: $m_t = \min(1, \sigma_{target}/\sigma_{20})$. Size scales down when markets get wild and is
  never levered up above 1. A missing or zero σ means no trade (fail closed).

## Mark-to-market and drawdown
- **Spot:** $E_t = C_t + \sum_i Q_i P_{i,t}$. **Futures:** $E_t = C_t + \sum_i s_i Q_i M_i (P_{i,t} - P_{i,entry})$,
  where $C_t$ is net of fees and funding.
- $DD_t = (\max_{s \le t} E_s - E_t)/\max_{s \le t} E_s$. The owner's 7.5/10/15% tiers use this marked
  value, not closed-trade equity.

## Funding
- $FundingPnL_t = -q_t \cdot M \cdot P_t \cdot f_t$, with $q_t$ signed contracts, M the multiplier and
  $f_t$ the hourly rate. When $f_t > 0$, longs pay and shorts receive.

## Risk-adjusted measures
- Sharpe $= \bar r / s_r \cdot \sqrt{365}$, with daily returns and a risk-free rate of 0.
- Sortino uses only the downside deviation.
- Calmar = CAGR / max drawdown.
- Expected shortfall (5%) = average of the worst 5% of daily returns.
- Profit factor = gross winning P&L / |gross losing P&L|.

## Deflated Sharpe ratio (Bailey and López de Prado, 2014)
- Expected best Sharpe from N trials by luck:
  $E[\max SR_N] = \sqrt{V}\left[(1-\gamma)\Phi^{-1}(1 - 1/N) + \gamma\Phi^{-1}(1 - 1/(Ne))\right]$, γ ≈ 0.5772.
- DSR $= \Phi\left(\frac{(\widehat{SR} - SR_0)\sqrt{T-1}}{\sqrt{1 - \hat\gamma_3 \widehat{SR} + \frac{\hat\gamma_4 - 1}{4}\widehat{SR}^2}}\right)$,
  with per-period (daily) Sharpe, skewness $\hat\gamma_3$ and kurtosis $\hat\gamma_4$.
- These are the formulas as widely reproduced. The journal version was paywalled during this build, so this
  implementation has not been checked line by line against the paper.

## Kelly
- For a binary bet, Kelly $f^* = p - (1-p)/b$. It maximizes long-run growth only if p and b are known
  exactly, and estimation error makes full Kelly very aggressive. The platform never uses full Kelly:
  live risk starts at 0.5% per trade.
