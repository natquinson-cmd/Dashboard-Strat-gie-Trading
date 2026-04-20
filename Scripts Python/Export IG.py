"""
========================================================
  Export Historique OHLCV - API IG Markets
  Compatible : ProRealTime V12 / IG Markets
========================================================
  Prérequis :
    pip install requests pandas

  Clé API IG :
    Mon Compte IG > Paramètres > Gestion des applications API
    https://www.ig.com/fr/aide/gestion-du-compte/cle-api

  Trouver l'EPIC d'un instrument :
    Ouvrez l'instrument dans PRT, cherchez dans l'URL ou
    utilisez la fonction search_epic() en bas de ce fichier
========================================================
"""

import requests
import pandas as pd
from datetime import datetime
import sys
import time

# ============================================================
#   CONFIGURATION — Modifiez uniquement cette section
# ============================================================

IG_API_KEY  = "c1393762f03d90b117167c210c43f8cb5bb2b997"       # Clé API IG
IG_USERNAME = "natquinson2"   # Identifiant IG
IG_PASSWORD = "Mohican/0509"  # Mot de passe IG

ACCOUNT_TYPE = "LIVE"               # "LIVE" ou "DEMO"

# --- Instruments à exporter ---
# Liste de tuples (nom_affichage, epic)
INSTRUMENTS = [
    ("Nasdaq 100",  "IX.D.NASDAQ.IFE.IP"),
    ("DAX 40",      "IX.D.DAX.DAILY.IP"),
    ("Dow Jones",   "IX.D.DOW.IFE.IP"),
    ("SP 500",      "IX.D.SPTRD.DAILY.IP"),
    ("Or (Gold)",   "CS.D.CFDGOLD.CFDGC.IP"),
    ("EUR/USD",     "CS.D.EURUSD.MINI.IP"),
]

# Exemples d'EPIC supplémentaires :
#   CAC 40 (CFD)      : "IX.D.CAC.DAILY.IP"
#   FTSE 100 (CFD)    : "IX.D.FTSE.DAILY.IP"
#   Apple (action US) : "UA.D.AAPL.CASH.IP"

# --- Timeframes à exporter ---
RESOLUTIONS = ["MINUTE_5", "MINUTE_15"]
# Options disponibles :
#   SECOND | MINUTE | MINUTE_2 | MINUTE_3 | MINUTE_5 |
#   MINUTE_10 | MINUTE_15 | MINUTE_30 |
#   HOUR | HOUR_2 | HOUR_3 | HOUR_4 |
#   DAY | WEEK | MONTH

# --- Plage de dates ---
# DATE_TO = maintenant
# DATE_FROM = calculé automatiquement selon le timeframe
#   L'API IG limite l'historique intraday (les limites exactes dépendent
#   de l'instrument, mais en général ~40 jours pour MINUTE_5/MINUTE_15).
#   Pour DAY/WEEK/MONTH, on peut remonter beaucoup plus loin.
DATE_TO = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

# Profondeur max par résolution (en jours calendaires)
from datetime import timedelta
MAX_HISTORY_DAYS = {
    "SECOND":    4,
    "MINUTE":    7,
    "MINUTE_2":  14,
    "MINUTE_3":  14,
    "MINUTE_5":  40,
    "MINUTE_10": 40,
    "MINUTE_15": 40,
    "MINUTE_30": 90,
    "HOUR":      360,
    "HOUR_2":    360,
    "HOUR_3":    360,
    "HOUR_4":    360,
    "DAY":       365 * 25,
    "WEEK":      365 * 25,
    "MONTH":     365 * 25,
}

def get_date_from(resolution):
    """Retourne la date de début la plus ancienne autorisée pour ce timeframe."""
    days = MAX_HISTORY_DAYS.get(resolution, 40)
    dt = datetime.now() - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%S")

# --- Répertoire de sortie ---
import os as _os
_SCRIPT_DIR = _os.path.dirname(_os.path.abspath(__file__))
_HIST_DIR   = _os.path.join(_SCRIPT_DIR, "Historique")
_os.makedirs(_HIST_DIR, exist_ok=True)

# ============================================================
#   CONNEXION
# ============================================================

BASE_URL = (
    "https://api.ig.com/gateway/deal"
    if ACCOUNT_TYPE == "LIVE"
    else "https://demo-api.ig.com/gateway/deal"
)


def login():
    """Authentification à l'API IG. Retourne (CST, X-SECURITY-TOKEN)."""
    print(f"  Connexion à l'API IG ({ACCOUNT_TYPE})...")
    url = f"{BASE_URL}/session"
    headers = {
        "Content-Type": "application/json; charset=UTF-8",
        "Accept":        "application/json; charset=UTF-8",
        "X-IG-API-KEY":  IG_API_KEY,
        "Version":       "2",
    }
    payload = {
        "identifier": IG_USERNAME,
        "password":   IG_PASSWORD,
    }
    r = requests.post(url, headers=headers, json=payload)

    if r.status_code == 403:
        print("\n[ERREUR] Authentification refusée.")
        print("  → Vérifiez votre clé API, identifiant et mot de passe.")
        print("  → Vérifiez que ACCOUNT_TYPE correspond bien à votre compte ('LIVE' ou 'DEMO').")
        sys.exit(1)

    r.raise_for_status()
    cst            = r.headers.get("CST")
    security_token = r.headers.get("X-SECURITY-TOKEN")
    print("  Connecté avec succès.")
    return cst, security_token


# ============================================================
#   RÉCUPÉRATION DES DONNÉES HISTORIQUES
# ============================================================

def get_historical_prices(cst, security_token, epic, resolution, date_from, date_to):
    """Récupère toutes les bougies OHLCV (avec pagination automatique)."""
    url = f"{BASE_URL}/prices/{epic}"
    headers = {
        "Content-Type":     "application/json; charset=UTF-8",
        "Accept":           "application/json; charset=UTF-8",
        "X-IG-API-KEY":     IG_API_KEY,
        "CST":              cst,
        "X-SECURITY-TOKEN": security_token,
        "Version":          "3",
    }

    all_prices  = []
    page_number = 1

    while True:
        params = {
            "resolution":  resolution,
            "from":        date_from,
            "to":          date_to,
            "pageSize":    1000,
            "pageNumber":  page_number,
        }

        r = requests.get(url, headers=headers, params=params)

        if r.status_code == 404:
            print(f"\n  [ERREUR 404] EPIC introuvable : {epic}")
            print("    → Vérifiez l'EPIC ou utilisez search_epic() pour le retrouver.")
            return []

        if r.status_code == 400:
            error_msg = ""
            try:
                error_msg = r.json().get("errorCode", r.text[:200])
            except Exception:
                error_msg = r.text[:200]
            print(f"\n  [ERREUR 400] {error_msg}")
            print("    → Plage de dates probablement trop large pour ce timeframe.")
            return []

        if r.status_code == 403:
            error_msg = ""
            try:
                error_msg = r.json().get("errorCode", r.text[:200])
            except Exception:
                error_msg = r.text[:200]
            print(f"\n  [ERREUR 403] Accès refusé pour {epic}")
            print(f"    Code : {error_msg}")
            print("    → L'EPIC n'est peut-être pas disponible sur votre compte.")
            print("    → Ou la session a expiré. Tentative de reconnexion...")
            return "REAUTH"

        if r.status_code == 429:
            print("  Limite de requêtes atteinte, pause de 10 secondes...")
            time.sleep(10)
            continue

        r.raise_for_status()
        data   = r.json()
        prices = data.get("prices", [])
        all_prices.extend(prices)

        # Pagination
        page_data    = data.get("metadata", {}).get("pageData", {})
        current_page = page_data.get("pageNumber", 1)
        total_pages  = page_data.get("totalPages", 1)

        print(f"  Page {current_page}/{total_pages} — {len(all_prices)} bougies récupérées...", end="\r")

        if current_page >= total_pages:
            break

        page_number += 1
        time.sleep(0.5)  # Évite de surcharger l'API

    print()  # Saut de ligne après le \r
    return all_prices


# ============================================================
#   MISE EN FORME & EXPORT
# ============================================================

def get_price(price_dict):
    """Retourne mid si disponible, sinon calcule (bid + ask) / 2."""
    if not price_dict:
        return None
    mid = price_dict.get("mid")
    if mid is not None:
        return mid
    bid = price_dict.get("bid")
    ask = price_dict.get("ask")
    if bid is not None and ask is not None:
        return round((bid + ask) / 2, 5)
    return bid or ask


def to_dataframe(prices):
    """Convertit la réponse JSON en DataFrame pandas propre."""
    rows = []
    for p in prices:
        rows.append({
            "Date":   p.get("snapshotTimeUTC"),
            "Open":   get_price(p.get("openPrice")),
            "High":   get_price(p.get("highPrice")),
            "Low":    get_price(p.get("lowPrice")),
            "Close":  get_price(p.get("closePrice")),
            "Volume": p.get("lastTradedVolume"),
        })

    df = pd.DataFrame(rows)
    df["Date"] = pd.to_datetime(df["Date"])
    df = df.sort_values("Date").reset_index(drop=True)
    return df


# ============================================================
#   RECHERCHE D'EPIC (optionnel)
# ============================================================

def search_epic(cst, security_token, search_term, limit=10):
    """
    Recherche un instrument par nom et affiche ses EPIC.
    Exemple d'utilisation :
        cst, token = login()
        search_epic(cst, token, "CAC")
    """
    url = f"{BASE_URL}/markets"
    headers = {
        "Content-Type":     "application/json; charset=UTF-8",
        "Accept":           "application/json; charset=UTF-8",
        "X-IG-API-KEY":     IG_API_KEY,
        "CST":              cst,
        "X-SECURITY-TOKEN": security_token,
        "Version":          "1",
    }
    params = {"searchTerm": search_term}
    r = requests.get(url, headers=headers, params=params)
    r.raise_for_status()

    markets = r.json().get("markets", [])[:limit]
    print(f"\nRésultats pour '{search_term}' :")
    print(f"{'Nom':<40} {'EPIC':<35} {'Type'}")
    print("-" * 90)
    for m in markets:
        print(f"{m.get('instrumentName',''):<40} {m.get('epic',''):<35} {m.get('instrumentType','')}")


# ============================================================
#   POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    total_jobs = len(INSTRUMENTS) * len(RESOLUTIONS)

    print("\n" + "=" * 60)
    print("  Export Historique OHLCV — IG Markets API")
    print("=" * 60)
    print(f"  Instruments : {', '.join(name for name, _ in INSTRUMENTS)}")
    print(f"  Timeframes  : {', '.join(RESOLUTIONS)}")
    print(f"  Période     : max disponible → {DATE_TO[:10]}")
    print(f"  Exports     : {total_jobs} fichiers")
    print("=" * 60 + "\n")

    # 1. Connexion
    cst, security_token = login()

    # 2. Vérification des EPICs disponibles
    print("\n  Vérification des EPICs sur votre compte...")
    print("  " + "-" * 55)
    valid_instruments = []
    for instr_name, epic in INSTRUMENTS:
        url = f"{BASE_URL}/markets/{epic}"
        headers = {
            "Content-Type":     "application/json; charset=UTF-8",
            "Accept":           "application/json; charset=UTF-8",
            "X-IG-API-KEY":     IG_API_KEY,
            "CST":              cst,
            "X-SECURITY-TOKEN": security_token,
            "Version":          "3",
        }
        r = requests.get(url, headers=headers)
        if r.status_code == 200:
            market_info = r.json()
            real_name = market_info.get("instrument", {}).get("name", instr_name)
            print(f"  ✓ {instr_name:<15} → {epic:<30} ({real_name})")
            valid_instruments.append((instr_name, epic))
        else:
            print(f"  ✗ {instr_name:<15} → {epic:<30} [ERREUR {r.status_code}]")
            # Tentative de recherche du bon EPIC
            print(f"    Recherche automatique de l'EPIC correct...")
            search_url = f"{BASE_URL}/markets"
            search_headers = {
                "Content-Type":     "application/json; charset=UTF-8",
                "Accept":           "application/json; charset=UTF-8",
                "X-IG-API-KEY":     IG_API_KEY,
                "CST":              cst,
                "X-SECURITY-TOKEN": security_token,
                "Version":          "1",
            }
            sr = requests.get(search_url, headers=search_headers,
                              params={"searchTerm": instr_name.split(" ")[0]})
            if sr.status_code == 200:
                markets = sr.json().get("markets", [])[:5]
                if markets:
                    print(f"    Suggestions :")
                    for m in markets:
                        print(f"      - {m.get('instrumentName',''):<35} EPIC: {m.get('epic','')}")
                else:
                    print(f"    Aucun résultat trouvé.")
            time.sleep(0.5)
        time.sleep(0.5)

    if not valid_instruments:
        print("\n  [ERREUR] Aucun instrument valide trouvé. Abandon.")
        sys.exit(1)

    print(f"\n  → {len(valid_instruments)}/{len(INSTRUMENTS)} instruments validés.\n")

    # Recalcul du nombre de jobs
    total_jobs = len(valid_instruments) * len(RESOLUTIONS)

    # 3. Boucle sur chaque instrument × timeframe
    job_num = 0
    successes = 0
    failures  = []

    for instr_name, epic in valid_instruments:
        for resolution in RESOLUTIONS:
            job_num += 1
            output_file = _os.path.join(_HIST_DIR, f"historique_{epic}_{resolution}.csv")

            print(f"\n{'─' * 60}")
            print(f"  [{job_num}/{total_jobs}] {instr_name} — {resolution}")
            print(f"  EPIC : {epic}")
            print(f"{'─' * 60}")

            try:
                date_from = get_date_from(resolution)
                prices = get_historical_prices(
                    cst, security_token, epic, resolution, date_from, DATE_TO
                )

                # Reconnexion automatique si la session a expiré
                if prices == "REAUTH":
                    print("  ↻ Reconnexion en cours...")
                    cst, security_token = login()
                    prices = get_historical_prices(
                        cst, security_token, epic, resolution, date_from, DATE_TO
                    )

                if not prices or prices == "REAUTH":
                    print(f"  ⚠ Aucune donnée retournée pour {instr_name} ({resolution})")
                    failures.append(f"{instr_name} ({resolution}) — aucune donnée ou accès refusé")
                    continue

                df = to_dataframe(prices)
                df.to_csv(output_file, index=False, sep=";", decimal=",")

                print(f"  ✓ {len(df)} bougies exportées")
                print(f"  ✓ Fichier : {output_file}")
                successes += 1

            except Exception as e:
                print(f"  ✗ ERREUR pour {instr_name} ({resolution}) : {e}")
                failures.append(f"{instr_name} ({resolution}) — {e}")

            # Pause entre chaque requête pour respecter les limites API
            time.sleep(2)

    # 4. Résumé final
    print(f"\n{'=' * 60}")
    print(f"  RÉSUMÉ")
    print(f"{'=' * 60}")
    print(f"  ✓ {successes}/{total_jobs} exports réussis")
    if failures:
        print(f"  ✗ {len(failures)} échecs :")
        for f in failures:
            print(f"      - {f}")
    print(f"  Répertoire : {_HIST_DIR}")
    print(f"{'=' * 60}\n")

    # Pour rechercher un EPIC manuellement, décommentez ces lignes :
    # search_epic(cst, security_token, "Nasdaq")
    # search_epic(cst, security_token, "Dow")