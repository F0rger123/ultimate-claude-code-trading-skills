"""Tests for the shared mark-to-market ledger, statistics and research candidates."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research"))

from tradedesk import candidates as C  # noqa: E402
from tradedesk import metrics as M  # noqa: E402
from tradedesk import portfolio as P  # noqa: E402
from tradedesk.market import Market  # noqa: E402
from tradedesk.strategies import Strategy  # noqa: E402

H = 3600
T0 = 1700006400 - 1700006400 % 86400


def bars(prices, start=T0, spread=0.0):
    out = []
    for k, p in enumerate(prices):
        o, c = p, p
        out.append((start + k * H, o, max(o, c) * (1 + spread), min(o, c) * (1 - spread), c, 10.0))
    return out


class Script(Strategy):
    """Enters at given base-bar indexes; exits at given indexes."""
    id = "script"

    def __init__(self, mkt, plan=None, exits=(), **kw):
        self.plan = plan or {}
        self.exits = set(exits)
        Strategy.__init__(self, mkt, **kw)

    def entry(self, i):
        return dict(self.plan[i]) if i in self.plan else None

    def exit(self, i, pos):
        return i in self.exits

    def features(self, i):
        return {}


ZERO = {"taker": 0.0, "maker": 0.0, "slip": 0.0}


class Ledger(unittest.TestCase):
    def test_drawdown_is_marked_to_market(self):
        # price falls 30% while the trade is open, then recovers before the exit
        px = [100] * 3 + [70] * 5 + [100] * 3
        m = Market(bars(px), "BTC", H)
        s = Script(m, {1: {"side": 1, "stop": 50.0, "target": None}}, exits={8})
        cfg = P.Config("spot", equity=1000, risk=1.0, pos_lev=1.0, gross_lev=1.0, costs=ZERO)
        r = P.run({"BTC": m}, {"BTC": [s]}, cfg)
        self.assertEqual(len(r["trades"]), 1)
        self.assertAlmostEqual(r["trades"][0]["pnl"], 0.0, places=6)  # closed-trade view: no loss at all
        self.assertGreater(M.max_dd([e for _, e in r["curve"]]), 0.25)  # marked view: ~30% drawdown

    def test_overlapping_trades_share_one_account(self):
        px = [100.0] * 12
        a, b = Market(bars(px), "BTC", H), Market(bars(px), "ETH", H)
        plan = {1: {"side": 1, "stop": 90.0, "target": None}}
        cfg = P.Config("spot", equity=1000, risk=1.0, pos_lev=1.0, gross_lev=1.0, costs=ZERO)
        r = P.run({"BTC": a, "ETH": b}, {"BTC": [Script(a, plan)], "ETH": [Script(b, plan)]}, cfg)
        notional = sum(t["qty"] * t["entry"] for t in r["trades"])
        self.assertLessEqual(notional, 1000 + 1e-6)  # never more than the account between both coins

    def test_spot_cannot_short_and_contracts_are_whole(self):
        px = [100.0] * 8
        m = Market(bars(px), "BTC", H)
        s = Script(m, {1: {"side": -1, "stop": 110.0, "target": None}})
        r = P.run({"BTC": m}, {"BTC": [s]}, P.Config("spot", equity=1000, costs=ZERO))
        self.assertEqual(r["trades"], [])
        cfg = P.Config("perp", equity=1000, risk=0.05, pos_lev=5, gross_lev=5, costs=ZERO, contracts={"BTC": 0.3})
        s2 = Script(m, {1: {"side": 1, "stop": 90.0, "target": None}})
        r = P.run({"BTC": m}, {"BTC": [s2]}, cfg)
        q = r["trades"][0]["qty"]
        self.assertAlmostEqual(q / 0.3, round(q / 0.3), places=9)

    def test_signed_funding(self):
        px = [100.0] * 30
        m = Market(bars(px), "BTC", H)
        for side, sign in ((1, -1), (-1, 1)):
            s = Script(m, {1: {"side": side, "stop": 100 - side * 10, "target": None}})
            cfg = P.Config("perp", equity=1000, risk=0.01, pos_lev=5, gross_lev=5, costs=ZERO,
                           funding_per_h=0.001, contracts={})
            r = P.run({"BTC": m}, {"BTC": [s]}, cfg)
            self.assertEqual(sign, 1 if r["trades"][0]["pnl"] > 0 else -1)  # long pays, short receives

    def test_gap_through_stop_fills_at_open(self):
        px = [100, 100, 100, 80, 80]
        m = Market(bars(px), "BTC", H)
        s = Script(m, {1: {"side": 1, "stop": 95.0, "target": None}})
        r = P.run({"BTC": m}, {"BTC": [s]}, P.Config("spot", equity=1000, risk=0.01, costs=ZERO))
        self.assertEqual(r["trades"][0]["why"], "stop_gap")
        self.assertAlmostEqual(r["trades"][0]["exit"], 80.0)

    def test_drawdown_policy_flattens_and_halts(self):
        px = [100] * 3 + [80] * 10
        m = Market(bars(px), "BTC", H)
        s = Script(m, {1: {"side": 1, "stop": 10.0, "target": None}})
        cfg = P.Config("spot", equity=1000, risk=1.0, costs=ZERO, dd_policy=True, resume_days=999)
        r = P.run({"BTC": m}, {"BTC": [s]}, cfg)
        self.assertTrue(any(e[1] == "halt" for e in r["events"]))
        self.assertEqual(r["trades"][0]["why"], "dd_flatten")


class Stats(unittest.TestCase):
    def test_dsr_penalizes_many_trials(self):
        rnd = random.Random(1)
        e, curve = 1000.0, []
        for k in range(800):
            e *= 1 + rnd.gauss(0.0008, 0.02)
            curve.append((T0 + k * 86400, e))
        one = M.deflated_sharpe(curve, 1)["dsr"]
        many = M.deflated_sharpe(curve, 200)["dsr"]
        self.assertGreater(one, many)

    def test_block_bootstrap_runs(self):
        curve = [(T0 + k * 86400, 1000 * (1.001 ** k)) for k in range(400)]
        b = M.block_bootstrap(curve, runs=200)
        self.assertGreater(b["cagr_p5"], 0)


class WalkForward(unittest.TestCase):
    def test_training_score_ignores_trades_that_exit_after_the_window(self):
        import corrected_tournament as CT
        trades = [{"t0": 10, "t1": 20, "R": 1.0}] * 8 + [{"t0": 15, "t1": 200, "R": 50.0}]
        s_in = CT.score(trades, 0, 100)
        self.assertAlmostEqual(s_in, 1.0 * (8 ** 0.5))  # the boundary-spanning +50R trade is excluded


class Candidates(unittest.TestCase):
    def test_candidates_have_no_lookahead(self):
        rnd = random.Random(5)
        p, raw = 100.0, []
        for k in range(24 * 400):
            o = p
            p *= 1 + rnd.gauss(0.0001, 0.006)
            raw.append((T0 + k * H, o, max(o, p) * 1.002, min(o, p) * 0.998, p, 5.0))
        cut = 24 * 330
        for cls in (C.VolManagedTrend, C.VolFilteredBreakout):
            a, b = cls(Market(raw[:cut], "BTC", H)), cls(Market(raw, "BTC", H))
            for i in range(cut - 24 * 20, cut):
                ea, eb = a.entry(i), b.entry(i)
                self.assertEqual(ea is None, eb is None, "%s differs at %d" % (cls.id, i))


if __name__ == "__main__":
    unittest.main()
