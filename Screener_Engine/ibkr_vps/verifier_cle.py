# verifier_cle.py : verifie que la cle secrete de la base Firebase (variable FIREBASE_DB_SECRET) est posee et
# VALIDE sur cette machine, sans jamais l'afficher. Test en lecture seule : les regles de la base
# (.settings/rules) ne se lisent qu'avec la cle administrateur ; 200 = cle valide, 401/403 = cle absente, fausse
# ou revoquee. Une lecture de donnees ne prouverait rien tant que la base est ouverte : Firebase y accepte meme
# une cle fausse. Si la cle est valide, affiche aussi la derniere ecriture de chaque collecteur (cours, pont,
# synchro IG, brief, screener) : une fois la base verrouillee, c est le seul moyen de la lire hors du dashboard.
# Usage : verifier_cle.bat (VPS) ou « python verifier_cle.py » (PC du Stream Deck), dans une NOUVELLE fenetre
# ouverte apres le setx : une fenetre deja ouverte ne voit pas la nouvelle variable.
import json
import os
import sys
from datetime import datetime, timezone
import urllib.error
import urllib.parse
import urllib.request

DB = os.environ.get('FIREBASE_DB_URL') or 'https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com'


# Derniere ecriture de chaque collecteur : une fois la base verrouillee, seule la cle permet de la lire.
COLLECTEURS = [
    ('Cours (toutes les 5 min)', 'stocks/screener/livePrices/generatedAt'),
    ('Pont IG', 'dashboard/pontIG/at'),
    ('Synchro IG', 'igSyncStatus/at'),
    ('Brief du matin', 'dashboard/morningBrief/at'),
    ('Screener', 'stocks/screener/quality/generatedAt'),
]


def _instant(v):
    """Horodatage Firebase (millisecondes ou texte ISO) -> datetime UTC, None si illisible."""
    if isinstance(v, (int, float)):
        return datetime.fromtimestamp(v / 1000, timezone.utc)
    if isinstance(v, str) and v:
        try:
            t = datetime.fromisoformat(v.replace('Z', '+00:00'))
            return t if t.tzinfo else t.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


def _age(t, maintenant):
    m = int((maintenant - t).total_seconds() // 60)
    if m < 60:
        return 'il y a %d min' % m
    if m < 48 * 60:
        return 'il y a %d h %02d' % (m // 60, m % 60)
    return 'il y a %d jours' % (m // 1440)


def fraicheur(cle):
    print('')
    print('Derniere ecriture des collecteurs :')
    maintenant = datetime.now(timezone.utc)
    for nom, chemin in COLLECTEURS:
        url = DB.rstrip('/') + '/' + chemin + '.json?auth=' + urllib.parse.quote(cle, safe='')
        try:
            with urllib.request.urlopen(url, timeout=20) as r:
                t = _instant(json.loads(r.read().decode('utf-8')))
            txt = (t.astimezone().strftime('%d/%m %H:%M') + ', ' + _age(t, maintenant)) if t else 'aucune date'
        except Exception as e:
            txt = 'lecture impossible (%s)' % type(e).__name__
        print('  %-26s %s' % (nom, txt))


def main():
    brute = os.environ.get('FIREBASE_DB_SECRET') or ''
    cle = brute.strip()
    if not cle:
        print('ECHEC : la variable FIREBASE_DB_SECRET est absente de cette fenetre.')
        print('  VPS : setx /M FIREBASE_DB_SECRET "..." dans un CMD administrateur, puis ouvre une NOUVELLE fenetre.')
        print('  PC  : setx FIREBASE_DB_SECRET "..." puis ouvre une NOUVELLE fenetre.')
        return 1
    if cle != brute:
        print('ATTENTION : la cle commence ou finit par un espace, les scripts l\'enverraient tel quel. Refais le setx.')
        return 4
    url = DB.rstrip('/') + '/.settings/rules.json?auth=' + urllib.parse.quote(cle, safe='')
    try:
        with urllib.request.urlopen(url, timeout=20) as r:
            r.read()
        print('OK : cle valide (%d caracteres), acces administrateur a la base confirme.' % len(cle))
        fraicheur(cle)
        return 0
    except urllib.error.HTTPError as e:
        print('ECHEC : cle refusee par Firebase (HTTP %d). Recopie-la depuis la console :' % e.code)
        print('  Parametres du projet, Comptes de service, Codes secrets de la base de donnees.')
        return 2
    except Exception as e:
        print('ECHEC : Firebase injoignable (%s : %s). Verifie le reseau puis relance.' % (type(e).__name__, e))
        return 3


if __name__ == '__main__':
    sys.exit(main())
