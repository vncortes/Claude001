#!/usr/bin/env python3
"""Gera os blocos "Parceiros recomendados" a partir de dominios.csv.

Uso:  python3 gerar.py
Edite dominios.csv (setor, subsetor, regiao, estado) e volte a correr.
"""
import csv
import hashlib
import html
import os
from collections import defaultdict

AQUI = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(AQUI, "saida")
MAX_PARCEIROS = 4

# Setores que fazem sentido recomendar a partir de cada setor.
COMPLEMENTARES = {
    "restauracao": ["alimentar", "turismo", "cultura"],
    "alimentar": ["restauracao", "turismo", "agro"],
    "turismo": ["restauracao", "alimentar", "auto", "desporto", "cultura"],
    "beleza": ["moda", "saude", "beleza", "flores"],
    "saude": ["beleza", "desporto", "alimentar"],
    "moda": ["beleza", "moda", "flores"],
    "flores": ["moda", "beleza", "turismo"],
    "casa": ["casa", "servicos", "agro"],
    "agro": ["alimentar", "casa"],
    "auto": ["auto", "turismo", "desporto"],
    "desporto": ["saude", "turismo"],
    "servicos": ["casa", "servicos"],
    "educacao": ["cultura", "educacao"],
    "cultura": ["educacao", "turismo", "restauracao"],
}

DESCRICOES = {
    "restaurante": "Restaurante", "cafe": "Café e brunch", "bar": "Bar",
    "pastelaria": "Pastelaria", "queijaria": "Queijaria", "garrafeira": "Garrafeira",
    "vinhos_gourmet": "Vinhos e produtos gourmet", "chocolataria": "Chocolates artesanais",
    "talho": "Talho", "padaria": "Padaria", "mercearia": "Mercearia",
    "supermercado": "Supermercado", "mel": "Mel e produtos apícolas",
    "produtos_regionais": "Produtos regionais", "frutas": "Fruta e legumes",
    "bebidas": "Bebidas tradicionais", "caseiro": "Comida caseira",
    "produtos_tropicais": "Produtos tropicais", "alojamento": "Alojamento",
    "atividades": "Experiências e atividades", "viagens": "Agência de viagens",
    "transfers": "Transfers", "transportes": "Transportes",
    "cabeleireiro": "Cabeleireiro", "barbearia": "Barbearia", "estetica": "Estética",
    "massagens": "Massagens", "cosmetica": "Cosmética",
    "cosmetica_natural": "Cosmética natural", "farmacia": "Farmácia", "otica": "Ótica",
    "nutricao": "Nutrição", "coaching": "Desenvolvimento pessoal",
    "terapias": "Terapias holísticas", "bem_estar": "Bem-estar", "roupa": "Moda",
    "acessorios": "Acessórios", "sapataria": "Sapataria", "ourivesaria": "Ourivesaria",
    "atelier": "Atelier de costura", "loja": "Loja", "florista": "Florista",
    "moveis": "Mobiliário", "jardim": "Jardim e exterior", "ferragens": "Ferragens",
    "climatizacao": "Climatização", "energia_solar": "Energia solar",
    "construcao": "Construção", "pedra": "Pedra natural", "metalurgia": "Metalurgia",
    "texteis": "Têxteis", "lenha": "Lenha", "agricultura": "Agricultura",
    "oficina": "Oficina auto", "bicicletas": "Bicicletas",
    "loja_desporto": "Artigos de desporto", "caca_pesca": "Caça e pesca",
    "embalagens": "Embalagens", "brindes": "Brindes personalizados",
    "papelaria": "Papelaria", "higiene_limpeza": "Higiene e limpeza",
    "imobiliaria": "Imobiliária", "infantil": "Espaço infantil",
    "explicacoes": "Centro de estudos", "material_didatico": "Material didático",
    "livraria": "Livraria", "artesanato": "Artesanato", "fotografia": "Fotografia",
    "musica": "Música",
}


def ler():
    with open(os.path.join(AQUI, "dominios.csv"), encoding="utf-8") as f:
        return list(csv.DictReader(f, delimiter=";"))


def desempate(a, b):
    return int(hashlib.md5(f"{a}>{b}".encode()).hexdigest()[:6], 16) / 0xFFFFFF


def pontuar(origem, alvo, entradas, ligacoes):
    so, sa = origem["setor"], alvo["setor"]
    if sa not in COMPLEMENTARES.get(so, []):
        return None
    # Concorrentes diretos (mesmo subsetor) não se recomendam.
    if origem["subsetor"] and origem["subsetor"] == alvo["subsetor"]:
        return None
    pontos = 2.0 if so != sa else 1.0
    if origem["regiao"] and origem["regiao"] == alvo["regiao"]:
        pontos += 3
    elif origem["regiao"] and alvo["regiao"]:
        pontos -= 3  # regiões diferentes e conhecidas
    # Evita trocas A<->B e espalha os links por todos os sites.
    if origem["dominio"] in ligacoes[alvo["dominio"]]:
        pontos -= 2.5
    pontos -= 0.4 * entradas[alvo["dominio"]]
    return pontos + desempate(origem["dominio"], alvo["dominio"])


def descricao(s):
    texto = DESCRICOES.get(s["subsetor"], s["setor"].capitalize())
    return f"{texto} em {s['regiao']}" if s["regiao"] else texto


def bloco_html(parceiros):
    itens = "\n".join(
        f'    <li><a href="https://www.{p["dominio"]}">{html.escape(p["nome"])}</a>'
        f" — {html.escape(descricao(p))}. <!-- personalize esta frase --></li>"
        for p in parceiros
    )
    return (
        '<section class="parceiros">\n'
        "  <h2>Parceiros recomendados</h2>\n"
        "  <ul>\n" + itens + "\n  </ul>\n</section>\n"
    )


def main():
    linhas = ler()
    ativos = [l for l in linhas if l["estado"] == "incluir"]
    entradas = defaultdict(int)
    ligacoes = defaultdict(set)
    resultado = {}

    # Ordem estável mas misturada, para não favorecer os primeiros da lista.
    for origem in sorted(ativos, key=lambda l: desempate("ordem", l["dominio"])):
        candidatos = []
        for alvo in ativos:
            if alvo is origem:
                continue
            p = pontuar(origem, alvo, entradas, ligacoes)
            if p is not None:
                candidatos.append((p, alvo))
        candidatos.sort(key=lambda c: -c[0])
        escolhidos, setores = [], defaultdict(int)
        for _, alvo in candidatos:
            if setores[alvo["subsetor"]] >= 1:  # variedade: 1 por subsetor
                continue
            escolhidos.append(alvo)
            setores[alvo["subsetor"]] += 1
            if len(escolhidos) == MAX_PARCEIROS:
                break
        for alvo in escolhidos:
            entradas[alvo["dominio"]] += 1
            ligacoes[origem["dominio"]].add(alvo["dominio"])
        resultado[origem["dominio"]] = escolhidos

    pasta = os.path.join(SAIDA, "parceiros")
    os.makedirs(pasta, exist_ok=True)
    for f in os.listdir(pasta):
        os.remove(os.path.join(pasta, f))
    for dom, parceiros in resultado.items():
        if parceiros:
            with open(os.path.join(pasta, f"{dom}.html"), "w", encoding="utf-8") as f:
                f.write(bloco_html(parceiros))

    with open(os.path.join(SAIDA, "mapa-de-links.csv"), "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, delimiter=";")
        w.writerow(["site", "setor", "links_saida", "links_entrada", "parceiros"])
        for l in ativos:
            d = l["dominio"]
            w.writerow([d, l["setor"], len(resultado[d]), entradas[d],
                        ", ".join(p["dominio"] for p in resultado[d])])

    with open(os.path.join(SAIDA, "redirecionamentos.txt"), "w", encoding="utf-8") as f:
        f.write("# Domínios duplicados: redirecionamento 301 para o principal.\n"
                "# hPanel > Domínios > Redirecionar, ou no .htaccess do domínio duplicado:\n\n")
        for l in linhas:
            if l["estado"] == "redirecionar":
                f.write(f"## {l['dominio']}  ->  {l['principal']}\n"
                        "RewriteEngine On\n"
                        f"RewriteRule ^(.*)$ https://www.{l['principal']}/$1 [R=301,L]\n\n")
        f.write("# Subdomínios de loja: não entram na rede; ligar a partir do menu do site principal.\n")
        for l in linhas:
            if l["estado"] == "subdominio":
                f.write(f"#   {l['dominio']}  (principal: {l['principal']})\n")

    with open(os.path.join(SAIDA, "por-rever.txt"), "w", encoding="utf-8") as f:
        f.write("# Preencha setor/subsetor/regiao em dominios.csv, mude estado para 'incluir' e corra gerar.py\n\n")
        for l in linhas:
            if l["estado"] == "rever":
                f.write(f"{l['dominio']}\n")

    sem = [d for d, p in resultado.items() if not p]
    print(f"{len(ativos)} sites na rede, {sum(len(p) for p in resultado.values())} links gerados.")
    print(f"Sem parceiros: {len(sem)} {sem}")
    print(f"Por rever: {sum(1 for l in linhas if l['estado'] == 'rever')}")


if __name__ == "__main__":
    main()
