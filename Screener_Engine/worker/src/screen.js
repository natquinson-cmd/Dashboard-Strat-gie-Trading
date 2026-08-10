// screen.js — coeur du moteur (pur, sans I/O), testable en local et importe par le Worker.
// Prend une liste de titres enrichis, applique les garde-fous + un plancher growth,
// puis calcule un score composite base sur des PERCENTILES sectoriels et classe.

// ---------------------------------------------------------------------------
// Configuration des criteres "growth agressif". Tout est ajustable ici.
// ---------------------------------------------------------------------------
export const DEFAULT_CONFIG = {
  // Garde-fous DURS (exclusion si echec) — liquidite / anti-penny / qualite mini
  guards: {
    minMarketCap: 300e6,       // >= 300 M$
    minPrice: 5,               // >= 5 $ (anti penny stock)
    minDollarVolume: 5e6,      // prix * volume moyen >= 5 M$/jour
    maxSharesGrowth: 0.10,     // dilution < 10 %/an (ignore si donnee absente)
    maxNetDebtToEbitda: 4,     // dette nette / EBITDA < 4x (ignore si absent)
    // Exception BPA negatif : autorise seulement si forte croissance + grosse marge
    negEpsMinRevGrowth: 0.30,  // CA YoY >= 30 %
    negEpsMinGrossMargin: 0.50 // marge brute >= 50 %
  },
  // Plancher "growth" (gate) pour rester oriente croissance
  gate: {
    minRevenueGrowthYoY: 0.15  // CA YoY >= 15 % (sinon ecarte, ce n'est pas du growth)
  },
  // Seuils "agressifs" servant de DRAPEAUX (flags) affiches, pas d'exclusion
  flags: {
    revenueGrowthYoY: 0.40,
    epsGrowthYoY: 0.25,
    grossMargin: 0.40,
    roe: 0.15,
    ruleOf40: 0.40,
    nearHigh: 0.85 // cours >= 85 % du plus-haut 52 sem
  },
  // Poids du score composite (somme = 1)
  weights: {
    momentum: 0.32,
    salesGrowth: 0.25,
    epsGrowth: 0.20,
    quality: 0.15,
    volume: 0.08
  },
  // Percentiles par secteur si le bucket a au moins N noms, sinon percentile global
  minSectorBucket: 12,
  topN: 50 // taille du classement conserve
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
const num = (x) => (typeof x === 'number' && isFinite(x)) ? x : null;

// Rendement composite (Rule of 40) : croissance CA % + marge FCF/operationnelle %
function ruleOf40(t) {
  const g = num(t.revenueGrowthYoY);
  const m = num(t.fcfMargin != null ? t.fcfMargin : t.operatingMargin);
  if (g == null || m == null) return null;
  return g + m; // exprime en fraction (0.40 = 40 %)
}

// Momentum brut : moyenne de sous-signaux normalises grossierement (avant percentile)
function momentumRaw(t) {
  const parts = [];
  if (num(t.price) != null && num(t.priceAvg200) != null && t.priceAvg200 > 0)
    parts.push(t.price / t.priceAvg200 - 1);            // au-dessus/dessous MM200
  if (num(t.price) != null && num(t.yearHigh) != null && t.yearHigh > 0)
    parts.push(t.price / t.yearHigh - 1);               // proximite plus-haut 52s (<=0)
  if (num(t.perf6m) != null) parts.push(t.perf6m);      // perf 6 mois
  if (num(t.perf1y) != null) parts.push(t.perf1y);      // perf 12 mois
  if (!parts.length) return null;
  return parts.reduce((a, b) => a + b, 0) / parts.length;
}

// Structure haussiere requise pour un candidat momentum
function isUptrend(t) {
  const p = num(t.price), a50 = num(t.priceAvg50), a200 = num(t.priceAvg200);
  if (p == null || a200 == null) return false;
  if (p <= a200) return false;
  if (a50 != null && a50 <= a200) return false;
  return true;
}

// ---------------------------------------------------------------------------
// Garde-fous + gate. Renvoie {ok, reason} ; ok=false => exclu.
// ---------------------------------------------------------------------------
export function passesGuards(t, cfg = DEFAULT_CONFIG) {
  const g = cfg.guards;
  const mc = num(t.marketCap), pr = num(t.price), av = num(t.avgVolume);
  if (mc == null || pr == null) return { ok: false, reason: 'donnees prix/cap manquantes' };
  if (mc < g.minMarketCap) return { ok: false, reason: 'capitalisation trop faible' };
  if (pr < g.minPrice) return { ok: false, reason: 'penny stock (prix < 5 $)' };
  if (av == null) return { ok: false, reason: 'volume manquant' };
  if (pr * av < g.minDollarVolume) return { ok: false, reason: 'liquidite insuffisante' };

  // Fondamentaux minimaux presents
  const rev = num(t.revenueGrowthYoY), gm = num(t.grossMargin);
  if (rev == null || gm == null) return { ok: false, reason: 'fondamentaux incomplets' };

  // Exception BPA negatif
  const eps = num(t.eps);
  if (eps != null && eps < 0) {
    if (!(rev >= g.negEpsMinRevGrowth && gm >= g.negEpsMinGrossMargin))
      return { ok: false, reason: 'perte non compensee (BPA<0 sans forte croissance+marge)' };
  }
  // Dilution
  const sg = num(t.sharesGrowth);
  if (sg != null && sg > g.maxSharesGrowth) return { ok: false, reason: 'dilution excessive' };
  // Dette
  const nd = num(t.netDebtToEbitda);
  if (nd != null && nd > g.maxNetDebtToEbitda) return { ok: false, reason: 'endettement excessif' };

  // Gate growth
  if (rev < cfg.gate.minRevenueGrowthYoY) return { ok: false, reason: 'croissance CA sous le plancher growth' };

  return { ok: true, reason: null };
}

// ---------------------------------------------------------------------------
// Percentile rank d'une valeur dans un tableau trie croissant (0..100).
// ---------------------------------------------------------------------------
function percentileRank(sortedAsc, value) {
  if (value == null || !sortedAsc.length) return null;
  // proportion des valeurs <= value
  let lo = 0, hi = sortedAsc.length;
  while (lo < hi) { const mid = (lo + hi) >> 1; if (sortedAsc[mid] <= value) lo = mid + 1; else hi = mid; }
  return (lo / sortedAsc.length) * 100;
}

function buildDistributions(items, keyFn) {
  const arr = items.map(keyFn).filter((v) => v != null).sort((a, b) => a - b);
  return arr;
}

// ---------------------------------------------------------------------------
// Scoring principal : garde les survivants, calcule les percentiles (par secteur
// si bucket assez grand, sinon global), combine en score 0-100, trie, top N.
// ---------------------------------------------------------------------------
export function rankUniverse(universe, cfg = DEFAULT_CONFIG) {
  const survivors = [];
  const rejected = [];
  for (const t of universe) {
    const g = passesGuards(t, cfg);
    if (g.ok) survivors.push({ ...t, _ro40: ruleOf40(t), _mom: momentumRaw(t), _uptrend: isUptrend(t) });
    else rejected.push({ symbol: t.symbol, reason: g.reason });
  }

  // Regroupement par secteur pour les percentiles
  const bySector = new Map();
  for (const t of survivors) {
    const s = t.sector || 'N/A';
    if (!bySector.has(s)) bySector.set(s, []);
    bySector.get(s).push(t);
  }

  // Distributions globales (fallback)
  const globalDist = {
    mom: buildDistributions(survivors, (t) => t._mom),
    sales: buildDistributions(survivors, (t) => num(t.revenueGrowthYoY)),
    sales3y: buildDistributions(survivors, (t) => num(t.revenueCAGR3y)),
    eps: buildDistributions(survivors, (t) => num(t.epsGrowthYoY)),
    gm: buildDistributions(survivors, (t) => num(t.grossMargin)),
    roe: buildDistributions(survivors, (t) => num(t.roe)),
    ro40: buildDistributions(survivors, (t) => t._ro40),
    vol: buildDistributions(survivors, (t) => (num(t.price) != null && num(t.avgVolume) != null) ? t.price * t.avgVolume : null)
  };

  // Distributions par secteur (si bucket >= minSectorBucket)
  const sectorDist = new Map();
  for (const [s, arr] of bySector) {
    if (arr.length >= cfg.minSectorBucket) {
      sectorDist.set(s, {
        mom: buildDistributions(arr, (t) => t._mom),
        sales: buildDistributions(arr, (t) => num(t.revenueGrowthYoY)),
        sales3y: buildDistributions(arr, (t) => num(t.revenueCAGR3y)),
        eps: buildDistributions(arr, (t) => num(t.epsGrowthYoY)),
        gm: buildDistributions(arr, (t) => num(t.grossMargin)),
        roe: buildDistributions(arr, (t) => num(t.roe)),
        ro40: buildDistributions(arr, (t) => t._ro40),
        vol: buildDistributions(arr, (t) => (num(t.price) != null && num(t.avgVolume) != null) ? t.price * t.avgVolume : null)
      });
    }
  }

  const pick = (t, field, rawFn) => {
    const d = sectorDist.get(t.sector) || globalDist;
    return percentileRank(d[field], rawFn(t));
  };
  const avg = (xs) => { const v = xs.filter((x) => x != null); return v.length ? v.reduce((a, b) => a + b, 0) / v.length : null; };

  const scored = survivors.map((t) => {
    const pMom = pick(t, 'mom', (x) => x._mom);
    const pSales = avg([pick(t, 'sales', (x) => num(x.revenueGrowthYoY)), pick(t, 'sales3y', (x) => num(x.revenueCAGR3y))]);
    const pEps = pick(t, 'eps', (x) => num(x.epsGrowthYoY));
    const pQual = avg([pick(t, 'gm', (x) => num(x.grossMargin)), pick(t, 'roe', (x) => num(x.roe)), pick(t, 'ro40', (x) => x._ro40)]);
    const pVol = pick(t, 'vol', (x) => (num(x.price) != null && num(x.avgVolume) != null) ? x.price * x.avgVolume : null);

    const w = cfg.weights;
    // Somme ponderee sur les composantes disponibles, renormalisee par le poids present
    const comps = [
      [pMom, w.momentum], [pSales, w.salesGrowth], [pEps, w.epsGrowth], [pQual, w.quality], [pVol, w.volume]
    ].filter(([v]) => v != null);
    const wsum = comps.reduce((a, [, ww]) => a + ww, 0) || 1;
    const score = comps.reduce((a, [v, ww]) => a + v * ww, 0) / wsum;

    // Malus si pas en tendance haussiere (le growth agressif exige la confirmation prix)
    const penalized = t._uptrend ? score : score * 0.7;

    return {
      symbol: t.symbol, name: t.name, sector: t.sector || 'N/A',
      score: Math.round(penalized * 10) / 10,
      subscores: {
        momentum: round1(pMom), salesGrowth: round1(pSales), epsGrowth: round1(pEps),
        quality: round1(pQual), volume: round1(pVol)
      },
      metrics: {
        price: t.price, marketCap: t.marketCap,
        revenueGrowthYoY: t.revenueGrowthYoY, revenueCAGR3y: t.revenueCAGR3y ?? null,
        epsGrowthYoY: t.epsGrowthYoY ?? null, grossMargin: t.grossMargin, roe: t.roe ?? null,
        ruleOf40: t._ro40, priceAvg50: t.priceAvg50 ?? null, priceAvg200: t.priceAvg200 ?? null,
        yearHigh: t.yearHigh ?? null, distToHigh: (num(t.price) != null && num(t.yearHigh)) ? (t.price / t.yearHigh - 1) : null,
        perf6m: t.perf6m ?? null, perf1y: t.perf1y ?? null, uptrend: t._uptrend
      },
      flags: computeFlags(t, cfg),
      onRevolut: t.onRevolut !== false // true par defaut ; false si absent de la whitelist
    };
  });

  scored.sort((a, b) => b.score - a.score);
  return {
    generatedFrom: universe.length,
    survivors: survivors.length,
    rejectedCount: rejected.length,
    top: scored.slice(0, cfg.topN),
    all: scored
  };
}

function round1(x) { return x == null ? null : Math.round(x * 10) / 10; }

function computeFlags(t, cfg) {
  const f = cfg.flags, out = [];
  if (num(t.revenueGrowthYoY) != null && t.revenueGrowthYoY >= f.revenueGrowthYoY) out.push('CA+40%');
  if (num(t.epsGrowthYoY) != null && t.epsGrowthYoY >= f.epsGrowthYoY) out.push('BPA+25%');
  if (num(t.grossMargin) != null && t.grossMargin >= f.grossMargin) out.push('marge>=40%');
  if (num(t.roe) != null && t.roe >= f.roe) out.push('ROE>=15%');
  const r40 = ruleOf40(t); if (r40 != null && r40 >= f.ruleOf40) out.push('Rule40');
  if (num(t.price) != null && num(t.yearHigh) && t.price >= f.nearHigh * t.yearHigh) out.push('proche 52s-haut');
  if (isUptrend(t)) out.push('tendance haussiere');
  return out;
}
