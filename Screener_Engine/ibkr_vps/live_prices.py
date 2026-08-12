#!/usr/bin/env python3
# live_prices.py - cours "temps reel" des positions du dashboard.
# Lit stocks/screener/myPositions (les tickers saisis dans le dashboard), recupere le dernier
# cours de chacun via Yahoo (cote VPS, pas de blocage CORS), et pousse dans
# stocks/screener/livePrices. A planifier toutes les ~15 min pendant les heures de marche.
#
# Env : FIREBASE_DB_URL (+ FIREBASE_DB_SECRET ou GOOGLE_APPLICATION_CREDENTIALS si regles fermees)
import os
import time
from datetime import datetime, timezone

from yahoo import Yahoo
from firebase_push import push, get


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def main():
    db = os.environ.get('FIREBASE_DB_URL')
    if not db:
        print('FIREBASE_DB_URL manquant'); return
    pos = get(db, 'stocks/screener/myPositions')
    tickers = []
    if isinstance(pos, list):
        tickers = [p.get('ticker') for p in pos if isinstance(p, dict) and p.get('ticker')]
    elif isinstance(pos, dict):
        tickers = [p.get('ticker') for p in pos.values() if isinstance(p, dict) and p.get('ticker')]
    tickers = sorted({str(t).upper().strip() for t in tickers if t})
    if not tickers:
        print('Aucune position a suivre.'); return
    y = Yahoo()
    prices = []   # liste (le ticker peut contenir un '.', interdit comme cle Firebase -> on le met DANS l'objet)
    for t in tickers:
        q = y.live_quote(t)
        if q and q.get('price') is not None:
            prices.append({'ticker': t, 'price': q['price'], 'changePct': q.get('changePct'), 'exchange': q.get('exchange')})
        time.sleep(0.3)
    push(db, 'stocks/screener/livePrices', {'generatedAt': _now_iso(), 'prices': prices})
    print(f'Cours live pousses : {len(prices)}/{len(tickers)} ({", ".join(p["ticker"] for p in prices)})')


if __name__ == '__main__':
    main()
