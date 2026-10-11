"""HTML for the app. Pure strings, no Streamlit, so the look can be previewed and tested on its own.

Every builder returns one line of HTML (no blank lines or indentation), which keeps Streamlit's
markdown renderer from mangling it.
"""
from __future__ import annotations
import base64
from functools import lru_cache
from html import escape
import pandas as pd
from ..config import ROOT, logo_url
from .board import PROP_LABEL, model_pick, nick

WINDOW = 0.08          # the meter shows break-even +/- this many points of win chance

CSS = """
@import url('https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&display=swap');
:root{--chalk:#F3F6FB;--card:#FFFFFF;--ink:#0B1A3A;--brand:#1463D8;--brand-soft:#E5EEFC;--accent:#FF7A1A;--navy:#0A1F5C;--cyan:#19B4F0;--muted:#58677F;--rule:#DCE3EE;
--display:'Barlow Condensed','Arial Narrow','Roboto Condensed',sans-serif;--body:'Barlow','Segoe UI',system-ui,sans-serif}
html,body,.stApp,[data-testid="stAppViewContainer"]{background:var(--chalk);color:var(--ink);font-family:var(--body)}
[data-testid="stSidebar"],[data-testid="collapsedControl"],[data-testid="stSidebarCollapsedControl"]{display:none}
header[data-testid="stHeader"]{background:transparent}
.block-container,[data-testid="stMainBlockContainer"]{max-width:1080px;padding-top:2.4rem;padding-bottom:4rem}
.stTabs [data-baseweb="tab-list"]{gap:30px;border-bottom:1px solid var(--rule)}
.stTabs [data-baseweb="tab"]{padding:10px 0;background:transparent;color:var(--muted)}
.stTabs [data-baseweb="tab"] p{font-family:var(--display);font-size:1.25rem;font-weight:600;letter-spacing:.01em}
.stTabs [data-baseweb="tab"][aria-selected="true"]{color:var(--ink)}
.stTabs [data-baseweb="tab-highlight"]{background:var(--accent);height:4px}
.stTabs [data-baseweb="tab-border"]{display:none}
.stTabs .stTabs [data-baseweb="tab-list"]{gap:8px;border-bottom:0;margin:6px 0 4px}
.stTabs .stTabs [data-baseweb="tab"]{padding:6px 18px;border:1px solid var(--rule);border-radius:999px;background:var(--card)}
.stTabs .stTabs [data-baseweb="tab"] p{font-family:var(--body);font-size:.95rem;font-weight:600}
.stTabs .stTabs [data-baseweb="tab"][aria-selected="true"]{background:var(--brand);border-color:var(--brand)}
.stTabs .stTabs [data-baseweb="tab"][aria-selected="true"] p{color:#fff}
.stTabs .stTabs [data-baseweb="tab-highlight"]{display:none}
.nb *{box-sizing:border-box}
.nb{font-family:var(--body);color:var(--ink);line-height:1.4}
.nb-head{display:flex;align-items:flex-end;justify-content:space-between;gap:16px;flex-wrap:wrap;margin:0 0 18px}
.nb-week{font-family:var(--display);font-weight:700;font-size:3.4rem;line-height:.95;letter-spacing:-.01em}
.nb-sub{color:var(--muted);font-size:1rem;margin-top:6px;max-width:72ch}
.nb-stamp{color:var(--muted);font-size:.85rem}
.nb-h2{font-family:var(--display);font-weight:600;font-size:1.7rem;margin:26px 0 4px}
.nb-lead{color:var(--muted);margin:0 0 14px;max-width:70ch}
.nb-panel{background:var(--card);border:1px solid var(--rule);border-radius:14px;overflow:hidden}
.nb-row{display:grid;grid-template-columns:44px 44px minmax(0,1fr) 78px 230px 70px;align-items:center;gap:14px;padding:14px 18px;border-top:1px solid var(--rule)}
.nb-row:first-child{border-top:0}
.nb-rank{font-family:var(--display);font-weight:700;font-size:1.9rem;color:var(--muted);text-align:center}
.nb-row.clears .nb-rank{color:var(--ink)}
.nb img{overflow:hidden;font-size:0;color:transparent;flex:none}
.nb-logo{width:40px;height:40px;object-fit:contain}
.nb-logos{display:flex;flex-direction:column;align-items:center;gap:2px}
.nb-logos img{width:22px;height:22px;object-fit:contain}
.nb-pick{font-family:var(--display);font-weight:600;font-size:1.45rem;line-height:1.1}
.nb-meta{color:var(--muted);font-size:.88rem;margin-top:3px}
.nb-tag{display:inline-block;font-size:.76rem;font-weight:600;color:var(--brand);background:var(--brand-soft);border-radius:4px;padding:1px 7px;margin-right:8px}
.nb-odds{font-family:var(--display);font-weight:600;font-size:1.5rem;text-align:right}
.nb-edge{text-align:right}
.nb-edge b{font-family:var(--display);font-weight:700;font-size:1.5rem;display:block;line-height:1}
.nb-edge span{font-size:.78rem;color:var(--muted)}
.nb-row.short .nb-edge b{color:var(--muted)}
.nb-meter .track{position:relative;height:14px;border-radius:3px;background:repeating-linear-gradient(90deg,#E8EDF5 0,#E8EDF5 calc(12.5% - 1px),#fff calc(12.5% - 1px),#fff 12.5%)}
.nb-meter .gain{position:absolute;top:0;bottom:0;background:var(--brand);border-radius:2px}
.nb-meter .gain.short{background:#B8C3D4}
.nb-meter .need{position:absolute;top:-4px;bottom:-4px;left:50%;width:4px;margin-left:-2px;background:var(--accent);border-radius:2px}
.nb-meter .ball{position:absolute;top:50%;width:12px;height:12px;margin:-6px 0 0 -6px;border-radius:50%;background:var(--ink);border:2px solid #fff}
.nb-meter .lbl{display:flex;justify-content:space-between;font-size:.8rem;color:var(--muted);margin-top:5px}
.nb-meter .lbl b{color:var(--ink);font-weight:600}
.nb-note{color:var(--muted);font-size:.9rem;margin:16px 2px 0;max-width:78ch}
.nb-note b{color:var(--ink);font-weight:600}
.nb-empty{padding:28px 22px;color:var(--muted)}
.nb-game{background:var(--card);border:1px solid var(--rule);border-radius:14px;margin:0 0 14px;padding:16px 18px 14px}
.nb-ghead{display:flex;justify-content:space-between;align-items:baseline;gap:12px;flex-wrap:wrap;margin-bottom:10px}
.nb-gname{font-family:var(--display);font-weight:600;font-size:1.55rem}
.nb-gtime{color:var(--muted);font-size:.9rem}
.nb-mk{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.nb-mkcol h4{font-family:var(--body);font-size:.82rem;font-weight:600;color:var(--muted);margin:0 0 6px}
.nb-opt{display:grid;grid-template-columns:24px minmax(0,1fr) auto;align-items:center;gap:8px;padding:8px 10px;border:1px solid var(--rule);border-radius:9px;margin-bottom:6px;position:relative}
.nb-opt img{width:22px;height:22px;object-fit:contain}
.nb-opt .what{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nb-opt .price{color:var(--muted);font-weight:500;margin-left:6px}
.nb-opt .chance{font-family:var(--display);font-weight:600;font-size:1.2rem}
.nb-opt.pick{border-color:var(--brand);background:var(--brand-soft)}
.nb-opt.value::before{content:"";position:absolute;left:-1px;top:8px;bottom:8px;width:4px;border-radius:2px;background:var(--accent)}
.nb-opt .right{display:flex;align-items:center;gap:8px}
.nb-chip{font-size:.72rem;font-weight:600;border-radius:4px;padding:1px 6px;background:var(--accent);color:var(--ink)}
.nb-key{display:flex;gap:18px;flex-wrap:wrap;color:var(--muted);font-size:.88rem;margin:0 0 14px}
.nb-key span{display:inline-flex;align-items:center;gap:7px}
.nb-key i{width:26px;height:16px;border-radius:5px;border:1px solid var(--brand);background:var(--brand-soft);display:inline-block}
.nb-gfoot{color:var(--muted);font-size:.88rem;margin-top:6px}
.nb-table{width:100%;border-collapse:collapse}
.nb-table th{font-size:.8rem;font-weight:600;color:var(--muted);text-align:left;padding:10px 14px;border-bottom:1px solid var(--rule);white-space:nowrap}
.nb-table td{padding:11px 14px;border-top:1px solid var(--rule);vertical-align:middle}
.nb-table tr:first-child td{border-top:0}
.nb-table .num{font-family:var(--display);font-weight:600;font-size:1.35rem;white-space:nowrap}
.nb-table .r{text-align:right}
.nb-player{display:flex;align-items:center;gap:10px}
.nb-player img{width:26px;height:26px;object-fit:contain}
.nb-player b{font-weight:600;display:block;line-height:1.15}
.nb-player span{color:var(--muted);font-size:.84rem}
.nb-range{position:relative;height:14px;min-width:170px}
.nb-range .w{position:absolute;top:6px;height:2px;background:#B8C3D4}
.nb-range .b{position:absolute;top:3px;height:8px;border-radius:2px;background:var(--brand)}
.nb-range .m{position:absolute;top:0;width:3px;height:14px;margin-left:-1px;background:var(--ink);border-radius:1px}
.nb-bar{position:relative;height:10px;min-width:150px;background:#E8EDF5;border-radius:2px}
.nb-bar i{position:absolute;left:0;top:0;bottom:0;background:var(--brand);border-radius:2px}
.nb-verdict{font-size:.88rem;white-space:nowrap}
.nb-verdict .yes{font-weight:600;color:var(--brand)}
.nb-verdict .no{color:var(--muted)}
.nb-table tr.sum td{background:#F6F8FC;font-weight:600}
.nb-table td.c,.nb-table th.c{text-align:right}
.nb-table td.plain{font-size:1rem;white-space:nowrap}
.nb-leg{display:grid;grid-template-columns:44px minmax(0,1fr) auto;align-items:center;gap:14px;padding:14px 18px;border-top:1px solid var(--rule)}
.nb-leg:first-child{border-top:0}
.nb-leg .was{color:var(--muted);font-size:.9rem;text-align:right}
.nb-facts{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:0 0 16px}
.nb-fact{background:var(--card);border:1px solid var(--rule);border-radius:12px;padding:12px 14px}
.nb-fact b{font-family:var(--display);font-weight:700;font-size:1.7rem;display:block;line-height:1.1}
.nb-fact span{color:var(--muted);font-size:.84rem}
@media (max-width:760px){.nb-facts{grid-template-columns:repeat(2,minmax(0,1fr))}}
.nb-load{text-align:center;margin:16vh auto 18px;max-width:680px}
.nb-load h1{font-family:var(--display);font-weight:700;font-size:2.6rem;line-height:1;margin:0 0 10px;color:var(--ink)}
.nb-load p{color:var(--muted);margin:0;font-size:1rem}
.nb-step{text-align:center;color:var(--muted);font-size:.92rem;margin-top:8px;min-height:1.4em}
.nb-axis{display:flex;justify-content:space-between;font-size:.74rem;color:var(--muted);font-weight:400}
.nb-brand{display:flex;align-items:center;justify-content:space-between;gap:16px;padding:0 0 12px;margin:-1.4rem 0 8px;border-bottom:1px solid var(--rule)}
.nb-brand .lock{display:flex;align-items:center;gap:8px}
.nb-brand .mark{height:54px;width:auto}
.nb-brand .word{height:30px;width:auto}
.nb-brand .tag{color:var(--muted);font-size:.88rem;text-align:right;max-width:42ch}
.nb-hero{position:relative;overflow:hidden;border-radius:20px;padding:32px 32px 24px;margin:8px 0 26px;color:#fff;background:linear-gradient(118deg,var(--navy) 0%,#0F3A9E 55%,var(--brand) 100%)}
.nb-hero::after{content:"";position:absolute;right:-80px;top:-60px;width:460px;height:320px;transform:skewX(-24deg);pointer-events:none;background:repeating-linear-gradient(-14deg,transparent 0 16px,rgba(25,180,240,.22) 16px 18px,transparent 18px 30px,rgba(255,122,26,.18) 30px 31px)}
.nb-hero .kick{position:relative;z-index:1;font-size:.78rem;letter-spacing:.16em;text-transform:uppercase;color:#9FD8FF;font-weight:600}
.nb-hero .h{position:relative;z-index:1;font-family:var(--display);font-weight:700;font-size:3.4rem;line-height:.98;margin:8px 0 10px;color:#fff}
.nb-hero .h span{color:var(--cyan)}
.nb-hero .s{position:relative;z-index:1;color:#D6E4FF;max-width:62ch;margin:0 0 22px;font-size:1.05rem}
.nb-stats{position:relative;z-index:1;display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}
.nb-stat{background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.16);border-radius:12px;padding:12px 14px}
.nb-stat b{font-family:var(--display);font-size:1.9rem;font-weight:700;display:block;line-height:1.05;color:#fff;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.nb-stat span{font-size:.82rem;color:#C5D6F5}
.nb-hero .stamp{position:relative;z-index:1;font-size:.8rem;color:#9FB6E0;margin-top:14px}
.nb-feat{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:14px}
.nb-fcard{background:var(--card);border:1px solid var(--rule);border-top:4px solid #B8C3D4;border-radius:16px;padding:16px 18px;display:flex;flex-direction:column;gap:10px;box-shadow:0 1px 3px rgba(11,26,58,.05)}
.nb-fcard.clears{border-top-color:var(--brand)}
.nb-fcard .top{display:flex;justify-content:space-between;align-items:center}
.nb-fcard .rk{font-family:var(--display);font-weight:700;font-size:1.05rem;color:var(--muted);letter-spacing:.04em}
.nb-fcard .pk{font-family:var(--display);font-weight:600;font-size:1.6rem;line-height:1.08}
.nb-fcard .row{display:flex;justify-content:space-between;align-items:baseline}
.nb-fcard .odds{font-family:var(--display);font-weight:600;font-size:1.45rem}
.nb-fcard .ed{font-family:var(--display);font-weight:700;font-size:1.45rem;color:var(--brand)}
.nb-fcard:not(.clears) .ed{color:var(--muted)}
.nb-explore{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.nb-tile{background:var(--card);border:1px solid var(--rule);border-radius:14px;padding:14px 16px}
.nb-tile i{display:block;width:28px;height:4px;border-radius:2px;background:var(--accent);margin-bottom:10px}
.nb-tile b{font-family:var(--display);font-size:1.3rem;font-weight:600;display:block}
.nb-tile span{color:var(--muted);font-size:.9rem}
.nb-foot{margin-top:44px;padding:20px 0 0;border-top:1px solid var(--rule);display:flex;justify-content:space-between;align-items:center;gap:16px;flex-wrap:wrap;color:var(--muted);font-size:.84rem}
.nb-foot img{height:22px;width:auto}
.nb-parlay{background:var(--card);border:1px solid var(--rule);border-radius:16px;margin:0 0 14px;overflow:hidden}
.nb-parlay.clears{border-left:4px solid var(--brand)}
.nb-ph{display:flex;justify-content:space-between;align-items:center;gap:14px;flex-wrap:wrap;padding:14px 18px;background:var(--brand-soft);border-bottom:1px solid var(--rule)}
.nb-ph .t{font-family:var(--display);font-weight:700;font-size:1.45rem}
.nb-ph .t small{font-family:var(--body);font-weight:500;font-size:.85rem;color:var(--muted);margin-left:8px}
.nb-pn{display:flex;gap:22px}
.nb-pn div{text-align:right}
.nb-pn b{font-family:var(--display);font-weight:700;font-size:1.4rem;display:block;line-height:1}
.nb-pn span{font-size:.76rem;color:var(--muted)}
.nb-leg .price{text-align:right;white-space:nowrap}
.nb-leg .price b{font-family:var(--display);font-weight:600;font-size:1.3rem;display:block;line-height:1}
.nb-leg .price span{font-size:.8rem;color:var(--muted)}
@media (max-width:760px){
.nb-brand .tag{display:none}
.nb-hero{padding:24px 20px 20px}
.nb-hero .h{font-size:2.5rem}
.nb-stats{grid-template-columns:repeat(2,minmax(0,1fr))}
.nb-feat,.nb-explore{grid-template-columns:1fr}
.nb-pn{gap:14px}
.nb-week{font-size:2.6rem}
.nb-pick{font-size:1.2rem}
.nb-odds{font-size:1.25rem}
.nb-row{grid-template-columns:30px 34px minmax(0,1fr) auto;row-gap:10px;padding:14px}
.nb-row .nb-meter{grid-column:2 / 4}
.nb-row .nb-edge{grid-column:4}
.nb-logo{width:32px;height:32px}
.nb-mk{grid-template-columns:1fr}
.nb-table th.hide,.nb-table td.hide{display:none}
}
"""


def style_tag() -> str:
    return f"<style>{CSS}</style>"


def _one_line(html: str) -> str:
    return "".join(part.strip() for part in html.splitlines())


def fmt_odds(o) -> str:
    return f"{int(o):+d}"


def pct(p, digits=0) -> str:
    return f"{100 * p:.{digits}f}%"


def logo(code, cls="nb-logo") -> str:
    if not code:
        return ""
    return f'<img class="{cls}" src="{logo_url(code)}" alt="{escape(nick(code))} logo" loading="lazy">'


def header(board: dict, title: str | None = None, sub: str = "") -> str:
    wk = f"Week {board['week']}" if board.get("week") else "No games yet"
    stamp = f'<div class="nb-stamp">Lines and projections updated {escape(board.get("built", ""))}</div>' if board.get("built") else ""
    return _one_line(f'''<div class="nb"><div class="nb-head"><div><div class="nb-week">{escape(title or wk)}</div>
<div class="nb-sub">{escape(sub)}</div></div>{stamp}</div></div>''')


def meter(b: dict) -> str:
    """Break-even sits on the orange line in the middle; the marker is the model's win chance."""
    gap = max(-WINDOW, min(WINDOW, b["p_win"] - b["breakeven"]))
    pos = 50 + 50 * gap / WINDOW
    left, width = (50, pos - 50) if gap >= 0 else (pos, 50 - pos)
    short = "" if gap >= 0 else " short"
    return _one_line(f'''<div class="nb-meter" role="img" aria-label="Model {pct(b['p_win'])}, needs {pct(b['breakeven'])} to break even">
<div class="track"><div class="gain{short}" style="left:{left:.1f}%;width:{width:.1f}%"></div><div class="need"></div>
<div class="ball" style="left:{pos:.1f}%"></div></div>
<div class="lbl"><span>Need {pct(b['breakeven'], 1)}</span><span>Model <b>{pct(b['p_win'], 1)}</b></span></div></div>''')


def bet_row(rank: int, b: dict, games_by_id: dict | None = None) -> str:
    clears = b["ev"] > 0
    if b.get("team"):
        art = logo(b["team"])
    else:
        g = (games_by_id or {}).get(b.get("game_id"))
        art = f'<div class="nb-logos">{logo(g["away"], "")}{logo(g["home"], "")}</div>' if g else ""
    where = " ".join(x for x in (b.get("matchup", ""), b.get("kickoff", "")) if x)
    edge = f"{100 * b['edge']:+.1f}"
    return _one_line(f'''<div class="nb-row {'clears' if clears else 'short'}"><div class="nb-rank">{rank}</div><div>{art}</div>
<div><div class="nb-pick">{escape(b['pick'])}</div><div class="nb-meta"><span class="nb-tag">{escape(b['market'])}</span>{escape(where)}</div></div>
<div class="nb-odds">{fmt_odds(b['odds'])}</div>{meter(b)}
<div class="nb-edge"><b>{edge}</b><span>{'edge' if clears else 'short'}</span></div></div>''')


def top_list(bets: list[dict], games: list[dict], start: int = 1) -> str:
    if not bets and start > 1:
        return ""
    if not bets:
        return '<div class="nb"><div class="nb-panel"><div class="nb-empty">No games with posted lines yet. Lines usually appear early in the week; reload then.</div></div></div>'
    by_id = {g["game_id"]: g for g in games}
    rows = "".join(bet_row(i, b, by_id) for i, b in enumerate(bets, start))
    return f'<div class="nb"><div class="nb-panel">{rows}</div></div>'


def note(html: str) -> str:
    return f'<div class="nb"><p class="nb-note">{html}</p></div>'


def section(title: str, lead: str = "") -> str:
    lead_html = f'<p class="nb-lead">{escape(lead)}</p>' if lead else ""
    return f'<div class="nb"><div class="nb-h2">{escape(title)}</div>{lead_html}</div>'


def _opt(b: dict, label: str, code=None, pick: bool = False) -> str:
    """One side of a market. `pick` = the side the model predicts to win the bet; the Value chip marks any
    side whose price pays more than the model's chance requires (on a moneyline that can be the underdog)."""
    value = b["ev"] > 0
    cls = "nb-opt" + (" pick" if pick else "") + (" value" if value else "")
    art = logo(code, "") if code else "<span></span>"
    chip = '<span class="nb-chip">Value</span>' if value else ""
    return (f'<div class="{cls}">{art}<div class="what">{escape(label)}'
            f'<span class="price">{fmt_odds(b["odds"])}</span></div>'
            f'<div class="right">{chip}<div class="chance">{pct(b["p_win"])}</div></div></div>')


def lines_key() -> str:
    return ('<div class="nb"><div class="nb-key"><span><i></i>Model\'s pick in each market</span>'
            '<span><span class="nb-chip">Value</span>The price pays more than the model\'s chance requires</span></div></div>')


def game_card(g: dict) -> str:
    cols = []
    for title, key, label in (("Moneyline", "moneyline", lambda b: nick(b["team"])), ("Spread", "spread", lambda b: b["pick"]),
                              ("Total points", "total", lambda b: b["pick"])):
        if not g[key]:
            continue
        best = model_pick(g[key])
        cols.append(f"<h4>{title}</h4>" + "".join(_opt(b, label(b), b.get("team"), b is best) for b in g[key]))
    m = g["model_margin"]
    lean = "a toss-up" if abs(m) < 0.25 else f"{g['home_name'] if m > 0 else g['away_name']} by {abs(m):.1f}"
    tot = f" and {g['model_total']:.1f} total points" if g["total"] else ""
    body = "".join(f'<div class="nb-mkcol">{c}</div>' for c in cols)
    return _one_line(f'''<div class="nb"><div class="nb-game"><div class="nb-ghead"><div class="nb-gname">{escape(g['away_name'])} at {escape(g['home_name'])}</div>
<div class="nb-gtime">{'<span class="nb-tag">Your lines</span>' if g.get('yours') else ''}{escape(g['kickoff'])}</div></div><div class="nb-mk">{body}</div>
<div class="nb-gfoot">Model sees {escape(lean)}{tot}.</div></div></div>''')


def _player_cell(r) -> str:
    return (f'<div class="nb-player">{logo(r.team, "")}<div><b>{escape(str(r.player_display_name))}</b>'
            f'<span>{escape(nick(r.team))} vs {escape(nick(r.opponent_team))}</span></div></div>')


def _verdict(bets: list[dict]) -> str:
    """Best side of a saved sportsbook line, in plain words. Empty when no line is saved for the player."""
    if not bets:
        return ""
    b = max(bets, key=lambda x: x["edge"])
    if " over " in b["pick"]:
        what = "Over " + b["pick"].split(" over ")[-1].split(" ")[0]
    elif " under " in b["pick"]:
        what = "Under " + b["pick"].split(" under ")[-1].split(" ")[0]
    else:
        what = "Yes"
    txt = f"{what} at {fmt_odds(b['odds'])}"
    if b["ev"] > 0:
        return f'<span class="yes">{escape(txt)}, {100 * b["edge"]:+.1f} edge</span>'
    return f'<span class="no">{escape(txt)}, no edge</span>'


def _book_col(bets: list[dict]):
    """(header cell, cell-builder) for the sportsbook column; the column disappears when nothing is saved."""
    by_player = {}
    for b in bets:
        by_player.setdefault(b["player"], []).append(b)
    if not by_player:
        return "", lambda name: ""
    return ('<th class="hide">Your sportsbook</th>',
            lambda name: f'<td class="nb-verdict hide">{_verdict(by_player.get(name, []))}</td>')


def yards_table(df: pd.DataFrame, bets: list[dict], unit: str = "yards") -> str:
    """Projection, likely range and fair line for a yardage prop. `bets`: priced saved lines for these players."""
    if df is None or not len(df):
        return '<div class="nb"><div class="nb-panel"><div class="nb-empty">No players to show for this week yet.</div></div></div>'
    lo, hi = max(0.0, float(df.q10.min())), float(df.q90.max())
    span = max(hi - lo, 1.0)
    pos = lambda v: 100 * (min(max(v, lo), hi) - lo) / span
    book_th, book_td = _book_col(bets)
    rows = []
    for r in df.itertuples(index=False):
        fair = round(r.q50 - 0.5) + 0.5
        rng = (f'<div class="nb-range" title="Middle half of outcomes: {r.q25:.0f} to {r.q75:.0f}">'
               f'<div class="w" style="left:{pos(r.q10):.1f}%;width:{pos(r.q90) - pos(r.q10):.1f}%"></div>'
               f'<div class="b" style="left:{pos(r.q25):.1f}%;width:{pos(r.q75) - pos(r.q25):.1f}%"></div>'
               f'<div class="m" style="left:{pos(r.q50):.1f}%"></div></div>')
        rows.append(f'<tr><td>{_player_cell(r)}</td><td class="num r">{r.pred:.0f}</td><td class="hide">{rng}</td>'
                    f'<td class="num r">{fair:.1f}</td>{book_td(r.player_display_name)}</tr>')
    axis = f'<div class="nb-axis"><span>{lo:.0f}</span><span>Likely range</span><span>{hi:.0f} {unit}</span></div>'
    head = (f'<tr><th>Player</th><th class="r">Projection</th><th class="hide">{axis}</th>'
            f'<th class="r">Fair line</th>{book_th}</tr>')
    return f'<div class="nb"><div class="nb-panel"><table class="nb-table"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div></div>'


def count_table(df: pd.DataFrame, bets: list[dict], noun: str) -> str:
    """Counting props (receptions, passing TDs): projection and the chance of clearing the nearest line."""
    if df is None or not len(df):
        return '<div class="nb"><div class="nb-panel"><div class="nb-empty">No players to show for this week yet.</div></div></div>'
    book_th, book_td = _book_col(bets)
    rows = []
    for r in df.itertuples(index=False):
        bar = f'<div class="nb-bar"><i style="width:{100 * r.p_over:.0f}%"></i></div>'
        rows.append(f'<tr><td>{_player_cell(r)}</td><td class="num r">{r.pred:.1f}</td><td class="num r">{r.line:g}</td>'
                    f'<td class="num r">{pct(r.p_over)}</td><td class="hide">{bar}</td>{book_td(r.player_display_name)}</tr>')
    head = (f'<tr><th>Player</th><th class="r">Projected {escape(noun)}</th><th class="r">Line</th>'
            f'<th class="r">Chance to go over</th><th class="hide"></th>{book_th}</tr>')
    return f'<div class="nb"><div class="nb-panel"><table class="nb-table"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div></div>'


def td_table(df: pd.DataFrame, bets: list[dict]) -> str:
    if df is None or not len(df):
        return '<div class="nb"><div class="nb-panel"><div class="nb-empty">No players to show for this week yet.</div></div></div>'
    book_th, book_td = _book_col(bets)
    rows = []
    for r in df.itertuples(index=False):
        bar = f'<div class="nb-bar"><i style="width:{100 * r.p_td:.0f}%"></i></div>'
        rows.append(f'<tr><td>{_player_cell(r)}</td><td class="num r">{pct(r.p_td)}</td><td class="hide">{bar}</td>'
                    f'<td class="num r">{fmt_odds(r.fair_odds)}</td>'
                    f'{book_td(r.player_display_name)}</tr>')
    head = ('<tr><th>Player</th><th class="r">Chance to score</th><th class="hide"></th>'
            f'<th class="r">Fair price</th>{book_th}</tr>')
    return f'<div class="nb"><div class="nb-panel"><table class="nb-table"><thead>{head}</thead><tbody>{"".join(rows)}</tbody></table></div></div>'


def simple_table(df: pd.DataFrame) -> str:
    """A plain table of already-formatted text. Rows whose first cell doesn't start with 'Week' are summary rows."""
    if df is None or not len(df):
        return '<div class="nb"><div class="nb-panel"><div class="nb-empty">No finished weeks to show yet.</div></div></div>'
    head = "".join(f'<th{"" if i == 0 else " class=c"}>{escape(str(c))}</th>' for i, c in enumerate(df.columns))
    rows = []
    for row in df.itertuples(index=False):
        cls = "" if str(row[0]).startswith("Week") else ' class="sum"'
        cells = "".join(f'<td class="{"plain" if i == 0 else "num c"}">{escape(str(v))}</td>' for i, v in enumerate(row))
        rows.append(f"<tr{cls}>{cells}</tr>")
    return f'<div class="nb"><div class="nb-panel"><table class="nb-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table></div></div>'


def teaser_facts(t: dict) -> str:
    """The record behind the teaser page, with what it means at the prices sportsbooks usually charge."""
    cell = lambda big, small: f'<div class="nb-fact"><b>{big}</b><span>{escape(small)}</span></div>'
    return ('<div class="nb"><div class="nb-facts">'
            + cell(pct(t["rate"], 1), f'of {t["legs"]} legs like these have won since {t["first"]}')
            + cell(fmt_odds(t["breakeven"]), "break-even price for a two-team teaser at that rate")
            + cell(f'{100 * t["roi"][-120]:+.0f}%', "past return per teaser at -120")
            + cell(f'{100 * t["roi"][-130]:+.0f}%', "past return per teaser at -130")
            + '</div></div>')


def teaser_list(legs: list[dict]) -> str:
    if not legs:
        return ('<div class="nb"><div class="nb-panel"><div class="nb-empty">No games qualify this week. '
                'A leg needs an underdog of +1.5 to +2.5 in a game with a total of 49 or less.</div></div></div>')
    rows = "".join(
        f'<div class="nb-leg"><div>{logo(l["team"])}</div><div><div class="nb-pick">{escape(l["pick"])}</div>'
        f'<div class="nb-meta">{escape(l["matchup"])} {escape(l["kickoff"])}</div></div>'
        f'<div class="was">teased from {escape(l["was"])}<br>total {l["total"]:g}</div></div>' for l in legs)
    return f'<div class="nb"><div class="nb-panel">{rows}</div></div>'


def loading(title: str = "Setting up this week's board", sub: str = "") -> str:
    """Centered heading for the loading screen; the progress bar and step text sit under it."""
    return f'<div class="nb"><div class="nb-load"><h1>{escape(title)}</h1><p>{escape(sub)}</p></div></div>'


def loading_step(text: str) -> str:
    return f'<div class="nb"><div class="nb-step">{escape(text)}</div></div>'


# ------------------------------------------------------------------ site chrome ----
BRAND = "DeepRoute AI"
TAGLINE = "NFL bets priced by a model, checked only on seasons it had never seen."


@lru_cache(maxsize=None)
def asset_uri(name: str) -> str:
    """An image from assets/ as a data URI, so it renders inside st.markdown and in the static preview alike."""
    path = ROOT / "assets" / name
    if not path.exists():
        return ""
    kind = {".webp": "webp", ".png": "png", ".jpg": "jpeg"}[path.suffix]
    return f"data:image/{kind};base64,{base64.b64encode(path.read_bytes()).decode()}"


def brand_bar() -> str:
    return _one_line(f'''<div class="nb"><div class="nb-brand"><div class="lock"><img class="mark" src="{asset_uri('logo_mark.webp')}" alt="">
<img class="word" src="{asset_uri('logo_word.webp')}" alt="{BRAND}"></div><div class="tag">{escape(TAGLINE)}</div></div></div>''')


def hero(kicker: str, title: str, accent: str, sub: str, stats: list[tuple[str, str]], stamp: str = "") -> str:
    """The landing band: headline (last word in cyan), one line of context and up to four key numbers."""
    tiles = "".join(f'<div class="nb-stat"><b>{escape(big)}</b><span>{escape(small)}</span></div>' for big, small in stats)
    st = f'<div class="stamp">{escape(stamp)}</div>' if stamp else ""
    return _one_line(f'''<div class="nb"><div class="nb-hero"><div class="kick">{escape(kicker)}</div>
<div class="h">{escape(title)} <span>{escape(accent)}</span></div><div class="s">{escape(sub)}</div>
<div class="nb-stats">{tiles}</div>{st}</div></div>''')


def _art(b: dict, games_by_id: dict) -> str:
    if b.get("team"):
        return logo(b["team"])
    g = games_by_id.get(b.get("game_id"))
    return f'<div class="nb-logos">{logo(g["away"], "")}{logo(g["home"], "")}</div>' if g else ""


def _where(b: dict) -> str:
    return escape(" ".join(x for x in (b.get("matchup", ""), b.get("kickoff", "")) if x))


def featured(bets: list[dict], games: list[dict]) -> str:
    """The best three as cards: the bet, its price, the meter and the edge."""
    if not bets:
        return top_list([], games)
    by_id = {g["game_id"]: g for g in games}
    cards = []
    for i, b in enumerate(bets, 1):
        clears = b["ev"] > 0
        cards.append(f'''<div class="nb-fcard{' clears' if clears else ''}"><div class="top"><span class="rk">NO. {i}</span>{_art(b, by_id)}</div>
<div><div class="pk">{escape(b['pick'])}</div><div class="nb-meta"><span class="nb-tag">{escape(b['market'])}</span>{_where(b)}</div></div>
{meter(b)}<div class="row"><span class="odds">{fmt_odds(b['odds'])}</span><span class="ed">{100 * b['edge']:+.1f} {'edge' if clears else 'short'}</span></div></div>''')
    return _one_line(f'<div class="nb"><div class="nb-feat">{"".join(cards)}</div></div>')


def explore(tiles: list[tuple[str, str]]) -> str:
    cells = "".join(f'<div class="nb-tile"><i></i><b>{escape(t)}</b><span>{escape(d)}</span></div>' for t, d in tiles)
    return f'<div class="nb"><div class="nb-explore">{cells}</div></div>'


def footer() -> str:
    return _one_line(f'''<div class="nb"><div class="nb-foot"><img src="{asset_uri('logo_word.webp')}" alt="{BRAND}">
<span>Model estimates, not guarantees. Bet only what you can afford to lose. Must be 21+. Problem gambling? Call 1-800-GAMBLER.</span></div></div>''')


# ------------------------------------------------------------------ parlays ----
def parlay_card(i: int, p: dict, games_by_id: dict) -> str:
    legs = "".join(f'<div class="nb-leg"><div>{_art(b, games_by_id)}</div><div><div class="nb-pick">{escape(b["pick"])}</div>'
                   f'<div class="nb-meta"><span class="nb-tag">{escape(b["market"])}</span>{_where(b)}</div></div>'
                   f'<div class="price"><b>{fmt_odds(b["odds"])}</b><span>model {pct(b["p_win"])}</span></div></div>'
                   for b in p["legs"])
    head = (f'<div class="nb-ph"><div class="t">Parlay {i}<small>{len(p["legs"])} legs</small></div><div class="nb-pn">'
            f'<div><b>{fmt_odds(p["odds"])}</b><span>pays</span></div>'
            f'<div><b>{pct(p["p_win"])}</b><span>model chance</span></div>'
            f'<div><b>{pct(p["breakeven"])}</b><span>needed</span></div>'
            f'<div><b>{100 * p["ev"]:+.0f}%</b><span>expected return</span></div></div></div>')
    return f'<div class="nb-parlay{" clears" if p["ev"] > 0 else ""}">{head}{legs}</div>'


def parlay_list(parlays: list[dict], games: list[dict], n_legs: int) -> str:
    if not parlays:
        return (f'<div class="nb"><div class="nb-panel"><div class="nb-empty">Not enough bets clear break-even in different '
                f"games to build a {n_legs}-leg parlay this week. Adding your sportsbook's lines can change that.</div></div></div>")
    by_id = {g["game_id"]: g for g in games}
    return '<div class="nb">' + "".join(parlay_card(i, p, by_id) for i, p in enumerate(parlays, 1)) + "</div>"


def parlay_facts(r: pd.DataFrame) -> str:
    """Long-run record from reports/parlays_backtest.csv: each parlay size against the same legs bet singly."""
    if r is None or r.empty:
        return ""
    row = {int(x.legs): x for x in r.itertuples(index=False)}
    cell = lambda big, small: f'<div class="nb-fact"><b>{big}</b><span>{escape(small)}</span></div>'
    span = f"{int(r['first'].iloc[0])}-{int(r['last'].iloc[0])}"
    out = [cell(f"{100 * row[n].roi:+.1f}%", f"return on {name} since {span.split('-')[0]} ({int(row[n].bets)} bets; "
                                             f"range {100 * row[n].lo:+.0f}% to {100 * row[n].hi:+.0f}%)")
           for n, name in ((1, "the same legs as single bets"), (2, "2-leg parlays"), (3, "3-leg parlays")) if n in row]
    if 2 in row:
        out.append(cell(pct(row[2].win_rate), f"of 2-leg parlays won; the model expected {pct(row[2].expected)}"))
    return '<div class="nb"><div class="nb-facts">' + "".join(out) + "</div></div>"
