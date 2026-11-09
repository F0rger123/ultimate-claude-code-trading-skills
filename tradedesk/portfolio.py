"""Portfolio backtester with one shared, mark-to-market ledger.

Why this exists: `backtest.simulate` sizes each trade from realized equity and lets overlapping trades
each see the full account. This module replaces that for research:

- One ledger (cash + positions) shared by every symbol and strategy, in deterministic time order.
- Equity is marked to market at every base bar:
      spot:  E = cash + sum(qty * price)
      perp:  E = cash + sum(side * qty * mult * (price - entry))   (cash already net of fees and funding)
- Drawdown is measured on that marked curve (intrabar-close granularity) and on daily closes.
- Sizing uses current marked equity, the stop distance, and caps: per-position leverage, total gross
  exposure, available cash (spot), whole contracts (perp), venue minimums.
- Fills: market orders at the next bar's open plus slippage; stops fill at the stop or, if the bar gaps
  through it, at the open; when stop and target are both inside a bar the stop wins. Limit orders are NOT
  assumed filled because a candle touched them; maker fees are only used where explicitly configured.
- Funding (perps): signed. A positive rate charges longs and pays shorts. Without a historical funding
  series the rate is an ASSUMPTION and is reported as such.
- Optional drawdown policy (owner's tiers): warn at 7.5% (risk x0.5), block new entries at 10%,
  flatten and halt at 15%. In research a halt can be released after `resume_days` (an assumption that
  stands in for the owner's decision to resume).

Strategies are the existing single-symbol classes. Walk-forward parameter switching is supported via
`active(t)`, which returns the index of the strategy variant that may open new positions at time t.
"""
import math

DAY = 86400

SPOT_COSTS = {"taker": 0.009, "maker": 0.005, "slip": 0.0005}   # 2026 US entry-tier scenario (unverified)
PERP_COSTS = {"taker": 0.0006, "maker": 0.0006, "slip": 0.0002}  # provisional CFM assumption
CONTRACTS = {"BTC": 0.01, "ETH": 0.1, "SOL": 5.0}


class Config:
    def __init__(self, mode="spot", equity=10000.0, risk=0.01, pos_lev=1.0, gross_lev=1.0,
                 costs=None, funding_per_h=0.0, contracts=None, min_notional=1.0, dd_policy=False,
                 dd_warn=0.075, dd_block=0.10, dd_flat=0.15, resume_days=30, cost_mult=1.0):
        self.mode = mode
        self.equity = equity
        self.risk = risk
        self.pos_lev = pos_lev
        self.gross_lev = gross_lev
        base = dict(SPOT_COSTS if mode == "spot" else PERP_COSTS)
        base.update(costs or {})
        self.costs = {k: v * cost_mult for k, v in base.items()}
        self.funding_per_h = funding_per_h  # signed rate per hour; positive = longs pay
        self.contracts = contracts if contracts is not None else (CONTRACTS if mode == "perp" else {})
        self.min_notional = min_notional
        self.dd_policy = dd_policy
        self.dd_warn, self.dd_block, self.dd_flat = dd_warn, dd_block, dd_flat
        self.resume_days = resume_days


class Position:
    __slots__ = ("sym", "side", "qty", "entry", "stop", "target", "t0", "variant", "risk_usd", "fees",
                 "funding", "mae", "size_mult", "feat")

    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def run(markets, variants, cfg, start_t=None, end_t=None, active=None, log=None):
    """markets: {sym: Market}; variants: {sym: [strategy instance per variant]} (same base granularity).
    active(t) -> variant index allowed to open positions at t (default 0).
    Returns dict(trades, curve=[(t, equity)], events, halts)."""
    syms = sorted(markets)
    base = markets[syms[0]].base
    idx = {s: {t: i for i, t in enumerate(markets[s].b.t)} for s in syms}
    clock = sorted(set().union(*[set(markets[s].b.t) for s in syms]))
    if start_t is not None:
        clock = [t for t in clock if t >= start_t]
    if end_t is not None:
        clock = [t for t in clock if t < end_t]
    k = cfg.costs
    cash = cfg.equity
    pos = {}
    pending_entry, pending_exit = {}, set()
    last_px = {}
    trades, curve, events = [], [], []
    hwm = cfg.equity
    blocked_until = -1
    halted_flat = False
    active = active or (lambda t: 0)

    def equity_now():
        e = cash
        for p in pos.values():
            px = last_px.get(p.sym, p.entry)
            if cfg.mode == "spot":
                e += p.qty * px
            else:
                e += p.side * p.qty * (px - p.entry)
        return e

    def gross_now():
        return sum(p.qty * last_px.get(p.sym, p.entry) for p in pos.values())

    def close(p, px, why, t):
        nonlocal cash
        side = p.side
        fill = px * (1 - side * k["slip"])
        fee = p.qty * fill * k["taker"]
        if cfg.mode == "spot":
            cash += p.qty * fill - fee
            gross = p.qty * (fill - p.entry)
        else:
            gross = side * p.qty * (fill - p.entry)
            cash += gross - fee
        net = gross - p.fees - fee - p.funding
        trades.append({"sym": p.sym, "side": side, "t0": p.t0, "t1": t, "entry": p.entry, "exit": fill,
                       "stop": p.stop, "qty": p.qty, "why": why, "variant": p.variant, "gross": gross,
                       "fees": p.fees + fee, "funding": p.funding, "pnl": net,
                       "R": net / p.risk_usd if p.risk_usd > 0 else 0.0, "risk_usd": p.risk_usd,
                       "hours": (t - p.t0) / 3600.0, "mae": p.mae, "size_mult": p.size_mult, "feat": p.feat})
        del pos[p.sym]

    for t in clock:
        # ---------------- opens: every pending exit first (frees cash), then pending entries
        for s in syms:
            i = idx[s].get(t)
            if i is not None and s in pending_exit and s in pos:
                close(pos[s], markets[s].b.o[i], "signal", t)
            if i is not None:
                pending_exit.discard(s)
        for s in syms:
            i = idx[s].get(t)
            if i is None:
                continue
            o = markets[s].b.o[i]
            sig = pending_entry.pop(s, None)
            if sig is not None and s not in pos and not halted_flat and t >= blocked_until:
                side = sig["side"]
                if cfg.mode == "spot" and side == -1:
                    events.append((t, "skip", s, "spot cannot short"))
                    continue
                fill = o * (1 + side * k["slip"])
                stop = sig["stop"]
                if (side == 1 and stop >= fill) or (side == -1 and stop <= fill):
                    events.append((t, "skip", s, "gap invalidated stop"))
                    continue
                e = equity_now()
                dd = (hwm - e) / hwm if hwm > 0 else 0
                risk = cfg.risk * sig.get("size_mult", 1.0)
                if cfg.dd_policy and dd >= cfg.dd_warn:
                    risk *= 0.5
                budget = risk * e
                qty = budget / abs(fill - stop)
                qty = min(qty, cfg.pos_lev * e / fill)
                room = cfg.gross_lev * e - gross_now()
                qty = min(qty, max(0.0, room) / fill)
                if cfg.mode == "spot":
                    qty = min(qty, max(0.0, cash) / (fill * (1 + k["taker"])))
                cs = cfg.contracts.get(s)
                if cs:
                    qty = math.floor(qty / cs + 1e-9) * cs
                if qty * fill < max(cfg.min_notional, 1e-9) or qty <= 0:
                    events.append((t, "skip", s, "size below minimum (contract/notional/cash)"))
                    continue
                fee = qty * fill * k["taker"]
                if cfg.mode == "spot":
                    cash -= qty * fill + fee
                else:
                    cash -= fee
                pos[s] = Position(sym=s, side=side, qty=qty, entry=fill, stop=stop, target=sig.get("target"),
                                  t0=t, variant=sig["variant"], risk_usd=qty * abs(fill - stop), fees=fee,
                                  funding=0.0, mae=0.0, size_mult=sig.get("size_mult", 1.0),
                                  feat=sig.get("feat", {}))
        # ---------------- intrabar: stops and targets
        for s in syms:
            i = idx[s].get(t)
            if i is None or s not in pos:
                continue
            b = markets[s].b
            p = pos[s]
            o, h, l = b.o[i], b.h[i], b.l[i]
            if p.side == 1:
                p.mae = max(p.mae, (p.entry - l) / p.entry)
                if o <= p.stop:
                    close(p, o, "stop_gap", t)
                elif l <= p.stop:
                    close(p, p.stop, "stop", t)
                elif p.target is not None and h >= p.target:
                    close(p, max(o, p.target), "target", t)
            else:
                p.mae = max(p.mae, (h - p.entry) / p.entry)
                if o >= p.stop:
                    close(p, o, "stop_gap", t)
                elif h >= p.stop:
                    close(p, p.stop, "stop", t)
                elif p.target is not None and l <= p.target:
                    close(p, min(o, p.target), "target", t)
        # ---------------- funding (perps), signed
        if cfg.mode == "perp" and cfg.funding_per_h:
            for p in pos.values():
                f = p.side * p.qty * last_px.get(p.sym, p.entry) * cfg.funding_per_h * (base / 3600.0)
                p.funding += f
                cash -= f
        # ---------------- closes: marks, exits, entries
        for s in syms:
            i = idx[s].get(t)
            if i is not None:
                last_px[s] = markets[s].b.c[i]
        e = equity_now()
        hwm = max(hwm, e)
        dd = (hwm - e) / hwm if hwm > 0 else 0.0
        curve.append((t, e))
        if cfg.dd_policy and not halted_flat:
            if dd >= cfg.dd_flat:
                for p in list(pos.values()):
                    close(p, last_px[p.sym], "dd_flatten", t + base)
                events.append((t, "halt", "*", "15%% drawdown: flatten and halt (dd %.1f%%)" % (100 * dd)))
                halted_flat = True
                blocked_until = t + cfg.resume_days * DAY
                hwm = equity_now()  # a resumed account starts a new high-water mark
            elif dd >= cfg.dd_block and t >= blocked_until:
                blocked_until = t + cfg.resume_days * DAY
                events.append((t, "block", "*", "10%% drawdown: new entries blocked (dd %.1f%%)" % (100 * dd)))
        if halted_flat and t >= blocked_until:
            halted_flat = False
            events.append((t, "resume", "*", "research assumption: owner resumes after %d days" % cfg.resume_days))
        for s in syms:
            i = idx[s].get(t)
            if i is None:
                continue
            if s in pos:
                p = pos[s]
                strat = variants[s][p.variant]
                held = (t - p.t0) // base
                if strat.exit(i, {"side": p.side, "i0": i - held}) or (strat.max_bars and held >= strat.max_bars):
                    pending_exit.add(s)
                continue
            if s in pending_entry:
                continue
            v = active(t)
            if v is None:
                continue
            strat = variants[s][v]
            sig = strat.entry(i)
            if sig is not None:
                sig["variant"] = v
                pending_entry[s] = sig
    for p in list(pos.values()):  # mark-out at the end (counted as a closed trade for statistics)
        close(p, last_px[p.sym], "end", clock[-1] if clock else 0)
    if curve:
        curve[-1] = (curve[-1][0], cash)  # everything is closed out at the end
    return {"trades": trades, "curve": curve, "events": events}
