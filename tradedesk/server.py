"""Phone API. Standard library HTTP server with a bearer token.

Run: TRADEDESK_API_TOKEN=<long random string> python -m tradedesk serve --host <tailscale ip>
Bind it to your Tailscale address (100.x.y.z), not 0.0.0.0, so only your own devices reach it.
"""
import calendar
import hmac
import json
import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from . import ladder as L
from . import risk as R
from . import strategies as S
from .journal import Journal

LIVE_CONFIRM = "I understand real money is at risk"


class Api:
    def __init__(self, state_dir):
        self.dir = state_dir
        self.j = Journal(os.path.join(state_dir, "journal.sqlite"))
        self.rules_path = os.path.join(state_dir, "rules.json")

    def mode(self, rules):
        return "live" if rules["live_enabled"] and os.environ.get("TRADEDESK_LIVE") == "1" else "paper"

    def summary(self, q):
        rules = R.load_rules(self.rules_path)
        mode = self.mode(rules)
        closed = self.j.closed_trades(mode)
        pnl = sum(t["pnl_usd"] or 0 for t in closed)
        start = rules["paper_equity_usd"]
        now = int(time.time())
        today, _ = self.j.realized_since(mode, now - now % 86400)
        wins = [t for t in closed if (t["pnl_usd"] or 0) > 0]
        gw = sum(t["pnl_usd"] for t in wins)
        gl = -sum(t["pnl_usd"] or 0 for t in closed if (t["pnl_usd"] or 0) <= 0)
        curve = [r["equity"] for r in self.j.equity_curve(mode)]
        peak, mdd = (curve[0] if curve else start), 0.0
        for e in curve:
            peak = max(peak, e)
            mdd = max(mdd, (peak - e) / peak if peak else 0)
        lad = L.Ladder(os.path.join(self.dir, "ladder.json"))
        running = sum(1 for v in lad.d.values() if v.get("stage") in ("forward", "paper", "small_live", "scaled"))
        return {"mode": mode, "balance": start + pnl, "pnl_all": pnl, "pnl_all_pct": pnl / start if start else 0,
                "pnl_today": today, "win_rate": len(wins) / len(closed) if closed else None,
                "profit_factor": (gw / gl) if gl > 0 else None, "max_drawdown": mdd,
                "open_trades": self.trades({"status": ["open"]})["trades"], "strategies_running": running,
                "kill_switch": rules["kill_switch"], "events": self.j.events(10)}

    def trades(self, q):
        status = (q.get("status") or ["closed"])[0]
        rules = R.load_rules(self.rules_path)
        mode = (q.get("mode") or [self.mode(rules)])[0]
        rows = self.j.open_trades(mode) if status == "open" else self.j.closed_trades(mode, limit=200)
        names = {s.id: s.name for s in S.ALL}
        for r in rows:
            r["strategy_name"] = names.get(r["strategy"], r["strategy"])
            r.pop("feat", None)
        return {"mode": mode, "status": status, "trades": rows}

    def equity(self, q):
        rules = R.load_rules(self.rules_path)
        mode = self.mode(rules)
        rng = (q.get("range") or ["1M"])[0]
        secs = {"1D": 86400, "1W": 7 * 86400, "1M": 30 * 86400, "ALL": 10 ** 10}.get(rng.upper(), 30 * 86400)
        pts = self.j.equity_curve(mode, int(time.time()) - secs)
        step = max(1, len(pts) // 200)
        return {"mode": mode, "range": rng, "points": pts[::step] + (pts[-1:] if pts and len(pts) % step else [])}

    def calendar(self, q):
        rules = R.load_rules(self.rules_path)
        mode = self.mode(rules)
        ym = (q.get("month") or [time.strftime("%Y-%m", time.gmtime())])[0]
        y, m = int(ym[:4]), int(ym[5:7])
        a = calendar.timegm((y, m, 1, 0, 0, 0))
        b = calendar.timegm((y + (m == 12), m % 12 + 1, 1, 0, 0, 0))
        days = {}
        for t in self.j.q("SELECT t1, pnl_usd, strategy FROM trades WHERE mode=? AND status='closed' AND t1>=? AND t1<?",
                          (mode, a, b)):
            d = time.gmtime(t["t1"]).tm_mday
            e = days.setdefault(d, {"day": d, "pnl": 0.0, "trades": 0, "wins": 0, "by": {}})
            e["pnl"] += t["pnl_usd"] or 0
            e["trades"] += 1
            e["wins"] += 1 if (t["pnl_usd"] or 0) > 0 else 0
            e["by"][t["strategy"]] = e["by"].get(t["strategy"], 0) + (t["pnl_usd"] or 0)
        out = []
        for d in sorted(days):
            e = days[d]
            e["best"] = max(e["by"], key=e["by"].get) if e["by"] else None
            e.pop("by")
            out.append(e)
        return {"mode": mode, "month": ym, "first_weekday": calendar.weekday(y, m, 1),
                "days_in_month": calendar.monthrange(y, m)[1], "days": out}

    def strategies(self, q):
        lad = L.Ladder(os.path.join(self.dir, "ladder.json"))
        out = []
        for cls in S.ALL:
            for k, v in sorted(lad.d.items()):
                sid, sym = k.split(":")
                if sid != cls.id:
                    continue
                live = self.j.q("SELECT COUNT(*) AS n, COALESCE(SUM(pnl_usd),0) AS p FROM trades WHERE strategy=? "
                                "AND symbol=? AND status='closed' AND mode IN ('forward','paper','live')", (sid, sym))[0]
                out.append({"id": sid, "symbol": sym, "name": cls.name, "family": cls.family,
                            "stage": v.get("stage"), "stage_index": L.STAGES.index(v.get("stage", "backtest")),
                            "backtest": v.get("backtest"), "tracked_trades": live["n"], "tracked_pnl": live["p"],
                            "history": v.get("history", [])[-5:]})
        return {"stages": L.STAGES, "gates": L.GATES, "strategies": out}

    def get_rules(self, q):
        r = R.load_rules(self.rules_path)
        r["exchange_max_leverage"] = R.EXCHANGE_MAX_LEV
        return r

    def post_rules(self, body):
        cur = R.load_rules(self.rules_path)
        new = dict(cur)
        new.update(body.get("rules", body))
        if new.get("live_enabled") and not cur["live_enabled"] and body.get("confirm") != LIVE_CONFIRM:
            return 400, {"error": "to unlock live, send confirm: '%s'" % LIVE_CONFIRM}
        R.save_rules(self.rules_path, new)
        self.j.event("info", "rules changed from the app")
        return 200, R.load_rules(self.rules_path)

    def kill(self, on):
        r = R.load_rules(self.rules_path)
        r["kill_switch"] = on
        R.save_rules(self.rules_path, r)
        self.j.event("warn" if on else "info", "kill switch %s from the app" % ("ON" if on else "off"))
        return 200, {"kill_switch": on}


def make_handler(api, token):
    routes = {"/api/summary": api.summary, "/api/trades": api.trades, "/api/equity": api.equity,
              "/api/calendar": api.calendar, "/api/strategies": api.strategies, "/api/rules": api.get_rules}

    class H(BaseHTTPRequestHandler):
        def _auth(self):
            got = self.headers.get("Authorization", "")
            return bool(token) and hmac.compare_digest(got.encode(), ("Bearer " + token).encode())

        def _send(self, code, obj):
            b = json.dumps(obj, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            u = urlparse(self.path)
            if u.path == "/health":
                return self._send(200, {"ok": True})
            if not self._auth():
                return self._send(401, {"error": "bad token"})
            fn = routes.get(u.path)
            if not fn:
                return self._send(404, {"error": "not found"})
            self._send(200, fn(parse_qs(u.query)))

        def do_POST(self):
            u = urlparse(self.path)
            if not self._auth():
                return self._send(401, {"error": "bad token"})
            n = int(self.headers.get("Content-Length") or 0)
            try:
                body = json.loads(self.rfile.read(min(n, 65536)) or b"{}")
            except ValueError:
                return self._send(400, {"error": "bad json"})
            if u.path == "/api/rules":
                return self._send(*api.post_rules(body))
            if u.path == "/api/kill":
                return self._send(*api.kill(True))
            if u.path == "/api/resume":
                return self._send(*api.kill(False))
            self._send(404, {"error": "not found"})

        def log_message(self, fmt, *args):  # quiet; never log headers (token)
            pass

    return H


def serve(state_dir="state", host="127.0.0.1", port=8787, token_file=None):
    token = os.environ.get("TRADEDESK_API_TOKEN", "")
    if not token and token_file and os.path.exists(token_file):
        with open(token_file, encoding="utf-8") as f:
            token = f.read().strip()
    if len(token) < 24:
        raise SystemExit("set TRADEDESK_API_TOKEN (or --token-file) to a random string of 24+ characters first")
    httpd = ThreadingHTTPServer((host, port), make_handler(Api(state_dir), token))
    print("tradedesk API on http://%s:%d (token required)" % (host, port))
    httpd.serve_forever()
