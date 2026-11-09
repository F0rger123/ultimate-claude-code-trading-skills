"""python -m tradedesk <command>

  data         download or extend 5m history (Coinbase spot, no key)
  tournament   walk-forward every strategy, apply the backtest gate, write reports/
  learn        propose and test filters from the out-of-sample trades
  desk         run forward / paper (and live, only if unlocked) every 30 seconds
  serve        phone API (needs TRADEDESK_API_TOKEN)
  check-live   read-only Coinbase check: balance, positions, an order preview (needs keys)
  status       ladder and journal summary
  rotate       weekly paper shake-up: retire the bottom 3 accounts, start 3 new ones (--dry-run, --force)
"""
import argparse
import json
import os
import sys
import time


def main(argv=None):
    p = argparse.ArgumentParser(prog="tradedesk")
    p.add_argument("cmd")
    p.add_argument("--data", default="data")
    p.add_argument("--state", default="state")
    p.add_argument("--reports", default="reports")
    p.add_argument("--days", type=int, default=730)
    p.add_argument("--symbols", default="BTC,ETH,SOL")
    p.add_argument("--strategies", default="")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8787)
    p.add_argument("--token-file", default=None)
    p.add_argument("--gran", type=int, default=300, help="base bar seconds: 300 or 3600")
    p.add_argument("--train-days", type=int, default=180)
    p.add_argument("--test-days", type=int, default=60)
    p.add_argument("--tag", default="latest")
    p.add_argument("--min-train-trades", type=int, default=15)
    p.add_argument("--force", action="store_true", help="rotate: run even if this week already ran")
    p.add_argument("--dry-run", action="store_true", help="rotate: rank and test, change nothing")
    a = p.parse_args(argv)
    syms = [s.strip().upper() for s in a.symbols.split(",") if s.strip()]

    if a.cmd == "data":
        from . import data as D
        for s in syms:
            b = D.update_cache(a.data, D.PERPS[s]["spot"], a.gran, days=a.days)
            print("%s: %d bars, %d missing" % (s, len(b), D.gaps(b, a.gran)))
    elif a.cmd == "tournament":
        from . import tournament
        tournament.run(a.data, a.reports, a.state, syms, [x for x in a.strategies.split(",") if x] or None,
                       base=a.gran, train_days=a.train_days, test_days=a.test_days, tag=a.tag,
                       min_train_trades=a.min_train_trades)
        print("report: %s" % os.path.join(a.reports, "tournament-%s.md" % a.tag))
    elif a.cmd == "learn":
        from . import data as D, learn as LN, strategies as S, walkforward as W
        from .market import Market
        out = []
        for s in syms:
            mkt = Market(D.load(D.cache_path(a.data, D.PERPS[s]["spot"], 300)), s)
            for cls in ([S.BY_ID[x] for x in a.strategies.split(",") if x] or S.ALL):
                wf = W.walk_forward(cls, mkt)
                props, cut = LN.propose_first_half(wf["oos"])
                for prop in props[:5]:
                    r = LN.evaluate(cls, mkt, prop, wf, cut)
                    r.update(strategy=cls.id, symbol=s)
                    out.append(r)
                    print("%s %s skip %s=%s (judged on 2nd half): parent %+.3fR (%d) -> child %+.3fR (%d) %s" % (
                        s, cls.id, prop["skip_field"], prop["skip_value"], r["parent_avg_R"], r["parent_oos_trades"],
                        r["child_avg_R"], r["child_oos_trades"], "PROMOTE" if r["promote"] else "reject"))
        os.makedirs(a.reports, exist_ok=True)
        with open(os.path.join(a.reports, "learn-latest.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, default=str)
    elif a.cmd == "rotate":
        from . import rotation as ROT
        from .journal import Journal
        j = Journal(os.path.join(a.state, "journal.sqlite"))
        ROT.run(a.state, j, force=a.force, dry=a.dry_run)
    elif a.cmd == "desk":
        from .desk import Desk
        Desk(a.state).run()
    elif a.cmd == "serve":
        from .server import serve
        serve(a.state, a.host, a.port, a.token_file)
    elif a.cmd == "check-live":
        from .broker_coinbase import CoinbaseCFM, LiveDisabled
        try:
            b = CoinbaseCFM()
            bal = b.balance().get("balance_summary", {})
            print("futures buying power:", (bal.get("futures_buying_power") or {}).get("value"))
            print("open positions:", len(b.positions().get("positions", [])))
            print("preview (not placed):", json.dumps(b.preview("BIP-20DEC30-CDE", 1, 1, 1.0, 10 ** 7, 1.0))[:400])
        except LiveDisabled as e:
            print("live not available: %s" % e)
            return 1
    elif a.cmd == "status":
        from . import ladder as L
        lad = L.Ladder(os.path.join(a.state, "ladder.json"))
        for k, v in sorted(lad.d.items()):
            bt = v.get("backtest") or {}
            print("%-26s %-10s OOS %s trades, PF %s" % (k, v["stage"], bt.get("oos_trades"), bt.get("pf")))
        jp = os.path.join(a.state, "journal.sqlite")
        if os.path.exists(jp):
            from .journal import Journal
            j = Journal(jp)
            print("open trades:", len(j.open_trades()), " closed:", len(j.closed_trades()))
            for e in j.events(5):
                print(time.strftime("%m-%d %H:%M", time.gmtime(e["t"])), e["level"], e["msg"][:120])
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
