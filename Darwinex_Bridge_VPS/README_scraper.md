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

## Installation (VPS Windows, à côté du PontDarwinex)
```bat
py -m pip install playwright
py -m playwright install chromium
copy darwinex_scrape_config.example.json darwinex_scrape_config.json
:: éditer darwinex_scrape_config.json : mettre le database_secret Firebase
```

## Utilisation
```bat
py darwinex_scrape_daily.py --login      :: 1x : connexion manuelle, sauvegarde storage_state.json
py darwinex_scrape_daily.py --backfill   :: (optionnel) reconstruit tout l'historique quotidien
py darwinex_scrape_daily.py --once       :: pousse le point du jour (value + pnl)
py darwinex_scrape_daily.py --dump       :: debug : réponses brutes
```

## Planification (Task Scheduler Windows, ~23h30)
Le plus simple : lancer une fois **`darwinex_scrape_install_task.bat`** (crée la tâche
`DarwinexScraperDaily` à 23h30, qui exécute `darwinex_scrape_run.bat` → `--once`).
```
schtasks /Query  /TN DarwinexScraperDaily   :: vérifier
schtasks /Run    /TN DarwinexScraperDaily   :: tester tout de suite
schtasks /Delete /TN DarwinexScraperDaily /F:: supprimer
```
`--once` à 23h30 capture le P&L de fin de journée (dernier point de `/1D`) et met à
jour value + pnl + invested + feesTotal. Log dans `darwinex_scrape.log`.

## Session expirée
Si un run échoue (redirection login / réponse non-JSON), le script écrit
`dashboard/darwinex/collectorStatus = { status: "expired", ... }`.
Relancer alors `--login` pour re-sauvegarder la session.

## Sécurité
`darwinex_scrape_config.json` (secret Firebase) et `storage_state.json` (cookies de
session) sont **gitignorés**. Ne jamais les committer.

> `darwinex_to_firebase.py` (ancien scaffold OAuth) est **obsolète** : l'API OAuth
> publique Darwinex est morte. Utiliser `darwinex_scrape_daily.py`.
