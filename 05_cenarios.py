"""Quanto cada alavanca abriria de vaga, mantendo o resto igual.

Compara tetos diferentes por promotor e mostra quantas lojas passariam a
caber em cada um. O criterio atual e o piso da media.
"""

import pandas as pd
import numpy as np
import math
import sys

sys.stdout.reconfigure(encoding="utf-8")

PASTA = r"C:\dev\roteiro-nintendo"
ROT = r"C:\Users\usuario\Downloads\ROTEIRO OUTUBRO.xlsx"
DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB"]
RAIO_KM = 120


def hav(lat, lon, lats, lons):
    R = 6371.0
    p1, p2 = np.radians(lat), np.radians(np.asarray(lats, dtype=float))
    a = (np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2)
         * np.sin((np.radians(np.asarray(lons, dtype=float)) - np.radians(lon)) / 2) ** 2)
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


db = pd.read_csv(PASTA + r"\db_lojas.csv", dtype={"COD_LOJA": str})
db["_cod"] = db["COD_LOJA"].astype(str).str.strip()
db["LATITUDE"] = pd.to_numeric(db["LATITUDE"], errors="coerce")
db["LONGITUDE"] = pd.to_numeric(db["LONGITUDE"], errors="coerce")
cad = db.drop_duplicates("_cod").set_index("_cod")

rot = pd.read_excel(ROT, sheet_name="ROTEIRO", dtype={"COD_LOJA": str})
rem = pd.read_excel(ROT, sheet_name="LOJAS SENDO REMOVIDAS", dtype={"COD_LOJA": str})
rot["_cod"] = rot["COD_LOJA"].astype(str).str.strip()
rot["LAT"] = rot["_cod"].map(cad["LATITUDE"])
rot["LON"] = rot["_cod"].map(cad["LONGITUDE"])

base = pd.read_csv(PASTA + r"\base_geocodificada.csv", dtype={"CNPJ": str})
cand = base[(~base["NO_ROTEIRO"]) & base["LAT"].notna()].copy()
cand["_prio"] = cand["ATENDIMENTO"].map(
    {"SIM": 0, "PODE TER ATENDIMENTO": 1, "NÃO": 2}).fillna(3)

saindo = rem.groupby("PROMOTOR").size()

perfis = []
for prom, g in rot.groupby("PROMOTOR"):
    carga = {d: int(g[d].notna().sum()) for d in DIAS}
    ativos = [d for d, v in carga.items() if v > 0]
    if not ativos:
        continue
    perfis.append({
        "prom": prom, "carga": carga, "ativos": ativos,
        "media": sum(carga[d] for d in ativos) / len(ativos),
        "pico": max(carga.values()),
        "saindo": int(saindo.get(prom, 0)),
        "lats0": g["LAT"].dropna().tolist(), "lons0": g["LON"].dropna().tolist(),
    })

# distancia de cada candidata ate cada promotor (uma vez so)
tl = {p["prom"]: (np.array(p["lats0"]), np.array(p["lons0"])) for p in perfis}
dist = {}
for i, c in cand.iterrows():
    dist[i] = {p["prom"]: float(min(hav(c["LAT"], c["LON"], *tl[p["prom"]]))) for p in perfis}

cand["_dmin"] = [min(dist[i].values()) for i in cand.index]
ordem = cand.sort_values(["_prio", "_dmin"]).index.tolist()


def rodar(nome, teto_fn, usar_saindo=True):
    vagas = {}
    for p in perfis:
        teto = teto_fn(p)
        folga = sum(max(teto - p["carga"][d], 0) for d in p["ativos"])
        vagas[p["prom"]] = folga + (p["saindo"] if usar_saindo else 0)

    livre = dict(vagas)
    cabem = 0
    sim = 0
    for i in ordem:
        alvo, melhor = None, None
        for p in perfis:
            if livre[p["prom"]] <= 0:
                continue
            d = dist[i][p["prom"]]
            if d <= RAIO_KM and (melhor is None or d < melhor):
                melhor, alvo = d, p["prom"]
        if alvo:
            livre[alvo] -= 1
            cabem += 1
            if cand.at[i, "_prio"] == 0:
                sim += 1

    print(f"{nome:<42}{sum(vagas.values()):>8}{cabem:>9}{sim:>8}")
    return cabem


print(f"{'CENÁRIO':<42}{'VAGAS':>8}{'CABEM':>9}{'SIM':>8}")
print("-" * 67)
rodar("média, piso (critério atual)", lambda p: math.floor(p["media"]))
rodar("média, arredondada", lambda p: round(p["media"]))
rodar("média, teto", lambda p: math.ceil(p["media"]))
rodar("média + 1 loja/dia", lambda p: math.floor(p["media"]) + 1)
rodar("média + 2 lojas/dia", lambda p: math.floor(p["media"]) + 2)
rodar("pico (critério anterior)", lambda p: p["pico"])
print()
rodar("média piso, SEM contar lojas que saem", lambda p: math.floor(p["media"]), False)

print()
print("=" * 67)
print("ONDE ESTÁ A DEMANDA REPRIMIDA")
perto = cand[cand["_dmin"] <= 5]
print(f"candidatas a menos de 5 km de alguma rota: {len(perto)}")
print(perto["ATENDIMENTO"].value_counts().to_string())
print()
print("por UF:")
print(perto["UF"].value_counts().head(8).to_string())
print()
# quanto custa atender todas as de 5km
print(f"para absorver essas {len(perto)}, faltariam ~"
      f"{math.ceil((len(perto) - 55) / (sum(p['media'] for p in perfis) / len(perfis) * 5))} promotores")
