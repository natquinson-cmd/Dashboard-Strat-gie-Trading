# screen.py — portage Python du coeur de scoring (identique a worker/src/screen.js).
# Oriente PRE-CASSURE : mene par les fondamentaux de croissance, bonus quand le prix
# consolide sous sa resistance, pas de course au momentum. Pur, testable.
from bisect import bisect_right

DEFAULT_CONFIG = {
    'guards': {
        'minMarketCap': 300e6, 'minPrice': 5, 'minDollarVolume': 5e6,
        'maxSharesGrowth': 0.10, 'maxNetDebtToEbitda': 4,
        'negEpsMinRevGrowth': 0.30, 'negEpsMinGrossMargin': 0.50,
    },
    'gate': {'minRevenueGrowthYoY': 0.15},
    'flags': {
        'revenueGrowthYoY': 0.40, 'epsGrowthYoY': 0.25, 'grossMargin': 0.40,
        'roe': 0.15, 'ruleOf40': 0.40, 'nearHigh': 0.97,
        'preBreakoutLow': -0.20, 'preBreakoutHigh': -0.03, 'brokenBelow': -0.35,
    },
    'weights': {'momentum': 0.12, 'salesGrowth': 0.34, 'epsGrowth': 0.26, 'quality': 0.20, 'volume': 0.08},
    'minSectorBucket': 12, 'topN': 50,
}


def _num(x):
    return x if isinstance(x, (int, float)) and x == x else None


def _rule_of_40(t):
    g = _num(t.get('revenueGrowthYoY'))
    m = _num(t.get('fcfMargin') if t.get('fcfMargin') is not None else t.get('operatingMargin'))
    if g is None or m is None:
        return None
    return g + m


def _momentum_raw(t):
    parts = []
    p, a200, yh = _num(t.get('price')), _num(t.get('priceAvg200')), _num(t.get('yearHigh'))
    if p is not None and a200:
        parts.append(p / a200 - 1)
    if p is not None and yh:
        parts.append(p / yh - 1)
    if _num(t.get('perf6m')) is not None:
        parts.append(t['perf6m'])
    if _num(t.get('perf12m')) is not None:
        parts.append(t['perf12m'])
    return sum(parts) / len(parts) if parts else None


def _is_uptrend(t):
    p, a50, a200 = _num(t.get('price')), _num(t.get('priceAvg50')), _num(t.get('priceAvg200'))
    if p is None or a200 is None or p <= a200:
        return False
    if a50 is not None and a50 <= a200:
        return False
    return True


def passes_guards(t, cfg=DEFAULT_CONFIG):
    g = cfg['guards']
    mc, pr, av = _num(t.get('marketCap')), _num(t.get('price')), _num(t.get('avgVolume'))
    if mc is None or pr is None:
        return False, 'donnees prix/cap manquantes'
    if mc < g['minMarketCap']:
        return False, 'capitalisation trop faible'
    if pr < g['minPrice']:
        return False, 'penny stock (prix < 5$)'
    if av is None:
        return False, 'volume manquant'
    if pr * av < g['minDollarVolume']:
        return False, 'liquidite insuffisante'
    rev, gm = _num(t.get('revenueGrowthYoY')), _num(t.get('grossMargin'))
    if rev is None or gm is None:
        return False, 'fondamentaux incomplets'
    eps = _num(t.get('eps'))
    if eps is not None and eps < 0:
        if not (rev >= g['negEpsMinRevGrowth'] and gm >= g['negEpsMinGrossMargin']):
            return False, 'perte non compensee (BPA<0 sans forte croissance+marge)'
    sg = _num(t.get('sharesGrowth'))
    if sg is not None and sg > g['maxSharesGrowth']:
        return False, 'dilution excessive'
    nd = _num(t.get('netDebtToEbitda'))
    if nd is not None and nd > g['maxNetDebtToEbitda']:
        return False, 'endettement excessif'
    if rev < cfg['gate']['minRevenueGrowthYoY']:
        return False, 'croissance CA sous le plancher growth'
    return True, None


def _pct_rank(sorted_asc, value):
    if value is None or not sorted_asc:
        return None
    return bisect_right(sorted_asc, value) / len(sorted_asc) * 100


def _dist(items, keyfn):
    return sorted(v for v in (keyfn(t) for t in items) if v is not None)


def _round1(x):
    return round(x, 1) if isinstance(x, (int, float)) else None


def _compute_flags(t, cfg):
    f, out = cfg['flags'], []
    if _num(t.get('revenueGrowthYoY')) is not None and t['revenueGrowthYoY'] >= f['revenueGrowthYoY']:
        out.append('CA+40%')
    if _num(t.get('epsGrowthYoY')) is not None and t['epsGrowthYoY'] >= f['epsGrowthYoY']:
        out.append('BPA+25%')
    if _num(t.get('grossMargin')) is not None and t['grossMargin'] >= f['grossMargin']:
        out.append('marge>=40%')
    if _num(t.get('roe')) is not None and t['roe'] >= f['roe']:
        out.append('ROE>=15%')
    r40 = _rule_of_40(t)
    if r40 is not None and r40 >= f['ruleOf40']:
        out.append('Rule40')
    p, yh = _num(t.get('price')), _num(t.get('yearHigh'))
    dh = (p / yh - 1) if (p is not None and yh) else None
    if dh is not None:
        if f['preBreakoutLow'] <= dh <= f['preBreakoutHigh']:
            out.append('pré-cassure')
        elif p >= f['nearHigh'] * yh:
            out.append('au sommet')
    if _is_uptrend(t):
        out.append('tendance haussiere')
    return out


def rank_universe(universe, cfg=DEFAULT_CONFIG):
    survivors, rejected = [], []
    for t in universe:
        ok, reason = passes_guards(t, cfg)
        if ok:
            s = dict(t)
            s['_ro40'] = _rule_of_40(t); s['_mom'] = _momentum_raw(t); s['_uptrend'] = _is_uptrend(t)
            survivors.append(s)
        else:
            rejected.append({'symbol': t.get('symbol'), 'reason': reason})

    by_sector = {}
    for t in survivors:
        by_sector.setdefault(t.get('sector') or 'N/A', []).append(t)

    def dists(items):
        return {
            'mom': _dist(items, lambda t: t.get('_mom')),
            'sales': _dist(items, lambda t: _num(t.get('revenueGrowthYoY'))),
            'sales3y': _dist(items, lambda t: _num(t.get('revenueCAGR3y'))),
            'eps': _dist(items, lambda t: _num(t.get('epsGrowthYoY'))),
            'gm': _dist(items, lambda t: _num(t.get('grossMargin'))),
            'roe': _dist(items, lambda t: _num(t.get('roe'))),
            'ro40': _dist(items, lambda t: t.get('_ro40')),
            'vol': _dist(items, lambda t: (t['price'] * t['avgVolume']) if (_num(t.get('price')) is not None and _num(t.get('avgVolume')) is not None) else None),
        }

    global_d = dists(survivors)
    sector_d = {s: dists(arr) for s, arr in by_sector.items() if len(arr) >= cfg['minSectorBucket']}

    def pick(t, field, rawfn):
        d = sector_d.get(t.get('sector'), global_d)
        return _pct_rank(d[field], rawfn(t))

    def avg(xs):
        v = [x for x in xs if x is not None]
        return sum(v) / len(v) if v else None

    w = cfg['weights']
    scored = []
    for t in survivors:
        p_mom = pick(t, 'mom', lambda x: x.get('_mom'))
        p_sales = avg([pick(t, 'sales', lambda x: _num(x.get('revenueGrowthYoY'))),
                       pick(t, 'sales3y', lambda x: _num(x.get('revenueCAGR3y')))])
        p_eps = pick(t, 'eps', lambda x: _num(x.get('epsGrowthYoY')))
        p_qual = avg([pick(t, 'gm', lambda x: _num(x.get('grossMargin'))),
                      pick(t, 'roe', lambda x: _num(x.get('roe'))),
                      pick(t, 'ro40', lambda x: x.get('_ro40'))])
        p_vol = pick(t, 'vol', lambda x: (x['price'] * x['avgVolume']) if (_num(x.get('price')) is not None and _num(x.get('avgVolume')) is not None) else None)

        comps = [(p_mom, w['momentum']), (p_sales, w['salesGrowth']), (p_eps, w['epsGrowth']),
                 (p_qual, w['quality']), (p_vol, w['volume'])]
        comps = [(v, ww) for (v, ww) in comps if v is not None]
        wsum = sum(ww for _, ww in comps) or 1
        score = sum(v * ww for v, ww in comps) / wsum

        p, yh = _num(t.get('price')), _num(t.get('yearHigh'))
        dh = (p / yh - 1) if (p is not None and yh) else None
        adj = 1.0
        if dh is not None:
            if cfg['flags']['preBreakoutLow'] <= dh <= cfg['flags']['preBreakoutHigh']:
                adj = 1.06
            elif dh < cfg['flags']['brokenBelow'] and not t['_uptrend']:
                adj = 0.85
        penalized = min(100, score * adj)

        scored.append({
            'symbol': t.get('symbol'), 'name': t.get('name'), 'sector': t.get('sector') or 'N/A',
            'score': round(penalized, 1),
            'subscores': {'momentum': _round1(p_mom), 'salesGrowth': _round1(p_sales),
                          'epsGrowth': _round1(p_eps), 'quality': _round1(p_qual), 'volume': _round1(p_vol)},
            'metrics': {
                'price': t.get('price'), 'marketCap': t.get('marketCap'),
                'revenueGrowthYoY': t.get('revenueGrowthYoY'), 'revenueCAGR3y': t.get('revenueCAGR3y'),
                'epsGrowthYoY': t.get('epsGrowthYoY'), 'grossMargin': t.get('grossMargin'), 'roe': t.get('roe'),
                'ruleOf40': t.get('_ro40'), 'priceAvg50': t.get('priceAvg50'), 'priceAvg200': t.get('priceAvg200'),
                'yearHigh': t.get('yearHigh'), 'distToHigh': dh, 'perf6m': t.get('perf6m'),
                'perf12m': t.get('perf12m'), 'uptrend': t['_uptrend'],
            },
            'flags': _compute_flags(t, cfg),
        })

    scored.sort(key=lambda x: x['score'], reverse=True)
    return {'generatedFrom': len(universe), 'survivors': len(survivors),
            'rejectedCount': len(rejected), 'top': scored[:cfg['topN']], 'all': scored}
