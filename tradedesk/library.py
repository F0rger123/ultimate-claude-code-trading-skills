"""Strategy bank: strategies added from outside research (for example a ChatGPT deep-research run), coded
against the same Strategy interface as tradedesk/strategies.py.

How an idea gets here (see research/strategy_bank/README.md):
1. The idea arrives as a written spec: exact entry, exit, stop, timeframe, a small parameter grid, the
   mechanism, and a source.
2. Claude codes it as a Strategy subclass below, sets `cadence = "fast"` (runs on 5-minute bars) or
   `cadence = "slow"` (hourly bars), and adds it to ALL.
3. Unit tests check it runs and never looks ahead. It then joins the weekly shake-up's candidate pool,
   where it must win a test on recent data with costs before it gets a paper account.
Nothing here can trade real money.
"""

ALL = []
