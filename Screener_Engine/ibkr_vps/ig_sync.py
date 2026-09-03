# -*- coding: utf-8 -*-
"""
Synchronisation IG -> Firebase, cote VPS (sans navigateur).

Portage fidele de syncFromIG() du dashboard : meme API IG, meme conversion,
meme logique de fusion et memes noeuds Firebase, pour que le resultat soit
identique a un clic sur le bouton "Synchroniser IG".

  1. login IG            -> CST + X-SECURITY-TOKEN
  2. lastDataUpdate      -> date de depart (avec 1 jour de marge)
  3. /history/transactions
  4. conversion          -> trades / dividendes / depots / frais
  5. fusion              -> deduplication par reference IG
  6. ecriture Firebase   -> trades, dividends, deposits, fees, lastDataUpdate

Identifiants : dans ig_config.json a cote de ce script (JAMAIS dans le code,
JAMAIS dans git). Voir ig_config.example.json.

Usage :
    python ig_sync.py            # incremental (depuis la derniere synchro)
    python ig_sync.py --full     # tout l'historique depuis le 01/01/2026
    python ig_sync.py --dry-run  # affiche ce qui serait ecrit, sans ecrire
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone

from firebase_push import get as fb_get
from firebase_push import push as fb_push

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG = os.path.join(HERE, 'ig_config.json')
DEFAULT_BASE = 'https://api.ig.com/gateway/deal'


def log(msg):
    print('[%s] %s' % (datetime.now().strftime('%H:%M:%S'), msg), flush=True)


def load_config():
    if not os.path.exists(CONFIG):
        log('ERREUR : %s introuvable.' % CONFIG)
        log('Copie ig_config.example.json en ig_config.json et renseigne tes identifiants IG.')
        sys.exit(1)
    with open(CONFIG, 'r', encoding='utf-8') as f:
        cfg = json.load(f)
    for k in ('apiKey', 'username', 'password'):
        if not cfg.get(k):
            log('ERREUR : champ "%s" manquant ou vide dans ig_config.json' % k)
            sys.exit(1)
    cfg.setdefault('apiBase', DEFAULT_BASE)
    return cfg


def ig_request(base, path, method, headers, body=None):
    """Retourne (headers_minuscules, json). Leve une exception sur erreur."""
    url = base + path
    data = json.dumps(body).encode('utf-8') if body is not None else None
    h = {'Accept': 'application/json; charset=UTF-8'}
    h.update(headers or {})
    if data is not None:
        h['Content-Type'] = 'application/json'
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            payload = json.loads(r.read().decode('utf-8') or '{}')
            hdrs = {k.lower(): v for k, v in r.headers.items()}
            return hdrs, payload
    except urllib.error.HTTPError as e:
        raw = e.read().decode('utf-8', 'replace')
        try:
            code = json.loads(raw).get('errorCode') or ('HTTP %s' % e.code)
        except Exception:
            code = 'HTTP %s' % e.code
        raise RuntimeError('IG %s %s -> %s' % (method, path, code))


# ---------------------------------------------------------------- conversion
def parse_ig_pl(pl):
    """Portage de parseIgPL : ne garde que chiffres, point et signe."""
    if not pl:
        return 0.0
    cleaned = re.sub(r'[^0-9.\-]', '', str(pl))
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def map_market_name(name):
    """Portage de mapMarketName."""
    n = (name or '').lower()
    if 'us tech 100' in n or 'nasdaq' in n:
        return 'NASDAQ'
    if 'allemagne 40' in n or 'germany 40' in n or 'dax' in n:
        return 'DAX'
    return name


RE_FINANCEMENT = re.compile(r'int[eé]r[eê]t\s+(de\s+)?financement', re.I)


def convert_ig_transactions(txs):
    """Portage de convertIgTransactions."""
    trades, dividends, deposits, fees = [], [], [], []
    for tx in txs:
        amount = parse_ig_pl(tx.get('profitAndLoss'))
        date_utc = tx.get('dateUtc') or tx.get('date') or ''
        if not date_utc or len(date_utc) < 10:
            continue
        date_str = date_utc[:10]
        ref = tx.get('reference') or ''
        tx_type = (tx.get('transactionType') or '').upper()
        market = tx.get('instrumentName') or ''

        if tx_type in ('DEPO', 'DEPOSIT'):
            if RE_FINANCEMENT.search(market):
                dividends.append({'date': date_str, 'amount': amount, 'ref': ref, 'market': market})
            else:
                deposits.append({'date': date_str, 'amount': amount, 'ref': ref})
            continue
        if tx_type == 'DIVIDEND':
            dividends.append({'date': date_str, 'amount': amount, 'ref': ref, 'market': market})
            continue
        if tx_type not in ('ORDRE', 'TRADE', 'DEAL'):
            fees.append({'date': date_str, 'amount': amount, 'ref': ref, 'type': tx_type, 'market': market})
            continue

        def num(v):
            if v in (None, '', '-'):
                return 0.0
            try:
                return float(v)
            except (TypeError, ValueError):
                return 0.0

        symbol = map_market_name(market)
        open_date = tx.get('openDateUtc') or ''
        trade_date = open_date[:10] if len(open_date) >= 10 else date_str
        trades.append([trade_date, symbol, amount, ref, num(tx.get('size')),
                       num(tx.get('openLevel')), num(tx.get('closeLevel')), open_date, date_utc])
    return {'trades': trades, 'dividends': dividends, 'deposits': deposits, 'fees': fees}


def trade_key(t):
    """Portage de tradeKey : la reference IG si elle existe, sinon date|symbole|gain."""
    if t[3]:
        return t[3]
    sym = re.sub(r'\s+', ' ', str(t[1]).strip()).lower()
    return '%s|%s|%.2f' % (t[0], sym, t[2])


# ------------------------------------------------------------ lecture Firebase
def as_list(v):
    if not v:
        return []
    return v if isinstance(v, list) else list(v.values())


TRADE_FIELDS = ('date', 'symbol', 'gain', 'ref', 'size', 'openLevel', 'closeLevel', 'openDate', 'closeDate')


def trade_to_row(t):
    return [t.get('date'), t.get('symbol'), t.get('gain'), t.get('ref') or '', t.get('size') or 0,
            t.get('openLevel') or 0, t.get('closeLevel') or 0, t.get('openDate') or '', t.get('closeDate') or '']


def row_to_trade(r):
    return dict(zip(TRADE_FIELDS, [r[0], r[1], r[2], r[3] or '', r[4] or 0, r[5] or 0, r[6] or 0, r[7] or '', r[8] or '']))


# ------------------------------------------------------------------------ main
def run(cfg, db, full, dry):
    # 1. connexion IG
    log('Connexion a IG...')
    hdrs, _ = ig_request(cfg['apiBase'], '/session', 'POST',
                         {'X-IG-API-KEY': cfg['apiKey'], 'Version': '2'},
                         {'identifier': cfg['username'], 'password': cfg['password']})
    cst, token = hdrs.get('cst'), hdrs.get('x-security-token')
    if not cst or not token:
        log('ERREUR : IG n a pas renvoye de jeton de session.')
        sys.exit(1)
    log('Connecte.')

    # 2. fenetre de recuperation (meme regle que le dashboard)
    now = datetime.now(timezone.utc)
    if full:
        frm = datetime(2026, 1, 1, tzinfo=timezone.utc)
    else:
        last = fb_get(db, 'lastDataUpdate')
        if isinstance(last, (int, float)) and last > 0:
            frm = datetime.fromtimestamp(last / 1000.0, tz=timezone.utc)
        else:
            frm = now - timedelta(days=3)
        frm = frm - timedelta(days=1)   # 1 jour de marge
    from_str = frm.strftime('%Y-%m-%d') + 'T00:00:00'
    to_str = now.strftime('%Y-%m-%d') + 'T23:59:59'
    log('Transactions du %s au %s' % (from_str[:10], to_str[:10]))

    # 3. transactions
    _, body = ig_request(cfg['apiBase'],
                         '/history/transactions?from=%s&to=%s&type=ALL&pageSize=500' % (from_str, to_str),
                         'GET',
                         {'X-IG-API-KEY': cfg['apiKey'], 'CST': cst, 'X-SECURITY-TOKEN': token, 'Version': '2'})
    txs = body.get('transactions') or []
    log('%d transaction(s) recuperee(s).' % len(txs))
    if not txs:
        log('Rien a fusionner, arret.')
        return 'Aucune transaction IG sur la periode.'

    # 4. conversion
    data = convert_ig_transactions(txs)
    log('Converties : %d trade(s), %d dividende(s), %d depot(s), %d frais.'
        % (len(data['trades']), len(data['dividends']), len(data['deposits']), len(data['fees'])))

    # 5. fusion avec l existant (portage de mergeIgData)
    trades = [trade_to_row(t) for t in as_list(fb_get(db, 'trades'))]
    dividends = as_list(fb_get(db, 'dividends'))
    deposits = as_list(fb_get(db, 'deposits'))
    fees = as_list(fb_get(db, 'fees'))
    log('Existant : %d trades, %d dividendes, %d depots, %d frais.'
        % (len(trades), len(dividends), len(deposits), len(fees)))

    existing = {trade_key(t): t for t in trades}
    new_count = updated = dup = 0
    for t in data['trades']:
        k = trade_key(t)
        cur = existing.get(k)
        if cur is not None:
            if cur[0] != t[0]:
                cur[0] = t[0]
                updated += 1
            else:
                dup += 1
        else:
            trades.append(t)
            existing[k] = t
            new_count += 1
    trades.sort(key=lambda t: (t[0] or ''), reverse=True)

    div_refs = {d.get('ref') for d in dividends}
    new_divs = [d for d in data['dividends'] if d['ref'] not in div_refs]
    incoming_div_refs = {d['ref'] for d in data['dividends']}
    deposits = [d for d in deposits if d.get('ref') not in incoming_div_refs]
    dividends = dividends + new_divs

    dep_refs = {d.get('ref') for d in deposits}
    new_deps = [d for d in data['deposits'] if d['ref'] not in dep_refs]
    deposits = deposits + new_deps

    fee_refs = {f.get('ref') for f in fees}
    new_fees = [f for f in data['fees'] if f['ref'] not in fee_refs]
    fees = fees + new_fees

    msg = ('%d nouveau(x) trade(s), %d mis a jour, %d doublon(s) ignore(s), '
           '+%d dividende(s), +%d depot(s), +%d frais.'
           % (new_count, updated, dup, len(new_divs), len(new_deps), len(new_fees)))
    log('Fusion : ' + msg)

    if dry:
        log('--dry-run : aucune ecriture effectuee.')
        return msg
    if new_count == 0 and updated == 0 and not new_divs and not new_deps and not new_fees:
        log('Rien de nouveau, on n ecrit pas (evite de reecrire inutilement).')
        return msg

    # 6. ecriture (memes noeuds que le dashboard)
    fb_push(db, 'trades', [row_to_trade(r) for r in trades])
    fb_push(db, 'dividends', dividends)
    fb_push(db, 'deposits', deposits)
    fb_push(db, 'fees', fees)
    fb_push(db, 'lastDataUpdate', int(time.time() * 1000))
    log('Ecrit dans Firebase : %d trades, %d dividendes, %d depots, %d frais.'
        % (len(trades), len(dividends), len(deposits), len(fees)))
    return msg


def write_status(db, ok, message):
    """Statut de la derniere synchro, lu par le dashboard pour ALERTER en cas d echec.

    Ecrit succes ET echec : sans ca, une cle API IG expiree passerait inapercue
    pendant des semaines, le dashboard continuant d afficher de vieilles donnees.
    """
    payload = {'ok': bool(ok), 'at': int(time.time() * 1000), 'message': str(message)[:400]}
    try:
        fb_push(db, 'igSyncStatus', payload)
        log('Statut ecrit (ok=%s).' % bool(ok))
    except Exception as e:
        log('(statut non ecrit : %s)' % e)


def main():
    full = '--full' in sys.argv
    dry = '--dry-run' in sys.argv
    cfg = load_config()
    db = os.environ.get('FIREBASE_DB_URL')
    if not db:
        log('ERREUR : variable d environnement FIREBASE_DB_URL manquante.')
        sys.exit(1)
    try:
        msg = run(cfg, db, full, dry)
    except Exception as e:
        log('ECHEC : %s' % e)
        if not dry:
            write_status(db, False, e)   # l echec DOIT etre trace
        sys.exit(1)
    if not dry:
        write_status(db, True, msg)


if __name__ == '__main__':
    main()
