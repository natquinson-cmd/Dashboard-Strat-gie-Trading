#!/usr/bin/env python3
# live_prices.py - cours "temps reel" des positions du dashboard + instantane quotidien du portefeuille.
# 1) Lit stocks/screener/myPositions, recupere le dernier cours de chaque ticker via Yahoo
#    (cote VPS, pas de blocage CORS) et pousse dans stocks/screener/livePrices.
# 2) Calcule la valeur et le montant investi du portefeuille (en USD, conversion FX) et ecrit
#    un instantane du jour dans stocks/screener/positionsHistory/{YYYY-MM-DD} -> courbe + calendriers.
# A planifier toutes les ~15 min pendant les heures de marche (le dernier run du jour = cloture).
#
# Env : FIREBASE_DB_URL (+ FIREBASE_DB_SECRET ou GOOGLE_APPLICATION_CREDENTIALS si regles fermees)
import json
import os
import time
import urllib.request
from datetime import datetime, timezone

from yahoo import Yahoo
from firebase_push import push, get


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


# Meme table que le dashboard (SCR_EXCH_CCY) : devise de cotation par place boursiere.
EXCH_CCY = {'NMS': 'USD', 'NGM': 'USD', 'NCM': 'USD', 'NYQ': 'USD', 'ASE': 'USD', 'PCX': 'USD', 'BATS': 'USD',
            'PAR': 'EUR', 'AMS': 'EUR', 'GER': 'EUR', 'MIL': 'EUR', 'MCE': 'EUR', 'BRU': 'EUR', 'LIS': 'EUR',
            'HEL': 'EUR', 'VIE': 'EUR', 'LSE': 'GBX', 'EBS': 'CHF', 'VTX': 'CHF', 'STO': 'SEK', 'CPH': 'DKK'}


def _fx_rates():
    """Taux CCY par USD (open.er-api.com, gratuit, sans cle). {} si indispo."""
    try:
        with urllib.request.urlopen('https://open.er-api.com/v6/latest/USD', timeout=15) as r:
            j = json.loads(r.read())
            return j.get('rates') or {}
    except Exception:
        return {}


def _to_usd(v, exch, fx):
    """Convertit un cours natif (selon sa place) en USD. None si le taux manque."""
    ccy = EXCH_CCY.get(exch, 'USD')
    if ccy == 'USD':
        return v
    if ccy == 'GBX':                                   # LSE cote en pence
        return (v / 100) / fx['GBP'] if fx.get('GBP') else None
    return v / fx[ccy] if fx.get(ccy) else None


def _poslist(pos):
    if isinstance(pos, list):
        raw = pos
    elif isinstance(pos, dict):
        raw = list(pos.values())
    else:
        raw = []
    return [p for p in raw if isinstance(p, dict) and p.get('ticker')]


def main():
    db = os.environ.get('FIREBASE_DB_URL')
    if not db:
        print('FIREBASE_DB_URL manquant'); return
    poslist = _poslist(get(db, 'stocks/screener/myPositions'))
    tickers = sorted({str(p['ticker']).upper().strip() for p in poslist})
    if not tickers:
        print('Aucune position a suivre.'); return

    y = Yahoo()
    prices = []   # liste (le ticker peut contenir un '.', interdit comme cle Firebase -> on le met DANS l'objet)
    pmap = {}     # ticker -> (price, exchange) pour calculer la valeur du portefeuille
    for t in tickers:
        q = y.live_quote(t)
        if q and q.get('price') is not None:
            item = {'ticker': t, 'price': q['price'], 'changePct': q.get('changePct'), 'exchange': q.get('exchange')}
            if q.get('quoteType'):
                item['quoteType'] = q['quoteType']   # EQUITY/ETF... -> le dashboard etiquette les ETF
            prices.append(item)
            pmap[t] = (q['price'], q.get('exchange'))
        time.sleep(0.3)
    push(db, 'stocks/screener/livePrices', {'generatedAt': _now_iso(), 'prices': prices})
    print(f'Cours live pousses : {len(prices)}/{len(tickers)} ({", ".join(p["ticker"] for p in prices)})')

    # --- Instantane quotidien du portefeuille (valeur + investi, en USD) + composition par ticker ---
    fx = _fx_rates()
    agg = {}   # ticker -> {value, invested} agrege (permet le detail par position au clic d'un jour)
    for p in poslist:
        t = str(p['ticker']).upper().strip()
        try:
            qty = float(p.get('qty') or 0)
            pru = float(p.get('pru') or 0)
        except (TypeError, ValueError):
            continue
        pu = _to_usd(pmap[t][0], pmap[t][1], fx) if t in pmap else None
        lv = qty * (pu if pu is not None else pru)   # cours indispo -> on retient le cout (P&L neutre)
        a = agg.setdefault(t, {'value': 0.0, 'invested': 0.0})
        a['value'] += lv
        a['invested'] += qty * pru
    lines = [{'ticker': k, 'value': round(v['value'], 2), 'invested': round(v['invested'], 2)} for k, v in sorted(agg.items())]
    value = round(sum(v['value'] for v in agg.values()), 2)
    invested = round(sum(v['invested'] for v in agg.values()), 2)
    day = datetime.now().strftime('%Y-%m-%d')                # date locale du VPS (cloture US ~22h FR)
    snap = {'value': value, 'invested': invested, 'ts': _now_iso(), 'lines': lines}
    push(db, f'stocks/screener/positionsHistory/{day}', snap)
    print(f'Instantane {day} : valeur ${value:.0f} / investi ${invested:.0f} ({len(lines)} lignes)')


if __name__ == '__main__':
    main()
