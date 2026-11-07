"""Self-learning loop (BLUEPRINT section 10).

1. Group a strategy's trades by each context field.
2. Flag groups with at least 30 trades and expectancy <= -0.2R while the strategy overall is positive.
3. Each flag becomes a proposal: the same strategy with a filter that skips that group.
4. A proposal is promoted only if walk-forward out-of-sample results beat the parent by >= 0.05R
   expectancy while keeping >= 70% of the trades. Nothing changes live settings directly.
"""
import json

from . import walkforward as W

MIN_GROUP = 30
BAD_R = -0.2
MIN_GAIN_R = 0.05
MIN_KEEP = 0.70


def groups(trades):
    out = {}
    for t in trades:
        feat = t.get("feat") or {}
        if isinstance(feat, str):
            feat = json.loads(feat or "{}")
        for k, v in feat.items():
            if v is None:
                continue
            if k == "volume_ratio":
                v = "<1" if v < 1 else "1-2" if v < 2 else ">=2"
            elif k == "htf_age_h":
                v = "<6h" if v < 6 else "6-24h" if v < 24 else ">=24h"
            out.setdefault((k, v), []).append(t["R"])
    return out


def propose(trades):
    if len(trades) < MIN_GROUP:
        return []
    overall = sum(t["R"] for t in trades) / len(trades)
    props = []
    for (k, v), rs in sorted(groups(trades).items(), key=lambda kv: str(kv[0])):
        if len(rs) >= MIN_GROUP and sum(rs) / len(rs) <= BAD_R and overall > 0:
            props.append({"skip_field": k, "skip_value": v, "group_trades": len(rs),
                          "group_avg_R": sum(rs) / len(rs), "overall_avg_R": overall})
        elif len(rs) >= MIN_GROUP and overall <= 0 and sum(rs) / len(rs) <= overall - 0.15:
            # strategy is losing overall: still show the worst pockets, as diagnostics only
            props.append({"skip_field": k, "skip_value": v, "group_trades": len(rs),
                          "group_avg_R": sum(rs) / len(rs), "overall_avg_R": overall, "diagnostic": True})
    return props


def _filter(p):
    k, v = p["skip_field"], p["skip_value"]

    def f(feat, sig):
        x = feat.get(k)
        if x is None:
            return True
        if k == "volume_ratio":
            x = "<1" if x < 1 else "1-2" if x < 2 else ">=2"
        elif k == "htf_age_h":
            x = "<6h" if x < 6 else "6-24h" if x < 24 else ">=24h"
        return x != v
    return f


def evaluate(strat_cls, mkt, proposal, parent_wf=None):
    parent = parent_wf or W.walk_forward(strat_cls, mkt)
    child = W.walk_forward(strat_cls, mkt, entry_filter=_filter(proposal))
    pn, cn = len(parent["oos"]), len(child["oos"])
    pr = sum(t["R"] for t in parent["oos"]) / pn if pn else 0.0
    cr = sum(t["R"] for t in child["oos"]) / cn if cn else 0.0
    keep = cn / pn if pn else 0.0
    ok = (cr - pr) >= MIN_GAIN_R and keep >= MIN_KEEP and not proposal.get("diagnostic")
    return {"proposal": proposal, "parent_oos_trades": pn, "parent_avg_R": pr, "child_oos_trades": cn,
            "child_avg_R": cr, "kept": keep, "promote": ok}
