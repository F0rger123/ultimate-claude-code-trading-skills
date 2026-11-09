"""Correctness tests for the MNQ opening-range model (SYNTHETIC: no profitability meaning)."""
import calendar
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "research"))
import mnq_opening_range as O  # noqa: E402


def ny_to_utc(y, mo, d, h, mi):
    guess = calendar.timegm((y, mo, d, h, mi, 0)) + 5 * 3600
    off = O.ny_offset_hours(guess)
    return calendar.timegm((y, mo, d, h, mi, 0)) - off * 3600


def session(y, mo, d, path, start=(9, 0)):
    """path: list of (o, h, l, c) for consecutive 15m bars starting at `start` New York time."""
    t = ny_to_utc(y, mo, d, *start)
    return [(t + k * 900, o, h, l, c, 100.0) for k, (o, h, l, c) in enumerate(path)]


class Clock(unittest.TestCase):
    def test_dst_offsets(self):
        self.assertEqual(O.ny_offset_hours(calendar.timegm((2026, 1, 15, 15, 0, 0))), -5)
        self.assertEqual(O.ny_offset_hours(calendar.timegm((2026, 7, 15, 15, 0, 0))), -4)
        # 2026 DST starts Sunday March 8 at 07:00 UTC and ends Sunday November 1 at 06:00 UTC
        self.assertEqual(O.ny_offset_hours(calendar.timegm((2026, 3, 8, 6, 59, 0))), -5)
        self.assertEqual(O.ny_offset_hours(calendar.timegm((2026, 3, 8, 7, 0, 0))), -4)
        self.assertEqual(O.ny_offset_hours(calendar.timegm((2026, 11, 1, 5, 59, 0))), -4)
        self.assertEqual(O.ny_offset_hours(calendar.timegm((2026, 11, 1, 6, 0, 0))), -5)

    def test_range_bar_is_915_ny_in_summer_and_winter(self):
        for (y, mo, d) in ((2026, 1, 14), (2026, 7, 15)):
            t = ny_to_utc(y, mo, d, 9, 15)
            self.assertEqual(O.ny_parts(t)[3:], (9, 15))


class Rules(unittest.TestCase):
    def base_path(self):
        # 9:00, 9:15 (range 100-104), 9:30 inside, 9:45 closes 105 (breakout, low 103), 10:00 opens 105
        return [(100, 101, 99, 100), (101, 104, 100, 102), (102, 103.5, 101, 103), (103, 106, 103, 105),
                (105, 105.5, 104.75, 105.25)] + [(105.25, 105.5, 105, 105.25)] * 30

    def test_long_breakout_fill_stop_target_from_actual_fill(self):
        bars = session(2026, 7, 15, self.base_path())
        r = O.simulate(bars, slip_ticks=0, commission=0.0)
        tr = r["trades"][0]
        self.assertEqual(tr["side"], 1)
        self.assertEqual(tr["fill"], 105.0)           # next bar open, not the signal close
        self.assertEqual(tr["stop"], 103.0)           # breakout candle low
        self.assertEqual(tr["target"], 106.0)         # fill + 0.5 x (105 - 103)
        self.assertEqual(tr["why"], "flatten_1545")   # price never reaches 106 or 103

    def test_one_trade_per_session_and_no_entry_before_range(self):
        path = [(100, 110, 99, 109)] + self.base_path()[1:]  # 9:00 bar spikes above: no range yet, ignored
        bars = session(2026, 7, 15, path)
        r = O.simulate(bars, slip_ticks=0, commission=0.0)
        self.assertEqual(r["n"], 1)
        self.assertGreaterEqual(O.ny_parts(r["trades"][0]["t0"])[3:], (9, 30))

    def test_stop_first_when_both_hit(self):
        path = self.base_path()
        path[4] = (105, 107, 102, 104)  # fill bar spans both target (106) and stop (103)
        r = O.simulate(session(2026, 7, 15, path), slip_ticks=0, commission=0.0)
        self.assertEqual(r["trades"][0]["why"], "stop")

    def test_gap_that_invalidates_stop_means_no_trade(self):
        path = self.base_path()
        path[4] = (102.5, 103, 102, 102.5)  # opens below the breakout low (103)
        r = O.simulate(session(2026, 7, 15, path), slip_ticks=0, commission=0.0)
        self.assertEqual(r["n"], 0)

    def test_breakeven_math(self):
        self.assertAlmostEqual(O.simulate([], target_r=0.5)["breakeven_win_rate_before_costs"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
