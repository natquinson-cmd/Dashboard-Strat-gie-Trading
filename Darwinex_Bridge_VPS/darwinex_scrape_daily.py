#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Collecteur QUOTIDIEN Darwinex (compte investisseur) -> Firebase
===============================================================================
Récupère la valeur du portefeuille + le P&L du jour depuis les endpoints JSON
INTERNES de darwinex.com (ceux qu'appelle la page /fr/portfolio/chart) et les
pousse dans Firebase sur `dashboard/darwinex/daily/<YYYY-MM-DD> = { value, pnl }`,
que le Trading Dashboard lit pour les 2 calendriers Darwinex (journalier + mensuel).

Pourquoi un Chrome débogué (et pas un login automatisé) ?
  - L'API OAuth publique Darwinex est morte (host down). MAIS la plateforme web
    expose des endpoints JSON internes, authentifiés par simple COOKIE de session.
  - Darwinex BLOQUE la connexion dans un navigateur piloté (le clic sur LOG IN ne
    fait rien). On ne se logue donc PAS via le script : on lance un VRAI Chrome en
    mode débogage (start_chrome_debug.bat), on s'y connecte à la main (login normal,
    ça marche), et le script s'y branche via CDP pour lire les endpoints. Pas de 2FA.

Endpoints utilisés (investorAccountId dans la config) :
  - /api/investment/investoraccount ................ equity (valeur €), invested, openPnL
  - /api/investment/graphic/portfolio/pl/<id>/1D ... P&L intraday du jour (dernier point = P&L du jour)
  - /api/investment/graphic/portfolio/pl/<id>/ALL .. P&L cumulé € (pour backfill historique)
  - /api/investment/graphic/portfolio/<id>/ALL ..... courbe indice + DÉPÔTS (3e élément)

-------------------------------------------------------------------------------
INSTALLATION (VPS Windows, à côté du PontDarwinex) :
  1) py -m pip install playwright        (Chrome doit être installé sur le VPS)
  2) Copier darwinex_scrape_config.example.json -> darwinex_scrape_config.json et remplir.
  3) Lance start_chrome_debug.bat -> un Chrome s'ouvre : connecte-toi à Darwinex
     (coche « Keep me logged in ») et va sur ta page portefeuille. Laisse-le ouvert.
  4) Vérifie :   py darwinex_scrape_daily.py --login   (doit dire "session valide")
  5) Backfill :  py darwinex_scrape_daily.py --backfill
  6) Tâche planifiée 00h30 : darwinex_scrape_install_task.bat (via darwinex_scrape_run.bat,
     qui relance start_chrome_debug.bat au besoin).

AUCUN secret dans le repo : darwinex_scrape_config.json et le profil chrome_profile/
(cookies de session) sont à exclure de git.
===============================================================================
"""

import json
import os
import re
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
BASE = "https://www.darwinex.com"
PORTFOLIO_URL = BASE + "/fr/portfolio/chart"
DARWINS_URL = BASE + "/fr/portfolio/darwins"  # page ventilation par DARWIN (investi, P&L ouvert)
DEFAULT_CDP_URL = "http://localhost:9222"  # Chrome lancé par start_chrome_debug.bat

# Une ligne de la page darwins : TICKER investi€ risque€ alloc% levier prixMoy prixAct devise fx% pnlOuvert€ (pnl%)
_DARWIN_ROW = re.compile(
    r"([A-Z][A-Z0-9]{1,7})\s+"      # ticker
    r"([\d.,]+)\s*€\s+"       # investi
    r"[\d.,]+\s*€\s+"        # risque sur capital
    r"([\d.,]+)\s*%\s+"           # allocation
    r"[\d.]+\s+"                  # levier
    r"[\d.,]+\s+[\d.,]+\s+"       # prix moyen, prix actuel
    r"[A-Z]{3}\s+"               # devise
    r"-?[\d.,]+\s*%\s+"          # impact devise
    r"(-?[\d.,]+)\s*€\s*"   # P&L ouvert €
    r"\(\s*(-?[\d.,]+)\s*%\s*\)"  # P&L ouvert %
)


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
    # Le secret est OPTIONNEL : si les règles de la base autorisent l'écriture non
    # authentifiée (cas de ce dashboard), on omet ?auth. Sinon on l'utilise.
    secret = (fb.get("database_secret") or "").strip()
    q = f"?auth={secret}" if secret and not secret.startswith("TON_") else ""
    url = f"{fb['database_url'].rstrip('/')}/{path}.json{q}"
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


def _cdp_url(cfg):
    return (cfg.get("darwinex", {}) or {}).get("chrome_debug_url") or DEFAULT_CDP_URL


def _cdp_context(p, cfg):
    """Se branche sur le Chrome lancé en mode débogage (start_chrome_debug.bat), où TU
    t'es connecté à Darwinex normalement. Aucun login automatisé (Darwinex bloque les
    navigateurs pilotés) : on réutilise simplement ta session réelle. Renvoie (browser, context)."""
    url = _cdp_url(cfg)
    try:
        browser = p.chromium.connect_over_cdp(url)
    except Exception as e:
        sys.exit(f"[ERREUR] Chrome en mode débogage introuvable sur {url}.\n"
                 f"Lance d'abord start_chrome_debug.bat, connecte-toi à Darwinex, puis réessaie.\n({e})")
    ctx = browser.contexts[0] if browser.contexts else browser.new_context()
    return browser, ctx


def do_login(cfg):
    """Ne logue rien : vérifie que le Chrome débogué est bien connecté à Darwinex."""
    sync_playwright = _require_playwright()
    with sync_playwright() as p:
        _, ctx = _cdp_context(p, cfg)
        r = ctx.request.get(BASE + "/api/investment/investoraccount", timeout=30000)
        ok = (r.status == 200 and r.text().strip().startswith("["))
        if ok:
            print("[OK] Chrome débogué connecté à Darwinex — session valide. Lance : py darwinex_scrape_daily.py --backfill")
        else:
            print(f"[!] Pas connecté (HTTP {r.status}). Dans le Chrome ouvert par start_chrome_debug.bat, "
                  f"connecte-toi à Darwinex (coche « Keep me logged in ») et va sur ta page portefeuille, puis relance ceci.")


def fetch_json(cfg, paths):
    """Récupère les endpoints via le Chrome débogué. {key: obj} ou lève SessionExpired."""
    sync_playwright = _require_playwright()
    out = {}
    with sync_playwright() as p:
        _, ctx = _cdp_context(p, cfg)  # ne pas fermer : c'est le vrai Chrome de l'utilisateur
        req = ctx.request
        for key, path in paths.items():
            r = req.get(BASE + path, timeout=30000)
            if r.status in (401, 403) or "/login" in (r.url or "") or "trading-accounts" in (r.url or ""):
                raise SessionExpired(f"{path} -> HTTP {r.status} / redirection login")
            txt = r.text()
            try:
                out[key] = json.loads(txt)
            except Exception:
                raise SessionExpired(f"{path} -> réponse non-JSON (session probablement expirée)")
    return out


def _num(s):
    return float(s.replace(",", ""))  # "5,000.00" -> 5000.00 ; "-155.92" -> -155.92


def fetch_darwins(cfg):
    """Rend la page /fr/portfolio/darwins et parse la ventilation par DARWIN.
    Retourne { ticker: {inv, alloc, pnl, pct} } (pnl = P&L Ouvert CUMULÉ €). {} si échec.
    Best-effort : si la page ne rend pas, on renvoie {} (le jour n'aura pas le détail)."""
    sync_playwright = _require_playwright()
    text = ""
    try:
        with sync_playwright() as p:
            _, ctx = _cdp_context(p, cfg)
            page = ctx.new_page()
            try:
                page.goto(DARWINS_URL, timeout=45000, wait_until="domcontentloaded")
                try:
                    page.wait_for_selector("text=P&L Ouvert", timeout=20000)
                except Exception:
                    pass
                page.wait_for_timeout(2500)  # laisse React peupler le tableau
                text = page.inner_text("body")
            finally:
                page.close()
    except Exception as e:
        print(f"[WARN] fetch_darwins: {e}")
        return {}
    out = {}
    for m in _DARWIN_ROW.finditer(text):
        out[m.group(1)] = {
            "inv": round(_num(m.group(2)), 2),
            "alloc": round(_num(m.group(3)), 2),
            "pnl": round(_num(m.group(4)), 2),
            "pct": round(_num(m.group(5)), 2),
        }
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


def sum_fees(pl_json):
    """Somme des frais/commissions (entrées négatives des colonnes >= 2 de la série /pl)."""
    fees = 0.0
    if isinstance(pl_json, list):
        for pt in pl_json:
            for i in range(2, len(pt)):
                if isinstance(pt[i], list):
                    for f in pt[i]:
                        if isinstance(f, list) and len(f) >= 2 and isinstance(f[1], (int, float)) and f[1] < 0:
                            fees += f[1]
    return round(abs(fees), 2)


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
def push_aggregate(cfg, equity, deposits_total, fees_total):
    """Snapshot agrégé (hero + intégration portfolio), source 'vps'."""
    fb_write(cfg, "dashboard/darwinex",
             {"source": "vps", "asOf": int(time.time() * 1000), "currency": "EUR",
              "currentValue": round(equity, 2), "invested": round(deposits_total, 2),
              "feesTotal": round(fees_total, 2)})


def run_once(cfg, dump=False):
    """Enregistre le jour COURANT (P&L intraday). Utile pour un check manuel en journée.
    La tâche nocturne (00h30) utilise plutôt --backfill (journée complète, auto-correctif)."""
    acc = cfg["darwinex"]["investor_account_id"]
    paths = {
        "account": "/api/investment/investoraccount",
        "pl1d": f"/api/investment/graphic/portfolio/pl/{acc}/1D",
        "plAll": f"/api/investment/graphic/portfolio/pl/{acc}/ALL",
        "valAll": f"/api/investment/graphic/portfolio/{acc}/ALL",
    }
    data = fetch_json(cfg, paths)
    if dump:
        print(json.dumps(data, indent=2)[:6000]); return
    equity, _, open_pnl = account_equity(data["account"], acc)
    pnl_today = round(last_pl(data["pl1d"]), 2)
    deposits_total = sum(a for _, a in deposits_from_value_series(data["valAll"]))
    fees_total = sum_fees(data["plAll"])
    day = today_str()
    darwins = fetch_darwins(cfg)  # ventilation par DARWIN (best-effort)
    day_payload = {"value": round(equity, 2), "pnl": pnl_today}
    if darwins:
        day_payload["darwins"] = darwins
    fb_write(cfg, f"dashboard/darwinex/daily/{day}", day_payload, method="PUT")
    push_aggregate(cfg, equity, deposits_total, fees_total)
    set_collector_status(cfg, "ok", f"{day} value={round(equity,2)} pnl={pnl_today} darwins={len(darwins)}")
    print(f"[OK] {day} : valeur={round(equity,2)} € · P&L jour={pnl_today} € "
          f"(investi/dépôts={round(deposits_total,2)}, frais={fees_total}, darwins={len(darwins)}, openPnL={round(open_pnl,2)})")


def run_backfill(cfg):
    acc = cfg["darwinex"]["investor_account_id"]
    paths = {
        "account": "/api/investment/investoraccount",
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
    # agrégat hero/portfolio (valeur = equity live, dépôts = somme, frais = /pl)
    equity, _, _ = account_equity(data["account"], acc)
    deposits_total = sum(a for _, a in deps)
    fees_total = sum_fees(pl)
    push_aggregate(cfg, equity, deposits_total, fees_total)
    # Ventilation par DARWIN : seulement l'instantané du jour (l'API n'a pas d'historique par DARWIN)
    darwins = fetch_darwins(cfg)
    if darwins:
        fb_write(cfg, f"dashboard/darwinex/daily/{today_str()}/darwins", darwins, method="PUT")
    if status == 200:
        set_collector_status(cfg, "ok", f"backfill {len(payload)} jours -> {days[-1]} darwins={len(darwins)}")
        print(f"[OK] Backfill : {len(payload)} jours écrits ({days[0]} -> {days[-1]}). "
              f"Valeur={round(equity,2)} € · dépôts={round(deposits_total,2)} · frais={fees_total} · darwins={len(darwins)}")
    else:
        print(f"[ERREUR] Backfill Firebase ({status}) : {txt[:300]}")


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    args = set(sys.argv[1:])
    if "--login" in args:
        do_login(load_config())
    elif "--dump" in args:
        run_once(load_config(), dump=True)
    elif "--backfill" in args:
        cfg = load_config()
        try:
            run_backfill(cfg)
        except SessionExpired as e:
            set_collector_status(cfg, "expired", str(e))
            sys.exit(f"[SESSION EXPIRÉE] {e}\nDans le Chrome de start_chrome_debug.bat, reconnecte-toi à Darwinex, puis réessaie.")
    elif "--once" in args:
        cfg = load_config()
        try:
            run_once(cfg)
        except SessionExpired as e:
            set_collector_status(cfg, "expired", str(e))
            sys.exit(f"[SESSION EXPIRÉE] {e}\nDans le Chrome de start_chrome_debug.bat, reconnecte-toi à Darwinex, puis réessaie.")
    else:
        print("Prérequis : lance start_chrome_debug.bat et connecte-toi à Darwinex (une fois).\n"
              "Usage: py darwinex_scrape_daily.py [--login | --once | --backfill | --dump]\n"
              "  --login    : vérifie que le Chrome débogué est bien connecté à Darwinex\n"
              "  --once     : pousse le point du jour (value + pnl) dans Firebase\n"
              "  --backfill : reconstruit tout l'historique quotidien  [tâche 00h30]\n"
              "  --dump     : imprime les réponses brutes des endpoints (debug)")
