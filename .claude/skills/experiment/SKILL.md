---
name: experiment
description: Test an idea for improving the NFL game models (new feature, parameter, or model change) with a leak-free walk-forward A/B against the current model and the sportsbook. Use whenever proposing or evaluating a model accuracy change in this project.
argument-hint: "<idea to test, e.g. 'add success rate features'>"
---

# Walk-forward experiment

Test the idea in `$ARGUMENTS` before touching production code.

1. **Write the experiment in the scratchpad**, not in the repo. Start from the harness:
   ```python
   import sys; sys.path.insert(0, r"<project root>/.claude/skills/experiment")
   from harness import *
   f = table()
   # build the candidate feature(s) on f using ONLY information known before kickoff
   base = win_prob(f, CURRENT)
   compare("+ idea", win_prob(f, CURRENT + ["new_feat"]), base)
   ```
   - For the board's own models also check `CURRENT_WITH_SPREAD` (moneyline) and `margin_mse` / `compare_mse`
     (spread with `target="result"`, totals with `target="total", line="total_line"`).
   - Rolling stats must be shifted so a game never sees its own result (e.g. `groupby(team).ewm(...).mean().shift(1)`
     in game order), and same-week games must not see each other.
   - Run the harness itself first (`python harness.py`) if unsure it works: it should print a 0 difference.

2. **Judge by the project's evidence standard.** Paired difference on the same games; adopt only if z < -2.
   Report the gap to the market too: a change that helps the no-market model may vanish once the line is included.
   Don't try many variants and keep the best one without saying how many were tried.

3. **Report** a small table: variant, difference vs current, z, verdict, gap to market. Say plainly when nothing helped.

4. **Only if it improves:** implement it in `nfl_model/`, tag new features in `features/availability.py`,
   run `python -m nfl_model test` (the leakage test must pass), then `/refresh-reports`.
