# Test du scoring qualite-valorisation (quality.py). Aucun reseau.
#   python Screener_Engine/ibkr_vps/test_quality.py
from quality import rate_universe, passes_quality, QUALITY_CONFIG

p = f = 0


def ok(cond, msg):
    global p, f
    if cond:
        p += 1
    else:
        f += 1
        print('  ECHEC:', msg)


base = dict(sector='Technology', marketCap=50e9, roe=0.25, freeCashflow=5e9, earningsGrowthYoY=0.2,
            grossMargin=0.6, netDebtToEbitda=1.0, price=100, revenueGrowthYoY=0.15)

U = [
    # Pas cher : PEG bas, benefices >> cours, gros FCF yield, PE fwd bas -> Achat fort
    {**base, 'symbol': 'CHEAP', 'name': 'CheapQuality', 'peg': 0.8, 'forwardPE': 12, 'earningsCAGR': 0.35,
     'priceCAGR': 0.10, 'gap': 0.25, 'fcfYield': 0.07, 'trailingPE': 15},
    # Correct : valo neutre
    {**base, 'symbol': 'FAIR', 'name': 'FairCo', 'peg': 1.6, 'forwardPE': 22, 'earningsCAGR': 0.15,
     'priceCAGR': 0.14, 'gap': 0.01, 'fcfYield': 0.035, 'trailingPE': 25},
    # Cher : cours parti devant les benefices, PEG haut, PE eleve -> Surevaluee
    {**base, 'symbol': 'RICH', 'name': 'RichCo', 'peg': 3.2, 'forwardPE': 45, 'earningsCAGR': 0.10,
     'priceCAGR': 0.35, 'gap': -0.25, 'fcfYield': 0.012, 'trailingPE': 55},
    # Milieu haut
    {**base, 'symbol': 'GOOD', 'name': 'GoodValue', 'peg': 1.1, 'forwardPE': 16, 'earningsCAGR': 0.25,
     'priceCAGR': 0.16, 'gap': 0.09, 'fcfYield': 0.05, 'trailingPE': 19},
    # Echoue au gate qualite : ROE trop faible
    {**base, 'symbol': 'LOWQ', 'name': 'LowQuality', 'roe': 0.05, 'peg': 0.5, 'forwardPE': 8,
     'earningsCAGR': 0.3, 'priceCAGR': 0.1, 'gap': 0.2, 'fcfYield': 0.08},
    # Echoue : trop petite
    {**base, 'symbol': 'TINY', 'name': 'TinyCo', 'marketCap': 1e9, 'peg': 0.7, 'forwardPE': 10,
     'earningsCAGR': 0.3, 'priceCAGR': 0.1, 'gap': 0.2, 'fcfYield': 0.08},
    # Echoue : benefices en declin + FCF negatif
    {**base, 'symbol': 'DECL', 'name': 'DecliningCo', 'earningsGrowthYoY': -0.2, 'earningsCAGR': -0.15,
     'freeCashflow': -2e9, 'peg': 0.4, 'forwardPE': 9, 'priceCAGR': -0.3, 'gap': 0.15, 'fcfYield': None},
]

res = rate_universe(U, QUALITY_CONFIG)
by = {r['symbol']: r for r in res['all']}
kept = set(by)
print('survivants=%d rejetes=%d' % (res['survivors'], res['rejectedCount']))
print('Notes :', '  '.join('%s=%s(%s)' % (r['symbol'], r['rating'], r['valuationScore']) for r in res['all']))

ok('LOWQ' not in kept, 'LOWQ exclu (ROE faible)')
ok('TINY' not in kept, 'TINY exclu (trop petite)')
ok('DECL' not in kept, 'DECL exclu (benefices en declin + FCF<0)')
ok({'CHEAP', 'FAIR', 'RICH', 'GOOD'} <= kept, 'les 4 societes de qualite retenues')
ok(by['CHEAP']['valuationScore'] > by['RICH']['valuationScore'], 'CHEAP mieux note que RICH')
ok(by['CHEAP']['rating'] == 'Achat fort', 'CHEAP = Achat fort (obtenu: %s)' % by.get('CHEAP', {}).get('rating'))
ok(by['RICH']['rating'] == 'Surévaluée', 'RICH = Surevaluee (obtenu: %s)' % by.get('RICH', {}).get('rating'))
ok(res['all'][0]['valuationScore'] >= res['all'][-1]['valuationScore'], 'trie du moins cher au plus cher')
ok(passes_quality(U[0])[0] is True and passes_quality(U[4])[0] is False, 'gate qualite coherent')

print('%d OK, %d echec(s)' % (p, f))
raise SystemExit(1 if f else 0)
