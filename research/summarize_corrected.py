"""Builds reports/corrected/summary.md from the JSON written by research/corrected_tournament.py.

The deflated Sharpe ratio here counts EVERY registered trial across all families (not just one family),
which is the honest denominator for "best of everything we tried".
    python research/summarize_corrected.py
"""
import glob
import json
import math
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tradedesk import metrics as M  # noqa: E402

DIR = os.path.join(ROOT, "reports", "corrected")


def pct(x, d=1):
    return "-" if x is None else ("%+." + str(d) + "f%%") % (100 * x)


def dd(x):
    return "-" if x is None else "%.1f%%" % (100 * x)


def num(x, d=2):
    return "-" if x is None or (isinstance(x, float) and math.isinf(x)) else ("%." + str(d) + "f") % x


def main():
    rows = []
    for fn in sorted(glob.glob(os.path.join(DIR, "*.json"))):
        if fn.endswith(("summary.json", "ranking.json")):
            continue
        with open(fn, encoding="utf-8") as f:
            r = json.load(f)
        r["file"] = os.path.basename(fn)
        rows.append(r)
    n_total = sum(r["trials"] for r in rows)
    trial_daily = [n.get("sharpe", 0) / math.sqrt(365) for r in rows for n in r["neighborhood"] if n.get("sharpe") is not None]
    for r in rows:
        curve = [(d * 86400, e) for d, e in r["daily_equity"]]
        r["dsr_all"] = M.deflated_sharpe(curve, n_total, trial_daily).get("dsr")
    rows.sort(key=lambda r: -(r["curve_stats"].get("sharpe") or -9))
    o0 = time.strftime("%Y-%m-%d", time.gmtime(rows[0]["oos_start"]))
    o1 = time.strftime("%Y-%m-%d", time.gmtime(rows[0]["oos_end"]))
    L = ["# Corrected tournament: ranked results", "",
         "Label: **VERIFIED RUN**: real Coinbase spot hourly data (BTC and ETH from 2018-12-29, SOL from 2021-06-17), "
         "this repository's code. Reproduce: `python research/corrected_tournament.py && python research/summarize_corrected.py`.",
         "",
         "- **Engine:** shared mark-to-market ledger. Risk 1% of marked equity per trade at the stop. Next-bar-open "
         "market fills, stop-first, gap fills at open.",
         "- **Spot:** long-only, no leverage, 0.90% taker per side + 0.05% slippage (assumed 2026 entry tier, unverified).",
         "- **Perp:** long/short, effective leverage <= 1.5x, whole contracts, 0.06% + 0.02% per side, funding "
         "**ASSUMED** at 0.001%/h against longs (no historical CFM funding data).",
         "- **Walk-forward:** 1,095-day train / 180-day non-overlapping OOS, with parameters picked only from trades "
         "closed inside the training window. Continuous OOS ledger %s to %s. The last partial window "
         "(about 5 months) is not scored." % (o0, o1),
         "- **Trials registered:** %d in total. DSR (all) = deflated Sharpe probability against all %d trials. "
         "Bootstrap = 10-day block bootstrap, 5th percentile CAGR." % (n_total, n_total),
         "",
         "| Rank | Strategy | Market | Trials | OOS trades | CAGR | Sharpe | Max DD (daily) | Max DD (hourly) | PF | Fees | Bootstrap CAGR p5 | DSR (all) | Costs x3 CAGR | Verdict |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for k, r in enumerate(rows, 1):
        cs, ts, bs = r["curve_stats"], r["trade_stats"], r["bootstrap"]
        x3 = r["stress"].get("costs_x3", {})
        verdict = verdict_for(r, cs, ts, bs, x3)
        r["verdict"] = verdict
        L.append("| %d | %s | %s | %d | %s | %s | %s | %s | %s | %s | $%s | %s | %s | %s | %s |" % (
            k, r["name"], r["mode"], r["trials"], ts.get("trades", 0), pct(cs.get("cagr")), num(cs.get("sharpe")),
            dd(cs.get("max_dd_daily")), dd(cs.get("max_dd_intraday")), num(ts.get("profit_factor")),
            num(ts.get("fees", 0), 0), pct(bs.get("cagr_p5")), num(r["dsr_all"]), pct(x3.get("cagr")), verdict))
    b = rows[0]
    L += ["", "## Benchmarks over the same OOS period (bought once, one 0.90% fee)", "",
          "| Benchmark | CAGR | Sharpe | Max DD |", "|---|---|---|---|"]
    for name, key in (("Buy-and-hold BTC", "bench_btc"), ("Buy-and-hold equal weight BTC/ETH/SOL", "bench_equal_weight")):
        s = b[key]
        L.append("| %s | %s | %s | %s |" % (name, pct(s.get("cagr")), num(s.get("sharpe")), dd(s.get("max_dd_daily"))))
    L += ["", "Risk-matched buy-and-hold (equal weight scaled to each strategy's own volatility, rest in cash):", "",
          "| Strategy | Market | Strategy CAGR | Risk-matched B&H CAGR | Strategy max DD | Risk-matched B&H max DD |",
          "|---|---|---|---|---|---|"]
    for r in rows:
        rm = r.get("bench_risk_matched", {})
        L.append("| %s | %s | %s | %s | %s | %s |" % (r["name"], r["mode"], pct(r["curve_stats"].get("cagr")),
                                                   pct(rm.get("cagr")), dd(r["curve_stats"].get("max_dd_daily")),
                                                   dd(rm.get("max_dd_daily"))))
    L += ["", "## Stress tests (same OOS ledger)", "",
          "| Strategy | Market | Base CAGR | Costs x2 | Costs x3 | Risk 0.5% CAGR / DD | Owner DD tiers (7.5/10/15%) CAGR / DD | Spot at 0.60% taker |",
          "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        st, cs = r["stress"], r["curve_stats"]
        L.append("| %s | %s | %s | %s | %s | %s / %s | %s / %s | %s |" % (
            r["name"], r["mode"], pct(cs.get("cagr")), pct(st.get("costs_x2", {}).get("cagr")),
            pct(st.get("costs_x3", {}).get("cagr")), pct(st.get("risk_0.5pct", {}).get("cagr")),
            dd(st.get("risk_0.5pct", {}).get("max_dd_daily")), pct(st.get("dd_policy_7.5_10_15", {}).get("cagr")),
            dd(st.get("dd_policy_7.5_10_15", {}).get("max_dd_daily")), pct(st.get("spot_taker_0.60pct", {}).get("cagr"))))
    L += ["", "## Parameter neighborhoods (each fixed parameter set over the whole OOS span, no selection)", ""]
    for r in rows:
        if r["trials"] <= 1:
            continue
        cg = [n["cagr"] for n in r["neighborhood"] if n.get("cagr") is not None]
        pos = sum(1 for x in cg if x > 0)
        L.append("- **%s (%s):** %d of %d parameter sets positive; CAGR range %s to %s." % (
            r["name"], r["mode"], pos, len(cg), pct(min(cg)), pct(max(cg))))
    L += ["", "## Out-of-sample windows (the best candidate)", ""]
    best = rows[0]
    L.append("Strategy: %s (%s)." % (best["name"], best["mode"]))
    L.append("")
    L.append("| Test window | Params chosen on training | Trades | Return |")
    L.append("|---|---|---|---|")
    for w in best["windows"]:
        L.append("| %s to %s | %s | %d | %s |" % (time.strftime("%Y-%m-%d", time.gmtime(w["test_start"])),
                                              time.strftime("%Y-%m-%d", time.gmtime(w["test_end"])),
                                              json.dumps(w["params"]), w["trades"], pct(w["return"])))
    L += ["", "Generated %s UTC." % time.strftime("%Y-%m-%d %H:%M", time.gmtime())]
    with open(os.path.join(DIR, "summary.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    with open(os.path.join(DIR, "ranking.json"), "w", encoding="utf-8") as f:
        json.dump([{"name": r["name"], "mode": r["mode"], "trials": r["trials"], "verdict": r["verdict"],
                    "cagr": r["curve_stats"].get("cagr"), "sharpe": r["curve_stats"].get("sharpe"),
                    "max_dd": r["curve_stats"].get("max_dd_daily"), "dsr_all": r["dsr_all"],
                    "trades": r["trade_stats"].get("trades")} for r in rows], f, indent=1)
    print("\n".join(L[:len(rows) + 14]))


def verdict_for(r, cs, ts, bs, x3):
    if (ts.get("trades") or 0) < 60:
        return "INSUFFICIENT EVIDENCE (trades)"
    if (cs.get("sharpe") or 0) <= 0:
        return "REJECT"
    if r["dsr_all"] is None or r["dsr_all"] < 0.95 or (bs.get("cagr_p5") or -1) <= 0:
        return "PAPER CANDIDATE: not statistically proven"
    if (x3.get("cagr") or -1) <= 0:
        return "COST-FRAGILE"
    return "PAPER PRIORITY"


if __name__ == "__main__":
    main()
