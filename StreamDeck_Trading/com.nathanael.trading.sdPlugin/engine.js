// Moteur de calcul des touches Stream Deck.
// Principe : on NE recopie PAS les formules du dashboard. On lit Trading_Dashboard.html, on en extrait
// toutes les fonctions de haut niveau (acorn) et on les execute dans un bac a sable avec les memes
// donnees Firebase. Les touches affichent donc exactement les chiffres de l'onglet Trading total,
// et suivent automatiquement toute correction faite dans le dashboard.
// Lecture seule : aucune ecriture Firebase.
'use strict';
const fs = require('fs');
const vm = require('vm');
const acorn = require('acorn');

const FB = 'https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com';
const DASH_URL_RAW = 'https://raw.githubusercontent.com/natquinson-cmd/Dashboard-Strat-gie-Trading/main/index.html';

// Initialisations sans effet de bord (litteraux, objets, tableaux) : gardees telles quelles.
// Tout le reste (appels, localStorage, DOM) est declare vide, pour que les fonctions qui y font
// reference ne levent pas de ReferenceError.
function isPureInit(node) {
  if (!node) return true;
  switch (node.type) {
    case 'Literal': return true;
    case 'Identifier': return node.name === 'undefined';
    case 'UnaryExpression': return isPureInit(node.argument);
    case 'TemplateLiteral': return node.expressions.length === 0;
    case 'ArrayExpression': return node.elements.every(e => !e || isPureInit(e));
    case 'ObjectExpression': return node.properties.every(p => p.type === 'Property' && !p.computed && isPureInit(p.value));
    default: return false;
  }
}

function extractFunctions(html) {
  const scripts = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(m => m[1]);
  if (!scripts.length) throw new Error('aucun <script> inline dans le dashboard');
  const out = [];
  for (const src of scripts) {
    const ast = acorn.parse(src, { ecmaVersion: 'latest', sourceType: 'script', allowAwaitOutsideFunction: true });
    for (const node of ast.body) {
      if (node.type === 'FunctionDeclaration') {
        out.push(src.slice(node.start, node.end));
      } else if (node.type === 'VariableDeclaration') {
        for (const d of node.declarations) {
          if (d.id.type !== 'Identifier') continue;
          out.push(isPureInit(d.init)
            ? 'var ' + d.id.name + ' = ' + (d.init ? src.slice(d.init.start, d.init.end) : 'undefined') + ';'
            : 'var ' + d.id.name + ';');
        }
      }
    }
  }
  return out.join('\n');
}

async function getJson(url) {
  const r = await fetch(url, { signal: AbortSignal.timeout(20000) });
  if (!r.ok) throw new Error('HTTP ' + r.status + ' sur ' + url.replace(FB, 'firebase').replace(/\?auth=.*/, ''));
  return r.json();
}
// Quand les regles Firebase seront verrouillees, poser FIREBASE_DB_SECRET (variable d'environnement).
function fbUrl(path) {
  const secret = process.env.FIREBASE_DB_SECRET;
  return FB + '/' + path + '.json' + (secret ? '?auth=' + encodeURIComponent(secret) : '');
}
const asList = v => Array.isArray(v) ? v.filter(Boolean) : (v && typeof v === 'object' ? Object.values(v) : []);

let fxCache = null;   // taux USD -> devises, rafraichi toutes les heures
async function getFx() {
  if (fxCache && Date.now() - fxCache.t < 3600000) return fxCache.rates;
  const j = await getJson('https://open.er-api.com/v6/latest/USD');
  if (!j || !j.rates || !j.rates.EUR) throw new Error('taux de change indisponibles');
  fxCache = { rates: j.rates, t: Date.now() };
  return j.rates;
}

async function loadDashboardSource(localPath) {
  try { return fs.readFileSync(localPath, 'utf8'); }
  catch (e) {
    const r = await fetch(DASH_URL_RAW, { signal: AbortSignal.timeout(20000) });
    if (!r.ok) throw new Error('dashboard introuvable (local et GitHub)');
    return r.text();
  }
}

// Calcule les chiffres de l'onglet Trading total + l'etat des ponts.
async function compute(opts) {
  const html = await loadDashboardSource(opts.dashboardPath);
  const code = extractFunctions(html);

  const [trades, deposits, fees, dividends, posHist, dwxDaily, livePrices, myPositions, quality, pont, igSync, fx, kids, kidsPrice, kidsHist] = await Promise.all([
    getJson(fbUrl('trades')), getJson(fbUrl('deposits')), getJson(fbUrl('fees')), getJson(fbUrl('dividends')),
    getJson(fbUrl('stocks/screener/positionsHistory')), getJson(fbUrl('dashboard/darwinex/daily')),
    getJson(fbUrl('stocks/screener/livePrices')), getJson(fbUrl('stocks/screener/myPositions')),
    getJson(fbUrl('stocks/screener/quality')), getJson(fbUrl('dashboard/pontIG')), getJson(fbUrl('igSyncStatus')), getFx(),
    getJson(fbUrl('stocks/kids')), getJson(fbUrl('stocks/kidsPrice')), getJson(fbUrl('stocks/kidsHistory')),
  ]);

  const store = {};
  const ctx = vm.createContext({
    console: { log() {}, warn() {}, error() {} },
    localStorage: { getItem: k => (k in store ? store[k] : null), setItem: (k, v) => { store[k] = String(v); }, removeItem: k => { delete store[k]; } },
  });
  vm.runInContext(code, ctx, { filename: 'Trading_Dashboard.html', timeout: 10000 });

  // Memes chargements que le dashboard (loadTradesFromFirebase, loadDepositsFromFirebase, etc.)
  const mapper = t => [t.date, t.symbol, t.gain, t.ref || '', t.size || 0, t.openLevel || 0, t.closeLevel || 0, t.openDate || '', t.closeDate || ''];
  ctx.realTrades = asList(trades).map(mapper);
  ctx.realDeposits = asList(deposits);
  ctx.realFees = asList(fees);
  ctx.realDividends = asList(dividends);
  ctx.darwinexDaily = (dwxDaily && typeof dwxDaily === 'object') ? dwxDaily : {};
  ctx.positionsHistoryData = posHist || {};
  ctx.usdEurRate = fx.EUR;
  ctx.SCR_FX = fx;
  ctx.SCR_POSITIONS = asList(myPositions);
  // carte des cours : snapshot quality (bourse de cotation), puis cours temps reel du cron VPS par-dessus
  ctx.SCR_PRICE_MAP = {};
  ((quality && quality.top) || []).forEach(t => {
    const mm = t.metrics || {};
    if (t.symbol && mm.price != null) ctx.SCR_PRICE_MAP[String(t.symbol).toUpperCase()] = Object.assign({}, mm, { symbol: String(t.symbol).toUpperCase() });
  });
  ctx.__lp = livePrices;

  const r = vm.runInContext(`(function () {
    SCR_HIST = scrHistArray(positionsHistoryData);
    if (typeof scrApplyLpValue === 'function') scrApplyLpValue(__lp);
    if (typeof scrMergeLiveHist === 'function') scrMergeLiveHist();
    const c = ttlCompute();
    const athJ = ttlAthDaily();
    const now = new Date();
    const ym = now.getFullYear() + '-' + String(now.getMonth() + 1).padStart(2, '0');
    const day = ym + '-' + String(now.getDate()).padStart(2, '0');
    const ath = Math.max(athJ.ath, c.capTotal);
    // Poches ETF et crypto : meme calcul ligne a ligne que l'ecran Actions du dashboard (scrMobilePortfolio),
    // plus-value = valeur au cours live - quantite x PRU, classement par mpCat. Converti en EUR.
    const cats = {};
    scrGetPositions().forEach(function (p) {
      const t = String(p.ticker || '').toUpperCase(), d = SCR_PRICE_MAP[t];
      const qty = (p.qty != null) ? p.qty : ((p.amount != null && p.pru) ? p.amount / p.pru : 0);
      const investi = qty * (p.pru || 0), pu = d ? scrToUsd(d.price, d.exchange) : null;
      const valeur = pu != null ? qty * pu : investi;
      const chg = (d && d.changePct != null) ? d.changePct : null;
      const dj = (chg != null && pu != null && typeof scrDayImpact === 'function') ? scrDayImpact(p.ticker, qty, pu, chg) : null;
      const k = mpCat(t, d), o = cats[k] || (cats[k] = { value: 0, inv: 0, day: 0, lines: 0 });
      o.value += valeur * c.fx; o.inv += investi * c.fx; o.day += (dj ? dj.usd : 0) * c.fx; o.lines++;
    });
    Object.keys(cats).forEach(function (k) { const o = cats[k]; o.pnl = o.value - o.inv; o.pnlPct = o.inv > 0 ? o.pnl / o.inv * 100 : 0; });
    return JSON.stringify({
      cats: cats,
      capTotal: c.capTotal, pnlTotal: c.pnlTotal, invTotal: c.invTotal, pnlPct: c.pnlPct,
      igNow: c.igNow, stkNow: c.stkNow, dwxNow: c.dwxNow,
      today: ttlDayData[day] || { ig: 0, stk: 0, dwx: 0, total: 0 },
      month: ttlMonthPnl[ym] || { ig: 0, stk: 0, dwx: 0, total: 0 },
      monthBase: ttlEquityAtMonthStart(now.getFullYear(), now.getMonth()),
      ath: ath, ddPct: ath > 0 ? (c.capTotal - ath) / ath * 100 : 0,
      liveAt: SCR_LIVE_AT || null,
    });
  })()`, ctx, { timeout: 10000 });

  return Object.assign(JSON.parse(r), { pont: pont || null, igSync: igSync || null, kids: kidsPocket(kids, kidsPrice, kidsHist), computedAt: Date.now() });
}

// Poche enfants (onglet Enfants, modele en PARTS de VWCE) : parts x cours, par enfant.
// Poche separee du capital personnel, jamais melangee aux chiffres ci-dessus.
// Variation du jour : cours actuel moins la derniere cloture de stocks/kidsHistory ({date: cours}) avant aujourd'hui.
function kidsPocket(kids, price, hist) {
  const px = price && Number(price.price);
  if (!kids || !(px > 0)) return null;
  const by = {};
  asList(kids.contributions).forEach(c => {
    const o = by[c.child] || (by[c.child] = { child: c.child, units: 0, paid: 0 });
    o.units += Number(c.units) || 0; o.paid += Number(c.amount) || 0;
  });
  const children = Object.values(by).map(o => Object.assign(o, { value: o.units * px })).sort((a, b) => b.value - a.value);
  const value = children.reduce((a, o) => a + o.value, 0), paid = children.reduce((a, o) => a + o.paid, 0);
  const d = new Date(), today = d.getFullYear() + '-' + String(d.getMonth() + 1).padStart(2, '0') + '-' + String(d.getDate()).padStart(2, '0');
  const prevKey = Object.keys(hist || {}).filter(k => k < today && Number(hist[k]) > 0).sort().pop();
  const prev = prevKey ? Number(hist[prevKey]) : null, units = children.reduce((a, o) => a + o.units, 0);
  const day = prev ? units * (px - prev) : null, dayPct = prev ? (px / prev - 1) * 100 : null;
  return { day, dayPct, value, paid, pnl: value - paid, pct: paid > 0 ? (value - paid) / paid * 100 : 0, price: px, ticker: price.ticker, priceAt: price.marketAt || price.at, children };
}

module.exports = { compute, extractFunctions };
