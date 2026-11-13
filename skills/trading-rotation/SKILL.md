---
name: trading-rotation
description: The weekly paper shake-up and the study loop. Every day the paper accounts are studied (where each one makes and loses money, and improved versions of the winners). Every week losing accounts are retired and three new strategies, picked by testing candidates on recent data plus what earlier paper accounts taught, start as fresh paper accounts. Use when the user says "knock out the worst strategies", "replace the losers", "rotate strategies", "shake up the accounts", "which strategies got cut", "what did it learn this week", "why is this strategy winning", "improve the winners", "add these strategies", or asks why an account disappeared.
---

# Weekly paper shake-up

The engine is `tradedesk/rotation.py`. The desk runs it by itself every Monday at 14:00 UTC (9 AM Eastern in
winter, 10 AM in summer). If the PC was asleep, it runs the next time the desk is awake that week.

## Commands
- Replace accounts the owner names, now (skips the trial; Monday still runs): `python -m tradedesk rotate --state <state dir> --replace <id>,<id>`
- Preview without changing anything: `python -m tradedesk rotate --state <state dir> --dry-run`
- Run now even though this week already ran: `python -m tradedesk rotate --state <state dir> --force`
- Phone API: `GET /api/rotation` returns the next run, the last cuts and picks, the standings and the
  per-family memory. The app's Accounts tab shows the same.
- Files: `state/paper/rotation.json` (memory and run history), `state/paper/rotation.log` (each run's output),
  `state/paper/retired/` (every retired account, kept in full), `state/paper/roster.json` (accounts running now).

## Study and improve (tradedesk/study.py)
Runs once a day from the desk (`python -m tradedesk study`) and again at the start of every weekly run.
- **Why accounts win or lose.** Every closed paper trade is tagged with its market context, using only data
  known at the signal: session (Asia, Europe, US, late US), weekday or weekend, with or against the 1-hour
  trend, calm/normal/jumpy volatility, coin and side. For accounts with 8+ closed trades it reports the group
  that made the most and the group that lost the most (`state/paper/study.json`, and on the phone).
- **Improved versions of winners.** For each account that is up, it builds challengers:
  one setting changed (from the strategy's grid), or the same rules skipping a group where its paper trades
  lost money. Each challenger is judged against its parent on the period BEFORE the parent started paper
  trading, so an idea found in the paper trades is never scored on those same trades. It qualifies only if it
  beats the parent by 1 score point and, for a filter, keeps 60% of the trades.
- **Running accounts never change.** A qualified challenger becomes a candidate called "<parent> v2" in the
  next weekly run, competing on the same recent test as everyone else. Parent and v2 then run side by side on
  paper, which is the real test of the improvement.
- **Family memory learns from winners too.** A family's score now includes its accounts running now
  (2+ days old), not only the ones that were cut.

## Strategy bank (tradedesk/library.py)
New strategies from outside research go through `research/strategy_bank/README.md`: a written spec with
exact rules, at most 3 parameters, the mechanism and a source. Claude codes usable specs as Strategy classes
in `tradedesk/library.py` with `cadence = "fast"` or `"slow"`, adds unit tests, and they join the candidate
pool. Specs that need data the desk lacks are parked, not faked.

## How one run decides
1. **Rank.** Only losing accounts can be cut; a winner is never retired to fill the bottom three. An account can be cut only after its trial: 6 days for fast accounts, 27 days for slow ones
   (slow strategies trade a few times a month, so a week of them is noise). The score is the paper return
   since the account started. An account that hit its own 10% drawdown block ranks last.
2. **Cut the bottom three.** The $50 pilot mirror is protected and never cut. Retired accounts move to
   `paper/retired/`. The "All accounts" balance shows only accounts still running (owner's choice); retired results
   are listed on the shake-up card, and the 15% paper drawdown halt still counts them.
3. **Learn.** The retired account's return is added to its strategy family's memory. A family keeps the
   average of its last 10 retired results, and that average is added to its future test scores, so a
   family that keeps losing on paper sinks. The exact setting that was cut cannot return for 8 weeks.
4. **Find replacements.** Up to 3 settings per strategy family (from each strategy's parameter grid) are
   tested on recent data, run the same way as the paper accounts and with the same costs:
   fast on the last 21 days of 5-minute bars, slow on the last 365 days of hourly bars.
   Score = return % − 0.5 × worst drawdown % + family memory. Fewer than 5 trades (fast) or 3 (slow)
   ranks behind everything with enough trades.
5. **Start three new accounts.** A replacement keeps the speed of the account it replaces. Families
   already running are skipped when another family is available. Each new account starts with $10,000
   of paper money, and its note says why it was picked.

The number of accounts never shrinks: if fewer replacements can be tested than accounts were cut, only
that many are cut.

## Guardrails (do not change without the owner)
- Paper only. The shake-up edits the paper roster and nothing else: not the promotion ladder, not
  `rules.json`, not live settings, not money. Moving any strategy toward real money still needs the
  owner's explicit approval, every time.
- It does not run while the kill switch is on.
- New accounts may only use the default risk (1% per trade, 1.5× leverage) or less.
- Never lower the trial lengths, the drawdown block or the cooldown to make the loop look busier.

## Explain to the user
- One week is a small sample. Ranking on it mostly measures luck, especially for fast accounts. That is
  fine for choosing what to watch on paper, and it is why nothing here can reach real money.
- Picking the best of about 30 recent tests flatters the winner. Expect new accounts to do worse than
  their test. The family memory exists to correct for that over many weeks.
- Report the cuts, the picks and the tests that lost. Read `rotation.log` for the full table.
