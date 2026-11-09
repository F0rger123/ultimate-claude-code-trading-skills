"""Strategies. Each one looks only at data up to the close of base bar i.

entry(i) -> None or dict(side=+1|-1, stop=price, target=price|None)
exit(i, pos) -> True to exit at the next bar's open
features(i) -> dict of context saved with every trade (used by the learning loop)
"""
import itertools

from . import indicators as I

H1, M30, M15, M5 = 3600, 1800, 900, 300


class Strategy:
    id = "base"
    name = "Base"
    family = ""
    source = ""
    defaults = {}
    grid = {}
    max_bars = None

    def __init__(self, mkt, **params):
        self.m = mkt
        self.p = dict(self.defaults)
        self.p.update(params)
        self.prepare()

    @classmethod
    def combos(cls):
        keys = sorted(cls.grid)
        for vals in itertools.product(*[cls.grid[k] for k in keys]):
            yield dict(zip(keys, vals))

    def prepare(self):
        pass

    def entry(self, i):
        return None

    def exit(self, i, pos):
        return False

    # shared context for the journal and learning loop
    def features(self, i):
        m = self.m
        h1 = m.frame(H1)
        e50 = h1.memo(("ema", 50), lambda: I.ema(h1.c, 50))
        e200 = h1.memo(("ema", 200), lambda: I.ema(h1.c, 200))
        a = m.b.memo(("atr", 14), lambda: I.atr(m.b.h, m.b.l, m.b.c, 14))
        ap = m.b.memo(("atrpct_rank",), lambda: I.percentile_rank(
            [None if a[k] is None else a[k] / m.b.c[k] for k in range(len(a))], 2016))
        va = m.b.memo(("sma_v", 20), lambda: I.sma(m.b.v, 20))
        x50, x200 = m.at(H1, e50, i), m.at(H1, e200, i)
        t = m.b.t[i]
        return {
            "hour_utc": (t // 3600) % 24,
            "weekday": (t // 86400 + 4) % 7,  # 0 = Monday
            "trend_1h": None if x50 is None or x200 is None else (1 if x50 > x200 else -1),
            "vol_regime": None if ap[i] is None else (0 if ap[i] < 0.33 else 1 if ap[i] < 0.67 else 2),
            "volume_ratio": None if not va[i] else round(m.b.v[i] / va[i], 2),
        }

    def atr_tf(self, gran, n=14):
        f = self.m.frame(gran)
        return f.memo(("atr", n), lambda: I.atr(f.h, f.l, f.c, n))


class MTFQuick(Strategy):
    """Owner's strategy: 1h, 30m, 15m and 5m signals all agree, volume confirms, enter on the bar
    that completes the alignment. Exit when the 15m signal flips. Hard stop at k x 15m ATR."""
    id = "mtf_quick"
    name = "4-TF alignment (quick)"
    family = "owner"
    source = "Owner's TradingView method; SuperTrend stands in for the unnamed indicator"
    defaults = {"kind": "supertrend", "st_n": 10, "st_mult": 3.0, "vol_k": 1.0, "stop_atr": 1.5}
    grid = {"st_mult": [2.0, 3.0], "vol_k": [0.0, 1.2], "stop_atr": [1.5, 2.5]}
    tfs = (H1, M30, M15, M5)

    def prepare(self):
        m, p = self.m, self.p
        self.sig = {}
        for g in self.tfs:
            f = m.frame(g)
            self.sig[g] = f.memo(("sig", p["kind"], p["st_n"], p["st_mult"]), lambda f=f: I.signal_line(
                f.h, f.l, f.c, p["kind"], n=p["st_n"], mult=p["st_mult"]))
        self.vavg = m.b.memo(("sma_v", 20), lambda: I.sma(m.b.v, 20))
        self.a15 = self.atr_tf(M15)
        self.prev_state = {}

    def state(self, i, tfs=None):
        vals = [self.m.at(g, self.sig[g], i) for g in (tfs or self.tfs)]
        if None in vals:
            return 0
        return vals[0] if all(v == vals[0] for v in vals) else 0

    def entry(self, i):
        if i == 0:
            return None
        s, s0 = self.state(i), self.state(i - 1)
        if s == 0 or s == s0:
            return None
        if self.p["vol_k"] > 0 and (not self.vavg[i] or self.m.b.v[i] < self.p["vol_k"] * self.vavg[i]):
            return None
        a = self.m.at(M15, self.a15, i)
        if not a:
            return None
        c = self.m.b.c[i]
        return {"side": s, "stop": c - s * self.p["stop_atr"] * a, "target": None}

    def exit(self, i, pos):
        d = self.m.at(M15, self.sig[M15], i)
        return d is not None and d != pos["side"]

    def features(self, i):
        f = Strategy.features(self, i)
        # age of the 1h signal in hours: the owner reads fresh higher-timeframe signals as stronger
        h = self.sig[H1]
        j = self.m.maps[H1][i]
        age = 0
        while j - age - 1 >= 0 and h[j - age - 1] == h[j]:
            age += 1
            if age > 200:
                break
        f["htf_age_h"] = age
        return f


class MTFSwing(MTFQuick):
    """1h and 30m agree: enter. Exit when the 30m signal flips. Stop at k x 30m ATR."""
    id = "mtf_swing"
    name = "1h + 30m alignment (swing)"
    defaults = {"kind": "supertrend", "st_n": 10, "st_mult": 3.0, "vol_k": 0.0, "stop_atr": 2.0}
    grid = {"st_mult": [2.0, 3.0], "stop_atr": [1.5, 2.5, 3.5]}
    tfs = (H1, M30)

    def prepare(self):
        MTFQuick.prepare(self)
        self.a30 = self.atr_tf(M30)

    def entry(self, i):
        if i == 0 or not self.m.closes_tf(M30, i):
            return None
        s, s0 = self.state(i), self.state(i - 1)
        if s == 0 or s == s0:
            return None
        a = self.m.at(M30, self.a30, i)
        if not a:
            return None
        c = self.m.b.c[i]
        return {"side": s, "stop": c - s * self.p["stop_atr"] * a, "target": None}

    def exit(self, i, pos):
        d = self.m.at(M30, self.sig[M30], i)
        return d is not None and d != pos["side"]


class DonchianBreakout(Strategy):
    """15m close breaks the prior n-bar high (low), 1h trend agrees. Exit on the n/2 channel."""
    id = "donchian_breakout"
    name = "Trend breakout (Donchian)"
    family = "trend"
    source = "Classic channel breakout (Turtle-style)"
    defaults = {"n": 20, "stop_atr": 2.0, "tf": M15}
    grid = {"n": [20, 48], "stop_atr": [1.5, 2.5]}

    def prepare(self):
        m, n = self.m, self.p["n"]
        self.tf = self.p["tf"]
        f = m.frame(self.tf)
        self.hi, self.lo = f.memo(("don", n), lambda: I.donchian(f.h, f.l, n))
        self.xhi, self.xlo = f.memo(("don", n // 2), lambda: I.donchian(f.h, f.l, n // 2))
        h1 = m.frame(H1)
        self.e50 = h1.memo(("ema", 50), lambda: I.ema(h1.c, 50))
        self.e200 = h1.memo(("ema", 200), lambda: I.ema(h1.c, 200))
        self.a = self.atr_tf(self.tf)
        self.f = f

    def entry(self, i):
        m = self.m
        if not m.closes_tf(self.tf, i):
            return None
        j = m.maps[self.tf][i]
        if j < 1 or self.hi[j] is None:
            return None
        x50, x200 = m.at(H1, self.e50, i), m.at(H1, self.e200, i)
        if x50 is None or x200 is None:
            return None
        c = self.f.c[j]
        side = 0
        if c > self.hi[j] and x50 > x200:
            side = 1
        elif c < self.lo[j] and x50 < x200:
            side = -1
        if not side:
            return None
        return {"side": side, "stop": c - side * self.p["stop_atr"] * self.a[j], "target": None}

    def exit(self, i, pos):
        m = self.m
        if not m.closes_tf(self.tf, i):
            return False
        j = m.maps[self.tf][i]
        c = self.f.c[j]
        if self.xlo[j] is None:
            return False
        return c < self.xlo[j] if pos["side"] == 1 else c > self.xhi[j]


class EMAPullback(Strategy):
    """15m trend (EMA50 > EMA200): the bar dips to the 20 EMA and closes back above it. 2R target."""
    id = "ema_pullback"
    name = "EMA pullback"
    family = "trend"
    source = "Common day-trader pullback setup"
    defaults = {"stop_atr": 1.5, "tgt_r": 2.0, "tf": M15}
    grid = {"stop_atr": [1.0, 2.0], "tgt_r": [1.5, 2.5]}
    max_bars = 288

    def prepare(self):
        self.tf = self.p["tf"]
        f = self.m.frame(self.tf)
        self.f = f
        self.e20 = f.memo(("ema", 20), lambda: I.ema(f.c, 20))
        self.e50 = f.memo(("ema", 50), lambda: I.ema(f.c, 50))
        self.e200 = f.memo(("ema", 200), lambda: I.ema(f.c, 200))
        self.a = self.atr_tf(self.tf)

    def entry(self, i):
        m = self.m
        if not m.closes_tf(self.tf, i):
            return None
        j = m.maps[self.tf][i]
        if j < 1 or self.e200[j] is None:
            return None
        f, e20 = self.f, self.e20[j]
        up = self.e50[j] > self.e200[j]
        side = 0
        if up and f.l[j] <= e20 < f.c[j] and f.c[j] > f.o[j]:
            side = 1
        elif not up and f.h[j] >= e20 > f.c[j] and f.c[j] < f.o[j]:
            side = -1
        if not side:
            return None
        c = f.c[j]
        risk = self.p["stop_atr"] * self.a[j]
        return {"side": side, "stop": c - side * risk, "target": c + side * self.p["tgt_r"] * risk}


class VWAPReclaim(Strategy):
    """US-session trend day: 1h trend up and the 5m bar closes back above the daily VWAP with
    volume. Mirror for shorts. 2R target, flat at the UTC day end."""
    id = "vwap_reclaim"
    name = "VWAP reclaim"
    family = "intraday"
    source = "Common intraday VWAP setup"
    defaults = {"stop_atr": 2.0, "tgt_r": 2.0, "vol_k": 1.2}
    grid = {"stop_atr": [1.5, 2.5], "tgt_r": [1.5, 2.5]}

    def prepare(self):
        b = self.m.b
        self.vw = b.memo(("vwap",), lambda: I.daily_vwap(b.t, b.h, b.l, b.c, b.v))
        self.vavg = b.memo(("sma_v", 20), lambda: I.sma(b.v, 20))
        self.a = b.memo(("atr", 14), lambda: I.atr(b.h, b.l, b.c, 14))
        h1 = self.m.frame(H1)
        self.e50 = h1.memo(("ema", 50), lambda: I.ema(h1.c, 50))
        self.e200 = h1.memo(("ema", 200), lambda: I.ema(h1.c, 200))

    def entry(self, i):
        b = self.m.b
        hr = (b.t[i] // 3600) % 24
        if i < 1 or not (13 <= hr < 20) or self.a[i] is None or not self.vavg[i]:
            return None
        if b.v[i] < self.p["vol_k"] * self.vavg[i]:
            return None
        x50, x200 = self.m.at(H1, self.e50, i), self.m.at(H1, self.e200, i)
        if x50 is None or x200 is None:
            return None
        side = 0
        if x50 > x200 and b.c[i - 1] < self.vw[i - 1] and b.c[i] > self.vw[i]:
            side = 1
        elif x50 < x200 and b.c[i - 1] > self.vw[i - 1] and b.c[i] < self.vw[i]:
            side = -1
        if not side:
            return None
        c, risk = b.c[i], self.p["stop_atr"] * self.a[i]
        return {"side": side, "stop": c - side * risk, "target": c + side * self.p["tgt_r"] * risk}

    def exit(self, i, pos):
        t = self.m.b.t[i]
        return (t + 300) % 86400 == 0  # flat at the UTC day end


class RSI2Reversion(Strategy):
    """15m RSI(2) washes out in the direction of the 1h trend: buy the dip, exit on the 5-bar
    average or after 12 bars."""
    id = "rsi2_reversion"
    name = "RSI(2) reversion"
    family = "mean_reversion"
    source = "Connors-style short-term mean reversion"
    defaults = {"lo": 10, "stop_atr": 2.0}
    grid = {"lo": [5, 10], "stop_atr": [1.5, 3.0]}
    max_bars = 36

    def prepare(self):
        f = self.m.frame(M15)
        self.f = f
        self.r = f.memo(("rsi", 2), lambda: I.rsi(f.c, 2))
        self.s5 = f.memo(("sma", 5), lambda: I.sma(f.c, 5))
        h1 = self.m.frame(H1)
        self.e200 = h1.memo(("ema", 200), lambda: I.ema(h1.c, 200))
        self.a = self.atr_tf(M15)

    def entry(self, i):
        m = self.m
        if not m.closes_tf(M15, i):
            return None
        j = m.maps[M15][i]
        e = m.at(H1, self.e200, i)
        if j < 2 or self.r[j] is None or e is None:
            return None
        c, lo = self.f.c[j], self.p["lo"]
        side = 1 if (self.r[j] < lo and c > e) else -1 if (self.r[j] > 100 - lo and c < e) else 0
        if not side:
            return None
        return {"side": side, "stop": c - side * self.p["stop_atr"] * self.a[j], "target": None}

    def exit(self, i, pos):
        m = self.m
        if not m.closes_tf(M15, i):
            return False
        j = m.maps[M15][i]
        c = self.f.c[j]
        return c > self.s5[j] if pos["side"] == 1 else c < self.s5[j]


H4 = 14400


class MTFTrend(MTFQuick):
    """Slow version of the owner's alignment: 4h and 1h agree, exit on the 1h flip. Wider stops,
    so costs are a small share of each trade."""
    id = "mtf_trend"
    name = "4h + 1h alignment (trend)"
    defaults = {"kind": "supertrend", "st_n": 10, "st_mult": 3.0, "vol_k": 0.0, "stop_atr": 2.5}
    grid = {"st_mult": [2.0, 3.0], "stop_atr": [2.0, 3.5]}
    tfs = (H4, H1)

    def prepare(self):
        MTFQuick.prepare(self)
        self.a1 = self.atr_tf(H1)

    def entry(self, i):
        if i < 12 or not self.m.closes_tf(H1, i):
            return None
        s, s0 = self.state(i), self.state(i - 12)
        if s == 0 or s == s0:
            return None
        a = self.m.at(H1, self.a1, i)
        if not a:
            return None
        c = self.m.b.c[i]
        return {"side": s, "stop": c - s * self.p["stop_atr"] * a, "target": None}

    def exit(self, i, pos):
        d = self.m.at(H1, self.sig[H1], i)
        return d is not None and d != pos["side"]

    def features(self, i):
        f = Strategy.features(self, i)
        h = self.sig[H4]
        j = self.m.maps[H4][i]
        age = 0
        while j - age - 1 >= 0 and h[j - age - 1] == h[j] and age < 200:
            age += 1
        f["htf_age_h"] = age * 4
        return f


class Donchian4h(DonchianBreakout):
    id = "donchian_4h"
    name = "Trend breakout, 4h (Donchian)"
    defaults = {"n": 20, "stop_atr": 2.0, "tf": H4}
    grid = {"n": [20, 55], "stop_atr": [2.0, 3.0]}


class Donchian1h(DonchianBreakout):
    id = "donchian_1h"
    name = "Trend breakout, 1h (Donchian)"
    defaults = {"n": 24, "stop_atr": 2.0, "tf": H1}
    grid = {"n": [24, 72], "stop_atr": [2.0, 3.0]}


class EMAPullback1h(EMAPullback):
    id = "ema_pullback_1h"
    name = "EMA pullback, 1h"
    defaults = {"stop_atr": 2.0, "tgt_r": 2.0, "tf": H1}
    grid = {"stop_atr": [1.5, 2.5], "tgt_r": [2.0, 3.0]}
    max_bars = 576


D1 = 86400


class _Slow(Strategy):
    """Shared helpers for daily/4h trend strategies. long_only = 1 skips shorts (crypto drifts up)."""
    tf = D1

    def prepare(self):
        self.f = self.m.frame(self.tf)
        self.a = self.atr_tf(self.tf, 20)
        key = (self.id, tuple(sorted(self.p.items())))
        self.dirs = self.f.memo(key, self.direction)

    def direction(self):
        return [None] * len(self.f.t)

    def _j(self, i):
        if not self.m.closes_tf(self.tf, i):
            return None
        j = self.m.maps[self.tf][i]
        return j if j >= 1 else None

    def entry(self, i):
        j = self._j(i)
        if j is None or self.dirs[j] is None or self.dirs[j - 1] is None or self.a[j] is None:
            return None
        d = self.dirs[j]
        if d == self.dirs[j - 1] or d == 0:
            return None
        if d == -1 and self.p.get("long_only"):
            return None
        c = self.f.c[j]
        return {"side": d, "stop": c - d * self.p["stop_atr"] * self.a[j], "target": None}

    def exit(self, i, pos):
        j = self._j(i)
        return j is not None and self.dirs[j] is not None and self.dirs[j] != pos["side"]


class TSMOMDaily(_Slow):
    """Time-series momentum: long if the daily close is above the close n days ago, short if below."""
    id = "tsmom_daily"
    name = "Time-series momentum, daily"
    family = "trend"
    source = "Moskowitz, Ooi and Pedersen (2012), time-series momentum"
    defaults = {"n": 30, "stop_atr": 4.0, "long_only": 0}
    grid = {"n": [20, 60], "stop_atr": [3.0, 5.0], "long_only": [0, 1]}

    def direction(self):
        c, n = self.f.c, self.p["n"]
        return [None if k < n else (1 if c[k] > c[k - n] else -1) for k in range(len(c))]


class TurtleDaily(_Slow):
    """Turtle-style: close beyond the prior n-day high (low); exit on the n/2-day opposite channel."""
    id = "turtle_daily"
    name = "Turtle breakout, daily"
    family = "trend"
    source = "Turtle trading rules (20/55-day breakouts, 2N stops) as published by Curtis Faith"
    defaults = {"n": 20, "stop_atr": 2.0, "long_only": 0}
    grid = {"n": [20, 55], "stop_atr": [2.0, 3.0], "long_only": [0, 1]}

    def direction(self):
        f, n = self.f, self.p["n"]
        hi, lo = I.donchian(f.h, f.l, n)
        xhi, xlo = I.donchian(f.h, f.l, max(2, n // 2))
        out, d = [None] * len(f.c), 0
        for k in range(len(f.c)):
            if hi[k] is None:
                continue
            if f.c[k] > hi[k]:
                d = 1
            elif f.c[k] < lo[k]:
                d = -1
            elif d == 1 and f.c[k] < xlo[k]:
                d = 0
            elif d == -1 and f.c[k] > xhi[k]:
                d = 0
            out[k] = d
        return out


class EMACross4h(_Slow):
    """4-hour EMA cross: fast above slow = long, below = short. Slow = 4 x fast."""
    id = "ema_cross_4h"
    name = "EMA cross, 4h"
    family = "trend"
    source = "Classic moving-average crossover trend following"
    tf = 14400
    defaults = {"fast": 20, "stop_atr": 4.0, "long_only": 0}
    grid = {"fast": [12, 30], "stop_atr": [3.0, 5.0], "long_only": [0, 1]}

    def direction(self):
        c, n = self.f.c, self.p["fast"]
        a, b = I.ema(c, n), I.ema(c, 4 * n)
        return [None if a[k] is None or b[k] is None else (1 if a[k] > b[k] else -1) for k in range(len(c))]



class TrendEnsemble(Strategy):
    """Daily trend-following ensemble with a regime filter.

    Edge: crypto trends persist (slow information diffusion, herding, leveraged momentum flows), and
    time-series momentum has been documented across markets for a century. The other side is traders
    who fade moves too early and late sellers who capitulate into trends.
    Signal: for each look-back L in `lookbacks` (days), vote +1 if today's close is above the close
    L days ago, else -1. Average the votes. Long at or above +thr, short at or below -thr, flat between.
    Regime: no new entries in CRASH; half size in SIDEWAYS and JUMPY; full size in CALM_TREND.
    Stop: `stop_atr` x 20-day ATR. Nothing here is fitted: look-backs are the usual 1-6 month horizons.
    """
    id = "trend_ensemble"
    name = "Trend ensemble, daily (regime-filtered)"
    family = "trend"
    source = "Time-series momentum (Moskowitz, Ooi, Pedersen 2012; Hurst, Ooi, Pedersen 'A Century of Evidence on Trend-Following')"
    defaults = {"lookbacks": (20, 40, 60, 90, 120), "thr": 0.6, "stop_atr": 3.0, "long_only": 0, "regime": 1}
    grid = {}

    def prepare(self):
        from . import regime as RG
        self.RG = RG
        self.f = self.m.frame(D1)
        self.a = self.atr_tf(D1, 20)
        p = self.p
        key = ("ens", tuple(p["lookbacks"]), p["thr"])
        self.dirs = self.f.memo(key, self._dirs)
        self.reg = self.f.memo(("regime",), lambda: RG.classify(self.f.c, self.f.h))

    def _dirs(self):
        c, lbs, thr = self.f.c, self.p["lookbacks"], self.p["thr"]
        out = [None] * len(c)
        for k in range(max(lbs), len(c)):
            v = sum(1 if c[k] > c[k - L] else -1 for L in lbs) / len(lbs)
            out[k] = 1 if v >= thr else -1 if v <= -thr else 0
        return out

    def _j(self, i):
        if not self.m.closes_tf(D1, i):
            return None
        j = self.m.maps[D1][i]
        return j if j >= 1 else None

    def entry(self, i):
        j = self._j(i)
        if j is None or self.dirs[j] in (None, 0) or self.a[j] is None:
            return None
        d = self.dirs[j]
        if d == self.dirs[j - 1]:
            return None
        if d == -1 and self.p["long_only"]:
            return None
        mult = 1.0
        if self.p["regime"]:
            r = self.reg[j]
            if r is None:
                return None
            mult = self.RG.SIZE[r[0]]
            if mult <= 0:
                return None
        c = self.f.c[j]
        return {"side": d, "stop": c - d * self.p["stop_atr"] * self.a[j], "target": None, "size_mult": mult}

    def exit(self, i, pos):
        j = self._j(i)
        return j is not None and self.dirs[j] is not None and self.dirs[j] != pos["side"]

    def features(self, i):
        f = Strategy.features(self, i)
        j = self.m.maps[D1][i]
        r = self.reg[j] if j >= 0 else None
        f["regime"] = r[0] if r else None
        return f


SLOW = [TSMOMDaily, TurtleDaily, EMACross4h, TrendEnsemble]

ALL = [MTFQuick, MTFSwing, MTFTrend, DonchianBreakout, Donchian1h, Donchian4h, EMAPullback, EMAPullback1h,
       VWAPReclaim, RSI2Reversion] + SLOW
BY_ID = {s.id: s for s in ALL}
