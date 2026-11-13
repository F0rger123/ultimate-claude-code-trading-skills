"""Weekly paper shake-up: who gets cut, what replaces them, and that losses stay counted."""
import json
import os
import shutil
import tempfile
import unittest

from tradedesk import paper as PA
from tradedesk import risk as RK
from tradedesk import rotation as R

DAY = 86400


class FakeJournal:
    def __init__(self):
        self.events = []

    def event(self, level, msg):
        self.events.append((level, msg))


class RotationTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp()
        os.makedirs(os.path.join(self.dir, "paper"))
        RK.save_rules(os.path.join(self.dir, "rules.json"), RK.normalize({}))
        self.now = R.slot(1794700000) + 3600  # a Monday after the run time
        pnl = {"pb_trend_perp": 3.0, "pb_vmt_perp": -1.0, "pb_breakout_perp": -2.0, "pb_rotation_spot": 0.5,
               "pb_pilot_spot50": -50.0, "pb_fast_mtf": -4.0, "pb_fast_vwap": 1.0, "pb_fast_rsi2": -6.0,
               "pb_fast_scalp10": -0.5}
        for b in PA.BOOKS:
            age = 30 if b["cadence"] == "slow" else 7
            if b["id"] == "pb_fast_scalp10":
                age = 2  # still on trial
            start = self.now - age * DAY
            eq = b["equity"] * (1 + pnl[b["id"]] / 100)
            bk = {"id": b["id"], "name": b["name"], "start": start, "start_equity": b["equity"], "equity": eq,
                  "pnl": eq - b["equity"], "closed": 3, "open": [], "pending": [], "events": [], "trades": [],
                  "curve": [[start, b["equity"]], [self.now - 3600, eq]], "cadence": b["cadence"]}
            with open(os.path.join(self.dir, "paper", b["id"] + ".json"), "w") as f:
                json.dump(bk, f)
        self.orig = R.screen
        R.screen = lambda cls, params, cadence, markets, now: {
            "ret_pct": 2.0 if cls.id == "donchian_4h" else -1.0, "max_dd_pct": 1.0, "trades": 9, "days": 21,
            "enough": True, "score": (5.0 if cls.id == "donchian_4h" else 1.0) + len(params) * 0.01}

    def tearDown(self):
        R.screen = self.orig
        shutil.rmtree(self.dir, ignore_errors=True)

    def run_once(self, **kw):
        return R.run(self.dir, FakeJournal(), now=self.now, markets_for=lambda c: {}, log=lambda *a: None, **kw)

    def test_cuts_bottom_three_eligible_only(self):
        e = self.run_once()
        cut = [r["id"] for r in e["cut"]]
        # the pilot mirror (-50%) is protected and the scalper is on trial; the worst three others go
        self.assertEqual(cut, ["pb_fast_rsi2", "pb_fast_mtf", "pb_breakout_perp"])
        ids = [b["id"] for b in PA.roster(self.dir)]
        self.assertIn("pb_pilot_spot50", ids)
        self.assertIn("pb_fast_scalp10", ids)
        self.assertEqual(len(ids), len(PA.BOOKS))  # same number of accounts after the swap
        speeds = [b["cadence"] for b in PA.roster(self.dir) if b["id"] in {s["id"] for s in e["added"]}]
        self.assertEqual(sorted(speeds), ["fast", "fast", "slow"])  # replacements keep the cut accounts' speed
        self.assertTrue(any(s["cls"] == "donchian_4h" for s in e["added"]))  # best test wins a fast slot

    def test_retired_loss_left_out_of_display_but_not_halt(self):
        before = PA.rebuild(self.dir, FakeJournalDB(), RK.load_rules(os.path.join(self.dir, "rules.json")), self.now)
        self.run_once()
        after = PA.rebuild(self.dir, FakeJournalDB(), RK.load_rules(os.path.join(self.dir, "rules.json")), self.now)
        cut_pnl = (-6.0 - 4.0 - 2.0) * 100  # the three retired $10,000 accounts
        self.assertAlmostEqual(after["retired_pnl"], cut_pnl, places=6)
        # the displayed total leaves retired accounts out; the drawdown halt still counts them
        self.assertAlmostEqual(after["total_equity"], before["total_equity"] - 30000 - cut_pnl, places=6)
        self.assertAlmostEqual(after["total_with_retired"], before["total_equity"] - 30000, places=6)

    def test_once_a_week_and_memory(self):
        self.run_once()
        self.assertIsNone(self.run_once())  # already ran this week
        led = R.load_ledger(self.dir)
        self.assertEqual(led["families"]["rsi2_reversion"]["paper_pct"], [-6.0])
        self.assertIn('rsi2_reversion|{}', led["tried"])  # the cut setting cools down for 8 weeks

    def test_owner_replace_skips_trial_and_keeps_monday(self):
        e = self.run_once(replace=["pb_fast_scalp10", "pb_fast_vwap", "pb_pilot_spot50"])
        self.assertEqual(sorted(r["id"] for r in e["cut"]), ["pb_fast_scalp10", "pb_fast_vwap"])  # pilot protected
        self.assertTrue(e["manual"])
        self.assertNotEqual(R.load_ledger(self.dir).get("last_week"), R.week_key(self.now))  # Monday still runs
        self.assertEqual(len(PA.roster(self.dir)), len(PA.BOOKS))

    def test_winners_never_cut(self):
        e = self.run_once()
        self.assertTrue(all(r["pnl_pct"] < 0 for r in e["cut"]))
        self.assertIn("pb_trend_perp", [b["id"] for b in PA.roster(self.dir)])  # +3%, past trial

    def test_kill_switch_blocks_shake_up(self):
        rules = RK.load_rules(os.path.join(self.dir, "rules.json"))
        rules["kill_switch"] = True
        RK.save_rules(os.path.join(self.dir, "rules.json"), rules)
        self.assertIsNone(self.run_once())

    def test_due_waits_a_week_after_first_check(self):
        self.assertFalse(R.due(self.dir, self.now))  # first check only starts the clock
        self.assertTrue(R.due(self.dir, self.now + 7 * DAY))


class FakeJournalDB:
    """Minimal journal for rebuild(): an in-memory SQLite with the paper tables."""

    def __init__(self):
        import sqlite3
        import threading
        self.lock = threading.Lock()
        self.db = sqlite3.connect(":memory:")
        self.db.execute("CREATE TABLE equity(t INTEGER, mode TEXT, equity REAL)")
        self.db.execute("CREATE TABLE trades(id INTEGER PRIMARY KEY, mode TEXT, strategy TEXT, symbol TEXT, side INTEGER,"
                        " contracts REAL, entry REAL, stop REAL, target REAL, t0 INTEGER, exit REAL, t1 INTEGER, why TEXT,"
                        " pnl_usd REAL, fees_usd REAL, R REAL, risk_usd REAL, leverage REAL, status TEXT, feat TEXT)")

    def event(self, *a):
        pass


if __name__ == "__main__":
    unittest.main()
