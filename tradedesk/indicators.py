"""Indicators on plain Python lists. Each returns a list the same length as its input;
values that are not defined yet are None. Index i only uses data up to and including bar i."""
import math


def sma(xs, n):
    out = [None] * len(xs)
    s = 0.0
    for i, x in enumerate(xs):
        s += x
        if i >= n:
            s -= xs[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(xs, n):
    out = [None] * len(xs)
    k = 2.0 / (n + 1)
    e = None
    for i, x in enumerate(xs):
        if i < n - 1:
            continue
        if e is None:
            e = sum(xs[i - n + 1:i + 1]) / n
        else:
            e = x * k + e * (1 - k)
        out[i] = e
    return out


def true_range(h, l, c):
    tr = [h[0] - l[0]]
    for i in range(1, len(c)):
        tr.append(max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1])))
    return tr


def atr(h, l, c, n=14):
    """Wilder ATR."""
    tr = true_range(h, l, c)
    out = [None] * len(c)
    a = None
    for i in range(len(tr)):
        if i < n - 1:
            continue
        if a is None:
            a = sum(tr[:n]) / n
        else:
            a = (a * (n - 1) + tr[i]) / n
        out[i] = a
    return out


def rsi(c, n=14):
    out = [None] * len(c)
    if len(c) <= n:
        return out
    gain = loss = 0.0
    for i in range(1, n + 1):
        d = c[i] - c[i - 1]
        gain += max(d, 0)
        loss += max(-d, 0)
    ag, al = gain / n, loss / n
    out[n] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    for i in range(n + 1, len(c)):
        d = c[i] - c[i - 1]
        ag = (ag * (n - 1) + max(d, 0)) / n
        al = (al * (n - 1) + max(-d, 0)) / n
        out[i] = 100.0 if al == 0 else 100 - 100 / (1 + ag / al)
    return out


def supertrend(h, l, c, n=10, mult=3.0):
    """Returns direction list: +1 (buy), -1 (sell), None before defined. Standard SuperTrend."""
    a = atr(h, l, c, n)
    dirs = [None] * len(c)
    up = dn = None
    d = 1
    for i in range(len(c)):
        if a[i] is None:
            continue
        mid = (h[i] + l[i]) / 2
        bu = mid - mult * a[i]
        bd = mid + mult * a[i]
        if up is None:
            up, dn = bu, bd
        else:
            up = max(bu, up) if c[i - 1] > up else bu
            dn = min(bd, dn) if c[i - 1] < dn else bd
            if d == 1 and c[i] < up:
                d = -1
            elif d == -1 and c[i] > dn:
                d = 1
        dirs[i] = d
    return dirs


def ema_cross_dir(c, fast=9, slow=21):
    f, s = ema(c, fast), ema(c, slow)
    return [None if f[i] is None or s[i] is None else (1 if f[i] > s[i] else -1) for i in range(len(c))]


def signal_line(h, l, c, kind="supertrend", **kw):
    """The buy/sell signal used by the multi-timeframe strategy.

    Stand-in for the owner's TradingView indicator until it is named. To plug in the real one,
    add a branch here that returns +1/-1/None per bar.
    """
    if kind == "supertrend":
        return supertrend(h, l, c, kw.get("n", 10), kw.get("mult", 3.0))
    if kind == "ema_cross":
        return ema_cross_dir(c, kw.get("fast", 9), kw.get("slow", 21))
    raise ValueError("unknown signal kind %s" % kind)


def donchian(h, l, n):
    hi = [None] * len(h)
    lo = [None] * len(l)
    for i in range(n, len(h)):
        hi[i] = max(h[i - n:i])  # prior n bars, excludes current
        lo[i] = min(l[i - n:i])
    return hi, lo


def daily_vwap(t, h, l, c, v):
    """VWAP reset each UTC day."""
    out = [None] * len(c)
    day = None
    pv = vv = 0.0
    for i in range(len(c)):
        d = t[i] // 86400
        if d != day:
            day, pv, vv = d, 0.0, 0.0
        tp = (h[i] + l[i] + c[i]) / 3
        pv += tp * v[i]
        vv += v[i]
        out[i] = pv / vv if vv > 0 else c[i]
    return out


def stdev(xs, n):
    out = [None] * len(xs)
    m = sma(xs, n)
    for i in range(n - 1, len(xs)):
        mu = m[i]
        out[i] = math.sqrt(sum((x - mu) ** 2 for x in xs[i - n + 1:i + 1]) / n)
    return out


def percentile_rank(xs, n):
    """Rank of xs[i] among the previous n values, 0..1."""
    out = [None] * len(xs)
    for i in range(n, len(xs)):
        if xs[i] is None:
            continue
        w = [x for x in xs[i - n:i] if x is not None]
        if w:
            out[i] = sum(1 for x in w if x <= xs[i]) / len(w)
    return out


def ema_from(xs, n):
    """EMA of a series whose first values may be None (seeded with the first n defined values)."""
    out = [None] * len(xs)
    start = next((i for i, x in enumerate(xs) if x is not None), None)
    if start is None:
        return out
    sub = ema(xs[start:], n)
    out[start:] = sub
    return out


def macd(c, fast=12, slow=26, sig=9):
    """MACD line (EMA fast - EMA slow), its EMA signal line, and the histogram."""
    f, s = ema(c, fast), ema(c, slow)
    line = [None if a is None or b is None else a - b for a, b in zip(f, s)]
    signal = ema_from(line, sig)
    hist = [None if a is None or b is None else a - b for a, b in zip(line, signal)]
    return line, signal, hist


def adx(h, l, c, n=14):
    """Wilder ADX with +DI and -DI."""
    size = len(c)
    pdi, mdi, out = [None] * size, [None] * size, [None] * size
    if size <= 2 * n:
        return out, pdi, mdi
    tr = true_range(h, l, c)
    pdm = [0.0] + [max(h[i] - h[i - 1], 0.0) if h[i] - h[i - 1] > l[i - 1] - l[i] else 0.0 for i in range(1, size)]
    mdm = [0.0] + [max(l[i - 1] - l[i], 0.0) if l[i - 1] - l[i] > h[i] - h[i - 1] else 0.0 for i in range(1, size)]
    str_, sp, sm = sum(tr[1:n + 1]), sum(pdm[1:n + 1]), sum(mdm[1:n + 1])
    dx = [None] * size
    for i in range(n, size):
        if i > n:
            str_ = str_ - str_ / n + tr[i]
            sp = sp - sp / n + pdm[i]
            sm = sm - sm / n + mdm[i]
        if str_ <= 0:
            continue
        p, m = 100.0 * sp / str_, 100.0 * sm / str_
        pdi[i], mdi[i] = p, m
        dx[i] = 0.0 if p + m == 0 else 100.0 * abs(p - m) / (p + m)
    a = None
    for i in range(2 * n - 1, size):
        if a is None:
            vals = [x for x in dx[n:2 * n] if x is not None]
            if len(vals) < n:
                continue
            a = sum(vals) / n
        else:
            a = (a * (n - 1) + (dx[i] or 0.0)) / n
        out[i] = a
    return out, pdi, mdi
