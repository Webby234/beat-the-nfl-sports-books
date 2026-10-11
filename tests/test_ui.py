import numpy as np, pandas as pd
from nfl_model.ui import board as B, lines_store, render as R, tracker


def test_side_trust_pulls_between_book_and_model():
    raw = B.side(0.60, 0.40, -110, -110, trust=1.0)
    none = B.side(0.60, 0.40, -110, -110, trust=0.0)
    half = B.side(0.60, 0.40, -110, -110, trust=0.5)
    assert abs(raw["p_win"] - 0.60) < 1e-9 and abs(none["p_win"] - 0.50) < 1e-9
    assert none["p_win"] < half["p_win"] < raw["p_win"]
    assert abs(raw["breakeven"] - 110 / 210) < 1e-9
    assert abs(raw["ev"] - (0.60 * (1 + 100 / 110) - 1)) < 1e-9
    assert none["ev"] < 0 < raw["ev"]                      # at the book's own number you just pay the vig


def test_side_handles_pushes_and_blank_odds():
    s = B.side(0.45, 0.45, None, None, trust=1.0)          # 10% push, blank odds -> -110
    assert s["odds"] == -110 and abs(s["p_win"] - 0.5) < 1e-9
    assert abs(s["ev"] - 0.9 * (0.5 * (1 + 100 / 110) - 1)) < 1e-9
    assert B.clean_odds(50) == -110 and B.clean_odds("+145") == 145 and B.clean_odds(float("nan")) == -110


def test_two_way_counts_ties_as_neither():
    over, under = B._two_way(3.0, np.array([-1.0, 0.0, 0.2, 1.0]), 3)     # results 2, 3, 3, 4 against a line of 3
    assert over == 0.25 and under == 0.25


def _bet(market, game, edge, **kw):
    return dict(market=market, game_id=game, edge=edge, ev=edge, pick=market, odds=-110, p_win=.5, breakeven=.5, **kw)


def test_top_bets_one_opinion_per_game_and_one_side_per_player():
    bets = [_bet("Moneyline", "g1", .05), _bet("Spread", "g1", .04), _bet("Total", "g1", .03), _bet("Total", "g1", -.03),
            _bet("Spread", "g2", .02), _bet("Rushing yards", None, .01, stat="rush_yds", player="RB One"),
            _bet("Rushing yards", None, -.05, stat="rush_yds", player="RB One")]
    top = B.top_bets(bets)
    assert [(b["market"], b["game_id"]) for b in top] == [("Moneyline", "g1"), ("Total", "g1"), ("Spread", "g2"),
                                                           ("Rushing yards", None)]
    assert len(B.top_bets(bets, n=2)) == 2


def test_home_list_leaves_out_moneyline_underdogs_only():
    dog = _bet("Moneyline", "g1", .09); dog["odds"] = 180
    fav = _bet("Moneyline", "g2", .02); fav["odds"] = -150
    plus_total = _bet("Total", "g3", .01); plus_total["odds"] = 105          # plus money, but not a moneyline
    top = B.top_bets([dog, fav, plus_total])
    assert [b["game_id"] for b in top] == ["g2", "g3"]


def test_html_is_one_line_and_escapes_names():
    b = dict(B.side(0.6, 0.4, -110, -110, 1.0), market="Spread", pick="<script>x</script> -3", team="KC",
             matchup="A at B", kickoff="Sun 1:00 PM", game_id="g")
    out = R.top_list([b], [])
    assert "\n" not in out and "<script>" not in out and "&lt;script&gt;" in out
    assert "No games with posted lines" in R.top_list([], [])
    assert "\n\n" not in R.CSS.strip()


def test_meter_stays_inside_the_track():
    far = dict(p_win=0.95, breakeven=0.50); short = dict(p_win=0.10, breakeven=0.50)
    assert "left:100.0%" in R.meter(far) and "left:0.0%" in R.meter(short) and "gain short" in R.meter(short)


def test_saved_lines_round_trip_and_replace(tmp_path=None):
    import pathlib, tempfile
    old = lines_store.PATH
    lines_store.PATH = pathlib.Path(tmp_path or tempfile.mkdtemp()) / "lines" / "prop_lines.csv"
    try:
        rows = pd.DataFrame(dict(player=["A", "B", "C"], line=[70.5, None, "x"], over_odds=[-115, None, None], under_odds=[None] * 3))
        assert lines_store.save(2026, 4, "rush_yds", rows) == 1                     # blank and junk rows dropped
        lines_store.save(2026, 4, "anytime_td", pd.DataFrame(dict(player=["A"], line=[None], over_odds=[-120], under_odds=[None])))
        lines_store.save(2026, 4, "rush_yds", pd.DataFrame(dict(player=["B"], line=[55.5], over_odds=[None], under_odds=[None])))
        got = lines_store.load(2026, 4)
        assert sorted(zip(got.stat, got.player)) == [("anytime_td", "A"), ("rush_yds", "B")]
        assert lines_store.load(2026, 5).empty
    finally:
        lines_store.PATH = old


def test_every_market_shows_exactly_one_pick_and_value_only_when_it_beats_the_price():
    mk = lambda p, odds, other, team=None: dict(B.side(p, 1 - p, odds, other, 1.0), team=team, pick="x")
    g = dict(away_name="A", home_name="H", kickoff="Sun", model_margin=2.0, model_total=44.0,
             moneyline=[mk(.42, 150, -180, "KC"), mk(.58, -180, 150, "SF")],        # pick SF; value is the underdog KC
             spread=[mk(.56, -110, -110, "KC"), mk(.44, -110, -110, "SF")],         # pick KC, 56% > 52.4%: value
             total=[mk(.50, -110, -110), mk(.50, -105, -115)])                      # tie -> better price
    out = R.game_card(g)
    assert out.count('nb-opt pick') == 3 and out.count('nb-chip') == 2 and 'nb-opt value' in out and "\n" not in out
    assert B.model_pick(g["moneyline"])["team"] == "SF" and B.model_pick(g["total"])["odds"] == -105


def test_history_tables_and_summary_rows():
    from nfl_model.ui import history as H
    H._open_weeks = lambda: {(2026, 2)}
    bets = pd.DataFrame(dict(season=[2026] * 4 + [2025] * 2, week=[1, 1, 2, 2, 5, 5], market="Spread", is_pick=True,
                             result=["win", "loss", "win", "push", "loss", "loss"], profit=[.91, -1, .91, 0, -1, -1],
                             rank=[1, 2, 1, np.nan, 1, 2]))
    lt = H.lines_table(bets, 2026)
    assert lt[""].tolist() == ["Week 1", "Week 2 (in progress)", "This season", "Last season"]
    assert lt["Spread picks"].tolist() == ["1-1 (50%)", "1-0 (100%)", "2-1 (67%)", "0-2 (0%)"] and lt["Total picks"].iloc[0] == "-"
    ht = H.home_table(bets, 2026)
    assert ht["Top 10 record"].iloc[2] == "2-1 (67%)" and ht["Profit (units)"].iloc[2] == "+0.8"
    y = pd.DataFrame(dict(season=2026, week=1, actual=[100.0, 10.0], pred=[90.0, 40.0], base=[80.0, 40.0], q10=[50, 20],
                          q25=[70, 30], q75=[110, 50], q90=[130, 60]))
    row = H.yards_table(y, 2026).iloc[0]
    assert row["Average miss"] == "20.0" and row["Inside the thick bar (aim 50%)"] == "50%" and row["Players"] == 2
    td = pd.DataFrame(dict(season=2026, week=1, actual=[1.0, 0.0, 1.0], p=[.6, .5, .2]))
    assert H.td_table(td, 2026)["Scorers actual"].iloc[0] == 2
    html = R.simple_table(lt)
    assert html.count('class="sum"') == 2 and "\n" not in html and "No finished weeks" in R.simple_table(pd.DataFrame())


def test_past_weeks_are_scored_from_earlier_seasons_only():
    from nfl_model.ui import history as H
    seen = {}
    def fake(train, up):
        seen["train_max"], seen["scored"] = train.season.max(), set(up.season)
        return []
    old = B.score_games; B.score_games = fake
    try:
        df = pd.DataFrame(dict(season=[2024, 2025, 2025, 2026], game_type="REG", home_score=[1.0, 1.0, np.nan, 1.0],
                               home_moneyline=-110, spread_line=1.0))
        H.past_line_bets(df, 2025)
    finally:
        B.score_games = old
    assert seen == dict(train_max=2024, scored={2025})


def _game(spread_home=2.5, total=44.5):
    res = np.random.default_rng(0).normal(0.0, 13.0, 4000)      # continuous, like real model residuals
    g = dict(game_id="g1", matchup="A at H", kickoff="Sun", home="NYG", away="ARI", home_name="Giants", away_name="Cardinals",
             season=2026, week=4, yours=False,
             listed=dict(away_ml=-140, home_ml=120, home_spread=spread_home, away_spread_odds=-110, home_spread_odds=-110,
                         total=total, over_odds=-110, under_odds=-110),
             sim=dict(p_home=0.45, margin=-2.0, margin_res=res, total=44.0, total_res=res))
    g.update(B.price_game(g, g["listed"]))
    return g


def test_a_better_line_at_your_book_adds_edge_and_blank_fields_keep_listed():
    g = _game()
    saved = pd.DataFrame([dict(game_id="g1", home_spread=3.5, home_ml=np.nan, total=np.nan)])
    g2 = B.apply_book_lines([g], saved)[0]
    home, home2 = g["spread"][1], g2["spread"][1]
    assert home2["pick"] == "Giants +3.5" and home2["edge"] > home["edge"] and g2["yours"] and not g["yours"]
    assert g2["moneyline"][1]["odds"] == 120 and g2["total"][0]["line"] == 44.5         # untouched fields
    better_price = B.apply_book_lines([g], pd.DataFrame([dict(game_id="g1", home_ml=140)]))[0]["moneyline"][1]
    assert better_price["p_win"] == g["moneyline"][1]["p_win"] and better_price["edge"] > g["moneyline"][1]["edge"]
    assert B.apply_book_lines([g], pd.DataFrame([dict(game_id="other", home_spread=9)]))[0] is g


def test_teaser_legs_and_history_rules():
    legs = B.teaser_legs([_game(2.5, 44.5), _game(-2.0, 60.0), _game(3.5, 40.0), _game(-1.5, 49.0)])
    assert [l["pick"] for l in legs] == ["Giants +8.5", "Cardinals +7.5"]               # 60 total and +3.5 are out
    games = pd.DataFrame(dict(game_type="REG", season=2020, week=1, spread_line=[2.5, -2.0, 2.5, 6.0, 2.0],
                              total_line=[44.0, 44.0, 55.0, 44.0, 44.0], home_score=[27, 20, 30, 30, 28], away_score=[20, 27, 0, 0, 20]))
    h = B.teaser_history(games)
    # g1: away dog +2.5 loses by 7 -> +8.5 covers; g2: home dog +2 loses by 7 -> +8 covers; g5: away dog +2 loses by 8 -> tie
    assert len(h) == 3 and h.won.tolist()[:2] == [1.0, 1.0] and np.isnan(h.won.iloc[2])
    s = B.teaser_stats(pd.DataFrame(dict(season=2020, won=[1.0] * 3 + [0.0])))
    assert s["legs"] == 4 and abs(s["roi"][-120] - (0.75 ** 2 * (1 + 100 / 120) - 1)) < 1e-9 and s["low"] < 0.75 < s["high"]


def test_game_lines_store_keeps_only_your_changes():
    import pathlib, tempfile
    old = lines_store.GAME_PATH
    lines_store.GAME_PATH = pathlib.Path(tempfile.mkdtemp()) / "lines" / "game_lines.csv"
    try:
        listed = pd.DataFrame([dict(game_id=i, **_game()["listed"]) for i in ("g1", "g2")])
        edited = listed.copy(); edited.loc[0, "home_spread"] = 3.0; edited.loc[0, "total"] = None
        assert lines_store.save_game_lines(2026, 4, edited, listed) == 1
        got = lines_store.load_game_lines(2026, 4)
        assert got.game_id.tolist() == ["g1"] and got.home_spread.iloc[0] == 3.0 and pd.isna(got.home_ml.iloc[0])
        assert lines_store.save_game_lines(2026, 4, listed, listed) == 0 and lines_store.load_game_lines(2026, 4).empty
    finally:
        lines_store.GAME_PATH = old


def test_home_list_numbering_continues_and_teaser_markup():
    b = dict(B.side(0.6, 0.4, -110, -110, 1.0), market="Spread", pick="X -3", team="KC", matchup="A at B", kickoff="", game_id="g")
    assert ">4<" in R.top_list([b], [], start=4) and R.top_list([], [], start=4) == ""
    assert "No games qualify" in R.teaser_list([]) and "Giants +8.5" in R.teaser_list(B.teaser_legs([_game()]))
    assert "Your lines" in R.game_card(dict(_game(), yours=True, model_margin=1.0, model_total=44.0))


def _pick(**kw):
    base = dict(season=2026, week=4, game_id="g1", market="Spread", stat=None, player=None, player_id=None, team="AAA",
                pick="x", side="home", line=3.0, odds=-110, p_win=.55, breakeven=.524, edge=.026, ev=.05, rank=1.0)
    base.update(kw); return base


def test_grading_every_market():
    games = pd.DataFrame(dict(game_id=["g1", "g2"], home_score=[27.0, None], away_score=[24.0, None]))
    skill = pd.DataFrame(dict(season=2026, week=4, player_id=["p1", "p2"], rushing_yards=[80.0, 10.0], receiving_yards=0.0,
                              receptions=0.0, passing_yards=0.0, passing_tds=0.0, rushing_tds=[1, 0], receiving_tds=0))
    picks = pd.DataFrame([
        _pick(),                                                        # home -3, won by 3 -> push
        _pick(side="away"),                                             # away +3 -> push
        _pick(line=2.5),                                                # home -2.5 -> win
        _pick(market="Moneyline", side="away", line=None, odds=150),    # away lost
        _pick(market="Total", side="over", line=50.5),                  # 51 points -> win
        _pick(market="Total", side="under", line=50.5),                 # loss
        _pick(market="Rushing yards", stat="rush_yds", player_id="p1", side="over", line=79.5),      # 80 -> win
        _pick(market="Rushing yards", stat="rush_yds", player_id="p2", side="under", line=9.5),      # 10 -> loss
        _pick(market="Anytime touchdown", stat="anytime_td", player_id="p1", side="yes", line=None, odds=120),
        _pick(market="Anytime touchdown", stat="anytime_td", player_id="zz", side="yes", line=None),  # did not play
        _pick(game_id="g2"),                                            # not played yet
    ])
    g = tracker.grade(picks, games, skill)
    assert g.result.tolist()[:10] == ["push", "push", "win", "loss", "win", "loss", "win", "loss", "win", "void"]
    assert pd.isna(g.result.iloc[10]) and pd.isna(g.profit.iloc[10])
    assert abs(g.profit.iloc[2] - 100 / 110) < 1e-9 and g.profit.iloc[3] == -1 and abs(g.profit.iloc[8] - 1.2) < 1e-9
    s = tracker.summarize(g).set_index("group")
    assert s.loc["Home top 10", "bets"] == 9 and s.loc["Home top 10", "wins"] == 4      # void and unplayed excluded
    assert "4 wins, 3 losses" in tracker.record_line(g)
    assert tracker.record_line(g[g.game_id == "g2"]) == ""


def _leg(game, ev, odds=-110, market="Total", **kw):
    return dict(dict(game_id=game, market=market, odds=odds, p_win=(1 + ev) / B.american_to_decimal(odds), ev=ev,
                     pick=f"leg {game}", team=None, matchup="A at B", kickoff="Sun"), **kw)


def test_parlays_use_value_legs_from_different_games_and_price_like_a_sportsbook():
    legs = [_leg("g1", .05), _leg("g1", .04, market="Rushing yards", player="RB"),       # same game as the best leg
            _leg("g2", .03), _leg("g3", .02), _leg("g4", -.01),                        # g4 does not clear break-even
            _leg("g5", .10, odds=150, market="Moneyline", team="NYG")]                   # moneyline underdog: left out
    pool = B.parlay_legs(legs)
    assert [b["game_id"] for b in pool] == ["g1", "g2", "g3"] and pool[0]["ev"] == .05
    p = B.parlay(pool[:2])
    assert abs(p["decimal"] - (210 / 110) ** 2) < 1e-9 and p["odds"] == 264
    assert abs(p["ev"] - (1.05 * 1.03 - 1)) < 1e-9 and abs(p["breakeven"] - 1 / p["decimal"]) < 1e-12
    two = B.best_parlays(legs, 2)
    assert len(two) == 1 and {b["game_id"] for b in two[0]["legs"]} == {"g1", "g2"}   # a second would reuse a leg
    assert B.best_parlays(legs, 4) == []


def test_past_parlays_grade_pushes_and_losses_like_a_sportsbook():
    from nfl_model.ui import history as H
    rows = [dict(_leg(g, ev), season=2025, week=1, result=r) for g, ev, r in
            (("g1", .05, "win"), ("g2", .04, "push"), ("g3", .03, "win"), ("g4", .02, "loss"))]
    p = H.past_parlays(pd.DataFrame(rows)).set_index("n")
    d = 210 / 110
    two = H.past_parlays(pd.DataFrame(rows[:2]))                                   # win + push: paid as a single
    assert len(two) == 1 and abs(two.profit.iloc[0] - (d - 1)) < 1e-9 and two.won.iloc[0]
    assert abs(p.loc[3, "profit"] - (d * d - 1)) < 1e-9                              # win, push, win: a 2-leg winner
    assert len(p.loc[2]) == 2                                                       # g1+g2 and g3+g4, no shared legs
    lost = H.past_parlays(pd.DataFrame([rows[0], rows[3]]))
    assert lost.profit.iloc[0] == -1.0 and not lost.won.iloc[0]
    t = H.parlay_table(H.past_parlays(pd.DataFrame(rows)), 2025)
    assert "2-leg won" in t.columns and t.iloc[0, 0] == "Week 1"


def test_site_chrome_and_parlay_markup():
    assert R.asset_uri("logo_mark.webp").startswith("data:image/webp;base64,") and R.asset_uri("missing.png") == ""
    for out in (R.brand_bar(), R.footer(), R.hero("k", "Week 5", "picks", "sub <x>", [("14", "games")], "now"),
                R.explore([("Parlays", "two & three")])):
        assert "\n" not in out
    assert "sub &lt;x&gt;" in R.hero("k", "Week 5", "picks", "sub <x>", [])
    p = B.parlay([_leg("g1", .05), _leg("g2", .03)])
    html = R.parlay_list([p], [], 2)
    assert "+264" in html and "Parlay 1" in html and "clears" in html and "expected return" in html
    assert "Not enough bets" in R.parlay_list([], [], 3)
    f = pd.DataFrame(dict(legs=[1, 2, 3], bets=[100, 40, 30], win_rate=[.52, .27, .14], expected=[.52, .28, .15],
                          roi=[.03, 0.0, .03], lo=[-.02, -.15, -.2], hi=[.09, .16, .3], first=2015, last=2026))
    facts = R.parlay_facts(f)
    assert "single bets" in facts and "27%" in facts and R.parlay_facts(None) == ""
    top = [dict(_leg("g1", .05), pick="Under 44.5", breakeven=.524, edge=.02)]
    assert "NO. 1" in R.featured(top, []) and "No games with posted lines" in R.featured([], [])


def test_closing_line_value_per_market():
    games = pd.DataFrame(dict(game_id=["g1"], home_score=[27.0], away_score=[24.0], spread_line=[4.0], total_line=[49.0],
                              home_moneyline=[-200], away_moneyline=[170]))
    skill = pd.DataFrame(columns=["season", "week", "player_id", "rushing_tds", "receiving_tds"])
    picks = pd.DataFrame([
        _pick(line=3.0),                                                # home -3, closed -4: got 1 point better
        _pick(side="away", line=3.0),                                   # away +3, closed +4: 1 point worse
        _pick(market="Total", side="under", line=50.5),                 # under 50.5, closed 49: 1.5 better
        _pick(market="Moneyline", side="home", line=None, odds=-150),   # -150 bet, closed -200
        _pick(market="Rushing yards", stat="rush_yds", player_id="p1", side="over", line=79.5),
    ])
    c = tracker.grade(picks, games, skill).clv.tolist()
    assert c[0] == 1.0 and c[1] == -1.0 and c[2] == 1.5 and pd.isna(c[4])
    h, a = 200 / 300, 100 / 270
    assert abs(c[3] - (h / (h + a) - 0.6)) < 1e-9 and c[3] > 0                   # the close made -150 a good price
    assert "mean_clv" in tracker.summarize(tracker.grade(picks, games, skill)).columns


def test_prop_trust_waits_for_enough_bets_then_checks_week_by_week():
    from nfl_model.ui import calibrate as C
    assert C.prop_trust(pd.DataFrame(dict(market=["Rushing yards"], result=["win"], season=2026, week=1,
                                          p_raw=0.6, fair=0.5))) is None
    rng = np.random.default_rng(0)
    n = 1500
    fair, p_raw = rng.uniform(0.35, 0.65, n), rng.uniform(0.25, 0.75, n)
    z = lambda p: np.log(p / (1 - p))
    p_true = 1 / (1 + np.exp(-(z(fair) + 0.6 * (z(p_raw) - z(fair)))))
    d = pd.DataFrame(dict(market="Rushing yards", season=2026, week=np.repeat(np.arange(1, 16), 100), p_raw=p_raw,
                          fair=fair, result=np.where(rng.random(n) < p_true, "win", "loss")))
    r = C.prop_trust(pd.concat([d, d.head(50).assign(market="Total")]))        # game markets are left out
    assert r["n"] == n and r["n_oos"] == 11 * 100 and 0.3 < r["trust"] < 0.9


def test_log_keeps_finished_games_and_replaces_live_ones():
    import pathlib, tempfile
    old = tracker.PATH
    tracker.PATH = pathlib.Path(tempfile.mkdtemp()) / "lines" / "picks_log.csv"
    try:
        board = dict(season=2026, week=4, games=[dict(game_id="g1"), dict(game_id="g2")])
        a, b = _pick(pick="first"), _pick(game_id="g2", pick="second")
        assert tracker.log(board, [a, b], []) == 2
        later = dict(board, games=[dict(game_id="g2")])                  # g1 has been played and left the board
        prop = _pick(game_id="g2", market="Rushing yards", player="RB", pick="prop", edge=.01)
        worse = _pick(game_id="g2", market="Rushing yards", player="RB", pick="other side", edge=-.05)
        tracker.log(later, [_pick(game_id="g2", pick="second, new price")], [prop, worse])
        got = tracker.load()
        assert sorted(got.pick) == ["first", "prop", "second, new price"]
        assert got.set_index("pick").loc["prop"].isna()["rank"]
    finally:
        tracker.PATH = old


def test_scheduled_log_keeps_every_snapshot_and_compares_them():
    import pathlib, tempfile
    tmp = pathlib.Path(tempfile.mkdtemp()) / "log"
    path, hist = tmp / "picks_log.csv", tmp / "picks_history.csv"
    board = dict(season=2026, week=4, games=[dict(game_id="g1")])
    tracker.log(board, [_pick(line=3.0, pick="wed")], [], path=path, history=hist)
    tracker.log(board, [_pick(line=4.5, pick="sun")], [], path=path, history=hist)
    assert tracker.load(path).pick.tolist() == ["sun"]                   # graded: the last price before the game
    h = tracker.load(hist)
    assert h.pick.tolist() == ["wed", "sun"]
    h["logged_at"] = ["2026-10-07 14:00", "2026-10-11 15:00"]
    games = pd.DataFrame(dict(game_id=["g1"], home_score=[27.0], away_score=[24.0], spread_line=[4.0]))
    no_skill = pd.DataFrame(columns=["season", "week", "player_id", "rushing_tds", "receiving_tds"])
    s = tracker.by_snapshot(tracker.grade(h, games, no_skill)).set_index("snapshot")
    assert s.loc["Wednesday", "mean_clv"] == 1.0 and s.loc["Sunday", "mean_clv"] == -0.5      # home -3 beat a -4 close
    assert s.loc["Wednesday", "roi"] == 0.0 and s.loc["Sunday", "roi"] == -1.0                 # push, then a loss at -4.5


def test_hosted_app_reads_the_log_from_the_bet_log_branch():
    import importlib, os, pathlib, tempfile
    from nfl_model import config
    assert tracker.LOG_URL.endswith("/bet-log/picks_log.csv")
    old = (os.environ.get("NFL_BOARD_HOSTED"), os.environ.get("NFL_BOARD_LOG_URL"))
    try:
        os.environ["NFL_BOARD_HOSTED"], os.environ["NFL_BOARD_LOG_URL"] = "1", "file:///nonexistent/picks_log.csv"
        importlib.reload(config); T = importlib.reload(tracker)
        T.PATH = pathlib.Path(tempfile.mkdtemp()) / "picks_log.csv"
        assert T.load().empty and list(T.load().columns) == T.COLS      # unreachable log: empty, never an error
        pd.DataFrame([_pick(pick="from repo")]).to_csv(T.PATH, index=False)
        assert T.load().pick.tolist() == ["from repo"]                  # before the first Action run: the repo's copy
    finally:
        for k, v in zip(("NFL_BOARD_HOSTED", "NFL_BOARD_LOG_URL"), old):
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        importlib.reload(config); importlib.reload(tracker)


def test_hosted_lines_stay_in_the_visitors_session_and_off_the_disk():
    import pathlib, tempfile
    old = (lines_store.PATH, lines_store.GAME_PATH)
    tmp = pathlib.Path(tempfile.mkdtemp())
    lines_store.PATH, lines_store.GAME_PATH = tmp / "lines" / "prop_lines.csv", tmp / "lines" / "game_lines.csv"
    try:
        alice, bob = {}, {}
        rows = pd.DataFrame(dict(player=["A"], line=[70.5], over_odds=[-110], under_odds=[-110]))
        assert lines_store.save(2026, 4, "rush_yds", rows, store=alice) == 1
        listed = pd.DataFrame([dict(game_id="g1", **_game()["listed"])])
        edited = listed.copy(); edited.loc[0, "home_spread"] = 3.0
        assert lines_store.save_game_lines(2026, 4, edited, listed, store=alice) == 1
        assert len(lines_store.load(2026, 4, store=alice)) == 1 and len(lines_store.load_game_lines(2026, 4, store=alice)) == 1
        assert lines_store.load(2026, 4, store=bob).empty and lines_store.load_game_lines(2026, 4, store=bob).empty
        assert not (tmp / "lines").exists()                              # nothing touched the shared disk
        assert lines_store.load(2026, 4).empty                           # and the file-based store is unaffected
    finally:
        lines_store.PATH, lines_store.GAME_PATH = old


def test_hosted_flag_follows_the_environment():
    import importlib, os, nfl_model.config as C
    try:
        os.environ["NFL_BOARD_HOSTED"] = "1"; assert importlib.reload(C).HOSTED
        os.environ["NFL_BOARD_HOSTED"] = "0"; assert not importlib.reload(C).HOSTED
    finally:
        os.environ.pop("NFL_BOARD_HOSTED", None); importlib.reload(C)


def test_loading_screen_markup_and_progress_hooks():
    import inspect
    from nfl_model.ui import history as H
    assert "Setting up" in R.loading() and "\n" not in R.loading("a", "b") and "&lt;" in R.loading_step("<x>")
    for fn in (B.build_board, B.build_props, H.build, H.load_or_build, H.past_props):
        assert inspect.signature(fn).parameters["progress"].default is None      # progress reporting is optional


def test_timestamp_uses_no_platform_specific_codes():
    import inspect
    assert B._stamp(pd.Timestamp("2026-10-02 19:09")) == "Oct 2, 7:09 PM"
    assert B._stamp(pd.Timestamp("2026-10-12 00:05")) == "Oct 12, 12:05 AM"
    for mod in (B, R, lines_store, tracker):
        assert "%-" not in inspect.getsource(mod).replace("%-d / %-I", "")     # these break strftime on Windows


def _trust_data(true_trust, seasons=range(2012, 2027), n=400, seed=0):
    rng = np.random.default_rng(seed)
    rows = []
    for s in seasons:
        market, gap = rng.normal(0, 1, n), rng.normal(0, 0.4, n)
        p = 1 / (1 + np.exp(-(market + true_trust * gap)))
        rows.append(pd.DataFrame(dict(season=s, market=market, gap=gap, y=(rng.random(n) < p).astype(float))))
    return pd.concat(rows, ignore_index=True)


def test_trust_is_checked_on_seasons_the_fit_never_saw():
    from nfl_model.ui import calibrate as C
    d = _trust_data(0.6)
    wf = C.walk_forward(d, first=2017)
    assert wf.season.min() == 2017 and wf.season.nunique() == 10
    # the 2017 trust can only come from 2012-2016
    assert abs(wf[wf.season == 2017].trust.iloc[0] - C.fit_trust(d[d.season < 2017])) < 1e-12


def test_trust_kept_only_when_the_model_helped_out_of_sample():
    from nfl_model.ui import calibrate as C
    useful = C.summarize(_trust_data(0.6), n_boot=20)
    assert useful["oos_gain_x1000"] > 0 and 0.3 < useful["trust"] < 0.9
    noise = C.summarize(_trust_data(0.0, seed=1), n_boot=20)
    assert noise["oos_gain_x1000"] < 0 and noise["trust"] == 0.0


if __name__ == "__main__":
    bad = 0
    for n, f in list(globals().items()):
        if n.startswith("test_"):
            try: f(); print("ok  ", n)
            except Exception as e: bad += 1; print("FAIL", n, repr(e))
    raise SystemExit(bad)
