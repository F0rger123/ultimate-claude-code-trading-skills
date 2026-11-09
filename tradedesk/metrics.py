"""Performance statistics on a marked equity curve and a trade ledger.

Daily statistics use the last marked equity of each UTC day. Crypto trades every day, so annualizing
uses 365 days. Formulas:
  return r_t = E_t / E_{t-1} - 1
  Sharpe = mean(r) / stdev(r) * sqrt(365)        (risk-free rate taken as 0)
  Sortino = mean(r) / downside_dev(r) * sqrt(365)
  DD_t = (max_{s<=t} E_s - E_t) / max_{s<=t} E_s
  CAGR = (E_end / E_start)^(365/days) - 1;  Calmar = CAGR / maxDD
  Expected shortfall (5%) = mean of the worst 5% daily returns
  Profit factor = sum(winning net P&L) / |sum(losing net P&L)|
Deflated Sharpe ratio (Bailey and Lopez de Prado, 2014), as published; the paper itself was behind a
paywall during this build, so the implementation follows the widely reproduced formulas:
  E[max SR_N] = sqrt(V) * ((1 - g) * Z^-1(1 - 1/N) + g * Z^-1(1 - 1/(N e))),  g = 0.5772156649
  DSR = Z( (SR - SR0) * sqrt(T - 1) / sqrt(1 - skew * SR + (kurt - 1) / 4 * SR^2) )
with SR and V the per-period (daily) Sharpe and the variance of Sharpe ratios across trials.
"""
import math
import random
from statistics import NormalDist

N01 = NormalDist()
EULER = 0.5772156649015329


def daily(curve):
    by = {}
    for t, e in curve:
        by[t // 86400] = e
    days = sorted(by)
    return days, [by[d] for d in days]


def rets(eq):
    return [eq[k] / eq[k - 1] - 1 for k in range(1, len(eq)) if eq[k - 1] > 0]


def max_dd(eq):
    peak, m = eq[0] if eq else 0, 0.0
    for e in eq:
        peak = max(peak, e)
        if peak > 0:
            m = max(m, (peak - e) / peak)
    return m


def underwater_days(days, eq):
    peak, start, longest = -1e18, None, 0
    for d, e in zip(days, eq):
        if e >= peak:
            peak = e
            if start is not None:
                longest = max(longest, d - start)
            start = None
        elif start is None:
            start = d
    if start is not None and days:
        longest = max(longest, days[-1] - start)
    return longest


def moments(r):
    n = len(r)
    if n < 3:
        return 0.0, 0.0, 3.0
    mu = sum(r) / n
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (n - 1))
    if sd == 0:
        return mu, 0.0, 3.0
    skew = sum(((x - mu) / sd) ** 3 for x in r) / n
    kurt = sum(((x - mu) / sd) ** 4 for x in r) / n
    return mu, sd, skew, kurt


def curve_stats(curve):
    days, eq = daily(curve)
    if len(eq) < 3:
        return {"days": len(eq)}
    r = rets(eq)
    mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1)) if len(r) > 1 else 0.0
    dn = math.sqrt(sum(min(0, x) ** 2 for x in r) / len(r)) if r else 0.0
    yrs = max(1e-9, (days[-1] - days[0]) / 365.0)
    cagr = (eq[-1] / eq[0]) ** (1 / yrs) - 1 if eq[0] > 0 and eq[-1] > 0 else -1.0
    worst = sorted(r)[:max(1, len(r) // 20)]
    mdd_d = max_dd(eq)
    return {
        "start_equity": eq[0], "end_equity": eq[-1], "days": days[-1] - days[0],
        "total_return": eq[-1] / eq[0] - 1, "cagr": cagr,
        "sharpe": mu / sd * math.sqrt(365) if sd > 0 else 0.0,
        "sortino": mu / dn * math.sqrt(365) if dn > 0 else 0.0,
        "max_dd_daily": mdd_d, "max_dd_intraday": max_dd([e for _, e in curve]),
        "calmar": cagr / mdd_d if mdd_d > 0 else None,
        "es5_daily": sum(worst) / len(worst), "underwater_days": underwater_days(days, eq),
        "daily_sharpe": mu / sd if sd > 0 else 0.0, "n_days": len(r),
    }


def trade_stats(trades, curve=None):
    n = len(trades)
    if n == 0:
        return {"trades": 0}
    pnl = [t["pnl"] for t in trades]
    rs = sorted(t["R"] for t in trades)
    wins = [x for x in pnl if x > 0]
    losses = [x for x in pnl if x <= 0]
    streak = best = 0
    for x in pnl:
        streak = streak + 1 if x <= 0 else 0
        best = max(best, streak)
    gross_profit = sum(t["gross"] for t in trades if t["gross"] > 0)
    costs = sum(t["fees"] + t["funding"] for t in trades)
    out = {
        "trades": n, "win_rate": len(wins) / n,
        "profit_factor": sum(wins) / -sum(losses) if losses and sum(losses) < 0 else float("inf"),
        "avg_R": sum(rs) / n, "median_R": rs[n // 2],
        "payoff": (sum(wins) / len(wins)) / (-sum(losses) / len(losses)) if wins and losses and sum(losses) < 0 else None,
        "fees": sum(t["fees"] for t in trades), "funding": sum(t["funding"] for t in trades),
        "cost_share_of_gross_profit": costs / gross_profit if gross_profit > 0 else None,
        "avg_hold_days": sum(t["hours"] for t in trades) / n / 24, "longest_losing_streak": best,
        "long_share": sum(1 for t in trades if t["side"] == 1) / n,
    }
    if curve:
        span = curve[-1][0] - curve[0][0]
        if span > 0:
            # union of time with at least one open position
            iv = sorted((max(t["t0"], curve[0][0]), min(t["t1"], curve[-1][0])) for t in trades)
            covered, cur_a, cur_b = 0, None, None
            for a, b in iv:
                if cur_b is None or a > cur_b:
                    if cur_b is not None:
                        covered += cur_b - cur_a
                    cur_a, cur_b = a, b
                else:
                    cur_b = max(cur_b, b)
            if cur_b is not None:
                covered += cur_b - cur_a
            out["exposure"] = covered / span
            out["trades_per_year"] = n / (span / 86400 / 365)
    return out


def block_bootstrap(curve, runs=2000, block=10, seed=11):
    """Resample whole blocks of consecutive daily returns (keeps volatility clustering and streaks)."""
    days, eq = daily(curve)
    r = rets(eq)
    if len(r) < block * 3:
        return {"runs": 0}
    rnd = random.Random(seed)
    n = len(r)
    cagrs, dds = [], []
    yrs = n / 365.0
    for _ in range(runs):
        path, e, peak, mdd = [], 1.0, 1.0, 0.0
        while len(path) < n:
            a = rnd.randrange(0, n - block + 1)
            path.extend(r[a:a + block])
        for x in path[:n]:
            e *= 1 + x
            peak = max(peak, e)
            mdd = max(mdd, (peak - e) / peak)
        cagrs.append(e ** (1 / yrs) - 1 if e > 0 else -1.0)
        dds.append(mdd)
    cagrs.sort()
    dds.sort()
    return {"runs": runs, "block_days": block, "cagr_p5": cagrs[int(0.05 * runs)],
            "cagr_p50": cagrs[runs // 2], "cagr_p95": cagrs[int(0.95 * runs)],
            "maxdd_p50": dds[runs // 2], "maxdd_p95": dds[int(0.95 * runs)],
            "prob_loss": sum(1 for c in cagrs if c < 0) / runs}


def expected_max_sharpe(n_trials, var_sr):
    if n_trials < 2:
        return 0.0
    return math.sqrt(var_sr) * ((1 - EULER) * N01.inv_cdf(1 - 1.0 / n_trials)
                                + EULER * N01.inv_cdf(1 - 1.0 / (n_trials * math.e)))


def deflated_sharpe(curve, n_trials, trial_daily_sharpes=None):
    """Probability that the true daily Sharpe exceeds what the best of n_trials would show by luck."""
    days, eq = daily(curve)
    r = rets(eq)
    m = moments(r)
    if len(m) < 4 or m[1] == 0:
        return {"dsr": None}
    mu, sd, skew, kurt = m
    sr = mu / sd
    T = len(r)
    if trial_daily_sharpes and len(trial_daily_sharpes) > 1:
        mean = sum(trial_daily_sharpes) / len(trial_daily_sharpes)
        var_sr = sum((x - mean) ** 2 for x in trial_daily_sharpes) / (len(trial_daily_sharpes) - 1)
    else:
        var_sr = 1.0 / T  # Sharpe estimation variance under the null when trial spread is unknown
    sr0 = expected_max_sharpe(n_trials, var_sr)
    denom = 1 - skew * sr + (kurt - 1) / 4.0 * sr * sr
    z = (sr - sr0) * math.sqrt(T - 1) / math.sqrt(denom) if denom > 0 else float("nan")
    return {"dsr": N01.cdf(z) if z == z else None, "daily_sharpe": sr, "sr0_daily": sr0,
            "n_trials": n_trials, "T": T, "skew": skew, "kurtosis": kurt}


def buy_hold_curve(markets, syms, start_t, end_t, equity=10000.0, fee=0.009):
    """Equal-weight buy-and-hold on daily closes, bought once with one taker fee, never rebalanced."""
    closes = {}
    for s in syms:
        f = markets[s].frame(86400)
        closes[s] = {t: c for t, c in zip(f.t, f.c) if start_t <= t < end_t}
    common = sorted(set.intersection(*[set(closes[s]) for s in syms]))
    if not common:
        return []
    alloc = equity * (1 - fee) / len(syms)
    qty = {s: alloc / closes[s][common[0]] for s in syms}
    return [(t + 86399, sum(qty[s] * closes[s][t] for s in syms)) for t in common]


def risk_matched(bh_curve, target_vol_daily):
    """Buy-and-hold scaled down (rest in cash, rebalanced daily) to a target daily volatility."""
    days, eq = daily(bh_curve)
    r = rets(eq)
    if len(r) < 3:
        return bh_curve
    mu = sum(r) / len(r)
    sd = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
    w = min(1.0, target_vol_daily / sd) if sd > 0 else 0.0
    out, e = [(days[0] * 86400, eq[0])], eq[0]
    for d, x in zip(days[1:], r):
        e *= 1 + w * x
        out.append((d * 86400, e))
    return out
