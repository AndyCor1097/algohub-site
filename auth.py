"""
Free accounts for thealgohub.com (Supabase email login).

  auth_config.json   {"supabase_url": "...", "anon_key": "..."}  (both are public values, safe in git)
  If it's empty, the site stays fully open (no login), so nothing breaks before it's set up.

build_site.py uses this to:
  - write public/login.html  (teaser + "create free account" with email link login)
  - add a tiny script to every page that keeps the login fresh + a "Sign out" link
  - write middleware.js at the repo root: Vercel runs it before every page and sends anyone
    not signed in to /login. That's the real lock (not just hiding things in the browser).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CFG_FILE = ROOT / "auth_config.json"
SUPABASE_JS = "https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.45.4/dist/umd/supabase.min.js"
COOKIE = "ah_at"


def config():
    try:
        c = json.loads(CFG_FILE.read_text(encoding="utf-8"))
        if c.get("supabase_url") and c.get("anon_key"):
            return {"url": c["supabase_url"].rstrip("/"), "key": c["anon_key"]}
    except Exception:
        pass
    return None


def _client_js(c):
    return f"""<script src="{SUPABASE_JS}"></script>
<script>
window.AH = (function(){{
  const sb = supabase.createClient({json.dumps(c['url'])}, {json.dumps(c['key'])},
    {{auth: {{flowType: 'implicit', persistSession: true, autoRefreshToken: true, detectSessionInUrl: true}}}});
  function setCookie(s){{
    if (s && s.access_token) {{
      const age = Math.max(60, (s.expires_at || 0) - Math.floor(Date.now()/1000));
      document.cookie = '{COOKIE}=' + s.access_token + '; Path=/; Max-Age=' + age + '; SameSite=Lax; Secure';
    }} else {{
      document.cookie = '{COOKIE}=; Path=/; Max-Age=0; SameSite=Lax; Secure';
    }}
  }}
  sb.auth.onAuthStateChange((_e, s) => setCookie(s));
  sb.auth.getSession().then(r => setCookie(r.data.session));
  return {{sb, setCookie,
    async signOut(){{ await sb.auth.signOut(); setCookie(null); location.href = '/login'; }}}};
}})();
</script>"""


def page_js():
    """Goes on every member page: keeps the cookie fresh while they browse + adds a Sign out link."""
    c = config()
    if not c:
        return ""
    return _client_js(c) + """<script>
document.addEventListener('DOMContentLoaded',()=>{const f=document.querySelector('.ah-foot');
 if(f){const a=document.createElement('a');a.href='#';a.textContent='Sign out';a.style.cssText='color:var(--dim)';
  a.onclick=e=>{e.preventDefault();AH.signOut();};f.appendChild(a);}});
</script>"""


LOGIN_CSS = """<style>
.lg{max-width:460px;margin:26px auto 40px;background:var(--panel);border:1px solid var(--rule);border-radius:16px;padding:26px 24px}
.lg h2{font:800 34px/1.05 "Big Shoulders Display",sans-serif;margin:0 0 6px}
.lg p{color:var(--dim);margin:0 0 16px}
.lg ul{margin:0 0 18px;padding-left:18px;color:var(--chalk)} .lg li{margin:4px 0}
.lg input{width:100%;box-sizing:border-box;background:var(--ink);color:var(--chalk);border:1px solid var(--rule);border-radius:10px;
  padding:12px 14px;font:500 16px Archivo,sans-serif;margin-bottom:10px}
.lg button{width:100%;border:0;border-radius:10px;padding:12px 14px;font:700 16px Archivo,sans-serif;cursor:pointer;
  background:var(--amber);color:var(--ink)}
.lg button[disabled]{opacity:.6;cursor:default}
.lg .msg{margin-top:12px;font-size:14px;color:var(--chalk)} .lg .msg.err{color:#ffa198}
.lg small{display:block;margin-top:14px;color:var(--dim);font-size:12px}
</style>"""


def login_body():
    c = config()
    if not c:
        return '<p class="note">Accounts aren\'t set up yet.</p>'
    return LOGIN_CSS + """
<section class="lg" aria-labelledby="lg-h">
  <h2 id="lg-h">Get in free</h2>
  <p>Create a free account to see every algo: picks, cards, sharp bets and matchups across every sport.</p>
  <ul><li>Daily model picks for NFL, CFB, NHL and more</li><li>Sharp money tracker</li><li>Full public record, wins and losses</li></ul>
  <form id="lg-f">
    <label for="lg-e" class="hint">Email</label>
    <input id="lg-e" type="email" required autocomplete="email" placeholder="you@email.com">
    <button id="lg-b" type="submit">Email me a sign-in link</button>
  </form>
  <div id="lg-m" class="msg" role="status" aria-live="polite"></div>
  <small>No password. We email you a link, tap it and you're in. Same link signs you up or back in.</small>
</section>""" + _client_js(c) + """<script>
(async function(){
  const p = new URLSearchParams(location.search), next = p.get('next') || '/';
  const safeNext = next.startsWith('/') && !next.startsWith('//') ? next : '/';
  const m = document.getElementById('lg-m');
  // already signed in (or just tapped the email link): set the cookie and go
  const go = s => { AH.setCookie(s); location.replace(safeNext); };
  const r = await AH.sb.auth.getSession();
  if (r.data.session) return go(r.data.session);
  AH.sb.auth.onAuthStateChange((e, s) => { if (s) go(s); });
  document.getElementById('lg-f').onsubmit = async ev => {
    ev.preventDefault();
    const b = document.getElementById('lg-b'), email = document.getElementById('lg-e').value.trim();
    b.disabled = true; m.className = 'msg'; m.textContent = 'Sending...';
    const { error } = await AH.sb.auth.signInWithOtp({ email,
      options: { emailRedirectTo: location.origin + '/login?next=' + encodeURIComponent(safeNext) } });
    b.disabled = false;
    if (error) { m.className = 'msg err'; m.textContent = error.message; }
    else { m.textContent = 'Check your email (and spam) for the sign-in link. You can close this tab.'; }
  };
})();
</script>"""


def middleware_js():
    """Vercel Routing Middleware: runs before every page. Signed in = continue, otherwise -> /login."""
    c = config()
    if not c:
        return None
    return f"""// Generated by build_site.py (auth.py). Sends anyone not signed in to /login.
export const config = {{
  matcher: ['/((?!login|api/|sharp_markets\\\\.json|favicon|robots\\\\.txt|404).*)'],
}};

const SUPABASE_URL = {json.dumps(c['url'])};
const ANON_KEY = {json.dumps(c['key'])};
const ok = new Map();   // token -> time it was last checked (skip re-checking for 5 min)

function cookie(req, name) {{
  const m = (req.headers.get('cookie') || '').match(new RegExp('(?:^|; )' + name + '=([^;]+)'));
  return m ? m[1] : null;
}}

async function valid(token) {{
  if (!token) return false;
  const t = ok.get(token);
  if (t && Date.now() - t < 5 * 60 * 1000) return true;
  try {{
    const r = await fetch(SUPABASE_URL + '/auth/v1/user',
                          {{ headers: {{ apikey: ANON_KEY, Authorization: 'Bearer ' + token }} }});
    if (r.ok) {{ ok.set(token, Date.now()); if (ok.size > 5000) ok.clear(); return true; }}
  }} catch (e) {{}}
  return false;
}}

export default async function middleware(request) {{
  if (await valid(cookie(request, '{COOKIE}'))) return;          // signed in: show the page
  const url = new URL(request.url);
  const to = new URL('/login', url);
  to.searchParams.set('next', url.pathname + url.search);
  return Response.redirect(to, 307);
}}
"""


SQL = """-- Run once in Supabase: SQL Editor -> New query -> paste -> Run
create table if not exists public.profiles (
  id uuid primary key references auth.users(id) on delete cascade,
  email text,
  tier text not null default 'free',      -- free | pro | comp
  created_at timestamptz not null default now()
);
alter table public.profiles enable row level security;
create policy "read own profile" on public.profiles for select using (auth.uid() = id);

create or replace function public.handle_new_user() returns trigger
language plpgsql security definer set search_path = public as $$
begin
  insert into public.profiles (id, email) values (new.id, new.email) on conflict do nothing;
  return new;
end; $$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created after insert on auth.users
  for each row execute function public.handle_new_user();
"""
