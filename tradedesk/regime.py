"""Market regime on daily bars: CALM_TREND, SIDEWAYS, JUMPY, CRASH.

Simple, explainable measures, each using only data up to and including that day's close:
- trend strength: 30-day return divided by the volatility expected over 30 days (a t-stat-like score)
- realised volatility: stdev of daily returns over 20 days, ranked against the past 365 days
- crash speed: 7-day return, and drawdown from the 30-day high

Rules, checked in this order:
  CRASH       7-day return <= -15%, or drawdown from the 30-day high <= -25% while the 7-day return < 0
  JUMPY       20-day volatility in the top 20% of the past year
  CALM_TREND  |trend strength| >= 1.0
  SIDEWAYS    everything else
"""
import math

CALM_TREND, SIDEWAYS, JUMPY, CRASH = "CALM_TREND", "SIDEWAYS", "JUMPY", "CRASH"
REGIMES = (CALM_TREND, SIDEWAYS, JUMPY, CRASH)
# Position-size multiplier per regime. CRASH = no new entries.
SIZE = {CALM_TREND: 1.0, SIDEWAYS: 0.5, JUMPY: 0.5, CRASH: 0.0}


def _stdev(xs):
    n = len(xs)
    if n < 2:
        return None
    m = sum(xs) / n
    return math.sqrt(sum((x - m) ** 2 for x in xs) / (n - 1))


def classify(closes, highs=None):
    """closes: daily closes, oldest first. Returns a list of (label, info) per day; None before warm-up."""
    highs = highs or closes
    n = len(closes)
    rets = [None] + [closes[k] / closes[k - 1] - 1 for k in range(1, n)]
    vol20 = [None] * n
    for k in range(21, n):
        vol20[k] = _stdev(rets[k - 19:k + 1])
    out = [None] * n
    for k in range(n):
        if k < 30 or vol20[k] is None:
            continue
        past = [v for v in vol20[max(21, k - 365):k] if v is not None]
        if len(past) < 120:
            continue
        vol_rank = sum(1 for v in past if v <= vol20[k]) / len(past)
        r30 = closes[k] / closes[k - 30] - 1
        strength = r30 / (vol20[k] * math.sqrt(30)) if vol20[k] > 0 else 0.0
        r7 = closes[k] / closes[k - 7] - 1
        dd30 = closes[k] / max(highs[k - 29:k + 1]) - 1
        if r7 <= -0.15 or (dd30 <= -0.25 and r7 < 0):
            label = CRASH
        elif vol_rank >= 0.80:
            label = JUMPY
        elif abs(strength) >= 1.0:
            label = CALM_TREND
        else:
            label = SIDEWAYS
        out[k] = (label, {"strength": strength, "vol_rank": vol_rank, "r7": r7, "dd30": dd30,
                          "vol20": vol20[k], "trend_dir": 1 if r30 > 0 else -1})
    return out


def evaluate(closes, labels, horizon=10):
    """How often each label described the NEXT `horizon` days correctly, next to the base rate
    (how often that outcome happens on any day). A label is only useful if it beats its base rate.

    CALM_TREND right: the next 10-day return has the trend's sign.
    SIDEWAYS right:   the next 10-day move is smaller than 1 x the 10-day expected move.
    JUMPY right:      next-10-day realised volatility stays above the past year's median.
    CRASH right:      the next 10 days do not recover above the crash-day close by more than 5%
                      (staying out cost little), or volatility stays high.
    """
    n = len(closes)
    rets = [None] + [closes[k] / closes[k - 1] - 1 for k in range(1, n)]
    stats = {r: {"days": 0, "right": 0, "base_right": 0, "base_days": 0} for r in REGIMES}
    for k in range(n - horizon):
        lab = labels[k]
        if lab is None:
            continue
        label, info = lab
        fwd = closes[k + horizon] / closes[k] - 1
        fvol = _stdev(rets[k + 1:k + horizon + 1]) or 0.0
        exp_move = info["vol20"] * math.sqrt(horizon)
        past = [x for x in (_stdev(rets[j - 19:j + 1]) for j in range(max(21, k - 365), k, 5)) if x]
        med = sorted(past)[len(past) // 2] if past else info["vol20"]
        outcomes = {
            CALM_TREND: (fwd > 0) == (info["trend_dir"] > 0),
            SIDEWAYS: abs(fwd) < exp_move,
            JUMPY: fvol > med,
            CRASH: fwd < 0.05 or fvol > med,
        }
        for r in REGIMES:  # base rate: how often each outcome happens regardless of label
            stats[r]["base_days"] += 1
            stats[r]["base_right"] += 1 if outcomes[r] else 0
        stats[label]["days"] += 1
        stats[label]["right"] += 1 if outcomes[label] else 0
    out = {}
    for r, s in stats.items():
        out[r] = {"days": s["days"], "hit_rate": s["right"] / s["days"] if s["days"] else None,
                  "base_rate": s["base_right"] / s["base_days"] if s["base_days"] else None}
    return out
