from services.serpapi_service import criar_parametros_base, executar_consulta


def adicionar_preco_referencia(resultados, lista_precos):
    """Adiciona o menor preço indicado pela API, quando disponível."""
    preco = resultados.get("price_insights", {}).get("lowest_price")
    if preco is None:
        return

    try:
        lista_precos.append(float(preco))
    except (TypeError, ValueError):
        pass


def criar_dados_voo(
    origem,
    destino,
    preco,
    companhia,
    duracao=0,
    escalas=0,
    saida="",
    chegada="",
    data_voo=None,
    fonte=None,
    preco_referencia_google=None,
    quantidade_voos_analisados=0,
    menores_por_busca=None,
):
    """Cria a estrutura padronizada usada pelos resultados de voo."""
    dados = {
        "origem": origem,
        "destino": destino,
        "preco": preco,
        "companhia": companhia,
        "saida": saida,
        "chegada": chegada,
        "duracao": duracao,
        "escalas": escalas,
        "data_voo": data_voo,
        "preco_referencia_google": preco_referencia_google,
        "quantidade_voos_analisados": quantidade_voos_analisados,
        "menores_por_busca": menores_por_busca or [],
    }
    if fonte:
        dados["fonte"] = fonte
    return dados


def montar_dados_voo(voo, origem_query, destino_query):
    """Transforma o retorno detalhado da API no formato da aplicação."""
    trechos = voo.get("flights", [])
    if not trechos:
        return None

    partida = trechos[0].get("departure_airport", {})
    chegada = trechos[-1].get("arrival_airport", {})
    companhias = list(dict.fromkeys(
        trecho.get("airline")
        for trecho in trechos
        if trecho.get("airline")
    ))

    return criar_dados_voo(
        origem=partida.get("id", origem_query),
        destino=chegada.get("id", destino_query),
        preco=voo["_preco"],
        companhia=", ".join(companhias) or "N/A",
        saida=partida.get("time", ""),
        chegada=chegada.get("time", ""),
        duracao=voo.get("_duracao", 0),
        escalas=max(len(trechos) - 1, 0),
    )


def extrair_voos(resultados):
    """Reúne e normaliza os voos das categorias retornadas pela API."""
    voos = []
    for chave in ["best_flights", "other_flights", "top_flights"]:
        for voo in resultados.get(chave, []) or []:
            try:
                voo_copia = voo.copy()
                voo_copia["_preco"] = float(voo["price"])
                voo_copia["_duracao"] = int(voo.get("total_duration", 999999))
                voos.append(voo_copia)
            except (KeyError, TypeError, ValueError):
                continue
    return voos


def remover_voos_duplicados(voos):
    """Remove resultados repetidos vindos de categorias diferentes."""
    voos_unicos = []
    vistos = set()

    for voo in voos:
        trechos = voo.get("flights", [])
        if not trechos:
            continue

        partida = trechos[0].get("departure_airport", {})
        chegada = trechos[-1].get("arrival_airport", {})
        chave = (
            partida.get("id"),
            partida.get("time"),
            chegada.get("id"),
            chegada.get("time"),
            voo["_preco"],
        )

        if chave not in vistos:
            vistos.add(chave)
            voos_unicos.append(voo)

    return voos_unicos


def executar_busca_google_flights(origem, destino, data_ida, data_volta=None):
    """Executa uma busca de voos detalhados entre origem e destino."""
    parametros = criar_parametros_base(origem, data_ida, data_volta)
    parametros.update({
        "engine": "google_flights",
        "arrival_id": destino,
        "sort_by": 2,
        "show_hidden": "true",
        "deep_search": "true",
    })
    return executar_consulta(parametros)


def consultar_voo(origem_query, destino_query, data_ida, data_volta=None):
    """Obtém o voo mais barato e o mais rápido no Google Flights."""
    voos_validos = []
    menores_por_busca = []
    precos_ref_google = []

    resultado_geral = executar_busca_google_flights(
        origem_query, destino_query, data_ida, data_volta
    )
    voos_gerais = extrair_voos(resultado_geral)
    adicionar_preco_referencia(resultado_geral, precos_ref_google)
    voos_validos.extend(voos_gerais)

    if voos_gerais:
        menores_por_busca.append({
            "rota": f"{origem_query} → {destino_query}",
            "preco": min(voo["_preco"] for voo in voos_gerais),
        })

    origens = [codigo.strip() for codigo in origem_query.split(",") if codigo.strip()]
    destinos = [codigo.strip() for codigo in destino_query.split(",") if codigo.strip()]

    if len(origens) > 1 or len(destinos) > 1:
        for origem in origens:
            for destino in destinos:
                try:
                    resultado = executar_busca_google_flights(
                        origem, destino, data_ida, data_volta
                    )
                except Exception:
                    continue

                novos_voos = extrair_voos(resultado)
                adicionar_preco_referencia(resultado, precos_ref_google)

                if novos_voos:
                    voos_validos.extend(novos_voos)
                    menores_por_busca.append({
                        "rota": f"{origem} → {destino}",
                        "preco": min(voo["_preco"] for voo in novos_voos),
                    })

    voos_unicos = remover_voos_duplicados(voos_validos)
    if not voos_unicos:
        return None, None

    mais_barato = min(voos_unicos, key=lambda voo: voo["_preco"])
    mais_rapido = min(voos_unicos, key=lambda voo: voo["_duracao"])

    voo_barato = montar_dados_voo(mais_barato, origem_query, destino_query)
    voo_rapido = montar_dados_voo(mais_rapido, origem_query, destino_query)

    for voo in (voo_barato, voo_rapido):
        if voo:
            voo["data_voo"] = data_ida

    if voo_barato:
        voo_barato["quantidade_voos_analisados"] = len(voos_unicos)
        voo_barato["menores_por_busca"] = menores_por_busca
        voo_barato["preco_referencia_google"] = (
            min(precos_ref_google) if precos_ref_google else None
        )

    return voo_barato, voo_rapido


def consultar_promocao_google_flights(
    origem_query, destino_query, data_ida, data_volta=None
):
    """Busca ofertas no Google Flights Deals."""
    parametros = criar_parametros_base(origem_query, data_ida, data_volta)
    parametros["engine"] = "google_flights_deals"

    try:
        resultados = executar_consulta(parametros)
    except Exception:
        return None

    destinos_validos = {
        codigo.strip().upper()
        for codigo in str(destino_query).split(",")
        if codigo.strip()
    }
    candidatos = []

    for oferta in resultados.get("deals", []) or []:
        destino = str(oferta.get("arrival_airport_code", "")).upper()
        if destino not in destinos_validos:
            continue

        try:
            preco = float(oferta["price"])
            candidatos.append(criar_dados_voo(
                origem=oferta.get("departure_airport_code", origem_query),
                destino=destino,
                preco=preco,
                companhia=oferta.get("airline", "Google Flights"),
                duracao=oferta.get("flight_duration", 0),
                escalas=oferta.get("stops", 0),
                fonte="Google Flights Deals",
                preco_referencia_google=preco,
                data_voo=data_ida,
            ))
        except (KeyError, TypeError, ValueError):
            continue

    return min(candidatos, key=lambda voo: voo["preco"]) if candidatos else None


def consultar_google_travel_explore(
    origem_query, destino_query, data_ida, data_volta=None
):
    """Busca ofertas no Google Travel Explore."""
    parametros = criar_parametros_base(origem_query, data_ida, data_volta)
    parametros.update({
        "engine": "google_travel_explore",
        "arrival_id": destino_query,
    })

    try:
        resultados = executar_consulta(parametros)
    except Exception:
        return None

    voos = resultados.get("flights", []) or []
    candidatos = []

    for voo in voos:
        try:
            preco = float(voo["price"])
            partida = voo.get("departure_airport", {}) or {}
            chegada = voo.get("arrival_airport", {}) or {}
            candidatos.append(criar_dados_voo(
                origem=partida.get("id", origem_query),
                destino=chegada.get("id", destino_query),
                preco=preco,
                companhia=voo.get("airline", "Google Travel Explore"),
                duracao=voo.get("duration", 0),
                escalas=voo.get("number_of_stops", 0),
                fonte="Google Travel Explore",
                preco_referencia_google=preco,
                quantidade_voos_analisados=len(voos),
                menores_por_busca=[{
                    "rota": (
                        f"Google Travel Explore: "
                        f"{origem_query} → {destino_query}"
                    ),
                    "preco": preco,
                }],
                data_voo=data_ida,
            ))
        except (KeyError, TypeError, ValueError):
            continue

    return min(candidatos, key=lambda voo: voo["preco"]) if candidatos else None


def buscar_melhores_voos(origem, destino, data_ida, data_volta=None):
    """Consulta as fontes e retorna o voo mais barato e o mais rápido."""
    voo_barato, voo_rapido = consultar_voo(
        origem, destino, data_ida, data_volta
    )
    voo_promocional = consultar_promocao_google_flights(
        origem, destino, data_ida, data_volta
    )
    voo_explore = consultar_google_travel_explore(
        origem, destino, data_ida, data_volta
    )

    candidatos = [
        voo
        for voo in (voo_barato, voo_promocional, voo_explore)
        if voo is not None
    ]
    if candidatos:
        voo_barato = min(candidatos, key=lambda voo: voo["preco"])

    return voo_barato, voo_rapido