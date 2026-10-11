"""Walk-forward A/B harness for game-model ideas. Import from an experiment script:

    import sys; sys.path.insert(0, ".claude/skills/experiment")
    from harness import *
    f = table()                                    # cached feature table (all pre-game features)
    f["my_feat"] = ...                             # build the idea (pre-game information only!)
    base = win_prob(f, CURRENT)
    compare("+ my_feat", win_prob(f, CURRENT + ["my_feat"]), base)

`compare` prints the paired log-loss difference vs the current model on the same games (with z) and the gap to
the closing moneyline. Adopt a change only if z < -2. For spreads/totals use `margin_mse` / `compare_mse`.
"""
import sys, warnings
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

import numpy as np, pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import log_loss
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from nfl_model.config import FIRST_TEST, TRAIN_START
from nfl_model.evaluation import lines_backtest as L
from nfl_model.evaluation.backtest import eligible
from nfl_model.evaluation.metrics import paired_logloss_diff
from nfl_model.features import NO_MARKET, QB_FEATURES, WITH_SPREAD, load_feature_table

CURRENT = NO_MARKET + QB_FEATURES          # best no-market win model (logit_no_market_qb)
CURRENT_WITH_SPREAD = WITH_SPREAD          # the board's moneyline model (logit_with_spread)

_table = None


def table() -> pd.DataFrame:
    global _table
    if _table is None:
        _table = load_feature_table()
    return _table.copy()


def win_prob(df: pd.DataFrame, feats: list, C: float = 0.5, first: int = FIRST_TEST) -> pd.DataFrame:
    """Walk-forward logistic win probability: train on TRAIN_START..S-1, predict season S."""
    e = eligible(df)
    out = []
    for s in sorted(e.season[e.season >= first].unique()):
        tr, te = e[(e.season >= TRAIN_START) & (e.season < s)], e[e.season == s].copy()
        m = make_pipeline(SimpleImputer(strategy="median"), StandardScaler(), LogisticRegression(C=C, max_iter=2000))
        te["p"] = m.fit(tr[feats], tr.home_win.astype(int)).predict_proba(te[feats])[:, 1]
        out.append(te[["game_id", "season", "week", "home_win", "market_ml_prob", "p"]])
    return pd.concat(out).set_index("game_id")


def compare(name: str, cand: pd.DataFrame, base: pd.DataFrame) -> dict:
    c = cand.loc[base.index]
    y = c.home_win.to_numpy(float)
    d, se = paired_logloss_diff(y, c.p.to_numpy(float), base.p.to_numpy(float))
    dm, _ = paired_logloss_diff(y, c.p.to_numpy(float), c.market_ml_prob.to_numpy(float))
    z = d / se if se else 0.0
    verdict = "IMPROVES" if z < -2 else "WORSE" if z > 2 else "no clear change"
    print(f"{name:40s} ll {log_loss(y, c.p):.5f}  vs current {d:+.5f} (z {z:+.2f}) {verdict:16s} vs market {dm:+.5f}")
    return dict(name=name, ll_diff=d, se=se, z=z, vs_market=dm, verdict=verdict)


def margin_mse(df: pd.DataFrame, target: str = "result", feats=None, line: str | None = "spread_line") -> pd.DataFrame:
    """Walk-forward ridge for margin ('result') or 'total'; the board's versions include the line."""
    feats = feats if feats is not None else (L.MARGIN_FEATS if target == "result" else L.TOTAL_FEATS)
    return L.walk_forward(L.prep(df), target, feats, line).set_index("game_id")


def compare_mse(name: str, cand: pd.DataFrame, base: pd.DataFrame, target: str = "result") -> dict:
    c, b = cand.loc[base.index], base
    dd = (c[target] - c.pred) ** 2 - (b[target] - b.pred) ** 2
    d, se = dd.mean(), dd.std() / len(dd) ** 0.5
    z = d / se if se else 0.0
    verdict = "IMPROVES" if z < -2 else "WORSE" if z > 2 else "no clear change"
    print(f"{name:40s} MSE diff vs current {d:+.3f} (se {se:.3f}, z {z:+.2f}) {verdict}")
    return dict(name=name, mse_diff=d, se=se, z=z, verdict=verdict)


if __name__ == "__main__":       # smoke test: the current model against itself
    f = table()
    base = win_prob(f, CURRENT)
    compare("current (should be 0)", base, base)
