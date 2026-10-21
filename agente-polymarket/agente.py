#!/usr/bin/env python3
"""Agente Polymarket em modo simulação.

Comandos:
  varrer      lê todos os mercados abertos e grava os candidatos do ciclo
  decidir     aplica critério, Kelly e política às estimativas do agente
  liquidar    marca a carteira a mercado e fecha previsões resolvidas
  estado      mostra saldo, exposição e gatilhos de parada
  parar       dispara a parada total na mão
  retomar     volta de uma parada (exige aprovação do dono)
  teste-parada  teste mensal do botão de parada

Não existe código de envio de ordem: toda decisão é simulada.
Só usa a biblioteca padrão do Python.
"""

import argparse
import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request

RAIZ = os.path.dirname(os.path.abspath(__file__))
DADOS = os.environ.get("AGENTE_DADOS", os.path.join(RAIZ, "dados"))  # outra pasta só para testes
POLITICA = os.path.join(RAIZ, "politica-de-risco.md")
CARTEIRA = os.path.join(DADOS, "carteira.json")
CANDIDATOS = os.path.join(DADOS, "candidatos.json")
DECISOES = os.path.join(DADOS, "decisoes.csv")
PREVISOES = os.path.join(DADOS, "previsoes.csv")
LOG = os.path.join(DADOS, "log.jsonl")
PARAR_LOCAL = os.path.join(RAIZ, "PARAR")

GAMMA = "https://gamma-api.polymarket.com"
UA = {"User-Agent": "agente-polymarket-simulacao/0.1"}
MODO_TESTE = False  # teste-parada liga isto para não sujar o log com paradas falsas

COLUNAS_DECISOES = [
    "data_utc", "estrategia", "market_id", "evento_id", "mercado", "lado",
    "p_agente", "confianca", "preco", "taxa_cota", "erro", "borda_bruta",
    "borda_liquida", "kelly_cheio", "fracao_final", "valor_usd", "cotas",
    "decisao", "motivo", "fontes", "justificativa",
]
COLUNAS_PREVISOES = [
    "data_utc", "market_id", "previsao", "probabilidade", "preco_mercado",
    "resultado",
]


# ---------- utilitários ----------

def agora():
    return dt.datetime.now(dt.timezone.utc)


def hoje():
    return agora().date().isoformat()


def registrar(evento, **campos):
    os.makedirs(DADOS, exist_ok=True)
    if MODO_TESTE:
        evento = "teste_" + evento
    linha = {"data_utc": agora().isoformat(timespec="seconds"), "evento": evento, **campos}
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    return linha


def avisar(msg):
    """Linha que o loop transforma em notificação para o dono."""
    print(f"{'TESTE' if MODO_TESTE else 'AVISAR'}: {msg}")
    registrar("aviso", mensagem=msg)


def carregar_politica():
    with open(POLITICA, encoding="utf-8") as f:
        texto = f.read()
    blocos = re.findall(r"```json\n(.*?)\n```", texto, re.S)
    if len(blocos) != 1:
        sys.exit("ERRO: politica-de-risco.md precisa de exatamente um bloco ```json")
    return json.loads(blocos[0])


def politica_intacta():
    """Falso se a política tem alterações não commitadas (alguém mexeu)."""
    r = subprocess.run(["git", "-C", RAIZ, "status", "--porcelain", "--", POLITICA],
                       capture_output=True, text=True)
    return r.returncode == 0 and r.stdout.strip() == ""


def http_json(caminho, params):
    url = f"{GAMMA}{caminho}?{urllib.parse.urlencode(params, doseq=True)}"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def lista_json(v):
    if isinstance(v, list):
        return v
    try:
        return json.loads(v or "[]")
    except ValueError:
        return []


# ---------- carteira simulada ----------

def carteira_nova(pol):
    return {
        "saldo_inicial": pol["saldo_inicial_usd"],
        "caixa": pol["saldo_inicial_usd"],
        "posicoes": [],
        "valor_inicio_dia": {},
        "resultado_dia": {},
        "entradas_dia": {},
        "entradas_mes": {},
        "falhas_api": 0,
        "estrategia": "A_valor",
        "pausa_ate": None,
        "parada": None,
        "retomado_em": None,
    }


def ler_carteira(pol):
    if not os.path.exists(CARTEIRA):
        return carteira_nova(pol)
    with open(CARTEIRA, encoding="utf-8") as f:
        return json.load(f)


def gravar_carteira(c):
    os.makedirs(DADOS, exist_ok=True)
    with open(CARTEIRA, "w", encoding="utf-8") as f:
        json.dump(c, f, ensure_ascii=False, indent=2)


def valor_carteira(c):
    return c["caixa"] + sum(p["cotas"] * p.get("preco_atual", p["preco"]) for p in c["posicoes"])


def tetos_do_dia(pol, c):
    """Tetos valendo hoje; pela metade no primeiro dia após retomada."""
    fator = 0.5 if c.get("retomado_em") == hoje() else 1.0
    return {k: pol[k] * fator for k in
            ("teto_decisao_pct", "teto_decisao_usd", "teto_evento_pct",
             "teto_dia_usd", "teto_mes_usd", "exposicao_max_pct")}


# ---------- parada ----------

def parar_remoto(pol):
    """True se existe agente-polymarket/PARAR no branch do GitHub.
    None se não deu para verificar (conta como falha: sem entradas novas)."""
    branch = pol["branch_parada"]
    f = subprocess.run(["git", "-C", RAIZ, "fetch", "-q", "origin", branch],
                       capture_output=True, text=True, timeout=60)
    if f.returncode != 0:
        return None
    r = subprocess.run(["git", "-C", RAIZ, "cat-file", "-e", "FETCH_HEAD:agente-polymarket/PARAR"],
                       capture_output=True)
    return r.returncode == 0


def disparar_parada(c, motivo):
    if not c.get("parada"):
        c["parada"] = {"motivo": motivo, "data_utc": agora().isoformat(timespec="seconds")}
        registrar("PARADA", motivo=motivo)
        avisar(f"PARADA TOTAL: {motivo}. Nada novo entra; posições congeladas. "
               "Para voltar: python3 agente-polymarket/agente.py retomar --dono")


def checar_gatilhos(pol, c, remoto=True):
    """Aplica todos os gatilhos de parada. Devolve True se pode operar."""
    if not politica_intacta():
        disparar_parada(c, "politica-de-risco.md alterada sem commit")
    if os.path.exists(PARAR_LOCAL):
        disparar_parada(c, "arquivo PARAR local")
    if remoto:
        r = parar_remoto(pol)
        if r:
            disparar_parada(c, "arquivo PARAR no GitHub")
        elif r is None:
            avisar("não consegui verificar o botão de parada no GitHub; sem entradas neste ciclo")
            return False
    valor = valor_carteira(c)
    if valor <= c["saldo_inicial"] * (1 - pol["perda_total_pct"]):
        disparar_parada(c, f"perda total: valor US$ {valor:.2f}")
    dias = sorted(c["resultado_dia"].items())[-pol["dias_abaixo_meta_parada"]:]
    if len(dias) == pol["dias_abaixo_meta_parada"] and all(v < 0 for _, v in dias):
        disparar_parada(c, f"{len(dias)} dias seguidos abaixo da meta")
    if c["falhas_api"] >= pol["falhas_api_parada"]:
        disparar_parada(c, f"API fora do ar {c['falhas_api']} ciclos seguidos")
    if c.get("parada"):
        return False
    if c["falhas_api"] >= pol["falhas_api_pausa"]:
        avisar(f"API falhou {c['falhas_api']} ciclos seguidos; sem entradas novas")
        return False
    inicio = c["valor_inicio_dia"].get(hoje())
    if inicio and valor <= inicio * (1 - pol["perda_dia_pct"]):
        if c.get("pausa_ate") != hoje():
            c["pausa_ate"] = hoje()
            c["estrategia"] = "C_observar"
            avisar(f"perda do dia atingida (US$ {inicio - valor:.2f}); sem entradas até amanhã")
        return False
    return c.get("pausa_ate") != hoje()


# ---------- mercado ----------

def taxa_por_cota(m, preco, pol):
    """fee = C × rate × (p(1−p))^exponent, por cota. Sem dado: pior taxa."""
    if m.get("feesEnabled") is False:
        return 0.0, "sem taxa"
    fs = m.get("feeSchedule") or {}
    rate = num(fs.get("rate"))
    exp = num(fs.get("exponent")) or 1
    if m.get("feesEnabled") is None or rate is None:
        rate, exp = pol["taxa_fallback"], 1
        return round(rate * (preco * (1 - preco)) ** exp, 5), "taxa ausente: pior caso"
    return round(rate * (preco * (1 - preco)) ** exp, 5), f"taxa {rate}"


def problemas_dado(m, pol):
    p = []
    bid, ask = num(m.get("bestBid")), num(m.get("bestAsk"))
    if bid is None or ask is None:
        p.append("sem bestBid/bestAsk")
    elif ask - bid > pol["spread_max"]:
        p.append(f"spread {ask - bid:.3f}")
    if not m.get("acceptingOrders") or not m.get("enableOrderBook"):
        p.append("não aceita ordens")
    if (num(m.get("liquidityNum")) or 0) < pol["liquidez_min_usd"]:
        p.append("liquidez baixa")
    if (num(m.get("volume24hr")) or 0) < pol["volume24h_min_usd"]:
        p.append("volume 24h baixo")
    fim = m.get("endDate")
    if not fim:
        p.append("sem data de fim")
    else:
        dias = (dt.datetime.fromisoformat(fim.replace("Z", "+00:00")) - agora()).total_seconds() / 86400
        if not pol["dias_resolucao_min"] <= dias <= pol["dias_resolucao_max"]:
            p.append(f"resolve em {dias:.1f} dias")
    if bid is not None and ask is not None:
        meio = (bid + ask) / 2
        if not pol["preco_min"] <= meio <= pol["preco_max"]:
            p.append(f"preço {meio:.3f} fora da faixa")
    return p


def buscar_mercados_abertos(volume_min, max_paginas=200):
    """Mercados abertos do maior para o menor volume 24 h, até cair abaixo
    do volume mínimo da política (há >100 mil abertos; quase todos parados)."""
    mercados, cursor = [], None
    for _ in range(max_paginas):
        params = {"closed": "false", "limit": 100, "order": "volume24hr", "ascending": "false"}
        if cursor:
            params["after_cursor"] = cursor
        d = http_json("/markets/keyset", params)
        pagina = d.get("markets", [])
        mercados += pagina
        cursor = d.get("next_cursor")
        if not cursor or not pagina or (num(pagina[-1].get("volume24hr")) or 0) < volume_min:
            break
    return mercados


def buscar_por_id(ids):
    out = {}
    ids = list(dict.fromkeys(str(i) for i in ids))
    for i in range(0, len(ids), 100):
        d = http_json("/markets/keyset", {"id": ids[i:i + 100], "closed": "any", "limit": 100})
        out.update({str(m["id"]): m for m in d.get("markets", [])})
    return out


# ---------- comandos ----------

def cmd_varrer(args):
    pol = carregar_politica()
    c = ler_carteira(pol)
    try:
        mercados = buscar_mercados_abertos(pol["volume24h_min_usd"])
        c["falhas_api"] = 0
    except Exception as e:  # noqa: BLE001 — qualquer falha de rede conta igual
        c["falhas_api"] += 1
        registrar("falha_api", erro=str(e), seguidas=c["falhas_api"])
        checar_gatilhos(pol, c, remoto=False)
        gravar_carteira(c)
        sys.exit(f"ERRO: API falhou ({e}); falhas seguidas: {c['falhas_api']}")

    validos, descartes = [], {}
    for m in mercados:
        prob = problemas_dado(m, pol)
        if prob:
            descartes[prob[0].split(" ")[0]] = descartes.get(prob[0].split(" ")[0], 0) + 1
            continue
        bid, ask = num(m["bestBid"]), num(m["bestAsk"])
        liq = num(m.get("liquidityNum")) or 1
        # Pré-filtro barato: movimento recente e giro alto chamam atenção.
        # Não é o sinal; o sinal é a probabilidade estimada depois.
        atencao = abs(num(m.get("oneDayPriceChange")) or 0) * 10 + min((num(m.get("volume24hr")) or 0) / liq, 2)
        taxa, _ = taxa_por_cota(m, ask, pol)
        ev = (m.get("events") or [{}])[0]
        validos.append({
            "market_id": str(m["id"]), "evento_id": str(ev.get("id", "")),
            "mercado": m.get("question"), "slug": m.get("slug"),
            "bestBid": bid, "bestAsk": ask, "taxa_cota_sim": taxa,
            "sem_taxa": taxa == 0, "liquidez": liq, "volume24h": num(m.get("volume24hr")),
            "variacao_1d": num(m.get("oneDayPriceChange")), "fim": m.get("endDate"),
            "descricao": (m.get("description") or "")[:600], "atencao": round(atencao, 3),
        })

    if c["estrategia"] == "B_sem_taxa":
        validos = [v for v in validos if v["sem_taxa"]]
    validos.sort(key=lambda v: v["atencao"], reverse=True)
    escolhidos = validos[:args.top]
    lido_em = agora().isoformat(timespec="seconds")
    os.makedirs(DADOS, exist_ok=True)
    with open(CANDIDATOS, "w", encoding="utf-8") as f:
        json.dump({"lido_em": lido_em, "estrategia": c["estrategia"], "candidatos": escolhidos},
                  f, ensure_ascii=False, indent=2)
    c["valor_inicio_dia"].setdefault(hoje(), round(valor_carteira(c), 4))
    gravar_carteira(c)
    registrar("varredura", lidos=len(mercados), validos=len(validos),
              candidatos=len(escolhidos), descartes=descartes)
    print(f"Varridos {len(mercados)} mercados abertos; {len(validos)} passaram no filtro de dados; "
          f"{len(escolhidos)} candidatos em dados/candidatos.json (estratégia {c['estrategia']}).")
    print("Descartes por motivo:", json.dumps(descartes, ensure_ascii=False))


def erro_atual(pol):
    """Erro de calibração medido (ECE) se houver previsões suficientes."""
    linhas = [r for r in ler_csv(PREVISOES) if r.get("resultado") in ("0", "1")]
    if len(linhas) < pol["previsoes_min_calibracao"]:
        return pol["erro_padrao"], f"padrão ({len(linhas)} resolvidas)"
    faixas = {}
    for r in linhas:
        p = float(r["probabilidade"])
        faixas.setdefault(min(int(p * 10), 9), []).append((p, int(r["resultado"])))
    ece = sum(abs(sum(p for p, _ in v) / len(v) - sum(y for _, y in v) / len(v)) * len(v)
              for v in faixas.values()) / len(linhas)
    return max(ece, pol["erro_minimo"]), f"medido ({len(linhas)} resolvidas)"


def brier_recente(n=20):
    linhas = [r for r in ler_csv(PREVISOES) if r.get("resultado") in ("0", "1")][-n:]
    if len(linhas) < n:
        return None
    return sum((float(r["probabilidade"]) - int(r["resultado"])) ** 2 for r in linhas) / len(linhas)


def ler_csv(caminho):
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def anexar_csv(caminho, colunas, linha):
    novo = not os.path.exists(caminho)
    with open(caminho, "a", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        if novo:
            w.writeheader()
        w.writerow(linha)


def avaliar(est, m, pol, c, tetos, erro, pode_operar):
    """Uma estimativa → uma linha de decisão. Pura: não mexe na carteira."""
    p_sim = float(est["p_sim"])
    bid, ask = num(m.get("bestBid")), num(m.get("bestAsk"))
    linha = {"market_id": str(m["id"]), "mercado": m.get("question"),
             "evento_id": str(((m.get("events") or [{}])[0]).get("id", "")),
             "p_agente": p_sim, "confianca": est.get("confianca", ""),
             "fontes": est.get("fontes", ""), "justificativa": est.get("justificativa", ""),
             "estrategia": c["estrategia"], "erro": round(erro, 4)}

    def fim(decisao, motivo, **extra):
        linha.update(extra, decisao=decisao, motivo=motivo)
        return linha

    prob = problemas_dado(m, pol)
    if prob:
        return fim("NAO_ENTRAR", "dado ruim: " + "; ".join(prob))
    if not est.get("fontes") or not est.get("justificativa"):
        return fim("NAO_ENTRAR", "estimativa sem fonte ou justificativa")

    # Comprar SIM paga o ask; comprar NÃO paga 1 − bid.
    if p_sim - ask >= 1 - p_sim - (1 - bid):
        lado, p, preco = "SIM", p_sim, ask
    else:
        lado, p, preco = "NAO", 1 - p_sim, round(1 - bid, 4)
    taxa, nota_taxa = taxa_por_cota(m, preco, pol)
    custo = preco + taxa
    bruta = p - preco
    liquida = bruta - taxa - erro
    p_aj = p - erro
    kelly = max(0.0, (p_aj - custo) / (1 - custo)) if custo < 1 else 0.0
    linha.update(lado=lado, preco=preco, taxa_cota=taxa, borda_bruta=round(bruta, 4),
                 borda_liquida=round(liquida, 4), kelly_cheio=round(kelly, 4))

    if est.get("confianca", "").lower() == "baixa":
        return fim("ESPERAR", "confiança baixa: espera e avisa")
    if bruta <= pol["borda_min"]:
        return fim("NAO_ENTRAR", f"folga {bruta * 100:.1f} pts ≤ {pol['borda_min'] * 100:.0f} pts")
    if liquida <= 0:
        return fim("NAO_ENTRAR", f"folga não paga taxa ({nota_taxa}) + erro ({erro * 100:.1f} pts)")
    if c["estrategia"] == "C_observar":
        return fim("NAO_ENTRAR", "estratégia C_observar: só registra previsão")
    if c["estrategia"] == "B_sem_taxa" and taxa > 0:
        return fim("NAO_ENTRAR", "estratégia B_sem_taxa: mercado com taxa")
    if not pode_operar:
        return fim("NAO_ENTRAR", "entradas bloqueadas (parada/pausa/sem verificação)")

    valor_cart = valor_carteira(c)
    fracao = min(kelly * pol["fracao_kelly"], tetos["teto_decisao_pct"])
    valor = min(fracao * valor_cart, tetos["teto_decisao_usd"])
    motivos = [f"meio Kelly {kelly * pol['fracao_kelly'] * 100:.1f}%"]
    no_evento = sum(x["custo"] for x in c["posicoes"] if x["evento_id"] == linha["evento_id"])
    valor = min(valor, max(0.0, tetos["teto_evento_pct"] * valor_cart - no_evento))
    dia = c["entradas_dia"].get(hoje(), 0.0)
    mes = c["entradas_mes"].get(hoje()[:7], 0.0)
    exposto = sum(x["custo"] for x in c["posicoes"])
    valor = min(valor, tetos["teto_dia_usd"] - dia, tetos["teto_mes_usd"] - mes,
                tetos["exposicao_max_pct"] * valor_cart - exposto, c["caixa"])
    cotas = int(valor / custo) if valor > 0 else 0
    valor = round(cotas * custo, 2)
    minimo = num(m.get("orderMinSize")) or 5
    linha.update(fracao_final=round(valor / valor_cart, 4) if valor_cart else 0,
                 valor_usd=valor, cotas=cotas)
    if cotas < minimo:
        return fim("NAO_ENTRAR", "; ".join(motivos + [f"tamanho {cotas} cotas < mínimo {minimo:g} após tetos"]))
    if valor >= pol["aprovacao_a_partir_usd"]:
        return fim("PRECISA_APROVACAO", f"valor US$ {valor:.2f} ≥ US$ {pol['aprovacao_a_partir_usd']:.2f}")
    return fim("ENTRAR_SIM", "; ".join(motivos + [f"folga líquida {liquida * 100:.1f} pts"]))


def cmd_decidir(args):
    pol = carregar_politica()
    c = ler_carteira(pol)
    if c["estrategia"] not in pol["estrategias_aprovadas"]:
        disparar_parada(c, f"estratégia {c['estrategia']} não aprovada")
    b = brier_recente()
    if b is not None and b > pol["brier_max"] and c["estrategia"] != "C_observar":
        c["estrategia"] = "C_observar"
        avisar(f"Brier das últimas 20 previsões = {b:.3f} > {pol['brier_max']}; troquei para C_observar")
    pode = checar_gatilhos(pol, c, remoto=not args.sem_remoto)
    tetos = tetos_do_dia(pol, c)
    erro, nota_erro = erro_atual(pol)

    ests = ler_csv(args.estimativas)
    if not ests:
        print("Nenhuma estimativa para decidir.")
        gravar_carteira(c)
        return
    try:
        mercados = buscar_por_id([e["market_id"] for e in ests])
        c["falhas_api"] = 0
    except Exception as e:  # noqa: BLE001
        c["falhas_api"] += 1
        gravar_carteira(c)
        sys.exit(f"ERRO: API falhou ao reler preços ({e})")

    contagem = {}
    for est in ests:
        m = mercados.get(str(est["market_id"]))
        if not m:
            avisar(f"mercado {est['market_id']} não encontrado; ignorado")
            continue
        linha = avaliar(est, m, pol, c, tetos, erro, pode)
        linha["data_utc"] = agora().isoformat(timespec="seconds")
        anexar_csv(DECISOES, COLUNAS_DECISOES, {k: linha.get(k, "") for k in COLUNAS_DECISOES})
        anexar_csv(PREVISOES, COLUNAS_PREVISOES, {
            "data_utc": linha["data_utc"], "market_id": linha["market_id"],
            "previsao": f"SIM em: {m.get('question')}", "probabilidade": est["p_sim"],
            "preco_mercado": round(((num(m.get('bestBid')) or 0) + (num(m.get('bestAsk')) or 0)) / 2, 4),
            "resultado": ""})
        contagem[linha["decisao"]] = contagem.get(linha["decisao"], 0) + 1
        if linha["decisao"] == "ENTRAR_SIM":
            custo = linha["valor_usd"]
            c["caixa"] = round(c["caixa"] - custo, 4)
            c["entradas_dia"][hoje()] = round(c["entradas_dia"].get(hoje(), 0) + custo, 4)
            c["entradas_mes"][hoje()[:7]] = round(c["entradas_mes"].get(hoje()[:7], 0) + custo, 4)
            tokens = lista_json(m.get("clobTokenIds"))
            c["posicoes"].append({
                "market_id": linha["market_id"], "evento_id": linha["evento_id"],
                "mercado": linha["mercado"], "lado": linha["lado"], "cotas": linha["cotas"],
                "preco": linha["preco"], "preco_atual": linha["preco"], "custo": custo,
                "token": tokens[0 if linha["lado"] == "SIM" else 1] if len(tokens) == 2 else "",
                "data_utc": linha["data_utc"]})
        elif linha["decisao"] in ("PRECISA_APROVACAO", "ESPERAR"):
            avisar(f"{linha['decisao']}: {linha['mercado']} — {linha['lado']} "
                   f"US$ {linha.get('valor_usd') or 0} — {linha['motivo']}")
        print(f"[{linha['decisao']}] {linha['mercado'][:70]} | {linha.get('lado', '')} "
              f"| {linha['motivo']}")
    gravar_carteira(c)
    registrar("decisoes", contagem=contagem, erro=erro, nota_erro=nota_erro, estrategia=c["estrategia"])
    print(f"Resumo: {contagem} | erro usado {erro * 100:.1f} pts ({nota_erro})")


def cmd_liquidar(args):
    pol = carregar_politica()
    c = ler_carteira(pol)
    abertas = [r for r in ler_csv(PREVISOES) if r.get("resultado") == ""]
    ids = [p["market_id"] for p in c["posicoes"]] + [r["market_id"] for r in abertas]
    if not ids:
        print("Nada a liquidar.")
    else:
        mercados = buscar_por_id(ids)
        restantes = []
        for pos in c["posicoes"]:
            m = mercados.get(pos["market_id"])
            if not m:
                restantes.append(pos)
                continue
            precos = [num(x) for x in lista_json(m.get("outcomePrices"))]
            if m.get("closed") and precos in ([1.0, 0.0], [0.0, 1.0]):
                ganhou = (precos[0] == 1.0) == (pos["lado"] == "SIM")
                pago = pos["cotas"] * (1.0 if ganhou else 0.0)
                c["caixa"] = round(c["caixa"] + pago, 4)
                registrar("liquidacao", market_id=pos["market_id"], lado=pos["lado"],
                          custo=pos["custo"], pago=pago)
                continue
            bid = num(m.get("bestBid"))
            ask = num(m.get("bestAsk"))
            if bid is not None and ask is not None:
                # Avalia pelo que daria para vender agora.
                pos["preco_atual"] = bid if pos["lado"] == "SIM" else round(1 - ask, 4)
            restantes.append(pos)
        c["posicoes"] = restantes
        todas = ler_csv(PREVISOES)
        fechadas = 0
        for r in todas:
            m = mercados.get(r["market_id"])
            if r.get("resultado") == "" and m and m.get("closed"):
                precos = [num(x) for x in lista_json(m.get("outcomePrices"))]
                if precos in ([1.0, 0.0], [0.0, 1.0]):
                    r["resultado"] = "1" if precos[0] == 1.0 else "0"
                    fechadas += 1
        if fechadas:
            with open(PREVISOES, "w", encoding="utf-8", newline="") as f:
                w = csv.DictWriter(f, fieldnames=COLUNAS_PREVISOES)
                w.writeheader()
                w.writerows(todas)
        print(f"{fechadas} previsões resolvidas; {len(c['posicoes'])} posições abertas.")
    valor = valor_carteira(c)
    inicio = c["valor_inicio_dia"].setdefault(hoje(), round(valor, 4))
    c["resultado_dia"][hoje()] = round(valor - inicio, 4)
    gravar_carteira(c)
    print(f"Valor a mercado: US$ {valor:.2f} (dia: {valor - inicio:+.2f})")


def cmd_estado(args):
    pol = carregar_politica()
    c = ler_carteira(pol)
    pode = checar_gatilhos(pol, c, remoto=not args.sem_remoto)
    gravar_carteira(c)
    valor = valor_carteira(c)
    exposto = sum(p["custo"] for p in c["posicoes"])
    print(f"Modo: {pol['modo']} | estratégia: {c['estrategia']} | pode operar: {pode}")
    print(f"Valor: US$ {valor:.2f} (início US$ {c['saldo_inicial']:.2f}) | caixa US$ {c['caixa']:.2f} "
          f"| exposto US$ {exposto:.2f} em {len(c['posicoes'])} posições")
    print(f"Entradas hoje: US$ {c['entradas_dia'].get(hoje(), 0):.2f} / {tetos_do_dia(pol, c)['teto_dia_usd']:.2f}"
          f" | mês: US$ {c['entradas_mes'].get(hoje()[:7], 0):.2f} / {pol['teto_mes_usd']:.2f}")
    if c.get("parada"):
        print(f"PARADA desde {c['parada']['data_utc']}: {c['parada']['motivo']}")


def cmd_parar(args):
    pol = carregar_politica()
    c = ler_carteira(pol)
    disparar_parada(c, args.motivo or "parada manual")
    gravar_carteira(c)


def cmd_retomar(args):
    # O .claude/settings.json obriga o dono a aprovar este comando.
    pol = carregar_politica()
    c = ler_carteira(pol)
    if not args.dono:
        sys.exit("Só o dono retoma: rode com --dono depois de revisar o motivo da parada.")
    if os.path.exists(PARAR_LOCAL):
        sys.exit("Remova o arquivo PARAR (local e no GitHub) antes de retomar.")
    registrar("retomada", parada=c.get("parada"))
    c.update(parada=None, pausa_ate=None, falhas_api=0, retomado_em=hoje(), estrategia="A_valor")
    gravar_carteira(c)
    print("Retomado. Hoje todos os tetos valem pela metade.")


def cmd_teste_parada(args):
    """Prova que o botão funciona sem mexer na carteira real da simulação."""
    global MODO_TESTE
    pol = carregar_politica()
    c = json.loads(json.dumps(ler_carteira(pol)))
    c["parada"] = None
    falhas = []
    MODO_TESTE = True
    open(PARAR_LOCAL, "w").close()
    try:
        if checar_gatilhos(pol, c, remoto=False):
            falhas.append("arquivo PARAR não bloqueou")
    finally:
        os.remove(PARAR_LOCAL)
    c2 = json.loads(json.dumps(c))
    c2.update(parada=None, caixa=c2["saldo_inicial"] * (1 - pol["perda_total_pct"]) - 0.01, posicoes=[])
    if checar_gatilhos(pol, c2, remoto=False):
        falhas.append("perda total não bloqueou")
    c3 = json.loads(json.dumps(c))
    c3.update(parada=None, falhas_api=pol["falhas_api_parada"])
    if checar_gatilhos(pol, c3, remoto=False):
        falhas.append("API fora do ar não bloqueou")
    est = {"p_sim": "0.9", "confianca": "alta", "fontes": "teste", "justificativa": "teste"}
    m = {"id": "0", "question": "teste", "bestBid": 0.39, "bestAsk": 0.40, "acceptingOrders": True,
         "enableOrderBook": True, "liquidityNum": 1e6, "volume24hr": 1e5, "orderMinSize": 1,
         "endDate": (agora() + dt.timedelta(days=10)).isoformat(), "feesEnabled": False}
    c4 = carteira_nova(pol)
    d = avaliar(est, m, pol, c4, tetos_do_dia(pol, c4), pol["erro_padrao"], True)
    if d["valor_usd"] > pol["teto_decisao_usd"] or d["valor_usd"] > pol["teto_decisao_pct"] * 50 + 0.01:
        falhas.append(f"teto por decisão furado: US$ {d['valor_usd']}")
    resultado = "OK" if not falhas else "FALHOU: " + "; ".join(falhas)
    MODO_TESTE = False
    registrar("teste_parada", resultado=resultado)
    print(f"Teste do botão de parada: {resultado}")
    if args.remoto:
        r = parar_remoto(pol)
        print(f"Verificação do PARAR no GitHub: {'existe' if r else 'não existe' if r is False else 'falhou'}")
    sys.exit(0 if not falhas else 1)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("varrer")
    v.add_argument("--top", type=int, default=20)
    d = sub.add_parser("decidir")
    d.add_argument("--estimativas", default=os.path.join(DADOS, "estimativas.csv"))
    d.add_argument("--sem-remoto", action="store_true", help="não consulta o PARAR no GitHub")
    sub.add_parser("liquidar")
    e = sub.add_parser("estado")
    e.add_argument("--sem-remoto", action="store_true")
    p = sub.add_parser("parar")
    p.add_argument("--motivo")
    r = sub.add_parser("retomar")
    r.add_argument("--dono", action="store_true")
    t = sub.add_parser("teste-parada")
    t.add_argument("--remoto", action="store_true")
    args = ap.parse_args()
    {"varrer": cmd_varrer, "decidir": cmd_decidir, "liquidar": cmd_liquidar, "estado": cmd_estado,
     "parar": cmd_parar, "retomar": cmd_retomar, "teste-parada": cmd_teste_parada}[args.cmd](args)


if __name__ == "__main__":
    main()
