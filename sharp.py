"""Sharp money tape: a bar along the bottom of every page that scrolls big Novig trades.
The browser asks /api/sharp (api/sharp.js on Vercel) once a minute; that function checks Novig's public
trade feed for the markets listed in public/sharp_markets.json, which build_site writes from the Vs Novig data.
"""
import json

import pandas as pd

SPORT_FILES = [  # (sport label, data folder)
    ("NFL", "nfl_novig"), ("CFB", "cfb_novig"), ("NHL", "nhl_novig"), ("CBB", "cbb_novig"), ("NBA", "nba_novig"),
]


def _newest(folder):
    fs = sorted(folder.glob("*.csv"), key=lambda p: ("".join(c for c in p.stem if c.isdigit()).zfill(12)))
    return fs[-1] if fs else None


def markets_json(data_dir):
    """One entry per Novig market on the current slates, with a readable name for each side."""
    out = {}
    for sport, sub in SPORT_FILES:
        f = _newest(data_dir / sub) if (data_dir / sub).exists() else None
        if f is None:
            continue
        d = pd.read_csv(f)
        if "market_id" not in d.columns:
            continue
        for r in d.itertuples(index=False):
            m = out.setdefault(r.market_id, {"market_id": r.market_id, "sport": sport, "matchup": r.matchup,
                                              "market": r.market, "outcomes": {}})
            m["outcomes"][r.outcome_id] = r.side
    return json.dumps(list(out.values()))


CSS = """
<style>
.st{position:fixed;left:0;right:0;bottom:0;z-index:30;background:rgba(11,14,19,.94);backdrop-filter:blur(8px);
  -webkit-backdrop-filter:blur(8px);border-top:1px solid var(--rule);overflow:hidden}
.st[hidden]{display:none}
.st-row{display:flex;align-items:stretch}
.st-tag{flex:none;display:flex;align-items:center;gap:7px;padding:0 14px;font:800 15px "Big Shoulders Display",sans-serif;
  color:var(--ink);background:var(--turf);letter-spacing:.04em}
.st-view{flex:1;overflow:hidden;mask-image:linear-gradient(90deg,transparent,#000 24px,#000 calc(100% - 24px),transparent)}
.st-track{display:flex;width:max-content;animation:sts var(--dur,70s) linear infinite}
.st:hover .st-track,.st:focus-within .st-track{animation-play-state:paused}
@keyframes sts{to{transform:translateX(-50%)}}
.st-g{display:flex;align-items:center;gap:9px;padding:8px 18px;border-right:1px solid var(--rule);white-space:nowrap;font-size:13px}
.st-sp{font:700 11px Archivo,sans-serif;color:var(--dim)}
.st-amt{font:800 18px "Big Shoulders Display",sans-serif;color:#7ee787}
.st-amt.hot{color:var(--amber)}
.st-side{font-weight:700;color:var(--chalk)}
.st-mu,.st-ago{color:var(--dim);font-size:12px}
body{padding-bottom:46px}
@media (prefers-reduced-motion:reduce){.st-track{animation:none}.st-view{overflow-x:auto;mask-image:none}}
@media (max-width:640px){.st-g{padding:7px 14px}.st-tag{padding:0 10px}}
</style>"""

HTML = """<div class="st" id="st" hidden aria-label="Big bets on the Novig exchange">
  <div class="st-row"><div class="st-tag" title="Big trades on the Novig betting exchange">SHARP $</div>
  <div class="st-view"><div class="st-track" id="st-track"></div></div></div></div>"""

JS = """<script>
(function(){
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const ago=ms=>{const m=Math.round((Date.now()-ms)/60000);return m<1?'just now':m<60?m+'m ago':Math.round(m/60)+'h ago';};
const money=n=>'$'+n.toLocaleString('en-US');
let timer;
async function load(){
  try{
    const r=await fetch('/api/sharp',{cache:'no-store'}); if(!r.ok)throw 0;
    const j=await r.json(), t=j.trades||[], el=document.getElementById('st'), tr=document.getElementById('st-track');
    if(!t.length){el.hidden=true;}
    else{
      const html=t.map(x=>`<div class="st-g"><span class="st-sp">${esc(x.sport)}</span>`+
        `<span class="st-amt ${x.staked>=5000?'hot':''}">${x.staked>=5000?'&#128293; ':''}${money(x.staked)}</span>`+
        `<span class="st-side">${esc(x.side||x.market)}</span><span class="st-mu">@ ${Math.round(x.price*100)}&cent; &middot; ${esc(x.matchup)}</span>`+
        `<span class="st-ago">${ago(x.ts)}</span></div>`).join('');
      tr.innerHTML=html+html; tr.style.setProperty('--dur',Math.max(25,t.length*7)+'s'); el.hidden=false;}
  }catch(e){document.getElementById('st').hidden=true;}
  clearTimeout(timer); timer=setTimeout(load,60000);
}
load();
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
})();
</script>"""
