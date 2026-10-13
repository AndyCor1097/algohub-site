"""AlgoHub CBB cards - same dark, edge-first look as the other algos, built for 100+ game slates:
team search, plays-only by default on big nights, KenPom-style rank strip on every card.
render_cards(df, day) -> html str (df = a picks/cbb_YYYY-MM-DD.csv)."""
import html
import math

import pandas as pd

TIER_RANK = {"HAMMER": 3, "PLAY": 2, "LEAN": 1, "": 0}
e = lambda s: html.escape(str(s)) if s is not None and not (isinstance(s, float) and math.isnan(s)) else ""


def _na(v):
    return v is None or (isinstance(v, float) and math.isnan(v)) or v == ""


def _s(v):
    return "" if _na(v) else str(v)


def _o(v):
    return "-" if _na(v) else f"{int(float(v)):+d}"


def _abbr(r, side):
    a = _s(r.get(f"{side}_abbr"))
    if a:
        return a[:4]
    words = _s(r.get(f"{side}_name")).replace("State", "St").split()
    return ("".join(w[0] for w in words) if len(words) > 1 else _s(r.get(f"{side}_name"))[:3]).upper()[:4]


def _color(r, side):
    c = _s(r.get(f"{side}_color")).lstrip("#")
    return f"#{c}" if len(c) in (3, 6) else "#30363d"


def _fg(hexc):
    h = hexc.lstrip("#")
    if len(h) == 3:
        h = "".join(ch * 2 for ch in h)
    try:
        r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return "#fff"
    return "#0b0e13" if (0.299 * r + 0.587 * g + 0.114 * b) > 160 else "#fff"


def _rk(v):
    return "" if _na(v) else f"#{int(float(v))}"


def _team(r, side, fav):
    col = _color(r, side)
    proj = r[f"proj_{side}"]
    rank = _rk(r.get(f"{side}_rank"))
    return f"""
      <div class="team {'fav' if fav else ''}">
        <span class="badge" style="background:{col};color:{_fg(col)}">{e(_abbr(r, side))}</span>
        <div class="tname"><b>{f'<i class="rk">{e(rank)}</i>' if rank else ''}{e(r[f'{side}_name'])}</b><small>{e(_s(r.get(f'{side}_rec')))}</small></div>
        <div class="proj">{proj:.0f}</div>
      </div>"""


def _line_txt(r, pts_home, model=False):
    """'Duke -7.5' style from a home-perspective spread."""
    if _na(pts_home):
        return "-"
    pts_home = float(pts_home)
    if abs(pts_home) < (0.25 if model else 0.05):
        return "PK"
    fmt = (lambda v: f"{v:+.1f}") if model else (lambda v: f"{v:+g}")
    return f"{r['home_name']} {fmt(pts_home)}" if pts_home < 0 else f"{r['away_name']} {fmt(-pts_home)}"


def _market(label, book, model, edge, tier_, pick, extra=""):
    has = isinstance(tier_, str) and tier_
    et = "-" if _na(edge) else f"{abs(edge):.1f}"
    p = (f'<div class="pick t-{tier_.lower()}"><span class="tier">{e(tier_)}</span>{e(pick)}{extra}</div>'
         if has else '<div class="pick none">NO PLAY</div>')
    return f"""
      <div class="mkt"><div class="mlabel">{label}</div>
        <div class="cols"><div><small>BOOK</small><span>{e(book)}</span></div>
          <div><small>MODEL</small><span>{e(model)}</span></div>
          <div class="edge {'hot' if has else ''}"><small>EDGE</small><span>{et}</span></div></div>
        {p}</div>"""


def _strip(r):
    def row(side):
        return (f'<div class="srow"><b>{e(_abbr(r, side))}</b>'
                f'<span>OFF <i>{e(_rk(r.get(f"{side}_orank")))}</i></span>'
                f'<span>DEF <i>{e(_rk(r.get(f"{side}_drank")))}</i></span>'
                f'<span>TEMPO <i>{e(_rk(r.get(f"{side}_trank")))}</i></span></div>')
    return f'<div class="strip"><div class="mlabel">ADJUSTED RANKS</div>{row("away")}{row("home")}</div>'


def _card(r):
    sp_t, tot_t = _s(r.get("sp_tier")), _s(r.get("tot_tier"))
    best = max((sp_t, tot_t), key=lambda x: TIER_RANK.get(x, 0))
    ml = _s(r.get("ml_pick"))
    hw = float(r["home_wp"])
    ca, ch = _color(r, "away"), _color(r, "home")
    flags = [f for f in _s(r.get("flags")).split("|") if f]
    chips = "".join(f'<span class="chip{" out" if "MISSED" in f else ""}">{e(f)}</span>' for f in flags)
    ml_html = (f'<div class="ml">ML VALUE <b>{e(ml)} {_o(r.get("ml_odds"))}</b><span>+{float(r["ml_edge"]):.1%} vs no-vig</span></div>'
               if ml else "")
    search = f"{r['home_name']} {r['away_name']} {_s(r.get('home_abbr'))} {_s(r.get('away_abbr'))}".lower()
    sp_extra = f' <small>{float(r["sp_cover"]):.0%} to cover</small>' if sp_t and not _na(r.get("sp_cover")) else ""
    return f"""
    <article class="card b-{best.lower() or 'none'}" data-play="{1 if (best or ml) else 0}" data-s="{e(search)}">
      <header class="meta"><span>{e(r['start_et'])} ET</span><span>{e(_s(r.get('venue')))}</span></header>
      {_team(r, 'away', hw < .5)}{_team(r, 'home', hw >= .5)}
      <div class="wp"><div class="wplab"><span>{e(_abbr(r, 'away'))} {1 - hw:.0%}</span><span class="cap">WIN PROB</span><span>{e(_abbr(r, 'home'))} {hw:.0%}</span></div>
        <div class="wpbar"><i style="width:{(1 - hw) * 100:.1f}%;background:{ca}"></i><i style="width:{hw * 100:.1f}%;background:{ch}"></i></div></div>
      {_market("SPREAD", _line_txt(r, r.get("spread")), _line_txt(r, -float(r["pred_margin"]), model=True), r.get("sp_edge"), sp_t, _s(r.get("sp_pick")), sp_extra)}
      {_market("TOTAL", "-" if _na(r.get("total")) else f"{float(r['total']):g}", f"{float(r['pred_total']):.1f}", r.get("tot_edge"), tot_t, _s(r.get("tot_pick")))}
      {ml_html}
      {_strip(r)}
      {f'<div class="chips">{chips}</div>' if chips else ''}
    </article>"""


def render_cards(df, day):
    df = df.copy()
    tiers = list(df.sp_tier.fillna("")) + list(df.tot_tier.fillna(""))
    n_play = sum(1 for t in tiers if t)
    n_ham = sum(1 for t in tiers if t == "HAMMER")
    df["_r"] = [max(TIER_RANK.get(_s(a), 0), TIER_RANK.get(_s(b), 0)) for a, b in zip(df.sp_tier, df.tot_tier)]
    big = len(df) > 30 and n_play > 0
    d = pd.Timestamp(day)
    title = f"{d.strftime('%A, %B').upper()} {d.day}"
    cards = "".join(_card(r) for r in df.to_dict("records"))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>AlgoHub CBB {e(day)}</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0b0e13;--card:#12161d;--card2:#171c25;--line:#222a35;--tx:#e6edf3;--mu:#7d8590;--lean:#58a6ff;--play:#3fb950;--ham:#f2b134}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:14px/1.4 Inter,system-ui,sans-serif;padding:28px 16px 60px}}
.wrap{{max-width:1180px;margin:0 auto}}
.proj,.cols span,.top h1,.stats b,.wplab,.pick,.srow i{{font-family:"Barlow Condensed",sans-serif}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:18px}}
.top .k{{color:var(--mu);font-size:12px;letter-spacing:.18em;font-weight:600}}
.top h1{{font-size:44px;font-weight:800;line-height:1}}
.stats{{display:flex;gap:22px}} .stats div{{text-align:right}} .stats small{{display:block;color:var(--mu);font-size:11px;letter-spacing:.14em}}
.stats b{{font-size:30px}} .stats .h b{{color:var(--ham)}} .stats .p b{{color:var(--play)}}
.tools{{display:flex;gap:8px;margin:18px 0;flex-wrap:wrap;align-items:center}}
.tools button{{background:transparent;border:1px solid var(--line);color:var(--mu);padding:7px 14px;border-radius:999px;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.08em;cursor:pointer}}
.tools button.on{{background:var(--tx);color:var(--bg);border-color:var(--tx)}}
.tools input{{flex:1;min-width:180px;max-width:320px;background:var(--card);border:1px solid var(--line);color:var(--tx);border-radius:999px;padding:8px 14px;font:500 13px Inter,sans-serif}}
.tools input:focus,.tools button:focus-visible{{outline:2px solid var(--ham);outline-offset:2px}}
.count{{color:var(--mu);font-size:12px;margin-left:auto}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;align-items:start}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;border-top:3px solid var(--line)}}
.card.b-lean{{border-top-color:var(--lean)}} .card.b-play{{border-top-color:var(--play)}}
.card.b-hammer{{border-top-color:var(--ham);box-shadow:0 0 0 1px rgba(242,177,52,.25),0 8px 30px rgba(242,177,52,.08)}}
.meta{{display:flex;justify-content:space-between;gap:10px;padding:11px 16px;color:var(--mu);font-size:11px;letter-spacing:.06em;border-bottom:1px solid var(--line)}}
.meta span:last-child{{text-align:right;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.team{{display:flex;align-items:center;gap:12px;padding:10px 16px}}
.badge{{width:40px;height:40px;border-radius:10px;display:grid;place-items:center;font:800 12px "Barlow Condensed";flex:none}}
.tname{{flex:1;min-width:0}} .tname b{{display:block;font-size:16px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.tname small{{color:var(--mu);font-size:12px}} .rk{{font-style:normal;color:var(--mu);font-size:12px;font-weight:600;margin-right:6px}}
.proj{{font-size:32px;font-weight:700;color:var(--mu)}} .team.fav .proj{{color:var(--tx)}}
.wp{{padding:6px 16px 14px}} .wplab{{display:flex;justify-content:space-between;font-size:15px;font-weight:700;margin-bottom:6px}}
.wplab .cap{{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.16em;align-self:center}}
.wpbar{{display:flex;height:8px;border-radius:99px;overflow:hidden;gap:2px;background:var(--line)}} .wpbar i{{display:block;height:100%}}
.mkt{{border-top:1px solid var(--line);padding:12px 16px;background:var(--card2)}}
.mlabel{{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.18em;margin-bottom:8px}}
.cols{{display:grid;grid-template-columns:1.4fr 1.4fr .6fr;gap:8px}} .cols small{{display:block;color:var(--mu);font-size:10px;letter-spacing:.14em}}
.cols span{{font-size:17px;font-weight:700}} .edge span{{color:var(--mu)}} .edge.hot span{{color:var(--tx);font-size:24px}}
.pick{{margin-top:10px;display:flex;align-items:center;gap:10px;font-size:19px;font-weight:700;flex-wrap:wrap}}
.pick small{{color:var(--mu);font:600 12px Inter,sans-serif}}
.pick .tier{{font:800 11px Inter,system-ui,sans-serif;letter-spacing:.14em;padding:4px 8px;border-radius:6px;color:#0b0e13}}
.t-lean .tier{{background:var(--lean)}} .t-play .tier{{background:var(--play)}} .t-hammer .tier{{background:var(--ham)}}
.t-hammer{{color:var(--ham)}} .pick.none{{color:#4b535d;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.16em}}
.ml{{border-top:1px solid var(--line);padding:10px 16px;font-size:12px;color:var(--mu);display:flex;gap:10px;align-items:baseline;flex-wrap:wrap}}
.ml b{{color:var(--play);font-size:14px}}
.strip{{border-top:1px solid var(--line);padding:12px 16px}}
.srow{{display:flex;gap:16px;font-size:11px;color:var(--mu);letter-spacing:.06em;padding:3px 0;align-items:baseline}}
.srow b{{color:var(--tx);width:40px;font-size:12px}} .srow i{{font-style:normal;color:var(--tx);font-size:15px;font-weight:700}}
.chips{{display:flex;flex-wrap:wrap;gap:6px;padding:0 16px 14px}}
.chip{{font:600 10px Inter,system-ui,sans-serif;letter-spacing:.1em;color:#c9d1d9;border:1px solid var(--line);background:#0f1319;padding:4px 8px;border-radius:6px}}
.chip.out{{color:#ffb4ab;border-color:#5a2a27;background:#1d1212}}
.foot{{color:var(--mu);font-size:11px;margin-top:30px}}
.hide{{display:none}}
</style></head><body><div class="wrap">
  <div class="top"><div><div class="k">THE ALGOHUB · CBB GAME ALGO</div><h1>{e(title)}</h1></div>
    <div class="stats"><div><small>GAMES</small><b>{len(df)}</b></div><div class="p"><small>PLAYS</small><b>{n_play}</b></div>
      <div class="h"><small>HAMMERS</small><b>{n_ham}</b></div></div></div>
  <div class="tools">
    <button data-f="plays" class="{'on' if big else ''}">PLAYS ONLY</button><button data-f="all" class="{'' if big else 'on'}">ALL GAMES</button>
    <input type="search" placeholder="Find a team" aria-label="Find a team">
    <span class="count"></span>
  </div>
  <div class="grid">{cards}</div>
  <p class="foot">Opponent-adjusted offense, defense and tempo, rebuilt every morning from every game played. Edges are points vs the book. LEAN / PLAY / HAMMER. Not betting advice.</p>
</div>
<script>
let mode='{'plays' if big else 'all'}', q='';
const cards=[...document.querySelectorAll('.card')], cnt=document.querySelector('.count');
function apply(){{let n=0;cards.forEach(c=>{{const show=(q?c.dataset.s.includes(q):(mode==='all'||c.dataset.play==='1'));
  c.classList.toggle('hide',!show); if(show)n++;}}); cnt.textContent=n+' of '+cards.length+' games';}}
document.querySelectorAll('.tools button').forEach(b=>b.onclick=()=>{{mode=b.dataset.f;
  document.querySelectorAll('.tools button').forEach(x=>x.classList.toggle('on',x===b));apply();}});
document.querySelector('.tools input').oninput=ev=>{{q=ev.target.value.trim().toLowerCase();apply();}};
apply();
</script></body></html>"""
