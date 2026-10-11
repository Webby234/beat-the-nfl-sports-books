"""Keep a record of what the app recommended and grade it once the games are played.

log()    saves the current Home list (and every priced prop line) for games that haven't finished;
         the last snapshot before a game is what gets graded.
grade()  marks each logged bet win / loss / push / void and its profit on a 1-unit stake, and for game markets its
         closing-line value (clv): how far the closing line moved in the bet's favour after it was logged. CLV is a
         much quicker read than profit on whether betting when you do (early, or at your book's number) pays.
This is the only honest measure of whether the app's picks win: it is forward-looking and uses real prices.
p_raw (the model alone) and fair (the book's vig-free chance) are logged so prop trust can later be measured on
real prices (calibrate.prop_trust), the way the game markets' trust is.

The hosted app has no disk that survives a restart, so there the log is written by a scheduled GitHub Action
(python -m nfl_model log, .github/workflows/log-picks.yml) to the repo's bet-log branch, and load() reads it from
LOG_URL. Every snapshot also goes to a history file, so early-week and game-day prices can be compared.
"""
from __future__ import annotations
import os
import numpy as np, pandas as pd
from ..betting.odds import american_to_decimal
from ..config import HOSTED, ROOT

PATH = ROOT / "lines" / "picks_log.csv"
LOG_URL = os.environ.get("NFL_BOARD_LOG_URL",
                         "https://raw.githubusercontent.com/Webby234/NFL_Predicitions/bet-log/picks_log.csv")
COLS = ["season", "week", "game_id", "market", "stat", "player", "player_id", "team", "pick", "side", "line",
        "odds", "p_win", "breakeven", "edge", "ev", "rank", "logged_at", "p_raw", "fair"]
STAT_COL = {"qb_pass_yds": "passing_yards", "rush_yds": "rushing_yards", "rec_yds": "receiving_yards",
            "receptions": "receptions", "pass_tds": "passing_tds"}


def load(path=None) -> pd.DataFrame:
    """The log: `path` if given, else (on a shared host) the bet-log branch, else lines/picks_log.csv."""
    for src in ([path] if path else [LOG_URL, PATH] if HOSTED else [PATH]):
        try:
            return pd.read_csv(src).reindex(columns=COLS)      # older logs lack later columns
        except Exception:                                      # no log yet (missing file, or 404 before the first run)
            pass
    return pd.DataFrame(columns=COLS)


def log(board: dict, top: list[dict], prop_bets: list[dict], path=None, history=None) -> int:
    """Replace the logged rows for this week's unfinished games with the current snapshot (and append the snapshot
    to `history` when given, so earlier snapshots are not lost)."""
    path = path or PATH
    if not board.get("games"):
        return 0
    rows = [dict(b, rank=i) for i, b in enumerate(top, 1)]
    in_top = {id(b) for b in top}
    best = {}
    for b in prop_bets:                               # best side of each priced prop line, even outside the top 10
        if id(b) in in_top:
            continue
        k = (b["market"], b.get("player"))
        if k not in best or b["edge"] > best[k]["edge"]:
            best[k] = b
    top_keys = {(b["market"], b.get("player")) for b in top if b.get("player")}
    rows += [dict(b, rank=np.nan) for k, b in best.items() if k not in top_keys]
    new = pd.DataFrame(rows).reindex(columns=COLS)
    new["season"], new["week"] = board["season"], board["week"]
    new["logged_at"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")
    live = {g["game_id"] for g in board["games"]}
    old = load(path)
    keep = old[~((old.season == board["season"]) & (old.week == board["week"]) & old.game_id.isin(live))]
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.concat([keep, new], ignore_index=True).to_csv(path, index=False)
    if history is not None:
        pd.concat([load(history), new], ignore_index=True).to_csv(history, index=False)
    return len(new)


def grade(picks: pd.DataFrame, games: pd.DataFrame, skill: pd.DataFrame) -> pd.DataFrame:
    """Add `result` (win/loss/push/void, or NaN while the game is unplayed) and `profit` per 1-unit stake."""
    out = picks.copy()
    g = games.set_index("game_id")
    sk = skill.assign(any_td=(skill.rushing_tds + skill.receiving_tds) > 0).set_index(["season", "week", "player_id"])
    res, profit, clv = [], [], []
    for r in out.itertuples(index=False):
        game = g.loc[r.game_id] if r.game_id in g.index else None
        clv.append(_clv(r, game) if game is not None else np.nan)
        if game is None or pd.isna(game.home_score):
            res.append(np.nan); profit.append(np.nan); continue
        margin, total = game.home_score - game.away_score, game.home_score + game.away_score
        if r.market == "Moneyline":
            d = margin if r.side == "home" else -margin
        elif r.market == "Spread":                      # line is from the home side: home covers when margin > line
            d = (margin - r.line) if r.side == "home" else (r.line - margin)
        elif r.market == "Total":
            d = (total - r.line) if r.side == "over" else (r.line - total)
        else:
            key = (r.season, r.week, r.player_id)
            if key not in sk.index:                     # did not play: sportsbooks void the bet
                res.append("void"); profit.append(0.0); continue
            row = sk.loc[key]
            row = row.iloc[0] if isinstance(row, pd.DataFrame) else row
            if r.stat == "anytime_td":
                d = 1.0 if row.any_td else -1.0
            else:
                val = float(row[STAT_COL[r.stat]])
                d = (val - r.line) if r.side == "over" else (r.line - val)
        outcome = "win" if d > 0 else "loss" if d < 0 else "push"
        res.append(outcome)
        profit.append(float(american_to_decimal(r.odds)) - 1 if outcome == "win" else -1.0 if outcome == "loss" else 0.0)
    out["result"], out["profit"], out["clv"] = res, profit, clv
    return out


def _clv(r, game) -> float:
    """Spread / total: points the closing line moved our way. Moneyline: closing vig-free chance of our side minus
    the break-even of the price we logged. NaN for props (no closing prices) or when the close is missing."""
    close = lambda c: float(game.get(c, np.nan))
    if r.market == "Spread":                        # both lines are the home team's expected margin
        d = close("spread_line") - r.line
        return d if r.side == "home" else -d
    if r.market == "Total":
        d = close("total_line") - r.line
        return d if r.side == "over" else -d
    if r.market == "Moneyline":
        if np.isnan(close("home_moneyline")) or np.isnan(close("away_moneyline")):
            return np.nan
        h, a = (1 / american_to_decimal(close(c)) for c in ("home_moneyline", "away_moneyline"))
        fair = h / (h + a) if r.side == "home" else a / (h + a)
        return fair - 1 / american_to_decimal(r.odds)
    return np.nan


def summarize(graded: pd.DataFrame) -> pd.DataFrame:
    """Record and profit for the Home list and for each market (settled bets only)."""
    d = graded[graded.result.isin(["win", "loss", "push"])]
    groups = [("Home top 10", d[d["rank"].notna()])] + [(m, x) for m, x in d.groupby("market")]
    rows = []
    for name, x in groups:
        if len(x):
            rows.append(dict(group=name, bets=len(x), wins=int((x.result == "win").sum()),
                             losses=int((x.result == "loss").sum()), pushes=int((x.result == "push").sum()),
                             units=round(x.profit.sum(), 2), roi=round(x.profit.mean(), 3),
                             expected_win_rate=round(x.p_win.mean(), 3), mean_clv=round(x.clv.mean(), 3)))
    return pd.DataFrame(rows)


def by_snapshot(graded_history: pd.DataFrame) -> pd.DataFrame:
    """Game-market picks per snapshot day (history file, graded): does logging early beat logging on game day?
    Settled Home-list picks only; CLV is measured against the same closing line for every snapshot."""
    d = graded_history[graded_history["rank"].notna() & graded_history.result.isin(["win", "loss", "push"])]
    d = d[d.market.isin(["Moneyline", "Spread", "Total"])]
    if d.empty:
        return pd.DataFrame(columns=["snapshot", "market", "bets", "roi", "mean_clv", "clv_se"])
    d = d.assign(snapshot=pd.to_datetime(d.logged_at).dt.day_name())
    s = d.groupby(["snapshot", "market"]).agg(bets=("profit", "size"), roi=("profit", "mean"), mean_clv=("clv", "mean"),
                                               clv_sd=("clv", "std")).reset_index()
    s["clv_se"] = s.pop("clv_sd") / s.bets ** 0.5
    return s.round(3)


def record_line(graded: pd.DataFrame) -> str:
    """One plain sentence for the Home page, or '' when nothing has been settled yet."""
    d = graded[graded["rank"].notna() & graded.result.isin(["win", "loss", "push"])]
    if d.empty:
        return ""
    w, l, weeks, u = int((d.result == "win").sum()), int((d.result == "loss").sum()), d[["season", "week"]].drop_duplicates().shape[0], d.profit.sum()
    return (f"Home list so far: {w} wins, {l} losses, {u:+.1f} units over {weeks} week{'s' if weeks != 1 else ''} "
            f"(1 unit on each pick).")
