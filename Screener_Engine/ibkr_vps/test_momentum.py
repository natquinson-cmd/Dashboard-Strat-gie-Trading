# Test local de momentum.py (aucune connexion IBKR requise).
#   python Screener_Engine/ibkr_vps/test_momentum.py
from momentum import compute_momentum, momentum_score

pass_n = fail_n = 0


def ok(cond, msg):
    global pass_n, fail_n
    if cond:
        pass_n += 1
    else:
        fail_n += 1
        print('  ECHEC:', msg)


def make_bars(start, step, n, vol=1_000_000):
    """Serie lineaire simple close=start+step*i, high=close*1.01, low=close*0.99."""
    bars = []
    p = start
    for i in range(n):
        p = start + step * i
        bars.append({'close': p, 'high': p * 1.01, 'low': p * 0.99, 'volume': vol})
    return bars


# 1) Trop court -> None
ok(compute_momentum(make_bars(10, 0.1, 20)) is None, 'moins de 30 barres -> None')

# 2) Tendance haussiere reguliere sur 260 barres
up = make_bars(50, 0.5, 260)  # de 50 a ~179.5
mu = compute_momentum(up)
ok(mu is not None, 'momentum calcule sur 260 barres')
ok(mu['uptrend'] is True, 'serie croissante -> uptrend True')
ok(mu['vsMa200'] > 0, 'prix au-dessus de la MM200')
ok(mu['perf6m'] is not None and mu['perf6m'] > 0, 'perf 6 mois positive')
ok(mu['distToHigh'] is not None and -0.05 < mu['distToHigh'] <= 0, 'proche du plus-haut 52s (au sommet)')
ok(mu['ma50'] > mu['ma200'], 'MM50 > MM200 en tendance haussiere')

# 3) Tendance baissiere -> pas uptrend, score bas
down = make_bars(200, -0.5, 260)  # de 200 a ~70.5
md = compute_momentum(down)
ok(md['uptrend'] is False, 'serie decroissante -> uptrend False')
ok(md['vsMa200'] < 0, 'prix sous la MM200 en baisse')

# 4) Scores
su = momentum_score(mu)
sd = momentum_score(md)
ok(su is not None and sd is not None, 'scores calcules')
ok(su > sd, 'le titre haussier score plus haut que le baissier')
ok(0 <= su <= 100 and 0 <= sd <= 100, 'scores bornes 0-100')
ok(momentum_score(None) is None, 'score(None) -> None')

# 5) ATR present
ok(mu['atr14'] is not None and mu['atrPct'] is not None, 'ATR14 calcule')
ok(mu['dollarVolume'] is not None and mu['dollarVolume'] > 0, 'dollar volume calcule')

print(f"\nmomentum : haussier score={su}  baissier score={sd}")
print(f"{pass_n} OK, {fail_n} echec(s)")
raise SystemExit(1 if fail_n else 0)
