"""Python parity model of pine/mnq_opening_range_915_930.pine (RESEARCH HYPOTHESIS).

Status: logic and tests only. No lawful CME MNQ intraday history is available to this project, so no
historical profitability numbers exist yet ("historical tests PENDING"). Feed it 15-minute bars of a real
MNQ contract (t = bar OPEN time, UTC seconds) from a licensed source to run the six registered models:
baseline, and each of filters A-E alone, at target 0.5R (plus 0.75R and 1R as separate trials).

MNQ contract (verify against CME before use): $2 per index point, tick 0.25 points = $0.50.
Costs are inputs. The default commission ($0.62/side) and 1-tick slippage per side are ASSUMPTIONS.
"""
import math
import time

TICK = 0.25
POINT_VALUE = 2.0
BAR = 900


# ---------------- New York time without tzdata (US DST rules since 2007)
def _nth_sunday(year, month, n):
    first = time.gmtime(time.mktime((year, month, 1, 12, 0, 0, 0, 0, 0)) - time.timezone)
    wd = first.tm_wday  # Monday = 0
    day = 1 + ((6 - wd) % 7) + 7 * (n - 1)
    return day


def ny_offset_hours(t):
    """UTC offset of New York for UTC epoch t: -4 during daylight time, else -5."""
    y = time.gmtime(t).tm_year
    start_day = _nth_sunday(y, 3, 2)   # second Sunday of March, 2:00 local standard time (= 07:00 UTC)
    end_day = _nth_sunday(y, 11, 1)    # first Sunday of November, 2:00 local daylight time (= 06:00 UTC)
    start = _utc(y, 3, start_day, 7)
    end = _utc(y, 11, end_day, 6)
    return -4 if start <= t < end else -5


def _utc(y, mo, d, h):
    import calendar
    return calendar.timegm((y, mo, d, h, 0, 0))


def ny_parts(t):
    lt = time.gmtime(t + 3600 * ny_offset_hours(t))
    return lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, lt.tm_min


def ceil_tick(x):
    return math.ceil(round(x / TICK, 9)) * TICK


def floor_tick(x):
    return math.floor(round(x / TICK, 9)) * TICK


# ---------------- indicators used by the filters
def ema(xs, n):
    out, e, k = [None] * len(xs), None, 2 / (n + 1)
    for i, x in enumerate(xs):
        if i < n - 1:
            continue
        e = sum(xs[i - n + 1:i + 1]) / n if e is None else x * k + e * (1 - k)
        out[i] = e
    return out


def adx(h, l, c, n=14):
    """Wilder's ADX."""
    L = len(c)
    out = [None] * L
    if L < 2 * n + 1:
        return out
    tr, pdm, mdm = [0.0] * L, [0.0] * L, [0.0] * L
    for i in range(1, L):
        up, dn = h[i] - h[i - 1], l[i - 1] - l[i]
        pdm[i] = up if up > dn and up > 0 else 0.0
        mdm[i] = dn if dn > up and dn > 0 else 0.0
        tr[i] = max(h[i] - l[i], abs(h[i] - c[i - 1]), abs(l[i] - c[i - 1]))
    atr, sp, sm = sum(tr[1:n + 1]), sum(pdm[1:n + 1]), sum(mdm[1:n + 1])
    dxs = []
    for i in range(n + 1, L):
        atr = atr - atr / n + tr[i]
        sp = sp - sp / n + pdm[i]
        sm = sm - sm / n + mdm[i]
        pdi, mdi = 100 * sp / atr if atr else 0, 100 * sm / atr if atr else 0
        dx = 100 * abs(pdi - mdi) / (pdi + mdi) if (pdi + mdi) else 0
        dxs.append(dx)
        if len(dxs) == n:
            a = sum(dxs) / n
            out[i] = a
        elif len(dxs) > n:
            a = (out[i - 1] * (n - 1) + dx) / n
            out[i] = a
    return out


# ---------------- simulator
DEFAULTS = {"target_r": 0.5, "cutoff_hour": 12, "body_rule": False, "filters": "",
            "c_lo": 10.0, "c_hi": 90.0, "c_lookback": 60, "d_max_gap_pct": 1.0, "e_min": 20.0,
            "commission": 0.62, "slip_ticks": 1}


def simulate(bars, **params):
    """bars: list of (t_open_utc, o, h, l, c, v) 15-minute bars, oldest first. Returns trades + stats."""
    p = dict(DEFAULTS)
    p.update(params)
    fs = set(p["filters"])
    t = [b[0] for b in bars]
    o = [b[1] for b in bars]
    h = [b[2] for b in bars]
    lo = [b[3] for b in bars]
    c = [b[4] for b in bars]
    v = [b[5] for b in bars]
    ny = [ny_parts(x) for x in t]
    # 1h EMAs from completed hours only (value known at the end of the hour)
    hourly_close, hour_end_index = [], {}
    for i, x in enumerate(t):
        if (x + BAR) % 3600 == 0:
            hourly_close.append(c[i])
            hour_end_index[i] = len(hourly_close) - 1
    e50, e200 = ema(hourly_close, 50), ema(hourly_close, 200)
    adx_v = adx(h, lo, c, 14)
    trades, rejected = [], {k: 0 for k in "ABCDE"}
    widths = []
    state = {}
    last_h_idx = None
    prev_rth_close = None
    pos = None
    for i in range(len(bars)):
        y, mo, d, hh, mm = ny[i]
        day = (y, mo, d)
        if state.get("day") != day:
            state = {"day": day, "range": None, "traded": False, "rth_open": None, "pv": 0.0, "vol": 0.0}
        if i in hour_end_index:
            last_h_idx = hour_end_index[i]
        # ----- manage an open position on this bar (entry happened at this bar's open or earlier)
        if pos is not None:
            closed = None
            if pos["side"] == 1:
                if o[i] <= pos["stop"] and i > pos["i"]:
                    closed = (o[i], "stop_gap")
                elif lo[i] <= pos["stop"]:
                    closed = (pos["stop"], "stop")
                elif h[i] >= pos["target"]:
                    closed = (pos["target"], "target")
            else:
                if o[i] >= pos["stop"] and i > pos["i"]:
                    closed = (o[i], "stop_gap")
                elif h[i] >= pos["stop"]:
                    closed = (pos["stop"], "stop")
                elif lo[i] <= pos["target"]:
                    closed = (pos["target"], "target")
            if closed is None and (hh, mm) == (15, 45):
                closed = (o[i], "flatten_1545")
            if closed is not None:
                px = closed[0] - pos["side"] * p["slip_ticks"] * TICK
                pts = pos["side"] * (px - pos["fill"])
                cost = 2 * p["commission"]
                pnl = pts * POINT_VALUE - cost
                risk = pos["r_pts"] * POINT_VALUE
                trades.append(dict(pos, exit=px, why=closed[1], t1=t[i], pnl=pnl, R=pnl / risk if risk else 0))
                pos = None
        # ----- session VWAP from 9:30
        if (hh, mm) == (9, 30):
            state["rth_open"] = o[i]
        if state["rth_open"] is not None and hh < 16:
            tp = (h[i] + lo[i] + c[i]) / 3
            state["pv"] += tp * v[i]
            state["vol"] += v[i]
        vwap = state["pv"] / state["vol"] if state["vol"] > 0 else None
        # ----- range bar closes at 9:30
        if (hh, mm) == (9, 15):
            state["range"] = (h[i], lo[i])
            continue
        rng = state["range"]
        end_min = hh * 60 + mm + 15  # this bar closes at end_min; the order fills at that minute
        if (rng and not state["traded"] and pos is None and (hh, mm) >= (9, 30)
                and end_min < p["cutoff_hour"] * 60 and i + 1 < len(bars)):
            hi_, lo_ = rng
            up = (min(o[i], c[i]) > hi_) if p["body_rule"] else c[i] > hi_
            dn = (max(o[i], c[i]) < lo_) if p["body_rule"] else c[i] < lo_
            side = 1 if up else -1 if dn else 0
            if side:
                width = hi_ - lo_
                gap = (100 * (state["rth_open"] - prev_rth_close) / prev_rth_close
                       if state["rth_open"] and prev_rth_close else None)
                hist = widths[-p["c_lookback"]:]
                checks = [
                    ("A", "A" not in fs or (last_h_idx is not None and e50[last_h_idx] is not None
                                            and e200[last_h_idx] is not None
                                            and (e50[last_h_idx] > e200[last_h_idx]) == (side == 1))),
                    ("B", "B" not in fs or (vwap is not None and ((c[i] > vwap) if side == 1 else (c[i] < vwap)))),
                    ("C", "C" not in fs or (len(hist) >= 20 and _pct(hist, p["c_lo"]) <= width <= _pct(hist, p["c_hi"]))),
                    ("D", "D" not in fs or (gap is not None and abs(gap) <= p["d_max_gap_pct"])),
                    ("E", "E" not in fs or (adx_v[i] is not None and adx_v[i] >= p["e_min"])),
                ]
                bad = [k for k, ok in checks if not ok]
                if bad:
                    rejected[bad[0]] += 1
                else:
                    fill = o[i + 1] + side * p["slip_ticks"] * TICK
                    stop = lo[i] if side == 1 else h[i]
                    if (side == 1 and fill <= stop) or (side == -1 and fill >= stop):
                        state["traded"] = True  # gap invalidated the stop: no position; session done (Pine parity)
                    else:
                        r_pts = abs(fill - stop)
                        tgt = ceil_tick(fill + p["target_r"] * r_pts) if side == 1 else floor_tick(fill - p["target_r"] * r_pts)
                        pos = {"side": side, "fill": fill, "stop": stop, "target": tgt, "r_pts": r_pts,
                               "t0": t[i + 1], "i": i + 1, "day": "%04d-%02d-%02d" % day}
                        state["traded"] = True
        if (hh, mm) == (15, 45):
            prev_rth_close = c[i]
            if rng:
                widths.append(rng[0] - rng[1])
    n = len(trades)
    wins = sum(1 for x in trades if x["pnl"] > 0)
    return {"trades": trades, "rejected": rejected, "n": n, "win_rate": wins / n if n else None,
            "net_pnl": sum(x["pnl"] for x in trades), "avg_R": sum(x["R"] for x in trades) / n if n else None,
            "breakeven_win_rate_before_costs": 1 / (1 + p["target_r"])}


def _pct(xs, q):
    s = sorted(xs)
    k = (len(s) - 1) * q / 100.0
    a, b = int(math.floor(k)), int(math.ceil(k))
    return s[a] + (s[b] - s[a]) * (k - a)


MODELS = [("baseline", ""), ("A: 1h EMA trend", "A"), ("B: session VWAP", "B"), ("C: range width", "C"),
          ("D: overnight gap", "D"), ("E: ADX(14)", "E")]


if __name__ == "__main__":
    print("Historical MNQ tests PENDING: no licensed CME 15-minute MNQ data in this repository.")
    print("Registered models:", [m[0] for m in MODELS], "x target R in (0.5, 0.75, 1.0) = 18 trials")
