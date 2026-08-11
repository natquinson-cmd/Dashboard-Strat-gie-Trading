# quality.py — 2e mode du screener : QUALITE + VALORISATION (style "prix decroche sous les benefices").
# Univers de grandes societes de qualite, note de Achat fort a Surevaluee selon la valorisation.
# Pur (aucun I/O), testable. Le signal cle = les benefices ont-ils grimpe plus vite que le cours
# (multiple comprime = pas cher), tout en etant une bonne societe (gate qualite).
from bisect import bisect_right

QUALITY_CONFIG = {
    'gate': {
        'minRoe': 0.12,               # rentabilite des capitaux propres
        'maxNetDebtToEbitda': 4.0,    # dette maitrisee (ignore si absent)
        'requirePositiveFcf': True,   # free cash-flow positif
        'requirePositiveEarnings': True,  # benefices en croissance (pas en declin structurel)
        'minMarketCap': 5e9,
    },
    # Poids du score de VALORISATION (plus le score est haut, plus c'est "pas cher")
    'weights': {'peg': 0.30, 'gap': 0.30, 'fcfYield': 0.20, 'fwdPe': 0.20},
    # Bandes de notation sur le score de valorisation 0-100 (au sein des survivants qualite)
    'ratingBands': [(80, 'Achat fort'), (60, 'Achat'), (40, 'Neutre'), (0, 'Surévaluée')],
    'minSectorBucket': 8,
    'topN': 60,
}


def _num(x):
    return x if isinstance(x, (int, float)) and x == x else None


def passes_quality(t, cfg=QUALITY_CONFIG):
    g = cfg['gate']
    mc = _num(t.get('marketCap'))
    if mc is None or mc < g['minMarketCap']:
        return False, 'trop petite'
    roe = _num(t.get('roe'))
    if roe is None or roe < g['minRoe']:
        return False, 'rentabilite insuffisante (ROE)'
    if g['requirePositiveFcf']:
        fcf = _num(t.get('freeCashflow'))
        if fcf is not None and fcf <= 0:
            return False, 'free cash-flow negatif'
    if g['requirePositiveEarnings']:
        ec = _num(t.get('earningsCAGR'))
        eg = _num(t.get('earningsGrowthYoY'))
        # au moins un signal de croissance des benefices, et pas de declin franc
        if ec is not None and ec < 0 and (eg is None or eg < 0):
            return False, 'benefices en declin'
    nd = _num(t.get('netDebtToEbitda'))
    if nd is not None and nd > g['maxNetDebtToEbitda']:
        return False, 'endettement excessif'
    # il faut un vrai multiple exploitable (evite les cotations etrangeres "vides")
    if all(_num(t.get(k)) is None for k in ('peg', 'forwardPE', 'trailingPE')):
        return False, 'valorisation non calculable'
    return True, None


def _pct(sorted_asc, v):
    if v is None or not sorted_asc:
        return None
    return bisect_right(sorted_asc, v) / len(sorted_asc) * 100


def _dist(items, keyfn):
    return sorted(v for v in (keyfn(t) for t in items) if v is not None)


def _round1(x):
    return round(x, 1) if isinstance(x, (int, float)) else None


def _rating(score, cfg):
    for thr, label in cfg['ratingBands']:
        if score >= thr:
            return label
    return cfg['ratingBands'][-1][1]


def rate_universe(universe, cfg=QUALITY_CONFIG):
    survivors, rejected = [], []
    for t in universe:
        ok, why = passes_quality(t, cfg)
        (survivors if ok else rejected).append(t if ok else {'symbol': t.get('symbol'), 'reason': why})

    # Signaux de valorisation orientes "plus haut = moins cher"
    #   pegInv    : PEG bas = pas cher      -> on prend -peg (borne pour eviter les negatifs absurdes)
    #   gap       : CAGR benefices - CAGR cours (positif = cours a la traine = pas cher)
    #   fcfYield  : FCF / capitalisation (haut = pas cher)
    #   fwdPeInv  : P/E forward bas = pas cher -> -forwardPE
    def peg_signal(t):
        p = _num(t.get('peg'))
        return (-p) if (p is not None and p > 0) else None
    def fwdpe_signal(t):
        p = _num(t.get('forwardPE'))
        return (-p) if (p is not None and p > 0) else None

    dists = {
        'peg': _dist(survivors, peg_signal),
        'gap': _dist(survivors, lambda t: _num(t.get('gap'))),
        'fcf': _dist(survivors, lambda t: _num(t.get('fcfYield'))),
        'fpe': _dist(survivors, fwdpe_signal),
    }
    w = cfg['weights']

    scored = []
    for t in survivors:
        comps = [
            (_pct(dists['peg'], peg_signal(t)), w['peg']),
            (_pct(dists['gap'], _num(t.get('gap'))), w['gap']),
            (_pct(dists['fcf'], _num(t.get('fcfYield'))), w['fcfYield']),
            (_pct(dists['fpe'], fwdpe_signal(t)), w['fwdPe']),
        ]
        comps = [(v, ww) for (v, ww) in comps if v is not None]
        wsum = sum(ww for _, ww in comps) or 1
        vscore = sum(v * ww for v, ww in comps) / wsum
        scored.append({
            'symbol': t.get('symbol'), 'name': t.get('name'), 'sector': t.get('sector') or 'N/A',
            'rating': _rating(vscore, cfg),
            'valuationScore': round(vscore, 1),
            'metrics': {
                'price': t.get('price'), 'marketCap': t.get('marketCap'), 'exchange': t.get('exchange'),
                'peg': t.get('peg'), 'trailingPE': t.get('trailingPE'), 'forwardPE': t.get('forwardPE'),
                'earningsCAGR': t.get('earningsCAGR'), 'priceCAGR': t.get('priceCAGR'), 'gap': t.get('gap'),
                'roe': t.get('roe'), 'grossMargin': t.get('grossMargin'), 'fcfYield': t.get('fcfYield'),
                'revenueGrowthYoY': t.get('revenueGrowthYoY'), 'earningsGrowthYoY': t.get('earningsGrowthYoY'),
                'dividendYield': t.get('dividendYield'),
            },
        })

    # tri : Achat fort d'abord (score de valo decroissant)
    scored.sort(key=lambda x: x['valuationScore'], reverse=True)
    return {'generatedFrom': len(universe), 'survivors': len(survivors),
            'rejectedCount': len(rejected), 'top': scored[:cfg['topN']], 'all': scored}
