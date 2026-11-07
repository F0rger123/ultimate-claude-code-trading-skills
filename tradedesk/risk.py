"""Rules and the risk guard. Every order goes through check() before paper or live.

The values are the owner's to set (from the app). The guardrails themselves always exist:
a resting stop, a daily loss cap, a loss cap per trade, leverage and position limits, the kill switch.
"""
import json
import math
import os
import time

DEFAULT_RULES = {
    "live_enabled": False,
    "kill_switch": False,
    "risk_pct": 0.01,
    "max_loss_per_trade_usd": 30.0,
    "daily_loss_cap_usd": 150.0,
    "max_leverage": 5.0,
    "max_open_positions": 3,
    "max_trades_per_day": 12,
    "news_filter": True,
    "news_blackout": [],
    "symbols": ["BTC", "ETH", "SOL"],
    "paper_equity_usd": 10000.0,
}

# Coinbase CFM overnight leverage (lowest of long/short, checked 2026-11-07 from the public product
# endpoint). Sizing always uses the overnight figure, so a position never needs more margin at 4pm ET.
EXCHANGE_MAX_LEV = {"BTC": 3.9, "ETH": 3.3, "SOL": 1.8}

FLOORS = {"daily_loss_cap_usd": 1.0, "max_loss_per_trade_usd": 1.0, "max_leverage": 1.0,
          "max_open_positions": 1, "max_trades_per_day": 1, "risk_pct": 0.0005}
CEILINGS = {"risk_pct": 0.05, "max_open_positions": 10, "max_trades_per_day": 100, "max_leverage": 20.0}


def normalize(r):
    out = dict(DEFAULT_RULES)
    out.update({k: v for k, v in (r or {}).items() if k in DEFAULT_RULES})
    for k, lo in FLOORS.items():
        out[k] = max(lo, type(DEFAULT_RULES[k])(out[k]))
    for k, hi in CEILINGS.items():
        out[k] = min(hi, out[k])
    out["live_enabled"] = bool(out["live_enabled"])
    out["kill_switch"] = bool(out["kill_switch"])
    out["news_filter"] = bool(out["news_filter"])
    return out


def load_rules(path):
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return normalize(json.load(f))
    r = normalize({})
    save_rules(path, r)
    return r


def save_rules(path, rules):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(normalize(rules), f, indent=2)
    os.replace(tmp, path)


def lev_cap(rules, symbol):
    return min(rules["max_leverage"], EXCHANGE_MAX_LEV.get(symbol, 1.0))


def size(rules, symbol, equity, entry, stop, contract):
    """Whole contracts so the loss at the stop fits both the per-trade cap and risk_pct, and
    notional fits the leverage cap. Returns (contracts, loss_at_stop_usd, leverage, limiter)."""
    dist = abs(entry - stop)
    if dist <= 0 or contract <= 0 or equity <= 0:
        return 0, 0.0, 0.0, "bad input"
    budget = min(rules["max_loss_per_trade_usd"], rules["risk_pct"] * equity)
    by_risk = math.floor(budget / (dist * contract))
    by_lev = math.floor(lev_cap(rules, symbol) * equity / (entry * contract))
    n = min(by_risk, by_lev)
    limiter = "risk" if by_risk <= by_lev else "leverage"
    if n < 1:
        return 0, 0.0, 0.0, "one contract risks $%.2f, over the $%.2f budget" % (dist * contract, budget) \
            if by_risk < 1 else "one contract needs more leverage than allowed"
    return n, n * dist * contract, n * contract * entry / equity, limiter


def in_blackout(rules, t):
    if not rules["news_filter"]:
        return None
    for w in rules["news_blackout"]:
        try:
            a = _parse(w["start"])
            b = _parse(w["end"])
        except (KeyError, ValueError):
            continue
        if a <= t < b:
            return w.get("label", "news")
    return None


def _parse(s):
    return int(time.mktime(time.strptime(s, "%Y-%m-%dT%H:%M:%SZ")) - time.timezone)


def check(rules, order, state):
    """order: symbol, side, entry, stop, contracts, loss_usd, leverage, t.
    state: open_positions, trades_today, realized_today_usd (negative = loss), open_risk_usd,
    data_age_s, bar_s. Returns (ok, reasons)."""
    why = []
    if rules["kill_switch"]:
        why.append("kill switch is on")
    if order.get("stop") is None:
        why.append("no stop")
    else:
        if order["side"] == 1 and order["stop"] >= order["entry"]:
            why.append("stop is not below entry for a long")
        if order["side"] == -1 and order["stop"] <= order["entry"]:
            why.append("stop is not above entry for a short")
    if order["contracts"] < 1:
        why.append("size rounds to zero contracts")
    if order["loss_usd"] > rules["max_loss_per_trade_usd"] + 1e-9:
        why.append("loss at stop $%.2f over max $%.2f" % (order["loss_usd"], rules["max_loss_per_trade_usd"]))
    if order["leverage"] > lev_cap(rules, order["symbol"]) + 1e-9:
        why.append("leverage %.2fx over cap %.2fx" % (order["leverage"], lev_cap(rules, order["symbol"])))
    lost = -min(0.0, state.get("realized_today_usd", 0.0))
    if lost + state.get("open_risk_usd", 0.0) + order["loss_usd"] > rules["daily_loss_cap_usd"] + 1e-9:
        why.append("would risk past the daily loss cap ($%.0f lost, $%.0f open risk, cap $%.0f)" % (
            lost, state.get("open_risk_usd", 0.0), rules["daily_loss_cap_usd"]))
    if state.get("open_positions", 0) >= rules["max_open_positions"]:
        why.append("max open positions reached")
    if state.get("trades_today", 0) >= rules["max_trades_per_day"]:
        why.append("max trades per day reached")
    if order["symbol"] not in rules["symbols"]:
        why.append("symbol not enabled")
    b = in_blackout(rules, order.get("t", time.time()))
    if b:
        why.append("news blackout: %s" % b)
    if state.get("data_age_s", 0) > 3 * state.get("bar_s", 300):
        why.append("data is stale")
    return (len(why) == 0), why
