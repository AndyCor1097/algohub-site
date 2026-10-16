// Vercel serverless function: GET /api/sharp
// Reads the market list the site build saved (/sharp_markets.json), asks Novig's public trades feed
// for recent fills on each one, and returns the big ones. Cached 60s at Vercel's edge, so Novig is
// called at most about once a minute no matter how many people have the site open.

const NOVIG = "https://api.novig.com";
const BIG = 1000;                 // a fill counts as "big" at this many dollars staked or more
const WINDOW_MS = 12 * 3600e3;    // only trades from the last 12 hours
const MAX_ITEMS = 40;

async function trades(marketId) {
  try {
    const r = await fetch(`${NOVIG}/v3/public/catalog/markets/${marketId}/trades?limit=100`,
                          { headers: { Accept: "application/json" } });
    if (!r.ok) return [];
    const j = await r.json();
    return j.items || [];
  } catch (e) { return []; }
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
    const mr = await fetch(`https://${host}/sharp_markets.json`);
    const markets = mr.ok ? await mr.json() : [];
    const now = Date.now();
    const lists = await pool(markets, 16, m => trades(m.market_id));
    const big = [];
    markets.forEach((m, i) => {
      (lists[i] || []).forEach(t => {
        const price = parseFloat(t.price), qty = Number(t.qty);
        const staked = qty * price;            // each contract pays $1, so this side put up qty x price
        const ts = Number(t.ts);
        if (staked >= BIG && now - ts <= WINDOW_MS) {
          big.push({ sport: m.sport, matchup: m.matchup, market: m.market,
                     side: (m.outcomes || {})[t.outcomeId] || "", price, staked: Math.round(staked),
                     payout: qty, ts });
        }
      });
    });
    big.sort((a, b) => b.ts - a.ts);
    res.setHeader("Cache-Control", "s-maxage=60, stale-while-revalidate=120");
    res.setHeader("Content-Type", "application/json");
    res.status(200).send(JSON.stringify({ asOf: now, trades: big.slice(0, MAX_ITEMS) }));
  } catch (e) {
    res.status(200).json({ asOf: Date.now(), trades: [], error: String(e) });
  }
};
