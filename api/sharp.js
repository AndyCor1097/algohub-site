// Vercel serverless function: GET /api/sharp?part=0
// Reads the market list the site build saved (/sharp_markets.json), asks Novig's public trades feed
// for recent fills, and returns the big ones. Novig rate-limits its public API, so the market list is
// split into parts of ~PART_SIZE markets: the browser asks for each part a second apart and merges them.
// Each part is cached 60s at Vercel's edge, so Novig gets the same load no matter how many people visit.

const NOVIG = "https://api.novig.com";
const BIG = 1000;                 // a fill counts as "big" at this many dollars staked or more...
const BIG_BY_SPORT = { NHL: 500, MLB: 500, NBA: 750, CBB: 500, EPL: 500 };   // ...smaller markets, smaller bar
const WINDOW_MS = 12 * 3600e3;    // only trades from the last 12 hours
const PART_SIZE = 40;
const CONCURRENCY = 6;
const sleep = ms => new Promise(r => setTimeout(r, ms));

async function trades(marketId) {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      const ctl = new AbortController();
      const kill = setTimeout(() => ctl.abort(), 6000);
      const r = await fetch(`${NOVIG}/v3/public/catalog/markets/${marketId}/trades?limit=100`,
                            { headers: { Accept: "application/json" }, signal: ctl.signal });
      clearTimeout(kill);
      if (r.status === 429) {                     // too fast: wait what Novig asks (max 2s) and retry
        await sleep(Math.min(2000, 1000 * (parseFloat(r.headers.get("retry-after")) || 1)));
        continue;
      }
      if (!r.ok) return { items: [], err: r.status };
      const j = await r.json();
      return { items: j.items || [] };
    } catch (e) { return { items: [], err: "timeout" }; }
  }
  return { items: [], err: 429 };
}

async function pool(items, n, fn) {
  const out = []; let i = 0;
  await Promise.all(Array.from({ length: n }, async () => {
    while (i < items.length) { const k = i++; out[k] = await fn(items[k]); }
  }));
  return out;
}

module.exports = async (req, res) => {
  try {
    const host = req.headers["x-forwarded-host"] || req.headers.host;
    const url = new URL(req.url, `https://${host}`);
    const mr = await fetch(`https://${host}/sharp_markets.json`);
    const all = mr.ok ? await mr.json() : [];
    const parts = Math.max(1, Math.ceil(all.length / PART_SIZE));
    const part = Math.min(parts - 1, Math.max(0, parseInt(url.searchParams.get("part") || "0", 10) || 0));
    const markets = all.filter((_, i) => i % parts === part);        // interleaved, so every part mixes sports
    const now = Date.now();
    const lists = await pool(markets, CONCURRENCY, m => trades(m.market_id));
    const checked = {}, fills = {}, biggest = {}, errors = {}, big = [];
    markets.forEach((m, i) => {
      const L = lists[i] || { items: [] };
      checked[m.sport] = (checked[m.sport] || 0) + 1;
      if (L.err) errors[m.sport] = (errors[m.sport] || 0) + 1;
      L.items.forEach(t => {
        const ts = Number(t.ts);
        if (now - ts > WINDOW_MS) return;
        const price = parseFloat(t.price), qty = Number(t.qty);
        const staked = qty * price;            // each contract pays $1, so this side put up qty x price
        fills[m.sport] = (fills[m.sport] || 0) + 1;
        if (staked > (biggest[m.sport] || 0)) biggest[m.sport] = Math.round(staked);
        if (staked >= (BIG_BY_SPORT[m.sport] || BIG)) {
          big.push({ sport: m.sport, matchup: m.matchup, market: m.market,
                     side: (m.outcomes || {})[t.outcomeId] || "", price, staked: Math.round(staked),
                     payout: qty, ts });
        }
      });
    });
    big.sort((a, b) => b.ts - a.ts);
    res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=120");
    res.setHeader("Content-Type", "application/json");
    res.status(200).send(JSON.stringify({ asOf: now, part, parts, checked, errors, fills_12h: fills,
                                          biggest_12h: biggest, trades: big.slice(0, 60) }));
  } catch (e) {
    res.status(200).json({ asOf: Date.now(), part: 0, parts: 1, trades: [], error: String(e) });
  }
};
