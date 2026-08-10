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


def push(db_url, path, data):
    db_url = db_url.rstrip('/')
    url = f'{db_url}/{path}.json'
    secret = os.environ.get('FIREBASE_DB_SECRET')
    if secret:
        url += f'?auth={secret}'
    else:
        tok = _oauth_token()
        if tok:
            url += f'?access_token={tok}'
    body = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(url, data=body, method='PUT',
                                 headers={'content-type': 'application/json'})
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status in (200, 204)
