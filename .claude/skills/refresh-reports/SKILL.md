---
name: refresh-reports
description: Regenerate every file in reports/ from the current code and data, recalibrate trust, and bring the README accuracy table in line with the new numbers.
disable-model-invocation: true
---

# Refresh reports

Run from the project root, in this order (each writes to `reports/`; later steps read earlier outputs):

1. `python -m nfl_model backtest`  (writes predictions.csv, used by calibrate)
2. `python -m nfl_model bets`
3. `python -m nfl_model ablation`
4. `python -m nfl_model lines`
5. `python -m nfl_model props backtest --stat all`
6. `python -m nfl_model.ui.calibrate`  (writes ui_trust.csv)
7. `python -m nfl_model parlays`  (writes parlays_backtest.csv, which the Parlays page reads; uses TRUST, so run it
   again if TRUST changes)

Then:

- Compare `reports/ui_trust.csv` `trust` column with `TRUST` in `nfl_model/ui/board.py`. If they differ, show the
  user both and ask before changing `TRUST` (it changes which bets the app shows). If `TRUST` changes, bump the
  last number of the cache key in `nfl_model/ui/history.py` `load_or_build`.
- Compare the "How accurate is it" table in `README.md` with the new reports and list every number that moved.
  Update the README only for numbers that come straight from a report.
- `git diff --stat reports/` and summarize what changed and by how much. Never edit a report CSV by hand.
