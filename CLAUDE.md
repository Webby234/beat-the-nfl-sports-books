# NFL Betting Board

Python 3.11 + pandas / scikit-learn / Streamlit. Predicts NFL games and player props from free nflverse data and
compares them with sportsbook lines. Streamlit entry point: `model.py`. CLI: `python -m nfl_model <command>`.

## Commands
- All tests: `python -m nfl_model test` (custom runner; pytest is NOT installed). One module: `python -m tests.test_ui`.
  `tests.test_no_leakage` takes ~30s; the others ~1s.
- Reports: `python -m nfl_model backtest | bets | ablation | lines | props`, then `python -m nfl_model.ui.calibrate`.
- Data is cached in `data/` (git-ignored) and refreshed as games finish.

## Rules that matter most
- **No future information.** Every feature must be computable before kickoff: snapshot state, then update with the
  result (`features/team_features.py`, `features/qb.py`). Same-week games must not see each other. Tag every new
  feature in `features/availability.py` (`early` / `gameday` / `market`). `tests/test_no_leakage.py` must pass.
- **Walk-forward only.** Every reported number comes from models trained on earlier seasons (first test season
  2015, `config.FIRST_TEST`). Never tune a constant on the seasons it is then scored on.
- **Evidence standard for model changes:** paired log-loss (or MSE) difference vs the current model on the same
  games, with its standard error. Adopt only if |z| > 2; also report the gap to the sportsbook. Use `/experiment`.
- **Reports are generated, never hand-edited.** `reports/*.csv` come from the commands above; the README's
  "How accurate is it" table must match them (use `/refresh-reports`).
- **Trust** (`ui/board.py` `TRUST`) = how far the board believes the model over the book. Set from
  `python -m nfl_model.ui.calibrate`, which measures it walk-forward; a market keeps trust only if blending beat
  the book out of sample (currently Moneyline 0, Spread 0, Total 0.56).

## Findings so far (2026-10)
- The game models trail the closing moneyline by ~0.015 log-loss; standard tweaks (EWMA reset, opponent
  adjustment, Elo tuning, recency weights, margin-based win prob, pass/rush matchup features) were all within noise.
- Play-by-play features (success rate, early-down EPA; garbage time = wp outside 10-90% or last 2 min of a half;
  EWMA half-life 6) tested 2026-10-11: no gain for moneyline or spread (all |z| < 2), worse for totals (z +2.2 to
  +3.0, also as summed both-team ratings). Not adopted.
- Early-week totals (5-8 days out) are where an edge shows: with *actual* gameday weather (an upper bound) bets
  >=1 pt off the line returned +9.4% (CI +1.6 to +17.1) with 0.56 pts CLV, vs +6.0% / 0.23 without weather. Real
  Open-Meteo forecasts (previous-runs API, only from 2024) on 2024-26: totals MSE -0.97 (z -1.56), no CLV gain.
  Not adopted; Open-Meteo keeps the archive, so re-run when 2026-27 add games.
- The market prices QB changes ~fully (lines_move_attribution: 99%), so backup-QB ratings are low value for betting.
- Bet tracking (`ui/tracker.py`) logs CLV and the inputs prop trust needs (`calibrate.prop_trust`, >=300 props).
  The hosted app writes nothing; `.github/workflows/log-picks.yml` runs `python -m nfl_model log` Wed + Sun and
  commits to the `bet-log` branch (props via a free `ODDS_API_KEY` secret); the hosted app reads its record there.

## Style
Dense code: short helpers, several statements per line are normal here. Match the surrounding code; don't
reformat files. Docstrings explain *why* (timing, leakage), not what.
