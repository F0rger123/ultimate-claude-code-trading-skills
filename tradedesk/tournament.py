"""Run every strategy on every symbol through walk-forward, apply the backtest gate, write a
Markdown report and update the ladder."""
import json
import os
import time

from . import backtest as B
from . import data as D
from . import risk as RK
from . import ladder as L
from . import strategies as S
from . import walkforward as W
from .market import Market


def run(data_dir="data", out_dir="reports", state_dir="state", symbols=("BTC", "ETH", "SOL"),
        strategy_ids=None, risk=0.01, max_lev=None, log=print, base=300, train_days=180, test_days=60,
        tag="latest", min_train_trades=15):
    results = []
    lad = L.Ladder(os.path.join(state_dir, "ladder.json"))
    strats = [S.BY_ID[x] for x in strategy_ids] if strategy_ids else S.ALL
    for sym in symbols:
        path = D.cache_path(data_dir, D.PERPS[sym]["spot"], base)
        if not os.path.exists(path):
            log("no data for %s at %s (run: python -m tradedesk data)" % (sym, path))
            continue
        bars = D.load(path)
        mkt = Market(bars, sym, base)
        lev = max_lev or RK.lev_cap(RK.normalize({}), sym)  # same cap the live desk uses
        log("%s: %d bars, %s to %s" % (sym, len(bars), _d(bars[0][0]), _d(bars[-1][0])))
        for cls in strats:
            t0 = time.time()
            wf = W.walk_forward(cls, mkt, train_days, test_days, min_trades=min_train_trades)
            sim, curve = B.simulate(wf["oos"], risk=risk, max_lev=lev)
            m = B.metrics(sim, curve)
            m["sharpe"] = B.sharpe_daily(curve)
            mc = B.monte_carlo(wf["oos"], risk=risk, max_lev=lev)
            ok, checks = L.check_backtest(m, mc, wf["windows"])
            cur = lad.get(cls.id, sym)["stage"]
            near = (not ok and m.get("trades", 0) >= L.SHADOW["min_trades"]
                    and (m.get("profit_factor") or 0) >= L.SHADOW["min_pf"])
            if ok and cur in ("backtest", "shadow"):
                lad.set(cls.id, sym, "forward", "passed backtest gate", {"params": wf["latest_params"]})
            elif near and cur == "backtest":
                lad.set(cls.id, sym, "shadow", "near miss: forward-watch only, no money",
                        {"params": wf["latest_params"]})
            elif not near and not ok and cur == "shadow":
                lad.set(cls.id, sym, "backtest", "no longer a near miss")
            elif not ok and cur == "forward":
                lad.set(cls.id, sym, "backtest", "failed backtest gate on re-run")
            e = lad.get(cls.id, sym)
            e["backtest"] = {"oos_trades": m.get("trades", 0), "pf": _num(m.get("profit_factor")),
                             "avg_R": m.get("avg_R"), "max_dd": m.get("max_drawdown"),
                             "p95_dd": mc.get("p95_drawdown"), "params": wf["latest_params"],
                             "t": int(time.time())}
            lad.d[lad.key(cls.id, sym)] = e
            results.append({"symbol": sym, "strategy": cls.id, "name": cls.name, "source": cls.source,
                            "metrics": m, "mc": mc, "passed": ok, "checks": checks,
                            "windows": wf["windows"], "in_sample": wf["in_sample_best"],
                            "params": wf["latest_params"], "secs": round(time.time() - t0, 1)})
            log("  %-18s OOS %4d trades  PF %5s  avgR %+.3f  DD %5.1f%%  %s" % (
                cls.id, m.get("trades", 0), _fmt(m.get("profit_factor")), m.get("avg_R", 0),
                100 * m.get("max_drawdown", 0), "PASS" if ok else "fail"))
    lad.save()
    os.makedirs(out_dir, exist_ok=True)
    md = report(results, risk, max_lev, base, train_days, test_days)
    with open(os.path.join(out_dir, "tournament-%s.md" % tag), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(out_dir, "tournament-%s.json" % tag), "w", encoding="utf-8") as f:
        json.dump([{k: v for k, v in r.items() if k != "windows"} for r in results], f, indent=1,
                  default=str)
    return results


def _d(t):
    return time.strftime("%Y-%m-%d", time.gmtime(t))


def _num(x):
    return None if x is None or x == float("inf") else x


def _fmt(x):
    return "inf" if x == float("inf") else ("%.2f" % x if x is not None else "-")


def report(results, risk, max_lev, base=300, train_days=180, test_days=60):
    lines = ["# Strategy tournament", "",
             "Generated %s UTC. Out-of-sample (walk-forward: train %d days, test %d days) results only. Base bars: %d min." %
             (time.strftime("%Y-%m-%d %H:%M", time.gmtime()), train_days, test_days, base // 60),
             "Costs: 0.06%% fee and 0.02%% slippage per side, funding 0.001%%/hour. Sizing: %.1f%% risk per trade, "
             "leverage capped at %s. Data: Coinbase spot candles (perp history is too short), so "
             "perp basis and real funding are approximated." % (
                 100 * risk, ("%gx" % max_lev) if max_lev else "the live desk's per-coin cap (BTC 3.9x, ETH 3.3x, SOL 1.8x)"),
             "", "Not financial advice. Past results do not predict future results.", "",
             "| Symbol | Strategy | OOS trades | Win rate | Avg R | Profit factor | Return | Max DD | Bootstrap 5th-pct return | Gate |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for r in sorted(results, key=lambda x: -(x["metrics"].get("avg_R") or -9)):
        m, mc = r["metrics"], r["mc"]
        if not m.get("trades"):
            lines.append("| %s | %s | 0 | | | | | | | fail |" % (r["symbol"], r["strategy"]))
            continue
        lines.append("| %s | %s | %d | %.0f%% | %+.3f | %s | %+.1f%% | %.1f%% | %s | %s |" % (
            r["symbol"], r["strategy"], m["trades"], 100 * m["win_rate"], m["avg_R"], _fmt(m["profit_factor"]),
            100 * m.get("return", 0), 100 * m.get("max_drawdown", 0),
            ("%+.1f%%" % (100 * mc["p5_return"])) if mc.get("runs") else "n/a",
            "**PASS**" if r["passed"] else "fail"))
    lines += ["", "## Gate detail", ""]
    for r in results:
        lines.append("### %s / %s (%s)" % (r["symbol"], r["strategy"], r["name"]))
        lines.append("Idea source: %s. Latest parameters: `%s`. In-sample best (for comparison, not "
                     "used): %d trades, avg R %+.3f." % (r["source"], json.dumps(r["params"]),
                                                       r["in_sample"]["trades"], r["in_sample"]["avg_R"]))
        lines.append("")
        for name, ok, val in r["checks"]:
            lines.append("- [%s] %s: %s" % ("x" if ok else " ", name, val))
        lines.append("")
    return "\n".join(lines) + "\n"
