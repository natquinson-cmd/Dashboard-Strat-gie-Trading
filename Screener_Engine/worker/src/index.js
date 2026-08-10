// index.js — Worker Cloudflare : orchestre le screener growth, filtre Revolut, stocke le classement en KV.
// Endpoints :
//   GET /latest              -> dernier classement (JSON, CORS ouvert)
//   GET /health              -> etat + compteurs
//   GET /whitelist           -> taille de la whitelist Revolut
//   GET /run?key=ADMIN&n=40  -> execution manuelle (protegee) pour tester, ne persiste pas si dry=1
//   POST /whitelist?key=ADMIN (body: un ticker par ligne, ou CSV col "ticker") -> met a jour la whitelist
// Cron (scheduled) : pipeline complet, refresh momentum + rolling fondamentaux, ecrit /latest.

import { DEFAULT_CONFIG, rankUniverse } from './screen.js';
import { fetchUniverse, fetchQuotes, fetchFundamentals, fetchPriceChange } from './providers.js';

const CORS = { 'access-control-allow-origin': '*', 'access-control-allow-methods': 'GET,POST,OPTIONS', 'access-control-allow-headers': 'content-type' };
const json = (obj, status = 200) => new Response(JSON.stringify(obj), { status, headers: { 'content-type': 'application/json; charset=utf-8', ...CORS } });

// Parametres runtime (surchargent DEFAULT_CONFIG cote screener + reglages pipeline)
function runtimeCfg(env) {
  return {
    ...DEFAULT_CONFIG,
    minMarketCap: Number(env.MIN_MARKET_CAP || DEFAULT_CONFIG.guards.minMarketCap),
    minVolume: Number(env.MIN_VOLUME || 100000),
    maxUniverse: Number(env.MAX_UNIVERSE || 3000),
    fundChunk: Number(env.FUND_CHUNK || 60),   // fondamentaux rafraichis par run (rolling)
    quoteChunk: Number(env.QUOTE_CHUNK || 50)
  };
}

export default {
  async fetch(req, env, ctx) {
    const url = new URL(req.url);
    if (req.method === 'OPTIONS') return new Response(null, { headers: CORS });

    if (url.pathname === '/latest') {
      const v = await env.SCREENER.get('latest');
      return v ? new Response(v, { headers: { 'content-type': 'application/json; charset=utf-8', ...CORS } })
               : json({ error: 'pas encore de classement, lancez /run ou attendez le cron' }, 404);
    }
    if (url.pathname === '/health') {
      const meta = await env.SCREENER.get('meta', 'json');
      const wl = await env.SCREENER.get('whitelist', 'json');
      return json({ ok: true, lastRun: meta?.lastRun || null, counts: meta?.counts || null, whitelistSize: wl?.length || 0 });
    }
    if (url.pathname === '/whitelist') {
      if (req.method === 'POST') {
        if (url.searchParams.get('key') !== env.ADMIN_KEY) return json({ error: 'non autorise' }, 401);
        const text = await req.text();
        const list = parseWhitelist(text);
        await env.SCREENER.put('whitelist', JSON.stringify(list));
        return json({ ok: true, whitelistSize: list.length });
      }
      const wl = await env.SCREENER.get('whitelist', 'json');
      return json({ whitelistSize: wl?.length || 0, sample: (wl || []).slice(0, 20) });
    }
    if (url.pathname === '/run') {
      if (url.searchParams.get('key') !== env.ADMIN_KEY) return json({ error: 'non autorise' }, 401);
      const n = Number(url.searchParams.get('n') || 40);
      const dry = url.searchParams.get('dry') === '1';
      try {
        const out = await runPipeline(env, { limitFund: n, persist: !dry });
        return json({ ok: true, dry, ...out.summary, top: out.result.top.slice(0, 20) });
      } catch (e) { return json({ error: e.message, stack: e.stack }, 500); }
    }
    return json({ service: 'stock-screener', endpoints: ['/latest', '/health', '/whitelist', '/run?key=..'] });
  },

  async scheduled(event, env, ctx) {
    ctx.waitUntil(runPipeline(env, { limitFund: runtimeCfg(env).fundChunk, persist: true }).catch((e) => console.error('cron', e.message)));
  }
};

function parseWhitelist(text) {
  const lines = text.split(/\r?\n/).map((l) => l.trim()).filter(Boolean);
  // supporte CSV avec en-tete "ticker" ou simple liste
  let idx = 0;
  const header = lines[0]?.toLowerCase().split(',').map((s) => s.trim());
  if (header && header.includes('ticker')) { idx = header.indexOf('ticker'); lines.shift(); }
  const set = new Set();
  for (const l of lines) {
    const cell = l.split(',')[idx] ?? l;
    const t = normTicker(cell);
    if (t) set.add(t);
  }
  return [...set];
}
// Normalisation UNIQUEMENT pour le matching whitelist (pas pour les appels API) :
// BRK.B / BRK-B / "BRK B" -> BRKB. Les appels API utilisent toujours le symbole d'origine.
const normTicker = (s) => (s || '').toUpperCase().trim().replace(/["']/g, '').replace(/[.\-\s]/g, '');

// ---------------------------------------------------------------------------
// Pipeline principal
// ---------------------------------------------------------------------------
async function runPipeline(env, { limitFund = 60, persist = true } = {}) {
  const cfg = runtimeCfg(env);
  const wl = (await env.SCREENER.get('whitelist', 'json')) || null;
  const wlSet = wl && wl.length ? new Set(wl.map(normTicker)) : null;

  // 1) Univers liquide US (1 appel screener)
  let universe = await fetchUniverse(env, cfg);
  // 2) Intersection Revolut si whitelist fournie
  if (wlSet) universe = universe.filter((u) => wlSet.has(normTicker(u.symbol)));
  // borne de securite
  if (universe.length > cfg.maxUniverse) universe = universe.slice(0, cfg.maxUniverse);
  const symbols = universe.map((u) => u.symbol);

  // 3) Quotes en lot (momentum + liquidite) pour tout l'univers
  const quotes = await fetchQuotes(symbols, env, cfg.quoteChunk);

  // 4) Rolling fondamentaux : refresh des `limitFund` plus anciens
  const cursor = Number((await env.SCREENER.get('cursor')) || 0) % Math.max(1, symbols.length);
  const slice = [];
  for (let i = 0; i < Math.min(limitFund, symbols.length); i++) slice.push(symbols[(cursor + i) % symbols.length]);
  await Promise.all(slice.map(async (sym) => {
    const f = await fetchFundamentals(sym, env);
    if (f) {
      if (env.ENABLE_PRICE_CHANGE === 'true') { const pc = await fetchPriceChange(sym, env); if (pc) Object.assign(f, pc); }
      await env.SCREENER.put('fund:' + sym, JSON.stringify({ ...f, _ts: Date.now() }), { expirationTtl: 60 * 60 * 24 * 60 }); // 60 j
    }
  }));
  if (persist) await env.SCREENER.put('cursor', String((cursor + slice.length) % Math.max(1, symbols.length)));

  // 5) Fusion quote + fondamentaux caches
  const enriched = [];
  for (const u of universe) {
    const q = quotes.get(u.symbol);
    const fRaw = await env.SCREENER.get('fund:' + u.symbol);
    if (!q || !fRaw) continue; // pas encore de fondamentaux -> attend son tour dans le rolling
    const f = JSON.parse(fRaw);
    enriched.push({
      symbol: u.symbol, name: u.name || q.name, sector: u.sector,
      price: q.price, marketCap: q.marketCap ?? u.marketCap, avgVolume: q.avgVolume,
      priceAvg50: q.priceAvg50, priceAvg200: q.priceAvg200, yearHigh: q.yearHigh, eps: q.eps,
      revenueGrowthYoY: f.revenueGrowthYoY, revenueCAGR3y: f.revenueCAGR3y, epsGrowthYoY: f.epsGrowthYoY,
      grossMargin: f.grossMargin, operatingMargin: f.operatingMargin, fcfMargin: f.fcfMargin,
      roe: f.roe, sharesGrowth: f.sharesGrowth, netDebtToEbitda: f.netDebtToEbitda,
      perf6m: f.perf6m, perf1y: f.perf1y,
      onRevolut: wlSet ? true : undefined, fundTs: f._ts
    });
  }

  // 6) Scoring + classement
  const result = rankUniverse(enriched, cfg);
  const summary = {
    universe: universe.length, quoted: quotes.size, enriched: enriched.length,
    survivors: result.survivors, top: result.top.length,
    fundRefreshed: slice.length, whitelist: wlSet ? wl.length : 0,
    coverage: symbols.length ? Math.round(enriched.length / symbols.length * 100) : 0
  };

  if (persist) {
    const payload = { generatedAt: new Date().toISOString(), summary, config: publicCfg(cfg), top: result.top };
    await env.SCREENER.put('latest', JSON.stringify(payload));
    await env.SCREENER.put('meta', JSON.stringify({ lastRun: payload.generatedAt, counts: summary }));
  }
  return { result, summary };
}

function publicCfg(cfg) {
  return { guards: cfg.guards, gate: cfg.gate, flags: cfg.flags, weights: cfg.weights };
}
