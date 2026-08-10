#!/usr/bin/env python3
# run.py — orchestrateur de la couche IBKR (VPS).
# 1) recupere les candidates du screener FMP (Worker Cloudflare /latest)
# 2) enrichit le top N avec IBKR : momentum (barres historiques), tradabilite
# 3) blende le momentum IBKR dans le score fondamental FMP, re-classe
# 4) recupere positions + compte live IBKR
# 5) pousse le tout dans Firebase (lu par le dashboard)
#
# Mode --mock : saute IBKR (aucune passerelle requise) pour valider la chaine + Firebase + dashboard.
#
# Config via variables d'environnement :
#   WORKER_URL           URL du Worker screener (ex https://stock-screener.xxx.workers.dev)
#   FIREBASE_DB_URL      https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com
#   FIREBASE_DB_SECRET   (ou GOOGLE_APPLICATION_CREDENTIALS)
#   IBKR_HOST/IBKR_PORT/IBKR_CLIENT_ID   (defaut 127.0.0.1 / 4002 / 17)
#   TOP_N                nb de candidates enrichies (defaut 40)
#   BLEND_IBKR           poids du momentum IBKR dans le score final 0..1 (defaut 0.4)
import json
import os
import sys
import urllib.request

TOP_N = int(os.environ.get('TOP_N', '40'))
# Poids du momentum IBKR dans le score final. Faible par defaut : la strategie vise le
# PRE-CASSURE (mene par les fondamentaux FMP), on ne veut pas re-tilter vers le momentum.
# Mets 0 pour un classement 100 % fondamental (IBKR ne sert alors qu'aux data live/positions).
BLEND = float(os.environ.get('BLEND_IBKR', '0.15'))
MOCK = '--mock' in sys.argv


def fetch_candidates():
    url = os.environ.get('WORKER_URL', '').rstrip('/')
    if not url:
        raise SystemExit('WORKER_URL manquant (URL du Worker screener FMP).')
    with urllib.request.urlopen(url + '/latest', timeout=20) as r:
        data = json.loads(r.read())
    return data


def blended_score(fmp_score, ibkr_mom_score):
    if ibkr_mom_score is None:
        return fmp_score
    return round((1 - BLEND) * fmp_score + BLEND * ibkr_mom_score, 1)


def enrich_with_ibkr(candidates):
    from ibkr_client import IBKRClient
    from momentum import momentum_score
    host = os.environ.get('IBKR_HOST', '127.0.0.1')
    port = int(os.environ.get('IBKR_PORT', '4002'))
    cid = int(os.environ.get('IBKR_CLIENT_ID', '17'))
    positions, account = [], {}
    with IBKRClient(host, port, cid, readonly=True) as ib:
        positions = ib.positions()
        account = ib.account_summary()
        for c in candidates:
            sym = c.get('symbol')
            m = ib.momentum(sym)
            c['ibkr'] = m
            c['ibkrMomentumScore'] = momentum_score(m)
            c['tradableIBKR'] = ib.is_tradable(sym)
            c['scoreFmp'] = c.get('score')
            c['score'] = blended_score(c.get('score') or 0, c['ibkrMomentumScore'])
            print(f"  {sym:<6} fmp={c['scoreFmp']} ibkr={c['ibkrMomentumScore']} -> {c['score']}  tradable={c['tradableIBKR']}")
    return candidates, positions, account


def enrich_mock(candidates):
    # Simule un momentum IBKR deterministe pour valider la chaine sans passerelle.
    from momentum import momentum_score
    for i, c in enumerate(candidates):
        m = c.get('metrics') or {}
        v200 = None
        if m.get('price') and m.get('priceAvg200'):
            v200 = m['price'] / m['priceAvg200'] - 1
        fake = {'vsMa200': v200, 'distToHigh': m.get('distToHigh'),
                'perf6m': None, 'perf12m': None, 'uptrend': bool(m.get('uptrend'))}
        c['ibkr'] = fake
        c['ibkrMomentumScore'] = momentum_score(fake)
        c['tradableIBKR'] = True
        c['scoreFmp'] = c.get('score')
        c['score'] = blended_score(c.get('score') or 0, c['ibkrMomentumScore'])
    positions = [{'symbol': 'DEMO', 'position': 10, 'avgCost': 100, 'marketPrice': 118,
                  'marketValue': 1180, 'unrealizedPnl': 180, 'currency': 'USD', 'secType': 'STK'}]
    return candidates, positions, {'NetLiquidation': 12345.6}


def main():
    data = fetch_candidates()
    top = (data.get('top') or [])[:TOP_N]
    print(f'{len(top)} candidates recuperees du screener FMP (mode={"MOCK" if MOCK else "IBKR"})')
    if not top:
        raise SystemExit('Aucune candidate : lance le screener FMP (/run) d\'abord.')

    if MOCK:
        top, positions, account = enrich_mock(top)
    else:
        top, positions, account = enrich_with_ibkr(top)

    top.sort(key=lambda c: c.get('score') or 0, reverse=True)

    payload = {
        'generatedAt': _now_iso(),
        'source': 'ibkr_vps' + ('_mock' if MOCK else ''),
        'summary': {**(data.get('summary') or {}), 'enrichedByIBKR': not MOCK, 'topEnriched': len(top)},
        'top': top,
    }

    db_url = os.environ.get('FIREBASE_DB_URL')
    if not db_url:
        print('\nFIREBASE_DB_URL manquant -> pas de push. Apercu du classement :')
        for c in top[:10]:
            print(f"  {c['symbol']:<6} {c['score']}")
        return
    from firebase_push import push
    push(db_url, 'stocks/screener/latest', payload)
    push(db_url, 'stocks/screener/positions', {'generatedAt': payload['generatedAt'], 'account': account, 'positions': positions})
    print(f'\nPousse dans Firebase : stocks/screener/latest ({len(top)} lignes) + positions ({len(positions)}).')


def _now_iso():
    # os.popen evite d'importer datetime (interdit dans certains bacs a sable) ; ici standard OK.
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


if __name__ == '__main__':
    main()
