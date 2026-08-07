import os
from datetime import date, datetime
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from serpapi import GoogleSearch
from sqlalchemy import Column, DateTime, Float, Integer, String, create_engine, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from streamlit_searchbox import st_searchbox

# CONFIGURAÇÕES E BANCO DE DADOS
load_dotenv()
SERPAPI_KEY = os.getenv("SERP_API_KEY") or os.getenv("SERPAPI_KEY")
DATABASE_URL = "sqlite:///pousaaqui.db"

engine = create_engine(DATABASE_URL, echo=False)
Base = declarative_base()


class HistoricoPreco(Base):
    __tablename__ = "historico_precos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    origem = Column(String(10), nullable=False)
    destino = Column(String(10), nullable=False)
    preco = Column(Float, nullable=False)
    companhia = Column(String(100))

    # Dados da passagem monitorada
    duracao = Column(Integer, nullable=True)
    escalas = Column(Integer, nullable=True)
    data_voo = Column(DateTime, nullable=True)

    data_consulta = Column(DateTime, default=datetime.now)


Base.metadata.create_all(engine)

def atualizar_banco():
    """Adiciona novas colunas à tabela historico_precos caso não existam."""
    novas_colunas = {
        "duracao": "INTEGER",
        "escalas": "INTEGER",
        "data_voo": "DATETIME",
    }
    
    with engine.begin() as conexao:
        colunas_existentes = {col["name"] for col in inspect(conexao).get_columns("historico_precos")}
        
        for nome, tipo in novas_colunas.items():
            if nome not in colunas_existentes:
                conexao.execute(text(f"ALTER TABLE historico_precos ADD COLUMN {nome} {tipo}"))

atualizar_banco()
SessionLocal = sessionmaker(bind=engine)

# STREAMLIT CONFIG
st.set_page_config(page_title="PousaAqui - Painel de Monitoramento", page_icon="✈️", layout="wide")
st.title("✈️ PousaAqui - Painel de Monitoramento")
st.write("Digite o nome ou código de qualquer cidade ou aeroporto!")


# FUNÇÕES AUXILIARES
def formatar_duracao(minutos):
    try:
        minutos = int(minutos)
    except (TypeError, ValueError):
        return "N/A"
    horas, mins = divmod(minutos, 60)
    if horas and mins:
        return f"{horas}h {mins:02d}min"
    return f"{horas}h" if horas else f"{mins}min"


def formatar_preco(valor):
    """Formata valores monetários no padrão exibido pela aplicação."""
    if valor is None or pd.isna(valor):
        return "N/A"
    return f"R$ {float(valor):,.0f}".replace(",", ".")


def formatar_escalas(escalas):
    """Transforma a quantidade de escalas em um texto amigável."""
    if escalas is None or pd.isna(escalas):
        return "N/A"

    quantidade = int(escalas)
    if quantidade == 0:
        return "Sem escalas"
    if quantidade == 1:
        return "1 escala"
    return f"{quantidade} escalas"


def adicionar_preco_referencia(resultados, lista_precos):
    """Adiciona à lista o menor preço indicado pela API, quando disponível."""
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


def _params_base(origem, data_ida, data_volta=None):
    params = {
        "departure_id": origem,
        "outbound_date": data_ida.strftime("%Y-%m-%d"),
        "type": 1 if data_volta else 2,
        "travel_class": 1,
        "adults": 1,
        "currency": "BRL",
        "gl": "br",
        "hl": "pt",
        "no_cache": "true",
        "api_key": SERPAPI_KEY,
    }
    if data_volta:
        params["return_date"] = data_volta.strftime("%Y-%m-%d")
    return params


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_locais(termo):
    termo = (termo or "").strip()
    if len(termo) < 3 or not SERPAPI_KEY:
        return []

    params = {
        "engine": "google_flights_autocomplete",
        "q": termo,
        "hl": "pt",
        "gl": "br",
        "exclude_regions": "true",
        "api_key": SERPAPI_KEY,
    }

    try:
        resultados = GoogleSearch(params).get_dict()
        sugestoes = resultados.get("suggestions", []) or []
        opcoes, ids_adicionados = [], set()

        for local in sugestoes:
            if local.get("type") != "city":
                continue

            nome_local = local.get("name", termo)
            aeroportos = local.get("airports", []) or []
            codigos = [a.get("id") for a in aeroportos if a.get("id")]
            todos_ids = ",".join(codigos) if codigos else local.get("id")

            if todos_ids and todos_ids not in ids_adicionados:
                opcoes.append((f"📍 {nome_local} - Todos os aeroportos", {"id": todos_ids, "nome": nome_local, "tipo": "cidade"}))
                ids_adicionados.add(todos_ids)

            for a in aeroportos:
                codigo = a.get("id")
                if not codigo or codigo in ids_adicionados:
                    continue
                cidade = a.get("city", "")
                texto = f"✈️ {codigo} - {a.get('name', '')}" + (f" ({cidade})" if cidade else "")
                opcoes.append((texto, {"id": codigo, "nome": f"{codigo} - {a.get('name', '')}", "tipo": "aeroporto"}))
                ids_adicionados.add(codigo)

        return opcoes[:12]
    except Exception as erro:
        print(f"Erro no autocomplete: {erro}")
        return []


def montar_dados_voo(voo, origem_query, destino_query):
    trechos = voo.get("flights", [])
    if not trechos:
        return None

    partida = trechos[0].get("departure_airport", {})
    chegada = trechos[-1].get("arrival_airport", {})
    companhias = list(dict.fromkeys(t.get("airline") for t in trechos if t.get("airline")))

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


def consultar_voo(origem_query, destino_query, data_ida, data_volta=None):
    if not SERPAPI_KEY:
        st.error("❌ Chave da SerpApi não encontrada no arquivo .env.")
        return None, None

    def executar_busca(origem, destino):
        params = _params_base(origem, data_ida, data_volta)
        params.update({
            "engine": "google_flights",
            "arrival_id": destino,
            "sort_by": 2,
            "show_hidden": "true",
            "deep_search": "true",
        })
        return GoogleSearch(params).get_dict()

    def extrair_voos(resultados):
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

    try:
        voos_validos, menores_por_busca, precos_ref_google = [], [], []

        # 1. Busca Geral
        res_geral = executar_busca(origem_query, destino_query)
        if res_geral.get("error"):
            st.error(f"❌ Erro da SerpApi: {res_geral['error']}")
            return None, None

        voos_gerais = extrair_voos(res_geral)
        adicionar_preco_referencia(res_geral, precos_ref_google)

        voos_validos.extend(voos_gerais)
        if voos_gerais:
            menores_por_busca.append({"rota": f"{origem_query} → {destino_query}", "preco": min(v["_preco"] for v in voos_gerais)})

        # 2. Busca Individual por Aeroporto (caso haja combinações)
        origens = [c.strip() for c in origem_query.split(",") if c.strip()]
        destinos = [c.strip() for c in destino_query.split(",") if c.strip()]

        if len(origens) > 1 or len(destinos) > 1:
            for orig in origens:
                for dest in destinos:
                    res_ind = executar_busca(orig, dest)
                    if res_ind.get("error"):
                        continue

                    novos_voos = extrair_voos(res_ind)
                    adicionar_preco_referencia(res_ind, precos_ref_google)

                    if novos_voos:
                        voos_validos.extend(novos_voos)
                        menores_por_busca.append({"rota": f"{orig} → {dest}", "preco": min(v["_preco"] for v in novos_voos)})

        if not voos_validos:
            return None, None

        # Remover duplicados
        voos_unicos, vistos = [], set()
        for voo in voos_validos:
            trechos = voo.get("flights", [])
            if not trechos:
                continue
            p, u = trechos[0].get("departure_airport", {}), trechos[-1].get("arrival_airport", {})
            chave = (p.get("id"), p.get("time"), u.get("id"), u.get("time"), voo["_preco"])
            if chave not in vistos:
                vistos.add(chave)
                voos_unicos.append(voo)

        v_barato = montar_dados_voo(min(voos_unicos, key=lambda x: x["_preco"]), origem_query, destino_query)
        v_rapido = montar_dados_voo(min(voos_unicos, key=lambda x: x["_duracao"]), origem_query, destino_query)

        for voo in (v_barato, v_rapido):
            if voo:
                voo["data_voo"] = data_ida

        if v_barato:
            v_barato["quantidade_voos_analisados"] = len(voos_unicos)
            v_barato["menores_por_busca"] = menores_por_busca
            v_barato["preco_referencia_google"] = min(precos_ref_google) if precos_ref_google else None

        return v_barato, v_rapido
    except Exception as erro:
        st.error(f"❌ Erro durante a consulta: {erro}")
        return None, None


def consultar_promocao_google_flights(origem_query, destino_query, data_ida, data_volta=None):
    if not SERPAPI_KEY:
        return None

    params = _params_base(origem_query, data_ida, data_volta)
    params["engine"] = "google_flights_deals"

    try:
        res = GoogleSearch(params).get_dict()
        if res.get("error"):
            return None

        destinos_validos = {c.strip().upper() for c in str(destino_query).split(",") if c.strip()}
        candidatos = []

        for deal in res.get("deals", []) or []:
            dest = str(deal.get("arrival_airport_code", "")).upper()
            if dest not in destinos_validos:
                continue
            try:
                preco = float(deal["price"])
                candidatos.append(criar_dados_voo(
                    origem=deal.get("departure_airport_code", origem_query),
                    destino=dest,
                    preco=preco,
                    companhia=deal.get("airline", "Google Flights"),
                    duracao=deal.get("flight_duration", 0),
                    escalas=deal.get("stops", 0),
                    fonte="Google Flights Deals",
                    preco_referencia_google=preco,
                    data_voo=data_ida,
                ))
            except (KeyError, TypeError, ValueError):
                continue

        return min(candidatos, key=lambda x: x["preco"]) if candidatos else None
    except Exception:
        return None


def consultar_google_travel_explore(origem_query, destino_query, data_ida, data_volta=None):
    if not SERPAPI_KEY:
        return None

    params = _params_base(origem_query, data_ida, data_volta)
    params.update({"engine": "google_travel_explore", "arrival_id": destino_query})

    try:
        res = GoogleSearch(params).get_dict()
        if res.get("error"):
            return None

        voos = res.get("flights", []) or []
        candidatos = []

        for voo in voos:
            try:
                preco = float(voo["price"])
                p, c = voo.get("departure_airport", {}) or {}, voo.get("arrival_airport", {}) or {}
                candidatos.append(criar_dados_voo(
                    origem=p.get("id", origem_query),
                    destino=c.get("id", destino_query),
                    preco=preco,
                    companhia=voo.get("airline", "Google Travel Explore"),
                    duracao=voo.get("duration", 0),
                    escalas=voo.get("number_of_stops", 0),
                    fonte="Google Travel Explore",
                    preco_referencia_google=preco,
                    quantidade_voos_analisados=len(voos),
                    menores_por_busca=[{"rota": f"Google Travel Explore: {origem_query} → {destino_query}", "preco": preco}],
                    data_voo=data_ida,
                ))
            except (KeyError, TypeError, ValueError):
                continue

        return min(candidatos, key=lambda x: x["preco"]) if candidatos else None
    except Exception:
        return None


# BANCO DE DADOS DA APLICAÇÃO
def salvar_historico_db(
    origem,
    destino,
    preco,
    companhia,
    duracao=None,
    escalas=None,
    data_voo=None
):
    session = SessionLocal()

    try:
        # O st.date_input retorna date; a coluna do banco é DateTime.
        if data_voo and isinstance(data_voo, date) and not isinstance(data_voo, datetime):
            data_voo = datetime.combine(data_voo, datetime.min.time())

        # Evita salvar novamente exatamente o mesmo voo monitorado.
        registro_existente = session.query(HistoricoPreco).filter(
            HistoricoPreco.origem == origem,
            HistoricoPreco.destino == destino,
            HistoricoPreco.preco == preco,
            HistoricoPreco.companhia == companhia,
            HistoricoPreco.duracao == duracao,
            HistoricoPreco.escalas == escalas,
            HistoricoPreco.data_voo == data_voo,
        ).first()

        if registro_existente:
            return False

        registro = HistoricoPreco(
            origem=origem,
            destino=destino,
            preco=preco,
            companhia=companhia,
            duracao=duracao,
            escalas=escalas,
            data_voo=data_voo,
        )

        session.add(registro)
        session.commit()
        return True

    except Exception as erro:
        session.rollback()
        st.error(f"Erro ao salvar no banco de dados: {erro}")
        return None

    finally:
        session.close()


def carregar_historico_db():
    session = SessionLocal()

    try:
        registros = (
            session.query(HistoricoPreco)
            .order_by(HistoricoPreco.data_consulta.asc())
            .all()
        )

        return pd.DataFrame([
            {
                "Data Consulta": r.data_consulta,
                "Data Voo": r.data_voo,
                "Origem": r.origem,
                "Destino": r.destino,
                "Preco": r.preco,
                "Companhia": r.companhia,
                "Duracao": r.duracao,
                "Escalas": r.escalas,
            }
            for r in registros
        ])

    finally:
        session.close()


def exibir_grafico_historico(
    origem_filtro=None,
    destino_filtro=None,
    data_voo_filtro=None
):
    df = carregar_historico_db()

    if df.empty:
        st.info(
            "ℹ️ O banco de dados está vazio. "
            "Busque e salve um voo para começar o monitoramento."
        )
        return

    if not origem_filtro or not destino_filtro or not data_voo_filtro:
        st.info(
            "ℹ️ Faça uma busca de voo para visualizar "
            "a evolução de preços daquela viagem."
        )
        return

    origem_alvo = str(origem_filtro).upper().strip()
    destino_alvo = str(destino_filtro).upper().strip()
    data_alvo = pd.to_datetime(data_voo_filtro).date()

    for coluna_data in ["Data Consulta", "Data Voo"]:
        df[coluna_data] = pd.to_datetime(df[coluna_data], errors="coerce")

    origem_ok = (
        df["Origem"].astype(str).str.upper().str.strip()
        == origem_alvo
    )
    destino_ok = (
        df["Destino"].astype(str).str.upper().str.strip()
        == destino_alvo
    )
    data_ok = df["Data Voo"].dt.date == data_alvo

    df_filtrado = df[
        origem_ok & destino_ok & data_ok
    ].copy()

    if df_filtrado.empty:
        st.info(
            f"ℹ️ Ainda não há preços salvos para "
            f"**{origem_alvo} ➔ {destino_alvo}** "
            f"com viagem em **{data_alvo.strftime('%d/%m/%Y')}**.\n\n"
            "Salve o voo encontrado para iniciar o histórico."
        )
        return

    df_filtrado = (
        df_filtrado
        .dropna(subset=["Data Consulta", "Preco"])
        .sort_values("Data Consulta")
        .reset_index(drop=True)
    )

    if df_filtrado.empty:
        st.info("ℹ️ Não há dados válidos suficientes para gerar o gráfico.")
        return

    preco_inicial = float(df_filtrado.iloc[0]["Preco"])
    preco_atual = float(df_filtrado.iloc[-1]["Preco"])
    menor_preco = float(df_filtrado["Preco"].min())

    variacao_reais = preco_atual - preco_inicial
    variacao_percentual = (
        (variacao_reais / preco_inicial) * 100
        if preco_inicial
        else 0
    )

    st.caption(
        f"📍 **{origem_alvo} ➔ {destino_alvo}** "
        f"• voo em **{data_alvo.strftime('%d/%m/%Y')}**"
    )

    metrica1, metrica2, metrica3 = st.columns(3)

    with metrica1:
        st.metric(
            "Preço mais recente",
            formatar_preco(preco_atual)
        )

    with metrica2:
        st.metric(
            "Menor preço registrado",
            formatar_preco(menor_preco)
        )

    with metrica3:
        st.metric(
            "Variação desde o 1º registro",
            f"R$ {variacao_reais:+,.0f}".replace(",", "."),
            delta=f"{variacao_percentual:+.1f}%"
        )

    df_filtrado["Rotulo Consulta"] = (
        df_filtrado["Data Consulta"]
        .dt.strftime("%d/%m\n%H:%M")
    )

    fig, ax = plt.subplots(figsize=(8.5, 4.8))

    ax.plot(
        df_filtrado["Rotulo Consulta"],
        df_filtrado["Preco"],
        marker="o",
        linewidth=2.2,
        markersize=6
    )

    indice_menor = df_filtrado["Preco"].idxmin()

    ax.scatter(
        df_filtrado.loc[indice_menor, "Rotulo Consulta"],
        df_filtrado.loc[indice_menor, "Preco"],
        s=90,
        zorder=3,
        label="Menor preço"
    )

    ax.set_title(
        "Evolução do preço da passagem",
        fontsize=12,
        fontweight="bold",
        pad=12
    )
    ax.set_xlabel("Data e hora da consulta", fontsize=10)
    ax.set_ylabel("Preço (R$)", fontsize=10)
    ax.grid(True, linestyle="--", alpha=0.35)

    if len(df_filtrado) > 1:
        ax.legend()

    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=9)
    plt.tight_layout()

    st.pyplot(fig)
    plt.close(fig)

    if len(df_filtrado) == 1:
        st.caption(
            "💡 Há apenas 1 preço salvo para esta viagem. "
            "Quando novos preços forem registrados, "
            "a linha de evolução será formada automaticamente."
        )

    tabela = df_filtrado.copy()
    tabela["Data Consulta"] = (
        tabela["Data Consulta"]
        .dt.strftime("%d/%m/%Y %H:%M")
    )
    tabela["Data Voo"] = (
        tabela["Data Voo"]
        .dt.strftime("%d/%m/%Y")
    )
    tabela["Preco"] = tabela["Preco"].apply(formatar_preco)
    tabela["Duracao"] = tabela["Duracao"].apply(
        formatar_duracao
    )
    tabela["Escalas"] = tabela["Escalas"].apply(formatar_escalas)

    colunas_tabela = [
        "Data Consulta",
        "Data Voo",
        "Origem",
        "Destino",
        "Preco",
        "Companhia",
        "Duracao",
        "Escalas",
    ]

    with st.expander("📄 Ver histórico detalhado desta viagem"):
        st.dataframe(
            tabela[colunas_tabela].sort_values(
                by="Data Consulta",
                ascending=False
            ),
            use_container_width=True,
            hide_index=True
        )


def exibir_card_voo(voo, titulo, cor_badge, chave_btn):
    """Auxiliar para renderizar os cards de resultados na interface."""
    if not voo:
        return

    if cor_badge == "success":
        st.success(f"🏷️ **{titulo}**")
    else:
        st.info(f"⚡ **{titulo}**")

    preco_fmt = formatar_preco(voo["preco"])
    st.metric(f"Preço ({voo['companhia']})", preco_fmt)

    if voo.get("fonte") == "Google Flights Deals":
        st.caption("🔥 Preço encontrado na busca promocional do Google Flights")
    elif voo.get("fonte") == "Google Travel Explore":
        st.caption("🌎 Preço encontrado no Google Travel Explore")

    st.write(f"✈️ **Rota:** {voo['origem']} ➔ {voo['destino']}")
    if voo["saida"]:
        st.write(f"🕒 **Saída:** {voo['saida']}")
    if voo["chegada"]:
        st.write(f"🕒 **Chegada:** {voo['chegada']}")

    escalas_txt = formatar_escalas(voo.get("escalas"))
    st.caption(f"⏱️ Duração: {formatar_duracao(voo['duracao'])} • {escalas_txt}")

    if "quantidade_voos_analisados" in voo:
        with st.expander("🔎 Detalhes da busca"):
            st.write(f"Voos analisados: **{voo.get('quantidade_voos_analisados', 0)}**")
            st.write(f"Menor preço com voo detalhado: **{preco_fmt}**")
            preco_g = voo.get("preco_referencia_google")
            preco_google_fmt = formatar_preco(preco_g) if preco_g is not None else "não informado pela API"
            st.write(f"Menor preço indicado pelo Google: **{preco_google_fmt}**")

            if voo.get("menores_por_busca"):
                st.write("**Menor preço por pesquisa:**")
                for item in voo["menores_por_busca"]:
                    preco_rota = formatar_preco(item["preco"])
                    st.write(f"• {item['rota']}: **{preco_rota}**")

    if st.button(f"💾 Salvar {titulo.split()[-1]}", key=chave_btn):
        resultado_salvamento = salvar_historico_db(
            origem=voo["origem"],
            destino=voo["destino"],
            preco=voo["preco"],
            companhia=voo["companhia"],
            duracao=voo.get("duracao"),
            escalas=voo.get("escalas"),
            data_voo=voo.get("data_voo"),
        )
        if resultado_salvamento:
            st.success("✅ Voo salvo no Banco de Dados!")
            st.rerun()
        elif resultado_salvamento is False:
            st.info("ℹ️ Este voo já está salvo no histórico.")


# INTERFACE DO USUÁRIO
col_esquerda, col_direita = st.columns([1.1, 0.9])

with col_esquerda:
    st.subheader("🔍 Buscar Passagem")
    col1, col2 = st.columns(2)

    with col1:
        origem_input = st_searchbox(buscar_locais, label="📍 Cidade de Origem:", placeholder="Digite pelo menos 3 letras...", key="origem_busca", debounce=350, edit_after_submit="option")
        data_ida = st.date_input("📅 Data de Ida:", value=None, min_value=date.today(), format="DD/MM/YYYY")
        tem_volta = st.checkbox("Incluir Data de Volta", value=False)

    with col2:
        destino_input = st_searchbox(buscar_locais, label="🎯 Cidade de Destino:", placeholder="Digite pelo menos 3 letras...", key="destino_busca", debounce=350, edit_after_submit="option")
        data_volta = st.date_input("📅 Data de Volta:", value=None, min_value=data_ida if data_ida else date.today(), format="DD/MM/YYYY") if tem_volta else None

    if st.button("🔍 Buscar Ofertas", type="primary", use_container_width=True):
        st.session_state["voo_barato"] = None
        st.session_state["voo_rapido"] = None

        if not origem_input:
            st.error("⚠️ Selecione uma cidade ou aeroporto de origem.")
        elif not destino_input:
            st.error("⚠️ Selecione uma cidade ou aeroporto de destino.")
        elif not data_ida:
            st.error("⚠️ Selecione a Data de Ida.")
        elif tem_volta and not data_volta:
            st.error("⚠️ Selecione a Data de Volta.")
        elif data_volta and data_volta < data_ida:
            st.error("⚠️ A Data de Volta não pode ser anterior à Data de Ida.")
        elif origem_input["id"] == destino_input["id"]:
            st.error("⚠️ Origem e destino precisam ser diferentes.")
        else:
            st.info(f"Buscando voos de **{origem_input['nome']}** para **{destino_input['nome']}**...")
            with st.spinner("Consultando ofertas no Google Flights..."):
                v_barato, v_rapido = consultar_voo(origem_input["id"], destino_input["id"], data_ida, data_volta)
                v_promocional = consultar_promocao_google_flights(origem_input["id"], destino_input["id"], data_ida, data_volta)
                v_explore = consultar_google_travel_explore(origem_input["id"], destino_input["id"], data_ida, data_volta)

                candidatos = [v for v in [v_barato, v_promocional, v_explore] if v is not None]
                if candidatos:
                    v_barato = min(candidatos, key=lambda x: x["preco"])

            if v_barato or v_rapido:
                st.session_state["voo_barato"] = v_barato
                st.session_state["voo_rapido"] = v_rapido
            else:
                st.warning("⚠️ Nenhum voo encontrado para a rota e data informadas.")

    # Exibição dos resultados
    v_barato = st.session_state.get("voo_barato")
    v_rapido = st.session_state.get("voo_rapido")

    if v_barato or v_rapido:
        st.write("---")
        res_col1, res_col2 = st.columns(2)
        with res_col1:
            exibir_card_voo(v_barato, "Voo Mais Barato", "success", "btn_salvar_barato")
        with res_col2:
            exibir_card_voo(v_rapido, "Voo Mais Rápido", "info", "btn_salvar_rapido")

with col_direita:
    st.subheader("📈 Histórico de Preços Monitorados")

    v_ref = (
        st.session_state.get("voo_barato")
        or st.session_state.get("voo_rapido")
    )

    exibir_grafico_historico(
        v_ref["origem"] if v_ref else None,
        v_ref["destino"] if v_ref else None,
        v_ref.get("data_voo") if v_ref else None,
    )