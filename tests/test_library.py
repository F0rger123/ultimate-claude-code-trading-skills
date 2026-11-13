"""Strategy bank: every strategy runs, and a signal at bar i never depends on bars after i."""
import math
import random
import unittest

from tradedesk import library as LIB
from tradedesk import portfolio as P
from tradedesk import strategies as S
from tradedesk.market import Market


def walk(n, step, seed, start=1700006400):
    """Trending random walk with regime changes (start is a Monday 00:00 UTC)."""
    rng = random.Random(seed)
    out, p, drift = [], 100.0, 0.0
    for k in range(n):
        if k % 400 == 0:
            drift = rng.choice([-1, 1]) * rng.uniform(0.0002, 0.0012) * math.sqrt(step / 300)
        r = drift + rng.gauss(0, 0.002 * math.sqrt(step / 300))
        o = p
        p = max(1.0, p * math.exp(r))
        hi, lo = max(o, p) * (1 + abs(rng.gauss(0, 0.001))), min(o, p) * (1 - abs(rng.gauss(0, 0.001)))
        out.append([start + k * step, o, hi, lo, p, rng.uniform(50, 150) * (3 if rng.random() < 0.05 else 1)])
    return out


SLOW = walk(24 * 330, 3600, 1)
FAST = walk(288 * 45, 300, 2)


def data(cls):
    return (FAST, 300) if getattr(cls, "cadence", "slow") == "fast" else (SLOW, 3600)


class LibraryTest(unittest.TestCase):
    def test_all_have_ids_and_cadence(self):
        ids = [c.id for c in LIB.ALL]
        self.assertEqual(len(ids), len(set(ids)))
        known = {c.id for c in S.ALL}
        self.assertFalse(known & set(ids))
        for c in LIB.ALL:
            self.assertIn(c.cadence, ("fast", "slow"))
            self.assertLessEqual(len(c.grid), 3)

    def test_runs_and_trades_somewhere(self):
        fired = 0
        for cls in LIB.ALL:
            bars, base = data(cls)
            m = Market(bars, "BTC", base)
            s = cls(m)
            sigs = [i for i in range(len(bars)) if s.entry(i)]
            fired += bool(sigs)
            for i in sigs[:5]:
                sg = s.entry(i)
                self.assertIn(sg["side"], (1, -1))
                self.assertGreater((m.b.c[i] - sg["stop"]) * sg["side"], 0, cls.id)
            cfg = P.Config("perp", equity=10000.0, risk=0.01, pos_lev=1.5, gross_lev=1.5)
            P.run({"BTC": m}, {"BTC": [s]}, cfg)  # no exception through the engine
        self.assertGreater(fired, len(LIB.ALL) // 2)

    def test_no_look_ahead(self):
        rng = random.Random(7)
        for cls in LIB.ALL:
            bars, base = data(cls)
            full = cls(Market(bars, "BTC", base))
            sigs = [i for i in range(len(bars) // 2, len(bars) - 1) if full.entry(i)]
            probe = sigs[:3] + rng.sample(range(len(bars) // 2, len(bars) - 1), 3)
            for i in probe:
                cut = cls(Market(bars[:i + 1], "BTC", base))
                a, b = full.entry(i), cut.entry(i)
                self.assertEqual(a is None, b is None, "%s at %d" % (cls.id, i))
                if a:
                    self.assertAlmostEqual(a["stop"], b["stop"], places=6, msg=cls.id)

    def test_winner_gates_off_by_default(self):
        m = Market(FAST, "BTC", 300)
        base, gated = S.EMAPullback1h(m), S.EMAPullback1h(m, adx_min=0, min_atr_frac=0, weekday_only=0)
        self.assertEqual([i for i in range(len(FAST)) if base.entry(i)],
                         [i for i in range(len(FAST)) if gated.entry(i)])
        strict = S.EMAPullback1h(m, adx_min=99)
        self.assertEqual([i for i in range(len(FAST)) if strict.entry(i)], [])


if __name__ == "__main__":
    unittest.main()
