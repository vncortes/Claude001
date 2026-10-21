# Rede de parceiros entre sites

Este kit substitui o diretório de ~220 links por blocos de **3 a 4 parceiros relevantes por site**.
Os blocos são escolhidos por setor complementar e região, sem ligar concorrentes diretos e evitando trocas A↔B.

## Ficheiros

| Ficheiro | Para quê |
|---|---|
| `dominios.csv` | Folha mestre (abre no Excel, separador `;`). **Corrija aqui** setor, subsetor, região e estado. |
| `gerar.py` | Gera tudo a partir da folha: `python3 gerar.py` |
| `saida/parceiros/<dominio>.html` | Bloco HTML a colar em cada site |
| `saida/mapa-de-links.csv` | Quem liga a quem, com contagem de links de entrada e saída |
| `saida/redirecionamentos.txt` | Domínios duplicados que devem fazer 301 |
| `saida/por-rever.txt` | Domínios cujo setor não consegui identificar pelo nome |
| `schema-localbusiness.html` | Modelo de dados estruturados para o `<head>` de cada site |

## Estados na coluna `estado`

- `incluir`: entra na rede.
- `rever`: setor desconhecido; fica de fora até ser classificado.
- `excluir`: plataformas, notícias, finanças, funerárias e a holding. Ficam fora da lista automática.
- `redirecionar`: duplicado; faz 301 para o domínio da coluna `principal`.
- `subdominio`: loja.*; liga-se pelo menu do site principal, não pela rede.

## Passo a passo

1. **Rever a folha.** Abra `dominios.csv` e:
   - classifique os domínios de `saida/por-rever.txt`;
   - confirme as linhas com `confianca = baixa`;
   - **preencha a coluna `regiao`** (ex.: `Beira Interior`, `Alentejo`, `Lisboa`, `Porto`, `Açores`). É o que mais melhora os resultados, porque parceiros da mesma zona são os mais naturais.
2. **Gerar:** `python3 gerar.py`.
3. **Redirecionamentos.** Para cada linha de `saida/redirecionamentos.txt`: hPanel → **Domínios** → **Redirecionar** → 301 para o principal.
4. **Personalizar.** Em cada bloco de `saida/parceiros/`, troque a frase genérica por uma frase real, por exemplo "Onde compramos o queijo que servimos às sextas". Blocos iguais em todos os sites são um padrão que o Google deteta.
5. **Publicar no Hostinger.**
   - *HTML estático:* hPanel → **Websites** → **Gerir** → **Gestor de Ficheiros** → `public_html`. Cole o bloco no fim da página "Sobre" ou numa página `parceiros.html` ligada a partir do rodapé.
   - *WordPress:* edite a página "Sobre" ou crie a página "Parceiros" → bloco **HTML personalizado** → cole o bloco.
   - *Hostinger Website Builder:* adicione um elemento **Incorporar código** ou escreva os links num bloco de texto.
   - Não use `noindex` nem `target="_blank"` com `noreferrer` nestes links.
6. **Publicar aos poucos.** Faça 10 a 20 sites por semana em vez de todos no mesmo dia.
7. **Schema.** Cole `schema-localbusiness.html` no `<head>` de cada site, com os dados reais, e valide no Rich Results Test.
8. **Search Console.** Verifique cada domínio (registo TXT no DNS do hPanel), envie o `sitemap.xml` e acompanhe a evolução em **Desempenho**.
9. **Retirar o diretório antigo** com os 185 links, se já estiver publicado.

## Fora da rede, mas com valor

- `notimparcial.com` e `truquesedicas.eu`: escreva artigos reais (ex.: "5 queijarias da Beira a visitar") com 1 a 2 links contextuais. Valem mais do que qualquer lista.
- `comercio-digital-alentejo.pt` e `catalogodigitalprr.eu`: se forem diretórios com fichas completas (morada, horário, fotos, descrição), uma ficha por negócio é legítima.
- `cortesholding.com`: crédito no rodapé de cada site, "Site desenvolvido por Cortes Holding", com `rel="nofollow"`.
