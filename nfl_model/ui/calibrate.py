"""Recompute the TRUST factors in board.py:  python -m nfl_model.ui.calibrate

For each market, trust is a one-parameter fit: how much of the gap between the model's chance and the sportsbook's
chance shows up in results. It is checked walk-forward: for every season S from FIRST_CHECK on, trust is fitted on
the seasons before S only and then scored on S, so the check never sees the season it is judged on.

A market is given the latest walk-forward trust only if blending in the model beat the sportsbook's own chance out
of sample; otherwise its recommended trust is 0 (believe the book). The in-sample fit is reported for reference only.
Needs reports/predictions.csv (python -m nfl_model backtest).
"""
import numpy as np, pandas as pd
from sklearn.linear_model import LogisticRegression
from ..config import FIRST_TEST, REPORT_DIR, TRAIN_START
from ..evaluation import lines_backtest as L
from ..features import load_feature_table
from .board import _two_way

FIRST_CHECK = FIRST_TEST + 2      # two seasons of out-of-sample predictions before trust is first fitted

lg = lambda p: np.log(np.clip(p, 1e-4, 1 - 1e-4) / (1 - np.clip(p, 1e-4, 1 - 1e-4)))


def fit_trust(d: pd.DataFrame) -> float:
    """d: market (logit of the book's chance), gap (model logit minus book logit), y (1/0)."""
    X = np.column_stack([d.market, d.gap])
    return float(LogisticRegression(C=1e6, fit_intercept=False).fit(X, d.y).coef_[0][1])


def _log_loss(y, z):
    p = np.clip(1 / (1 + np.exp(-z)), 1e-6, 1 - 1e-6)
    return -(y * np.log(p) + (1 - y) * np.log(1 - p))


def walk_forward(d: pd.DataFrame, first: int = FIRST_CHECK) -> pd.DataFrame:
    """Per game from season `first` on: trust fitted on earlier seasons, and how much the blend beat the book
    (gain > 0 = blend had lower log loss than the sportsbook's chance alone)."""
    out = []
    for s in sorted(d.season[d.season >= first].unique()):
        t = fit_trust(d[d.season < s])
        te = d[d.season == s]
        y = te.y.to_numpy(float)
        gain = _log_loss(y, te.market.to_numpy()) - _log_loss(y, (te.market + t * te.gap).to_numpy())
        out.append(pd.DataFrame(dict(season=s, trust=t, gain=gain)))
    return pd.concat(out, ignore_index=True)


def summarize(d: pd.DataFrame, n_boot: int = 300, seed: int = 0, first: int = FIRST_CHECK) -> dict:
    wf = walk_forward(d, first)
    gain, se = wf.gain.mean(), wf.gain.std() / len(wf) ** 0.5
    latest = fit_trust(d)                         # fitted on every season: what next season would use
    rng = np.random.default_rng(seed)
    bs = [fit_trust(d.iloc[rng.integers(0, len(d), len(d))]) for _ in range(n_boot)]
    return dict(trust=round(max(latest, 0.0), 2) if gain > 0 else 0.0, latest_fit=latest,
                lo=np.percentile(bs, 2.5), hi=np.percentile(bs, 97.5), oos_gain_x1000=1000 * gain,
                oos_se_x1000=1000 * se, n=len(d), n_oos=len(wf))


def collect() -> dict[str, pd.DataFrame]:
    """Out-of-sample model and book chances for every past game, per market (pushes left out)."""
    f = L.prep(load_feature_table())
    f = f[(f.game_type == "REG") & f.home_score.notna()]
    d = pd.read_csv(REPORT_DIR / "predictions.csv").dropna(subset=["p_logit_with_spread", "p_market_ml", "home_win"])
    out = {"Moneyline": pd.DataFrame(dict(season=d.season.values, week=d.week.values, market=lg(d.p_market_ml.values),
                                          gap=lg(d.p_logit_with_spread.values) - lg(d.p_market_ml.values),
                                          y=d.home_win.values))}
    for name, tgt, feats, line in (("Spread", "result", L.MARGIN_FEATS, "spread_line"),
                                   ("Total", "total", L.TOTAL_FEATS, "total_line")):
        rows = []
        for s in sorted(f.season.unique()):
            tr = f[(f.season >= TRAIN_START) & (f.season < s)].dropna(subset=[tgt, line])
            te = f[f.season == s].dropna(subset=[tgt, line])
            if s < FIRST_TEST or te.empty:
                continue
            cols = feats + [line]; m = L.ridge().fit(tr[cols], tr[tgt]); res = (tr[tgt] - m.predict(tr[cols])).values
            for p, l, y, wk in zip(m.predict(te[cols]), te[line], te[tgt], te.week):
                o, u = _two_way(p, res, l)
                if y != l:
                    rows.append((s, wk, o / (o + u), float(y > l)))
        r = pd.DataFrame(rows, columns=["season", "week", "p", "y"])
        # spread and total prices are close to even money, so the book's own chance is taken as 50%
        out[name] = pd.DataFrame(dict(season=r.season, week=r.week, market=0.0, gap=lg(r.p.to_numpy()), y=r.y))
    return out


def run() -> pd.DataFrame:
    rows = []
    for market, d in collect().items():
        rows.append(dict(market=market, **summarize(d)))
    return pd.DataFrame(rows)


PROP_MIN_BETS, PROP_FIRST_WEEKS = 300, 4


def prop_trust(graded: pd.DataFrame) -> dict | None:
    """Prop trust from the app's own pick log (tracker.grade output): props have no price history, so the only
    real prices are the lines typed into the app. Same walk-forward check as the game markets, but week by week:
    each logged week is scored with trust fitted on the weeks before it. None until PROP_MIN_BETS props settle."""
    d = graded[~graded.market.isin(["Moneyline", "Spread", "Total"]) & graded.result.isin(["win", "loss"])]
    d = d.dropna(subset=["p_raw", "fair"])
    if len(d) < PROP_MIN_BETS:
        return None
    wk = d.season * 100 + d.week
    step = wk.map({w: i for i, w in enumerate(sorted(wk.unique()))})          # 0, 1, 2 ... in week order
    x = pd.DataFrame(dict(season=step.values, market=lg(d.fair.values), gap=lg(d.p_raw.values) - lg(d.fair.values),
                          y=(d.result == "win").astype(float).values))
    return dict(market="prop", **summarize(x, first=PROP_FIRST_WEEKS))


if __name__ == "__main__":
    r = run(); r.round(3).to_csv(REPORT_DIR / "ui_trust.csv", index=False); print(r.round(2).to_string(index=False))
    from . import tracker
    from ..data import load_games, load_skill_games
    log = tracker.load()
    p = prop_trust(tracker.grade(log, load_games(), load_skill_games())) if len(log) else None
    print("\nProps:", "not enough settled props in lines/picks_log.csv yet (need %d), so props keep the assumed "
          "TRUST['prop']" % PROP_MIN_BETS if p is None else pd.Series(p).round(3).to_string())
