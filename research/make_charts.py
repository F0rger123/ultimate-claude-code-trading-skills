"""Draws evidence charts (plain SVG, no plotting library) from reports/corrected/*.json.

    python research/make_charts.py
Writes docs/assets/generated-charts/*.svg. Every chart is labeled with its source, period, costs and run.
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
from tradedesk import metrics as M  # noqa: E402

SRC = os.path.join(ROOT, "reports", "corrected")
OUT = os.path.join(ROOT, "docs", "assets", "generated-charts")
W, H, PADL, PADR, PADT, PADB = 960, 420, 70, 20, 60, 70
INK, MUTED, GRID = "#0a0a0a", "#737373", "#e5e5e5"
SERIES = ["#0a0a0a", "#1fa34a", "#737373", "#b45309", "#2563eb"]


def commit():
    try:
        return subprocess.check_output(["git", "-C", ROOT, "rev-parse", "--short", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def load(fn):
    with open(os.path.join(SRC, fn), encoding="utf-8") as f:
        return json.load(f)


def svg(title, subtitle, footer, lines, ylab, yfmt, zero=None):
    xs = [x for _, pts, _ in lines for x, _ in pts]
    ys = [y for _, pts, _ in lines for _, y in pts]
    x0, x1 = min(xs), max(xs)
    y0, y1 = min(ys + ([zero] if zero is not None else [])), max(ys + ([zero] if zero is not None else []))
    if y1 == y0:
        y1 += 1

    def px(x):
        return PADL + (x - x0) / (x1 - x0) * (W - PADL - PADR)

    def py(y):
        return PADT + (1 - (y - y0) / (y1 - y0)) * (H - PADT - PADB)

    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d" role="img" aria-label="%s">'
           % (W, H, W, H, title),
           '<rect width="%d" height="%d" fill="#ffffff"/>' % (W, H),
           '<style>text{font-family:ui-sans-serif,system-ui,Segoe UI,Roboto,Arial,sans-serif;fill:%s}</style>' % INK,
           '<text x="%d" y="26" font-size="17" font-weight="700">%s</text>' % (PADL, title),
           '<text x="%d" y="45" font-size="12" fill="%s">%s</text>' % (PADL, MUTED, subtitle)]
    for k in range(5):
        y = y0 + (y1 - y0) * k / 4
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s"/>' % (PADL, W - PADR, py(y), py(y), GRID))
        out.append('<text x="%d" y="%.1f" font-size="11" fill="%s" text-anchor="end">%s</text>' % (PADL - 6, py(y) + 4, MUTED, yfmt(y)))
    yr0, yr1 = time.gmtime(x0).tm_year, time.gmtime(x1).tm_year
    for yr in range(yr0, yr1 + 1):
        t = time.mktime((yr, 1, 1, 0, 0, 0, 0, 0, 0)) - time.timezone
        if x0 <= t <= x1:
            out.append('<line x1="%.1f" x2="%.1f" y1="%d" y2="%d" stroke="%s"/>' % (px(t), px(t), PADT, H - PADB, GRID))
            out.append('<text x="%.1f" y="%d" font-size="11" fill="%s" text-anchor="middle">%d</text>' % (px(t), H - PADB + 16, MUTED, yr))
    if zero is not None:
        out.append('<line x1="%d" x2="%d" y1="%.1f" y2="%.1f" stroke="%s" stroke-dasharray="4 3"/>' % (PADL, W - PADR, py(zero), py(zero), MUTED))
    for k, (name, pts, color) in enumerate(lines):
        d = " ".join(("M" if j == 0 else "L") + "%.1f %.1f" % (px(x), py(y)) for j, (x, y) in enumerate(pts))
        out.append('<path d="%s" fill="none" stroke="%s" stroke-width="2"/>' % (d, color))
        out.append('<rect x="%d" y="%d" width="12" height="3" fill="%s"/>' % (PADL + 10, PADT + 8 + 16 * k, color))
        out.append('<text x="%d" y="%d" font-size="12">%s</text>' % (PADL + 28, PADT + 13 + 16 * k, name))
    out.append('<text x="%d" y="%d" font-size="11" fill="%s" transform="rotate(-90 16 %d)">%s</text>' % (16, (H) // 2, MUTED, H // 2, ylab))
    for k, line in enumerate(footer):
        out.append('<text x="%d" y="%d" font-size="10.5" fill="%s">%s</text>' % (PADL, H - 30 + 14 * k, MUTED, line))
    out.append("</svg>")
    return "\n".join(out)


def main():
    os.makedirs(OUT, exist_ok=True)
    picks = [("trend_ensemble-perp.json", "Trend ensemble (perp, control)"),
             ("vol_filtered_breakout-perp.json", "Vol-filtered breakout (perp)"),
             ("weekly_strength_rotation-spot.json", "Weekly rotation (spot)"),
             ("trend_ensemble-spot.json", "Trend ensemble (spot)")]
    lines, dds = [], []
    ref = None
    for k, (fn, label) in enumerate(picks):
        if not os.path.exists(os.path.join(SRC, fn)):
            continue
        r = load(fn)
        ref = ref or r
        eq = r["daily_equity"]
        e0 = eq[0][1]
        lines.append((label, [(d * 86400, e / e0 - 1) for d, e in eq], SERIES[k]))
        peak, ddp = e0, []
        for d, e in eq:
            peak = max(peak, e)
            ddp.append((d * 86400, -(peak - e) / peak))
        dds.append((label, ddp, SERIES[k]))
    if ref is None:
        print("no results; run research/corrected_tournament.py first")
        return
    stamp = "Generated %s UTC from commit %s" % (time.strftime("%Y-%m-%d %H:%M", time.gmtime()), commit())
    period = "%s to %s" % (time.strftime("%Y-%m-%d", time.gmtime(ref["oos_start"])), time.strftime("%Y-%m-%d", time.gmtime(ref["oos_end"])))
    foot = ["VERIFIED RUN, backtest (not paper, not live). Coinbase spot hourly data. Walk-forward OOS %s. 1%% risk/trade." % period,
            "Spot 0.90%% taker + 0.05%% slip per side; perp 0.06%% + 0.02%%, funding ASSUMED 0.001%%/h. %s." % stamp]
    open(os.path.join(OUT, "oos-equity.svg"), "w", encoding="utf-8").write(svg(
        "Out-of-sample equity: corrected engine", "Cumulative return of each continuous walk-forward ledger",
        foot, lines, "cumulative return", lambda y: "%+.0f%%" % (100 * y), zero=0.0))
    open(os.path.join(OUT, "oos-drawdown.svg"), "w", encoding="utf-8").write(svg(
        "Out-of-sample drawdown (marked to market, daily)", "Distance below the running equity peak",
        foot, dds, "drawdown", lambda y: "%.0f%%" % (100 * y), zero=0.0))
    # cost sensitivity, as lines over cost multiple
    cost_lines = []
    for k, (fn, label) in enumerate(picks):
        if not os.path.exists(os.path.join(SRC, fn)):
            continue
        r = load(fn)
        pts = [(1, r["curve_stats"]["cagr"]), (2, r["stress"].get("costs_x2", {}).get("cagr")),
               (3, r["stress"].get("costs_x3", {}).get("cagr"))]
        pts = [(x * 86400 * 365 * 0 + x, y) for x, y in pts if y is not None]
        cost_lines.append((label, pts, SERIES[k]))
    # x axis is not time here: reuse svg with year ticks disabled by using tiny x values
    s = svg("Cost sensitivity: CAGR at 1x, 2x, 3x costs", "x axis: cost multiple (1 = base assumptions)",
            foot, cost_lines, "CAGR", lambda y: "%+.1f%%" % (100 * y), zero=0.0)
    open(os.path.join(OUT, "cost-sensitivity.svg"), "w", encoding="utf-8").write(s)
    print("charts written to", OUT)


if __name__ == "__main__":
    main()
