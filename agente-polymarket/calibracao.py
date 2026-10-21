#!/usr/bin/env python3
"""Calibração do agente: as probabilidades que ele dá batem com a realidade?

Lê previsoes.csv (colunas: previsao, probabilidade, resultado; resultado 1 = aconteceu,
0 = não aconteceu, vazio = ainda não resolvido) e mostra:
  1. previsões agrupadas por faixa de 10 pontos
  2. probabilidade média dada vs frequência real em cada faixa
  3. Brier score geral, em português simples
  4. se ele é otimista ou pessimista demais, e quanto
"""

import csv
import os
import sys

PADRAO = os.path.join(os.environ.get("AGENTE_DADOS", os.path.join(os.path.dirname(os.path.abspath(__file__)), "dados")),
                      "previsoes.csv")


def main(caminho):
    if not os.path.exists(caminho):
        sys.exit(f"Arquivo não encontrado: {caminho}")
    with open(caminho, encoding="utf-8", newline="") as f:
        linhas = [(float(r["probabilidade"]), int(r["resultado"]))
                  for r in csv.DictReader(f) if r.get("resultado") in ("0", "1")]
    if not linhas:
        sys.exit("Nenhuma previsão resolvida ainda; sem calibração para medir.")

    faixas = {}
    for p, y in linhas:
        faixas.setdefault(min(int(p * 10), 9), []).append((p, y))

    print(f"{'Faixa':<10}{'N':>5}{'Prob. dada':>13}{'Freq. real':>13}{'Diferença':>12}")
    for k in sorted(faixas):
        v = faixas[k]
        dada = sum(p for p, _ in v) / len(v)
        real = sum(y for _, y in v) / len(v)
        print(f"{k * 10:>3}-{k * 10 + 10:<3}% {len(v):>5}{dada * 100:>12.1f}%{real * 100:>12.1f}%"
              f"{(dada - real) * 100:>+11.1f}")

    n = len(linhas)
    brier = sum((p - y) ** 2 for p, y in linhas) / n
    base = sum(y for _, y in linhas) / n
    brier_ingenuo = base * (1 - base)  # quem sempre chuta a taxa média
    vies = sum(p - y for p, y in linhas) / n
    ece = sum(abs(sum(p for p, _ in v) / len(v) - sum(y for _, y in v) / len(v)) * len(v)
              for v in faixas.values()) / n

    print(f"\nPrevisões resolvidas: {n}")
    print(f"Brier score: {brier:.3f}  (0 = perfeito; 0,25 = chutar 50% em tudo; quanto menor, melhor)")
    print(f"Referência: quem sempre dissesse {base * 100:.0f}% teria {brier_ingenuo:.3f}.")
    if brier < brier_ingenuo:
        print("Em português simples: as probabilidades dele carregam informação; "
              "erram menos do que um chute fixo.")
    else:
        print("Em português simples: ele não está melhor que um chute fixo; "
              "as probabilidades dele não merecem dinheiro ainda.")
    print(f"Erro médio de calibração: {ece * 100:.1f} pontos (é o 'erro' que entra no critério de entrada).")
    if abs(vies) < 0.02:
        print(f"Viés: equilibrado ({vies * 100:+.1f} pontos).")
    elif vies > 0:
        print(f"Viés: OTIMISTA demais — dá em média {vies * 100:.1f} pontos a mais do que acontece.")
    else:
        print(f"Viés: PESSIMISTA demais — dá em média {-vies * 100:.1f} pontos a menos do que acontece.")
    if n < 30:
        print(f"Atenção: só {n} previsões; com menos de 30 a medida ainda é ruído.")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else PADRAO)
