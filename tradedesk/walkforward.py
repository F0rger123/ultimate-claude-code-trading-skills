"""Walk-forward: choose parameters on a training window, score them on the next unseen window.

Each parameter set runs once over the whole history; windows then pick trades by entry time.
Only the out-of-sample (OOS) trades count toward the ladder.
"""
import math

from . import backtest as B

DAY = 86400


def score(trades, min_trades=15):
    """Training score: mean R times sqrt(n), so a few lucky trades can't win."""
    if len(trades) < min_trades:
        return -1e9
    rs = [t["R"] for t in trades]
    return (sum(rs) / len(rs)) * math.sqrt(len(rs))


def walk_forward(strat_cls, mkt, train_days=180, test_days=60, costs=None, entry_filter=None,
                 log=None):
    combos = list(strat_cls.combos()) or [{}]
    runs = []
    for p in combos:
        s = strat_cls(mkt, **p)
        runs.append((p, B.run(s, costs=costs, entry_filter=entry_filter)))
        if log:
            log("  %s %s -> %d trades" % (strat_cls.id, p, len(runs[-1][1])))
    t_start, t_end = mkt.b.t[0], mkt.b.t[-1]
    windows = []
    oos = []
    t = t_start + train_days * DAY
    while t + test_days * DAY <= t_end + DAY:
        tr0, te0, te1 = t - train_days * DAY, t, t + test_days * DAY
        best, best_s = None, -1e18
        for p, trades in runs:
            s = score([x for x in trades if tr0 <= x["t0"] < te0])
            if s > best_s:
                best, best_s = (p, trades), s
        test = [x for x in best[1] if te0 <= x["t0"] < te1] if best_s > -1e9 else []
        r = sum(x["R"] for x in test)
        windows.append({"train_start": tr0, "test_start": te0, "test_end": te1, "params": best[0],
                        "train_score": best_s, "test_trades": len(test), "test_R": r})
        oos.extend(test)
        t += test_days * DAY
    full = max(runs, key=lambda pr: score(pr[1]))
    return {"strategy": strat_cls.id, "oos": oos, "windows": windows, "combos": len(combos),
            "in_sample_best": {"params": full[0], "trades": len(full[1]),
                               "avg_R": (sum(x["R"] for x in full[1]) / len(full[1])) if full[1] else 0.0},
            "latest_params": windows[-1]["params"] if windows else full[0]}
