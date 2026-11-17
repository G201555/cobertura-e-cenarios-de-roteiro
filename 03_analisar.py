"""Quais lojas da BASE GERAL cabem no ROTEIRO DE OUTUBRO com a equipe atual.

Capacidade (criterio definido pela operacao): o teto de cada promotor e a
MEDIA de lojas por dia que ele ja faz, nao o pico. Dias abaixo da media sao
nivelados ate ela; dias acima ficam como estao. Soma-se a isso as lojas que
estao saindo do roteiro, que liberam visita.
"""

import pandas as pd
import numpy as np
import sys
import math

sys.stdout.reconfigure(encoding="utf-8")

PASTA = r"C:\dev\roteiro-nintendo"
ROT = r"C:\Users\usuario\Downloads\ROTEIRO OUTUBRO.xlsx"

DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB"]
RAIO_KM = 120

# quantas lojas/dia acima da media cada promotor pode assumir.
# 0 = so nivela os dias fracos ate a media; 1 = media + 1 loja por dia.
AJUSTE_TETO = int(sys.argv[1]) if len(sys.argv) > 1 else 0

SAIDA = PASTA + (r"\LOJAS PARA INCLUIR - OUTUBRO.xlsx" if AJUSTE_TETO == 0
                 else rf"\LOJAS PARA INCLUIR - OUTUBRO (media+{AJUSTE_TETO}).xlsx")


def dig(s):
    return s.astype(str).str.replace(r"\D", "", regex=True).str.zfill(14)


def hav(lat, lon, lats, lons):
    R = 6371.0
    p1, p2 = np.radians(lat), np.radians(np.asarray(lats, dtype=float))
    a = (np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2)
         * np.sin((np.radians(np.asarray(lons, dtype=float)) - np.radians(lon)) / 2) ** 2)
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


db = pd.read_csv(PASTA + r"\db_lojas.csv", dtype={"NUM_CNPJ": str, "COD_LOJA": str})
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
print(f"Base: {len(base)} | com coordenada: {int(base['LAT'].notna().sum())}")
print(f"Roteiro: {len(rot)} lojas | com coordenada: {int(rot['LAT'].notna().sum())}")

# ------------------------------------------------- capacidade pela MEDIA
saindo = rem.groupby("PROMOTOR").size()

equipe = []
for prom, g in rot.groupby("PROMOTOR"):
    carga = {d: int(g[d].notna().sum()) for d in DIAS}
    ativos = [d for d, v in carga.items() if v > 0]
    if not ativos:
        continue
    media = sum(carga[d] for d in ativos) / len(ativos)
    teto = math.floor(media) + AJUSTE_TETO
    folga = sum(max(teto - carga[d], 0) for d in ativos)
    equipe.append({
        "promotor": prom,
        "uf": g["UF"].mode().iat[0] if len(g["UF"].mode()) else "",
        "lojas": len(g),
        "visitas_semana": sum(carga.values()),
        "dias": len(ativos),
        "media_dia": round(media, 1),
        "teto": teto,
        "pico": max(carga.values()),
        "folga_nivelando": folga,
        "saindo": int(saindo.get(prom, 0)),
        "lats": g["LAT"].dropna().tolist(),
        "lons": g["LON"].dropna().tolist(),
    })

for e in equipe:
    e["vagas"] = e["folga_nivelando"] + e["saindo"]
    e["restantes"] = e["vagas"]

eq = pd.DataFrame([{k: v for k, v in e.items() if k not in ("lats", "lons", "restantes")}
                   for e in equipe])
print(f"\nEquipe: {len(eq)} promotores")
print(f"Folga nivelando pela média: {int(eq['folga_nivelando'].sum())} visitas/semana")
print(f"Liberado pelas lojas que saem: {int(eq['saindo'].sum())}")
print(f"VAGAS TOTAIS: {int(eq['vagas'].sum())}")

# ------------------------------------------------------------ candidatas
cand = base[(~base["NO_ROTEIRO"]) & base["LAT"].notna()].copy()
sem = base[(~base["NO_ROTEIRO"]) & base["LAT"].isna()]
print(f"\nCandidatas com coordenada: {len(cand)} | sem coordenada: {len(sem)}")

# A marcacao ATENDIMENTO da base nao entra na fila: ela esta fora de sincronia
# com a operacao (lojas marcadas SIM fora do roteiro e NAO sendo visitadas).
# Criterio: quem esta mais perto de uma rota existente entra primeiro.
cand["_dist"] = [min(min(hav(r["LAT"], r["LON"], e["lats"], e["lons"])) for e in equipe)
                 for _, r in cand.iterrows()]
cand = cand.sort_values("_dist").reset_index(drop=True)

res = []
for _, c in cand.iterrows():
    alvo, melhor = None, None
    for e in equipe:
        if e["restantes"] <= 0:
            continue
        d = min(hav(c["LAT"], c["LON"], e["lats"], e["lons"]))
        if d <= RAIO_KM and (melhor is None or d < melhor):
            melhor, alvo = d, e

    if alvo is not None:
        alvo["restantes"] -= 1
        alvo["lats"].append(c["LAT"]); alvo["lons"].append(c["LON"])
        sit, quem, dd = "Cabe", alvo["promotor"], round(melhor, 1)
    else:
        prox = min(equipe, key=lambda e: min(hav(c["LAT"], c["LON"], e["lats"], e["lons"])))
        sit, quem, dd = "Não cabe", prox["promotor"], round(c["_dist"], 1)

    res.append({
        "Situação": sit,
        "Marcada na base como": c["ATENDIMENTO"],
        "Promotor sugerido": quem,
        "Distância até a rota (km)": dd,
        "Rede": c["REDE"], "Loja": c["LOJA"], "CNPJ": c["CNPJ"],
        "Endereço": c["ENDEREÇO"], "Cidade": c["CIDADE"], "UF": c["UF"],
        "Origem da coordenada": c["FONTE"],
        "Latitude": c["LAT"], "Longitude": c["LON"],
    })

res = pd.DataFrame(res)
cabem = res[res["Situação"] == "Cabe"]
naocabem = res[res["Situação"] == "Não cabe"]

print(f"\n=== RESULTADO ===")
print(f"Cabem: {len(cabem)}")
print(cabem["Marcada na base como"].value_counts().to_string())
print(f"\nNão cabem: {len(naocabem)}")
print(f"  a menos de 5 km de uma rota (falta vaga): "
      f"{int((naocabem['Distância até a rota (km)'] <= 5).sum())}")
print(f"  a mais de {RAIO_KM} km (longe demais): "
      f"{int((naocabem['Distância até a rota (km)'] > RAIO_KM).sum())}")

usado = {e["promotor"]: e["vagas"] - e["restantes"] for e in equipe}
eq["lojas_sugeridas"] = eq["promotor"].map(usado).fillna(0).astype(int)
eq["ainda_sobra"] = eq["vagas"] - eq["lojas_sugeridas"]

eq_out = eq.rename(columns={
    "promotor": "Promotor", "uf": "UF", "lojas": "Lojas hoje",
    "visitas_semana": "Visitas/semana", "dias": "Dias que trabalha",
    "media_dia": "Média lojas/dia", "teto": "Teto usado", "pico": "Dia mais cheio",
    "folga_nivelando": "Folga nivelando", "saindo": "Lojas saindo",
    "vagas": "Vagas totais", "lojas_sugeridas": "Lojas sugeridas",
    "ainda_sobra": "Ainda sobra",
}).sort_values("Vagas totais", ascending=False)

sem_out = sem[["ATENDIMENTO", "REDE", "LOJA", "ENDEREÇO", "CIDADE", "UF", "CNPJ"]]

with pd.ExcelWriter(SAIDA, engine="openpyxl") as w:
    eq_out.to_excel(w, sheet_name="CAPACIDADE DA EQUIPE", index=False)
    cabem.drop(columns=["Situação"]).to_excel(w, sheet_name="CABEM", index=False)
    naocabem.drop(columns=["Situação"]).to_excel(w, sheet_name="NAO CABEM", index=False)
    if len(sem_out):
        sem_out.to_excel(w, sheet_name="SEM COORDENADA", index=False)
    for nome in w.sheets:
        ws = w.sheets[nome]
        for col in ws.columns:
            larg = max((len(str(x.value)) if x.value is not None else 0) for x in col)
            ws.column_dimensions[col[0].column_letter].width = min(larg + 2, 46)
        ws.freeze_panes = "A2"

print("\nSalvo:", SAIDA)
