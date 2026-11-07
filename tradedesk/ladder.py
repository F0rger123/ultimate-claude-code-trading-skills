"""The ladder: backtest -> forward -> paper -> small_live -> scaled, with the gates from
docs/BLUEPRINT.md section 8. Gates are pure functions so they can be tested and shown in the app."""
import json
import os
import time

STAGES = ["backtest", "forward", "paper", "small_live", "scaled"]

GATES = {
    "backtest": {"min_trades": 100, "min_pf": 1.20, "max_dd": 0.20, "min_win_windows": 0.60,
                 "mc_p5_return_gt": 0.0},
    "forward": {"min_days": 30, "min_trades": 30, "min_pf": 1.10, "min_expectancy_share": 0.5},
    "paper": {"min_days": 60, "or_min_trades": 100, "min_pf": 1.15, "max_dd": 0.10, "max_breaches": 0,
              "owner_unlock": True},
    "small_live": {"min_days": 90, "min_pf": 1.15, "max_slip_ratio": 1.5, "owner_approval": True},
}
DEMOTE = {"last_n": 50, "min_pf": 0.90}
# Near misses: failed the backtest gate but strong enough to watch on live data with no money.
# Shadow signals are journaled as forward tests; they never count toward promotion by themselves.
SHADOW = {"min_trades": 50, "min_pf": 1.30}


def check_backtest(m, mc, windows):
    g = GATES["backtest"]
    ww = [w for w in windows if w["test_trades"] > 0]
    win_share = (sum(1 for w in ww if w["test_R"] > 0) / len(ww)) if ww else 0.0
    checks = [
        ("OOS trades >= %d" % g["min_trades"], m.get("trades", 0) >= g["min_trades"], m.get("trades", 0)),
        ("profit factor >= %.2f" % g["min_pf"], m.get("profit_factor", 0) >= g["min_pf"],
         round(m.get("profit_factor", 0), 2)),
        ("max drawdown <= %d%% at 1%% risk" % (g["max_dd"] * 100), m.get("max_drawdown", 1) <= g["max_dd"],
         "%.1f%%" % (100 * m.get("max_drawdown", 1))),
        (">= %d%% of OOS windows profitable" % (g["min_win_windows"] * 100), win_share >= g["min_win_windows"],
         "%.0f%%" % (100 * win_share)),
        ("bootstrap 5th-pct return > 0", mc.get("p5_return", -1) > g["mc_p5_return_gt"],
         "%.1f%%" % (100 * mc.get("p5_return", -1)) if mc.get("runs") else "n/a"),
    ]
    return all(c[1] for c in checks), checks


def check_forward(m, days, backtest_avg_R):
    g = GATES["forward"]
    checks = [
        ("days >= %d" % g["min_days"], days >= g["min_days"], round(days, 1)),
        ("signals >= %d" % g["min_trades"], m.get("trades", 0) >= g["min_trades"], m.get("trades", 0)),
        ("profit factor >= %.2f" % g["min_pf"], m.get("profit_factor", 0) >= g["min_pf"],
         round(m.get("profit_factor", 0), 2)),
        ("expectancy >= half of backtest", m.get("avg_R", -9) >= g["min_expectancy_share"] * backtest_avg_R,
         round(m.get("avg_R", 0), 3)),
    ]
    return all(c[1] for c in checks), checks


def check_paper(m, days, breaches, owner_unlocked):
    g = GATES["paper"]
    enough = days >= g["min_days"] or m.get("trades", 0) >= g["or_min_trades"]
    checks = [
        ("%d days or %d trades" % (g["min_days"], g["or_min_trades"]), enough,
         "%dd / %d" % (days, m.get("trades", 0))),
        ("profit factor >= %.2f" % g["min_pf"], m.get("profit_factor", 0) >= g["min_pf"],
         round(m.get("profit_factor", 0), 2)),
        ("drawdown <= %d%%" % (g["max_dd"] * 100), m.get("max_drawdown", 1) <= g["max_dd"],
         "%.1f%%" % (100 * m.get("max_drawdown", 1))),
        ("zero risk-rule breaches", breaches <= g["max_breaches"], breaches),
        ("owner unlocked live in the app", bool(owner_unlocked), bool(owner_unlocked)),
    ]
    return all(c[1] for c in checks), checks


def should_demote(recent_trades, backtest_p95_dd=None, current_dd=None):
    last = recent_trades[-DEMOTE["last_n"]:]
    if len(last) >= DEMOTE["last_n"]:
        gw = sum(t["R"] for t in last if t["R"] > 0)
        gl = -sum(t["R"] for t in last if t["R"] <= 0)
        pf = gw / gl if gl > 0 else float("inf")
        if pf < DEMOTE["min_pf"]:
            return True, "profit factor over last %d trades %.2f < %.2f" % (len(last), pf, DEMOTE["min_pf"])
    if backtest_p95_dd is not None and current_dd is not None and current_dd > backtest_p95_dd:
        return True, "drawdown %.1f%% beyond backtest 95th percentile %.1f%%" % (100 * current_dd,
                                                                                 100 * backtest_p95_dd)
    return False, ""


class Ladder:
    """Stage per (strategy, symbol), stored as JSON."""

    def __init__(self, path):
        self.path = path
        self.d = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self.d = json.load(f)

    def key(self, sid, sym):
        return "%s:%s" % (sid, sym)

    def get(self, sid, sym):
        return self.d.get(self.key(sid, sym), {"stage": "backtest", "history": []})

    def set(self, sid, sym, stage, reason, extra=None):
        e = self.get(sid, sym)
        if e["stage"] != stage:
            e["history"].append({"t": int(time.time()), "from": e["stage"], "to": stage, "reason": reason})
        e["stage"] = stage
        e.update(extra or {})
        self.d[self.key(sid, sym)] = e

    def save(self):
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self.d, f, indent=2, sort_keys=True)
        os.replace(tmp, self.path)
