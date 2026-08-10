// providers.js — acces aux donnees de marche (gratuit).
// Principal : Financial Modeling Prep (FMP). Secours fondamentaux : Yahoo Finance (non officiel).
// Aucune cle en dur : tout vient de `env` (secrets Worker).

const FMP = 'https://financialmodelingprep.com';

async function fetchJSON(url, opts = {}, timeoutMs = 15000) {
  const ctrl = new AbortController();
  const id = setTimeout(() => ctrl.abort(), timeoutMs);
  try {
    const r = await fetch(url, { ...opts, signal: ctrl.signal, headers: { 'accept': 'application/json', 'user-agent': 'screener-worker/1.0', ...(opts.headers || {}) } });
    if (!r.ok) throw new Error(`HTTP ${r.status} sur ${url.split('?')[0]}`);
    return await r.json();
  } finally { clearTimeout(id); }
}

const n = (x) => { const v = typeof x === 'string' ? parseFloat(x) : x; return (typeof v === 'number' && isFinite(v)) ? v : null; };

// --- Univers : screener FMP (1 appel) -> titres US liquides ---
export async function fetchUniverse(env, cfg) {
  const p = new URLSearchParams({
    marketCapMoreThan: String(cfg.minMarketCap ?? 300e6),
    exchange: 'NYSE,NASDAQ,AMEX',
    country: 'US',
    isActivelyTrading: 'true',
    isEtf: 'false',
    isFund: 'false',
    volumeMoreThan: String(cfg.minVolume ?? 100000),
    limit: String(cfg.maxUniverse ?? 3000),
    apikey: env.FMP_KEY
  });
  const rows = await fetchJSON(`${FMP}/stable/company-screener?${p}`);
  if (!Array.isArray(rows)) throw new Error('screener FMP: reponse inattendue (verifier la cle/plan)');
  return rows.map((r) => ({
    symbol: r.symbol,
    name: r.companyName || r.name || r.symbol,
    sector: r.sector || 'N/A',
    marketCap: n(r.marketCap)
  })).filter((r) => r.symbol);
}

// --- Quotes en lot : momentum + liquidite + cap (peu d'appels) ---
export async function fetchQuotes(symbols, env, chunk = 50) {
  const out = new Map();
  for (let i = 0; i < symbols.length; i += chunk) {
    const batch = symbols.slice(i, i + chunk).join(',');
    let rows;
    try { rows = await fetchJSON(`${FMP}/stable/quote?symbol=${encodeURIComponent(batch)}&apikey=${env.FMP_KEY}`); }
    catch (e) { console.warn('quote batch echoue', e.message); continue; }
    for (const q of (Array.isArray(rows) ? rows : [])) {
      out.set(q.symbol, {
        price: n(q.price),
        marketCap: n(q.marketCap),
        avgVolume: n(q.averageVolume ?? q.avgVolume),
        priceAvg50: n(q.priceAvg50),
        priceAvg200: n(q.priceAvg200),
        yearHigh: n(q.yearHigh),
        yearLow: n(q.yearLow),
        eps: n(q.eps),
        exchange: q.exchange || q.exchangeShortName || null,
        name: q.name || null
      });
    }
  }
  return out;
}

// --- Fondamentaux par ticker : FMP d'abord, Yahoo en secours ---
export async function fetchFundamentals(symbol, env) {
  let f = null;
  try { f = await fmpFundamentals(symbol, env); } catch (e) { console.warn('FMP fond.', symbol, e.message); }
  if (!f || (f.revenueGrowthYoY == null && f.grossMargin == null)) {
    if (env.ENABLE_YAHOO_FALLBACK === 'true') {
      try { const y = await yahooFundamentals(symbol); if (y) f = { ...(f || {}), ...y }; } catch (e) { console.warn('Yahoo fond.', symbol, e.message); }
    }
  }
  return f;
}

async function fmpFundamentals(symbol, env) {
  const k = env.FMP_KEY;
  const [growthArr, ratios] = await Promise.all([
    fetchJSON(`${FMP}/stable/financial-growth?symbol=${symbol}&period=annual&limit=1&apikey=${k}`).catch(() => null),
    fetchJSON(`${FMP}/stable/ratios-ttm?symbol=${symbol}&apikey=${k}`).catch(() => null)
  ]);
  const g = Array.isArray(growthArr) ? growthArr[0] : null;
  const r = Array.isArray(ratios) ? ratios[0] : (ratios || null);
  if (!g && !r) return null;
  return {
    revenueGrowthYoY: n(g?.revenueGrowth),
    epsGrowthYoY: n(g?.epsgrowth ?? g?.epsGrowth),
    revenueCAGR3y: n(g?.threeYRevenueGrowthPerShare),
    sharesGrowth: n(g?.weightedAverageSharesGrowth),
    grossMargin: n(r?.grossProfitMarginTTM ?? r?.grossProfitMargin),
    operatingMargin: n(r?.operatingProfitMarginTTM ?? r?.operatingProfitMargin),
    roe: n(r?.returnOnEquityTTM ?? r?.returnOnEquity),
    netDebtToEbitda: n(r?.netDebtToEBITDATTM ?? r?.netDebtToEBITDA),
    _src: 'fmp'
  };
}

// Yahoo quoteSummary (non officiel) : fallback fondamentaux. Fragile depuis une IP Worker.
async function yahooFundamentals(symbol) {
  const mods = 'financialData,defaultKeyStatistics';
  const url = `https://query1.finance.yahoo.com/v10/finance/quoteSummary/${symbol}?modules=${mods}`;
  const j = await fetchJSON(url);
  const res = j?.quoteSummary?.result?.[0];
  if (!res) return null;
  const fd = res.financialData || {};
  return {
    revenueGrowthYoY: n(fd.revenueGrowth?.raw),
    epsGrowthYoY: n(fd.earningsGrowth?.raw),
    grossMargin: n(fd.grossMargins?.raw),
    operatingMargin: n(fd.operatingMargins?.raw),
    roe: n(fd.returnOnEquity?.raw),
    _src: 'yahoo'
  };
}

// Perf multi-fenetres (best-effort) pour la force relative
export async function fetchPriceChange(symbol, env) {
  try {
    const rows = await fetchJSON(`${FMP}/stable/stock-price-change?symbol=${symbol}&apikey=${env.FMP_KEY}`);
    const r = Array.isArray(rows) ? rows[0] : rows;
    if (!r) return null;
    return { perf6m: n(r['6M']) != null ? n(r['6M']) / 100 : null, perf1y: n(r['1Y']) != null ? n(r['1Y']) / 100 : null };
  } catch { return null; }
}
