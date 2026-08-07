import os

from dotenv import load_dotenv
from serpapi import GoogleSearch


load_dotenv()
SERPAPI_KEY = os.getenv("SERP_API_KEY") or os.getenv("SERPAPI_KEY")


class SerpApiErro(Exception):
    """Representa um erro de configuração ou consulta à SerpApi."""


def criar_parametros_base(origem, data_ida, data_volta=None):
    """Cria os parâmetros compartilhados pelas consultas de voo."""
    parametros = {
        "departure_id": origem,
        "outbound_date": data_ida.strftime("%Y-%m-%d"),
        "type": 1 if data_volta else 2,
        "travel_class": 1,
        "adults": 1,
        "currency": "BRL",
        "gl": "br",
        "hl": "pt",
        "no_cache": "true",
    }

    if data_volta:
        parametros["return_date"] = data_volta.strftime("%Y-%m-%d")
    return parametros


def executar_consulta(parametros):
    """Executa uma consulta e lança SerpApiErro quando ela falha."""
    if not SERPAPI_KEY:
        raise SerpApiErro("Chave da SerpApi não encontrada no arquivo .env.")

    parametros_completos = {**parametros, "api_key": SERPAPI_KEY}

    try:
        resultados = GoogleSearch(parametros_completos).get_dict()
    except Exception as erro:
        raise SerpApiErro(f"Não foi possível consultar a SerpApi: {erro}") from erro

    if resultados.get("error"):
        raise SerpApiErro(str(resultados["error"]))
    return resultados


def buscar_locais_api(termo):
    """Busca cidades e aeroportos para o campo de autocomplete."""
    termo = (termo or "").strip()
    if len(termo) < 3:
        return []

    resultados = executar_consulta({
        "engine": "google_flights_autocomplete",
        "q": termo,
        "hl": "pt",
        "gl": "br",
        "exclude_regions": "true",
    })

    sugestoes = resultados.get("suggestions", []) or []
    opcoes = []
    ids_adicionados = set()

    for local in sugestoes:
        if local.get("type") != "city":
            continue

        nome_local = local.get("name", termo)
        aeroportos = local.get("airports", []) or []
        codigos = [
            aeroporto.get("id")
            for aeroporto in aeroportos
            if aeroporto.get("id")
        ]
        todos_ids = ",".join(codigos) if codigos else local.get("id")

        if todos_ids and todos_ids not in ids_adicionados:
            opcoes.append((
                f"📍 {nome_local} - Todos os aeroportos",
                {"id": todos_ids, "nome": nome_local, "tipo": "cidade"},
            ))
            ids_adicionados.add(todos_ids)

        for aeroporto in aeroportos:
            codigo = aeroporto.get("id")
            if not codigo or codigo in ids_adicionados:
                continue

            cidade = aeroporto.get("city", "")
            nome = aeroporto.get("name", "")
            texto = f"✈️ {codigo} - {nome}"
            if cidade:
                texto += f" ({cidade})"

            opcoes.append((
                texto,
                {
                    "id": codigo,
                    "nome": f"{codigo} - {nome}",
                    "tipo": "aeroporto",
                },
            ))
            ids_adicionados.add(codigo)

    return opcoes[:12]