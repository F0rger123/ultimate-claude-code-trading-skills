"""Research candidates from the 2026-11-09 master brief. Each uses only completed daily bars.

Status labels (see docs/research-methodology.md):
  vol_managed_trend        implemented, tested in the portfolio engine
  vol_filtered_breakout    implemented, tested in the portfolio engine
  weekly_strength_rotation implemented (multi-asset coordinator), spot only
  funding_carry_research   NOT implemented: no historical CFM funding series is available (see docs/funding.md)
  eth_btc_relative_value   NOT implemented: needs a two-leg (paired) execution architecture
"""
import math

from . import indicators as I
from .strategies import D1, Strategy


def _daily_vol(c):
    """20-day stdev of daily log returns (not annualized), None before defined."""
    lr = [None] + [math.log(c[k] / c[k - 1]) for k in range(1, len(c))]
    out = [None] * len(c)
    for k in range(20, len(c)):
        w = lr[k - 19:k + 1]
        mu = sum(w) / 20
        out[k] = math.sqrt(sum((x - mu) ** 2 for x in w) / 19)
    return out


def _vol_rank(v, look=180):
    """Rank of v[k] among the preceding `look` values (strictly earlier), 0..1."""
    out = [None] * len(v)
    for k in range(len(v)):
        if v[k] is None:
            continue
        past = [x for x in v[max(0, k - look):k] if x is not None]
        if len(past) >= look // 2:
            out[k] = sum(1 for x in past if x <= v[k]) / len(past)
    return out


class _Daily(Strategy):
    """Helpers: daily frame, index of the daily bar that closed with base bar i."""
    family = "trend"

    def daily(self):
        self.f = self.m.frame(D1)
        self.a = self.atr_tf(D1, 20)

    def _j(self, i):
        if not self.m.closes_tf(D1, i):
            return None
        j = self.m.maps[D1][i]
        return j if j >= 1 else None

    def features(self, i):  # cheap: the portfolio engine does not use the journal context
        return {}


class VolManagedTrend(_Daily):
    """Multi-look-back trend votes with volatility targeting and a crisis gate.

    Votes: for L in 20/40/60/90/120 days, +1 if close > close L days ago else -1; average.
    Long >= thr, short <= -thr (shorts only where the venue allows). Stop k x ATR(20).
    Size multiplier m = min(1, target_vol / sigma20_annualized), halved when sigma20 is above the 80th
    percentile of the preceding 180 days (optional, registered as a separate trial).
    Crisis gate: 7-day return <= -18% or close >= 30% below the 30-day high: no new longs, exit longs.
    """
    id = "vol_managed_trend"
    name = "Volatility-managed trend ensemble (daily)"
    source = ("Moskowitz, Ooi, Pedersen 2012 (time-series momentum); Moreira and Muir 2017 "
              "(volatility-managed portfolios)")
    defaults = {"lookbacks": (20, 40, 60, 90, 120), "thr": 0.6, "stop_atr": 3.0, "vol_target": 0.35,
                "halve_high_vol": 0, "crisis": 1}
    grid = {"thr": [0.6, 0.8], "stop_atr": [2.5, 3.0, 3.5], "vol_target": [0.25, 0.35]}

    def prepare(self):
        self.daily()
        f, p = self.f, self.p
        key = ("vmt", tuple(p["lookbacks"]), p["thr"])
        self.dirs = f.memo(key, self._dirs)
        self.vol = f.memo(("dvol20",), lambda: _daily_vol(f.c))
        self.vrank = f.memo(("dvolrank180",), lambda: _vol_rank(self.vol, 180))

    def _dirs(self):
        c, lbs, thr = self.f.c, self.p["lookbacks"], self.p["thr"]
        out = [None] * len(c)
        for k in range(max(lbs), len(c)):
            v = sum(1 if c[k] > c[k - L] else -1 for L in lbs) / len(lbs)
            out[k] = 1 if v >= thr else -1 if v <= -thr else 0
        return out

    def crisis(self, j):
        f = self.f
        if j < 30:
            return False
        r7 = f.c[j] / f.c[j - 7] - 1
        hi30 = max(f.h[j - 29:j + 1])
        return r7 <= -0.18 or f.c[j] <= 0.70 * hi30

    def size(self, j):
        v = self.vol[j]
        if v is None or v <= 0:
            return 0.0  # fail closed on missing volatility
        m = min(1.0, self.p["vol_target"] / (v * math.sqrt(365)))
        if self.p["halve_high_vol"] and self.vrank[j] is not None and self.vrank[j] > 0.80:
            m *= 0.5
        return m

    def entry(self, i):
        j = self._j(i)
        if j is None or self.dirs[j] in (None, 0) or self.a[j] is None:
            return None
        d = self.dirs[j]
        if d == self.dirs[j - 1]:
            return None
        if d == 1 and self.p["crisis"] and self.crisis(j):
            return None
        m = self.size(j)
        if m <= 0:
            return None
        c = self.f.c[j]
        return {"side": d, "stop": c - d * self.p["stop_atr"] * self.a[j], "target": None, "size_mult": m}

    def exit(self, i, pos):
        j = self._j(i)
        if j is None or self.dirs[j] is None:
            return False
        if pos["side"] == 1 and self.p["crisis"] and self.crisis(j):
            return True
        return self.dirs[j] != pos["side"]


class VolFilteredBreakout(_Daily):
    """Daily Donchian breakout: close above the prior N-day high (long) or below the prior N-day low
    (short, futures only). Exit on the opposite channel (10 days for N=20, 20 days for N=55) or the stop
    (k x ATR20). Entries are skipped when 20-day realized volatility ranks above `vol_cap` among the
    preceding 180 days (vol_cap = 1.0 disables the filter: the unfiltered baseline)."""
    id = "vol_filtered_breakout"
    name = "Volatility-filtered Donchian breakout (daily)"
    source = "Donchian channel / Turtle breakout rules; volatility filter is a research hypothesis"
    defaults = {"n": 20, "stop_atr": 3.0, "vol_cap": 0.8}
    grid = {"n": [20, 55], "stop_atr": [2.5, 3.0], "vol_cap": [0.8, 0.9]}

    def prepare(self):
        self.daily()
        f, n = self.f, self.p["n"]
        xn = 10 if n <= 20 else 20
        self.hi, self.lo = f.memo(("don", n), lambda: I.donchian(f.h, f.l, n))
        self.xhi, self.xlo = f.memo(("don", xn), lambda: I.donchian(f.h, f.l, xn))
        self.vol = f.memo(("dvol20",), lambda: _daily_vol(f.c))
        self.vrank = f.memo(("dvolrank180",), lambda: _vol_rank(self.vol, 180))

    def entry(self, i):
        j = self._j(i)
        if j is None or self.hi[j] is None or self.a[j] is None:
            return None
        if self.p["vol_cap"] < 1.0 and (self.vrank[j] is None or self.vrank[j] > self.p["vol_cap"]):
            return None
        c = self.f.c[j]
        prev_c = self.f.c[j - 1]
        side = 0
        if c > self.hi[j] and not (self.hi[j - 1] is not None and prev_c > self.hi[j - 1]):
            side = 1
        elif c < self.lo[j] and not (self.lo[j - 1] is not None and prev_c < self.lo[j - 1]):
            side = -1
        if not side:
            return None
        return {"side": side, "stop": c - side * self.p["stop_atr"] * self.a[j], "target": None}

    def exit(self, i, pos):
        j = self._j(i)
        if j is None or self.xlo[j] is None:
            return False
        c = self.f.c[j]
        return c < self.xlo[j] if pos["side"] == 1 else c > self.xhi[j]


class RotationCoordinator:
    """Weekly selection shared by the per-coin rotation strategies.

    At the daily close that ends on Monday 00:00 UTC, rank coins by `lookback`-day return. A coin is
    eligible if that return is positive and its close is above its 200-day EMA, and only while BTC is
    above its own 200-day EMA. Hold the single strongest eligible coin, else cash."""

    def __init__(self, markets, lookback=90, regime_sym="BTC"):
        self.lb = lookback
        self.regime_sym = regime_sym
        self.frames = {s: m.frame(D1) for s, m in markets.items()}
        self.ema = {s: f.memo(("ema", 200), lambda f=f: I.ema(f.c, 200)) for s, f in self.frames.items()}
        self.idx = {s: {t: j for j, t in enumerate(f.t)} for s, f in self.frames.items()}
        self.cache = {}

    def choice(self, day_t):
        """day_t = open time of the daily bar that just closed. Returns a symbol or None."""
        if day_t in self.cache:
            return self.cache[day_t]
        best, best_r = None, 0.0
        ok_regime = True
        jr = self.idx.get(self.regime_sym, {}).get(day_t)
        if jr is None or self.ema[self.regime_sym][jr] is None:
            ok_regime = False
        else:
            ok_regime = self.frames[self.regime_sym].c[jr] > self.ema[self.regime_sym][jr]
        if ok_regime:
            for s, f in self.frames.items():
                j = self.idx[s].get(day_t)
                if j is None or j < self.lb or self.ema[s][j] is None:
                    continue
                r = f.c[j] / f.c[j - self.lb] - 1
                if r > 0 and f.c[j] > self.ema[s][j] and r > best_r:
                    best, best_r = s, r
        self.cache[day_t] = best
        return best


class WeeklyStrengthRotation(_Daily):
    id = "weekly_strength_rotation"
    name = "Weekly strength rotation (spot)"
    family = "momentum"
    source = "Cross-sectional crypto momentum (Liu, Tsyvinski, Wu 2022, J. Finance)"
    defaults = {"lookback": 90, "stop_atr": 3.0}
    grid = {"lookback": [60, 90, 120]}

    def __init__(self, mkt, coordinator=None, **params):
        self.coord = coordinator
        Strategy.__init__(self, mkt, **params)

    def prepare(self):
        self.daily()

    def _monday(self, i):
        end = self.m.b.t[i] + self.m.base
        return (end // 86400 + 3) % 7 == 0  # 1970-01-01 was a Thursday

    def entry(self, i):
        j = self._j(i)
        if j is None or not self._monday(i) or self.a[j] is None:
            return None
        if self.coord.choice(self.f.t[j]) != self.m.symbol:
            return None
        c = self.f.c[j]
        return {"side": 1, "stop": c - self.p["stop_atr"] * self.a[j], "target": None}

    def exit(self, i, pos):
        j = self._j(i)
        if j is None or not self._monday(i):
            return False
        return self.coord.choice(self.f.t[j]) != self.m.symbol


ALL = [VolManagedTrend, VolFilteredBreakout, WeeklyStrengthRotation]
