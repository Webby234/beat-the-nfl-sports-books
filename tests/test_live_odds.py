"""Parser/aggregation test on a hand-written sample shaped like The Odds API v4 h2h response."""
import pandas as pd

from nfl_model.betting.live_odds import best_and_consensus, parse_events
from nfl_model.betting.odds import devig_two_way
from nfl_model.betting.picks import picks_table

SAMPLE = [{
    "id": "x1", "commence_time": "2026-10-04T17:00:00Z",
    "home_team": "Houston Texans", "away_team": "Dallas Cowboys",
    "bookmakers": [
        {"key": "bk1", "title": "BookOne", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Houston Texans", "price": -160}, {"name": "Dallas Cowboys", "price": 140}]}]},
        {"key": "bk2", "title": "BookTwo", "markets": [{"key": "h2h", "outcomes": [
            {"name": "Dallas Cowboys", "price": 150}, {"name": "Houston Texans", "price": -175}]}]},
        {"key": "bk3", "title": "SpreadsOnly", "markets": [{"key": "spreads", "outcomes": []}]},
    ]}, {"id": "x2", "home_team": "Unknown FC", "away_team": "Dallas Cowboys", "bookmakers": []}]


def test_parse_and_best_prices():
    books = parse_events(SAMPLE)
    assert len(books) == 2 and set(books.book) == {"BookOne", "BookTwo"}
    assert set(books.home_team) == {"HOU"} and set(books.away_team) == {"DAL"}
    g = best_and_consensus(books).iloc[0]
    assert g.home_moneyline == -160 and g.home_book == "BookOne"      # least negative = best for home
    assert g.away_moneyline == 150 and g.away_book == "BookTwo"       # larger positive = best for away
    f1 = devig_two_way(-160, 140)[0]; f2 = devig_two_way(-175, 150)[0]
    assert abs(g.market_home_prob - (f1 + f2) / 2) < 1e-12 and g.n_books == 2


def test_live_prices_flow_into_picks():
    games = pd.DataFrame({"game_id": ["g1"], "gameday": [pd.Timestamp("2026-10-04")], "home_team": ["HOU"],
                          "away_team": ["DAL"], "home_moneyline": [-200.0], "away_moneyline": [170.0],
                          "p_home": [0.50]})
    live = best_and_consensus(parse_events(SAMPLE))
    cands, bets = picks_table(games, min_edge=0.0, live=live)
    assert set(cands.moneyline) == {-160.0, 150.0}                    # live best prices replaced file prices
    assert (cands.market_prob.sum() - 2.0) < 1e-9 and abs(cands.groupby("side").market_prob.first().sum() - 1) < 1e-9


def test_prop_lines_one_real_two_way_price_per_player():
    from nfl_model.betting.live_props import parse_props
    o = lambda side, who, price, point: {"name": side, "description": who, "price": price, "point": point}
    ev = {"id": "e1", "commence_time": "2026-10-11T17:00:00Z", "bookmakers": [
        {"key": "smallbook", "markets": [{"key": "player_pass_yds", "outcomes": [
            o("Over", "Joe Burrow", -105, 262.5), o("Under", "Joe Burrow", -125, 262.5)]}]},
        {"key": "fanduel", "markets": [
            {"key": "player_pass_yds", "outcomes": [o("Over", "Joe Burrow", -110, 259.5), o("Under", "Joe Burrow", -110, 259.5)]},
            {"key": "player_rush_yds", "outcomes": [o("Over", "Chase Brown", -115, 55.5), o("Under", "Chase Brown", -105, 54.5)]},
            {"key": "player_pass_tds", "outcomes": [o("Over", "Joe Burrow", -150, 1.5), o("Under", "Joe Burrow", 120, 1.5)]}]},
        {"key": "draftkings", "markets": [{"key": "player_rush_yds", "outcomes": [
            o("Over", "Chase Brown", -110, 56.5), o("Under", "Chase Brown", -110, 56.5), o("Over", "Only Over", -110, 9.5)]}]}]}
    d = parse_props(ev).set_index(["stat", "player"])
    assert len(d) == 2                                                   # unknown market, one-sided offer dropped
    b = d.loc[("qb_pass_yds", "Joe Burrow")]
    assert b.book == "fanduel" and b.line == 259.5 and b.over_odds == -110   # preferred book wins over smallbook
    c = d.loc[("rush_yds", "Chase Brown")]
    assert c.book == "draftkings" and c.line == 56.5                     # fanduel's mismatched lines are not a pair


if __name__ == "__main__":
    test_parse_and_best_prices(); print("PASS test_parse_and_best_prices")
    test_live_prices_flow_into_picks(); print("PASS test_live_prices_flow_into_picks")
    test_prop_lines_one_real_two_way_price_per_player(); print("PASS test_prop_lines_one_real_two_way_price_per_player")
