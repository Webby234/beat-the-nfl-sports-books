"""Player prop lines from The Odds API (free tier), for the scheduled pick log.

Props have no free price history, so the only way to measure prop trust on real prices is to record them as they
are offered. The events list is free; each game's props cost (markets returned x regions) credits, so one snapshot
of the four markets below is about 4 credits a game, ~60 a week, inside the free tier's monthly allowance.

One bookmaker's two-way price is kept per player (the first of BOOKS that offers both sides at the same line), so
every logged line is one you could actually have bet.
NOTE: parse_props() is unit-tested on a hand-written sample shaped like the documented v4 response.
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request

import pandas as pd

BASE = "https://api.the-odds-api.com/v4/sports/americanfootball_nfl"
MARKETS = {"player_pass_yds": "qb_pass_yds", "player_rush_yds": "rush_yds", "player_reception_yds": "rec_yds",
           "player_receptions": "receptions"}
BOOKS = ["draftkings", "fanduel", "betmgm", "williamhill_us", "espnbet", "betrivers"]   # preference order
COLS = ["stat", "player", "line", "over_odds", "under_odds", "book", "game_start"]


def _get(path: str, timeout: int = 30, **params):
    qs = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{BASE}/{path}?{qs}", timeout=timeout) as r:
        return json.loads(r.read())


def parse_props(event: dict) -> pd.DataFrame:
    """One row per (stat, player): the first preferred book with both Over and Under at the same line."""
    found = {}
    for bk in event.get("bookmakers", []):
        for mk in bk.get("markets", []):
            stat = MARKETS.get(mk.get("key"))
            if stat is None:
                continue
            sides = {}
            for o in mk.get("outcomes", []):
                sides.setdefault(o.get("description"), {})[o.get("name")] = (o.get("point"), o.get("price"))
            for player, s in sides.items():
                if player and "Over" in s and "Under" in s and s["Over"][0] == s["Under"][0] and s["Over"][0] is not None:
                    found.setdefault((stat, player), []).append((bk.get("key"), s["Over"][0], s["Over"][1], s["Under"][1]))
    rank = lambda b: BOOKS.index(b) if b in BOOKS else len(BOOKS)
    rows = []
    for (stat, player), offers in found.items():
        book, line, over, under = min(offers, key=lambda x: rank(x[0]))
        rows.append(dict(stat=stat, player=player, line=float(line), over_odds=float(over), under_odds=float(under),
                         book=book, game_start=event.get("commence_time")))
    return pd.DataFrame(rows, columns=COLS)


def fetch_prop_lines(until: pd.Timestamp, api_key: str | None = None) -> pd.DataFrame:
    """Prop lines for every game kicking off before `until` (UTC). Pass the end of the board's week: a later game's
    line would otherwise be matched to this week's projection for the same player. Started games are not listed."""
    api_key = api_key or os.environ.get("ODDS_API_KEY")
    if not api_key:
        raise RuntimeError("Set the ODDS_API_KEY environment variable (or pass api_key).")
    events = [e for e in _get("events", apiKey=api_key)                                   # free: no credits used
              if pd.Timestamp(e["commence_time"]) <= until]
    frames = [parse_props(_get(f"events/{e['id']}/odds", apiKey=api_key, regions="us", oddsFormat="american",
                               markets=",".join(MARKETS))) for e in events]
    d = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLS)
    return d.drop_duplicates(["stat", "player"]).reset_index(drop=True)
