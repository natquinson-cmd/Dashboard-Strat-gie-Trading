#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collecteur QUOTIDIEN Darwinex (compte investisseur) -> Firebase
===============================================================================
Récupère la valeur du portefeuille + le P&L du jour depuis les endpoints JSON
INTERNES de darwinex.com (ceux qu'appelle la page /fr/portfolio/chart) et les
pousse dans Firebase sur `dashboard/darwinex/daily/<YYYY-MM-DD> = { value, pnl }`,
que le Trading Dashboard lit pour les 2 calendriers Darwinex (journalier + mensuel).

Pourquoi Playwright + session persistée ?
  - L'API OAuth publique Darwinex est morte (host down). MAIS la plateforme web
    expose des endpoints JSON internes, authentifiés par simple COOKIE de session.
  - Pas de 2FA sur ce compte : on se logue UNE fois à la main (--login), Playwright
    sauvegarde les cookies dans storage_state.json, et les runs suivants sont
    headless et réutilisent cette session. Re-login manuel seulement à l'expiration.

Endpoints utilisés (investorAccountId dans la config) :
  - /api/investment/investoraccount ................ equity (valeur €), invested, openPnL
  - /api/investment/graphic/portfolio/pl/<id>/1D ... P&L intraday du jour (dernier point = P&L du jour)
  - /api/investment/graphic/portfolio/pl/<id>/ALL .. P&L cumulé € (pour backfill historique)
  - /api/investment/graphic/portfolio/<id>/ALL ..... courbe indice + DÉPÔTS (3e élément)

-------------------------------------------------------------------------------
INSTALLATION (VPS Windows, à côté du PontDarwinex) :
  1) py -m pip install playwright
     py -m playwright install chromium
  2) Copier darwinex_scrape_config.example.json -> darwinex_scrape_config.json et remplir.
  3) Login initial (fenêtre visible) :   py darwinex_scrape_daily.py --login
       -> connecte-toi, va sur ta page portefeuille, puis reviens ici et Entrée.
  4) (optionnel) Backfill de tout l'historique :   py darwinex_scrape_daily.py --backfill
  5) Test d'un run :   py darwinex_scrape_daily.py --once
  6) Planificateur de tâches Windows : tâche quotidienne ~23h30 lançant --once
       (comme la tâche du PontDarwinex).

AUCUN secret dans le repo : darwinex_scrape_config.json et storage_state.json
sont à exclure de git.
===============================================================================
"""

import json
import os
import sys
import time
import datetime as dt
import urllib.request
import urllib.error

try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Europe/Paris")  # jour "de marché" Darwinex (CET/CEST)
except Exception:
    TZ = None

HERE = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(HERE, "darwinex_scrape_config.json")
STATE_PATH = os.path.join(HERE, "storage_state.json")
BASE = "https://www.darwinex.com"
PORTFOLIO_URL = BASE + "/fr/portfolio/chart"


# ─────────────────────────────────────────────────────────────────────────────
# Config
# ─────────────────────────────────────────────────────────────────────────────
def load_config():
    if not os.path.exists(CONFIG_PATH):
        sys.exit(f"[ERREUR] Config introuvable : {CONFIG_PATH}\n"
                 f"Copie darwinex_scrape_config.example.json -> darwinex_scrape_config.json et remplis-le.")
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def day_of(ts_ms):
    """Timestamp ms -> 'YYYY-MM-DD' dans le fuseau du marché (Europe/Paris)."""
    d = dt.datetime.fromtimestamp(ts_ms / 1000, tz=dt.timezone.utc)
    if TZ:
        d = d.astimezone(TZ)
    return d.strftime("%Y-%m-%d")


def today_str():
    now = dt.datetime.now(TZ) if TZ else dt.datetime.now()
    return now.strftime("%Y-%m-%d")


# ─────────────────────────────────────────────────────────────────────────────
# Firebase REST (auth = database secret)
# ─────────────────────────────────────────────────────────────────────────────
def fb_write(cfg, path, payload, method="PATCH"):
    fb = cfg["firebase"]
    url = f"{fb['database_url'].rstrip('/')}/{path}.json?auth={fb['database_secret']}"
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.status, resp.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace")
    except Exception as e:
        return 0, str(e)


def set_collector_status(cfg, status, message=""):
    fb_write(cfg, "dashboard/darwinex/collectorStatus",
             {"status": status, "message": message, "asOf": int(time.time() * 1000)},
             method="PUT")


# ─────────────────────────────────────────────────────────────────────────────
# Playwright : session + fetch des endpoints JSON
# ─────────────────────────────────────────────────────────────────────────────
def _require_playwright():
    try:
        from playwright.sync_api import sync_playwright  # noqa
        return sync_playwright
    except Exception:
        sys.exit("[ERREUR] Playwright manquant. Installe :\n"
                 "  py -m pip install playwright\n"
                 "  py -m playwright install chromium")


def do_login():
    """Ouvre une fenêtre, laisse l'utilisateur se connecter, sauvegarde la session."""
    sync_playwright = _require_playwright()
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        ctx = browser.new_context()
        page = ctx.new_page()
        page.goto(PORTFOLIO_URL)
        print("\n>>> Connecte-toi à Darwinex dans la fenêtre, va sur ta page portefeuille,")
        input(">>> puis reviens ici et appuie sur Entrée pour sauvegarder la session... ")
        ctx.storage_state(path=STATE_PATH)
        browser.close()
        print(f"[OK] Session sauvegardée : {STATE_PATH}")


def fetch_json(cfg, paths):
    """Charge la session et récupère plusieurs endpoints. Retourne {key: obj} ou lève SessionExpired."""
    sync_playwright = _require_playwright()
    if not os.path.exists(STATE_PATH):
        sys.exit(f"[ERREUR] Session absente ({STATE_PATH}). Lance d'abord : py {os.path.basename(__file__)} --login")
    out = {}
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        ctx = browser.new_context(storage_state=STATE_PATH)
        req = ctx.request
        for key, path in paths.items():
            r = req.get(BASE + path, timeout=30000)
            if r.status in (401, 403) or "/login" in (r.url or "") or "trading-accounts" in (r.url or ""):
                browser.close()
                raise SessionExpired(f"{path} -> HTTP {r.status} / redirection login")
            txt = r.text()
            try:
                out[key] = json.loads(txt)
            except Exception:
                browser.close()
                raise SessionExpired(f"{path} -> réponse non-JSON (session probablement expirée)")
        # rafraîchit la session sur disque (prolonge les cookies)
        ctx.storage_state(path=STATE_PATH)
        browser.close()
    return out


class SessionExpired(Exception):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# Extraction
# ─────────────────────────────────────────────────────────────────────────────
def account_equity(account_json, acc_id):
    """[{id, equity, invested, openPnL, currency, ...}] -> (equity, invested, openPnL)."""
    rows = account_json if isinstance(account_json, list) else [account_json]
    row = next((r for r in rows if str(r.get("id")) == str(acc_id)), rows[0] if rows else {})
    return (float(row.get("equity") or 0.0),
            float(row.get("invested") or 0.0),
            float(row.get("openPnL") or 0.0))


def last_pl(pl_json):
    """Série [[ts, cumPnl, ...], ...] -> dernière valeur cumPnl (P&L du jour pour /1D)."""
    if not isinstance(pl_json, list) or not pl_json:
        return 0.0
    return float(pl_json[-1][1] or 0.0)


def deposits_from_value_series(value_json):
    """Courbe indice: [[ts, idx, [[depTs, depAmt], ...], []], ...] -> [(depTs, depAmt), ...] triés."""
    deps = []
    if isinstance(value_json, list):
        for pt in value_json:
            if len(pt) > 2 and isinstance(pt[2], list):
                for d in pt[2]:
                    if isinstance(d, list) and len(d) >= 2:
                        deps.append((int(d[0]), float(d[1])))
    deps.sort(key=lambda x: x[0])
    return deps


# ─────────────────────────────────────────────────────────────────────────────
# Modes
# ─────────────────────────────────────────────────────────────────────────────
def run_once(cfg, dump=False):
    acc = cfg["darwinex"]["investor_account_id"]
    paths = {
        "account": "/api/investment/investoraccount",
        "pl1d": f"/api/investment/graphic/portfolio/pl/{acc}/1D",
    }
    data = fetch_json(cfg, paths)
    if dump:
        print(json.dumps(data, indent=2)[:6000]); return
    equity, invested, open_pnl = account_equity(data["account"], acc)
    pnl_today = round(last_pl(data["pl1d"]), 2)
    day = today_str()
    # 1) point quotidien
    fb_write(cfg, f"dashboard/darwinex/daily/{day}",
             {"value": round(equity, 2), "pnl": pnl_today}, method="PUT")
    # 2) snapshot agrégé (hero/portfolio) — source 'vps'
    fb_write(cfg, "dashboard/darwinex",
             {"source": "vps", "asOf": int(time.time() * 1000),
              "currency": "EUR", "currentValue": round(equity, 2)})
    set_collector_status(cfg, "ok", f"{day} value={round(equity,2)} pnl={pnl_today}")
    print(f"[OK] {day} : valeur={round(equity,2)} € · P&L jour={pnl_today} € (investi={invested}, openPnL={round(open_pnl,2)})")


def run_backfill(cfg):
    acc = cfg["darwinex"]["investor_account_id"]
    paths = {
        "plAll": f"/api/investment/graphic/portfolio/pl/{acc}/ALL",
        "valAll": f"/api/investment/graphic/portfolio/{acc}/ALL",
    }
    data = fetch_json(cfg, paths)
    pl = data["plAll"]                      # [[ts, cumPnl€, ...], ...]
    deps = deposits_from_value_series(data["valAll"])  # [(ts, amt), ...]

    # cumPnl de fin de journée pour chaque jour
    eod = {}
    for pt in pl:
        ts, cum = int(pt[0]), float(pt[1] or 0.0)
        eod[day_of(ts)] = cum  # dernière valeur du jour (série chronologique)
    days = sorted(eod.keys())

    def deposits_upto(day):
        end = dt.datetime.strptime(day, "%Y-%m-%d")
        if TZ:
            end = end.replace(tzinfo=TZ)
        end = end + dt.timedelta(days=1)  # fin de journée
        end_ms = end.timestamp() * 1000
        return sum(a for (t, a) in deps if t <= end_ms)

    payload = {}
    prev_cum = 0.0
    for day in days:
        cum = eod[day]
        pnl = round(cum - prev_cum, 2)
        value = round(deposits_upto(day) + cum, 2)
        payload[day] = {"value": value, "pnl": pnl}
        prev_cum = cum

    status, txt = fb_write(cfg, "dashboard/darwinex/daily", payload, method="PATCH")
    if status == 200:
        print(f"[OK] Backfill : {len(payload)} jours écrits ({days[0]} -> {days[-1]}).")
    else:
        print(f"[ERREUR] Backfill Firebase ({status}) : {txt[:300]}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--login" in args:
        do_login()
    elif "--dump" in args:
        run_once(load_config(), dump=True)
    elif "--backfill" in args:
        cfg = load_config()
        try:
            run_backfill(cfg)
        except SessionExpired as e:
            set_collector_status(cfg, "expired", str(e))
            sys.exit(f"[SESSION EXPIRÉE] {e}\nRelance : py {os.path.basename(__file__)} --login")
    elif "--once" in args:
        cfg = load_config()
        try:
            run_once(cfg)
        except SessionExpired as e:
            set_collector_status(cfg, "expired", str(e))
            sys.exit(f"[SESSION EXPIRÉE] {e}\nRelance : py {os.path.basename(__file__)} --login")
    else:
        print("Usage: py darwinex_scrape_daily.py [--login | --once | --backfill | --dump]\n"
              "  --login    : connexion manuelle unique, sauvegarde la session (storage_state.json)\n"
              "  --once     : pousse le point du jour (value + pnl) dans Firebase  [tâche 23h30]\n"
              "  --backfill : reconstruit tout l'historique quotidien depuis l'ouverture du compte\n"
              "  --dump     : imprime les réponses brutes des endpoints (debug)")
