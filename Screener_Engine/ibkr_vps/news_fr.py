# -*- coding: utf-8 -*-
"""Resumes FRANCAIS des actualites des lignes detenues.

Pourquoi un resume et pas la traduction integrale : les articles sont syndiques
(Motley Fool, MT Newswires, Reuters, Benzinga), leur HTML differe chez chacun et
certains sont reserves aux abonnes ; surtout, le dashboard est publie sur GitHub
Pages, donc y stocker la copie traduite d'articles proteges serait de la
rediffusion. On produit donc une SYNTHESE (oeuvre transformative), et le texte
d'origine n'est JAMAIS conserve : il sert uniquement d'entree au modele, en
memoire, puis il est jete. Le lien vers l'article complet reste affiche.

Cache : on reprend ft/fr deja calcules pour une meme URL dans le releve precedent,
donc un article n'est jamais paye deux fois. Sans ANTHROPIC_API_KEY, la fonction
renvoie les groupes inchanges et le dashboard affiche un repli explicite.
"""
import html as _html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

ANTHROPIC_URL = 'https://api.anthropic.com/v1/messages'
MODELE = os.environ.get('ANTHROPIC_MODEL', 'claude-haiku-4-5-20251001')
UA = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
      '(KHTML, like Gecko) Chrome/124.0 Safari/537.36')
MAX_CAR_ARTICLE = 3500      # entree modele par article : au-dela on n'apprend plus rien d'utile
LOT = 6                     # articles par appel : petits lots = echec isole, pas total


RSS = 'https://feeds.finance.yahoo.com/rss/2.0/headline?s={}&region=US&lang=en-US'


def _cle(titre):
    """Cle de rapprochement titre RSS <-> titre collecte (casse et ponctuation ignorees)."""
    return re.sub(r'[^a-z0-9]+', '', (titre or '').lower())[:60]


def _descriptions_rss(ticker):
    """{cle_titre: description} depuis le flux RSS Yahoo du ticker.

    On prend le RSS et NON la page de l'article : celle-ci est rendue en JavaScript,
    on n'en tire que le menu de navigation ("Skip to navigation..."), ce qui polluerait
    le resume. Le RSS, lui, est fait pour la syndication : l'editeur y publie lui-meme
    un resume de quelques lignes, court mais propre.
    """
    out = {}
    try:
        req = urllib.request.Request(RSS.format(urllib.parse.quote(ticker)), headers={'User-Agent': UA})
        with urllib.request.urlopen(req, timeout=12) as r:
            x = r.read(300000).decode('utf-8', 'replace')
    except Exception:
        return out
    for bloc in re.findall(r'(?is)<item>(.*?)</item>', x):
        t = re.search(r'(?is)<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>', bloc)
        d = re.search(r'(?is)<description>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</description>', bloc)
        if not t or not d:
            continue
        desc = _html.unescape(re.sub(r'(?s)<[^>]+>', ' ', d.group(1)))
        desc = re.sub(r'\s+', ' ', desc).strip()
        if desc:
            out[_cle(_html.unescape(t.group(1)))] = desc[:MAX_CAR_ARTICLE]
    return out


CONSIGNE = (
    "Tu produis des fiches de lecture en FRANCAIS pour un investisseur particulier.\n"
    "Pour CHAQUE article de la liste JSON ci-dessous, rends :\n"
    "  ft = le titre traduit en francais, naturel et court ;\n"
    "  fr = un RESUME en francais de 3 a 5 phrases.\n\n"
    "Regles imperatives :\n"
    "- RESUME, ne recopie pas : reformule entierement, ne reprends aucune phrase telle quelle.\n"
    "- Tiens-toi aux faits presents dans le texte fourni. N'invente aucun chiffre, aucune date,\n"
    "  aucune citation. Si le texte est vide ou inexploitable, resume a partir du seul titre et\n"
    "  reste prudent.\n"
    "- Dis en quoi cela concerne l'entreprise citee et, si l'article le dit, l'effet sur le cours.\n"
    "- Pas de conseil d'achat ou de vente, pas de recommandation : de l'information seulement.\n"
    "- Pas de tirets cadratins, utilise des virgules.\n\n"
    "Reponds UNIQUEMENT par un tableau JSON, sans texte autour :\n"
    '[{"i": 0, "ft": "...", "fr": "..."}, ...]\n\n'
    "ARTICLES :\n")


def _appel(api_key, lots):
    body = {'model': MODELE, 'max_tokens': 2000,
            'messages': [{'role': 'user',
                          'content': CONSIGNE + json.dumps(lots, ensure_ascii=False)}]}
    try:
        req = urllib.request.Request(
            ANTHROPIC_URL, data=json.dumps(body).encode('utf-8'),
            headers={'content-type': 'application/json', 'x-api-key': api_key,
                     'anthropic-version': '2023-06-01'}, method='POST')
        with urllib.request.urlopen(req, timeout=120) as r:
            j = json.loads(r.read().decode('utf-8', 'replace'))
        txt = ''.join(b.get('text', '') for b in (j.get('content') or []) if b.get('type') == 'text')
        m = re.search(r'\[.*\]', txt, re.S)
        return json.loads(m.group(0)) if m else []
    except urllib.error.HTTPError as e:
        print(f'  resumes Anthropic HTTP {e.code} : {e.read().decode("utf-8", "replace")[:180]}')
    except Exception as e:
        print(f'  resumes Anthropic : {e}')
    return []


def resumer_groupes(groupes, prev=None, api_key=None, autoriser_appel=True):
    """Ajoute ft (titre francais) et fr (resume) a chaque article.

    groupes : [{'ticker': 'META', 'items': [{'t','u','p','ts'}, ...]}, ...]
    prev    : releve precedent (dashboard/positionNews) servant de CACHE par URL.
    Renvoie les groupes enrichis. Ne modifie rien si la cle API est absente.
    """
    api_key = api_key or os.environ.get('ANTHROPIC_API_KEY')
    if not groupes:
        return groupes
    # --- cache : ce qui a deja ete resume pour la meme URL ---
    # Applique AVANT toute sortie anticipee : un passage sans cle API, ou en mode recopie,
    # ne doit jamais effacer des resumes deja payes en les omettant du push suivant.
    cache = {}
    for g in ((prev or {}).get('groups') or []):
        for it in (g.get('items') or []):
            if it.get('u') and it.get('fr'):
                cache[it['u']] = {'ft': it.get('ft') or '', 'fr': it['fr']}

    a_faire, index = [], []
    for g in groupes:
        for it in (g.get('items') or []):
            u = it.get('u')
            if u and u in cache:
                it['ft'] = cache[u]['ft'] or it.get('t') or ''
                it['fr'] = cache[u]['fr']
                continue
            index.append(it)
            a_faire.append({'ticker': g.get('ticker'), 'titre': it.get('t') or '',
                            'source': it.get('p') or '', 'u': u or ''})

    if not a_faire:
        print(f'  resumes : {len(cache)} en cache, aucun nouvel article a traduire')
        return groupes
    if not autoriser_appel:
        # Mode RECOPIE : on conserve les resumes deja payes, on n'en produit aucun. C'est le
        # mode de live_prices.py, qui tourne toutes les 15 min : sans cela chaque passage
        # aurait facture des appels API. La production a lieu une fois par jour dans le brief.
        print(f'  resumes : {len(cache)} recopies, {len(a_faire)} sans resume (production reservee au brief)')
        return groupes
    if not api_key:
        print(f'  ANTHROPIC_API_KEY absente : {len(cache)} resume(s) conserve(s), aucun nouveau produit.')
        return groupes
    print(f'  resumes : {len(a_faire)} nouvel(s) article(s), {len(cache)} repris du cache')

    # --- matiere : resume RSS de l'editeur, un appel par ticker, garde en memoire ---
    rss = {}
    for lot in a_faire:
        tk = lot.get('ticker') or ''
        if tk and tk not in rss:
            rss[tk] = _descriptions_rss(tk)
        lot['texte'] = (rss.get(tk) or {}).get(_cle(lot.get('titre')), '')
        lot.pop('u', None)          # l'URL ne sert pas au modele
    vides = sum(1 for l in a_faire if not l['texte'])
    if vides:
        print(f'  {vides} article(s) sans resume RSS : synthese a partir du titre seul')

    # --- appels par petits lots : un echec n'emporte pas tout ---
    faits = 0
    for d in range(0, len(a_faire), LOT):
        tranche = a_faire[d:d + LOT]
        for k, lot in enumerate(tranche):
            lot['i'] = k
        for res in (_appel(api_key, tranche) or []):
            try:
                i = int(res.get('i'))
            except Exception:
                continue
            if 0 <= i < len(tranche):
                cible = index[d + i]
                if res.get('fr'):
                    cible['fr'] = str(res['fr'])[:1500]
                    cible['ft'] = str(res.get('ft') or cible.get('t') or '')[:220]
                    faits += 1
    print(f'  resumes produits : {faits}/{len(a_faire)}')
    return groupes
