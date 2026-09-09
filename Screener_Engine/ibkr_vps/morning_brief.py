#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
morning_brief.py - Brief matinal du Trading Dashboard (a planifier ~07h45, avant 8h30).
===============================================================================
Produit `dashboard/morningBrief` :
  1. Fear & Greed CNN : score, comparaisons, 1 an d'historique, sous-indicateurs.
     Le NAVIGATEUR ne peut pas appeler CNN (politique CORS), d'ou la collecte ici.
  2. Actualites Yahoo des lignes detenues + du marche, FILTREES du bruit
     (Yahoo etiquette un article "META" alors qu'il parle de Jushi Holdings).
  3. Synthese redigee en francais par l'API Anthropic (modele Haiku : rapide,
     peu cher, largement suffisant pour resumer des titres).

Le brief est du REPERAGE, pas du conseil : le prompt interdit explicitement
toute recommandation d'achat ou de vente.

Env : FIREBASE_DB_URL, ANTHROPIC_API_KEY (cle creee par l'utilisateur lui-meme).
Si ANTHROPIC_API_KEY est absente, le script pousse quand meme le Fear & Greed et
les titres bruts : le bloc reste utile, seule la synthese manque.
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

from firebase_push import push, get

UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36')
CNN_URL = 'https://production.dataviz.cnn.io/index/fearandgreed/graphdata'
ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
# Modele par defaut : Haiku 4.5. Resumer une vingtaine de titres en un paragraphe est
# une tache ou il fait aussi bien qu'un gros modele, pour une fraction du prix.
# Surchargeable sans toucher au code :
#     setx ANTHROPIC_MODEL "claude-opus-5"
ANTHROPIC_MODEL = os.environ.get('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
NEWS_MAX_AGE_H = 36          # au-dela, ce n'est plus "la nouvelle du matin"
NEWS_PER_TICKER = 3


def _now_iso():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _get_json(url, headers=None, timeout=20):
    h = {'User-Agent': UA, 'Accept': 'application/json, text/plain, */*'}
    if headers:
        h.update(headers)
    req = urllib.request.Request(url, headers=h)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8', 'replace'))


# ── 1. Fear & Greed (CNN) ────────────────────────────────────────────────────
def fetch_fear_greed():
    """Payload compact : score, rating, comparaisons, historique 1 an, indicateurs.
    CNN bloque les User-Agent non navigateur, d'ou les en-tetes Referer/Origin."""
    j = _get_json(CNN_URL, {'Referer': 'https://edition.cnn.com/',
                            'Origin': 'https://edition.cnn.com'})
    f = j.get('fear_and_greed') or {}
    hist = ((j.get('fear_and_greed_historical') or {}).get('data') or [])
    # On garde 1 point par jour, en millisecondes -> date ISO courte, valeur arrondie.
    series = []
    for p in hist:
        try:
            d = datetime.fromtimestamp(p['x'] / 1000, timezone.utc).strftime('%Y-%m-%d')
            series.append({'d': d, 'v': round(float(p['y']), 1)})
        except Exception:
            continue
    comps = {}
    for k, v in j.items():
        if k in ('fear_and_greed', 'fear_and_greed_historical') or not isinstance(v, dict):
            continue
        if v.get('score') is None:
            continue
        comps[k] = {'score': round(float(v['score']), 1), 'rating': v.get('rating')}
    return {
        'score': round(float(f.get('score') or 0), 1),
        'rating': f.get('rating'),
        'at': f.get('timestamp'),
        'prev': {
            'close': round(float(f.get('previous_close') or 0), 1),
            'week': round(float(f.get('previous_1_week') or 0), 1),
            'month': round(float(f.get('previous_1_month') or 0), 1),
            'year': round(float(f.get('previous_1_year') or 0), 1),
        },
        'components': comps,
        'history': series,
    }


# ── 2. Actualites Yahoo, filtrees ────────────────────────────────────────────
def _name_keys(name):
    """Mots significatifs du nom de societe, pour reconnaitre un article qui parle
    vraiment d'elle ('Meta Platforms, Inc.' -> {'meta','platforms'})."""
    stop = {'inc', 'corp', 'corporation', 'company', 'limited', 'ltd', 'plc', 'holdings',
            'the', 'and', 'sa', 'nv', 'ag', 'co', 'group', 'ucits', 'etf', 'usd',
            'accumulation', 'com'}
    out = set()
    for w in re.split(r'[^A-Za-z0-9]+', (name or '').lower()):
        if len(w) >= 3 and w not in stop:
            out.add(w)
    return out


def _relevant(item, ticker, keys):
    """Yahoo rattache large : un article sur Jushi Holdings est etiquete META.
    On garde donc seulement si le titre nomme la societe, ou si le ticker est le
    PREMIER des tickers lies (l'article lui est alors principalement consacre)."""
    title = (item.get('title') or '')
    tl = title.lower()
    if any(k in tl for k in keys):
        return True
    rel = [str(t).upper() for t in (item.get('relatedTickers') or [])]
    return bool(rel) and rel[0] == ticker.upper()


def fetch_news(ticker, name, limit=NEWS_PER_TICKER):
    url = ('https://query1.finance.yahoo.com/v1/finance/search?q='
           + urllib.parse.quote(ticker) + '&newsCount=10&quotesCount=0')
    try:
        j = _get_json(url)
    except Exception as e:
        print(f'  actus {ticker} : {e}')
        return []
    keys = _name_keys(name)
    cutoff = time.time() - NEWS_MAX_AGE_H * 3600
    out = []
    for it in (j.get('news') or []):
        ts = it.get('providerPublishTime') or 0
        if ts and ts < cutoff:
            continue
        if not _relevant(it, ticker, keys):
            continue
        out.append({'t': (it.get('title') or '')[:220], 'p': it.get('publisher'),
                    'u': it.get('link'), 'ts': ts})
        if len(out) >= limit:
            break
    return out


def fetch_market_news(limit=12):
    """Actualites de marche : on interroge les grands indices, sans filtre de nom."""
    seen, out = set(), []
    cutoff = time.time() - NEWS_MAX_AGE_H * 3600
    for q in ('^GSPC', '^IXIC'):
        try:
            j = _get_json('https://query1.finance.yahoo.com/v1/finance/search?q='
                          + urllib.parse.quote(q) + '&newsCount=10&quotesCount=0')
        except Exception:
            continue
        for it in (j.get('news') or []):
            u = it.get('uuid')
            ts = it.get('providerPublishTime') or 0
            if not u or u in seen or (ts and ts < cutoff):
                continue
            seen.add(u)
            out.append({'t': (it.get('title') or '')[:220], 'p': it.get('publisher'),
                        'u': it.get('link'), 'ts': ts})
        time.sleep(0.3)
    out.sort(key=lambda x: x.get('ts') or 0, reverse=True)
    return out[:limit]


# ── 2 bis. Calendrier economique americain (Nasdaq, sans cle) ────────────────
# Nasdaq publie 25 a 70 evenements par jour, en majorite du bruit (demandes de credit
# immobilier, indices hebdo...). On ne garde que ce qui deplace reellement les indices.
ECON_CLES = re.compile(
    r'\b(CPI|PPI|PCE|Nonfarm|Non-Farm|Payroll|Unemployment Rate|FOMC|Interest Rate Decision'
    r'|Fed Interest Rate|GDP|Retail Sales|ISM|Consumer Confidence|Michigan|Durable Goods'
    r'|Initial Jobless Claims|Beige Book|Powell)\b', re.I)


def fetch_econ_calendar(days=7):
    """Evenements macro US des `days` prochains jours, dates FIABLES (contrairement aux
    articles de presse, qui evoquent les rendez-vous sans toujours les dater)."""
    out, vus = [], set()
    for k in range(days):
        jour = (datetime.now() + timedelta(days=k)).strftime('%Y-%m-%d')
        try:
            j = _get_json('https://api.nasdaq.com/api/calendar/economicevents?date=' + jour)
        except Exception as e:
            print(f'  calendrier {jour} : {e}')
            continue
        for r in ((j.get('data') or {}).get('rows') or []):
            if 'united states' not in str(r.get('country') or '').lower():
                continue
            nom = re.sub(r'<[^>]*>', '', str(r.get('eventName') or '')).strip()
            if not nom or not ECON_CLES.search(nom):
                continue
            cle = (jour, nom, str(r.get('consensus') or ''))
            if cle in vus:
                continue
            vus.add(cle)
            out.append({'date': jour, 'heure': str(r.get('gmt') or '').strip(),
                        'nom': nom[:90], 'consensus': str(r.get('consensus') or '').strip(),
                        'precedent': str(r.get('previous') or '').strip()})
        time.sleep(0.3)
    return out


# ── 3. Synthese Anthropic ────────────────────────────────────────────────────
PROMPT = """Tu rédiges le brief matinal du tableau de bord d'investissement d'un particulier français.

RÈGLES ABSOLUES :
- Tu rapportes des FAITS. Tu ne donnes JAMAIS de recommandation d'achat, de vente ou de conservation, ni d'objectif de cours. Ce n'est pas un conseil en investissement.
- Français naturel, sans tiret cadratin. Utilise des virgules.
- Si une ligne n'a pas d'actualité notable, tu ne l'inventes pas et tu ne la mentionnes pas.
- Sois bref. Le lecteur lit ça en deux minutes avant l'ouverture.

RÈGLE SUR LES DATES, LA PLUS IMPORTANTE :
- Le CALENDRIER ÉCONOMIQUE ci-dessous est une source FIABLE : cite ses dates, ses heures et
  ses consensus sans hésiter, ce sont les échéances qui comptent pour la semaine.
- Pour tout le reste, tu ne cites une échéance QUE si elle apparaît dans les données fournies.
- Tu n'écris JAMAIS une date de mémoire. Si un article mentionne un rendez-vous sans le dater,
  dis "prochainement" plutôt que d'inventer un jour.

STRUCTURE ATTENDUE, en JSON strict et rien d'autre :
{"market": "un paragraphe de 2 à 4 phrases sur le climat général : indices, taux, macro, et ce que dit l'indice Fear & Greed",
 "attentisme": "1 à 3 phrases expliquant ce qui peut retenir le marché aujourd'hui : rendez-vous macro ou résultats attendus, incertitude, sous-indicateurs du Fear & Greed qui divergent. Chaîne de causalité explicite. Si rien ne le justifie dans les données, dis-le franchement.",
 "semaine": [{"quand": "le repère temporel TEL QU'IL APPARAÎT dans les données (ex : jeudi, cette semaine, prochainement)", "quoi": "l'échéance", "pourquoi": "en quoi elle compte pour un portefeuille d'actions américaines"}],
 "positions": [{"ticker": "XXXX", "text": "1 à 2 phrases factuelles sur ce qui concerne cette ligne"}],
 "watch": ["2 à 4 faits ou échéances à surveiller aujourd'hui"]}

DONNÉES DU JOUR :
"""


def anthropic_brief(api_key, fg, per_ticker, market, econ=None):
    """Retourne le dict {market, positions, watch} ou None. Ne leve jamais."""
    lignes = []
    JOURS = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
    MOIS = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
            'septembre', 'octobre', 'novembre', 'décembre']
    d = datetime.now()
    lignes.append(f"Nous sommes le {JOURS[d.weekday()]} {d.day} {MOIS[d.month - 1]} {d.year}.")
    lignes.append(f"Fear & Greed CNN : {fg['score']} ({fg['rating']}). "
                  f"Hier {fg['prev']['close']}, il y a une semaine {fg['prev']['week']}, "
                  f"un mois {fg['prev']['month']}, un an {fg['prev']['year']}.")
    comp = ', '.join(f"{k} {v['score']} ({v['rating']})" for k, v in (fg.get('components') or {}).items())
    if comp:
        lignes.append('Sous-indicateurs : ' + comp)
    if econ:
        lignes.append('\nCALENDRIER ÉCONOMIQUE AMÉRICAIN (dates fiables, heures de New York) :')
        for e in econ:
            det = []
            if e.get('consensus'):
                det.append('consensus ' + e['consensus'])
            if e.get('precedent'):
                det.append('précédent ' + e['precedent'])
            lignes.append(f"- {e['date']} {e.get('heure', '')} {e['nom']}"
                          + (' (' + ', '.join(det) + ')' if det else ''))
    lignes.append('\nACTUALITÉS DE MARCHÉ :')
    for n in market:
        lignes.append(f"- [{n.get('p')}] {n['t']}")
    lignes.append('\nACTUALITÉS DES LIGNES DÉTENUES :')
    for grp in per_ticker:
        for n in grp['items']:
            lignes.append(f"- {grp['ticker']} [{n.get('p')}] {n['t']}")
    body = {
        'model': ANTHROPIC_MODEL,
        'max_tokens': 1500,
        'messages': [{'role': 'user', 'content': PROMPT + '\n'.join(lignes)}],
    }
    try:
        req = urllib.request.Request(
            ANTHROPIC_URL, data=json.dumps(body).encode('utf-8'),
            headers={'content-type': 'application/json', 'x-api-key': api_key,
                     'anthropic-version': '2023-06-01'}, method='POST')
        with urllib.request.urlopen(req, timeout=90) as r:
            j = json.loads(r.read().decode('utf-8', 'replace'))
        txt = ''.join(b.get('text', '') for b in (j.get('content') or []) if b.get('type') == 'text')
        m = re.search(r'\{.*\}', txt, re.S)          # le modele peut encadrer le JSON
        return json.loads(m.group(0)) if m else None
    except urllib.error.HTTPError as e:
        print(f'  Anthropic HTTP {e.code} : {e.read().decode("utf-8", "replace")[:200]}')
    except Exception as e:
        print(f'  Anthropic : {e}')
    return None


def normalize_brief(b):
    """Impose la forme stricte {market, positions[], watch[]}.

    Un modele reste un modele : il peut rendre `positions` en LISTE ou en OBJET
    indexe par ticker. Or Firebase refuse les cles contenant . $ # [ ] / et un
    ticker comme VUAA.DE en contient un : l ecriture repartait en HTTP 400 et le
    script mourait sur une trace brute. On ne fait donc JAMAIS confiance a la forme."""
    if not isinstance(b, dict):
        return None
    out = {'market': str(b.get('market') or '')[:1200],
           'attentisme': str(b.get('attentisme') or '')[:900],
           'semaine': [], 'positions': [], 'watch': []}
    sem = b.get('semaine')
    if isinstance(sem, dict):
        sem = list(sem.values())
    if isinstance(sem, list):
        for e in sem[:6]:
            if isinstance(e, dict) and (e.get('quoi') or e.get('what')):
                out['semaine'].append({'quand': str(e.get('quand') or '')[:60],
                                       'quoi': str(e.get('quoi') or '')[:180],
                                       'pourquoi': str(e.get('pourquoi') or '')[:220]})
            elif isinstance(e, str) and e.strip():
                out['semaine'].append({'quand': '', 'quoi': e[:180], 'pourquoi': ''})
    pos = b.get('positions')
    if isinstance(pos, dict):                       # {"META": "..."} -> liste
        pos = [{'ticker': k, 'text': v} for k, v in pos.items()]
    if isinstance(pos, list):
        for p in pos:
            tk, tx = (p.get('ticker'), p.get('text')) if isinstance(p, dict) else (None, p)
            if not tx:
                continue
            out['positions'].append({'ticker': str(tk or '')[:12], 'text': str(tx)[:400]})
    w = b.get('watch')
    if isinstance(w, dict):
        w = list(w.values())
    if isinstance(w, list):
        out['watch'] = [str(x)[:250] for x in w if x][:6]
    return out if (out['market'] or out['positions'] or out['watch'] or out['semaine']) else None


# ── Orchestration ────────────────────────────────────────────────────────────
def _parse_iso(v):
    """Le dashboard envoie du '...Z', le script du '...+00:00' : on compare des instants,
    jamais des chaines, sinon la comparaison lexicographique ment."""
    try:
        return datetime.fromisoformat(str(v).replace('Z', '+00:00'))
    except Exception:
        return None


def demande_en_attente(db):
    """True si une demande de rafraichissement est plus recente que le brief actuel."""
    req = _parse_iso((get(db, 'dashboard/morningBriefRequest') or {}).get('at'))
    if req is None:
        print('Aucune demande de rafraichissement.')
        return False
    cur = _parse_iso((get(db, 'dashboard/morningBrief') or {}).get('at'))
    if cur is not None and cur >= req:
        print('Demande deja servie (brief plus recent qu elle).')
        return False
    print(f'Demande de rafraichissement du {req.isoformat()} : on relance.')
    return True


def main():
    db = os.environ.get('FIREBASE_DB_URL')
    if not db:
        print('FIREBASE_DB_URL manquant'); sys.exit(1)

    # Mode sentinelle : lance toutes les 5 min par une tache, ne fait rien sans demande.
    if '--if-requested' in sys.argv and not demande_en_attente(db):
        return

    try:
        fg = fetch_fear_greed()
        print(f'Fear & Greed : {fg["score"]} ({fg["rating"]}), {len(fg["history"])} jours d historique')
    except Exception as e:
        print(f'Fear & Greed indisponible : {e}')
        fg = None

    meta = get(db, 'stocks/screener/positionMeta') or []
    if isinstance(meta, dict):
        meta = list(meta.values())
    lignes = [(m.get('symbol'), m.get('name') or '') for m in meta if isinstance(m, dict) and m.get('symbol')]

    # LISTE et non dict : un ticker comme VUAA.DE ferait une cle Firebase invalide.
    per_ticker, total = [], 0
    for sym, name in sorted(lignes):
        items = fetch_news(sym, name)
        if items:
            per_ticker.append({'ticker': sym, 'items': items})
            total += len(items)
        time.sleep(0.3)
    market = fetch_market_news()
    econ = fetch_econ_calendar()
    print(f'Calendrier economique : {len(econ)} evenements US retenus sur 7 jours')
    print(f'Actualites : {total} sur {len(per_ticker)} lignes, {len(market)} de marche')

    brief = None
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        print('ANTHROPIC_API_KEY absente : pas de synthese, on pousse les titres bruts.')
    elif fg:
        brief = normalize_brief(anthropic_brief(key, fg, per_ticker, market, econ))
        if brief:
            # Horodatage de l'actualite la PLUS RECENTE de chaque ligne : le modele redige,
            # il n'invente pas de date. Le dashboard l'affiche entre parentheses.
            by_tk = {g['ticker']: g['items'] for g in per_ticker}
            for p in brief['positions']:
                items = by_tk.get(p.get('ticker')) or []
                ts = max((i.get('ts') or 0) for i in items) if items else 0
                if ts:
                    p['ts'] = int(ts)
        print('Synthese : ' + ('OK' if brief else 'ECHEC (titres bruts conserves)'))

    # Resumes FRANCAIS des actualites : produits ICI et nulle part ailleurs, donc une fois par
    # jour a 07h45 et a la demande via le bouton Rafraichir (--if-requested). live_prices.py, qui
    # tourne toutes les 15 min, se borne a les recopier : la depense API reste quotidienne.
    try:
        from news_fr import resumer_groupes
        prev_news = get(db, 'dashboard/positionNews') or {}
        per_ticker = resumer_groupes(per_ticker, prev_news, api_key=key, autoriser_appel=True)
        push(db, 'dashboard/positionNews', {'at': _now_iso(), 'groups': per_ticker})
        print('Actualites resumees poussees dans dashboard/positionNews')
    except Exception as e:
        print(f'  resumes fr err : {e}')

    payload = {'at': _now_iso(), 'fearGreed': fg, 'news': per_ticker, 'econ': econ,
               'marketNews': market, 'brief': brief,
               'ok': bool(fg), 'model': ANTHROPIC_MODEL if brief else None}
    # push() ne rattrape pas ses erreurs : sans ce garde, un refus de Firebase sortait
    # en trace brute illisible au lieu de dire ce qui n allait pas.
    try:
        push(db, 'dashboard/morningBrief', payload)
        print('Brief pousse dans dashboard/morningBrief')
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:300]
        print(f'ECHEC ecriture Firebase : HTTP {e.code} {detail}')
        sys.exit(1)
    except Exception as e:
        print(f'ECHEC ecriture Firebase : {e}')
        sys.exit(1)


if __name__ == '__main__':
    main()
