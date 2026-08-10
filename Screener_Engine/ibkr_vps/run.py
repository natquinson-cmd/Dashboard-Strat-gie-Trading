#!/usr/bin/env python3
# run.py — orchestrateur du screener (Option C : tout sur le VPS, source gratuite Yahoo).
# 1) Yahoo screener : univers US filtre par croissance + capitalisation (cote serveur)
# 2) Yahoo quoteSummary : enrichit chaque ticker (fondamentaux + prix + MM50/200 + 52s-haut)
# 3) scoring PRE-CASSURE (screen.py) -> classement
# 4) IBKR (optionnel, si ENABLE_IBKR=true) : momentum precis sur le top + positions live
# 5) push Firebase (stocks/screener/latest + /positions), lu par le dashboard
#
# Flags : --no-push (calcule + affiche, ne pousse pas) | --limit N (cap enrichissement)
#
# Env : FIREBASE_DB_URL, FIREBASE_DB_SECRET (ou GOOGLE_APPLICATION_CREDENTIALS)
#       SCREEN_MIN_REVGROWTH (0.25) SCREEN_MIN_MCAP (300000000) UNIVERSE_LIMIT (250) MAX_TOTAL (500) TOP_N (50)
#       ENABLE_IBKR (false) IBKR_HOST IBKR_PORT IBKR_CLIENT_ID BLEND_IBKR (0.15)
import os
import sys

from yahoo import Yahoo
from screen import rank_universe, DEFAULT_CONFIG

NO_PUSH = '--no-push' in sys.argv
WATCH = '--watch' in sys.argv   # relance a chaque changement de config depuis le dashboard
LIMIT_OVERRIDE = next((int(a.split('=')[1]) for a in sys.argv if a.startswith('--limit=')), None)

MIN_REVGROWTH = float(os.environ.get('SCREEN_MIN_REVGROWTH', '0.30'))
# Fourchette de capitalisation : on vise les SMALL/MID caps "pretes a exploser" et on EXCLUT
# les mega caps (qui ne montent que de quelques %). Baisse MAX_MCAP pour cibler plus petit.
MIN_MCAP = float(os.environ.get('SCREEN_MIN_MCAP', '500000000'))
MAX_MCAP = float(os.environ.get('SCREEN_MAX_MCAP', '10000000000'))
# Borne HAUTE de croissance appliquee EN PYTHON (le champ croissance du screener Yahoo devient
# incoherent avec deux bornes) : au-dela = croissance depuis une base quasi nulle = distorsion.
MAX_REVGROWTH = float(os.environ.get('SCREEN_MAX_REVGROWTH', '3.0'))
UNIVERSE_LIMIT = LIMIT_OVERRIDE or int(os.environ.get('UNIVERSE_LIMIT', '300'))
MAX_TOTAL = int(os.environ.get('MAX_TOTAL', '1000'))
TOP_N = int(os.environ.get('TOP_N', '50'))
ENABLE_IBKR = os.environ.get('ENABLE_IBKR', 'false') == 'true'
BLEND = float(os.environ.get('BLEND_IBKR', '0.15'))


# Places boursieres US majeures (on exclut l'OTC/Pink et les tickers etrangers = ~560 titres de junk)
MAJOR_EXCH = {'NMS', 'NYQ', 'NGM', 'NCM', 'ASE', 'PCX', 'BATS'}


def screen_universe():
    y = Yahoo()
    # UNE seule borne de croissance cote screener (le champ devient incoherent avec deux bornes).
    # Fourchette de cap pour cibler small/mid. Tri par cap CROISSANTE = les plus petites d'abord
    # (plus de potentiel). Le filtrage fin (marges, BPA, pre-cassure) se fait en Python.
    operands = [
        ('gt', 'quarterlyrevenuegrowth.quarterly', MIN_REVGROWTH),
        ('gt', 'intradaymarketcap', MIN_MCAP),
        ('lt', 'intradaymarketcap', MAX_MCAP),
        ('eq', 'region', 'us'),
    ]
    rows = y.screen(operands, size=250, sort_field='intradaymarketcap', sort_type='asc', max_total=MAX_TOTAL)
    rows = [t for t in rows if t.get('exchange') in MAJOR_EXCH]   # exclut l'OTC/etranger
    print(f'Yahoo screener : {len(rows)} titres US small/mid ({MIN_MCAP/1e6:.0f}M-{MAX_MCAP/1e9:.0f}Md$, CA YoY>{MIN_REVGROWTH:.0%})')
    return y, [t['symbol'] for t in rows]


def ibkr_enrich(top):
    from ibkr_client import IBKRClient
    from momentum import momentum_score
    host = os.environ.get('IBKR_HOST', '127.0.0.1')
    port = int(os.environ.get('IBKR_PORT', '4001'))
    cid = int(os.environ.get('IBKR_CLIENT_ID', '17'))
    positions, account = [], {}
    with IBKRClient(host, port, cid, readonly=True) as ib:
        positions = ib.positions()
        account = ib.account_summary()
        for c in top:
            m = ib.momentum(c['symbol'])
            c['ibkr'] = m
            c['ibkrMomentumScore'] = momentum_score(m)
            c['tradableIBKR'] = ib.is_tradable(c['symbol'])
            c['scoreScreen'] = c['score']
            if c['ibkrMomentumScore'] is not None:
                c['score'] = round((1 - BLEND) * c['score'] + BLEND * c['ibkrMomentumScore'], 1)
    return positions, account


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def apply_firebase_config():
    """Override les defauts avec la config posee par le dashboard (sliders) -> stocks/screener/config."""
    global MIN_MCAP, MAX_MCAP, MIN_REVGROWTH, MAX_REVGROWTH, UNIVERSE_LIMIT, TOP_N
    db = os.environ.get('FIREBASE_DB_URL')
    if not db:
        return
    from firebase_push import get
    cfg = get(db, 'stocks/screener/config')
    if not isinstance(cfg, dict):
        return

    def f(k, cur, cast=float):
        try:
            return cast(cfg[k]) if cfg.get(k) is not None else cur
        except Exception:
            return cur

    MIN_MCAP = f('minMcap', MIN_MCAP)
    MAX_MCAP = f('maxMcap', MAX_MCAP)
    MIN_REVGROWTH = f('minRevGrowth', MIN_REVGROWTH)
    MAX_REVGROWTH = f('maxRevGrowth', MAX_REVGROWTH)
    if not LIMIT_OVERRIDE:
        UNIVERSE_LIMIT = f('universeLimit', UNIVERSE_LIMIT, int)
    TOP_N = f('topN', TOP_N, int)
    print(f'Config dashboard : cap {MIN_MCAP/1e6:.0f}M-{MAX_MCAP/1e9:.1f}Md, CA>{MIN_REVGROWTH:.0%}, analyses={UNIVERSE_LIMIT}, top={TOP_N}')


def main():
    apply_firebase_config()
    DEFAULT_CONFIG['topN'] = TOP_N
    y, symbols = screen_universe()
    if not symbols:
        raise SystemExit('Screener vide (Yahoo bloque ou filtres trop stricts).')

    symbols = symbols[:UNIVERSE_LIMIT]
    print(f'Enrichissement de {len(symbols)} titres via Yahoo quoteSummary...')
    records = y.enrich(symbols)
    # ecarte les distorsions de base basse (croissance absurde type biotech +5000 %)
    records = [r for r in records if r.get('revenueGrowthYoY') is None or r['revenueGrowthYoY'] <= MAX_REVGROWTH]
    print(f'{len(records)} enrichis')

    result = rank_universe(records, DEFAULT_CONFIG)
    top = result['top']
    print(f"survivants={result['survivors']}  top={len(top)}")

    positions, account, source = [], {}, 'yahoo_vps'
    if ENABLE_IBKR:
        try:
            positions, account = ibkr_enrich(top)
            top.sort(key=lambda c: c.get('score') or 0, reverse=True)
            source = 'ibkr_vps'
            print(f'IBKR : {len(positions)} positions, top re-classe avec momentum')
        except Exception as e:
            print(f'IBKR indisponible ({e}) -> classement Yahoo seul')

    payload = {
        'generatedAt': _now_iso(), 'source': source,
        'summary': {'universe': len(symbols), 'enriched': len(records),
                    'survivors': result['survivors'], 'topEnriched': len(top),
                    'coverage': round(len(records) / max(1, len(symbols)) * 100),
                    'enrichedByIBKR': ENABLE_IBKR and source == 'ibkr_vps'},
        'top': top,
    }

    if NO_PUSH or not os.environ.get('FIREBASE_DB_URL'):
        print('\n(pas de push) Top 15 :')
        for c in top[:15]:
            m = c['metrics']
            print(f"  {c['symbol']:<6} {c['score']:<5} CA={_p(m.get('revenueGrowthYoY'))} marge={_p(m.get('grossMargin'))} 52s={_p(m.get('distToHigh'))} {' '.join(c['flags'][:3])}")
        return

    from firebase_push import push
    db = os.environ['FIREBASE_DB_URL']
    push(db, 'stocks/screener/latest', payload)
    push(db, 'stocks/screener/positions', {'generatedAt': payload['generatedAt'], 'account': account, 'positions': positions})
    print(f"\nPousse dans Firebase : stocks/screener/latest ({len(top)}) + positions ({len(positions)}).")


def _p(x):
    return '-' if x is None else ('%+.0f%%' % (x * 100))


if __name__ == '__main__':
    if WATCH:
        import time
        _db = os.environ.get('FIREBASE_DB_URL')
        from firebase_push import get as _get

        def _token():
            c = _get(_db, 'stocks/screener/config') if _db else None
            return c.get('runRequested') if isinstance(c, dict) else None

        print('Mode --watch actif : relance a chaque "Appliquer" depuis le dashboard (Ctrl+C pour arreter).')
        _last = _token()
        main()
        while True:
            time.sleep(20)
            _t = _token()
            if _t is not None and _t != _last:
                _last = _t
                print(f'--- config modifiee (runRequested={_t}) -> relance ---')
                try:
                    main()
                except Exception as _e:
                    print('run echoue:', _e)
    else:
        main()
