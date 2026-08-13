# quality.py — 2e mode du screener : QUALITE + VALORISATION (style "prix decroche sous les benefices").
# Univers de grandes societes de qualite, note de Achat fort a Surevaluee selon la valorisation.
# Pur (aucun I/O), testable. Le signal cle = les benefices ont-ils grimpe plus vite que le cours
# (multiple comprime = pas cher), tout en etant une bonne societe (gate qualite).
from bisect import bisect_right

QUALITY_CONFIG = {
    # Seuils alignes sur la methode AQRP (Dividend King)
    'gate': {
        'minRoe': 0.15,               # DK : un bon ROE est > 15 %
        'minRoic': 0.15,              # DK : ROIC > 15 % = ratio n°1 (la ou l'EBIT est pertinent ; financieres exemptees)
        'maxNetDebtToEbitda': 3.0,    # DK : dette/EBITDA < 3 (< 2 ideal, > 3 danger)
        'minNetMargin': 0.10,         # DK : marge nette > 20 % (10 % pour produits physiques) -> plancher 10 %
        'minRevCagr': 0.10,           # DK : croissance CA REGULIERE >= 10 %/an (moyenne annualisee ~4-5 ans, repli YoY)
        'requirePositiveFcf': True,   # free cash-flow positif
        'requirePositiveEarnings': True,  # benefices en croissance (pas en declin structurel)
        'minMarketCap': 5e9,
    },
    # Poids du score : VALORISATION (pas cher) + dividende + GARP (croissance de qualite a prix raisonnable).
    # La brique GARP evite le biais pur "value" qui remonte les cycliques optiquement bon marche : elle
    # credite la croissance durable + les marges + le ROE, facon compounder de qualite (esprit Dividend King).
    'weights': {'peg': 0.20, 'gap': 0.22, 'fcfYield': 0.12, 'fwdPe': 0.14, 'dividend': 0.08, 'garp': 0.24},
    # Dividende : rendement sain valorise ; piege (rendement trop eleve) et payout non soutenable ecartes du bonus
    'divTrapYield': 0.09,     # rendement > 9% = piege probable
    'divPayoutIdeal': 0.40,   # DK : payout < 40 % = ideal/durable
    'divPayoutMax': 0.60,     # DK : 40-60 % acceptable, > 60 % = tension
    # Bandes de notation sur le score de valorisation 0-100 (au sein des survivants qualite)
    'ratingBands': [(80, 'Achat fort'), (60, 'Achat'), (40, 'Neutre'), (0, 'Surévaluée')],
    'minSectorBucket': 8,
    'topN': 60,
}


def _num(x):
    return x if isinstance(x, (int, float)) and x == x else None


def _growth(t):
    # croissance du CA privilegiee = moyenne annualisee sur l'historique (revCagr), repli sur le YoY
    rc = _num(t.get('revCagr'))
    return rc if rc is not None else _num(t.get('revenueGrowthYoY'))


def passes_quality(t, cfg=QUALITY_CONFIG):
    g = cfg['gate']
    mc = _num(t.get('marketCap'))
    if mc is None or mc < g['minMarketCap']:
        return False, 'trop petite'
    roe = _num(t.get('roe'))
    if roe is None or roe < g['minRoe']:
        return False, 'rentabilite insuffisante (ROE)'
    # ROIC (ratio n°1 DK) : > 15 % la ou il est pertinent (EBIT dispo). Les financieres (ROIC
    # approche via le resultat net) sont jugees sur le ROE, pas le ROIC -> exemptees du gate.
    roic = _num(t.get('roic'))
    if roic is not None and not t.get('roicApprox') and roic < g.get('minRoic', 0.15):
        return False, 'ROIC insuffisant (< 15 %)'
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
    nm = _num(t.get('netMargin'))
    if nm is not None and nm < g.get('minNetMargin', 0):
        return False, 'marge nette trop faible'
    # Croissance du CA facon DK : REGULIERE >= 10 %/an, mesuree sur la moyenne annualisee de
    # l'historique (~4-5 ans, revCagr) ; repli sur le YoY si l'historique manque.
    growth = _growth(t)
    if growth is not None and growth < g.get('minRevCagr', 0.10):
        return False, 'croissance CA (moyenne) trop faible'
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


def _div_signal(t, cfg):
    # Dividende sain valorise ; sans dividende = non note (neutre) ; piege/payout intenable = ecarte du bonus.
    y = _num(t.get('dividendYield'))
    if y is None or y <= 0:
        return None
    if y > cfg['divTrapYield']:   # rendement trop eleve = piege probable
        return None
    # Soutenabilite du payout facon DK : < 40% ideal, 40-60% acceptable, > 60% tension.
    p = _num(t.get('payoutRatio'))
    if p is None or p < cfg['divPayoutIdeal']:
        sust = 1.0
    elif p < cfg['divPayoutMax']:
        sust = 0.6
    elif p < 1.0:
        sust = 0.25
    else:
        sust = 0.1
    # Bonus DK : DIVIDENDE CROISSANT (sa signature). Streak long = business fiable.
    streak = _num(t.get('divStreak'))
    if streak is None:
        growth = 1.0                                   # historique inconnu -> neutre
    elif streak >= 10:
        growth = 1.3
    elif streak >= 5:
        growth = 1.15
    elif streak >= 3:
        growth = 1.0
    else:
        growth = 0.7                                   # dividende qui ne croit pas -> penalise
    return y * sust * growth


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
        'div': _dist(survivors, lambda t: _div_signal(t, cfg)),
        # GARP : croissance REGULIERE du CA (moyenne annualisee), marge nette, ROE, ROIC (ratio n°1 DK)
        # + rachats d'actions (baisse du nombre d'actions = critere DK)
        'grw': _dist(survivors, _growth),
        'nm': _dist(survivors, lambda t: _num(t.get('netMargin'))),
        'roe': _dist(survivors, lambda t: _num(t.get('roe'))),
        'roic': _dist(survivors, lambda t: _num(t.get('roic')) if _num(t.get('roic')) is not None else _num(t.get('roa'))),
        'buy': _dist(survivors, lambda t: (-_num(t.get('sharesChange'))) if _num(t.get('sharesChange')) is not None else None),
    }
    w = cfg['weights']

    def garp_pct(t):
        # moyenne des percentiles dispo : croissance CA (moyenne) + marge nette + ROE + ROIC + rachats
        sc = _num(t.get('sharesChange'))
        ce = _num(t.get('roic')) if _num(t.get('roic')) is not None else _num(t.get('roa'))
        ps = [p for p in (_pct(dists['grw'], _growth(t)),
                          _pct(dists['nm'], _num(t.get('netMargin'))),
                          _pct(dists['roe'], _num(t.get('roe'))),
                          _pct(dists['roic'], ce),
                          _pct(dists['buy'], (-sc) if sc is not None else None)) if p is not None]
        return (sum(ps) / len(ps)) if ps else None

    scored = []
    for t in survivors:
        comps = [
            (_pct(dists['peg'], peg_signal(t)), w['peg']),
            (_pct(dists['gap'], _num(t.get('gap'))), w['gap']),
            (_pct(dists['fcf'], _num(t.get('fcfYield'))), w['fcfYield']),
            (_pct(dists['fpe'], fwdpe_signal(t)), w['fwdPe']),
            (_pct(dists['div'], _div_signal(t, cfg)), w['dividend']),
            (garp_pct(t), w['garp']),
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
                'roe': t.get('roe'), 'roa': t.get('roa'), 'roic': t.get('roic'), 'roicApprox': t.get('roicApprox'),
                'grossMargin': t.get('grossMargin'), 'netMargin': t.get('netMargin'),
                'fcfYield': t.get('fcfYield'), 'revenueGrowthYoY': t.get('revenueGrowthYoY'),
                'revCagr': t.get('revCagr'), 'revYears': t.get('revYears'), 'fcfCagr': t.get('fcfCagr'),
                'sharesChange': t.get('sharesChange'), 'buyback': t.get('buyback'),
                'earningsGrowthYoY': t.get('earningsGrowthYoY'),
                'dividendYield': t.get('dividendYield'), 'payoutRatio': t.get('payoutRatio'),
                'divStreak': t.get('divStreak'), 'divCagr': t.get('divCagr'), 'divGrowing': t.get('divGrowing'),
                'website': t.get('website'),
            },
        })

    # tri : Achat fort d'abord (score de valo decroissant)
    scored.sort(key=lambda x: x['valuationScore'], reverse=True)
    return {'generatedFrom': len(universe), 'survivors': len(survivors),
            'rejectedCount': len(rejected), 'top': scored[:cfg['topN']], 'all': scored}
