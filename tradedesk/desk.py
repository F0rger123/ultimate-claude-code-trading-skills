"""The desk: one loop for forward, paper and live.

Every 30 seconds it pulls the newest closed 5-minute perp candles from Coinbase (public), runs
each strategy that has reached the forward stage or above, manages open positions, and
journals everything.

- forward: signals and simulated outcomes, no account (counts toward the forward gate)
- paper:   simulated fills against a paper account sized by rules.json
- live:    real orders through broker_coinbase, only when all three live locks are open
"""
import os
import time
import traceback

from . import backtest as B
from . import data as D
from . import ladder as L
from . import risk as R
from . import strategies as S
from .journal import Journal
from .market import Market

BAR = 300
WARMUP_DAYS = 90  # daily strategies need ~60 days; 200 x 1h EMA ~8.3 days


def day_start(t):
    return t - t % 86400


class Desk:
    def __init__(self, state_dir="state", log=print, fetch=None, now=time.time):
        self.dir = state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.log = log
        self.now = now
        self.fetch = fetch or (lambda prod, a, b: D.fetch_perp(prod, BAR, a, b, sleep=0.05))
        self.j = Journal(os.path.join(state_dir, "journal.sqlite"))
        self.rules_path = os.path.join(state_dir, "rules.json")
        self.ladder = L.Ladder(os.path.join(state_dir, "ladder.json"))
        self.bars = {}
        self.last_bar = {}
        self.pending_exit = set()
        self.broker = None

    # ---------------------------------------------------------------- state
    def rules(self):
        return R.load_rules(self.rules_path)

    def live_unlocked(self, rules):
        return rules["live_enabled"] and os.environ.get("TRADEDESK_LIVE") == "1"

    def paper_equity(self, rules):
        """Paper account equity MARKED TO MARKET: realized P&L plus open paper trades at the latest close."""
        s = self.j.q("SELECT COALESCE(SUM(pnl_usd),0) AS s FROM trades WHERE mode='paper' AND status='closed'")[0]["s"]
        unreal = 0.0
        for tr in self.j.open_trades("paper"):
            bars = self.bars.get(tr["symbol"])
            if bars:
                unreal += tr["side"] * (bars[-1][4] - tr["entry"]) * tr["contracts"] * D.PERPS[tr["symbol"]]["contract"]
        return rules["paper_equity_usd"] + s + unreal

    def active(self, sym):
        """(strategy class, params, stage) for every strategy at forward or above on this symbol."""
        out = []
        self.ladder = L.Ladder(self.ladder.path)
        for cls in S.ALL:
            e = self.ladder.get(cls.id, sym)
            if e["stage"] in ("shadow", "forward", "paper", "small_live", "scaled"):
                out.append((cls, e.get("params") or {}, e["stage"]))
        return out

    # ---------------------------------------------------------------- data
    def refresh(self, sym):
        prod = D.PERPS[sym]["perp"]
        t = int(self.now())
        end = t - t % BAR  # open time of the bar still forming
        have = self.bars.get(sym)
        start = (have[-1][0] + BAR) if have else end - WARMUP_DAYS * 86400
        if start < end:
            new = self.fetch(prod, start, end)
            merged = {b[0]: b for b in (have or [])}
            merged.update({b[0]: b for b in new})
            keep = sorted(merged)[-WARMUP_DAYS * 288:]
            self.bars[sym] = [merged[k] for k in keep]
        bars = self.bars.get(sym) or []
        age = t - (bars[-1][0] + BAR) if bars else 1e9
        return bars, age

    # ---------------------------------------------------------------- main step
    def step(self):
        rules = self.rules()
        t = int(self.now())
        if rules["kill_switch"]:
            self.flatten_all("kill switch")
        for sym in rules["symbols"]:
            if sym not in D.PERPS:
                continue
            try:
                bars, age = self.refresh(sym)
            except Exception as e:  # network trouble: stops already rest on the exchange in live
                self.j.event("warn", "%s data refresh failed: %s" % (sym, e))
                continue
            if not bars or self.last_bar.get(sym) == bars[-1][0]:
                continue
            self.last_bar[sym] = bars[-1][0]
            self.on_bar(sym, bars, age, rules, t)
        eq = self.paper_equity(rules)
        self.j.snap("paper", eq, t)
        self.drawdown_halt(rules, eq)

    def drawdown_halt(self, rules, eq):
        """Owner's drawdown tiers on MARKED equity: >= dd_warn (7.5%) halves new risk, >= dd_block (10%)
        blocks new entries, >= max_drawdown_pct (15%) flattens and turns the kill switch on. Only the owner
        resumes."""
        peak = max([rules["paper_equity_usd"]] + [r["equity"] for r in self.j.equity_curve("paper")])
        dd = (peak - eq) / peak if peak > 0 else 0.0
        if dd >= rules["max_drawdown_pct"] and not rules["kill_switch"]:
            rules["kill_switch"] = True
            R.save_rules(self.rules_path, rules)
            self.j.event("warn", "MAX DRAWDOWN HALT: %.1f%% from peak $%.2f (limit %.0f%%). Kill switch on." % (
                100 * dd, peak, 100 * rules["max_drawdown_pct"]))
            self.flatten_all("max drawdown halt")
        elif dd >= rules["dd_block_pct"] and not getattr(self, "_dd_block_logged", False):
            self.j.event("warn", "DRAWDOWN %.1f%%: new entries blocked (limit %.1f%%)" % (100 * dd, 100 * rules["dd_block_pct"]))
            self._dd_block_logged = True
        elif dd < rules["dd_block_pct"]:
            self._dd_block_logged = False
        self.dd = dd
        return dd

    def on_bar(self, sym, bars, age, rules, t):
        mkt = Market(bars, sym)
        i = len(bars) - 1
        bar = bars[i]
        for cls, params, stage in self.active(sym):
            mode = "forward" if stage in ("shadow", "forward") else "paper" if stage == "paper" else (
                "live" if self.live_unlocked(rules) else "paper")
            strat = cls(mkt, **params)
            opens = [x for x in self.j.open_trades(mode) if x["strategy"] == cls.id and x["symbol"] == sym]
            if opens:
                self.manage(opens[0], strat, i, bar, mode, rules)
                continue
            sig = strat.entry(i)
            if sig is None:
                continue
            self.try_enter(sym, cls, strat, sig, bar, mode, rules, age, t)

    # ---------------------------------------------------------------- positions
    def manage(self, tr, strat, i, bar, mode, rules):
        """Stop/target check on the newest bar (pessimistic: stop first), then the strategy exit."""
        side, stop, tgt = tr["side"], tr["stop"], tr["target"]
        _, o, h, l, c, _ = bar
        hit = None
        if side == 1:
            if l <= stop:
                hit = (min(o, stop), "stop")
            elif tgt and h >= tgt:
                hit = (max(o, tgt), "target")
        else:
            if h >= stop:
                hit = (max(o, stop), "stop")
            elif tgt and l <= tgt:
                hit = (min(o, tgt), "target")
        if hit:
            self.close(tr, hit[0], hit[1], mode, bar[0] + BAR)
            return
        pos = {"side": side, "i0": i}
        held = (bar[0] - tr["t0"]) // BAR
        if strat.exit(i, pos) or (strat.max_bars and held >= strat.max_bars):
            self.close(tr, c, "signal", mode, bar[0] + BAR)

    def try_enter(self, sym, cls, strat, sig, bar, mode, rules, age, t):
        entry = bar[4]
        contract = D.PERPS[sym]["contract"]
        equity = self.paper_equity(rules) if mode != "live" else self.live_equity()
        dd = getattr(self, "dd", 0.0)
        if mode != "forward" and dd >= rules["dd_block_pct"]:
            self.j.event("info", "%s %s %s blocked: drawdown %.1f%% >= %.1f%%" % (mode, cls.id, sym, 100 * dd, 100 * rules["dd_block_pct"]))
            return
        if dd >= rules["dd_warn_pct"]:  # prospective risk reduction, never an increase
            rules = dict(rules, risk_pct=rules["risk_pct"] * 0.5, max_loss_per_trade_usd=rules["max_loss_per_trade_usd"] * 0.5)
        n, loss, lev, limiter = R.size(rules, sym, equity, entry, sig["stop"], contract)
        ds = day_start(t)
        realized, _ = self.j.realized_since(mode, ds)
        open_all = self.j.open_trades(mode)
        order = {"symbol": sym, "side": sig["side"], "entry": entry, "stop": sig["stop"], "contracts": n,
                 "loss_usd": loss, "leverage": lev, "t": t}
        state = {"open_positions": len(open_all), "trades_today": self.j.opened_since(mode, ds),
                 "realized_today_usd": realized, "open_risk_usd": sum(x["risk_usd"] or 0 for x in open_all),
                 "data_age_s": age, "bar_s": BAR}
        if mode == "forward":  # forward test: record the signal with a notional 1-contract size
            n, loss, lev = max(n, 1), abs(entry - sig["stop"]) * contract, entry * contract / max(equity, 1)
            ok, why = True, []
        else:
            ok, why = R.check(rules, order, state)
        if not ok:
            self.j.event("info", "%s %s %s blocked: %s" % (mode, cls.id, sym, "; ".join(why)))
            return
        ref = None
        if mode == "live":
            try:
                b = self._broker()
                from .broker_coinbase import far_target
                tgt = sig["target"] or far_target(entry, sig["stop"], sig["side"])
                r = b.enter(D.PERPS[sym]["perp"], sig["side"], n, sig["stop"], tgt, R.lev_cap(rules, sym))
                if not r.get("success", False):
                    self.j.event("error", "live order rejected: %s" % r)
                    return
                ref = (r.get("success_response") or {}).get("order_id")
            except Exception as e:
                self.j.event("error", "live order failed: %s" % e)
                return
        tid = self.j.open_trade(mode, cls.id, sym, sig["side"], n, entry, sig["stop"], sig.get("target"),
                                bar[0] + BAR, loss, lev, strat.features(len(strat.m.b.t) - 1), ref)
        self.j.event("trade", "%s open #%d %s %s %s x%d @ %.2f stop %.2f (%s-limited)" % (
            mode, tid, cls.id, sym, "LONG" if sig["side"] == 1 else "SHORT", n, entry, sig["stop"], limiter))

    def close(self, tr, px, why, mode, t1):
        contract = D.PERPS[tr["symbol"]]["contract"]
        k = B.COSTS
        side = tr["side"]
        px_eff = px * (1 - side * k["slip"])
        e = tr["entry"] * (1 + side * k["slip"])
        units = tr["contracts"] * contract
        hours = max(0.0, (t1 - tr["t0"]) / 3600)
        fees = units * (e + px_eff) * k["fee"] + units * e * hours * k["funding_per_h"]
        pnl = side * (px_eff - e) * units - fees
        risk = abs(tr["entry"] - tr["stop"]) * units
        if mode == "live":
            try:
                prod = D.PERPS[tr["symbol"]]["perp"]
                if why in ("stop", "target"):  # the exchange's resting bracket already closed it
                    self._broker().cancel_all(prod)
                else:
                    self._broker().close(prod, tr["contracts"])
            except Exception as ex:
                self.j.event("error", "live close failed for #%d: %s" % (tr["id"], ex))
                return
        self.j.close_trade(tr["id"], px_eff, t1, why, pnl, fees, pnl / risk if risk else 0.0)
        self.j.event("trade", "%s close #%d %s %s %s @ %.2f pnl $%.2f" % (
            mode, tr["id"], tr["strategy"], tr["symbol"], why, px_eff, pnl))

    def flatten_all(self, why):
        for tr in self.j.open_trades():
            bars = self.bars.get(tr["symbol"])
            if bars:
                self.close(tr, bars[-1][4], why, tr["mode"], int(self.now()))

    # ---------------------------------------------------------------- live helpers
    def _broker(self):
        if self.broker is None:
            from .broker_coinbase import CoinbaseCFM
            self.broker = CoinbaseCFM()
        return self.broker

    def live_equity(self):
        b = self._broker().balance().get("balance_summary", {})
        return float((b.get("total_usd_balance") or {}).get("value", 0) or 0)

    # ---------------------------------------------------------------- run
    def run(self, every=30):
        self.j.event("info", "desk started")
        self.log("desk running; Ctrl+C to stop. State in %s" % self.dir)
        while True:
            try:
                self.step()
            except KeyboardInterrupt:
                raise
            except Exception:
                self.j.event("error", traceback.format_exc()[-800:])
            time.sleep(every)
