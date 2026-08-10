# Screener growth pré-cassure — service VPS (Option C, 100 % gratuit)

Tout le moteur tourne sur ton **VPS**, source de données **gratuite (Yahoo Finance)**, plus de Cloudflare Worker ni de FMP payant. IBKR est un **enrichissement optionnel** (momentum précis + positions live). Push dans **Firebase**, lu par le dashboard.

```
Yahoo screener (univers US croissance+cap)  ─┐
Yahoo quoteSummary (fondamentaux + prix)     ─┤ run.py (VPS)
                                              │  scoring PRE-CASSURE (screen.py)
IB Gateway (optionnel : momentum + positions) ┘        │
                                                        ▼
                                                   Firebase  ──►  Dashboard (onglet Screener)
                                             stocks/screener/latest + /positions
```

## Pourquoi le VPS et pas le Worker

Le screener de FMP est passé payant (HTTP 402). Le remplaçant gratuit est le screener non officiel de Yahoo, mais il **throttle les IP partagées** (Cloudflare). Depuis un **VPS** (IP normale, peu sollicitée), il répond de façon fiable. On consolide donc tout sur le VPS.

## Pièces

- `yahoo.py` : source gratuite. `screen()` (univers filtré côté serveur) + `quote_summary()` (fondamentaux + prix + MM50/200 + 52s-haut). Gère cookie/crumb + retries.
- `screen.py` : scoring **pré-cassure** (garde-fous, gate growth, percentiles sectoriels, bonus consolidation sous résistance). Pur, testé (`test_screen.py`).
- `momentum.py` : momentum depuis barres IBKR (enrichissement optionnel). Testé (`test_momentum.py`).
- `ibkr_client.py` : `ib_async` lecture seule (momentum, positions, tradabilité) — optionnel.
- `firebase_push.py` : écriture RTDB (secret legacy ou compte de service).
- `run.py` : orchestrateur.

## Mise en place sur le VPS Windows

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Puis teste SANS rien pousser (valide Yahoo + le scoring) :

```
set FIREBASE_DB_URL=
.venv\Scripts\python run.py --no-push --limit=40
```

Ça doit lister un top de candidates avec leurs flags (`pré-cassure`, `CA+40%`, ...). Ensuite branche Firebase :

```
set FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com
set FIREBASE_DB_SECRET=ton_secret
.venv\Scripts\python run.py
```

Ouvre l'onglet **Screener** du dashboard : le classement s'affiche (lu depuis Firebase).

Planifie `run.py` dans le **Planificateur de tâches** chaque jour ouvré (ex. 06:00). Un wrapper `run_screener.bat` est fourni (adapte les variables).

## Enrichissement IBKR (optionnel, live)

Quand tu veux le momentum précis + tes positions live : installe IB Gateway + IBC (voir plus bas), puis :

```
set ENABLE_IBKR=true
set IBKR_PORT=4001
.venv\Scripts\python run.py
```

IB Gateway headless piloté par **IBC** (auto-restart, API Read-Only port 4001, Trusted IP 127.0.0.1). 2FA validé **une fois par semaine** via l'app mobile IBKR. Souscris les market data US temps réel (~qq \$/mois) pour un momentum non différé. Si IBKR est indisponible, le run bascule automatiquement sur le classement Yahoo seul.

## Réglages (variables d'env)

Cible **small/mid caps « prêtes à exploser »** : mega caps EXCLUES, OTC/étranger filtré (places US majeures uniquement), tri par cap **croissante** (les plus petites d'abord).

`SCREEN_MIN_REVGROWTH` (0.30) · `SCREEN_MAX_REVGROWTH` (3.0, anti-distorsion base basse) · `SCREEN_MIN_MCAP` (500000000) · **`SCREEN_MAX_MCAP` (10000000000 = exclut les mega caps ; baisse-la, ex 3000000000, pour cibler encore plus petit)** · `UNIVERSE_LIMIT` (300, nb de titres enrichis) · `MAX_TOTAL` (1000) · `TOP_N` (50) · `BLEND_IBKR` (0.15 ; 0 = classement 100 % fondamental). Les seuils fins (poids pré-cassure, garde-fous) sont dans `screen.py` → `DEFAULT_CONFIG`.

## Pilotage depuis le dashboard (sliders)

L'onglet Screener a un bouton **⚙ Paramètres** : sliders pour cap mini/maxi, croissance CA mini, nb de titres analysés. **Appliquer** écrit la config dans Firebase `stocks/screener/config`, que `run.py` lit à chaque exécution (elle surcharge les variables d'env). Les changements s'appliquent au **prochain run**.

Pour un rafraîchissement **immédiat** à chaque Appliquer, lance le service en **mode veille** sur le VPS (il relance dès que `runRequested` change) :

```
.venv\Scripts\python run.py --watch
```

Le lien sur chaque ticker ouvre **TradingView** (graphes live). IBKR n'a pas de deep-link public exploitable (Client Portal login-gated, par conid), donc pas de lien direct IBKR possible.

## Tests locaux (sans réseau)

```
python test_screen.py
python test_momentum.py
```

## Sortie Firebase

- `stocks/screener/latest` : `{generatedAt, source, summary, top[]}` (chaque candidate : score, metrics, flags ; + `ibkrMomentumScore`/`tradableIBKR` si IBKR actif).
- `stocks/screener/positions` : `{account, positions[]}` live IBKR.

## Notes

- `ib_async` = fork maintenu d'`ib_insync` (mort en 2024). Ne pas installer `ib_insync`.
- Yahoo est **non officiel** : le crumb peut échouer ponctuellement (le code retente), et Yahoo peut changer ses champs. Robuste depuis un VPS, fragile depuis une IP partagée.
- Le Worker Cloudflare (`Screener_Engine/worker/`) est **remplacé** par ce service. Il reste dans le repo comme alternative si un jour tu prends un plan FMP payant.
- **Pas un conseil d'investissement** : le moteur classe des candidates, tu décides.
