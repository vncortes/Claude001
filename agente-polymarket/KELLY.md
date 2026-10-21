# Critério de Kelly em português simples

Para entender como o agente decide **quanto** pôr em cada oportunidade.

## 1. A fórmula, com as letras deste agente

Num mercado da Polymarket, uma cota custa `c` e paga US$ 1 se acontecer.

```
f = (p − c) / (1 − c)
```

- **p**: a probabilidade que o agente acha que o evento tem (ex.: 0,48).
- **c**: o preço da cota, que é a probabilidade que o mercado está pagando
  (ex.: 0,40).
- **f**: a fração do saldo que maximiza o crescimento composto, *se* `p`
  estiver certo.
- **p − c**: a vantagem. **1 − c**: quanto se ganha por dólar arriscado.

O agente usa uma versão mais dura: soma a taxa ao preço e tira o próprio erro
da probabilidade:

```
custo = c + taxa_por_cota        taxa_por_cota = rate × c × (1 − c)
f = (p − erro − custo) / (1 − custo)
```

## 2. Quanto ele põe, com p = 0,48 e c = 0,40 e saldo de US$ 50

| Caso | Taxa/cota | Kelly cheio | Meio Kelly | Depois do teto 6 % | Em dólares |
|---|---|---|---|---|---|
| Sem taxa, sem erro (a sua conta) | 0 | 13,3 % | 6,7 % | **6,0 %** | US$ 3,00 |
| Cripto (rate 0,07), sem erro | 0,0168 | 10,8 % | 5,4 % | 5,4 % | US$ 2,71 |
| Cripto + erro de 5 pontos | 0,0168 | 2,3 % | 1,1 % | 1,1 % | US$ 0,57 |
| Geopolítica (sem taxa) + erro de 5 pontos | 0 | 5,0 % | 2,5 % | 2,5 % | US$ 1,25 |

A taxa de cripto a 0,40 é `0,07 × 0,40 × 0,60 = 0,0168` por cota, ou seja,
US$ 1,68 em 100 cotas. Bate com a tabela da Polymarket.

A folga de 8 pontos parece grande, mas, depois de taxa e erro, o tamanho cai
para perto de 1 % do saldo. Com US$ 50, isso dá **menos que a ordem mínima
de 5 cotas**. Na prática, com esse saldo o agente só entra quando a folga é
bem maior que 8 pontos, ou em mercado sem taxa.

## 3. E se a estimativa estiver otimista?

Comprando a 0,40 em cripto (custo efetivo de 0,4168), o lucro esperado por
dólar posto é:

| Probabilidade real | Lucro esperado por US$ 1 |
|---|---|
| 0,48 (o agente acertou) | +15,2 centavos |
| 0,44 (otimista em 4 pontos) | +5,6 centavos |
| 0,40 (otimista em 8 pontos: não havia folga) | **−4,0 centavos** (perde a taxa) |
| 0,36 (otimista em 12 pontos) | **−13,6 centavos** |

Pior que o lucro menor é o tamanho. Se a verdade é 0,44, o Kelly certo seria
4 %, e o Kelly calculado com 0,48 manda pôr 10,8 %: **2,7 vezes demais**.
Apostar mais que o dobro do Kelly certo faz o saldo **encolher no longo
prazo mesmo com vantagem positiva**. É por isso que o erro de calibração
medido entra na conta.

## 4. Por que, na prática, se usa fração de Kelly e teto fixo

- **Ninguém conhece o próprio `p` exato.** O Kelly cheio pressupõe que conhece.
  Errar para cima é muito mais caro que errar para baixo: meio Kelly perde
  pouco crescimento quando `p` está certo e evita a ruína quando está errado.
- **A oscilação do Kelly cheio é brutal:** é comum ver o saldo cair pela
  metade antes de crescer. Meio Kelly reduz muito essa oscilação.
- **Os eventos não são independentes:** várias posições ligadas à mesma
  eleição caem juntas. Daí o teto por evento.
- **O teto fixo (6 %, US$ 5) protege do erro de modelo,** quando o agente
  está errado sem saber. Nenhuma fórmula protege disso; só um limite que ela
  não pode mudar.
