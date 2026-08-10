# Couche IBKR (VPS) — enrichissement live du screener

Ajoute à ton screener FMP la valeur unique d'Interactive Brokers : **momentum propre** (barres historiques), **tradabilité**, **positions/compte live**. Tourne sur ton VPS (à côté des bridges IG/Darwinex), pousse dans Firebase, le dashboard lit Firebase.

```
Worker FMP (/latest)  ──►  run.py (VPS)  ──►  IB Gateway (IBC)  ──►  IBKR
   candidates growth            │  enrichit top N : momentum, tradabilité
                                │  + positions/compte live
                                ▼
                          Firebase  ──►  Dashboard (onglet Screener)
                    stocks/screener/latest + /positions
```

## Pièces

- `momentum.py` : calcul RS/MM50/MM200/ATR/proximité 52s depuis des barres. **Pur, testé** (`test_momentum.py`).
- `ibkr_client.py` : enveloppe `ib_async` (lecture seule) : `positions()`, `momentum()`, `is_tradable()`, `snapshot()`, `scanner()`.
- `firebase_push.py` : écriture RTDB (secret legacy **ou** compte de service).
- `run.py` : orchestrateur. `--mock` = sans IBKR (valide la chaîne + Firebase + dashboard).
- `run_screener.bat` : wrapper Windows pour le Planificateur de tâches.

## Étape 0 — valider SANS IBKR (mock)

Aucune passerelle requise. Vérifie que la chaîne Worker → score → Firebase → dashboard marche :

```
set WORKER_URL=https://stock-screener.xxx.workers.dev
set FIREBASE_DB_URL=https://portfolio-dashboard-f0c69-default-rtdb.firebaseio.com
set FIREBASE_DB_SECRET=ton_secret
python run.py --mock
```

Ouvre l'onglet **Screener** du dashboard : il doit afficher le classement (mock). Puis passe en live.

## Étape 1 — IB Gateway headless (IBC) sur le VPS Windows

1. Installe **IB Gateway** (stable) et **IBC** (github.com/IbcAlpha/IBC, version Windows).
2. Dans `IBC\config.ini` : `IbLoginId`, `IbPassword`, `TradingMode=live`, `IbAutoClosedown=no`, `ClosedownAt=`, et surtout `AcceptNonBrokerageAccountWarning=yes`. Choisis **auto-restart** (pas auto-logoff) pour ne valider le **2FA qu'une fois par semaine** (maintenance du dimanche) via l'app mobile IBKR.
3. Dans IB Gateway > Configure > API : **Enable ActiveX and Socket Clients**, port **4001** (live) ou 4002 (paper), coche **Read-Only API** (on ne passe aucun ordre), et ajoute `127.0.0.1` aux Trusted IPs.
4. Lance IBC (`StartGateway.bat`) au démarrage du VPS (Planificateur, au logon). Prévois un watchdog qui relance si le process tombe.

Abonnements **market data** IBKR : sans eux tu as du différé 15 min. Pour du momentum fiable, souscris au moins les paquets US temps réel non-pro (quelques \$/mois) dans le portail IBKR.

## Étape 2 — le service Python

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

Renseigne `run_screener.bat` (WORKER_URL, FIREBASE_*, IBKR_PORT=4001), puis :

```
run_screener.bat
```

Planifie-le dans le **Planificateur de tâches** chaque jour ouvré, ~30 min après le cron du Worker FMP.

## Réglages (env)

`TOP_N` (défaut 40) = nb de candidates enrichies. `BLEND_IBKR` (défaut 0.4) = poids du momentum IBKR dans le score final (`final = (1-BLEND)*scoreFMP + BLEND*momentumIBKR`). `IBKR_CLIENT_ID` unique par process (ne pas collisionner avec tes bridges).

## Test local (sans rien installer d'IBKR)

```
python test_momentum.py
```

## Ce que ça pousse dans Firebase

- `stocks/screener/latest` : classement enrichi (mêmes champs que le Worker + `ibkr`, `ibkrMomentumScore`, `tradableIBKR`, `scoreFmp`).
- `stocks/screener/positions` : `{account, positions[]}` live IBKR.

## Notes

- `ib_async` est le fork **maintenu** d'`ib_insync` (non maintenu depuis 2024). Ne pas installer `ib_insync`.
- Lecture seule stricte : le client se connecte en `readonly=True`, aucun ordre possible.
- Linux au lieu de Windows : mêmes fichiers, mais IB Gateway a besoin d'un `Xvfb` (serveur X virtuel) et on planifie via `systemd timer` au lieu du Planificateur.
- **Pas un conseil d'investissement** : le moteur classe des candidates, tu décides.
