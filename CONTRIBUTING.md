# Contributing

1. **Run the tests:** `python -m unittest discover -s tests` must pass.
2. **New strategies:**
   - Implement the interface in `tradedesk/strategies.py`: `entry(i)` may use data only through the close
     of bar `i`.
   - Add it to the no-look-ahead test.
   - Register its grid; every variant you try counts as a trial.
3. **Results:** run `research/corrected_tournament.py` and report the summary as is, failures included.
   Never tune gates, costs or windows to make a result pass.
4. **Keep the core standard-library only.** Optional research packages go in `research/` with pinned versions.
5. **No secrets, no non-redistributable data,** and no code that moves money.
