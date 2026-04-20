"""
========================================================
  Téléchargement Historique OHLCV — Dukascopy
  via dukascopy-node (CLI)
========================================================
  Prérequis :
    - Node.js installé (https://nodejs.org)
    - pip install pandas   (pour le reformatage)

  Pas besoin d'installer dukascopy-node globalement,
  npx le télécharge automatiquement à la première
  exécution.

  Profondeur disponible sur Dukascopy :
    - 1min : depuis 2003-2013 selon l'instrument
    - Daily : depuis 1973-1990 selon l'instrument

  Stratégie de téléchargement :
    - Données en 1 minute (granularité max raisonnable)
    - Téléchargement année par année (évite les timeouts)
    - Fusion automatique en un seul CSV par instrument
    - À partir du 1min, on peut reconstruire n'importe
      quel timeframe (3, 5, 7, 15, 30min, 1h, etc.)

  Instruments configurés :
    - Nasdaq 100  : usatechidxusd (depuis 1990)
    - DAX 40      : deuidxeur     (depuis 2013)
    - Dow Jones   : usa30idxusd   (depuis 2013)
    - SP 500      : usa500idxusd  (depuis 1980)
    - Or (Gold)   : xauusd        (depuis 1999)
    - EUR/USD     : eurusd        (depuis 1973)
========================================================
"""

import subprocess
import os
import sys
import platform
import pandas as pd
from datetime import datetime

# Sur Windows, les commandes npm/npx sont des fichiers .cmd
# Il faut shell=True pour que subprocess les trouve
IS_WINDOWS = platform.system() == "Windows"

# ============================================================
#   CONFIGURATION
# ============================================================

# Instruments : (nom_affichage, ticker Dukascopy, date début)
# 7 ans d'historique : couvre plusieurs cycles de marché complets
# (COVID 2020, hausse des taux 2022, rallye IA 2023-2024, etc.)
# Suffisant pour backtester du 5min au 4h.
INSTRUMENTS = [
    ("Nasdaq 100",  "usatechidxusd", "2019-01-01"),
    ("DAX 40",      "deuidxeur",     "2019-01-01"),
    ("Dow Jones",   "usa30idxusd",   "2019-01-01"),
    ("SP 500",      "usa500idxusd",  "2019-01-01"),
    ("Or (Gold)",   "xauusd",        "2019-01-01"),
    ("EUR/USD",     "eurusd",        "2019-01-01"),
]

# Timeframe : on télécharge en 1 minute (granularité max raisonnable)
# À partir de ces données, on peut reconstruire n'importe quel
# timeframe (3min, 5min, 15min, 30min, 1h, etc.) pour le backtesting.
# Codes disponibles : tick, m1, m5, m15, m30, h1, h4, d1, mn1
TIMEFRAMES = [
    ("1min", "m1"),
]

# Date de fin = aujourd'hui
DATE_TO = datetime.now().strftime("%Y-%m-%d")

# Répertoire de sortie
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
HIST_DIR   = os.path.join(SCRIPT_DIR, "Historique")
os.makedirs(HIST_DIR, exist_ok=True)

# Répertoire temporaire pour les CSV bruts
TEMP_DIR = os.path.join(SCRIPT_DIR, "Historique", "_temp")
os.makedirs(TEMP_DIR, exist_ok=True)


# ============================================================
#   VÉRIFICATION DE NODE.JS
# ============================================================

def check_node():
    """Vérifie que Node.js est installé."""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True, text=True, timeout=10,
            shell=IS_WINDOWS,
        )
        if result.returncode == 0:
            print(f"  Node.js détecté : {result.stdout.strip()}")
            return True
    except FileNotFoundError:
        pass
    print("\n  [ERREUR] Node.js n'est pas installé.")
    print("  → Téléchargez-le sur https://nodejs.org")
    print("  → Puis relancez ce script.")
    return False


# ============================================================
#   TÉLÉCHARGEMENT VIA DUKASCOPY-NODE
# ============================================================

def download_instrument(ticker, timeframe_code, date_from, date_to, output_csv):
    """
    Télécharge les données historiques via dukascopy-node CLI.
    dukascopy-node sauvegarde les CSV dans un sous-dossier 'download/'.
    On cherche ensuite le fichier généré et on le copie à l'emplacement voulu.
    Retourne True si succès, False sinon.
    """
    import glob as _glob
    import shutil as _shutil

    # Dossier où dukascopy-node va écrire les fichiers
    download_dir = os.path.join(TEMP_DIR, "download")
    os.makedirs(download_dir, exist_ok=True)

    cmd = [
        "npx", "-y", "dukascopy-node",
        "-i", ticker,
        "-from", date_from,
        "-to", date_to,
        "-t", timeframe_code,
        "-f", "csv",
        "--cache"
    ]

    try:
        # Lister les fichiers existants avant le téléchargement
        existing_files = set()
        if os.path.exists(download_dir):
            existing_files = set(os.listdir(download_dir))

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600,  # 10 min max par instrument
            cwd=TEMP_DIR,
            shell=IS_WINDOWS,
        )

        if result.returncode != 0:
            print(f"[ERREUR]")
            stderr = result.stderr.strip()
            if stderr:
                lines = stderr.split("\n")
                for line in lines[-3:]:
                    print(f"    {line}")
            return False

        # Chercher le fichier CSV généré dans le dossier download/
        # Nom typique : {ticker}-{tf}-bid-{from}-{to}.csv
        found_csv = None

        # Méthode 1 : détecter le nouveau fichier dans download/
        if os.path.exists(download_dir):
            current_files = set(os.listdir(download_dir))
            new_files = current_files - existing_files
            csv_new = [f for f in new_files if f.endswith(".csv")]
            if csv_new:
                found_csv = os.path.join(download_dir, csv_new[0])

        # Méthode 2 : chercher par pattern dans download/
        if not found_csv:
            pattern = os.path.join(download_dir, f"{ticker}-{timeframe_code}*.csv")
            matches = sorted(_glob.glob(pattern), key=os.path.getmtime, reverse=True)
            if matches:
                found_csv = matches[0]

        # Méthode 3 : chercher dans TEMP_DIR directement
        if not found_csv:
            pattern = os.path.join(TEMP_DIR, f"{ticker}*.csv")
            matches = sorted(_glob.glob(pattern), key=os.path.getmtime, reverse=True)
            if matches:
                found_csv = matches[0]

        # Méthode 4 : chercher tout CSV récent dans download/
        if not found_csv and os.path.exists(download_dir):
            all_csvs = [f for f in os.listdir(download_dir) if f.endswith(".csv")]
            # Filtrer par ticker dans le nom
            ticker_csvs = [f for f in all_csvs if ticker in f]
            if ticker_csvs:
                # Prendre le plus récent
                ticker_csvs.sort(key=lambda f: os.path.getmtime(os.path.join(download_dir, f)), reverse=True)
                found_csv = os.path.join(download_dir, ticker_csvs[0])

        if found_csv and os.path.exists(found_csv) and os.path.getsize(found_csv) > 50:
            _shutil.copy2(found_csv, output_csv)
            return True
        else:
            # Peut-être que les données sont sur stdout quand même
            stdout_data = result.stdout.strip()
            if stdout_data and len(stdout_data) > 100:
                # Filtrer les lignes CSV
                lines = stdout_data.split("\n")
                csv_lines = [l.strip() for l in lines if l.strip().count(",") >= 2]
                if len(csv_lines) >= 2:
                    with open(output_csv, "w", encoding="utf-8") as f:
                        f.write("\n".join(csv_lines))
                    return True

            print(f"[ERREUR] Fichier CSV non trouvé après téléchargement.")
            return False

    except subprocess.TimeoutExpired:
        print(f"[ERREUR] Timeout dépassé (10 min).")
        return False
    except Exception as e:
        print(f"[ERREUR] {e}")
        return False


def reformat_csv(input_csv, output_csv):
    """
    Reformate le CSV de dukascopy-node au format standard
    compatible avec le script IG (séparateur ; décimale ,).
    """
    try:
        df = pd.read_csv(input_csv)

        # Colonnes dukascopy-node : timestamp, open, high, low, close, volume
        # Renommer si nécessaire
        col_map = {}
        for col in df.columns:
            cl = col.strip().lower()
            if cl in ("timestamp", "date", "time", "datetime"):
                col_map[col] = "Date"
            elif cl == "open":
                col_map[col] = "Open"
            elif cl == "high":
                col_map[col] = "High"
            elif cl == "low":
                col_map[col] = "Low"
            elif cl == "close":
                col_map[col] = "Close"
            elif cl == "volume":
                col_map[col] = "Volume"

        df = df.rename(columns=col_map)

        # Convertir le timestamp en datetime lisible
        if "Date" in df.columns:
            # Dukascopy retourne des timestamps en millisecondes ou des dates ISO
            sample = str(df["Date"].iloc[0])
            if sample.isdigit() or (sample.startswith("-") and sample[1:].isdigit()):
                df["Date"] = pd.to_datetime(df["Date"], unit="ms")
            else:
                df["Date"] = pd.to_datetime(df["Date"])

        # Garder uniquement les colonnes standard
        cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in df.columns]
        df = df[cols]
        df = df.sort_values("Date").reset_index(drop=True)

        # Sauvegarder au format IG (séparateur ; décimale ,)
        df.to_csv(output_csv, index=False, sep=";", decimal=",")

        return len(df)

    except Exception as e:
        print(f"  [ERREUR reformatage] {e}")
        return 0


# ============================================================
#   POINT D'ENTRÉE
# ============================================================

if __name__ == "__main__":
    total = len(INSTRUMENTS) * len(TIMEFRAMES)

    print("\n" + "=" * 65)
    print("  Téléchargement Historique OHLCV — Dukascopy")
    print("=" * 65)
    print(f"  Instruments : {', '.join(n for n, _, _ in INSTRUMENTS)}")
    print(f"  Timeframes  : {', '.join(label for label, _ in TIMEFRAMES)}")
    print(f"  Période     : depuis la date configurée → {DATE_TO}")
    print(f"  Exports     : {total} fichiers")
    print(f"  Destination : {HIST_DIR}")
    print("=" * 65 + "\n")

    # 1. Vérification Node.js
    if not check_node():
        sys.exit(1)

    # 2. Premier appel npx pour pré-installer dukascopy-node
    print("\n  Vérification de dukascopy-node (premier appel peut prendre 30s)...")
    test = subprocess.run(
        ["npx", "-y", "dukascopy-node", "--help"],
        capture_output=True, text=True, timeout=120,
        shell=IS_WINDOWS,
    )
    if test.returncode == 0:
        print("  ✓ dukascopy-node prêt.\n")
    else:
        print("  ⚠ Problème avec dukascopy-node. Tentative de continuer...\n")

    # 3. Boucle de téléchargement (année par année pour éviter les timeouts)
    job = 0
    successes = 0
    failures = []
    current_year = datetime.now().year

    for instr_name, ticker, date_from in INSTRUMENTS:
        for tf_label, tf_code in TIMEFRAMES:
            job += 1
            final_csv = os.path.join(HIST_DIR, f"historique_{ticker}_{tf_label}.csv")
            start_year = int(date_from[:4])

            print(f"\n  {'═' * 60}")
            print(f"  [{job}/{total}] {instr_name} ({ticker}) — {tf_label}")
            print(f"  Période : {date_from} → {DATE_TO}")
            print(f"  Téléchargement année par année...")
            print(f"  {'═' * 60}")

            year_csvs = []
            year_failures = 0

            for year in range(start_year, current_year + 1):
                y_from = f"{year}-01-01"
                # Le -to de dukascopy-node est exclusif, on prend le 2 janvier
                # pour être sûr d'inclure tout le 31 décembre
                y_to = f"{year + 1}-01-02" if year < current_year else DATE_TO
                raw_csv = os.path.join(TEMP_DIR, f"raw_{ticker}_{tf_code}_{year}.csv")

                print(f"    {year}...", end=" ", flush=True)

                ok = download_instrument(ticker, tf_code, y_from, y_to, raw_csv)

                if ok and os.path.getsize(raw_csv) > 50:
                    year_csvs.append(raw_csv)
                    print("✓", flush=True)
                else:
                    year_failures += 1
                    print("⚠ (pas de données)", flush=True)

            # Fusion de toutes les années en un seul fichier
            if year_csvs:
                # Diagnostic : afficher les premières lignes du premier fichier
                print(f"  Fusion de {len(year_csvs)} fichiers annuels...")
                try:
                    with open(year_csvs[0], "r", encoding="utf-8") as f:
                        preview = [f.readline().strip() for _ in range(3)]
                    print(f"    Aperçu du format :")
                    for line in preview:
                        print(f"      | {line[:100]}")
                except Exception:
                    pass
                all_dfs = []
                for csv_path in year_csvs:
                    try:
                        # Détection automatique du séparateur
                        with open(csv_path, "r", encoding="utf-8") as f:
                            first_line = f.readline()
                        if ";" in first_line and "," not in first_line:
                            sep = ";"
                        elif "\t" in first_line:
                            sep = "\t"
                        else:
                            sep = ","
                        df_chunk = pd.read_csv(csv_path, sep=sep, engine="python",
                                               on_bad_lines="skip")
                        if len(df_chunk.columns) == 1:
                            # Mauvais séparateur détecté, réessayer
                            for try_sep in [",", ";", "\t"]:
                                df_chunk = pd.read_csv(csv_path, sep=try_sep, engine="python",
                                                       on_bad_lines="skip")
                                if len(df_chunk.columns) >= 3:
                                    break
                        all_dfs.append(df_chunk)
                    except Exception as e:
                        print(f"    ⚠ Erreur lecture {csv_path}: {e}")

                if all_dfs:
                    merged = pd.concat(all_dfs, ignore_index=True)

                    # Renommer les colonnes
                    col_map = {}
                    for col in merged.columns:
                        cl = col.strip().lower()
                        if cl in ("timestamp", "date", "time", "datetime"):
                            col_map[col] = "Date"
                        elif cl == "open":
                            col_map[col] = "Open"
                        elif cl == "high":
                            col_map[col] = "High"
                        elif cl == "low":
                            col_map[col] = "Low"
                        elif cl == "close":
                            col_map[col] = "Close"
                        elif cl == "volume":
                            col_map[col] = "Volume"
                    merged = merged.rename(columns=col_map)

                    # Convertir le timestamp
                    if "Date" in merged.columns:
                        sample = str(merged["Date"].iloc[0])
                        if sample.isdigit() or (sample.startswith("-") and sample[1:].isdigit()):
                            merged["Date"] = pd.to_datetime(merged["Date"], unit="ms")
                        else:
                            merged["Date"] = pd.to_datetime(merged["Date"])

                    cols = [c for c in ["Date", "Open", "High", "Low", "Close", "Volume"] if c in merged.columns]
                    merged = merged[cols].sort_values("Date").reset_index(drop=True)
                    merged = merged.drop_duplicates(subset=["Date"])

                    # Sauvegarder au format compatible (séparateur ; décimale ,)
                    merged.to_csv(final_csv, index=False, sep=";", decimal=",")

                    print(f"  ✓ {len(merged):,} bougies exportées → {os.path.basename(final_csv)}")
                    size_mb = os.path.getsize(final_csv) / (1024 * 1024)
                    print(f"  ✓ Taille : {size_mb:.1f} Mo")
                    successes += 1
                else:
                    failures.append(f"{instr_name} ({tf_label}) — erreur fusion")
            else:
                failures.append(f"{instr_name} ({tf_label}) — aucune donnée téléchargée")

            print()

    # 4. Nettoyage des fichiers temporaires
    import shutil
    try:
        shutil.rmtree(TEMP_DIR, ignore_errors=True)
    except Exception:
        pass

    # 5. Résumé final
    print(f"{'=' * 65}")
    print(f"  RÉSUMÉ")
    print(f"{'=' * 65}")
    print(f"  ✓ {successes}/{total} exports réussis")
    if failures:
        print(f"  ✗ {len(failures)} échecs :")
        for f in failures:
            print(f"      - {f}")
    print(f"  Répertoire : {HIST_DIR}")
    print(f"{'=' * 65}\n")

    # Lister les fichiers générés
    csv_files = [f for f in os.listdir(HIST_DIR) if f.endswith(".csv")]
    if csv_files:
        print("  Fichiers générés :")
        for f in sorted(csv_files):
            size = os.path.getsize(os.path.join(HIST_DIR, f))
            size_mb = size / (1024 * 1024)
            print(f"    - {f} ({size_mb:.1f} Mo)")
    print()
