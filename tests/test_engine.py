import json
import os
import random
import sys
import tempfile
import threading
import unittest
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tradedesk import backtest as B  # noqa: E402
from tradedesk import data as D  # noqa: E402
from tradedesk import indicators as I  # noqa: E402
from tradedesk import ladder as L  # noqa: E402
from tradedesk import learn as LN  # noqa: E402
from tradedesk import risk as R  # noqa: E402
from tradedesk import strategies as S  # noqa: E402
from tradedesk.market import Market  # noqa: E402

T0 = 1700006400 - 1700006400 % 14400


def walk(n=12000, seed=3, vol=0.002, drift=0.0):
    rnd = random.Random(seed)
    p, out = 30000.0, []
    for k in range(n):
        o = p
        p *= 1 + rnd.gauss(drift, vol)
        h = max(o, p) * (1 + abs(rnd.gauss(0, vol / 3)))
        lo = min(o, p) * (1 - abs(rnd.gauss(0, vol / 3)))
        out.append((T0 + 300 * k, o, h, lo, p, rnd.uniform(5, 50)))
    return out


class Indicators(unittest.TestCase):
    def test_sma_ema(self):
        xs = [1, 2, 3, 4, 5]
        self.assertEqual(I.sma(xs, 3), [None, None, 2.0, 3.0, 4.0])
        e = I.ema(xs, 3)
        self.assertEqual(e[2], 2.0)
        self.assertAlmostEqual(e[3], 3.0)

    def test_rsi_bounds(self):
        r = I.rsi([float(x) for x in range(1, 40)], 14)
        self.assertEqual(r[-1], 100.0)

    def test_supertrend_flips(self):
        up = [100 + k for k in range(60)]
        dn = [160 - 2 * k for k in range(60)]
        c = up + dn
        d = I.supertrend([x + 1 for x in c], [x - 1 for x in c], c, 10, 3)
        self.assertEqual(d[55], 1)
        self.assertEqual(d[-1], -1)


class Data(unittest.TestCase):
    def test_resample_complete_buckets_only(self):
        bars = walk(30)
        r = D.resample(bars, 900)
        self.assertTrue(all(b[0] % 900 == 0 for b in r))
        self.assertEqual(len(r), 10)
        self.assertEqual(r[0][1], bars[0][1])
        self.assertEqual(r[0][4], bars[2][4])
        self.assertEqual(r[0][2], max(b[2] for b in bars[:3]))

    def test_save_load_roundtrip(self):
        bars = walk(50)
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "x.csv.gz")
            D.save(p, bars)
            self.assertEqual(D.load(p), bars)


class NoLookahead(unittest.TestCase):
    def test_entries_do_not_change_when_future_bars_arrive(self):
        bars = walk(9000)
        cut = 7000
        for cls in S.ALL:
            a = cls(Market(bars[:cut], "BTC"))
            b = cls(Market(bars, "BTC"))
            for i in range(cut - 400, cut):
                ea, eb = a.entry(i), b.entry(i)
                self.assertEqual(ea is None, eb is None, "%s differs at %d" % (cls.id, i))
                if ea:
                    self.assertAlmostEqual(ea["stop"], eb["stop"], places=6)

    def test_htf_map_uses_closed_bars(self):
        m = Market(walk(100), "BTC")
        f = m.frame(3600)
        for i, j in enumerate(m.maps[3600]):
            if j >= 0:
                self.assertLessEqual(f.t[j] + 3600, m.b.t[i] + 300)


class Fills(unittest.TestCase):
    def test_stop_wins_when_both_hit_and_gap_fills_at_open(self):
        class One(S.Strategy):
            id = "one"

            def entry(self, i):
                return {"side": 1, "stop": 99.0, "target": 101.0} if i == 1 else None

        bars = [(T0, 100, 100, 100, 100, 1), (T0 + 300, 100, 100, 100, 100, 1),
                (T0 + 600, 100, 102, 98, 100, 1), (T0 + 900, 100, 100, 100, 100, 1)]
        tr = B.run(One(Market(bars)), costs={"fee": 0, "slip": 0, "funding_per_h": 0})
        self.assertEqual(len(tr), 1)
        self.assertEqual(tr[0]["why"], "stop")
        self.assertAlmostEqual(tr[0]["R"], -1.0)
        bars[2] = (T0 + 600, 100, 100.5, 99.5, 100, 1)
        bars[3] = (T0 + 900, 97, 97, 96, 96, 1)
        bars.append((T0 + 1200, 96, 96, 96, 96, 1))
        tr = B.run(One(Market(bars)), costs={"fee": 0, "slip": 0, "funding_per_h": 0})
        self.assertEqual(tr[0]["why"], "stop_gap")
        self.assertAlmostEqual(tr[0]["R"], -3.0)

    def test_costs_reduce_R(self):
        s = S.DonchianBreakout(Market(walk(6000)))
        a = B.run(s)
        z = B.run(s, costs={"fee": 0, "slip": 0, "funding_per_h": 0})
        self.assertLess(sum(t["R"] for t in a), sum(t["R"] for t in z))

    def test_simulate_caps_leverage_and_liquidates(self):
        t = {"t0": 0, "t1": 1, "d": 0.001, "ret": -0.2, "mae": 0.2, "why": "stop", "R": -200}
        out, _ = B.simulate([t], equity=1000, risk=0.01, max_lev=5)
        self.assertAlmostEqual(out[0]["lev"], 5.0)
        self.assertTrue(out[0]["liquidated"])
        self.assertAlmostEqual(out[0]["pnl"], -1000.0)  # margin = 5000 notional / 5x


class Risk(unittest.TestCase):
    def setUp(self):
        self.r = R.normalize({})

    def test_floors_cannot_disable_guardrails(self):
        r = R.normalize({"daily_loss_cap_usd": 0, "max_leverage": 0, "max_open_positions": 0})
        self.assertGreaterEqual(r["daily_loss_cap_usd"], 1)
        self.assertGreaterEqual(r["max_leverage"], 1)
        self.assertGreaterEqual(r["max_open_positions"], 1)

    def test_size_respects_budget_and_leverage(self):
        n, loss, lev, lim = R.size(self.r, "BTC", 10000, 75000, 74250, 0.01)
        self.assertLessEqual(loss, 30.0 + 1e-9)
        self.assertLessEqual(lev, R.lev_cap(self.r, "BTC") + 1e-9)
        self.assertEqual(n, 4)

    def test_check_blocks(self):
        o = {"symbol": "BTC", "side": 1, "entry": 100, "stop": 101, "contracts": 1, "loss_usd": 5, "leverage": 1, "t": 0}
        ok, why = R.check(self.r, o, {})
        self.assertFalse(ok)
        self.assertIn("stop is not below entry for a long", why)
        o["stop"] = 99
        ok, why = R.check(dict(self.r, kill_switch=True), o, {})
        self.assertIn("kill switch is on", why)
        ok, why = R.check(self.r, o, {"realized_today_usd": -149})
        self.assertFalse(ok)
        ok, why = R.check(self.r, o, {})
        self.assertTrue(ok, why)


class Ladder(unittest.TestCase):
    def test_backtest_gate(self):
        m = {"trades": 150, "profit_factor": 1.3, "max_drawdown": 0.1}
        w = [{"test_trades": 10, "test_R": 1}] * 7 + [{"test_trades": 10, "test_R": -1}] * 3
        ok, _ = L.check_backtest(m, {"runs": 1, "p5_return": 0.02}, w)
        self.assertTrue(ok)
        ok, _ = L.check_backtest(dict(m, profit_factor=1.1), {"runs": 1, "p5_return": 0.02}, w)
        self.assertFalse(ok)

    def test_demote(self):
        bad = [{"R": -1}] * 30 + [{"R": 1}] * 20
        self.assertTrue(L.should_demote(bad)[0])


class Learn(unittest.TestCase):
    def test_proposes_bad_pocket(self):
        tr = [{"R": 1.0, "feat": {"hour_utc": 3}} for _ in range(60)] + \
             [{"R": -1.0, "feat": {"hour_utc": 15}} for _ in range(40)]
        props = LN.propose(tr)
        self.assertTrue(any(p["skip_field"] == "hour_utc" and p["skip_value"] == 15 for p in props))

    def test_proposals_come_from_first_half_only(self):
        tr = [{"t0": k, "R": 1.0, "feat": {"hour_utc": 3}} for k in range(100)] +              [{"t0": 100 + k, "R": -1.0, "feat": {"hour_utc": 15}} for k in range(100)]
        props, cut = LN.propose_first_half(tr)
        self.assertEqual(cut, 100)
        self.assertFalse(any(p["skip_value"] == 15 for p in props))


class Server(unittest.TestCase):
    def test_token_and_live_confirm(self):
        from http.server import ThreadingHTTPServer
        from tradedesk import server as SV
        with tempfile.TemporaryDirectory() as d:
            api = SV.Api(d)
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), SV.make_handler(api, "t" * 30))
            th = threading.Thread(target=httpd.serve_forever, daemon=True)
            th.start()
            base = "http://127.0.0.1:%d" % httpd.server_address[1]

            def call(path, token=None, body=None):
                req = urllib.request.Request(base + path, data=None if body is None else json.dumps(body).encode(),
                                             headers={"Authorization": "Bearer " + token} if token else {})
                try:
                    with urllib.request.urlopen(req) as r:
                        return r.status, json.loads(r.read())
                except urllib.error.HTTPError as e:
                    return e.code, json.loads(e.read())

            self.assertEqual(call("/api/summary")[0], 401)
            code, s = call("/api/summary", "t" * 30)
            self.assertEqual(code, 200)
            self.assertEqual(s["mode"], "paper")
            self.assertEqual(call("/api/rules", "t" * 30, {"live_enabled": True})[0], 400)
            code, r = call("/api/rules", "t" * 30, {"rules": {"live_enabled": True}, "confirm": SV.LIVE_CONFIRM})
            self.assertEqual(code, 200)
            self.assertTrue(r["live_enabled"])
            self.assertEqual(call("/api/summary", "t" * 30)[1]["mode"], "paper")  # TRADEDESK_LIVE not set
            self.assertTrue(call("/api/kill", "t" * 30, {})[1]["kill_switch"])
            httpd.shutdown()
            api.j.db.close()


if __name__ == "__main__":
    unittest.main()
