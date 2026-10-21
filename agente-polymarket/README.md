# Agente Polymarket (simulação)

Agente que varre os mercados da Polymarket a cada 10 minutos, estima
probabilidades, marca o que está com preço errado em mais de 8 pontos depois
de taxa e erro, dimensiona com meio Kelly e teto de 6 %, e registra cada
decisão. **Não envia ordens:** opera uma carteira simulada de US$ 50.

| Arquivo | Para quê |
|---|---|
| [`DESENHO.md`](DESENHO.md) | as 6 peças, objetivo corrigido, 3 buracos, o que nunca pode, parada total, botão de parada |
| [`politica-de-risco.md`](politica-de-risco.md) | todos os números; o agente não consegue editar |
| [`KELLY.md`](KELLY.md) | o critério de Kelly explicado com os números deste agente |
| `agente.py` | varrer, decidir, liquidar, estado, parar, retomar, teste-parada |
| `calibracao.py` | faixas de probabilidade, Brier, viés otimista/pessimista |
| `auditoria.py` | auditor das últimas 24 h, em até 10 linhas, com ALERTA |
| `dados/decisoes.csv` | cada decisão, com valor, motivo, fonte e justificativa |
| `dados/previsoes.csv` | cada probabilidade dada; o resultado é preenchido quando resolve |
| `dados/carteira.json` | carteira simulada (caixa, posições, tetos usados) |
| `dados/log.jsonl` | log de tudo, inclusive avisos e paradas |

## Um ciclo

```bash
python3 -I agente-polymarket/agente.py liquidar         # marca a mercado, fecha resolvidas
python3 -I agente-polymarket/agente.py varrer --top 20   # ~3.000 mercados → 20 candidatos
# o agente (Claude) pesquisa cada candidato e escreve dados/estimativas.csv:
#   market_id,p_sim,confianca,fontes,justificativa
python3 -I agente-polymarket/agente.py decidir           # critério, taxa, erro, Kelly, tetos
python3 -I agente-polymarket/agente.py estado
```

## Prompt do /loop

```
/loop 10m Ciclo do agente Polymarket (SIMULAÇÃO, nunca envie ordem real).
1) python3 -I agente-polymarket/agente.py liquidar
2) python3 -I agente-polymarket/agente.py varrer --top 20
3) Para cada candidato de agente-polymarket/dados/candidatos.json que ainda não tem previsão nas últimas 6 h em dados/previsoes.csv, pesquise notícias atuais e estime a probabilidade de SIM. Escreva dados/estimativas.csv (market_id,p_sim,confianca,fontes,justificativa). Use confiança "baixa" quando as fontes forem fracas ou se contradisserem. Não ajuste p para passar no critério.
4) python3 -I agente-polymarket/agente.py decidir
5) Para cada linha "AVISAR:" da saída, mande uma notificação ao dono.
6) Commit de agente-polymarket/dados e push para o branch.
Se aparecer PARADA, ou se qualquer regra de politica-de-risco.md parecer violada, pare o loop e me avise. Não edite politica-de-risco.md e não rode "retomar".
```

Tarefas agendadas sugeridas (`/schedule`):
- **Diária:** `python3 -I agente-polymarket/auditoria.py` e
  `python3 -I agente-polymarket/calibracao.py`; avisar se começar com ALERTA.
- **Mensal:** `python3 -I agente-polymarket/agente.py teste-parada --remoto`.

## O que falta para dinheiro real (só com aprovação do dono)

1. Confirmar que operar na Polymarket é permitido no seu país (ela bloqueia
   vários).
2. Pelo menos 30 previsões resolvidas, com Brier abaixo de 0,25 e melhor que o
   chute fixo (`calibracao.py`).
3. Deposit Wallet com exatamente US$ 50 e Session Key só de CLOB, guardada
   como segredo do ambiente, nunca no chat nem no repositório.
4. Código de envio de ordem, revisado, e `"modo"` mudado na política pelo dono.

O sentimento no X precisa de uma chave da API do X e de `api.x.com` liberado
na rede. Até lá, as estimativas usam só notícias.
