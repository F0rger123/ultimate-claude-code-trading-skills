"""SQLite journal: trades, equity snapshots, events. One file, safe to copy for backups."""
import json
import sqlite3
import threading
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mode TEXT NOT NULL,              -- forward | paper | live
  strategy TEXT NOT NULL, symbol TEXT NOT NULL, side INTEGER NOT NULL,
  contracts REAL NOT NULL, entry REAL NOT NULL, stop REAL NOT NULL, target REAL,
  t0 INTEGER NOT NULL, exit REAL, t1 INTEGER, why TEXT,
  pnl_usd REAL, fees_usd REAL, R REAL, risk_usd REAL, leverage REAL,
  status TEXT NOT NULL DEFAULT 'open', feat TEXT, broker_ref TEXT
);
CREATE INDEX IF NOT EXISTS trades_status ON trades(status, mode);
CREATE TABLE IF NOT EXISTS equity (t INTEGER NOT NULL, mode TEXT NOT NULL, equity REAL NOT NULL);
CREATE TABLE IF NOT EXISTS events (t INTEGER NOT NULL, level TEXT NOT NULL, msg TEXT NOT NULL);
"""


class Journal:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.lock = threading.Lock()
        with self.lock:
            self.db.executescript(SCHEMA)
            self.db.commit()

    def _x(self, sql, args=()):
        with self.lock:
            cur = self.db.execute(sql, args)
            self.db.commit()
            return cur

    def q(self, sql, args=()):
        with self.lock:
            return [dict(r) for r in self.db.execute(sql, args).fetchall()]

    def open_trade(self, mode, strategy, symbol, side, contracts, entry, stop, target, t0, risk_usd,
                   leverage, feat=None, broker_ref=None):
        cur = self._x("INSERT INTO trades(mode,strategy,symbol,side,contracts,entry,stop,target,t0,risk_usd,"
                      "leverage,feat,broker_ref) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
                      (mode, strategy, symbol, side, contracts, entry, stop, target, int(t0), risk_usd,
                       leverage, json.dumps(feat or {}), broker_ref))
        return cur.lastrowid

    def close_trade(self, tid, exit_px, t1, why, pnl_usd, fees_usd, R):
        self._x("UPDATE trades SET exit=?, t1=?, why=?, pnl_usd=?, fees_usd=?, R=?, status='closed' WHERE id=?",
                (exit_px, int(t1), why, pnl_usd, fees_usd, R, tid))

    def open_trades(self, mode=None):
        if mode:
            return self.q("SELECT * FROM trades WHERE status='open' AND mode=? ORDER BY t0", (mode,))
        return self.q("SELECT * FROM trades WHERE status='open' ORDER BY t0")

    def closed_trades(self, mode=None, since=0, limit=10000):
        if mode:
            return self.q("SELECT * FROM trades WHERE status='closed' AND mode=? AND t1>=? ORDER BY t1 DESC LIMIT ?",
                          (mode, since, limit))
        return self.q("SELECT * FROM trades WHERE status='closed' AND t1>=? ORDER BY t1 DESC LIMIT ?", (since, limit))

    def snap(self, mode, equity, t=None):
        self._x("INSERT INTO equity(t,mode,equity) VALUES(?,?,?)", (int(t or time.time()), mode, equity))

    def equity_curve(self, mode, since=0):
        return self.q("SELECT t, equity FROM equity WHERE mode=? AND t>=? ORDER BY t", (mode, since))

    def event(self, level, msg):
        self._x("INSERT INTO events(t,level,msg) VALUES(?,?,?)", (int(time.time()), level, msg))

    def events(self, limit=50):
        return self.q("SELECT * FROM events ORDER BY t DESC LIMIT ?", (limit,))

    def realized_since(self, mode, t):
        r = self.q("SELECT COALESCE(SUM(pnl_usd),0) AS s, COUNT(*) AS n FROM trades WHERE mode=? AND status='closed' "
                   "AND t1>=?", (mode, t))[0]
        return r["s"], r["n"]

    def opened_since(self, mode, t):
        return self.q("SELECT COUNT(*) AS n FROM trades WHERE mode=? AND t0>=?", (mode, t))[0]["n"]
