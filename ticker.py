"""Live scoreboard ticker for the static site.
Runs in the visitor's browser: pulls ESPN's public scoreboards every 30s while games are live,
scrolls every game across the top, and tracks today's AlgoHub picks (covering / not, then W / L).
The board's bet slips get the same live status. No server, nothing to keep awake."""
import json

ESPN = {  # board sport key -> ESPN scoreboard path + extra params
    "NFL": ("football/nfl", ""),
    "CFB": ("football/college-football", "&groups=80"),
    "NHL": ("hockey/nhl", ""),
    "MLB": ("baseball/mlb", ""),
    "CBB": ("basketball/mens-college-basketball", "&groups=50&limit=400"),
    "NBA": ("basketball/nba", ""),
    "EPL": ("soccer/eng.1", ""),
}

CSS = """
<style>
.tk{position:sticky;top:0;z-index:20;margin:-22px -16px 14px;background:rgba(11,14,19,.92);
  backdrop-filter:blur(8px);-webkit-backdrop-filter:blur(8px);border-bottom:1px solid var(--rule);overflow:hidden}
.tk[hidden]{display:none}
.tk-row{display:flex;align-items:stretch}
.tk-live{flex:none;display:flex;align-items:center;gap:7px;padding:0 14px;font:800 15px "Big Shoulders Display",sans-serif;
  color:var(--ink);background:var(--amber);letter-spacing:.04em}
.tk-live i{width:7px;height:7px;border-radius:50%;background:var(--ink);animation:tkb 1.4s ease-in-out infinite}
@keyframes tkb{50%{opacity:.25}}
.tk-view{flex:1;overflow:hidden;mask-image:linear-gradient(90deg,transparent,#000 24px,#000 calc(100% - 24px),transparent)}
.tk-track{display:flex;width:max-content;animation:tks var(--dur,80s) linear infinite}
.tk:hover .tk-track,.tk:focus-within .tk-track{animation-play-state:paused}
@keyframes tks{to{transform:translateX(-50%)}}
.tk-g{display:flex;align-items:center;gap:10px;padding:8px 18px;border-right:1px solid var(--rule);white-space:nowrap;font-size:13px}
.tk-sp{font:700 11px Archivo,sans-serif;color:var(--dim)}
.tk-t{display:flex;gap:6px;align-items:baseline}
.tk-t b{font:800 17px "Big Shoulders Display",sans-serif;color:var(--chalk)}
.tk-t span{font:800 17px "Big Shoulders Display",sans-serif;color:var(--chalk);min-width:14px;text-align:right}
.tk-t.lose b,.tk-t.lose span{color:var(--dim)}
.tk-st{font-size:12px;color:var(--dim)}
.tk-st.in{color:var(--amber);font-weight:600}
.tk-p{font:700 11px Archivo,sans-serif;padding:3px 7px;border-radius:6px;border:1px solid var(--rule);color:var(--chalk)}
.tk-p.up{background:rgba(63,185,80,.15);border-color:rgba(63,185,80,.5);color:#7ee787}
.tk-p.down{background:rgba(248,81,73,.12);border-color:rgba(248,81,73,.45);color:#ffa198}
.tk-p.push{color:var(--dim)}
.ah-live{display:inline-block;margin-top:6px;font:700 11px Archivo,sans-serif;padding:3px 8px;border-radius:6px;
  border:1px solid var(--rule);color:var(--dim)}
.ah-live.up{background:rgba(63,185,80,.15);border-color:rgba(63,185,80,.5);color:#7ee787}
.ah-live.down{background:rgba(248,81,73,.12);border-color:rgba(248,81,73,.45);color:#ffa198}
@media (prefers-reduced-motion:reduce){.tk-track{animation:none}.tk-view{overflow-x:auto;mask-image:none}.tk-live i{animation:none}}
@media (max-width:640px){.tk-g{padding:7px 14px}.tk-live{padding:0 10px}}
</style>"""

HTML = """<div class="tk" id="tk" hidden aria-label="Live scores">
  <div class="tk-row"><div class="tk-live"><i></i>LIVE</div>
  <div class="tk-view"><div class="tk-track" id="tk-track"></div></div></div></div>"""


def js(picks, sports):
    cfg = {s: ESPN[s] for s in sports if s in ESPN}
    return """<script>
(function(){
const PICKS=%s, SP=%s;
const ALIAS={NHL:{TBL:'TB',NJD:'NJ',SJS:'SJ',LAK:'LA',UTA:'UTAH'},MLB:{CWS:'CHW',TBR:'TB',KCR:'KC',SDP:'SD',SFG:'SF',WSN:'WSH'},NFL:{LA:'LAR',WAS:'WSH'},EPL:{'Man United':'Manchester United','Man City':'Manchester City',"Nott'm Forest":'Nottingham Forest',Wolves:'Wolverhampton Wanderers'}};
const norm=s=>(s||'').toLowerCase().replace(/&/g,'and').replace(/\\bstate\\b/g,'st').replace(/\\bsaint\\b/g,'st').replace(/[^a-z0-9]/g,'');
const keys=t=>[t.abbreviation,t.displayName,t.shortDisplayName,t.location,t.nickname,(t.location||'')+' '+(t.name||'')].filter(Boolean).map(norm);
function hit(name,sport,comp){const k=norm((ALIAS[sport]||{})[name]||name); if(!k)return false;
  const ks=keys(comp.team); return ks.includes(k)||ks.some(x=>x.length>3&&k.length>3&&(x.startsWith(k)||k.startsWith(x)));}
function parse(p){const t=(p||'').trim();let m;
  if(m=t.match(/^(over|under)\\s+([\\d.]+)/i))return{k:'tot',side:m[1].toLowerCase(),line:+m[2]};
  if(m=t.match(/^(.*)\\s+ML$/i))return{k:'ml',team:m[1]};
  if(m=t.match(/^(.*)\\s+PK$/i))return{k:'sp',team:m[1],line:0};
  if(m=t.match(/^(.*)\\s+([+-][\\d.]+)$/))return{k:'sp',team:m[1],line:+m[2]};
  return null;}
function findEvent(pk,events){const [a,h]=(pk.game||'').split(' at ');
  return events.find(ev=>{const c=ev.competitions[0].competitors;return c.some(x=>hit(h,pk.sport,x))&&c.some(x=>hit(a,pk.sport,x));});}
function status(pk,ev){const pp=parse(pk.pick); if(!pp||!ev)return null;
  const st=ev.status.type.state; if(st==='pre')return{cls:'',txt:ev.status.type.shortDetail};
  const c=ev.competitions[0].competitors, sc=x=>+x.score||0; let v;
  if(pp.k==='tot'){const t=sc(c[0])+sc(c[1]); v=pp.side==='over'?t-pp.line:pp.line-t;}
  else{const me=c.find(x=>hit(pp.team,pk.sport,x)); if(!me)return null; const op=c.find(x=>x!==me);
    v=sc(me)-sc(op)+(pp.k==='sp'?pp.line:0);}
  const done=st==='post';
  if(v===0)return{cls:'push',txt:done?'Push':'Even'};
  return v>0?{cls:'up',txt:done?'Win':(pp.k==='ml'?'Winning':pp.k==='tot'?'On pace':'Covering')}
            :{cls:'down',txt:done?'Loss':(pp.k==='ml'?'Losing':pp.k==='tot'?'Off pace':'Not covering')};}
const esc=s=>String(s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
let timer;
async function load(){
  const day=new Date(); const ymd=day.getFullYear()+String(day.getMonth()+1).padStart(2,'0')+String(day.getDate()).padStart(2,'0');
  const all={}; let anyLive=false;
  await Promise.all(Object.entries(SP).map(async([s,[path,extra]])=>{
    try{const r=await fetch(`https://site.api.espn.com/apis/site/v2/sports/${path}/scoreboard?dates=${ymd}${extra}`);
      if(!r.ok)return; const j=await r.json(); all[s]=j.events||[];}catch(e){}
  }));
  const items=[], used=new Set();
  // picks first, with live status; then the rest of the board
  const byEv={};
  PICKS.forEach(pk=>{const ev=findEvent(pk,all[pk.sport]||[]); if(!ev)return;
    if(!byEv[ev.id]){byEv[ev.id]=[pk.sport,ev,[]]; items.push(byEv[ev.id]);} byEv[ev.id][2].push([pk,status(pk,ev)]); used.add(ev.id);});
  Object.entries(all).forEach(([s,evs])=>evs.filter(e=>!used.has(e.id)).sort((a,b)=>
    (a.status.type.state==='in'?0:a.status.type.state==='pre'?1:2)-(b.status.type.state==='in'?0:b.status.type.state==='pre'?1:2))
    .slice(0,s==='CBB'||s==='CFB'?25:40).forEach(ev=>items.push([s,ev,[]])));
  // board slips
  document.querySelectorAll('.ah-slip[data-pick]').forEach(el=>{
    const pk={sport:el.dataset.sport,pick:el.dataset.pick,game:el.dataset.game};
    const ev=findEvent(pk,all[pk.sport]||[]); const s=status(pk,ev); let b=el.querySelector('.ah-live');
    if(!s||!ev||ev.status.type.state==='pre'){if(b)b.remove();return;}
    if(!b){b=document.createElement('span');b.className='ah-live';el.appendChild(b);}
    const c=ev.competitions[0].competitors; const sc=c.map(x=>x.team.abbreviation+' '+(x.score||0)).join(' – ');
    b.className='ah-live '+s.cls; b.textContent=s.txt+' · '+sc+' · '+ev.status.type.shortDetail;});
  const html=items.map(([s,ev,pks])=>{const c=ev.competitions[0].competitors.slice().sort((x,y)=>x.homeAway==='away'?-1:1);
    const state=ev.status.type.state; if(state==='in')anyLive=true;
    const lead=state==='pre'?null:(+c[0].score>+c[1].score?0:+c[1].score>+c[0].score?1:null);
    const team=(x,i)=>`<span class="tk-t ${lead!==null&&lead!==i?'lose':''}"><b>${esc(x.team.abbreviation||x.team.shortDisplayName)}</b>${state==='pre'?'':`<span>${esc(x.score||0)}</span>`}</span>`;
    const p=pks.filter(([pk,st])=>st).map(([pk,st])=>`<span class="tk-p ${st.cls}">${esc(pk.pick)}${state==='pre'?'':' · '+esc(st.txt)}</span>`).join('');
    return `<div class="tk-g"><span class="tk-sp">${esc(s)}</span>${team(c[0],0)}${team(c[1],1)}<span class="tk-st ${state==='in'?'in':''}">${esc(ev.status.type.shortDetail)}</span>${p}</div>`;}).join('');
  const tk=document.getElementById('tk'), tr=document.getElementById('tk-track');
  if(!items.length){tk.hidden=true;}else{tk.hidden=false; tr.innerHTML=html+html;
    tr.style.setProperty('--dur',Math.max(30,items.length*6)+'s');
    document.querySelector('.tk-live').lastChild.textContent=anyLive?'LIVE':'TODAY';}
  clearTimeout(timer); timer=setTimeout(load,anyLive?30000:300000);
}
load();
document.addEventListener('visibilitychange',()=>{if(!document.hidden)load();});
})();
</script>""" % (json.dumps(picks), json.dumps(cfg))
