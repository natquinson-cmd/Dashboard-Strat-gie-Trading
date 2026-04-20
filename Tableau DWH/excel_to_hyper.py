"""
Generate initial .hyper file from the historical Excel file
'Perimetre_Migration - Stockage Finale DataPrep.xlsx'
Same structure (columns + types) as defined in the .tds pivot source.
"""
import pandas as pd
from tableauhyperapi import (
    HyperProcess, Telemetry, Connection, CreateMode, NOT_NULLABLE, NULLABLE,
    SqlType, TableDefinition, Inserter, TableName, HyperException
)
from pathlib import Path

EXCEL = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration - Stockage Finale DataPrep.xlsx"
HYPER = r"\\scxdata\CommunOS_BI$\C Courant\Datasources\ISCS-BI\SuiviProjetDWH\flatfiles\Perimetre_Migration.hyper"
SHEET = "Perimetre_Migration"  # without the $ (pandas reads it without)

print(f"Reading Excel: {EXCEL}")
df = pd.read_excel(EXCEL, sheet_name=SHEET)
print(f"  Rows: {len(df)}, Columns: {len(df.columns)}")

# Normalize column names: replace newlines with spaces, collapse spaces
df.columns = [str(c).replace("\n", " ").replace("  ", " ").strip() for c in df.columns]
# Drop unnamed/empty columns
df = df.loc[:, ~df.columns.str.startswith("Unnamed")]
print(f"  After normalization: {len(df.columns)} columns")

# Column definitions from the .tds (Excel source, before pivot)
# Order matters to match ordinals
cols_spec = [
    ("DateDujour", "date"),
    ("Nom dataset", "string"),
    ("Type source", "string"),
    ("Nom source", "string"),
    ("Description source", "string"),
    ("Chemin source", "string"),
    ("Type rapport", "string"),
    ("Nom rapport", "string"),
    ("Description rapport", "string"),
    ("Chemin rapport", "string"),
    ("Projet", "string"),
    ("Domaine", "string"),
    ("Sous-domaine", "string"),
    ("Métier", "string"),
    ("PO métier", "string"),
    ("Utilisation 2023", "string"),
    ("REF BI01", "string"),
    ("REF BI02", "string"),
    ("# Ouverture 2024 (Hors DEV BI)", "string"),
    ("# Ouverture 2024 (Manual Edition)", "string"),
    ("# Ouverture 2025 (Hors DEV BI)", "string"),
    ("# Ouverture 2025 (Manual Edition)", "string"),
    ("# Utilisateurs 2025 ( Hors Dev BI)", "string"),
    ("# Utilisateurs 2025 (Manual Edition)", "string"),
    ("Utilisateurs", "integer"),
    ("Pertinence de reprise dans le cadre du projet", "string"),
    ("Commentaire Pertinence", "string"),
    ("Cibles", "string"),
    ("Commentaire Cibles", "string"),
    ("Flux cible BI", "string"),
    ("Rapport cible BI", "string"),
    ("Temporalité nécessaire", "string"),
    ("Temporalité présente dans système source", "string"),
    ("Rapport cible embedded", "string"),
    ("Charge", "string"),
    ("Date d'échéance", "date"),
    ("Echéance", "string"),
    ("Priorité", "string"),
    ("Stratégique", "string"),
    ("Complexité flux", "string"),
    ("Complexité viz", "string"),
    ("Commentaire Complexité", "string"),
    ("Statut Cadrage conception", "string"),
    ("Statut Conception", "string"),
    ("Statut flux", "string"),
    ("Statut reporting", "string"),
    ("Date début réalisation", "string"),
    ("Date de fin livraison Flux", "string"),
    ("Date de fin de livraison VIZ", "date"),
    ("F50", "real"),
    ("Num Semaine", "string"),
]

# Add any extra columns that are in the Excel but not in spec (as string)
excel_cols = set(df.columns)
spec_cols = set(c[0] for c in cols_spec)
extras = [c for c in df.columns if c not in spec_cols]
if extras:
    print(f"  Extra columns in Excel not in .tds spec: {extras}")
    for c in extras:
        cols_spec.append((c, "string"))

def to_hyper_type(t):
    if t == "string": return SqlType.text()
    if t == "integer": return SqlType.big_int()
    if t == "real": return SqlType.double()
    if t == "date": return SqlType.date()
    return SqlType.text()

def convert_value(val, t):
    if pd.isna(val):
        return None
    if t == "date":
        if hasattr(val, "date"):
            return val.date()
        try:
            return pd.to_datetime(val).date()
        except Exception:
            return None
    if t == "integer":
        try:
            return int(val)
        except Exception:
            return None
    if t == "real":
        try:
            return float(val)
        except Exception:
            return None
    return str(val)

Path(HYPER).parent.mkdir(parents=True, exist_ok=True)
print(f"Creating Hyper: {HYPER}")

with HyperProcess(telemetry=Telemetry.DO_NOT_SEND_USAGE_DATA_TO_TABLEAU) as hyper:
    with Connection(endpoint=hyper.endpoint, database=HYPER,
                    create_mode=CreateMode.CREATE_AND_REPLACE) as conn:
        conn.catalog.create_schema("Extract")
        table = TableDefinition(
            table_name=TableName("Extract", "Perimetre_Migration"),
            columns=[
                TableDefinition.Column(name, to_hyper_type(t), NULLABLE)
                for name, t in cols_spec
            ]
        )
        conn.catalog.create_table(table)

        # Reorder df columns to match spec (missing cols filled with None)
        for name, _ in cols_spec:
            if name not in df.columns:
                df[name] = None
        df_ordered = df[[name for name, _ in cols_spec]]

        rows_to_insert = []
        for _, row in df_ordered.iterrows():
            rows_to_insert.append([
                convert_value(row[name], t) for name, t in cols_spec
            ])

        with Inserter(conn, table) as inserter:
            inserter.add_rows(rows_to_insert)
            inserter.execute()

        row_count = conn.execute_scalar_query(
            f'SELECT COUNT(*) FROM {table.table_name}'
        )
        print(f"  Inserted {row_count} rows into {table.table_name}")

print("Done.")
