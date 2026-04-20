"""
SAP BW Process Chain Runner - EPFL CO2 Report Travel
=====================================================
Workflow complet :
  1. Récupère le CSV dans .../kuoni/toprocess
  2. Le déplace dans .../kuoni/processing et le renomme en EPFLCO2ReportTravel.csv
  3. Lance la process chain 1, attend la fin (succès requis)
  4. Lance la process chain 2, attend la fin (succès requis)
  5. Déplace le fichier processing → processed avec suffixe date YYYYMMDD
  6. Affiche un message de succès

Prérequis :
    pip install pyrfc
    + SAP NW RFC SDK installé

Usage :
    python sap_process_chain_runner.py
    python sap_process_chain_runner.py --chain1 ZPC_CHAIN_1 --chain2 ZPC_CHAIN_2
    python sap_process_chain_runner.py --config config_sap.json
"""

import argparse
import glob
import json
import os
import shutil
import time
import sys
from datetime import datetime

try:
    from pyrfc import Connection
except ImportError:
    print("ERREUR : Le module 'pyrfc' n'est pas installé.")
    print("  pip install pyrfc")
    print("  + Installer le SAP NW RFC SDK")
    sys.exit(1)


# ─── Configuration par défaut ───────────────────────────────────────────────────

DEFAULT_SAP_CONFIG = {
    "ashost": "sapnwbwd1.epfl.ch",  # Serveur SAP
    "sysnr": "00",                        # Numéro système
    "client": "100",                      # Mandant
    "user": "425063",                   # Utilisateur RFC
    "passwd": "Sopra/2027",                 # Mot de passe
    "lang": "FR"                          # Langue
}

DEFAULT_CHAIN_1 = "W_KU"
DEFAULT_CHAIN_2 = "W_AT"

POLL_INTERVAL_SEC = 30
MAX_WAIT_SEC = 1000

# ─── Chemins réseau ─────────────────────────────────────────────────────────────

BASE_PATH = r"\\scxdata\communOS_bi$\C Courant\Datasources\VPS\bilanco2\in\kuoni"
DIR_TOPROCESS  = os.path.join(BASE_PATH, "toprocess")
DIR_PROCESSING = os.path.join(BASE_PATH, "processing")
DIR_PROCESSED  = os.path.join(BASE_PATH, "processed")

TARGET_FILENAME = "EPFLCO2ReportTravel.csv"

# ─── Statuts process chain SAP BW ───────────────────────────────────────────────

STATUS_MAP = {
    "G": ("Vert - Succès", True, False),
    "R": ("Rouge - Erreur", True, True),
    "X": ("En cours d'exécution", False, False),
    "": ("Pas encore démarrée", False, False),
}


# ─── Utilitaires ────────────────────────────────────────────────────────────────

def log(msg: str):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}")


# ─── Étape 1 & 2 : Récupérer et déplacer le CSV ────────────────────────────────

def prepare_csv() -> str:
    """
    Cherche le CSV dans toprocess, le déplace dans processing
    en le renommant EPFLCO2ReportTravel.csv.
    Retourne le nom original du fichier (pour le renommage final).
    """
    # Chercher les fichiers CSV dans toprocess
    csv_files = glob.glob(os.path.join(DIR_TOPROCESS, "*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"Aucun fichier CSV trouvé dans {DIR_TOPROCESS}")

    if len(csv_files) > 1:
        log(f"ATTENTION : {len(csv_files)} fichiers CSV trouvés, utilisation du plus récent.")
        csv_files.sort(key=os.path.getmtime, reverse=True)

    source_file = csv_files[0]
    original_name = os.path.basename(source_file)
    dest_file = os.path.join(DIR_PROCESSING, TARGET_FILENAME)

    log(f"Fichier source : {source_file}")
    log(f"Déplacement vers : {dest_file}")

    # S'assurer que le répertoire processing existe
    os.makedirs(DIR_PROCESSING, exist_ok=True)

    shutil.move(source_file, dest_file)
    log(f"CSV déplacé et renommé en {TARGET_FILENAME}")

    return original_name


# ─── Étape 7 : Déplacer processing → processed avec date ───────────────────────

def archive_csv():
    """
    Déplace le fichier EPFLCO2ReportTravel.csv de processing vers processed
    en le renommant avec la date du jour (YYYYMMDD).
    Ex: EPFLCO2ReportTravel_20260317.csv
    """
    source_file = os.path.join(DIR_PROCESSING, TARGET_FILENAME)

    if not os.path.exists(source_file):
        raise FileNotFoundError(f"Fichier introuvable : {source_file}")

    date_suffix = datetime.now().strftime("%Y%m%d")
    name, ext = os.path.splitext(TARGET_FILENAME)
    archived_name = f"{name}_{date_suffix}{ext}"
    dest_file = os.path.join(DIR_PROCESSED, archived_name)

    # S'assurer que le répertoire processed existe
    os.makedirs(DIR_PROCESSED, exist_ok=True)

    shutil.move(source_file, dest_file)
    log(f"Fichier archivé : {dest_file}")


# ─── Fonctions SAP ──────────────────────────────────────────────────────────────

def connect_sap(config: dict) -> Connection:
    log(f"Connexion à SAP ({config['ashost']}, mandant {config['client']})...")
    conn = Connection(**config)
    log("Connexion établie.")
    return conn


def start_chain(conn: Connection, chain_id: str):
    log(f"Lancement de la process chain : {chain_id}")
    try:
        result = conn.call("RSPC_API_CHAIN_START", I_CHAIN=chain_id)
        log(f"Process chain {chain_id} démarrée avec succès.")
        return result
    except Exception as e:
        log(f"ERREUR au lancement de {chain_id} : {e}")
        raise


def get_chain_status(conn: Connection, chain_id: str) -> dict:
    try:
        result = conn.call("RSPC_API_CHAIN_GET_STATUS", I_CHAIN=chain_id)
        status_code = result.get("E_STATUS", "")
        label, finished, error = STATUS_MAP.get(
            status_code, (f"Inconnu ({status_code})", False, False)
        )
        return {"status": status_code, "label": label, "finished": finished, "error": error}
    except Exception as e:
        log(f"ERREUR lors de la vérification du statut de {chain_id} : {e}")
        raise


def wait_for_chain(conn: Connection, chain_id: str, poll_interval: int = POLL_INTERVAL_SEC,
                   max_wait: int = MAX_WAIT_SEC) -> bool:
    log(f"Attente de la fin de {chain_id} (toutes les {poll_interval}s, timeout {max_wait}s)...")
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        status = get_chain_status(conn, chain_id)
        log(f"  {chain_id} → {status['label']} ({elapsed}s écoulées)")

        if status["finished"]:
            if status["error"]:
                log(f"ERREUR : {chain_id} s'est terminée en erreur !")
                return False
            else:
                log(f"SUCCÈS : {chain_id} terminée avec succès.")
                return True

    raise TimeoutError(f"Timeout dépassé ({max_wait}s) pour {chain_id}")


# ─── Workflow principal ─────────────────────────────────────────────────────────

def run_workflow(sap_config: dict, chain1: str, chain2: str,
                 poll_interval: int = POLL_INTERVAL_SEC,
                 max_wait: int = MAX_WAIT_SEC):
    """
    Workflow complet :
      1. Préparer le CSV (toprocess → processing, renommage)
      2. Lancer chain 1, attendre succès
      3. Lancer chain 2, attendre succès
      4. Archiver le CSV (processing → processed, suffixe date)
      5. Message de succès
    """
    log("=" * 60)
    log("SAP BW Process Chain Runner - EPFL CO2 Report Travel")
    log(f"  Chain 1 : {chain1}")
    log(f"  Chain 2 : {chain2}")
    log("=" * 60)

    # ── Étape 1-2 : Préparation du CSV ──
    log("─── ÉTAPE 1-2 : Préparation du fichier CSV ───")
    try:
        original_name = prepare_csv()
    except FileNotFoundError as e:
        log(f"ERREUR : {e}")
        return False

    # ── Connexion SAP ──
    conn = connect_sap(sap_config)

    try:
        # ── Étape 3-4 : Process Chain 1 ──
        log("─── ÉTAPE 3 : Lancement Process Chain 1 ───")
        start_chain(conn, chain1)
        success1 = wait_for_chain(conn, chain1, poll_interval, max_wait)

        if not success1:
            log(f"ARRÊT : {chain1} a échoué. La chain 2 ne sera pas lancée.")
            return False

        # ── Étape 5 : Process Chain 2 ──
        log("─── ÉTAPE 4-5 : Lancement Process Chain 2 ───")
        start_chain(conn, chain2)
        success2 = wait_for_chain(conn, chain2, poll_interval, max_wait)

        if not success2:
            log(f"ERREUR : {chain2} s'est terminée en erreur.")
            return False

        # ── Étape 6-7 : Archivage et message de succès ──
        log("─── ÉTAPE 6-7 : Archivage du fichier ───")
        archive_csv()

        log("=" * 60)
        log("SUCCÈS COMPLET !")
        log(f"  Fichier original  : {original_name}")
        log(f"  Process Chain 1   : {chain1} → OK")
        log(f"  Process Chain 2   : {chain2} → OK")
        log(f"  Fichier archivé dans : {DIR_PROCESSED}")
        log("=" * 60)
        return True

    except TimeoutError as e:
        log(f"TIMEOUT : {e}")
        return False
    except Exception as e:
        log(f"ERREUR INATTENDUE : {e}")
        return False
    finally:
        conn.close()
        log("Connexion SAP fermée.")


# ─── CLI ────────────────────────────────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="EPFL CO2 Report Travel - Process Chain Runner"
    )
    parser.add_argument("--chain1", default=DEFAULT_CHAIN_1,
                        help="ID de la première process chain")
    parser.add_argument("--chain2", default=DEFAULT_CHAIN_2,
                        help="ID de la seconde process chain")
    parser.add_argument("--config",
                        help="Fichier JSON de config SAP (ashost, sysnr, client, user, passwd)")
    parser.add_argument("--poll", type=int, default=POLL_INTERVAL_SEC,
                        help="Intervalle de polling en secondes")
    parser.add_argument("--timeout", type=int, default=MAX_WAIT_SEC,
                        help="Timeout max en secondes")
    return parser.parse_args()


def main():
    args = parse_args()

    if args.config:
        with open(args.config, "r") as f:
            sap_config = json.load(f)
        log(f"Configuration chargée depuis {args.config}")
    else:
        sap_config = DEFAULT_SAP_CONFIG
        log("Configuration par défaut (modifier DEFAULT_SAP_CONFIG ou --config)")

    success = run_workflow(
        sap_config=sap_config,
        chain1=args.chain1,
        chain2=args.chain2,
        poll_interval=args.poll,
        max_wait=args.timeout
    )

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
