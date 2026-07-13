# Collecteur quotidien Darwinex → Firebase (calendriers du dashboard)

Alimente `dashboard/darwinex/daily/<YYYY-MM-DD> = { value, pnl }` que le Trading
Dashboard lit pour les 2 calendriers Darwinex (journalier + mensuel, onglet Darwinex).

Pas d'API OAuth (host mort). On utilise les **endpoints JSON internes** de
`darwinex.com`, authentifiés par **cookie de session** (pas de 2FA sur ce compte).
Playwright garde la session ; les runs nocturnes sont headless.

## Endpoints (compte investisseur `1000025396`)
| Donnée | Endpoint |
|---|---|
| Valeur portefeuille `equity` (€) | `/api/investment/investoraccount` |
| P&L du jour (€) | `/api/investment/graphic/portfolio/pl/1000025396/1D` → dernier point |
| P&L cumulé (backfill) | `/api/investment/graphic/portfolio/pl/1000025396/ALL` |
| Dépôts | `/api/investment/graphic/portfolio/1000025396/ALL` (3ᵉ élément) |

Le P&L Darwinex est **déjà net des dépôts** → stocké directement dans `pnl`.

> ⚠️ Darwinex **bloque le login dans un navigateur piloté**. On ne se logue donc pas
> via le script : on lance un **vrai Chrome en mode débogage** où tu te connectes à la
> main, et le script s'y branche (CDP) pour lire les données. Chrome doit être installé.

## Installation (VPS Windows, à côté du PontDarwinex)
```bat
py -m pip install playwright
copy darwinex_scrape_config.example.json darwinex_scrape_config.json
:: database_secret : laisser vide ("") — les règles de la base autorisent
:: l'écriture non authentifiée (comme le dashboard).
```

## Connexion (une fois)
1. Lance **`start_chrome_debug.bat`** → un Chrome s'ouvre sur ta page portefeuille.
2. Connecte-toi à Darwinex **normalement** (le login marche), coche « Keep me logged in ».
3. Laisse ce Chrome **ouvert**. Vérifie :
```bat
py darwinex_scrape_daily.py --login      :: doit afficher "session valide"
```

## Utilisation
```bat
py darwinex_scrape_daily.py --backfill   :: reconstruit tout l'historique quotidien
py darwinex_scrape_daily.py --once       :: pousse le point du jour (value + pnl)
py darwinex_scrape_daily.py --dump       :: debug : réponses brutes
```

## Planification (Task Scheduler Windows, 00h30)
Le plus simple : lancer une fois **`darwinex_scrape_install_task.bat`** (crée la tâche
`DarwinexScraperDaily` à **00h30**, qui exécute `darwinex_scrape_run.bat` → `--backfill`).
```
schtasks /Query  /TN DarwinexScraperDaily   :: vérifier
schtasks /Run    /TN DarwinexScraperDaily   :: tester tout de suite
schtasks /Delete /TN DarwinexScraperDaily /F:: supprimer
```
**Pourquoi 00h30 + `--backfill`** : après minuit, la journée de trading est complète.
`--backfill` recalcule chaque jour à sa vraie date depuis le P&L cumulé → la veille
reçoit son P&L final, et c'est auto-correctif (comble tout trou, idempotent). Il met
aussi à jour value + invested + feesTotal (agrégat hero). Log dans `darwinex_scrape.log`.

`darwinex_scrape_run.bat` relance `start_chrome_debug.bat` si le Chrome débogué n'est
pas déjà ouvert. **Le Chrome débogué doit rester connecté** : ajoute `start_chrome_debug.bat`
au démarrage Windows (autologon) pour qu'il soit toujours dispo à 00h30.

## Session expirée
Si un run échoue (redirection login / réponse non-JSON), le script écrit
`dashboard/darwinex/collectorStatus = { status: "expired", ... }`. Dans le Chrome de
`start_chrome_debug.bat`, reconnecte-toi à Darwinex.

## Sécurité
`darwinex_scrape_config.json` et le profil `chrome_profile/` (cookies de session) sont
**gitignorés**. Ne jamais les committer.

> `darwinex_to_firebase.py` (ancien scaffold OAuth) est **obsolète** : l'API OAuth
> publique Darwinex est morte. Utiliser `darwinex_scrape_daily.py`.
