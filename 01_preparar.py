"""Monta a base de trabalho: lojas da BASE GERAL com a coordenada oficial
do cadastro (bi_d_loja) onde existir, marcando quem ainda falta.

Saida: base_trabalho.csv  (fica em C:\\dev\\roteiro-nintendo, que persiste)
"""

import pandas as pd
import sys

sys.stdout.reconfigure(encoding="utf-8")

PASTA = r"C:\dev\roteiro-nintendo"
BASE = r"C:\Users\usuario\Downloads\BASE GERAL DE LOJAS COM NINTENDO SET 2026.xlsx"
ROT = r"C:\Users\usuario\Downloads\ROTEIRO OUTUBRO.xlsx"


def dig(s):
    return s.astype(str).str.replace(r"\D", "", regex=True).str.zfill(14)


db = pd.read_csv(PASTA + r"\db_lojas.csv", dtype={"NUM_CNPJ": str, "COD_LOJA": str})
db["_c"] = dig(db["NUM_CNPJ"])
db["LATITUDE"] = pd.to_numeric(db["LATITUDE"], errors="coerce")
db["LONGITUDE"] = pd.to_numeric(db["LONGITUDE"], errors="coerce")

base = pd.read_excel(BASE, sheet_name="LOJAS COM NINTENDO GERAL", dtype={"CNPJ": str})
base["_c"] = dig(base["CNPJ"])

rot = pd.read_excel(ROT, sheet_name="ROTEIRO", dtype={"COD_LOJA": str})
rot["_cod"] = rot["COD_LOJA"].astype(str).str.strip()
db["_cod"] = db["COD_LOJA"].astype(str).str.strip()
cad_cod = db.drop_duplicates("_cod").set_index("_cod")
cnpj_no_roteiro = set(rot["_cod"].map(cad_cod["_c"]).dropna()) - {"00000000000000"}

cad = db[db["_c"] != "00000000000000"].drop_duplicates("_c").set_index("_c")
base["LAT"] = base["_c"].map(cad["LATITUDE"])
base["LON"] = base["_c"].map(cad["LONGITUDE"])
base["FONTE"] = base["LAT"].notna().map({True: "cadastro", False: ""})
base["NO_ROTEIRO"] = base["_c"].isin(cnpj_no_roteiro)

print(f"Base: {len(base)} lojas")
print(f"  já no roteiro de outubro: {int(base['NO_ROTEIRO'].sum())}")
print(f"  com coordenada do cadastro: {int(base['LAT'].notna().sum())}")
print(f"  a geocodificar: {int(base['LAT'].isna().sum())}")

base.to_csv(PASTA + r"\base_trabalho.csv", index=False, encoding="utf-8-sig")
print("\nSalvo: base_trabalho.csv")
