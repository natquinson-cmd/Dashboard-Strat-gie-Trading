// Test local du coeur du moteur (screen.js). Aucune cle API requise.
// Lancer : node Screener_Engine/worker/test/local_test.mjs
import { rankUniverse, passesGuards, DEFAULT_CONFIG } from '../src/screen.js';

let pass = 0, fail = 0;
const ok = (cond, msg) => { if (cond) { pass++; } else { fail++; console.error('  ECHEC:', msg); } };

// --- Univers fictif ---
const U = [
  // Un leader growth typique : forte croissance, marge, momentum, liquide
  { symbol: 'GROW', name: 'GrowthCo', sector: 'Technology', price: 100, marketCap: 20e9, avgVolume: 3e6,
    priceAvg50: 92, priceAvg200: 80, yearHigh: 105, perf6m: 0.35, perf1y: 0.7,
    revenueGrowthYoY: 0.55, revenueCAGR3y: 0.45, epsGrowthYoY: 0.6, grossMargin: 0.75, roe: 0.25, eps: 3.2,
    operatingMargin: 0.15, sharesGrowth: 0.03, netDebtToEbitda: 0.5 },
  // Croissance correcte mais momentum faible (sous MM200) -> penalise
  { symbol: 'SLOW', name: 'SlowMo', sector: 'Technology', price: 40, marketCap: 8e9, avgVolume: 1e6,
    priceAvg50: 45, priceAvg200: 50, yearHigh: 70, perf6m: -0.2, perf1y: -0.1,
    revenueGrowthYoY: 0.28, revenueCAGR3y: 0.25, epsGrowthYoY: 0.2, grossMargin: 0.65, roe: 0.18, eps: 1.1,
    operatingMargin: 0.1, sharesGrowth: 0.02, netDebtToEbitda: 1 },
  // Penny stock -> exclu par garde-fou
  { symbol: 'PENNY', name: 'PennyJunk', sector: 'Healthcare', price: 2, marketCap: 500e6, avgVolume: 4e6,
    priceAvg50: 1.8, priceAvg200: 1.5, yearHigh: 3, perf6m: 1.2, perf1y: 2.0,
    revenueGrowthYoY: 0.8, revenueCAGR3y: 0.6, epsGrowthYoY: null, grossMargin: 0.55, roe: null, eps: -0.4,
    operatingMargin: -0.3, sharesGrowth: 0.2 },
  // Cap trop faible -> exclu
  { symbol: 'TINY', name: 'TinyCap', sector: 'Technology', price: 12, marketCap: 120e6, avgVolume: 2e5,
    priceAvg50: 11, priceAvg200: 10, yearHigh: 13, perf6m: 0.4, perf1y: 0.9,
    revenueGrowthYoY: 0.7, revenueCAGR3y: 0.5, epsGrowthYoY: 0.5, grossMargin: 0.6, roe: 0.2, eps: 0.8 },
  // Croissance sous le plancher growth (15 %) -> exclu par gate
  { symbol: 'MATURE', name: 'MatureInc', sector: 'Industrials', price: 80, marketCap: 30e9, avgVolume: 2e6,
    priceAvg50: 79, priceAvg200: 75, yearHigh: 85, perf6m: 0.05, perf1y: 0.1,
    revenueGrowthYoY: 0.06, revenueCAGR3y: 0.05, epsGrowthYoY: 0.08, grossMargin: 0.35, roe: 0.22, eps: 4,
    operatingMargin: 0.18, sharesGrowth: 0.0, netDebtToEbitda: 2 },
  // BPA negatif MAIS forte croissance + grosse marge -> exception acceptee
  { symbol: 'HYPER', name: 'HyperSaaS', sector: 'Technology', price: 60, marketCap: 5e9, avgVolume: 1.5e6,
    priceAvg50: 55, priceAvg200: 48, yearHigh: 62, perf6m: 0.5, perf1y: 1.1,
    revenueGrowthYoY: 0.9, revenueCAGR3y: 0.7, epsGrowthYoY: null, grossMargin: 0.8, roe: null, eps: -0.5,
    operatingMargin: -0.05, sharesGrowth: 0.06, netDebtToEbitda: null },
  // BPA negatif SANS marge suffisante -> exclu par exception
  { symbol: 'BURN', name: 'CashBurner', sector: 'Consumer', price: 25, marketCap: 2e9, avgVolume: 8e5,
    priceAvg50: 24, priceAvg200: 20, yearHigh: 30, perf6m: 0.2, perf1y: 0.3,
    revenueGrowthYoY: 0.5, revenueCAGR3y: 0.4, epsGrowthYoY: null, grossMargin: 0.25, roe: null, eps: -1.2,
    operatingMargin: -0.4, sharesGrowth: 0.15 },
  // Dilution excessive -> exclu
  { symbol: 'DILUT', name: 'DilutionCorp', sector: 'Technology', price: 30, marketCap: 3e9, avgVolume: 1e6,
    priceAvg50: 29, priceAvg200: 26, yearHigh: 33, perf6m: 0.25, perf1y: 0.4,
    revenueGrowthYoY: 0.6, revenueCAGR3y: 0.5, epsGrowthYoY: 0.3, grossMargin: 0.7, roe: 0.16, eps: 0.5,
    operatingMargin: 0.05, sharesGrowth: 0.3 }
];

const res = rankUniverse(U, DEFAULT_CONFIG);
const bySym = Object.fromEntries(res.all.map((r) => [r.symbol, r]));
const kept = new Set(res.all.map((r) => r.symbol));

console.log(`Univers=${res.generatedFrom} survivants=${res.survivors} rejetes=${res.rejectedCount}`);
console.log('Classement :', res.all.map((r) => `${r.symbol}(${r.score})`).join('  '));

// --- Assertions garde-fous ---
ok(!kept.has('PENNY'), 'PENNY (prix 2 $) doit etre exclu');
ok(!kept.has('TINY'), 'TINY (cap 120 M$) doit etre exclu');
ok(!kept.has('MATURE'), 'MATURE (CA +6 %) doit etre exclu par le gate growth');
ok(!kept.has('BURN'), 'BURN (BPA<0, marge 25 %) doit etre exclu');
ok(!kept.has('DILUT'), 'DILUT (dilution 30 %) doit etre exclu');

// --- Assertions inclusion ---
ok(kept.has('GROW'), 'GROW doit etre retenu');
ok(kept.has('HYPER'), 'HYPER (BPA<0 mais CA+90 %, marge 80 %) doit etre retenu via exception');
ok(kept.has('SLOW'), 'SLOW doit etre retenu (passe les garde-fous)');

// --- Assertions classement ---
ok(bySym.GROW && bySym.SLOW && bySym.GROW.score > bySym.SLOW.score, 'GROW doit primer SLOW');
ok(bySym.SLOW && bySym.SLOW.metrics.uptrend === false, 'SLOW doit etre marque hors-tendance');
ok(bySym.GROW && bySym.GROW.metrics.uptrend === true, 'GROW doit etre en tendance haussiere');
ok(res.all.every((r, i, a) => i === 0 || a[i - 1].score >= r.score), 'le classement doit etre decroissant');
ok(bySym.GROW && bySym.GROW.flags.includes('CA+40%'), 'GROW doit porter le flag CA+40%');

// --- Garde-fou unitaire ---
ok(passesGuards(U[0]).ok === true, 'passesGuards(GROW) doit etre ok');
ok(passesGuards(U[2]).ok === false, 'passesGuards(PENNY) doit echouer');

console.log(`\n${pass} OK, ${fail} echec(s)`);
process.exit(fail ? 1 : 0);
