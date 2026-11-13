"""Strategy bank: strategies added from outside research, coded against the same Strategy interface as
tradedesk/strategies.py. They join the weekly shake-up's candidate pool and must win a recent test with
costs before any of them gets a paper account. Nothing here can trade real money.

How an idea gets here (see research/strategy_bank/README.md): a written spec with exact rules, at most 3
parameters, the mechanism and a source; Claude codes it below with `cadence = "fast"` (5-minute base bars)
or `"slow"` (hourly base bars), adds it to ALL, and the tests in tests/test_library.py check it runs and
never looks ahead.

Source of the first batch: research bundle of 2026-11-13 (ChatGPT deep research). That research DESIGNED
these rules and linked family-level evidence; it did not backtest them, so every strategy here is untested
until the desk tests it. Simplifications versus the written rules:
- Trailing stops are checked at each signal-bar close and exit at the next bar's open (the engine's resting
  stop stays at the initial distance), slightly looser than an intrabar trail.
- "America/New_York" windows use the winter (EST) offset: Monday 00:00 ET = 05:00 UTC, Friday 16:00 ET =
  21:00 UTC. In summer they are one hour off.
- Fills are at the next base bar's open on spot prices: a spot-proxy test, not a futures replication.
Parked from the bundle (not coded): two-coin pair trades (ETH/BTC, SOL/ETH, 3-coin spread; the engine trades
one coin at a time), the 3-coin breadth rule, duplicates of strategies already running (4h Donchian 55,
weekly strength leader, 4-timeframe SuperTrend) and the six that need funding, open interest, liquidation,
on-chain or FOMC data.
"""
import math
import time

from . import indicators as I
from .strategies import H1, M15, M5, Strategy

H4, D1 = 14400, 86400
SRC = "Research bank 2026-11-13 (ChatGPT deep research): rule designed there, not yet backtested"


def _hh(xs, j, n):
    return max(xs[j - n:j]) if j >= n else None


def _ll(xs, j, n):
    return min(xs[j - n:j]) if j >= n else None


def weekday(t):
    """0 = Monday ... 6 = Sunday (UTC)."""
    return (t // D1 + 3) % 7


def us_week_ok(t):
    """Monday 00:00 to Friday 16:00 New York time (winter offset: 05:00 Monday to 21:00 Friday UTC)."""
    wd, h = weekday(t), (t % D1) / 3600.0
    return (wd == 0 and h >= 5) or wd in (1, 2, 3) or (wd == 4 and h < 21)


def _edge(cond, j):
    """Fire only when a condition turns true (one entry per signal)."""
    return cond(j) and not cond(j - 1)


class _Lib(Strategy):
    """Signals on closed bars of `tf`; stop = stop_atr x ATR14 of `stop_tf` (default tf); optional R target
    (`tgt_r`); max hold in seconds. Subclasses define sig(i, j) -> +1/-1/0 and ex(i, j, side, j0) -> bool,
    where i is the base bar, j the closed tf bar and j0 the tf bar at entry."""
    family = "trend"
    source = SRC
    cadence = "slow"
    tf = H1
    stop_tf = None
    hold = None
    defaults = {"stop_atr": 3.0}

    def prepare(self):
        self.f = self.m.frame(self.tf)
        self.a = self.atr_tf(self.stop_tf or self.tf)
        self.setup()
        h = self.hold_s()
        self.max_bars = int(h // self.m.base) if h else None

    def hold_s(self):
        return self.hold

    def setup(self):
        pass

    def sig(self, i, j):
        return 0

    def ex(self, i, j, side, j0):
        return False

    def stop_dist(self, i, j, side, d):
        return d

    # helpers ---------------------------------------------------------------
    def ema(self, n, tf=None):
        f = self.m.frame(tf) if tf else self.f
        return f.memo(("ema", n), lambda: I.ema(f.c, n))

    def sma(self, n, tf=None):
        f = self.m.frame(tf) if tf else self.f
        return f.memo(("sma", n), lambda: I.sma(f.c, n))

    def vsma(self, n=20, tf=None):
        f = self.m.frame(tf) if tf else self.f
        return f.memo(("sma_v", n), lambda: I.sma(f.v, n))

    def rsi(self, n, tf=None):
        f = self.m.frame(tf) if tf else self.f
        return f.memo(("rsi", n), lambda: I.rsi(f.c, n))

    def up(self, tf, i, fast=50, slow=200):
        """Trend of the last CLOSED bar of tf at base bar i: True up, False down, None unknown."""
        a, b = self.ema(fast, tf), self.ema(slow, tf)
        x, y = self.m.at(tf, a, i), self.m.at(tf, b, i)
        return None if x is None or y is None else x > y

    def cross(self, xs, ys, j):
        """+1 if xs crossed above ys on bar j, -1 if below, 0 otherwise."""
        if j < 1 or None in (xs[j], ys[j], xs[j - 1], ys[j - 1]):
            return 0
        if xs[j - 1] <= ys[j - 1] and xs[j] > ys[j]:
            return 1
        if xs[j - 1] >= ys[j - 1] and xs[j] < ys[j]:
            return -1
        return 0

    def _j(self, i):
        if not self.m.closes_tf(self.tf, i):
            return None
        j = self.m.maps[self.tf][i]
        return j if j >= 1 else None

    def entry(self, i):
        j = self._j(i)
        if j is None:
            return None
        s = self.sig(i, j)
        if not s:
            return None
        a = self.m.at(self.stop_tf, self.a, i) if self.stop_tf and self.stop_tf != self.tf else self.a[j]
        if not a:
            return None
        c = self.f.c[j]
        d = self.stop_dist(i, j, s, self.p["stop_atr"] * a)
        if not d or d <= 0:
            return None
        t = self.p.get("tgt_r")
        return {"side": s, "stop": c - s * d, "target": c + s * t * d if t else None}

    def exit(self, i, pos):
        j = self._j(i)
        if j is None:
            return False
        j0 = self.m.maps[self.tf][max(0, pos["i0"])]
        return bool(self.ex(i, j, pos["side"], j0))


# ============================================================ slow: daily
class DailyTSMOMATR(_Lib):
    id = "lib_tsmom_atr"
    name = "Daily momentum with ATR stop"
    tf, hold = D1, 30 * D1
    defaults = {"momentum_days": 60, "stop_atr": 3.0}
    grid = {"momentum_days": [40, 90], "stop_atr": [2.5, 3.5]}

    def setup(self):
        self.s200 = self.sma(200)

    def mom(self, j):
        n, c = self.p["momentum_days"], self.f.c
        return None if j < n else c[j] / c[j - n] - 1

    def sig(self, i, j):
        c, s = self.f.c, self.s200

        def lng(k):
            return k >= 1 and s[k] is not None and (self.mom(k) or 0) > 0 and c[k] > s[k]

        def sht(k):
            return k >= 1 and s[k] is not None and (self.mom(k) or 0) < 0 and c[k] < s[k]
        return 1 if _edge(lng, j) else -1 if _edge(sht, j) else 0

    def ex(self, i, j, side, j0):
        m = self.mom(j)
        return m is not None and m * side < 0


class DailyReturnVote(_Lib):
    id = "lib_return_vote"
    name = "Daily 20/60/120 return vote"
    family = "momentum"
    tf, hold = D1, 45 * D1
    defaults = {"votes_required": 2, "stop_atr": 3.0}
    grid = {"votes_required": [2, 3], "stop_atr": [2.5, 3.5]}

    def setup(self):
        self.s200 = self.sma(200)

    def votes(self, j):
        c = self.f.c
        if j < 120:
            return None
        rs = [c[j] / c[j - n] - 1 for n in (20, 60, 120)]
        return sum(r > 0 for r in rs), sum(r < 0 for r in rs)

    def sig(self, i, j):
        c, s, need = self.f.c, self.s200, self.p["votes_required"]

        def lng(k):
            v = self.votes(k)
            return v is not None and s[k] is not None and v[0] >= need and c[k] > s[k]

        def sht(k):
            v = self.votes(k)
            return v is not None and s[k] is not None and v[1] >= need and c[k] < s[k]
        return 1 if _edge(lng, j) else -1 if _edge(sht, j) else 0

    def ex(self, i, j, side, j0):
        v = self.votes(j)
        return v is not None and (v[0] if side == 1 else v[1]) < self.p["votes_required"]


class DailyEMACrossHold(_Lib):
    id = "lib_daily_ema_cross"
    name = "Daily 20/100 EMA cross"
    tf, hold = D1, 60 * D1
    defaults = {"ema_fast": 20, "ema_slow": 100, "stop_atr": 3.5}
    grid = {"ema_fast": [15, 30], "ema_slow": [80, 120]}

    def setup(self):
        self.ef, self.es, self.s200 = self.ema(self.p["ema_fast"]), self.ema(self.p["ema_slow"]), self.sma(200)

    def sig(self, i, j):
        x = self.cross(self.ef, self.es, j)
        if not x or self.s200[j] is None:
            return 0
        return x if (self.f.c[j] - self.s200[j]) * x > 0 else 0

    def ex(self, i, j, side, j0):
        return self.cross(self.ef, self.es, j) == -side


class DailyROCGate(_Lib):
    id = "lib_daily_roc"
    name = "Daily ROC with trend gate"
    family = "momentum"
    tf, hold = D1, 25 * D1
    defaults = {"roc_days": 20, "roc_threshold": 0.04, "stop_atr": 3.0}
    grid = {"roc_days": [30, 40], "roc_threshold": [0.03, 0.06]}

    def setup(self):
        self.e100 = self.ema(100)

    def roc(self, j):
        n, c = self.p["roc_days"], self.f.c
        return None if j < n else c[j] / c[j - n] - 1

    def sig(self, i, j):
        r, r0, e, c, th = self.roc(j), self.roc(j - 1), self.e100[j], self.f.c[j], self.p["roc_threshold"]
        if None in (r, r0, e):
            return 0
        if r > th and r0 <= th and c > e:
            return 1
        if r < -th and r0 >= -th and c < e:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        r = self.roc(j)
        return r is not None and r * side < 0


class DailyClosingRangeBreakout(_Lib):
    id = "lib_closing_range_breakout"
    name = "Daily closing-range breakout"
    family = "breakout"
    tf, hold = D1, 20 * D1
    defaults = {"lookback_days": 20, "close_position": 0.8, "stop_atr": 3.0, "tgt_r": 5.0}
    grid = {"lookback_days": [15, 30], "close_position": [0.7, 0.9]}

    def setup(self):
        self.e10 = self.ema(10)

    def sig(self, i, j):
        f, n, cp = self.f, self.p["lookback_days"], self.p["close_position"]
        rng = f.h[j] - f.l[j]
        hh, ll = _hh(f.h, j, n), _ll(f.l, j, n)
        if rng <= 0 or hh is None:
            return 0
        pos = (f.c[j] - f.l[j]) / rng
        if f.c[j] > hh and pos >= cp:
            return 1
        if f.c[j] < ll and pos <= 1 - cp:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e10[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class DailyTailCandle(_Lib):
    id = "lib_tail_candle"
    name = "Daily tail-candle continuation"
    family = "momentum"
    tf = D1
    defaults = {"shock_z": 2.0, "hold_days": 3, "stop_atr": 2.5, "tgt_r": 3.0}
    grid = {"shock_z": [1.5, 2.5], "hold_days": [2, 5]}

    def hold_s(self):
        return self.p["hold_days"] * D1

    def setup(self):
        c = self.f.c
        self.lr = [None] + [math.log(c[k] / c[k - 1]) if c[k - 1] > 0 and c[k] > 0 else None for k in range(1, len(c))]
        self.e50, self.e200 = self.ema(50), self.ema(200)

    def sig(self, i, j):
        f = self.f
        if j < 31 or self.e200[j] is None or self.lr[j] is None:
            return 0
        prev = [x for x in self.lr[j - 30:j] if x is not None]
        if len(prev) < 30:
            return 0
        mu = sum(prev) / 30
        sd = math.sqrt(sum((x - mu) ** 2 for x in prev) / 29)
        rng = f.h[j] - f.l[j]
        if sd <= 0 or rng <= 0:
            return 0
        pos, z, up = (f.c[j] - f.l[j]) / rng, self.lr[j] / sd, self.e50[j] > self.e200[j]
        if z > self.p["shock_z"] and pos >= 0.8 and up:
            return 1
        if z < -self.p["shock_z"] and pos <= 0.2 and not up:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        f = self.f
        mid = (f.h[j0] + f.l[j0]) / 2
        return (f.c[j] - mid) * side < 0


class MonthBoundary(_Lib):
    id = "lib_month_boundary"
    name = "Month-boundary continuation"
    family = "seasonality"
    tf, hold = D1, 7 * D1
    defaults = {"prior_month_threshold": 0.05, "stop_atr": 3.0, "tgt_r": 3.0}
    grid = {"prior_month_threshold": [0.04, 0.07]}

    def setup(self):
        self.e100, self.e20 = self.ema(100), self.ema(20)

    def sig(self, i, j):
        f = self.f
        if time.gmtime(f.t[j] + D1).tm_mday != 1:
            return 0
        n = time.gmtime(f.t[j]).tm_mday  # days in the month that just ended
        if j < n or self.e100[j] is None:
            return 0
        r, th = f.c[j] / f.c[j - n] - 1, self.p["prior_month_threshold"]
        if r > th and f.c[j] > self.e100[j]:
            return 1
        if r < -th and f.c[j] < self.e100[j]:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e20[j]
        return e is not None and (self.f.c[j] - e) * side < 0


# ============================================================ slow: 4-hour
class FourHourVolumeDonchian(_Lib):
    id = "lib_4h_volume_donchian"
    name = "4h volume-confirmed Donchian"
    family = "breakout"
    tf, hold = H4, 21 * D1
    defaults = {"breakout_lookback": 30, "volume_ratio": 1.5, "stop_atr": 2.8}
    grid = {"breakout_lookback": [20, 40], "volume_ratio": [1.2, 1.8]}

    def setup(self):
        self.e50, self.e200, self.va = self.ema(50), self.ema(200), self.vsma(20)

    def sig(self, i, j):
        f, n = self.f, self.p["breakout_lookback"]
        hh, ll = _hh(f.h, j, n), _ll(f.l, j, n)
        if hh is None or self.e200[j] is None or not self.va[j] or f.v[j] <= self.p["volume_ratio"] * self.va[j]:
            return 0
        up = self.e50[j] > self.e200[j]
        return 1 if f.c[j] > hh and up else -1 if f.c[j] < ll and not up else 0

    def ex(self, i, j, side, j0):
        f = self.f
        ll, hh = _ll(f.l, j, 10), _hh(f.h, j, 10)
        if ll is None:
            return False
        return f.c[j] < ll if side == 1 else f.c[j] > hh


class FourHourATRTrail(_Lib):
    id = "lib_4h_atr_trail"
    name = "4h ATR trailing trend"
    tf, hold = H4, 30 * D1
    defaults = {"stop_atr": 3.0, "new_close_lookback": 10}
    grid = {"stop_atr": [2.5, 3.5], "new_close_lookback": [8, 16]}

    def setup(self):
        self.e100 = self.ema(100)

    def sig(self, i, j):
        f, n, e = self.f, self.p["new_close_lookback"], self.e100
        if j < n + 7 or e[j] is None or e[j - 6] is None:
            return 0
        hc, lc = _hh(f.c, j, n), _ll(f.c, j, n)
        hc0, lc0 = _hh(f.c, j - 1, n), _ll(f.c, j - 1, n)
        if f.c[j] > e[j] and e[j] > e[j - 6] and f.c[j] > hc and f.c[j - 1] <= hc0:
            return 1
        if f.c[j] < e[j] and e[j] < e[j - 6] and f.c[j] < lc and f.c[j - 1] >= lc0:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        f, e, a = self.f, self.e100[j], self.a[j]
        if e is not None and (f.c[j] - e) * side < 0:
            return True
        if a is None:
            return False
        k = self.p["stop_atr"] * a
        if side == 1:
            return f.c[j] < max(f.h[j0:j + 1]) - k
        return f.c[j] > min(f.l[j0:j + 1]) + k


class FourHourEMAReclaim(_Lib):
    id = "lib_4h_ema_reclaim"
    name = "4h EMA50 reclaim"
    tf = H4
    defaults = {"ema_pullback": 50, "hold_4h_bars": 12, "stop_atr": 2.5, "tgt_r": 3.0}
    grid = {"ema_pullback": [34, 65], "hold_4h_bars": [18, 24]}

    def hold_s(self):
        return self.p["hold_4h_bars"] * H4

    def setup(self):
        self.ep, self.e200 = self.ema(self.p["ema_pullback"]), self.ema(200)

    def sig(self, i, j):
        f, e = self.f, self.ep
        if self.e200[j] is None or e[j - 1] is None:
            return 0
        up = e[j] > self.e200[j]
        if up and f.c[j - 1] < e[j - 1] and f.c[j] > e[j] and f.l[j] <= e[j]:
            return 1
        if not up and f.c[j - 1] > e[j - 1] and f.c[j] < e[j] and f.h[j] >= e[j]:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.ep[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class FourHourBollingerSqueeze(_Lib):
    id = "lib_4h_bb_squeeze"
    name = "4h Bollinger squeeze expansion"
    family = "volatility"
    tf, hold = H4, 12 * H4
    defaults = {"band_period": 20, "width_percentile": 10, "stop_atr": 2.7, "tgt_r": 3.0}
    grid = {"band_period": [25, 30], "width_percentile": [15, 20]}

    def setup(self):
        f, n = self.f, self.p["band_period"]

        def bands():
            m, sd = I.sma(f.c, n), I.stdev(f.c, n)
            k = math.sqrt(n / (n - 1.0))  # sample standard deviation
            up = [None if a is None else a + 2 * b * k for a, b in zip(m, sd)]
            lo = [None if a is None else a - 2 * b * k for a, b in zip(m, sd)]
            w = [None if a is None or not a else (u - lw) / a for a, u, lw in zip(m, up, lo)]
            return up, lo, w, I.percentile_rank(w, 120)
        self.ub, self.lb, self.w, self.wr = f.memo(("bb", n), bands)

    def sig(self, i, j):
        f, wr = self.f, self.wr
        if j < 2 or wr[j - 1] is None or self.ub[j - 1] is None:
            return 0
        if wr[j - 1] >= self.p["width_percentile"] / 100.0:
            return 0
        return 1 if f.c[j] > self.ub[j - 1] else -1 if f.c[j] < self.lb[j - 1] else 0

    def ex(self, i, j, side, j0):
        if self.ub[j] is None:
            return False
        c = self.f.c[j]
        return c < self.ub[j] if side == 1 else c > self.lb[j]


class WeekendCompressionBreak(_Lib):
    id = "lib_weekend_break"
    name = "Weekend range break (4h)"
    family = "seasonality"
    tf, hold = H4, 5 * D1
    defaults = {"weekend_range_frac": 0.75, "stop_atr": 3.0, "tgt_r": 3.0}
    grid = {"weekend_range_frac": [0.5, 1.0]}

    def setup(self):
        self.e50, self.e200 = self.ema(50), self.ema(200)

    def weekend(self, j):
        """High and low of the Saturday-Sunday before the week of bar j."""
        f = self.f
        t = f.t[j]
        mon = t - t % D1 - weekday(t) * D1
        sat = mon - 2 * D1
        hs, ls, k = [], [], j
        while k >= 0 and f.t[k] >= sat:
            if f.t[k] < mon:
                hs.append(f.h[k])
                ls.append(f.l[k])
            k -= 1
        return (max(hs), min(ls)) if len(hs) >= 10 else (None, None)

    def sig(self, i, j):
        f = self.f
        if weekday(f.t[j]) != 0 or self.e200[j] is None:
            return 0
        wh, wl = self.weekend(j)
        if wh is None:
            return 0
        first = weekday(f.t[j - 1]) != 0
        up = self.e50[j] > self.e200[j]
        if f.c[j] > wh and (first or f.c[j - 1] <= wh) and up:
            return 1
        if f.c[j] < wl and (first or f.c[j - 1] >= wl) and not up:
            return -1
        return 0

    def stop_dist(self, i, j, side, d):
        wh, wl = self.weekend(j)
        return min(d, self.p["weekend_range_frac"] * (wh - wl)) if wh is not None else d

    def ex(self, i, j, side, j0):
        f = self.f
        tc = f.t[j] + H4
        if weekday(tc) >= 5 or (weekday(tc) == 4 and (tc % D1) >= 21 * 3600):
            return True
        wh, wl = self.weekend(j0)
        return wh is not None and wl < f.c[j] < wh


# ============================================================ slow: hourly
class HourlyEMAReclaimTrend(_Lib):
    id = "lib_1h_ema50_reclaim"
    name = "Hourly EMA50 reclaim in trend"
    tf, hold = H1, 72 * H1
    defaults = {"ema_fast": 50, "stop_atr": 2.5, "tgt_r": 2.0}
    grid = {"ema_fast": [34, 65], "stop_atr": [2.0, 3.0]}

    def setup(self):
        self.ef, self.e200 = self.ema(self.p["ema_fast"]), self.ema(200)

    def sig(self, i, j):
        f, e = self.f, self.ef
        if j < 5 or self.e200[j] is None or e[j - 4] is None:
            return 0
        if e[j] > self.e200[j] and e[j] > e[j - 4] and f.c[j - 1] <= e[j - 1] and f.c[j] > e[j]:
            return 1
        if e[j] < self.e200[j] and e[j] < e[j - 4] and f.c[j - 1] >= e[j - 1] and f.c[j] < e[j]:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.ef[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class HourlyRSIReset(_Lib):
    id = "lib_1h_rsi_reset"
    name = "Hourly pullback RSI reset"
    tf, hold = H1, 48 * H1
    defaults = {"rsi_long_reentry": 45, "stop_atr": 2.8, "tgt_r": 2.0}
    grid = {"rsi_long_reentry": [40, 50]}

    def setup(self):
        self.r, self.e50, self.e200 = self.rsi(14), self.ema(50), self.ema(200)

    def sig(self, i, j):
        r, f, lo = self.r, self.f, self.p["rsi_long_reentry"]
        hi = 100 - lo
        if r[j] is None or r[j - 1] is None or self.e200[j] is None:
            return 0
        up = self.e50[j] > self.e200[j]
        if up and r[j - 1] <= lo < r[j] and f.c[j] > self.e50[j]:
            return 1
        if not up and r[j - 1] >= hi > r[j] and f.c[j] < self.e50[j]:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        r = self.r[j]
        return r is not None and (r >= 70 if side == 1 else r <= 30)


class HourlyATRExpansion(_Lib):
    id = "lib_1h_atr_expansion"
    name = "Hourly range expansion with 4h trend"
    family = "volatility"
    tf, hold = H1, 48 * H1
    defaults = {"expansion_ratio": 1.8, "range_lookback": 6, "stop_atr": 2.6, "tgt_r": 3.0}
    grid = {"expansion_ratio": [1.5, 2.2], "range_lookback": [9, 12]}

    def setup(self):
        self.e20 = self.ema(20)

    def sig(self, i, j):
        f, a, n = self.f, self.a, self.p["range_lookback"]
        if j < n or a[j - 1] is None:
            return 0
        if f.h[j] - f.l[j] <= self.p["expansion_ratio"] * a[j - 1]:
            return 0
        up = self.up(H4, i)
        if up is None:
            return 0
        if up and f.c[j] > f.o[j] and f.c[j] > _hh(f.h, j, n):
            return 1
        if not up and f.c[j] < f.o[j] and f.c[j] < _ll(f.l, j, n):
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e20[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class HourlyMACDDailyGate(_Lib):
    id = "lib_1h_macd"
    name = "Hourly MACD with daily gate"
    family = "momentum"
    tf, hold = H1, 120 * H1
    defaults = {"macd_fast": 12, "macd_slow": 26, "stop_atr": 3.0, "tgt_r": 4.0}
    grid = {"macd_fast": [10, 15], "macd_slow": [24, 30]}

    def setup(self):
        f, a, b = self.f, self.p["macd_fast"], self.p["macd_slow"]
        self.line, self.sigl, self.hist = f.memo(("macd", a, b), lambda: I.macd(f.c, a, b, 9))
        self.d100 = self.sma(100, D1)
        self.dc = self.m.frame(D1).c

    def sig(self, i, j):
        x = self.cross(self.line, self.sigl, j)
        if not x:
            return 0
        d, c = self.m.at(D1, self.d100, i), self.m.at(D1, self.dc, i)
        if d is None or c is None:
            return 0
        return x if (c - d) * x > 0 else 0

    def ex(self, i, j, side, j0):
        return self.cross(self.line, self.sigl, j) == -side


class HourlyADXCross(_Lib):
    id = "lib_1h_adx_cross"
    name = "Hourly ADX-gated EMA cross"
    tf, hold = H1, 120 * H1
    defaults = {"adx_threshold": 25, "ema_fast": 20, "stop_atr": 3.0, "tgt_r": 4.0}
    grid = {"adx_threshold": [20, 30], "ema_fast": [15, 25]}

    def setup(self):
        f = self.f
        self.ef, self.e50 = self.ema(self.p["ema_fast"]), self.ema(50)
        self.adx, self.pdi, self.mdi = f.memo(("adx", 14), lambda: I.adx(f.h, f.l, f.c, 14))

    def sig(self, i, j):
        x = self.cross(self.ef, self.e50, j)
        if not x or self.adx[j] is None or self.adx[j] <= self.p["adx_threshold"]:
            return 0
        return x if (self.pdi[j] - self.mdi[j]) * x > 0 else 0

    def ex(self, i, j, side, j0):
        return self.cross(self.ef, self.e50, j) == -side


class WeekdayHourlyContinuation(_Lib):
    id = "lib_weekday_1h_breakout"
    name = "Weekday hourly channel breakout"
    family = "seasonality"
    tf, hold = H1, 72 * H1
    defaults = {"price_channel_hours": 12, "stop_atr": 3.0, "tgt_r": 3.0}
    grid = {"price_channel_hours": [8, 16]}

    def setup(self):
        self.e20, self.e50, self.e200 = self.ema(20), self.ema(50), self.ema(200)

    def sig(self, i, j):
        f, n = self.f, self.p["price_channel_hours"]
        if j < n + 1 or not us_week_ok(f.t[j] + H1) or self.e200[j] is None:
            return 0
        up = self.e50[j] > self.e200[j]
        hh, ll, hh0, ll0 = _hh(f.h, j, n), _ll(f.l, j, n), _hh(f.h, j - 1, n), _ll(f.l, j - 1, n)
        if up and f.c[j] > hh and f.c[j - 1] <= hh0:
            return 1
        if not up and f.c[j] < ll and f.c[j - 1] >= ll0:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e20[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class HourlyROCVolCap(_Lib):
    id = "lib_1h_roc_volcap"
    name = "Hourly momentum with 4h volatility cap"
    family = "volatility"
    tf, hold, stop_tf = H1, 120 * H1, H4
    defaults = {"roc_threshold": 0.025, "vol_percentile_cap": 75, "stop_atr": 3.2, "tgt_r": 4.0}
    grid = {"roc_threshold": [0.02, 0.035], "vol_percentile_cap": [65, 85]}

    def setup(self):
        f4 = self.m.frame(H4)
        a4 = self.atr_tf(H4)
        self.vr = f4.memo(("atrpct_rank", 180), lambda: I.percentile_rank(
            [None if a4[k] is None or not f4.c[k] else a4[k] / f4.c[k] for k in range(len(a4))], 180))

    def roc(self, j):
        c = self.f.c
        return None if j < 20 else c[j] / c[j - 20] - 1

    def sig(self, i, j):
        r, r0, th = self.roc(j), self.roc(j - 1), self.p["roc_threshold"]
        vr, up = self.m.at(H4, self.vr, i), self.up(H4, i)
        if None in (r, r0, vr, up) or vr >= self.p["vol_percentile_cap"] / 100.0:
            return 0
        if r > th and r0 <= th and up:
            return 1
        if r < -th and r0 >= -th and not up:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        r = self.roc(j)
        return r is not None and r * side < 0


class HourlyRSI2DailyTrend(_Lib):
    id = "lib_1h_rsi2_daily"
    name = "Hourly RSI(2) dip with daily trend"
    family = "mean_reversion"
    tf = H1
    defaults = {"rsi_extreme": 5, "max_hold_hours": 12, "stop_atr": 3.0, "tgt_r": 2.0}
    grid = {"rsi_extreme": [8, 10], "max_hold_hours": [18, 24]}

    def hold_s(self):
        return self.p["max_hold_hours"] * H1

    def setup(self):
        self.r = self.rsi(2)

    def sig(self, i, j):
        r, f, x = self.r, self.f, self.p["rsi_extreme"]
        if j < 3 or None in (r[j], r[j - 1], r[j - 2]) or not self.a[j] or self.a[j] / f.c[j] <= 0.003:
            return 0
        up = self.up(D1, i)
        if up is None:
            return 0
        if up and r[j] < x and r[j - 1] < x and r[j - 2] >= x:
            return 1
        if not up and r[j] > 100 - x and r[j - 1] > 100 - x and r[j - 2] <= 100 - x:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        r = self.r[j]
        return r is not None and (r > 60 if side == 1 else r < 40)


class USHourFollowThrough(_Lib):
    id = "lib_us_hour_follow"
    name = "US-hours follow-through"
    family = "seasonality"
    tf, hold = H1, 8 * H1
    defaults = {"session_move_threshold": 0.01, "stop_atr": 2.5, "tgt_r": 2.5}
    grid = {"session_move_threshold": [0.008, 0.015]}

    def setup(self):
        self.e20 = self.ema(20)

    def sig(self, i, j):
        f = self.f
        if j < 4 or (f.t[j] + H1) % D1 != 16 * 3600:
            return 0
        up = self.up(H4, i)
        if up is None:
            return 0
        r, th = math.log(f.c[j] / f.c[j - 4]), self.p["session_move_threshold"]
        return 1 if r > th and up else -1 if r < -th and not up else 0

    def ex(self, i, j, side, j0):
        f = self.f
        if (f.t[j] + H1) % D1 == 0:
            return True
        e = self.e20[j]
        return e is not None and (f.c[j] - e) * side < 0


# ============================================================ fast: 5-minute base
class _Fast(_Lib):
    cadence = "fast"

    def gate(self, i):
        return self.up(H1, i)


class FifteenTrendResumption(_Fast):
    id = "lib_15m_trend_resume"
    name = "15m trend resumption, hourly gate"
    tf, hold = M15, 24 * H1
    defaults = {"ema_15m": 20, "rsi_gate": 50, "stop_atr": 2.8, "tgt_r": 3.0}
    grid = {"ema_15m": [15, 30], "rsi_gate": [45, 55]}

    def setup(self):
        self.e, self.r = self.ema(self.p["ema_15m"]), self.rsi(14)

    def sig(self, i, j):
        f, e, r, up = self.f, self.e, self.r, self.gate(i)
        if up is None or e[j - 1] is None or r[j] is None:
            return 0
        g = self.p["rsi_gate"]
        if up and f.c[j - 1] < e[j - 1] and f.c[j] > e[j] and r[j] > g:
            return 1
        if not up and f.c[j - 1] > e[j - 1] and f.c[j] < e[j] and r[j] < 100 - g:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class FifteenRangeBreak(_Fast):
    id = "lib_15m_range_break"
    name = "15m range break, hourly trend"
    family = "breakout"
    tf, hold = M15, 16 * M15
    defaults = {"breakout_bars": 24, "volume_ratio": 1.3, "stop_atr": 2.8, "tgt_r": 3.0}
    grid = {"breakout_bars": [16, 32], "volume_ratio": [1.2, 1.5]}

    def setup(self):
        self.e20, self.va = self.ema(20), self.vsma(20)

    def sig(self, i, j):
        f, n, up = self.f, self.p["breakout_bars"], self.gate(i)
        hh = _hh(f.h, j, n)
        if up is None or hh is None or not self.va[j] or f.v[j] <= self.p["volume_ratio"] * self.va[j]:
            return 0
        if up and f.c[j] > hh:
            return 1
        if not up and f.c[j] < _ll(f.l, j, n):
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e20[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class FiveMinuteImpulse(_Fast):
    id = "lib_5m_impulse"
    name = "5m impulse in hourly trend"
    family = "momentum"
    tf, hold = M5, 24 * M5
    defaults = {"roc_30m_threshold": 0.008, "volume_ratio": 1.5, "stop_atr": 3.0, "tgt_r": 3.0}
    grid = {"roc_30m_threshold": [0.006, 0.012], "volume_ratio": [1.3, 2.0]}

    def setup(self):
        self.e20, self.va = self.ema(20), self.vsma(20)

    def sig(self, i, j):
        f, up = self.f, self.gate(i)
        if (up is None or j < 6 or self.e20[j] is None or not self.va[j]
                or f.v[j] <= self.p["volume_ratio"] * self.va[j]):
            return 0
        r, th = f.c[j] / f.c[j - 6] - 1, self.p["roc_30m_threshold"]
        if up and r > th and f.c[j] > self.e20[j]:
            return 1
        if not up and r < -th and f.c[j] < self.e20[j]:
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e20[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class FiveMinuteVolumeBreak(_Fast):
    id = "lib_5m_volume_break"
    name = "5m high-volume range break"
    family = "breakout"
    tf, hold = M5, 24 * M5
    defaults = {"lookback_5m": 36, "volume_ratio": 2.0, "stop_atr": 3.0, "tgt_r": 3.0}
    grid = {"lookback_5m": [24, 48], "volume_ratio": [1.7, 2.5]}

    def setup(self):
        self.e20, self.va = self.ema(20), self.vsma(20)

    def sig(self, i, j):
        f, n, up = self.f, self.p["lookback_5m"], self.gate(i)
        hh = _hh(f.h, j, n)
        if (up is None or hh is None or not self.va[j] or f.v[j] <= self.p["volume_ratio"] * self.va[j]
                or not self.a[j] or self.a[j] / f.c[j] <= 0.002):
            return 0
        if up and f.c[j] > hh:
            return 1
        if not up and f.c[j] < _ll(f.l, j, n):
            return -1
        return 0

    def ex(self, i, j, side, j0):
        e = self.e20[j]
        return e is not None and (self.f.c[j] - e) * side < 0


class OverlapRangeBreak(_Fast):
    id = "lib_overlap_range_break"
    name = "London/New York overlap range break"
    family = "seasonality"
    tf, hold = M15, 6 * H1
    defaults = {"window_start_utc": 14, "opening_range_hours": 2, "stop_atr": 2.0, "tgt_r": 2.5}
    grid = {"window_start_utc": [13, 15], "opening_range_hours": [1, 3]}

    def setup(self):
        self.e20 = self.ema(20)

    def rng(self, j):
        f = self.f
        tc = f.t[j] + M15
        day0 = tc - tc % D1
        ws = day0 + self.p["window_start_utc"] * 3600
        r0 = ws - self.p["opening_range_hours"] * 3600
        hs, ls, k = [], [], j
        while k >= 0 and f.t[k] >= r0:
            if f.t[k] < ws:
                hs.append(f.h[k])
                ls.append(f.l[k])
            k -= 1
        need = self.p["opening_range_hours"] * 4
        return (max(hs), min(ls), ws) if len(hs) == need else (None, None, ws)

    def sig(self, i, j):
        f = self.f
        tc = f.t[j] + M15
        rh, rl, ws = self.rng(j)
        if rh is None or not (ws < tc <= ws + 3 * 3600) or self.e20[j] is None:
            return 0
        up = self.gate(i)
        if up is None:
            return 0
        first = f.t[j - 1] + M15 <= ws
        if up and f.c[j] > rh and (first or f.c[j - 1] <= rh):
            return 1
        if not up and f.c[j] < rl and (first or f.c[j - 1] >= rl):
            return -1
        return 0

    def stop_dist(self, i, j, side, d):
        rh, rl, _ = self.rng(j)
        return max(d, 0.5 * (rh - rl)) if rh is not None else d

    def ex(self, i, j, side, j0):
        f = self.f
        s = (f.t[j] + M15) % D1
        if s >= 20 * 3600 or s < 12 * 3600:
            return True
        e = self.e20[j]
        return e is not None and (f.c[j] - e) * side < 0


ALL = [DailyTSMOMATR, DailyReturnVote, DailyEMACrossHold, DailyROCGate, DailyClosingRangeBreakout,
       DailyTailCandle, MonthBoundary, FourHourVolumeDonchian, FourHourATRTrail, FourHourEMAReclaim,
       FourHourBollingerSqueeze, WeekendCompressionBreak, HourlyEMAReclaimTrend, HourlyRSIReset,
       HourlyATRExpansion, HourlyMACDDailyGate, HourlyADXCross, WeekdayHourlyContinuation, HourlyROCVolCap,
       HourlyRSI2DailyTrend, USHourFollowThrough, FifteenTrendResumption, FifteenRangeBreak,
       FiveMinuteImpulse, FiveMinuteVolumeBreak, OverlapRangeBreak]
