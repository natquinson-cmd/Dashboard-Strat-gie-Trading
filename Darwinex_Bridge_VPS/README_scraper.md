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
:: database_secret : laisser vide ("") — les règles de la base autorisent
:: l'écriture non authentifiée (comme le dashboard). Le mettre seulement si tu
:: verrouilles les règles plus tard.
```

## Utilisation
```bat
py darwinex_scrape_daily.py --login      :: 1x : connexion manuelle dans le vrai Chrome (profil pw_profile/)
py darwinex_scrape_daily.py --backfill   :: (optionnel) reconstruit tout l'historique quotidien
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

(`--once` reste dispo pour un check manuel en journée : enregistre le jour courant.)

## Session expirée
Si un run échoue (redirection login / réponse non-JSON), le script écrit
`dashboard/darwinex/collectorStatus = { status: "expired", ... }`.
Relancer alors `--login` pour re-sauvegarder la session.

## Sécurité
`darwinex_scrape_config.json` (secret Firebase) et `pw_profile/` (cookies de
session) sont **gitignorés**. Ne jamais les committer.

> `darwinex_to_firebase.py` (ancien scaffold OAuth) est **obsolète** : l'API OAuth
> publique Darwinex est morte. Utiliser `darwinex_scrape_daily.py`.
