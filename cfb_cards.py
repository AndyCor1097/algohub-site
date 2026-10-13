"""TheCFBAlgo cards - dark, edge-first layout matching NFL algo style.
render_cards(games, week, generated) -> html str."""
import html as html_mod
import math
from datetime import datetime

TIER_RANK = {"STRONG": 3, "EDGE": 2, "LEAN": 1, "": 0}

e = lambda s: html_mod.escape(str(s)) if s is not None and not (isinstance(s, float) and math.isnan(s)) else ""


def _s(v):
    return "" if v is None or (isinstance(v, float) and math.isnan(v)) else str(v)


def _parse_date(date_str):
    """Parse start_date string into datetime."""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str.split(" ")[0], "%m/%d/%Y")
    except Exception:
        return None


def _kick(g):
    from datetime import timezone, timedelta

    day_short = "TBD"
    day_long = "TBD"
    kickoff = ""

    ct = g.get("commence_time", "")
    if ct:
        try:
            dt_utc = datetime.fromisoformat(ct.replace("Z", "+00:00"))
            dt_et = dt_utc - timedelta(hours=4)
            day_short = dt_et.strftime("%a").upper()
            day_long = f"{dt_et.strftime('%A, %B').upper()} {dt_et.day}"
            kickoff = dt_et.strftime("%I:%M %p").lstrip("0") + " ET"
        except Exception:
            pass
    else:
        # fallback: try start_date field
        d = _parse_date(g.get("start_date", ""))
        if d:
            day_short = d.strftime("%a").upper()
            day_long = f"{d.strftime('%A, %B').upper()} {d.day}"

    return day_short, day_long, kickoff


def _spread_tier(edge):
    """Map spread edge value to tier label."""
    if edge is None:
        return ""
    ae = abs(edge)
    if ae >= 7:
        return "STRONG"
    elif ae >= 4:
        return "EDGE"
    elif ae >= 2:
        return "LEAN"
    return ""


def _total_tier(edge):
    """Map total edge value to tier label."""
    if edge is None:
        return ""
    ae = abs(edge)
    if ae >= 5:
        return "STRONG"
    elif ae >= 3:
        return "EDGE"
    elif ae >= 1.5:
        return "LEAN"
    return ""


def _wp(g):
    away = g.get("away_team", "")
    home = g.get("home_team", "")
    hw = float(g.get("home_win_prob", 50)) / 100.0
    aw = 1.0 - hw
    return f"""
      <div class="wp">
        <div class="wplab"><span>{e(away)} {aw:.0%}</span><span class="cap">WIN PROB</span><span>{e(home)} {hw:.0%}</span></div>
        <div class="wpbar"><i style="width:{aw*100:.1f}%;background:#58a6ff"></i><i style="width:{hw*100:.1f}%;background:#3fb950"></i></div>
      </div>"""


def _market(label, vegas, model, edge, tier_, pick):
    has = isinstance(tier_, str) and tier_
    edge_txt = "-" if edge is None else f"{edge:.1f}"
    pick_html = (f'<div class="pick t-{tier_.lower()}"><span class="tier">{e(tier_)}</span>{e(pick)}</div>'
                 if has else '<div class="pick none">NO PLAY</div>')
    return f"""
      <div class="mkt">
        <div class="mlabel">{label}</div>
        <div class="cols">
          <div><small>BOOK</small><span>{e(vegas)}</span></div>
          <div><small>MODEL</small><span>{e(model)}</span></div>
          <div class="edge {'hot' if has else ''}"><small>EDGE</small><span>{edge_txt}</span></div>
        </div>
        {pick_html}
      </div>"""


def _card(g):
    home = g.get("home_team", "")
    away = g.get("away_team", "")
    pred_home = g.get("pred_home", "?")
    pred_away = g.get("pred_away", "?")
    hw_prob = float(g.get("home_win_prob", 50))
    pred_margin = g.get("pred_margin")
    pred_total = g.get("pred_total")
    book_spread = g.get("book_spread")
    book_total = g.get("book_total")
    spread_edge = g.get("spread_edge")
    total_edge = g.get("total_edge")
    home_elo = g.get("home_elo", "")
    away_elo = g.get("away_elo", "")
    neutral = g.get("neutral_site", False)

    # Tiers
    sp_tier = _spread_tier(spread_edge)
    tot_tier = _total_tier(total_edge)
    best_tier = max((sp_tier, tot_tier), key=lambda x: TIER_RANK.get(x, 0))

    dkey, dlong, kickoff = _kick(g)
    win_side = "home" if (pred_margin or 0) > 0 else "away"

    # Spread display
    sp_str = f"{book_spread:+.1f}" if book_spread is not None else "-"
    ms_str = f"{pred_margin:+.1f}" if pred_margin is not None else "-"
    sp_pick = ""
    if sp_tier and spread_edge is not None:
        sp_pick = f"{'HOME' if spread_edge > 0 else 'AWAY'} {abs(spread_edge):.1f}"

    # Total display
    ou_str = f"{book_total:.1f}" if book_total is not None else "-"
    pt_str = f"{pred_total:.1f}" if pred_total is not None else "-"
    tot_pick = ""
    if tot_tier and total_edge is not None:
        tot_pick = f"{'OVER' if total_edge > 0 else 'UNDER'} {abs(total_edge):.1f}"

    venue_note = " · NEUTRAL" if neutral else ""

    return f"""
    <article class="card b-{best_tier.lower() or 'none'}" data-day="{dkey}" data-play="{1 if best_tier else 0}" data-rank="{TIER_RANK.get(best_tier,0)}">
      <header class="meta"><span>{dkey} · Wk{g.get('week','?')}{(' · ' + kickoff) if kickoff else ''}</span><span>{e(home)} vs {e(away)}{venue_note}</span></header>
      <div class="teams">
        <div class="team {'fav' if win_side=='away' else ''}">
          <div class="tname"><b>{e(away)}</b><small>ELO {away_elo}</small></div>
          <div class="proj">{pred_away}</div>
        </div>
        <div class="at">@</div>
        <div class="team {'fav' if win_side=='home' else ''}">
          <div class="tname"><b>{e(home)}</b><small>ELO {home_elo}</small></div>
          <div class="proj">{pred_home}</div>
        </div>
      </div>
      {_wp(g)}
      {_market("SPREAD", sp_str, ms_str, spread_edge, sp_tier, sp_pick)}
      {_market("TOTAL", ou_str, pt_str, total_edge, tot_tier, tot_pick)}
    </article>"""


def render_cards(games, week, generated=""):
    # Group by day
    from collections import defaultdict
    day_order = []
    by_day = defaultdict(list)
    for g in games:
        dk, _, _kt = _kick(g)
        if dk not in by_day:
            day_order.append(dk)
        by_day[dk].append(g)

    sections = []
    for dk in day_order:
        gs = by_day[dk]
        _, dlong, _kt = _kick(gs[0])
        cards_html = "".join(_card(g) for g in gs)
        sections.append(f"""
  <section class="day" data-day="{dk}">
    <div class="dayhead"><h2>{e(dlong)}</h2><span>{len(gs)} GAME{'S' if len(gs)!=1 else ''}</span></div>
    <div class="grid">{cards_html}</div>
  </section>""")

    # Stats
    all_tiers = [_spread_tier(g.get("spread_edge")) for g in games] + [_total_tier(g.get("total_edge")) for g in games]
    n_play = sum(1 for t in all_tiers if t)
    n_strong = sum(1 for t in all_tiers if t == "STRONG")
    uniq_days = list(dict.fromkeys(day_order))
    tabs = "".join(f'<button data-f="{d}">{d}</button>' for d in uniq_days)
    gen_str = generated[:10] if generated else ""

    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>TheCFBAlgo Week {week}</title>
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;700;800&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
<style>
:root{{--bg:#0b0e13;--card:#12161d;--card2:#171c25;--line:#222a35;--tx:#e6edf3;--mu:#7d8590;
--lean:#58a6ff;--edge:#3fb950;--strong:#f2b134;--neg:#f85149}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:var(--bg);color:var(--tx);font:14px/1.4 Inter,system-ui,sans-serif;padding:28px 16px 60px}}
.wrap{{max-width:1180px;margin:0 auto}}
.proj,.cols span,.top h1,.wplab,.pick{{font-family:"Barlow Condensed",sans-serif}}
.top{{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;flex-wrap:wrap;border-bottom:1px solid var(--line);padding-bottom:18px}}
.top .k{{color:var(--mu);font-size:12px;letter-spacing:.18em;font-weight:600}}
.top h1{{font-size:44px;font-weight:800;letter-spacing:.02em;line-height:1}}
.stats{{display:flex;gap:22px}} .stats div{{text-align:right}} .stats small{{display:block;color:var(--mu);font-size:11px;letter-spacing:.14em}}
.stats b{{font-size:30px}} .stats .s b{{color:var(--strong)}} .stats .p b{{color:var(--edge)}}
.tabs{{display:flex;gap:6px;margin:18px 0 6px;flex-wrap:wrap}}
.tabs button{{background:transparent;border:1px solid var(--line);color:var(--mu);padding:7px 14px;border-radius:999px;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.08em;cursor:pointer}}
.tabs button.on{{background:var(--tx);color:var(--bg);border-color:var(--tx)}}
.dayhead{{display:flex;justify-content:space-between;align-items:baseline;margin:26px 0 12px}}
.dayhead h2{{font:700 13px Inter,system-ui,sans-serif;letter-spacing:.16em}} .dayhead span{{color:var(--mu);font-size:11px;letter-spacing:.14em}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:14px;align-items:start}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:14px;overflow:hidden;border-top:3px solid var(--line)}}
.card.b-lean{{border-top-color:var(--lean)}} .card.b-edge{{border-top-color:var(--edge)}}
.card.b-strong{{border-top-color:var(--strong);box-shadow:0 0 0 1px rgba(242,177,52,.25),0 8px 30px rgba(242,177,52,.08)}}
.meta{{display:flex;justify-content:space-between;gap:10px;padding:11px 16px;color:var(--mu);font-size:11px;letter-spacing:.08em;border-bottom:1px solid var(--line)}}
.teams{{display:flex;align-items:center;gap:8px;padding:12px 16px}}
.team{{flex:1;min-width:0}} .team.fav .tname b{{color:var(--tx)}} .team.fav .proj{{color:var(--tx)}}
.tname b{{display:block;font-size:15px;font-weight:600;color:var(--mu)}} .tname small{{color:var(--mu);font-size:11px;opacity:.7}}
.proj{{font-size:36px;font-weight:700;color:var(--mu);font-family:"Barlow Condensed",sans-serif;line-height:1}}
.at{{color:var(--mu);font-size:12px;letter-spacing:.1em;font-weight:600;flex:none;padding:0 4px}}
.wp{{padding:6px 16px 14px}} .wplab{{display:flex;justify-content:space-between;font-size:15px;font-weight:700;margin-bottom:6px}}
.wplab .cap{{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.16em;align-self:center}}
.wpbar{{display:flex;height:8px;border-radius:99px;overflow:hidden;gap:2px;background:var(--line)}} .wpbar i{{display:block;height:100%}}
.mkt{{border-top:1px solid var(--line);padding:12px 16px;background:var(--card2)}}
.mlabel{{color:var(--mu);font:600 10px Inter,system-ui,sans-serif;letter-spacing:.18em;margin-bottom:8px}}
.cols{{display:grid;grid-template-columns:1fr 1fr 1fr;gap:8px}} .cols small{{display:block;color:var(--mu);font-size:10px;letter-spacing:.14em}}
.cols span{{font-size:20px;font-weight:700}} .edge span{{color:var(--mu)}} .edge.hot span{{color:var(--tx);font-size:26px}}
.pick{{margin-top:10px;display:flex;align-items:center;gap:10px;font-size:20px;font-weight:700;letter-spacing:.02em}}
.pick .tier{{font:800 11px Inter,system-ui,sans-serif;letter-spacing:.14em;padding:4px 8px;border-radius:6px;color:#0b0e13}}
.t-lean .tier{{background:var(--lean)}} .t-edge .tier{{background:var(--edge)}} .t-strong .tier{{background:var(--strong)}}
.t-strong{{color:var(--strong)}} .pick.none{{color:#4b535d;font:600 12px Inter,system-ui,sans-serif;letter-spacing:.16em}}
.foot{{color:var(--mu);font-size:11px;margin-top:30px;letter-spacing:.06em}}
.hide{{display:none}}
</style></head><body><div class="wrap">
  <div class="top">
    <div><div class="k">THE ALGOHUB · CFB GAME ALGO · 2026</div><h1>WEEK {week}</h1></div>
    <div class="stats">
      <div><small>GAMES</small><b>{len(games)}</b></div>
      <div class="p"><small>PLAYS</small><b>{n_play}</b></div>
      <div class="s"><small>STRONG</small><b>{n_strong}</b></div>
      <div><small>UPDATED</small><b style="font-size:18px">{gen_str}</b></div>
    </div>
  </div>
  <div class="tabs"><button class="on" data-f="all">ALL</button><button data-f="plays">PLAYS ONLY</button>{tabs}</div>
  {''.join(sections)}
  <p class="foot">Model trained on opponent-adjusted EPA, success rate, and Elo ratings. Edges in points vs. market. LEAN / EDGE / STRONG tiers. Not betting advice.</p>
</div>
<script>
document.querySelectorAll('.tabs button').forEach(b=>b.onclick=()=>{{
  document.querySelectorAll('.tabs button').forEach(x=>x.classList.toggle('on',x===b));
  const f=b.dataset.f;
  document.querySelectorAll('.card').forEach(c=>c.classList.toggle('hide',
    f==='plays'?c.dataset.play!=='1':(f!=='all'&&c.dataset.day!==f)));
  document.querySelectorAll('.day').forEach(s=>s.classList.toggle('hide',
    !s.querySelector('.card:not(.hide)')));
}});
</script></body></html>"""
