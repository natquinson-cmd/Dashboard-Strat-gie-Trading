# Test du portage Python du scoring (screen.py). Aucun reseau requis.
#   python Screener_Engine/ibkr_vps/test_screen.py
from screen import rank_universe, passes_guards, DEFAULT_CONFIG

p = f = 0


def ok(cond, msg):
    global p, f
    if cond:
        p += 1
    else:
        f += 1
        print('  ECHEC:', msg)


U = [
    {'symbol': 'GROW', 'name': 'GrowthCo', 'sector': 'Technology', 'price': 100, 'marketCap': 20e9, 'avgVolume': 3e6,
     'priceAvg50': 92, 'priceAvg200': 80, 'yearHigh': 105, 'perf6m': 0.35, 'perf12m': 0.7,
     'revenueGrowthYoY': 0.55, 'revenueCAGR3y': 0.45, 'epsGrowthYoY': 0.6, 'grossMargin': 0.75, 'roe': 0.25, 'eps': 3.2,
     'operatingMargin': 0.15, 'sharesGrowth': 0.03, 'netDebtToEbitda': 0.5},
    {'symbol': 'SLOW', 'name': 'SlowMo', 'sector': 'Technology', 'price': 40, 'marketCap': 8e9, 'avgVolume': 1e6,
     'priceAvg50': 45, 'priceAvg200': 50, 'yearHigh': 70, 'perf6m': -0.2, 'perf12m': -0.1,
     'revenueGrowthYoY': 0.28, 'revenueCAGR3y': 0.25, 'epsGrowthYoY': 0.2, 'grossMargin': 0.65, 'roe': 0.18, 'eps': 1.1,
     'operatingMargin': 0.1, 'sharesGrowth': 0.02, 'netDebtToEbitda': 1},
    {'symbol': 'PENNY', 'name': 'PennyJunk', 'sector': 'Healthcare', 'price': 2, 'marketCap': 500e6, 'avgVolume': 4e6,
     'priceAvg50': 1.8, 'priceAvg200': 1.5, 'yearHigh': 3, 'revenueGrowthYoY': 0.8, 'grossMargin': 0.55, 'eps': -0.4,
     'operatingMargin': -0.3, 'sharesGrowth': 0.2},
    {'symbol': 'TINY', 'name': 'TinyCap', 'sector': 'Technology', 'price': 12, 'marketCap': 120e6, 'avgVolume': 2e5,
     'priceAvg50': 11, 'priceAvg200': 10, 'yearHigh': 13, 'revenueGrowthYoY': 0.7, 'grossMargin': 0.6, 'eps': 0.8},
    {'symbol': 'MATURE', 'name': 'MatureInc', 'sector': 'Industrials', 'price': 80, 'marketCap': 30e9, 'avgVolume': 2e6,
     'priceAvg50': 79, 'priceAvg200': 75, 'yearHigh': 85, 'revenueGrowthYoY': 0.06, 'grossMargin': 0.35, 'roe': 0.22, 'eps': 4,
     'operatingMargin': 0.18, 'sharesGrowth': 0.0, 'netDebtToEbitda': 2},
    {'symbol': 'HYPER', 'name': 'HyperSaaS', 'sector': 'Technology', 'price': 60, 'marketCap': 5e9, 'avgVolume': 1.5e6,
     'priceAvg50': 55, 'priceAvg200': 48, 'yearHigh': 62, 'revenueGrowthYoY': 0.9, 'grossMargin': 0.8, 'eps': -0.5,
     'operatingMargin': -0.05, 'sharesGrowth': 0.06},
    {'symbol': 'BURN', 'name': 'CashBurner', 'sector': 'Consumer', 'price': 25, 'marketCap': 2e9, 'avgVolume': 8e5,
     'priceAvg50': 24, 'priceAvg200': 20, 'yearHigh': 30, 'revenueGrowthYoY': 0.5, 'grossMargin': 0.25, 'eps': -1.2,
     'operatingMargin': -0.4, 'sharesGrowth': 0.15},
    {'symbol': 'DILUT', 'name': 'DilutionCorp', 'sector': 'Technology', 'price': 30, 'marketCap': 3e9, 'avgVolume': 1e6,
     'priceAvg50': 29, 'priceAvg200': 26, 'yearHigh': 33, 'revenueGrowthYoY': 0.6, 'grossMargin': 0.7, 'epsGrowthYoY': 0.3,
     'roe': 0.16, 'eps': 0.5, 'operatingMargin': 0.05, 'sharesGrowth': 0.3},
]

res = rank_universe(U, DEFAULT_CONFIG)
kept = {r['symbol'] for r in res['all']}
by = {r['symbol']: r for r in res['all']}
print('survivants=%d rejetes=%d' % (res['survivors'], res['rejectedCount']))
print('Classement :', '  '.join('%s(%s)' % (r['symbol'], r['score']) for r in res['all']))

ok('PENNY' not in kept, 'PENNY exclu')
ok('TINY' not in kept, 'TINY exclu')
ok('MATURE' not in kept, 'MATURE exclu (gate growth)')
ok('BURN' not in kept, 'BURN exclu')
ok('DILUT' not in kept, 'DILUT exclu')
ok('GROW' in kept and 'HYPER' in kept and 'SLOW' in kept, 'GROW/HYPER/SLOW retenus')
ok(by['GROW']['score'] > by['SLOW']['score'], 'GROW > SLOW')
ok(by['SLOW']['metrics']['uptrend'] is False, 'SLOW hors-tendance')
ok(by['GROW']['metrics']['uptrend'] is True, 'GROW en tendance')
ok(all(res['all'][i - 1]['score'] >= res['all'][i]['score'] for i in range(1, len(res['all']))), 'classement decroissant')
ok('CA+40%' in by['GROW']['flags'], 'GROW porte CA+40%')
ok('pré-cassure' in by['GROW']['flags'], 'GROW en pré-cassure (prix pres du plus-haut)')
ok(all(0 <= r['score'] <= 100 for r in res['all']), 'scores bornes 0-100')
ok(passes_guards(U[0])[0] is True, 'guards(GROW) ok')
ok(passes_guards(U[2])[0] is False, 'guards(PENNY) echoue')

print('%d OK, %d echec(s)' % (p, f))
raise SystemExit(1 if f else 0)
