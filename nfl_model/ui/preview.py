"""Static preview of the app's pages (no Streamlit needed):  python -m nfl_model.ui.preview [out.html]"""
import sys
import pandas as pd
from . import board as B, lines_store, render as R


def build_html(board: dict, lines: pd.DataFrame) -> str:
    games, props = board["games"], board["props"]
    prop_bets = B.price_prop_lines(props, lines, games)
    top = B.top_bets(B.game_bets(games) + prop_bets)
    of = lambda stat: [b for b in prop_bets if b.get("stat") == stat]
    clear = [b for b in top if b["ev"] > 0]
    parts = [R.brand_bar(),
             R.hero(f"NFL · {board['season']} season", f"Week {board['week']}", "picks",
                    "The model's best-priced bets this week across every market.",
                    [(str(len(games)), "games on the board"), (f"{len(clear)} of {len(top)}", "top bets clear break-even"),
                     (f"{100 * top[0]['edge']:+.1f}" if top else "-", "biggest edge, in win-chance points"),
                     ("-", "Home list record this season")], stamp=f"Updated {board.get('built', '')}"),
             R.section("Top three"), R.featured(top[:3], games), R.section("The next seven"),
             R.top_list(top[3:], games, start=4), R.section("Parlays")]
    for n in (2, 3):
        parts += [R.section(f"{n}-leg parlays"), R.parlay_list(B.best_parlays(B.game_bets(games) + prop_bets, n), games, n)]
    parts += [R.section("Moneyline & Spread"), R.lines_key()]
    parts += [R.game_card(g) for g in games[:3]]
    for stat, title in (("qb_pass_yds", "Passing yards"), ("rush_yds", "Rushing yards"), ("rec_yds", "Receiving yards")):
        if stat in props:
            parts += [R.section(title), R.yards_table(props[stat].head(8), of(stat))]
    if "receptions" in props:
        parts += [R.section("Receptions"), R.count_table(props["receptions"].head(6), of("receptions"), "catches")]
    if "anytime_td" in props:
        parts += [R.section("Anytime touchdown"), R.td_table(props["anytime_td"].head(8), of("anytime_td"))]
    body = "".join(parts + [R.footer()])
    return (f'<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'{R.style_tag()}</head><body style="margin:0;padding:32px 20px"><div style="max-width:1080px;margin:0 auto">{body}</div></body></html>')


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "board_preview.html"
    bd = B.build_board()
    open(out, "w", encoding="utf-8").write(build_html(bd, lines_store.load(bd["season"], bd["week"])))
    print("wrote", out)
