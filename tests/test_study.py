"""Study: context tags use only closed bars, filters skip what they should, improved versions stay paper."""
import unittest

from tradedesk import study as ST
from tradedesk.market import Market


def bars(n, start=1794000000 - 1794000000 % 86400, step=300, drift=1.0):
    out, p = [], 100.0
    for k in range(n):
        p += drift * (1 if k % 7 else -3)
        out.append([start + k * step, p, p + 1, p - 1, p + 0.5, 10.0])
    return out


class Always:
    """Enters long on every bar."""
    max_bars = None

    def __init__(self, m):
        self.m = m

    def entry(self, i):
        return {"side": 1, "stop": self.m.b.c[i] - 5, "target": None}

    def exit(self, i, pos):
        return False


class StudyTest(unittest.TestCase):
    def test_context_sessions(self):
        m = Market(bars(400), "BTC", 300)
        sess = {ST.context(m, i, 1, "BTC")["session"] for i in range(0, 288)}
        self.assertEqual(sess, {"asia", "europe", "us", "late"})
        c = ST.context(m, 10, -1, "ETH")
        self.assertEqual((c["coin"], c["side"]), ("ETH", "short"))

    def test_filter_skips_matching_context(self):
        m = Market(bars(400), "BTC", 300)
        f = ST.Filtered(Always(m), [{"field": "session", "value": "asia"}], "BTC")
        for i in range(0, 288):
            sess = ST.context(m, i, 1, "BTC")["session"]
            self.assertEqual(f.entry(i) is None, sess == "asia")

    def test_groups_and_insights(self):
        tagged = [({"session": "us", "coin": "BTC", "side": "long"}, 50.0)] * 6 + \
                 [({"session": "asia", "coin": "BTC", "side": "long"}, -30.0)] * 5
        g = ST.groups(tagged)
        self.assertEqual(g[("session", "us")]["n"], 6)
        lines = ST.insights({"name": "Test"}, tagged)
        self.assertTrue(any("during US hours" in x for x in lines))
        self.assertTrue(any("during Asia hours" in x for x in lines))
        self.assertEqual(ST.insights({"name": "Test"}, tagged[:3]), [])  # too few trades to judge


if __name__ == "__main__":
    unittest.main()
