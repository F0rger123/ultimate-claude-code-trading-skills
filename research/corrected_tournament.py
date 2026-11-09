"""Corrected tournament: shared mark-to-market portfolio ledger, leak-free walk-forward, honest stats.

    python research/corrected_tournament.py            # all candidates, spot and perp
    python research/corrected_tournament.py --quick    # fewer stress runs

Walk-forward: rolling 1,095-day training, 180-day non-overlapping out-of-sample (OOS) windows.
Parameter choice per window uses ONLY trades that entered AND exited inside the training window
(a trade still open at the boundary would leak future prices). The OOS equity curve is one continuous
ledger that starts at the first OOS day; the parameter set allowed to open trades switches at each
window boundary; positions opened earlier are managed by the variant that opened them.

Outputs: reports/corrected/*.json, reports/corrected/summary.md, evidence/experiment-registry/registry.jsonl
Every number in summary.md comes from this script. Labels: VERIFIED RUN = real Coinbase data, this code.
"""
import argparse
import hashlib
import itertools
import json
import math
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tradedesk import candidates as C  # noqa: E402
from tradedesk import data as D  # noqa: E402
from tradedesk import metrics as M  # noqa: E402
from tradedesk import portfolio as P  # noqa: E402
from tradedesk import strategies as S  # noqa: E402
from tradedesk.market import Market  # noqa: E402

DAY = 86400
TRAIN, TEST = 1095, 180
SYMS = ["BTC", "ETH", "SOL"]
RISK = 0.01
PERP_FUNDING_ASSUMED = 0.00001  # 0.001%/h, longs pay; ASSUMPTION (no historical CFM funding series)


def combos(grid):
    keys = sorted(grid)
    return [dict(zip(keys, v)) for v in itertools.product(*[grid[k] for k in keys])] or [{}]


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def commit():
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def cfg_for(mode, cost_mult=1.0, risk=RISK, dd_policy=False, spot_taker=0.009):
    if mode == "spot":
        return P.Config("spot", risk=risk, pos_lev=1.0, gross_lev=1.0, cost_mult=cost_mult,
                        costs={"taker": spot_taker}, dd_policy=dd_policy)
    return P.Config("perp", risk=risk, pos_lev=1.5, gross_lev=1.5, cost_mult=cost_mult,
                    funding_per_h=PERP_FUNDING_ASSUMED * cost_mult, dd_policy=dd_policy)


def build(markets, cls, params_list, extra=None):
    out = {}
    coord = {}
    for s, m in markets.items():
        vs = []
        for k, p in enumerate(params_list):
            if cls is C.WeeklyStrengthRotation:
                key = p.get("lookback", 90)
                if key not in coord:
                    coord[key] = C.RotationCoordinator(markets, key)
                vs.append(cls(m, coordinator=coord[key], **dict(extra or {}, **p)))
            else:
                vs.append(cls(m, **dict(extra or {}, **p)))
        out[s] = vs
    return out


def score(trades, a, b, min_trades=8):
    tr = [t for t in trades if a <= t["t0"] and t["t1"] < b]  # closed inside the window: no leakage
    if len(tr) < min_trades:
        return None
    rs = [t["R"] for t in tr]
    return sum(rs) / len(rs) * math.sqrt(len(rs))


def windows(t0, t1):
    out, t = [], t0 + TRAIN * DAY
    while t + TEST * DAY <= t1:
        out.append((t - TRAIN * DAY, t, t + TEST * DAY))
        t += TEST * DAY
    return out


def evaluate(name, cls, grid, markets, mode, extra=None, quick=False, log=print):
    plist = combos(grid)
    variants = build(markets, cls, plist, extra)
    t_start = min(m.b.t[0] for m in markets.values())
    t_end = max(m.b.t[-1] for m in markets.values())
    full = []
    for k, p in enumerate(plist):
        r = P.run(markets, variants, cfg_for(mode), active=lambda t, k=k: k)
        full.append(r)
    wins = windows(t_start, t_end)
    if not wins:
        return None
    sel = []
    for a, b, c in wins:
        scores = [score(full[k]["trades"], a, b) for k in range(len(plist))]
        best = max((x for x in enumerate(scores) if x[1] is not None), key=lambda x: x[1], default=None)
        sel.append((b, c, best[0] if best else None, best[1] if best else None))

    def active(t):
        for b, c, k, _ in sel:
            if b <= t < c:
                return k
        return None

    oos0, oos1 = wins[0][1], wins[-1][2]
    res = {"name": name, "id": cls.id, "mode": mode, "trials": len(plist), "grid": grid, "extra": extra or {},
           "oos_start": oos0, "oos_end": oos1, "windows": [], "stress": {}}
    base = P.run(markets, variants, cfg_for(mode), start_t=oos0, end_t=oos1, active=active)
    res["curve_stats"] = M.curve_stats(base["curve"])
    res["trade_stats"] = M.trade_stats(base["trades"], base["curve"])
    res["bootstrap"] = M.block_bootstrap(base["curve"])
    trial_srs = []
    for r in full:
        cs = M.curve_stats([x for x in r["curve"] if oos0 <= x[0] < oos1])
        trial_srs.append(cs.get("daily_sharpe", 0.0))
    res["neighborhood"] = []
    for k, r in enumerate(full):
        part = [x for x in r["curve"] if oos0 <= x[0] < oos1]
        cs = M.curve_stats(part)
        tr = [t for t in r["trades"] if oos0 <= t["t0"] < oos1]
        ts = M.trade_stats(tr)
        res["neighborhood"].append({"params": plist[k], "cagr": cs.get("cagr"), "sharpe": cs.get("sharpe"),
                                    "max_dd": cs.get("max_dd_daily"), "trades": ts.get("trades"),
                                    "pf": ts.get("profit_factor")})
    res["dsr"] = M.deflated_sharpe(base["curve"], len(plist), trial_srs)
    for (a, b, k, sc) in sel:
        part = [x for x in base["curve"] if a <= x[0] < b]
        wr = (part[-1][1] / part[0][1] - 1) if len(part) > 1 else 0.0
        res["windows"].append({"test_start": a, "test_end": b, "params": plist[k] if k is not None else None,
                               "train_score": sc, "return": wr,
                               "trades": sum(1 for t in base["trades"] if a <= t["t0"] < b)})
    syms = sorted(markets)
    bh = M.buy_hold_curve(markets, syms, oos0, oos1, fee=0.009)
    res["bench_equal_weight"] = M.curve_stats(bh)
    res["bench_btc"] = M.curve_stats(M.buy_hold_curve(markets, ["BTC"], oos0, oos1, fee=0.009))
    sd = (res["curve_stats"].get("daily_sharpe") and res["curve_stats"]) or {}
    days, eq = M.daily(base["curve"])
    rr = M.rets(eq)
    if len(rr) > 2:
        mu = sum(rr) / len(rr)
        vol = math.sqrt(sum((x - mu) ** 2 for x in rr) / (len(rr) - 1))
        res["bench_risk_matched"] = M.curve_stats(M.risk_matched(bh, vol))
    if not quick:
        for mult in (2.0, 3.0):
            r = P.run(markets, variants, cfg_for(mode, cost_mult=mult), start_t=oos0, end_t=oos1, active=active)
            res["stress"]["costs_x%g" % mult] = M.curve_stats(r["curve"])
        r = P.run(markets, variants, cfg_for(mode, dd_policy=True), start_t=oos0, end_t=oos1, active=active)
        res["stress"]["dd_policy_7.5_10_15"] = M.curve_stats(r["curve"])
        res["stress"]["dd_policy_events"] = [e for e in r["events"] if e[1] in ("halt", "block", "resume")][:20]
        if mode == "spot":
            r = P.run(markets, variants, cfg_for(mode, spot_taker=0.006), start_t=oos0, end_t=oos1, active=active)
            res["stress"]["spot_taker_0.60pct"] = M.curve_stats(r["curve"])
        r = P.run(markets, variants, cfg_for(mode, risk=0.005), start_t=oos0, end_t=oos1, active=active)
        res["stress"]["risk_0.5pct"] = M.curve_stats(r["curve"])
    res["skips"] = sum(1 for e in base["events"] if e[1] == "skip")
    res["daily_equity"] = [[d, round(e, 2)] for d, e in zip(*M.daily(base["curve"]))]
    res["trades"] = [{k: v for k, v in t.items() if k != "feat"} for t in base["trades"]]
    cs, ts = res["curve_stats"], res["trade_stats"]
    log("%-34s %-4s trials %2d  OOS %s..%s  trades %3s  CAGR %+6.1f%%  Sharpe %5.2f  maxDD %5.1f%%  PF %s  DSR %s" % (
        name, mode, len(plist), time.strftime("%Y-%m", time.gmtime(oos0)), time.strftime("%Y-%m", time.gmtime(oos1)),
        ts.get("trades"), 100 * cs.get("cagr", 0), cs.get("sharpe", 0), 100 * cs.get("max_dd_daily", 0),
        "%.2f" % ts["profit_factor"] if ts.get("trades") else "-",
        "%.2f" % res["dsr"]["dsr"] if res["dsr"].get("dsr") is not None else "-"))
    return res


CANDIDATES = [
    # name, class, grid, extra, modes
    ("control: trend_ensemble (unchanged)", S.TrendEnsemble, {}, {}, ("spot", "perp")),
    ("vol_managed_trend", C.VolManagedTrend, C.VolManagedTrend.grid, {}, ("spot", "perp")),
    ("vol_managed_trend + halve-in-high-vol", C.VolManagedTrend, C.VolManagedTrend.grid, {"halve_high_vol": 1},
     ("spot", "perp")),
    ("vol_filtered_breakout", C.VolFilteredBreakout, C.VolFilteredBreakout.grid, {}, ("spot", "perp")),
    ("breakout, unfiltered baseline", C.VolFilteredBreakout, {"n": [20, 55], "stop_atr": [2.5, 3.0]},
     {"vol_cap": 1.0}, ("spot", "perp")),
    ("weekly_strength_rotation", C.WeeklyStrengthRotation, C.WeeklyStrengthRotation.grid, {}, ("spot",)),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    t0 = time.time()
    markets, hashes = {}, {}
    for s in SYMS:
        path = D.cache_path(os.path.join(ROOT, "data"), D.PERPS[s]["spot"], 3600)
        markets[s] = Market(D.load(path), s, 3600)
        hashes[s] = {"file": os.path.basename(path), "sha256_16": sha(path), "bars": len(markets[s].b.t),
                     "first": markets[s].b.t[0], "last": markets[s].b.t[-1]}
    out_dir = os.path.join(ROOT, "reports", "corrected")
    reg_dir = os.path.join(ROOT, "evidence", "experiment-registry")
    os.makedirs(out_dir, exist_ok=True)
    os.makedirs(reg_dir, exist_ok=True)
    results = []
    for name, cls, grid, extra, modes in CANDIDATES:
        if a.only and a.only not in name:
            continue
        for mode in modes:
            r = evaluate(name, cls, grid, markets, mode, extra, a.quick)
            if r is None:
                continue
            fn = "%s-%s%s.json" % (cls.id, mode, "-halve" if extra.get("halve_high_vol") else
                                   "-unfiltered" if extra.get("vol_cap") == 1.0 else "")
            with open(os.path.join(out_dir, fn), "w", encoding="utf-8") as f:
                json.dump(r, f, indent=1, default=str)
            r["file"] = fn
            results.append(r)
            with open(os.path.join(reg_dir, "registry.jsonl"), "a", encoding="utf-8") as f:
                f.write(json.dumps({
                    "t": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "commit": commit(),
                    "experiment": name, "strategy": cls.id, "mode": mode, "trials": r["trials"], "grid": grid,
                    "extra": extra, "train_days": TRAIN, "test_days": TEST, "oos_start": r["oos_start"],
                    "oos_end": r["oos_end"], "risk": RISK, "costs": cfg_for(mode).costs,
                    "funding_per_h": cfg_for(mode).funding_per_h, "funding_is_assumption": mode == "perp",
                    "data": hashes, "label": "VERIFIED RUN",
                    "command": "python research/corrected_tournament.py" + (" --quick" if a.quick else ""),
                    "result_file": "reports/corrected/" + fn}) + "\n")
    with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in r.items() if k not in ("trades", "daily_equity")} for r in results], f,
                  indent=1, default=str)
    print("done in %.0fs" % (time.time() - t0))


if __name__ == "__main__":
    main()
