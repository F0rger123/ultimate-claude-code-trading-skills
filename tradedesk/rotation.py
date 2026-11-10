"""Weekly shake-up of the PAPER accounts: retire the bottom three, start three new ones.

Paper only. This module edits the paper roster (state/paper/roster.json) and nothing else: it never
touches the promotion ladder, live settings, risk rules or money. Moving any strategy toward real money
still needs the owner's explicit approval (BLUEPRINT: no automatic promotion between money stages).

Once a week (Monday 14:00 UTC, 9 AM Eastern in winter; later if the PC was asleep):
1. Rank. Every account past its trial (fast 6 days, slow 27 days) is scored by its paper return since it
   started. An account that hit its own 10% drawdown block scores last. The $50 pilot mirror is never cut.
2. Cut. The bottom three are retired to state/paper/retired/. The 'All accounts' balance shows
   only accounts still running; the drawdown halt still counts retired losses.
3. Learn. Each retired result is added to the memory of its strategy family (rotation.json). A family that
   keeps losing on paper gets a lower score next time, and the exact setting that was cut waits 8 weeks
   before it may return.
4. Find replacements. Candidates are the engine's strategies across their parameter grids. Each is tested
   on recent data the same way the paper accounts run (fast: last 21 days of 5-minute bars, slow: last
   365 days of hourly bars), with costs. Score = return % - 0.5 x worst drawdown %, plus the family's
   paper memory. A replacement keeps the cut account's speed (fast for fast, slow for slow), and
   families already running are skipped when another family is available.
5. Start. The three best start as new $10,000 paper accounts. A good recent test is weak evidence (picking
   the best of many tests flatters the winner), which is exactly why new picks only go to paper.
"""
import datetime
import json
import os
import random
import time

from . import candidates as C
from . import paper as PA
from . import portfolio as P
from . import risk as RK
from . import strategies as S

FAST = [S.MTFQuick, S.MTFSwing, S.MTFTrend, S.DonchianBreakout, S.Donchian1h, S.Donchian4h, S.EMAPullback,
        S.EMAPullback1h, S.VWAPReclaim, S.RSI2Reversion, S.Scalp10]
SLOW = [S.TSMOMDaily, S.TurtleDaily, S.EMACross4h, S.TrendEnsemble, C.VolManagedTrend, C.VolFilteredBreakout,
        C.WeeklyStrengthRotation]
SPOT_ONLY = {C.WeeklyStrengthRotation.id}
SIZE = {S.Scalp10.id: {"risk": 0.0025, "pos_lev": 0.1, "gross_lev": 0.1}}  # smaller than the defaults only
CUT = 3
TRIAL_DAYS = {"fast": 6, "slow": 27}
SCREEN = {"fast": (21, 5), "slow": (365, 3)}  # test window in days, minimum trades
PER_CLASS = 3  # parameter settings tested per strategy family each week
COOLDOWN_WEEKS = 8
LEARN_WEIGHT = 1.0  # % of family paper memory added to the test score
RUN_WEEKDAY, RUN_HOUR_UTC = 0, 14
DAY = 86400


def week_key(t):
    y, w, _ = datetime.datetime.fromtimestamp(t, datetime.timezone.utc).isocalendar()
    return "%d-W%02d" % (y, w)


def slot(t):
    """This ISO week's run time (Monday 14:00 UTC)."""
    d = datetime.datetime.fromtimestamp(t, datetime.timezone.utc)
    monday = (d - datetime.timedelta(days=d.weekday())).replace(hour=RUN_HOUR_UTC, minute=0, second=0, microsecond=0)
    return int(monday.timestamp())


def next_slot(t):
    s = slot(t)
    return s if t < s else s + 7 * DAY


def ledger_path(state_dir):
    return os.path.join(state_dir, "paper", "rotation.json")


def load_ledger(state_dir, now=None, create=False):
    p = ledger_path(state_dir)
    if os.path.exists(p):
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    led = {"runs": [], "families": {}, "tried": {}, "created": int(now or time.time())}
    if create:  # the first week only starts the clock: books need their trial before any cut
        led["last_week"] = week_key(int(now or time.time()))
        save_ledger(state_dir, led)
    return led


def save_ledger(state_dir, led):
    p = ledger_path(state_dir)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p + ".tmp", "w", encoding="utf-8") as f:
        json.dump(led, f, indent=1)
    os.replace(p + ".tmp", p)


def due(state_dir, now):
    led = load_ledger(state_dir, now, create=True)
    return now >= slot(now) and led.get("last_week") != week_key(now)


def key(cls_id, params):
    return cls_id + "|" + json.dumps(params, sort_keys=True)


# ---------------------------------------------------------------- 1. rank
def rank(state_dir, now):
    rows = []
    for b in PA.roster(state_dir):
        bk = PA.load_book(state_dir, b["id"])
        if not bk:
            continue
        age = (now - bk["start"]) / DAY
        blocked = any(e[1] in ("block", "halt") for e in bk.get("events", []))
        pct = 100.0 * bk["pnl"] / bk["start_equity"] if bk["start_equity"] else 0.0
        rows.append({"id": b["id"], "name": b["name"], "cls": b["cls"].id, "cadence": b["cadence"],
                     "params": b.get("params") or {}, "days": round(age, 1), "pnl_pct": round(pct, 2),
                     "trades": bk["closed"], "blocked": blocked, "score": -1000.0 + pct if blocked else pct,
                     "eligible": not b.get("protected") and age >= TRIAL_DAYS[b["cadence"]]})
    return sorted(rows, key=lambda r: r["score"])


# ---------------------------------------------------------------- 4. candidates and their tests
def _settings(cls, rng):
    grid = getattr(cls, "grid", {}) or {}
    ks = sorted(grid)
    combos = [{}]
    for k in ks:
        combos = [dict(c, **{k: v}) for c in combos for v in grid[k]]
    if combos != [{}]:
        combos = [{}] + combos  # {} = the strategy's own defaults
    rng.shuffle(combos)
    return combos


def candidates(cadence, led, now, rng):
    out = []
    for cls in (FAST if cadence == "fast" else SLOW):
        n = 0
        for params in _settings(cls, rng):
            t = led.get("tried", {}).get(key(cls.id, params))
            if t and now - t < COOLDOWN_WEEKS * 7 * DAY:
                continue
            out.append((cls, params))
            n += 1
            if n >= PER_CLASS:
                break
    return out


def _book(cls, params, cadence):
    b = {"id": "screen", "cls": cls, "mode": "spot" if cls.id in SPOT_ONLY else "perp", "equity": 10000.0,
         "cadence": cadence, "params": params}
    b.update(SIZE.get(cls.id, {}))
    return b


def screen(cls, params, cadence, markets, now):
    """Paper-style test on recent data with costs. Returns a dict, or None if the strategy cannot run."""
    days, min_trades = SCREEN[cadence]
    b = _book(cls, params, cadence)
    try:
        r = P.run(markets, PA._variants(markets, b, params), PA._cfg(b), start_t=now - days * DAY, close_at_end=True)
    except Exception as e:  # a strategy that cannot run on this data is skipped, never fatal
        return {"error": str(e)[:200]}
    curve = r["curve"]
    if not curve:
        return None
    peak, mdd = b["equity"], 0.0
    for _, e in curve:
        peak = max(peak, e)
        mdd = max(mdd, (peak - e) / peak if peak else 0.0)
    ret = 100.0 * (curve[-1][1] - b["equity"]) / b["equity"]
    n = len(r["trades"])
    return {"ret_pct": round(ret, 2), "max_dd_pct": round(100 * mdd, 2), "trades": n, "days": days,
            "enough": n >= min_trades, "score": round(ret - 0.5 * 100 * mdd, 2)}


def family_memory(led, cls_id):
    f = led.get("families", {}).get(cls_id) or {}
    xs = f.get("paper_pct", [])[-10:]
    return sum(xs) / len(xs) if xs else 0.0


def pick(need, keep, led, now, log=print, markets_for=None):
    """need: {"fast": n, "slow": n}. keep: roster entries that stay. Returns (picks, tested)."""
    rng = random.Random(week_key(now))
    active = {b["cls"].id for b in keep}
    picks, tested = [], []
    for cadence in ("fast", "slow"):
        n = need.get(cadence, 0)
        if not n:
            continue
        gran = 300 if cadence == "fast" else 3600
        days = SCREEN[cadence][0]
        if markets_for:
            markets = markets_for(cadence)
        else:
            since = now - (days + PA.FAST_WARMUP_DAYS) * DAY if cadence == "fast" else None
            markets, _ = PA._markets(gran, now, True, since)
        rows = []
        for cls, params in candidates(cadence, led, now, rng):
            s = screen(cls, params, cadence, markets, now)
            if not s or "error" in s:
                log("  skip %s %s: %s" % (cls.id, params, (s or {}).get("error", "no data")))
                continue
            mem = family_memory(led, cls.id)
            row = {"cls": cls.id, "name": cls.name, "params": params, "cadence": cadence, "screen": s,
                   "memory_pct": round(mem, 2), "total": round(s["score"] + LEARN_WEIGHT * mem, 2)}
            rows.append(row)
            log("  test %-24s %-40s ret %+6.2f%%  dd %5.2f%%  %3d trades  memory %+.2f  -> %+.2f" % (
                cls.id, json.dumps(params)[:40], s["ret_pct"], s["max_dd_pct"], s["trades"], mem, row["total"]))
        tested += rows
        rows.sort(key=lambda r: (not r["screen"]["enough"], -r["total"]))
        chosen, used = [], set()
        for pass_ in (0, 1):  # first pass: families not running now; second pass: anything left
            for r in rows:
                if len(chosen) >= n:
                    break
                if r["cls"] in used or (pass_ == 0 and r["cls"] in active):
                    continue
                chosen.append(r)
                used.add(r["cls"])
        picks += chosen
    return picks, tested


def _label(params):
    return ", ".join("%s %s" % (k.replace("_", " "), v) for k, v in sorted(params.items()))[:40]


def new_spec(r, now, taken, manual=False):
    cls = PA.REGISTRY[r["cls"]]
    day = time.strftime("%y%m%d", time.gmtime(now))
    bid, k = "pb_%s_%s" % (cls.id, day), 2
    while bid in taken:
        bid, k = "pb_%s_%s_%d" % (cls.id, day, k), k + 1
    taken.add(bid)
    s = r["screen"]
    name = ("Fast: " if r["cadence"] == "fast" else "") + cls.name + (" (%s)" % _label(r["params"]) if r["params"] else "")
    how = "Replaced a losing account at your request" if manual else "Added by the weekly shake-up"
    note = "%s %s. Recent test: %+.1f%% over %d days, %d trades, worst drop %.1f%%. Paper only" % (
        how, time.strftime("%b %d", time.gmtime(now)), s["ret_pct"], s["days"], s["trades"], s["max_dd_pct"])
    spec = {"id": bid, "name": name, "cls": cls.id, "mode": "spot" if cls.id in SPOT_ONLY else "perp",
            "equity": 10000.0, "cadence": r["cadence"], "params": r["params"], "note": note, "added": now,
            "screen": dict(s, memory_pct=r["memory_pct"], total=r["total"])}
    spec.update(SIZE.get(cls.id, {}))
    return spec


# ---------------------------------------------------------------- the weekly run
def run(state_dir, journal=None, now=None, force=False, dry=False, log=print, markets_for=None, replace=None):
    """replace: account ids the OWNER chose to retire now (skips the trial and the weekly slot; the Monday
    run still happens). Protected accounts can never be replaced."""
    now = int(now or time.time())
    led = load_ledger(state_dir, now)
    wk = week_key(now)
    rules = RK.load_rules(os.path.join(state_dir, "rules.json"))
    if rules.get("kill_switch") and not force:
        log("kill switch is on: no shake-up this week (the owner halted trading)")
        return None
    if led.get("last_week") == wk and not force and not replace:
        log("already ran this week (%s)" % wk)
        return None
    ranks = rank(state_dir, now)
    for r in ranks:
        log("  rank %-24s %-5s %5.1f days  %+6.2f%%  %3d trades  %s" % (
            r["id"], r["cadence"], r["days"], r["pnl_pct"], r["trades"], "eligible" if r["eligible"] else "trial/protected"))
    if replace:
        prot = {b["id"] for b in PA.roster(state_dir) if b.get("protected")}
        cut = [r for r in ranks if r["id"] in set(replace) and r["id"] not in prot]
        missing = set(replace) - {r["id"] for r in cut}
        if missing:
            log("not replaced (unknown or protected): %s" % ", ".join(sorted(missing)))
    else:
        cut = [r for r in ranks if r["eligible"]][:CUT]
    need = {}
    for r in cut:
        need[r["cadence"]] = need.get(r["cadence"], 0) + 1
    roster = PA.roster(state_dir)
    keep = [b for b in roster if b["id"] not in {r["id"] for r in cut}]
    picks, tested = pick(need, keep, led, now, log, markets_for) if cut else ([], [])
    # never shrink the roster: cut only as many per speed as there are replacements
    got = {}
    for p in picks:
        got[p["cadence"]] = got.get(p["cadence"], 0) + 1
    final_cut, used = [], {}
    for r in cut:
        if used.get(r["cadence"], 0) < got.get(r["cadence"], 0):
            final_cut.append(r)
            used[r["cadence"]] = used.get(r["cadence"], 0) + 1
    taken = {b["id"] for b in roster} | {b["id"] for b in PA.retired_books(state_dir)}
    specs = [new_spec(p, now, taken, bool(replace)) for p in picks]
    entry = {"t": now, "week": wk, "ranked": ranks, "cut": final_cut, "added": specs,
             "tested": len(tested), "next": next_slot(now + 60)}
    if dry:
        log(json.dumps({"cut": [r["id"] for r in final_cut], "add": [s["id"] for s in specs]}))
        return entry
    for r in final_cut:
        why = "replaced at the owner's request" if replace else "weekly shake-up %s: bottom %d" % (wk, CUT)
        PA.retire(state_dir, r["id"], "%s, %+.2f%% after %.1f days" % (why, r["pnl_pct"], r["days"]), now)
    PA.save_roster(state_dir, [b for b in roster if b["id"] not in {r["id"] for r in final_cut}] + specs)
    fam = led.setdefault("families", {})
    for r in final_cut:
        f = fam.setdefault(r["cls"], {"paper_pct": [], "cuts": 0})
        f["paper_pct"] = (f["paper_pct"] + [r["pnl_pct"]])[-20:]
        f["cuts"] += 1
        led.setdefault("tried", {})[key(r["cls"], r["params"])] = now
    for s in specs:
        led.setdefault("tried", {})[key(s["cls"], s["params"])] = now
    entry["manual"] = bool(replace)
    if not replace:
        led["last_week"] = wk
    led["runs"] = (led.get("runs", []) + [entry])[-52:]
    save_ledger(state_dir, led)
    msg = ("Owner replacement" if replace else "Weekly shake-up") + ": retired %s; started %s" % (
        ", ".join("%s (%+.1f%%)" % (r["name"], r["pnl_pct"]) for r in final_cut) or "none",
        ", ".join(s["name"] for s in specs) or "none")
    log(msg)
    if journal is not None:
        journal.event("info", msg[:500])
    return entry


def summary(state_dir, now=None):
    """For the phone: next run, the last run and what the loop has learned per family."""
    now = int(now or time.time())
    led = load_ledger(state_dir, now, create=True)
    last = (led.get("runs") or [None])[-1]
    fams = [{"id": k, "name": PA.REGISTRY[k].name if k in PA.REGISTRY else k, "cuts": v.get("cuts", 0),
             "avg_paper_pct": round(sum(v["paper_pct"]) / len(v["paper_pct"]), 2) if v.get("paper_pct") else None}
            for k, v in led.get("families", {}).items()]
    ran = led.get("last_week") == week_key(now)
    out = {"next": next_slot(now + 60) if ran or now < slot(now) else now,
           "cut_per_week": CUT, "trial_days": TRIAL_DAYS, "runs": len(led.get("runs", [])), "families": fams,
           "standings": [{k: r[k] for k in ("id", "name", "cadence", "days", "pnl_pct", "eligible")}
                         for r in reversed(rank(state_dir, now))]}
    ps = PA.load_summary(state_dir) or {}
    out["retired_pnl"] = ps.get("retired_pnl", 0.0)
    out["retired_count"] = ps.get("retired_count", 0)
    if last:
        out["last"] = {"t": last["t"], "cut": [{"name": r["name"], "pnl_pct": r["pnl_pct"]} for r in last["cut"]],
                       "added": [{"name": s["name"], "note": s["note"]} for s in last["added"]],
                       "tested": last.get("tested", 0)}
    return out
