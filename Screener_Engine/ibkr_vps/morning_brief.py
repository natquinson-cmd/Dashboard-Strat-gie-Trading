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


def fetch_market_news(limit=6):
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


# ── 3. Synthese Anthropic ────────────────────────────────────────────────────
PROMPT = """Tu rédiges le brief matinal du tableau de bord d'investissement d'un particulier français.

RÈGLES ABSOLUES :
- Tu rapportes des FAITS. Tu ne donnes JAMAIS de recommandation d'achat, de vente ou de conservation, ni d'objectif de cours. Ce n'est pas un conseil en investissement.
- Français naturel, sans tiret cadratin. Utilise des virgules.
- Si une ligne n'a pas d'actualité notable, tu ne l'inventes pas et tu ne la mentionnes pas.
- Sois bref. Le lecteur lit ça en deux minutes avant l'ouverture.

STRUCTURE ATTENDUE, en JSON strict et rien d'autre :
{"market": "un paragraphe de 2 à 4 phrases sur le climat général : indices, taux, macro, et ce que dit l'indice Fear & Greed",
 "positions": [{"ticker": "XXXX", "text": "1 à 2 phrases factuelles sur ce qui concerne cette ligne"}],
 "watch": ["2 à 4 faits ou échéances à surveiller aujourd'hui"]}

DONNÉES DU JOUR :
"""


def anthropic_brief(api_key, fg, per_ticker, market):
    """Retourne le dict {market, positions, watch} ou None. Ne leve jamais."""
    lignes = []
    lignes.append(f"Fear & Greed CNN : {fg['score']} ({fg['rating']}). "
                  f"Hier {fg['prev']['close']}, il y a une semaine {fg['prev']['week']}, "
                  f"un mois {fg['prev']['month']}, un an {fg['prev']['year']}.")
    comp = ', '.join(f"{k} {v['score']} ({v['rating']})" for k, v in (fg.get('components') or {}).items())
    if comp:
        lignes.append('Sous-indicateurs : ' + comp)
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
    out = {'market': str(b.get('market') or '')[:1200], 'positions': [], 'watch': []}
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
    return out if (out['market'] or out['positions'] or out['watch']) else None


# ── Orchestration ────────────────────────────────────────────────────────────
def main():
    db = os.environ.get('FIREBASE_DB_URL')
    if not db:
        print('FIREBASE_DB_URL manquant'); sys.exit(1)

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
    print(f'Actualites : {total} sur {len(per_ticker)} lignes, {len(market)} de marche')

    brief = None
    key = os.environ.get('ANTHROPIC_API_KEY')
    if not key:
        print('ANTHROPIC_API_KEY absente : pas de synthese, on pousse les titres bruts.')
    elif fg:
        brief = normalize_brief(anthropic_brief(key, fg, per_ticker, market))
        print('Synthese : ' + ('OK' if brief else 'ECHEC (titres bruts conserves)'))

    payload = {'at': _now_iso(), 'fearGreed': fg, 'news': per_ticker,
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
