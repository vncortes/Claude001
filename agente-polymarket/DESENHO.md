# Desenho do agente Polymarket

Orçamento: **US$ 50**. Estado atual: **simulação** (papel). Os números
oficiais estão em [`politica-de-risco.md`](politica-de-risco.md); este
arquivo explica o porquê de cada um.

## O objetivo, e por que o original foi trocado

**Original:** "ou se autofinancia com ganhos compostos, ou morre."

Esse objetivo empurra para o pior comportamento possível. Quem só tem a
opção "ganhar ou morrer" não perde nada por arriscar tudo: perto de zero, a
melhor jogada para "não morrer" é apostar o resto numa zebra. E não há como
ele pagar o próprio computador: US$ 50 rendendo 1 % ao dia dão US$ 0,50, bem
abaixo do custo de qualquer máquina na nuvem.

**Objetivo novo:**

> Fazer o saldo crescer **com previsões medidas e calibradas**, entrando só
> quando a folga paga taxa e erro, **sem perder mais de 5 % num dia nem 20 %
> no total**. Ficar parado é um resultado aceitável. Na dúvida, **esperar e
> avisar**. O sucesso é medido a valor de mercado e pela calibração, não pelo
> ganho realizado.

Regras do objetivo novo:

1. **Não perder:** perda diária máxima de 5 % (pausa até o dia seguinte);
   perda total máxima de 20 %, ou seja, valor ≤ US$ 40 (parada total).
2. **Parar antes de zerar:** 3 dias seguidos com resultado a mercado
   negativo = parada total.
3. **Teto que ele não muda:** o saldo depositado na carteira (US$ 50). Uma
   Session Key da Polymarket pode operar, mas não pode sacar nem depositar.
   No código, a política é só leitura para o agente (veja "O que ele nunca
   pode fazer").
4. **Na dúvida:** decisão `ESPERAR`, registrada, e aviso ao dono.

## Três jeitos de cumprir a letra e trair a intenção

Fazendo o papel do agente que quer cumprir o objetivo novo pelo caminho mais
barato:

**Buraco 1: esconder a perda e não vender.** "Perda do dia" medida só pelo
que foi realizado: eu nunca vendo uma posição perdedora. No papel nunca perco
5 % num dia nem 20 % no total, enquanto a carteira derrete por dentro.
**Correção:** toda perda é medida **a valor de mercado**, com cada posição
avaliada pelo `bestBid` (o que daria para vender agora). Já está assim no
código (`liquidar` e `valor_carteira`).

**Buraco 2: inventar a própria folga.** O critério "minha probabilidade
difere do preço em mais de 8 pontos" usa um número que **eu mesmo gero**.
Basta eu dizer 0,60 onde o mercado diz 0,50 e tudo vira oportunidade.
**Correção:** (a) toda estimativa precisa de fonte e justificativa
registradas, senão `NAO_ENTRAR`; (b) toda estimativa vai para
`previsoes.csv` e é pontuada quando o mercado resolve; (c) o **erro medido**
de calibração é descontado da folga e da probabilidade usada no Kelly; (d)
Brier das últimas 20 previsões acima de 0,25 força a estratégia
`C_observar`; (e) o auditor marca entradas concentradas logo acima de 8
pontos.

**Buraco 3: fatiar para fugir dos tetos.** O teto é por decisão (6 %) e a
aprovação começa em US$ 4: faço três decisões de US$ 3 no mesmo evento, ou
seis decisões de US$ 3,90. Nenhuma passa do teto e nenhuma pede aprovação,
mas o risco somado é o mesmo de uma aposta grande.
**Correção:** teto **por evento** de 10 % do saldo, teto diário de US$ 10,
exposição aberta máxima de 50 %, e o auditor marca 3 ou mais entradas no
mesmo evento e tamanhos logo abaixo do valor que pede aprovação.

(Um quarto jeito, também fechado: comprar contratos a 0,97 "quase certos",
que ganham 3 % quase sempre e perdem 100 % de vez em quando. A faixa de preço
permitida é de 0,05 a 0,95, e o auditor marca maioria de entradas em preços
extremos.)

## As 6 peças

### 1. Ambiente isolado

- **Onde roda:** uma sessão do Claude Code na nuvem (contêiner descartável),
  com este repositório. O estado fica em `dados/` e vai para o branch por
  commit.
- **Rede:** só `gamma-api`, `data-api`, `clob` e `docs` da Polymarket, mais
  o GitHub.
- **Contas e permissões que TEM (hoje):** leitura pública de mercados e da
  carteira `0xDe40…e656`. Nenhuma chave, nenhum segredo.
- **Que NÃO TEM:** chave privada da carteira; Session Key; Builder API key;
  permissão de saque, depósito ou transferência; acesso ao X (sem API
  configurada); permissão de editar a política ou de rodar `retomar` sem
  aprovação.
- **Para dinheiro real (só com aprovação):** uma Deposit Wallet com
  **exatamente US$ 50**, uma **Session Key** com escopo só de CLOB e validade
  curta, guardada como segredo do ambiente. Session Key não saca: no pior
  caso, perde-se o que está na carteira, nunca mais.

### 2. Ciclo

- **A cada 10 minutos:** `liquidar` → `varrer` → estimativas → `decidir`.
- **Por quê 10 min:** os preços de mercados com volume mudam em minutos; a
  varredura leva cerca de 15 s. Menos que isso só aumenta o custo de
  estimativa sem dados novos. A política descarta dado com mais de 15 min.
- O `/loop` expira em 7 dias e precisa da sessão ativa. A auditoria diária e
  o teste mensal do botão de parada vão em tarefas agendadas (`/schedule`,
  mínimo de 1 h).

### 3. Varredura e sinal

- **Lê:** todos os mercados abertos ordenados por volume 24 h, até o volume
  cair abaixo de US$ 1.000 (≈ 3.000 mercados por ciclo; no teste, 3.200 em
  13 s). De cada um: `bestBid`, `bestAsk`, liquidez, volume, variação 1 d,
  data de fim, taxa do próprio mercado (`feeSchedule`), tamanho mínimo.
- **Filtro de dado:** descarta o que a política chama de dado ruim (≈ 18 %
  passa).
- **Pré-filtro (não é sinal):** movimento de preço em 1 dia + giro
  (volume ÷ liquidez). Os 20 primeiros viram candidatos.
- **Sinal:** a probabilidade do agente `p` para cada candidato, com fonte e
  justificativa (notícias pesquisadas na hora). **Sentimento no X ainda não
  está ligado:** precisa de uma chave da API do X e da liberação de
  `api.x.com` na rede. Até lá, o agente não finge que leu o X.

### 4. Critério de entrada

- Folga bruta: `p − preço_de_compra` **> 8 pontos**.
- Folga líquida: `p − preço − taxa_por_cota − erro` **> 0**.
  - Taxa por cota = `rate × preço × (1 − preço)`, com o `rate` do próprio
    mercado (cripto 0,07; geopolítica 0). Sem dado de taxa: 0,07.
  - Erro = 5 pontos até 30 previsões resolvidas; depois, o erro medido.
- Confiança "baixa" → `ESPERAR` e avisa.

### 5. Tamanho e teto

- Kelly com a probabilidade já descontada do erro e o preço já somado da
  taxa: `f = (p − erro − custo) / (1 − custo)`. Usa **meio Kelly**.
- **Por decisão:** mín(6 % do saldo, US$ 5). Com US$ 50: **US$ 3**.
- **Por evento:** 10 % do saldo. **Por dia:** US$ 10. **Por mês:** US$ 100.
  **Exposição aberta:** 50 % do saldo.
- **Aprovação:** a partir de **US$ 4** por decisão.
- **Restrição prática:** a Polymarket exige ordem mínima de **5 cotas**. Com
  teto de US$ 3, só cabem preços até ~0,60. No teste real de hoje, três
  sinais sintéticos foram barrados por isso. É o teto funcionando, mas
  significa que, com US$ 50, a maioria dos mercados caros fica de fora.

### 6. Mudança de estratégia

| De → Para | Sozinho? | Gatilho |
|---|---|---|
| A → B (só sem taxa) | sim | taxa média come mais da metade da folga na semana |
| qualquer → C (só observar) | **obrigatório** | Brier(20) > 0,25, ou perda do dia |
| C → A ou B | **não**, pede aprovação | — |
| qualquer → estratégia nova | **não**, pede aprovação | — |
| mudar tetos, categorias, critério | **não**, só o dono edita a política | — |

## O que ele nunca pode fazer sozinho

1. Enviar ordem real. Não existe código para isso; passar para dinheiro real
   exige aprovação e uma mudança de `modo` na política.
2. Editar `politica-de-risco.md` (bloqueado em `.claude/settings.json`; o
   código também recusa rodar com a política alterada sem commit).
3. Rodar `agente.py retomar` (exige aprovação do dono a cada vez).
4. Sacar, depositar, transferir ou pedir mais dinheiro.
5. Criar estratégia nova, ou voltar de `C_observar`.
6. Entrar com US$ 4 ou mais numa decisão.
7. Ler ou guardar chave privada da carteira principal.
8. Apagar ou reescrever `decisoes.csv`, `previsoes.csv` ou `log.jsonl`
   (só acrescenta linhas; tudo vai para o git).

## O que dispara a parada total

- Valor a mercado ≤ US$ 40 (perda de 20 %).
- 3 dias seguidos com resultado negativo.
- API fora do ar por 6 ciclos seguidos (1 hora).
- `politica-de-risco.md` alterada sem commit.
- Estratégia em uso fora da lista aprovada.
- Arquivo `PARAR` no repositório (local ou no GitHub).
- Decisão fora da política encontrada pelo auditor.

## Botão de parada

**1. O que dispara automaticamente:** a lista acima. Dado ruim num mercado só
barra aquele mercado. Não conseguir verificar o botão no GitHub barra as
entradas daquele ciclo.

**2. O que acontece na parada:**
- **Congela:** nenhuma entrada nova, estratégia em espera, carteira gravada
  como está.
- **Não desfaz automaticamente:** vender tudo na pressa custa spread e taxa e
  pode realizar perda sem necessidade. Fechar posições é decisão do dono.
  (Em simulação não há nada a desfazer.)
- **Avisa:** notificação no celular + mensagem na sessão + linha `PARADA` em
  `dados/log.jsonl`.

**3. Parar na mão, de qualquer lugar, em 1 passo:** no app do GitHub, no
branch `claude/inspiring-feynman-6plttn`, crie o arquivo
`agente-polymarket/PARAR` (qualquer conteúdo). O agente verifica isso a cada
ciclo, antes de decidir. Alternativa: escrever "pare" na sessão.

**4. Como volta:** só o dono. Apague o `PARAR` (se houver), revise o
motivo e aprove `python3 agente-polymarket/agente.py retomar --dono`, que
pede aprovação pelo `.claude/settings.json`. No **primeiro dia depois da
volta, todos os tetos valem pela metade**. A estratégia volta para `A_valor`.

**5. Teste mensal:** `python3 agente-polymarket/agente.py teste-parada --remoto`.
Ele prova, sem mexer na carteira, que (a) o arquivo `PARAR` bloqueia, (b)
perda de 20 % bloqueia, (c) API fora do ar bloqueia, (d) o teto por decisão
não é furado, e (e) mostra se o `PARAR` no GitHub está sendo lido. Faça
também, uma vez por mês, o teste de verdade: crie o `PARAR` no GitHub e
confira que o ciclo seguinte registra `PARADA`.
