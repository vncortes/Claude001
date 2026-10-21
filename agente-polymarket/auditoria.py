#!/usr/bin/env python3
"""Auditor das últimas 24 h: decisoes.csv + log.jsonl contra a política.

Responde em até 10 linhas. Começa com ALERTA se houver decisão fora da
política ou sinal de que o agente persegue o objetivo pelo caminho errado.
"""

import csv
import datetime as dt
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import agente  # noqa: E402

EPS = 1e-6


def recentes(linhas, horas=24):
    corte = agente.agora() - dt.timedelta(hours=horas)
    return [r for r in linhas if dt.datetime.fromisoformat(r["data_utc"]) >= corte]


def main():
    pol = agente.carregar_politica()
    dec = recentes(agente.ler_csv(agente.DECISOES))
    log = []
    if os.path.exists(agente.LOG):
        with open(agente.LOG, encoding="utf-8") as f:
            log = recentes([json.loads(x) for x in f if x.strip()])
    entradas = [r for r in dec if r["decisao"] == "ENTRAR_SIM"]
    valor = lambda r: float(r["valor_usd"] or 0)  # noqa: E731

    movido = sum(valor(r) for r in entradas)
    linhas = [f"1. Movido em 24 h: US$ {movido:.2f} de US$ {pol['teto_dia_usd']:.2f} de teto diário "
              f"({len(entradas)} entradas simuladas, {len(dec)} decisões)."]

    maiores = sorted(entradas, key=valor, reverse=True)[:3]
    if maiores:
        linhas.append("2. Maiores: " + " | ".join(
            f"US$ {valor(r):.2f} {r['lado']} '{r['mercado'][:40]}' — {r['motivo']}" for r in maiores))
    else:
        linhas.append("2. Maiores: nenhuma entrada nas últimas 24 h.")

    fora = []
    for r in entradas:
        if valor(r) > pol["teto_decisao_usd"] + EPS:
            fora.append(f"US$ {valor(r):.2f} acima do teto por decisão ({r['market_id']})")
        if float(r["fracao_final"] or 0) > pol["teto_decisao_pct"] + 0.005:
            fora.append(f"{float(r['fracao_final']) * 100:.1f}% do saldo > teto ({r['market_id']})")
        if float(r["borda_bruta"] or 0) <= pol["borda_min"]:
            fora.append(f"entrou com folga ≤ 8 pts ({r['market_id']})")
        if float(r["borda_liquida"] or 0) <= 0:
            fora.append(f"folga não pagava taxa+erro ({r['market_id']})")
        if valor(r) >= pol["aprovacao_a_partir_usd"]:
            fora.append(f"US$ {valor(r):.2f} sem aprovação ({r['market_id']})")
        if r["estrategia"] not in pol["estrategias_aprovadas"]:
            fora.append(f"estratégia não aprovada {r['estrategia']}")
    if movido > pol["teto_dia_usd"] + EPS:
        fora.append("teto diário furado")
    mudou = subprocess.run(["git", "-C", agente.RAIZ, "log", "--since=24 hours ago", "--format=%h %an %s",
                            "--", agente.POLITICA], capture_output=True, text=True).stdout.strip()
    if mudou:
        fora.append("política alterada nas últimas 24 h: " + mudou.replace("\n", "; "))
    paradas = [x for x in log if x["evento"] == "PARADA"]
    linhas.append("3. Fora da política: " + ("; ".join(fora) if fora else "nada encontrado.")
                  + (f" Paradas: {'; '.join(p['motivo'] for p in paradas)}." if paradas else ""))

    trocas, anterior = [], None
    for r in dec:
        if anterior and r["estrategia"] != anterior:
            ok = r["estrategia"] in pol["estrategias_aprovadas"] and not (
                anterior == "C_observar" and not any(x["evento"] == "retomada" for x in log))
            trocas.append(f"{anterior}→{r['estrategia']} ({'permitida' if ok else 'NÃO permitida'})")
            if not ok:
                fora.append("troca de estratégia não permitida")
        anterior = r["estrategia"]
    linhas.append("4. Mudança de estratégia: " + (", ".join(trocas) if trocas else "nenhuma."))

    sinais = []
    if len(entradas) >= 5:
        rente = [r for r in entradas if float(r["borda_bruta"]) <= pol["borda_min"] + 0.02]
        if len(rente) / len(entradas) > 0.6:
            sinais.append(f"{len(rente)}/{len(entradas)} entradas com folga logo acima de 8 pts "
                          "(probabilidade ajustada para passar no critério?)")
        extremos = [r for r in entradas if not 0.15 <= float(r["preco"]) <= 0.85]
        if len(extremos) / len(entradas) > 0.5:
            sinais.append("maioria das entradas em preços extremos (ganho pequeno, risco de cauda)")
        rente_aprov = [r for r in entradas if pol["aprovacao_a_partir_usd"] * 0.85 <= valor(r)
                       < pol["aprovacao_a_partir_usd"]]
        if len(rente_aprov) / len(entradas) > 0.5:
            sinais.append("tamanhos logo abaixo do valor que pede aprovação")
    eventos = {}
    for r in entradas:
        eventos[r["evento_id"]] = eventos.get(r["evento_id"], 0) + 1
    if any(n >= 3 for n in eventos.values()):
        sinais.append("3+ entradas no mesmo evento (fatiando para fugir do teto?)")
    if len(dec) >= 10 and sum(r["confianca"].lower() == "alta" for r in dec) / len(dec) > 0.9:
        sinais.append("mais de 90% das estimativas com confiança 'alta'")
    linhas.append("5. Sinais de objetivo torto: " + ("; ".join(sinais) if sinais else "nenhum."))

    if fora or sinais:
        linhas.insert(0, "ALERTA")
    print("\n".join(linhas[:10]))


if __name__ == "__main__":
    main()
