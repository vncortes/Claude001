# Política de risco do agente Polymarket

> **Este arquivo está fora do alcance de edição do agente.** O
> `.claude/settings.json` do repositório nega `Edit`/`Write` neste caminho, e o
> `agente.py` recusa rodar se ele tiver alterações não commitadas. Só o dono
> muda este arquivo, pelo GitHub, e toda mudança fica no histórico do git
> (o auditor mostra qualquer commit nele nas últimas 24 h).
>
> O teto que **ninguém dentro do contêiner consegue mudar** é o saldo da
> carteira: o agente só pode gastar o que está depositado (US$ 50), e uma
> Session Key da Polymarket não consegue sacar. Os números abaixo são o
> segundo cinto de segurança.

Moeda: dólar (USDC/pUSD). Orçamento inicial: **US$ 50,00**. Dia = dia UTC.
Modo atual: **SIMULAÇÃO** — nenhuma ordem real é enviada.

## 1. Teto por decisão

- **6 % do saldo atual** (valor a mercado), calculado depois do meio Kelly.
- **E nunca mais que US$ 5,00** por decisão, mesmo que 6 % dê mais.
- Com US$ 50: 6 % = **US$ 3,00**.
- Teto por **evento** (somando todas as posições ligadas ao mesmo evento):
  **10 % do saldo** (US$ 5,00 com US$ 50). Isso impede dividir uma aposta
  grande em várias pequenas.

## 2. Teto por dia e do mês

- **Por dia:** no máximo **US$ 10,00** (20 % do orçamento inicial) em
  entradas novas.
- **Do mês:** no máximo **US$ 100,00** (2× o orçamento inicial) em entradas
  novas somadas no mês.
- **Exposição aberta total:** no máximo **50 % do saldo** em posições
  abertas ao mesmo tempo; o resto fica em caixa.
- No **primeiro dia depois de uma retomada**, todos os tetos acima valem
  **pela metade**.

## 3. Perda máxima

Toda perda é medida **a valor de mercado** (cada posição avaliada pelo preço
de venda imediato, o `bestBid`), e não só pelo que já foi realizado.

- **Perda no dia ≥ 5 %** do valor do início do dia (US$ 2,50 com US$ 50):
  sem entradas novas até o dia seguinte. Avisa.
- **Perda total ≥ 20 %** do orçamento inicial (valor da carteira ≤
  **US$ 40,00**): **parada total**.
- **3 dias seguidos abaixo da meta** (dia com resultado a mercado negativo):
  **parada total**, mesmo que ainda haja dinheiro.

## 4. Quando ele precisa da minha aprovação

- Qualquer decisão de **US$ 4,00 ou mais**.
- Estratégia que não está na lista de estratégias aprovadas.
- Qualquer mudança nesta política, nos tetos ou na lista de categorias.
- Passar de simulação para dinheiro real.
- Voltar de uma parada total.

## 5. Dado ruim ou faltando

Conta como dado ruim:

- mercado sem `bestBid` ou `bestAsk`, ou com `acceptingOrders` falso;
- spread maior que **4 pontos** (0,04);
- liquidez abaixo de **US$ 5.000** ou volume 24 h abaixo de **US$ 1.000**;
- preço fora da faixa **0,05 a 0,95**;
- mercado que resolve em menos de **1 dia** ou em mais de **60 dias**;
- dado com mais de **15 minutos** entre a leitura e a decisão;
- taxa do mercado ausente: assume a **pior taxa da tabela (0,07)**, nunca zero;
- estimativa do agente sem fonte ou sem justificativa.

O que ele faz: **não entra** naquele mercado e registra o motivo. Se a API
falhar **2 ciclos seguidos**, pausa entradas e avisa. Se falhar **6 ciclos
seguidos** (1 hora), parada total.

Quando **não tem certeza** (confiança "baixa", fontes que se contradizem, ou
regra ambígua): **espera e me avisa**. Nunca decide no escuro.

## 6. Quem é avisado e por onde

| Situação | Quem | Canal |
|---|---|---|
| Decisão normal registrada | ninguém na hora | `decisoes.csv` + commit no branch |
| Precisa de aprovação | dono | notificação no celular (app Claude) + mensagem na sessão |
| Incerteza / "esperar" | dono | mensagem na sessão |
| Perda do dia atingida | dono | notificação no celular |
| Parada total | dono | notificação no celular + mensagem na sessão + linha `PARADA` no log |
| API fora do ar 2 ciclos | dono | mensagem na sessão |

## Critério de entrada

- Diferença entre a probabilidade do agente e o preço de compra: **mais de
  8 pontos**.
- E essa folga tem de pagar a **taxa** e o **erro** do agente:
  `p − preço − taxa_por_cota − erro > 0`.
- `erro` = **5 pontos** até haver **30 previsões resolvidas**; depois, o
  erro medido de calibração (nunca menos que 2 pontos).
- Tamanho: **meio Kelly**, calculado com a probabilidade já descontada do
  erro e com o preço já somado da taxa; depois os tetos acima.

## Estratégias aprovadas

| Nome | O que faz | Quando ele pode trocar para ela sozinho |
|---|---|---|
| `A_valor` | estimativa própria vs preço, em qualquer categoria | estratégia padrão |
| `B_sem_taxa` | igual à A, mas só mercados com taxa zero (geopolítica) | se a taxa média dos sinais da semana comer mais da metade da folga |
| `C_observar` | não entra; só registra previsões para calibrar | obrigatória se o Brier das últimas 20 previsões resolvidas passar de 0,25, ou depois de perda do dia |

Qualquer outra estratégia, ou voltar de `C_observar` para `A`/`B`, precisa
de aprovação.

## Limites que o código lê

O `agente.py` lê exatamente este bloco. Se ele não existir ou estiver
inválido, o agente não roda.

```json
{
  "modo": "simulacao",
  "saldo_inicial_usd": 50.0,
  "teto_decisao_pct": 0.06,
  "teto_decisao_usd": 5.0,
  "teto_evento_pct": 0.10,
  "teto_dia_usd": 10.0,
  "teto_mes_usd": 100.0,
  "exposicao_max_pct": 0.50,
  "aprovacao_a_partir_usd": 4.0,
  "perda_dia_pct": 0.05,
  "perda_total_pct": 0.20,
  "dias_abaixo_meta_parada": 3,
  "borda_min": 0.08,
  "erro_padrao": 0.05,
  "erro_minimo": 0.02,
  "previsoes_min_calibracao": 30,
  "fracao_kelly": 0.5,
  "preco_min": 0.05,
  "preco_max": 0.95,
  "spread_max": 0.04,
  "liquidez_min_usd": 5000,
  "volume24h_min_usd": 1000,
  "dias_resolucao_min": 1,
  "dias_resolucao_max": 60,
  "dado_velho_min": 15,
  "taxa_fallback": 0.07,
  "falhas_api_pausa": 2,
  "falhas_api_parada": 6,
  "brier_max": 0.25,
  "estrategias_aprovadas": ["A_valor", "B_sem_taxa", "C_observar"],
  "branch_parada": "claude/inspiring-feynman-6plttn"
}
```
