#!/usr/bin/env python3
# earnings_calendar.py - calendrier des resultats trimestriels des lignes detenues (onglet Resultats du dashboard).
# Pour chaque action du portefeuille (ETF et crypto ignores) : prochaine date de publication + consensus
# (BPA, chiffre d'affaires), 4 dernieres publications (BPA attendu/reel, CA attendu/reel) et reaction du cours.
# Ecrit stocks/screener/earnings. Appele par live_prices.py (toutes les 5 min) via maybe_refresh(), qui ne
# rappelle Yahoo que si c'est utile : donnees de plus de 6 h, ou publication en cours (moins de 36 h).
#
# Test local SANS Firebase :
#   python earnings_calendar.py --tickers MSFT,GOOGL --out test.json [--prev ancien.json] [--attendus MSFT=90736182420]
# Rafraichissement force sur le VPS (lit les positions, ecrit Firebase) :
#   python earnings_calendar.py --push
import argparse
import json
import math
import os
import sys
import time
from datetime import datetime, timezone, timedelta, date, time as dtime

from yahoo import Yahoo, BASE
from firebase_push import push, get_strict, patch

NODE = 'stocks/screener/earnings'
MODULES = 'calendarEvents,earnings,earningsHistory,price'
JOUR = 86400
AGE_MAX = 6 * 3600            # rafraichissement de routine
AGE_MIN = 20 * 60             # jamais plus d'une tentative toutes les 20 min
FENETRE_PUB = 36 * 3600       # publication recente : on suit la reaction du cours
FENETRE_REACTION = 10 * JOUR  # au-dela, plus d'appel au chart pour la reaction
APPARIEMENT = 3 * JOUR        # une date annoncee et une publication a moins de 3 jours = la meme
# La reaction se mesure avec les horaires de New York : places americaines seulement (code court du module price)
PLACES_US = {'NMS', 'NGM', 'NCM', 'NYQ', 'ASE', 'PCX', 'BATS'}


def _now_iso(ts=None):
    d = datetime.fromtimestamp(ts, timezone.utc) if ts is not None else datetime.now(timezone.utc)
    return d.replace(microsecond=0).isoformat()


def _parse_iso(v):
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00')).timestamp()
    except Exception:
        return None


def _raw(x):
    return x.get('raw') if isinstance(x, dict) else x


def _num(x):
    """Nombre fini ou None (NaN et Infinity rendraient le JSON invalide : Firebase refuserait tout le noeud)."""
    v = _raw(x)
    if isinstance(v, str):
        try:
            v = float(v.replace('%', ''))
        except ValueError:
            return None
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v if math.isfinite(v) else None


def _propre(o):
    """Filet de securite avant l'ecriture : tout flottant non fini devient null."""
    if isinstance(o, float) and not math.isfinite(o):
        return None
    if isinstance(o, dict):
        return {k: _propre(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_propre(v) for v in o]
    return o


def _cle(t):
    """Ticker -> cle Firebase (., $, #, [, ], / interdits)."""
    out = str(t)
    for c in '.$#[]/':
        out = out.replace(c, '_')
    return out


# --- Heure de New York : zoneinfo si tzdata est la, sinon les regles officielles (2e dimanche de mars,
#     1er dimanche de novembre, 2 h locale), comme morning_brief.ny_vers_paris ---
def _nieme_dimanche(an, mois, n):
    d = date(an, mois, 1)
    premier = d + timedelta(days=(6 - d.weekday()) % 7)
    return premier + timedelta(days=7 * (n - 1))


def _ny(ts):
    """epoch s -> datetime NAIF en heure de New York."""
    try:
        from zoneinfo import ZoneInfo
        return datetime.fromtimestamp(ts, ZoneInfo('America/New_York')).replace(tzinfo=None)
    except Exception:
        u = datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)
        deb = datetime.combine(_nieme_dimanche(u.year, 3, 2), dtime(7, 0))    # 2h EST = 7h UTC
        fin = datetime.combine(_nieme_dimanche(u.year, 11, 1), dtime(6, 0))   # 2h EDT = 6h UTC
        return u - timedelta(hours=(4 if deb <= u < fin else 5))


def _ny_date(ts):
    return _ny(ts).strftime('%Y-%m-%d')


def _utc_date(ts):
    return datetime.fromtimestamp(ts, timezone.utc).strftime('%Y-%m-%d')


def _date_seule(ts):
    """Yahoo donne parfois une date SANS heure, a minuit UTC pile : convertie en heure de New York, elle
    tomberait la VEILLE (TSM du 16/04/2026 affiche le 15/04)."""
    return isinstance(ts, int) and ts % JOUR == 0


def _fourchette(ce, prefixe):
    out = {'moy': _num(ce.get(prefixe + 'Average')), 'bas': _num(ce.get(prefixe + 'Low')), 'haut': _num(ce.get(prefixe + 'High'))}
    return out if any(v is not None for v in out.values()) else None


def fetch(y, t):
    j = y._get(f'{BASE}/v10/finance/quoteSummary/{t}?modules={MODULES}')
    res = ((j.get('quoteSummary') or {}).get('result') or [None])[0]
    if not res:
        err = (j.get('quoteSummary') or {}).get('error') or {}
        raise RuntimeError(err.get('description') or 'reponse Yahoo vide')
    return res


# --- Reaction du cours a une publication ---
def reaction(t, ts_pub, now, closes_fn, live_fn, jour=None, heure_connue=True):
    """{base, cours, pct, etat, baseDate, coursDate} ou None si la cloture de reference manque.
    Avant 9h30 NY : veille -> jour. Apres 16h NY : jour -> seance suivante. En seance : veille -> jour.
    Heure inconnue (date seule) : veille de bourse -> jour J, J etant la date telle que Yahoo la donne."""
    pub = _ny(ts_pub)
    d = jour or pub.strftime('%Y-%m-%d')
    minutes = pub.hour * 60 + pub.minute if heure_connue else 12 * 60
    closes = {k: v for k, v in (closes_fn(t) or {}).items() if _num(v) is not None}
    n_ny = _ny(now)
    auj = n_ny.strftime('%Y-%m-%d')
    seance_finie = n_ny.hour * 60 + n_ny.minute >= 16 * 60 + 10

    def definitive(j):
        # index_history rebouche le jour courant avec le cours de seance : ce n'est une cloture qu'apres 16h10 NY
        return j in closes and (j < auj or (j == auj and seance_finie))

    jours = sorted(j for j in closes if definitive(j))
    if minutes >= 16 * 60:
        base_j = d if definitive(d) else None
        suite = [j for j in jours if j > d]
        cours_j = suite[0] if suite else None
    else:
        avant = [j for j in jours if j < d]
        base_j = avant[-1] if avant else None
        cours_j = d if definitive(d) else None
    if not base_j:
        return None
    base = float(closes[base_j])
    if cours_j:
        cours, etat, cours_date = float(closes[cours_j]), 'definitif', cours_j
    else:
        cours = _num((live_fn(t) or {}).get('price'))
        if cours is None:
            return None
        etat, cours_date = 'provisoire', auj
    if not base:
        return None
    return {'base': round(base, 4), 'cours': round(cours, 4), 'pct': round(cours / base - 1, 5),
            'etat': etat, 'baseDate': base_j, 'coursDate': cours_date}


# --- Construction d'une ligne ---
def build_item(t, r, prev_item, now, closes_fn, live_fn, attendu_cli=None, errs=None):
    """None si ce n'est pas une action (ETF, crypto : pas de resultats trimestriels).
    Reponse Yahoo partielle : on garde ce qu'on savait et on note la raison dans errs."""
    errs = errs if errs is not None else []
    prev_item = prev_item or {}
    price = r.get('price') or {}
    qt = (price.get('quoteType') or '').upper()
    if not qt:
        if prev_item:
            errs.append('quoteType absent de la reponse Yahoo, ligne precedente gardee')
            return prev_item
        errs.append('quoteType absent de la reponse Yahoo')
        return None
    if qt != 'EQUITY':
        return None
    place_us = price.get('exchange') in PLACES_US or price.get('exchangeTimezoneName') == 'America/New_York'
    earn = r.get('earnings') or {}
    hist = (r.get('earningsHistory') or {}).get('history') or []
    devise_bpa = next((h.get('currency') for h in reversed(hist) if h.get('currency')), None) \
        or prev_item.get('deviseBpa') or price.get('currency')
    quarters = (earn.get('earningsChart') or {}).get('quarterly') or []
    reported = [_raw(q.get('reportedDate')) for q in quarters if _raw(q.get('reportedDate'))]

    # Prochaine publication annoncee (ou estimee) par Yahoo
    cal_ok = 'calendarEvents' in r
    ce = (r.get('calendarEvents') or {}).get('earnings') or {}
    if not cal_ok:
        errs.append('calendarEvents absent de la reponse Yahoo, prochaine date precedente gardee')
    ts_next = next((_raw(d) for d in (ce.get('earningsDate') or []) if _raw(d)), None)
    appel = next((_raw(d) for d in (ce.get('earningsCallDate') or []) if _raw(d)), None)
    if not (ts_next and appel and _ny_date(appel) == _ny_date(ts_next)):
        appel = None   # Yahoo laisse l'appel du trimestre PRECEDENT quand la date suivante n'est qu'estimee (TSM)
    bpa_next, ca_next = _fourchette(ce, 'earnings'), _fourchette(ce, 'revenue')
    consensus_frais = bool(bpa_next or ca_next)   # vient de CETTE reponse (sinon repris de l'etat precedent)
    prev_att, prev_proch = prev_item.get('attente'), prev_item.get('prochain') or {}

    def meme_date(a):
        return bool(a and a.get('ts') and ts_next and abs(a['ts'] - ts_next) <= APPARIEMENT)
    if cal_ok and ts_next and (bpa_next is None or ca_next is None):
        for src in (prev_proch, prev_att):     # consensus manquant : celui deja connu pour la meme date
            if meme_date(src):
                bpa_next = bpa_next or src.get('bpa')
                ca_next = ca_next or src.get('ca')
        if bpa_next is None and ca_next is None:
            errs.append('consensus absent de la reponse Yahoo')

    # Consensus capture AVANT publication : Yahoo bascule le consensus sur le trimestre suivant avant de
    # changer la date (MSFT le 29/10/2026 au matin : date du 28/10, consensus du trimestre suivant). On ne
    # le capture plus des que la publication est la (MA publie vers 8h03 NY pour une date Yahoo a 8h30).
    deja_publie = bool(ts_next) and any(rd <= now and abs(rd - ts_next) <= APPARIEMENT for rd in reported)
    attente, attente_prec = prev_att, prev_item.get('attentePrec')
    if cal_ok and ts_next and ts_next > now and not deja_publie and consensus_frais:
        if attente and attente.get('ts') and attente['ts'] <= now and abs(attente['ts'] - ts_next) > APPARIEMENT:
            attente_prec = attente   # nouvelle date alors que l'ancienne n'a pas encore ete appariee : on la garde
        attente = {'date': _ny_date(ts_next), 'ts': ts_next, 'bpa': bpa_next, 'ca': ca_next, 'at': _now_iso(now)}

    # Publications (earningsChart : BPA attendu/reel, date reelle de publication) + CA reel (financialsChart)
    ca_par_label = {q.get('date'): _num(q.get('revenue')) for q in ((earn.get('financialsChart') or {}).get('quarterly') or [])}
    prev_pubs = [p for p in (prev_item.get('publies') or []) if isinstance(p, dict)]
    prev_pub = {p.get('trimestre'): p for p in prev_pubs}
    if not quarters and prev_pubs:
        errs.append('earningsChart absent de la reponse Yahoo, publications precedentes gardees')
    pubs, vus = [], set()
    for q in quarters:
        ts_r, fin = _raw(q.get('reportedDate')), _raw(q.get('periodEndDate'))
        if not ts_r:
            continue
        tri = (q.get('periodEndDate') or {}).get('fmt') if isinstance(q.get('periodEndDate'), dict) else None
        tri = tri or (_utc_date(fin) if fin else None)
        ancien = prev_pub.get(tri) or {}
        # Date seule : l'heure vient de l'appariement avec la date annoncee, MEMORISE dans la publication
        # pour qu'elle ne retombe pas a minuit quand l'attente aura ete consommee.
        app = None
        if _date_seule(ts_r):
            if ancien.get('tsApparie') and abs(ancien['tsApparie'] - ts_r) <= APPARIEMENT:
                app = ancien['tsApparie']
            else:
                for a in (attente, attente_prec):
                    if a and a.get('ts') and not _date_seule(a['ts']) and abs(a['ts'] - ts_r) <= APPARIEMENT:
                        app = a['ts']
                        break
        if app:
            ts_ref, jour, heure_inconnue = app, _ny_date(app), False
        elif _date_seule(ts_r):
            ts_ref, jour, heure_inconnue = ts_r, _utc_date(ts_r), True
        else:
            ts_ref, jour, heure_inconnue = ts_r, _ny_date(ts_r), False
        att, reel = _num(q.get('estimate')), _num(q.get('actual'))
        ecart = _num(q.get('surprisePct'))
        if ecart is None and att and reel is not None:
            ecart = round((reel / att - 1) * 100, 2)
        ca_att = (ancien.get('ca') or {}).get('attendu')
        if ca_att is None:
            for a in (attente, attente_prec):
                if a and a.get('ts') and abs(a['ts'] - ts_r) <= APPARIEMENT and (a.get('ca') or {}).get('moy') is not None:
                    ca_att = a['ca']['moy']
                    break
        ca_reel = ca_par_label.get(q.get('date'))
        if ca_reel is None:
            ca_reel = (ancien.get('ca') or {}).get('reel')
        p = {'trimestre': tri, 'date': jour, 'ts': ts_ref, 'tsYahoo': ts_r,
             'bpa': {'attendu': att if att is not None else (ancien.get('bpa') or {}).get('attendu'),
                     'reel': reel if reel is not None else (ancien.get('bpa') or {}).get('reel'), 'ecartPct': ecart},
             'ca': {'attendu': ca_att, 'reel': ca_reel}, 'reaction': ancien.get('reaction')}
        if app:
            p['tsApparie'] = app
        if heure_inconnue:
            p['heureInconnue'] = True
        pubs.append(p)
        vus.add(tri)
    pubs += [p for p in prev_pubs if p.get('trimestre') not in vus]   # absentes de la reponse : gardees
    pubs.sort(key=lambda p: p.get('ts') or 0, reverse=True)
    pubs = pubs[:4]

    # Consensus de CA pose a la main (amorcage : publications passees avant la mise en service)
    if attendu_cli and pubs:
        val, jour = attendu_cli
        cible = next((p for p in pubs if p['date'] == jour), None) if jour else pubs[0]
        if cible and (cible.get('ca') or {}).get('attendu') is None:
            cible.setdefault('ca', {})['attendu'] = val

    # Reaction : places US seulement, jamais recalculee une fois definitive, publications des 10 derniers jours
    for p in pubs:
        if not place_us:
            p['reaction'] = None
            continue
        r0 = p.get('reaction') or {}
        ts = p.get('ts') or 0
        if r0.get('etat') == 'definitif' or now - ts > FENETRE_REACTION or ts > now:
            continue
        p['reaction'] = reaction(t, ts, now, closes_fn, live_fn, p.get('date'), not p.get('heureInconnue')) or p.get('reaction')

    # Une attente appariee a une publication ne sert plus
    if attente_prec and any(abs((p.get('tsYahoo') or p.get('ts') or 0) - (attente_prec.get('ts') or 0)) <= APPARIEMENT for p in pubs):
        attente_prec = None
    if attente_prec and now - (attente_prec.get('ts') or 0) > 30 * JOUR:
        attente_prec = None

    # Date Yahoo deja publiee : plus de prochaine date connue (consensus du trimestre suivant garde)
    if not cal_ok:
        prochain = prev_item.get('prochain')
    elif ts_next and not deja_publie:
        prochain = {'date': _ny_date(ts_next), 'ts': ts_next, 'appel': appel,
                    'estimee': bool(ce.get('isEarningsDateEstimate')), 'bpa': bpa_next, 'ca': ca_next}
    elif bpa_next or ca_next:
        prochain = {'date': None, 'ts': None, 'appel': None, 'estimee': True, 'bpa': bpa_next, 'ca': ca_next}
    else:
        prochain = None

    item = {'ticker': t, 'nom': price.get('shortName') or price.get('longName') or prev_item.get('nom') or t,
            'deviseBpa': devise_bpa,
            'deviseCa': earn.get('financialCurrency') or prev_item.get('deviseCa') or price.get('currency'),
            'prochain': prochain, 'publies': pubs, 'attente': attente}
    if attente_prec:
        item['attentePrec'] = attente_prec   # interne : consensus d'une date passee pas encore appariee
    return item


# --- Rafraichissement complet ---
def refresh(y, tickers, prev, now=None, attendus=None):
    now = int(now or time.time())
    prev = prev or {}
    prev_items = {it.get('ticker'): it for it in (prev.get('items') or []) if isinstance(it, dict)}
    cache_closes = {}

    def closes_fn(t):
        if t not in cache_closes:
            cache_closes[t] = y.index_history(t, '3mo') or {}
        return cache_closes[t]

    def live_fn(t):
        return y.live_quote(t)

    items, errors, repondu = [], {}, 0
    for t in tickers:
        errs = []
        try:
            r = fetch(y, t)
            repondu += 1
            it = build_item(t, r, prev_items.get(t), now, closes_fn, live_fn, (attendus or {}).get(t), errs)
            if it:
                items.append(it)
        except Exception as e:
            errs.append(f'{type(e).__name__}: {e}')
            if t in prev_items:
                items.append(prev_items[t])   # on garde la ligne precedente plutot qu'un trou
        if errs:
            errors[_cle(t)] = '; '.join(errs)[:200]
        time.sleep(0.3)

    if tickers and not repondu:
        # Panne globale : on ne touche pas aux donnees, on dit pourquoi
        raison = next(iter(errors.values()), 'aucune reponse')
        out = dict(prev)
        out.update({'v': 1, 'error': f'Yahoo injoignable ({raison})', 'errorAt': _now_iso(now), 'tentativeAt': _now_iso(now)})
        out.setdefault('items', [])
        return out
    return {'v': 1, 'generatedAt': _now_iso(now), 'tentativeAt': _now_iso(now), 'error': '', 'errors': errors, 'items': items}


def _a_rafraichir(prev, now):
    """(bool, raison) : regle de cadence (live_prices tourne toutes les 5 min)."""
    gen = _parse_iso((prev or {}).get('generatedAt'))
    tent = _parse_iso((prev or {}).get('tentativeAt')) or gen
    if tent and now - tent < AGE_MIN:
        return False, 'derniere tentative il y a moins de 20 min'
    if not gen or now - gen > AGE_MAX:
        return True, 'donnees de plus de 6 h' if gen else 'aucune donnee'
    for it in (prev.get('items') or []):
        if not isinstance(it, dict):
            continue
        for p in (it.get('publies') or []):
            ts = (p or {}).get('ts') or 0
            if 0 <= now - ts < FENETRE_PUB and ((p.get('reaction') or {}).get('etat') != 'definitif'):
                return True, f'reaction a suivre ({it.get("ticker")})'
        ts = ((it.get('prochain') or {}).get('ts')) or 0
        if ts and 0 <= now - ts < FENETRE_PUB:
            return True, f'publication attendue ({it.get("ticker")})'
    return False, 'rien a suivre'


def _bilan(data):
    items = data.get('items') or []
    proch = sorted((it['prochain']['date'], it['ticker']) for it in items if (it.get('prochain') or {}).get('date'))
    txt = ', '.join(f'{t} {d}' for d, t in proch[:4])
    err = f" ; ERREUR {data['error']}" if data.get('error') else ''
    per = f" ; {len(data.get('errors') or {})} ticker(s) en echec" if data.get('errors') else ''
    return f'Resultats : {len(items)} actions, prochaines : {txt or "aucune"}{per}{err}'


def maybe_refresh(db, y, tickers, force=False, now=None):
    """Appele par live_prices.py. Lit le noeud precedent, rafraichit si la cadence le demande, pousse."""
    now = int(now or time.time())
    if not tickers:
        print('Resultats : aucune position, rien ecrit')
        return False
    try:
        prev = get_strict(db, NODE) or {}
    except Exception as e:
        # Lecture ratee : surtout ne pas repartir de zero (le PUT effacerait consensus memorises et
        # reactions definitives). On signale seulement la raison, par un PATCH qui ne touche pas aux items.
        raison = f'lecture Firebase impossible ({type(e).__name__}: {e})'[:300]
        print(f'Resultats : {raison}, donnees laissees intactes')
        try:
            patch(db, NODE, {'error': raison, 'errorAt': _now_iso(now), 'tentativeAt': _now_iso(now)})
        except Exception as e2:
            print(f'Resultats : signalement de l erreur impossible ({type(e2).__name__}: {e2})')
        return False
    if not isinstance(prev, dict):
        prev = {}
    ok, pourquoi = (True, 'force') if force else _a_rafraichir(prev, now)
    if not ok:
        print(f'Resultats : pas de rafraichissement ({pourquoi})')
        return False
    try:
        data = refresh(y, tickers, prev, now)
    except Exception as e:
        # Panne imprevue : on garde les donnees precedentes et on pousse la RAISON pour le dashboard
        data = dict(prev)
        data.update({'v': 1, 'error': f'{type(e).__name__}: {e}'[:300], 'errorAt': _now_iso(now), 'tentativeAt': _now_iso(now)})
        data.setdefault('items', [])
    try:
        push(db, NODE, _propre(data))
    except Exception as e:
        print(f'Resultats : ecriture Firebase impossible ({type(e).__name__}: {e})')
        return False
    print(f'{_bilan(data)} ({pourquoi})')
    return True


def _parse_attendus(txt):
    """'MSFT=90736182420,GOOGL=127913936970@2026-10-28' -> {ticker: (valeur, date ou None)}"""
    out = {}
    for part in (txt or '').split(','):
        if '=' not in part:
            continue
        t, v = part.split('=', 1)
        v, _, jour = v.partition('@')
        out[t.strip().upper()] = (float(v), jour.strip() or None)
    return out


def main():
    ap = argparse.ArgumentParser(description='Calendrier des resultats des positions (onglet Resultats).')
    ap.add_argument('--tickers', help='liste separee par des virgules (mode local, sans Firebase)')
    ap.add_argument('--prev', help='JSON precedent (mode local)')
    ap.add_argument('--out', help='fichier de sortie (mode local)')
    ap.add_argument('--attendus', help='consensus de CA a poser : MSFT=90736182420,GOOGL=127913936970[@AAAA-MM-JJ]')
    ap.add_argument('--push', action='store_true', help='VPS : lit les positions, rafraichit et ecrit Firebase')
    a = ap.parse_args()
    y = Yahoo()
    if a.push:
        db = os.environ.get('FIREBASE_DB_URL')
        if not db:
            print('FIREBASE_DB_URL manquant'); return 1
        from live_prices import _poslist
        try:
            pos = get_strict(db, 'stocks/screener/myPositions')
        except Exception as e:
            print(f'Lecture des positions impossible ({type(e).__name__}: {e}), rien ecrit'); return 1
        tickers = sorted({str(p['ticker']).upper().strip() for p in _poslist(pos)})
        if not tickers:
            print('Aucune position, rien ecrit'); return 1
        return 0 if maybe_refresh(db, y, tickers, force=True) else 1
    if not a.tickers:
        ap.error('--tickers ou --push requis')
    tickers = [t.strip().upper() for t in a.tickers.split(',') if t.strip()]
    prev = json.load(open(a.prev, encoding='utf-8')) if a.prev else {}
    data = _propre(refresh(y, tickers, prev, attendus=_parse_attendus(a.attendus)))
    if a.out:
        with open(a.out, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=1, allow_nan=False)
    print(_bilan(data))
    return 0


if __name__ == '__main__':
    sys.exit(main())
