# firebase_push.py — ecrit un noeud JSON dans Firebase Realtime Database (REST).
# Auth, par ordre de preference :
#   1) FIREBASE_DB_SECRET (secret de base legacy)  -> ?auth=<secret>
#   2) GOOGLE_APPLICATION_CREDENTIALS (service account) -> jeton OAuth (google-auth)
#   3) aucune (fonctionne seulement si les regles RTDB autorisent l'ecriture)
import json
import os
import urllib.request


def _oauth_token():
    path = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    if not path:
        return None
    try:
        from google.oauth2 import service_account
        import google.auth.transport.requests
        scopes = ['https://www.googleapis.com/auth/firebase.database',
                  'https://www.googleapis.com/auth/userinfo.email']
        creds = service_account.Credentials.from_service_account_file(path, scopes=scopes)
        creds.refresh(google.auth.transport.requests.Request())
        return creds.token
    except Exception as e:
        print('  [firebase] google-auth indisponible:', e)
        return None


def _auth_url(db_url, path):
    url = f'{db_url.rstrip("/")}/{path}.json'
    secret = os.environ.get('FIREBASE_DB_SECRET')
    if secret:
        return url + f'?auth={secret}'
    tok = _oauth_token()
    return url + f'?access_token={tok}' if tok else url


def push(db_url, path, data):
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(_auth_url(db_url, path), data=body, method='PUT',
                                 headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status in (200, 204)


def get(db_url, path):
    try:
        with urllib.request.urlopen(urllib.request.Request(_auth_url(db_url, path)), timeout=15) as r:
            return json.loads(r.read())
    except Exception:
        return None


def get_strict(db_url, path):
    """Comme get, mais une lecture ratee (timeout, DNS, 4xx/5xx, corps illisible) LEVE une exception.
    None = noeud vraiment vide (HTTP 200, corps null). A utiliser avant de reecrire un noeud entier :
    avec get, une panne de lecture ressemble a un noeud vide et le PUT suivant efface tout."""
    with urllib.request.urlopen(urllib.request.Request(_auth_url(db_url, path)), timeout=15) as r:
        if r.status != 200:
            raise RuntimeError(f'HTTP {r.status}')
        return json.loads(r.read())


def patch(db_url, path, data):
    """Mise a jour PARTIELLE (PATCH) : seules les cles fournies sont ecrites, le reste du noeud est intact."""
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(_auth_url(db_url, path), data=body, method='PATCH',
                                 headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status in (200, 204)
