"""Candle data: download from Coinbase public endpoints (no key), cache as gzip CSV, resample.

A bar is a tuple (t, open, high, low, close, volume) with t = bar open time in UTC epoch seconds.
"""
import csv
import gzip
import json
import os
import time
import urllib.error
import urllib.request

UA = "tradedesk/0.1 (+https://github.com/F0rger123/ultimate-claude-code-trading-skills)"
SPOT_URL = "https://api.exchange.coinbase.com/products/%s/candles?granularity=%d&start=%s&end=%s"
PERP_URL = ("https://api.coinbase.com/api/v3/brokerage/market/products/%s/candles"
            "?granularity=%s&start=%d&end=%d&limit=300")
PERP_GRAN = {60: "ONE_MINUTE", 300: "FIVE_MINUTE", 900: "FIFTEEN_MINUTE", 1800: "THIRTY_MINUTE",
             3600: "ONE_HOUR", 7200: "TWO_HOUR", 21600: "SIX_HOUR", 86400: "ONE_DAY"}
SPOT_GRAN = (60, 300, 900, 3600, 21600, 86400)

# Backtests use spot history (perp history starts mid-2025); live and paper use the perp product.
PERPS = {
    "BTC": {"perp": "BIP-20DEC30-CDE", "spot": "BTC-USD", "contract": 0.01},
    "ETH": {"perp": "ETP-20DEC30-CDE", "spot": "ETH-USD", "contract": 0.1},
    "SOL": {"perp": "SLP-20DEC30-CDE", "spot": "SOL-USD", "contract": 5.0},
}


def _get(url, tries=5):
    last = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, ValueError) as e:
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError("download failed: %s (%s)" % (url, last))


def _iso(t):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t))


def fetch_spot(product, gran, start, end, sleep=0.12, progress=None):
    """Spot candles from the Coinbase Exchange API, oldest first."""
    if gran not in SPOT_GRAN:
        raise ValueError("spot granularity must be one of %s" % (SPOT_GRAN,))
    out = {}
    step = gran * 300
    t = start
    while t < end:
        t2 = min(end, t + step)
        rows = _get(SPOT_URL % (product, gran, _iso(t), _iso(t2)))
        if isinstance(rows, dict):
            raise RuntimeError("coinbase error: %s" % rows)
        for r in rows:  # [time, low, high, open, close, volume]
            out[int(r[0])] = (int(r[0]), float(r[3]), float(r[2]), float(r[1]), float(r[4]), float(r[5]))
        if progress:
            progress(t2, end)
        t = t2
        time.sleep(sleep)
    return [out[k] for k in sorted(out) if start <= k < end]


def fetch_perp(product, gran, start, end, sleep=0.12):
    """Perp candles from the Advanced Trade public market endpoint, oldest first."""
    g = PERP_GRAN[gran]
    out = {}
    step = gran * 300
    t = start
    while t < end:
        t2 = min(end, t + step)
        d = _get(PERP_URL % (product, g, t, t2))
        for c in d.get("candles", []):
            k = int(c["start"])
            out[k] = (k, float(c["open"]), float(c["high"]), float(c["low"]), float(c["close"]), float(c["volume"]))
        t = t2
        time.sleep(sleep)
    return [out[k] for k in sorted(out) if start <= k < end]


def cache_path(root, product, gran):
    return os.path.join(root, "%s-%ds.csv.gz" % (product, gran))


def save(path, bars):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with gzip.open(tmp, "wt", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "open", "high", "low", "close", "volume"])
        for b in bars:
            w.writerow(b)
    os.replace(tmp, path)


def load(path):
    bars = []
    with gzip.open(path, "rt", newline="") as f:
        r = csv.reader(f)
        next(r, None)
        for row in r:
            bars.append((int(row[0]), float(row[1]), float(row[2]), float(row[3]), float(row[4]), float(row[5])))
    return bars


def update_cache(root, product, gran=300, days=730, now=None, spot=True, log=print):
    """Download or extend the cached history for one product. Returns all cached bars."""
    now = int(now or time.time())
    end = now - now % gran
    path = cache_path(root, product, gran)
    bars = load(path) if os.path.exists(path) else []
    start = end - days * 86400
    if bars and bars[0][0] <= start + gran:
        start = bars[-1][0] + gran
    elif bars:
        bars = []  # asked for more history than cached: refetch the whole range
    if start < end:
        fetch = fetch_spot if spot else fetch_perp
        log("downloading %s %ds from %s" % (product, gran, _iso(start)))
        new = fetch(product, gran, start, end)
        merged = {b[0]: b for b in bars}
        merged.update({b[0]: b for b in new})
        bars = [merged[k] for k in sorted(merged)]
        save(path, bars)
    return bars


def resample(bars, gran):
    """Aggregate bars into gran-second bars aligned to UTC. Keeps only complete buckets."""
    if not bars:
        return []
    base = bars[1][0] - bars[0][0] if len(bars) > 1 else gran
    need = max(1, gran // base)
    out = []
    cur = None
    n = 0
    for t, o, h, l, c, v in bars:
        k = t - t % gran
        if cur is None or k != cur[0]:
            if cur is not None and n >= need:
                out.append(tuple(cur))
            cur = [k, o, h, l, c, v]
            n = 1
        else:
            cur[2] = max(cur[2], h)
            cur[3] = min(cur[3], l)
            cur[4] = c
            cur[5] += v
            n += 1
    if cur is not None and n >= need:
        out.append(tuple(cur))
    return out


def gaps(bars, gran):
    """Number of missing bars (Coinbase publishes nothing for intervals without trades)."""
    if len(bars) < 2:
        return 0
    return sum(max(0, (b[0] - a[0]) // gran - 1) for a, b in zip(bars, bars[1:]))
