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
from datetime import datetime, timezone, timedelta, date, time as dtime

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
    # Un point par jour, VRAIMENT : CNN renvoie deux fois le point du jour en cours. Sans
    # dedoublonnage la courbe portait un noeud double et le compteur de jours mentait.
    par_jour = {}
    for p in hist:
        try:
            d = datetime.fromtimestamp(p['x'] / 1000, timezone.utc).strftime('%Y-%m-%d')
            par_jour[d] = round(float(p['y']), 1)
        except Exception:
            continue
    series = [{'d': d, 'v': par_jour[d]} for d in sorted(par_jour)]
    comps, calc_ms = {}, 0
    for k, v in j.items():
        if k in ('fear_and_greed', 'fear_and_greed_historical') or not isinstance(v, dict):
            continue
        if v.get('score') is None:
            continue
        comps[k] = {'score': round(float(v['score']), 1), 'rating': v.get('rating')}
        try:
            calc_ms = max(calc_ms, int(float(v.get('timestamp') or 0)))
        except Exception:
            pass
    return {
        'score': round(float(f.get('score') or 0), 1),
        'rating': f.get('rating'),
        'at': f.get('timestamp'),
        # Vrai instant de CALCUL, et non la date de seance. `at` vaut deja aujourd'hui a 8 h du
        # matin alors que l'indice n'a pas bouge depuis la cloture de la veille : l'afficher
        # laissait croire a une valeur du jour. Les sous-indicateurs, eux, portent l'heure a
        # laquelle ils ont ete calcules, c'est la seule fraicheur honnete.
        'calcAt': (datetime.fromtimestamp(calc_ms / 1000, timezone.utc)
                   .replace(microsecond=0).isoformat() if calc_ms else None),
        'fetchedAt': _now_iso(),
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


NASDAQ_ECON = 'https://api.nasdaq.com/api/calendar/economicevents?date='
JOURS_FR = ['lundi', 'mardi', 'mercredi', 'jeudi', 'vendredi', 'samedi', 'dimanche']
MOIS_FR = ['janvier', 'février', 'mars', 'avril', 'mai', 'juin', 'juillet', 'août',
           'septembre', 'octobre', 'novembre', 'décembre']


def _nieme_dimanche(an, mois, n):
    """Date du n-ieme dimanche du mois. n = -1 pour le dernier."""
    d = date(an, mois, 1)
    premier = d + timedelta(days=(6 - d.weekday()) % 7)
    if n > 0:
        return premier + timedelta(days=7 * (n - 1))
    dernier = premier
    while (dernier + timedelta(days=7)).month == mois:
        dernier += timedelta(days=7)
    return dernier


def ny_vers_paris(d_ny):
    """datetime NAIF en heure de New York -> datetime NAIF en heure de Paris.

    L'ecart n'est pas constant : il vaut 6 h la majeure partie de l'annee, mais 5 h entre la
    fin de l'heure d'ete europeenne (dernier dimanche d'octobre) et celle des Etats-Unis
    (premier dimanche de novembre). Le coder en dur ferait mentir le calendrier deux semaines
    par an, precisement autour d'une reunion de la Fed.

    zoneinfo fait le travail proprement, mais sous Windows il exige le paquet tzdata, qui peut
    manquer sur le VPS. On retombe alors sur les regles officielles, inchangees depuis 2007
    cote americain et depuis 2002 cote europeen."""
    try:
        from zoneinfo import ZoneInfo
        return (d_ny.replace(tzinfo=ZoneInfo('America/New_York'))
                    .astimezone(ZoneInfo('Europe/Paris')).replace(tzinfo=None))
    except Exception:
        return _ny_vers_paris_regles(d_ny)


def _ny_vers_paris_regles(d_ny):
    """Secours sans tzdata : les regles officielles appliquees a la main."""
    # 3 h et non 2 h au printemps : entre 02h00 et 03h00 l'heure locale n'existe pas ce jour-la
    # (la pendule saute), et zoneinfo la rattache a l'heure d'hiver. On fait pareil.
    deb = datetime.combine(_nieme_dimanche(d_ny.year, 3, 2), dtime(3, 0))
    fin = datetime.combine(_nieme_dimanche(d_ny.year, 11, 1), dtime(2, 0))
    u = d_ny + timedelta(hours=(4 if deb <= d_ny < fin else 5))          # -> UTC
    deb_eu = datetime.combine(_nieme_dimanche(u.year, 3, -1), dtime(1, 0))
    fin_eu = datetime.combine(_nieme_dimanche(u.year, 10, -1), dtime(1, 0))
    return u + timedelta(hours=(2 if deb_eu <= u < fin_eu else 1))       # -> Paris


def _decalage_nasdaq():
    """Nombre de jours a AJOUTER a la date voulue pour l'obtenir de Nasdaq.

    Nasdaq rend, pour date=J, les evenements de J-1. Constate le 10/09/2026 : la requete du
    vendredi 11 renvoyait les inscriptions au chomage, publiees TOUS les jeudis, et celle du
    samedi 12 l'enquete Michigan, publiee TOUS les vendredis. Resultat, le brief annoncait le
    CPI un samedi, jour ou aucune statistique ne sort.

    On ne code pas ce decalage en dur : on le MESURE a chaque execution sur un ancrage
    hebdomadaire infaillible. Si Nasdaq corrige son API un jour, on suivra sans rien casser ;
    en le figeant on se serait remis a mentir en silence."""
    d = datetime.now()
    jeudi = d + timedelta(days=(3 - d.weekday()) % 7)      # prochain jeudi, aujourd'hui si jeudi
    for off in (1, 0):
        try:
            j = _get_json(NASDAQ_ECON + (jeudi + timedelta(days=off)).strftime('%Y-%m-%d'))
        except Exception:
            continue
        noms = ' | '.join(str(r.get('eventName') or '')
                          for r in ((j.get('data') or {}).get('rows') or []))
        if 'Initial Jobless Claims' in noms:
            print(f'  calendrier Nasdaq : decalage mesure = {off} jour(s)')
            return off
    print('  calendrier Nasdaq : decalage non mesurable, on garde 1 (comportement constate)')
    return 1


def fetch_econ_calendar(days=7):
    """Evenements macro US des `days` prochains jours, dates FIABLES (contrairement aux
    articles de presse, qui evoquent les rendez-vous sans toujours les dater)."""
    off = _decalage_nasdaq()
    out, vus = [], set()
    for k in range(days):
        cible = datetime.now() + timedelta(days=k)
        jour = cible.strftime('%Y-%m-%d')
        try:
            j = _get_json(NASDAQ_ECON + (cible + timedelta(days=off)).strftime('%Y-%m-%d'))
        except Exception as e:
            print(f'  calendrier {jour} : {e}')
            continue
        for r in ((j.get('data') or {}).get('rows') or []):
            if 'united states' not in str(r.get('country') or '').lower():
                continue
            nom = re.sub(r'<[^>]*>', '', str(r.get('eventName') or '')).strip()
            if not nom or not ECON_CLES.search(nom):
                continue
            # Nasdaq nomme son champ `gmt`, mais il contient l'heure de NEW YORK. Verifie deux
            # fois : le CPI y est a 08:30, l'heure de publication du BLS, et le CPI allemand a
            # 02:00, soit 08:00 a Berlin. On passe a l'heure de Paris, la seule qui serve ici,
            # en convertissant la DATE AUSSI : une intervention a 21:15 a New York tombe le
            # lendemain a Paris, et l'annoncer le bon jour importe autant que la bonne heure.
            quand, heure = cible, ''
            m = re.match(r'^(\d{1,2}):(\d{2})$', str(r.get('gmt') or '').strip())
            if m:
                quand = ny_vers_paris(datetime(cible.year, cible.month, cible.day,
                                               int(m.group(1)), int(m.group(2))))
                heure = quand.strftime('%Hh%M')
            jour_pa = quand.strftime('%Y-%m-%d')
            cle = (jour_pa, nom, str(r.get('consensus') or ''))
            if cle in vus:
                continue
            vus.add(cle)
            # `libelle` est fourni tout fait au modele : lui laisser deduire le jour de la
            # semaine a partir d'une date ISO, c'est une occasion de plus de se tromper.
            out.append({'date': jour_pa, 'heure': heure,
                        'jour': JOURS_FR[quand.weekday()],
                        'libelle': f'{JOURS_FR[quand.weekday()]} {quand.day} {MOIS_FR[quand.month - 1]}',
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

TRI DES LIGNES DÉTENUES, RÈGLE DÉCISIVE :
- Tu ne commentes PAS chaque ligne. Tu n'en retiens QUE celles dont l'actualité mérite qu'on
  s'y arrête, CINQ AU MAXIMUM, classées de la plus importante à la moins importante. Deux ou
  trois lignes valent mieux que neuf. Si aucune ne passe le test, tu rends une liste vide.
- Une ligne mérite d'être citée si, et seulement si, l'un de ces cas est vérifié :
  le titre a nettement bougé (environ 3 % ou plus) et l'article dit pourquoi ; des résultats,
  une prévision ou un chiffre d'activité viennent d'être publiés ; une décision de justice,
  de régulateur ou d'autorité de concurrence tombe ; une acquisition, une cession ou une
  fusion est annoncée, bloquée ou abandonnée ; un dirigeant change ; un contrat, une commande
  ou un investissement chiffré et significatif est signé ; le dividende ou un rachat d'actions
  évolue.
- Tu ÉCARTES sans hésiter : les annonces de partenariat sans montant, les lancements de
  produit sans effet chiffré, les initiatives éducatives ou caritatives, les articles
  sectoriels où la société n'est qu'un exemple parmi d'autres, les rétrospectives du genre
  « 10 000 dollars investis il y a dix ans », les avis d'analystes qui n'apportent aucun fait
  nouveau, et tout ce qui aurait pu être écrit la semaine dernière.
- Le test, en une phrase : est-ce que cela change quelque chose à la façon dont le lecteur
  regarde sa ligne ce matin ? Si la réponse est non, tu l'omets.
- Pas de phrase de remplissage, pas de reformulation de ce que le chiffre dit déjà.

STYLE, RÈGLE STRICTE :
- Tu écris des PHRASES COMPLÈTES, en français correct : articles, verbes conjugués, liaisons
  logiques. Le style télégraphique est INTERDIT. "Q3 revenus record accélérateurs IA
  personnalisés" ne veut rien dire ; écris "Broadcom a publié un chiffre d'affaires trimestriel
  record, tiré par ses accélérateurs d'IA personnalisés."
- Tu peux être dense, jamais elliptique. Le lecteur doit comprendre du premier coup, sans
  reconstituer mentalement les mots manquants.
- Tu relies les faits entre eux quand ils s'expliquent : "les rendements montent, DONC les
  valeurs de croissance reculent" vaut mieux que deux constats côte à côte.

MISE EN GRAS :
- Encadre de **doubles astérisques** les deux ou trois éléments qui portent le sens dans chaque
  texte : un chiffre, un nom d'entreprise, une date, le mot décisif. Jamais plus de trois par
  champ, sinon plus rien ne ressort.

HEURES :
- Les heures du calendrier sont DÉJÀ en heure de Paris. Tu les recopies telles quelles et tu ne
  convertis rien. Tu n'écris jamais "heure de New York".

RÈGLE SUR LE SENS DES OPÉRATIONS, AUSSI IMPORTANTE QUE LES DATES :
- Un titre d'article ne dit presque jamais QUI achète et QUI vend. "X Vs Y: rotation de 56 M$"
  ne dit pas le sens. Quand une ligne "RÉSUMÉ DE L'ARTICLE" suit un titre, c'est ELLE qui fait
  foi, elle est tirée du corps de l'article.
- Sans résumé, tu ne DÉDUIS JAMAIS le sens d'une opération, d'une hausse ou d'une baisse à
  partir d'un titre ambigu. Tu écris ce que le titre dit, pas plus. Se tromper de sens, c'est
  dire l'exact contraire de la réalité au lecteur.

RÈGLE SUR LES DATES, LA PLUS IMPORTANTE :
- Le CALENDRIER ÉCONOMIQUE ci-dessous est une source FIABLE : cite ses dates, ses heures et
  ses consensus sans hésiter, ce sont les échéances qui comptent pour la semaine.
- Chaque ligne du calendrier commence par un libellé du type "jeudi 10 septembre". RECOPIE-LE
  TEL QUEL. Tu ne recalcules JAMAIS un jour de la semaine à partir d'une date, tu ne décales
  jamais d'un jour. Aucune statistique américaine ne sort un samedi ni un dimanche : si tu
  t'apprêtes à écrire un tel jour, c'est que tu t'es trompé.
- Pour tout le reste, tu ne cites une échéance QUE si elle apparaît dans les données fournies.
- Tu n'écris JAMAIS une date de mémoire. Si un article mentionne un rendez-vous sans le dater,
  dis "prochainement" plutôt que d'inventer un jour.

STRUCTURE ATTENDUE, en JSON strict et rien d'autre :
{"market": "un paragraphe d'analyse de 4 à 5 phrases, la pièce maîtresse du brief. Dense mais pas bavard : chaque phrase apporte un fait ou un lien de cause, aucune ne reformule la précédente. Tu n'énumères pas, tu EXPLIQUES : ce qui bouge et par quel mécanisme, ce que les rendements obligataires et les matières premières font aux actions et pourquoi, ce que disent les sous-indicateurs du Fear & Greed et surtout ceux qui se CONTREDISENT entre eux, ce que cela révèle du positionnement des investisseurs, et ce qui distingue aujourd'hui des séances précédentes. Chaque affirmation est reliée à sa cause.",
 "attentisme": "2 à 4 phrases complètes sur ce qui peut faire bouger la séance AUJOURD'HUI, DANS UN SENS COMME DANS L'AUTRE. Ce champ n'est pas orienté à la baisse : si les données pointent vers un rebond, un catalyseur favorable ou une simple absence d'enjeu, tu l'écris aussi franchement que tu écrirais une menace. Rendez-vous macro ou résultats attendus, sous-indicateurs du Fear & Greed qui divergent. Chaîne de causalité explicite avec les deux branches, ce qui se passe si le chiffre surprend à la hausse et à la baisse. Si rien de notable ne ressort des données, dis-le.",
 "semaine": [{"quand": "le libellé du calendrier RECOPIÉ tel quel, court, ex : jeudi 10 septembre. Rien d'autre, ni heure ni fuseau", "quoi": "une phrase complète : l'échéance, son heure de Paris, son consensus et son précédent s'ils existent", "pourquoi": "une phrase complète expliquant en quoi elle compte pour un portefeuille d'actions américaines"}],
 "positions": [{"ticker": "XXXX", "text": "1 à 2 phrases complètes et factuelles : le fait, et pourquoi il compte si l'article le dit. Au plus 5 entrées dans cette liste, uniquement celles qui passent le test de matérialité ci-dessus, les plus importantes d'abord"}],
 "watch": ["2 à 4 points à surveiller aujourd'hui, une phrase complète chacun"]}

DONNÉES DU JOUR :
"""


def _referme(frag):
    """Referme les niveaux restes ouverts dans un fragment JSON coupe."""
    pile, chaine, echap = [], False, False
    for c in frag:
        if echap:
            echap = False
        elif c == '\\':
            echap = True
        elif c == '"':
            chaine = not chaine
        elif not chaine:
            if c in '{[':
                pile.append(c)
            elif c in '}]' and pile:
                pile.pop()
    out = frag + ('"' if chaine else '')
    for c in reversed(pile):
        out += '}' if c == '{' else ']'
    return out


def _points_de_coupe(brut):
    """Endroits ou amputer un JSON tronque sans casser un element : juste apres un } ou un ],
    ou juste avant une virgule. Rendus du plus tardif au plus tot, pour garder le maximum."""
    pts, chaine, echap = [], False, False
    for k, c in enumerate(brut):
        if echap:
            echap = False
        elif c == '\\':
            echap = True
        elif c == '"':
            chaine = not chaine
        elif not chaine:
            if c in '}]':
                pts.append(k + 1)
            elif c == ',':
                pts.append(k)
    pts.reverse()
    return pts[:60]


def _extraire_json(txt):
    """Isole l'objet JSON de la reponse. Retourne (objet, souci) : souci vaut None quand
    tout va bien, sinon il dit ce qui a manque.

    Deux pieges, les deux vus en production :
    - le modele encadre parfois son JSON de texte ou de balises ```json ;
    - surtout, la reponse peut etre COUPEE NET quand elle bute sur max_tokens. L'ancienne
      extraction (une regex gloutonne du premier { au dernier }) rendait alors un fragment
      invalide, json.loads levait, et TOUT le brief partait a la poubelle au profit des
      titres bruts. On repare desormais : on ampute le dernier element incomplet et on
      referme les niveaux ouverts. Un brief a onze positions sur douze vaut mieux que rien."""
    i = txt.find('{')
    if i < 0:
        return None, 'aucun objet JSON dans la reponse du modele'
    brut = txt[i:]
    j = brut.rfind('}')
    while j > 0:
        try:
            return json.loads(brut[:j + 1]), None
        except Exception:
            j = brut.rfind('}', 0, j)
    for fin in _points_de_coupe(brut):
        try:
            return json.loads(_referme(brut[:fin])), 'reponse tronquee, brief reconstitue en partie'
        except Exception:
            continue
    return None, 'reponse tronquee et irrecuperable'


def anthropic_brief(api_key, fg, per_ticker, market, econ=None):
    """Retourne (dict {market, ...} ou None, souci ou None). Ne leve jamais."""
    lignes = []
    d = datetime.now()
    lignes.append(f"Nous sommes le {JOURS_FR[d.weekday()]} {d.day} {MOIS_FR[d.month - 1]} {d.year}.")
    lignes.append(f"Fear & Greed CNN : {fg['score']} ({fg['rating']}). "
                  f"Hier {fg['prev']['close']}, il y a une semaine {fg['prev']['week']}, "
                  f"un mois {fg['prev']['month']}, un an {fg['prev']['year']}.")
    comp = ', '.join(f"{k} {v['score']} ({v['rating']})" for k, v in (fg.get('components') or {}).items())
    if comp:
        lignes.append('Sous-indicateurs : ' + comp)
    if econ:
        lignes.append('\nCALENDRIER ÉCONOMIQUE AMÉRICAIN (dates fiables, DÉJÀ converties en heure de Paris) :')
        for e in econ:
            det = []
            if e.get('consensus'):
                det.append('consensus ' + e['consensus'])
            if e.get('precedent'):
                det.append('précédent ' + e['precedent'])
            lignes.append(f"- {e.get('libelle') or e['date']} a {e.get('heure', '')} : {e['nom']}"
                          + (' (' + ', '.join(det) + ')' if det else ''))
    lignes.append('\nACTUALITÉS DE MARCHÉ :')
    for n in market:
        lignes.append(f"- [{n.get('p')}] {n['t']}")
    lignes.append('\nACTUALITÉS DES LIGNES DÉTENUES :')
    for grp in per_ticker:
        for n in grp['items']:
            lignes.append(f"- {grp['ticker']} [{n.get('p')}] {n['t']}")
            # Le resume est lu dans le CORPS de l'article : c'est lui qui porte le sens de
            # l'operation, la que le titre reste souvent ambigu.
            resume = str(n.get('fr') or '').strip()
            if resume:
                lignes.append(f"    RESUME DE L'ARTICLE : {resume[:500]}")
    body = {
        'model': ANTHROPIC_MODEL,
        # 6000. La reponse complete demandait deja 2100 jetons avec l'attentisme, la semaine et
        # le calendrier ; le retour aux phrases completes et au paragraphe d'analyse en demande
        # nettement plus. A 1500, elle etait coupee net, le JSON devenait illisible et le brief
        # tombait en silence sur les titres bruts. C'est un plafond, pas une depense : on ne paie
        # que ce qui est reellement ecrit.
        'max_tokens': 6000,
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
        u = j.get('usage') or {}
        print(f"  Anthropic : {u.get('input_tokens')} jetons en entree, {u.get('output_tokens')} "
              f"en sortie, arret sur {j.get('stop_reason')}")
        data, souci = _extraire_json(txt)
        if j.get('stop_reason') == 'max_tokens':
            souci = (souci + ', ' if souci else '') + 'butee sur max_tokens'
        return data, souci
    except urllib.error.HTTPError as e:
        detail = e.read().decode('utf-8', 'replace')[:200]
        print(f'  Anthropic HTTP {e.code} : {detail}')
        return None, f'HTTP {e.code} : {detail[:130]}'
    except Exception as e:
        print(f'  Anthropic : {e}')
        return None, f'{type(e).__name__} : {str(e)[:130]}'


def normalize_brief(b):
    """Impose la forme stricte {market, positions[], watch[]}.

    Un modele reste un modele : il peut rendre `positions` en LISTE ou en OBJET
    indexe par ticker. Or Firebase refuse les cles contenant . $ # [ ] / et un
    ticker comme VUAA.DE en contient un : l ecriture repartait en HTTP 400 et le
    script mourait sur une trace brute. On ne fait donc JAMAIS confiance a la forme."""
    if not isinstance(b, dict):
        return None
    # Plafonds larges et non serres : ils ne sont la que comme garde-fou contre un modele qui
    # part en boucle, pas pour raccourcir. Un plafond atteint couperait en plein milieu d'une
    # phrase, ce qui serait la enieme degradation silencieuse.
    out = {'market': str(b.get('market') or '')[:2200],
           'attentisme': str(b.get('attentisme') or '')[:1400],
           'semaine': [], 'positions': [], 'watch': []}
    sem = b.get('semaine')
    if isinstance(sem, dict):
        sem = list(sem.values())
    if isinstance(sem, list):
        for e in sem[:6]:
            if isinstance(e, dict) and (e.get('quoi') or e.get('what')):
                out['semaine'].append({'quand': str(e.get('quand') or '')[:60],
                                       'quoi': str(e.get('quoi') or '')[:320],
                                       'pourquoi': str(e.get('pourquoi') or '')[:340]})
            elif isinstance(e, str) and e.strip():
                out['semaine'].append({'quand': '', 'quoi': e[:320], 'pourquoi': ''})
    pos = b.get('positions')
    if isinstance(pos, dict):                       # {"META": "..."} -> liste
        pos = [{'ticker': k, 'text': v} for k, v in pos.items()]
    if isinstance(pos, list):
        for p in pos:
            tk, tx = (p.get('ticker'), p.get('text')) if isinstance(p, dict) else (None, p)
            if not tx:
                continue
            out['positions'].append({'ticker': str(tk or '')[:12], 'text': str(tx)[:520]})
        # Le plafond de 5 est aussi impose ICI et pas seulement demande dans le prompt : une
        # consigne de tri est ce qu'un modele oublie en premier quand il a neuf articles sous
        # les yeux. Le modele classe du plus important au moins important, on tronque la queue.
        out['positions'] = out['positions'][:5]
    w = b.get('watch')
    if isinstance(w, dict):
        w = list(w.values())
    if isinstance(w, list):
        out['watch'] = [str(x)[:320] for x in w if x][:6]
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

    key = os.environ.get('ANTHROPIC_API_KEY')

    # Resumes FRANCAIS des actualites : produits ICI et nulle part ailleurs, donc une fois par
    # jour a 07h45 et a la demande via le bouton Rafraichir (--if-requested). live_prices.py, qui
    # tourne toutes les 15 min, se borne a les recopier : la depense API reste quotidienne.
    #
    # Et AVANT la synthese, non apres. Le brief ne voyait que les TITRES, qui ne disent pas
    # toujours le sens d'une operation : le 10/09/2026, "META Vs GOOGL: Cathie Wood's ARK Makes
    # A Nearly $56M Mega-Cap Tech Rotation" ne dit pas qui est achete, et le modele a ecrit
    # « ARK vend Meta au profit de Google » alors qu'ARK ACHETAIT Meta et VENDAIT Alphabet. Le
    # resume francais, lui, lit le corps de l'article et avait juste. On le lui donne donc.
    try:
        from news_fr import resumer_groupes
        prev_news = get(db, 'dashboard/positionNews') or {}
        per_ticker = resumer_groupes(per_ticker, prev_news, api_key=key, autoriser_appel=True)
        push(db, 'dashboard/positionNews', {'at': _now_iso(), 'groups': per_ticker})
        print('Actualites resumees poussees dans dashboard/positionNews')
    except Exception as e:
        print(f'  resumes fr err : {e}')

    # brief_err voyage jusqu'au dashboard : un echec muet de la synthese s'y lisait
    # « synthese indisponible », ce qui ne dit rien et oblige a fouiller les logs du VPS.
    brief, brief_err = None, None
    if not key:
        brief_err = 'ANTHROPIC_API_KEY absente sur le VPS'
        print('ANTHROPIC_API_KEY absente : pas de synthese, on pousse les titres bruts.')
    elif not fg:
        brief_err = 'Fear & Greed indisponible, synthese non tentee'
    else:
        brut, brief_err = anthropic_brief(key, fg, per_ticker, market, econ)
        brief = normalize_brief(brut)
        if brut is not None and brief is None:
            brief_err = brief_err or 'reponse du modele inexploitable'
        if brief:
            # Horodatage de l'actualite la PLUS RECENTE de chaque ligne : le modele redige,
            # il n'invente pas de date. Le dashboard l'affiche entre parentheses.
            by_tk = {g['ticker']: g['items'] for g in per_ticker}
            for p in brief['positions']:
                items = by_tk.get(p.get('ticker')) or []
                ts = max((i.get('ts') or 0) for i in items) if items else 0
                if ts:
                    p['ts'] = int(ts)
        print('Synthese : ' + ('OK' if brief else 'ECHEC (titres bruts conserves)')
              + (' - ' + brief_err if brief_err else ''))

    payload = {'at': _now_iso(), 'fearGreed': fg, 'news': per_ticker, 'econ': econ,
               'marketNews': market, 'brief': brief, 'briefError': brief_err,
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
