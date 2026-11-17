"""Geocodifica as lojas da base que nao estao no cadastro do banco.

RETOMAVEL: grava a cada 20 lojas e, ao iniciar, pula o que ja foi resolvido.
Se a sessao cair, basta rodar de novo que ele continua de onde parou.

Estrategias, em ordem:
  1. rua presa ao municipio (busca estruturada)
  2. marco/shopping que vem depois do travessao no endereco
  3. nome da loja, quando nao ha endereco nenhum (caso VIVO)
  4. centro da cidade, como ultimo recurso

Validacao: coordenada a mais de 30 km do centro da cidade declarada e
descartada - foi assim que pegamos lojas caindo em outro municipio.
"""

import pandas as pd
import numpy as np
import requests
import time
import re
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

PASTA = r"C:\dev\roteiro-nintendo"
ENTRADA = PASTA + r"\base_trabalho.csv"
SAIDA = PASTA + r"\base_geocodificada.csv"
CENTROS = PASTA + r"\cache_centros.csv"

HEADERS = {"User-Agent": "roterizador-exemplo/1.0 (uso interno, roteirizacao de campo)"}
URL = "https://nominatim.openstreetmap.org/search"
RAIO_OK = 30
VAZIO = ("", "—", "-", "nan", "NAN", "#N/D")

ABREV = [(r"\bROD\b\.?", "Rodovia"), (r"\bAV\b\.?", "Avenida"), (r"\bR\b\.", "Rua"),
         (r"\bESTR\b\.?", "Estrada"), (r"\bEST\b\.?", "Estrada"),
         (r"\bPCA\b\.?", "Praça"), (r"\bAL\b\.?", "Alameda")]


def hav(la1, lo1, la2, lo2):
    R = 6371.0
    p1, p2 = np.radians(la1), np.radians(la2)
    a = (np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2)
         * np.sin((np.radians(lo2) - np.radians(lo1)) / 2) ** 2)
    return R * 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))


def buscar(params):
    for _ in range(2):
        try:
            r = requests.get(URL, params={**params, "format": "json", "limit": 1},
                             headers=HEADERS, timeout=20)
            if r.status_code == 200:
                d = r.json()
                if d:
                    return float(d[0]["lat"]), float(d[0]["lon"])
                return None, None
            time.sleep(3)
        except Exception:
            time.sleep(3)
    return None, None


def partes(endereco):
    p = re.split(r"[–—]", str(endereco))
    rua = p[0].strip()
    marco = p[1].strip() if len(p) > 1 else ""
    rua = re.sub(r",?\s*(S/N|SN)\b", "", rua, flags=re.I)
    for pat, sub in ABREV:
        rua = re.sub(pat, sub, rua, flags=re.I)
    return rua.strip(" ,"), marco


def nome_shopping(nome):
    n = str(nome).upper().strip()
    n = n[5:].strip() if n.startswith("LOJA ") else n
    n = re.sub(r"\s*-\s*P?\d+$", "", n)
    n = re.sub(r"\bSHOP\.?\b", "SHOPPING", n)
    n = re.sub(r"\s+(I{1,3})$", "", n)
    return n.strip()


# ---------------- carrega estado anterior (retomada) ----------------
if os.path.exists(SAIDA):
    df = pd.read_csv(SAIDA, dtype={"CNPJ": str})
    print("retomando trabalho anterior")
else:
    df = pd.read_csv(ENTRADA, dtype={"CNPJ": str})

if "TENTADO" not in df.columns:
    df["TENTADO"] = False

centros = {}
if os.path.exists(CENTROS):
    c = pd.read_csv(CENTROS)
    centros = {(r["cidade"], r["uf"]): (r["lat"], r["lon"]) for _, r in c.iterrows()}


def salvar():
    df.to_csv(SAIDA, index=False, encoding="utf-8-sig")
    pd.DataFrame([{"cidade": k[0], "uf": k[1], "lat": v[0], "lon": v[1]}
                  for k, v in centros.items()]).to_csv(CENTROS, index=False, encoding="utf-8-sig")


def centro(cidade, uf):
    ch = (str(cidade).strip().upper(), str(uf).strip().upper())
    if ch not in centros:
        la, lo = buscar({"city": cidade, "state": uf, "country": "Brasil"})
        time.sleep(1.05)
        if la is None:
            la, lo = buscar({"q": f"{cidade}, {uf}, Brasil", "countrycodes": "br"})
            time.sleep(1.05)
        centros[ch] = (la, lo)
    return centros[ch]


pend = df[df["LAT"].isna() & (~df["TENTADO"].astype(bool))].index.tolist()
print(f"pendentes: {len(pend)} (de {len(df)})\n")

feitos = 0
for n, idx in enumerate(pend, start=1):

    endereco = str(df.at[idx, "ENDEREÇO"]).strip()
    cidade = str(df.at[idx, "CIDADE"]).strip()
    uf = str(df.at[idx, "UF"]).strip()
    nome = str(df.at[idx, "LOJA"]).strip()

    lat = lon = None
    fonte = ""

    if cidade not in VAZIO:
        clat, clon = centro(cidade, uf)

        if endereco not in VAZIO:
            rua, marco = partes(endereco)
            tent = []
            if rua:
                tent.append({"street": rua, "city": cidade, "state": uf, "country": "Brasil"})
            if marco:
                tent.append({"q": f"{marco}, {cidade}, {uf}, Brasil", "countrycodes": "br"})
            for p in tent:
                la, lo = buscar(p)
                time.sleep(1.05)
                if la is None:
                    continue
                if clat is not None and hav(la, lo, clat, clon) > RAIO_OK:
                    continue
                lat, lon, fonte = la, lo, "endereço"
                break

        if lat is None and clat is not None:
            lat, lon, fonte = clat, clon, "centro da cidade"

    else:
        limpo = nome_shopping(nome)
        if limpo:
            for q in [f"{limpo}, {uf}, Brasil", f"Shopping {limpo}, {uf}, Brasil"]:
                la, lo = buscar({"q": q, "countrycodes": "br"})
                time.sleep(1.05)
                if la is not None:
                    lat, lon, fonte = la, lo, "nome do shopping"
                    break

    df.at[idx, "TENTADO"] = True
    if lat is not None:
        df.at[idx, "LAT"] = lat
        df.at[idx, "LON"] = lon
        df.at[idx, "FONTE"] = fonte
        feitos += 1

    if n % 20 == 0:
        salvar()
        print(f"[{n}/{len(pend)}] resolvidas nesta rodada: {feitos}", flush=True)

salvar()

print()
print("===== RESUMO =====")
print(df["FONTE"].fillna("sem coordenada").replace("", "sem coordenada").value_counts().to_string())
print(f"\nCom coordenada: {int(df['LAT'].notna().sum())} de {len(df)}")
print("FIM")
