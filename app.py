import os
import sqlite3
from datetime import datetime, date
import pandas as pd
import plotly.express as px
import streamlit as st
from streamlit_searchbox import st_searchbox
from serpapi import GoogleSearch
from dotenv import load_dotenv

# Carrega variáveis de ambiente (.env)
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_KEY")
DB_NAME = "historico_voos.db"

# ==========================================
# 1. GERENCIAMENTO DO BANCO DE DADOS (SQLITE)
# ==========================================
def init_db():
    """Cria a tabela no SQLite se ainda não existir."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS historico_voos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                origem TEXT NOT NULL,
                destino TEXT NOT NULL,
                preco REAL NOT NULL,
                companhia TEXT,
                duracao INTEGER,
                escalas INTEGER,
                data_voo TEXT,
                data_consulta TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.commit()

def salvar_historico_db(origem, destino, preco, companhia, duracao, escalas, data_voo):
    """Insere um novo registro de voo pesquisado no banco de dados."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        data_voo_str = data_voo.strftime("%Y-%m-%d") if isinstance(data_voo, (date, datetime)) else str(data_voo)
        cursor.execute("""
            INSERT INTO historico_voos (origem, destino, preco, companhia, duracao, escalas, data_voo)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (origem, destino, preco, companhia, duracao, escalas, data_voo_str))
        conn.commit()

def carregar_historico_db():
    """Recupera o histórico completo do banco de dados em formato DataFrame."""
    init_db()
    with sqlite3.connect(DB_NAME) as conn:
        df = pd.read_sql_query("SELECT * FROM historico_voos ORDER BY data_consulta DESC", conn)
    return df

def deletar_registro_db(registro_id):
    """Deleta um registro específico do histórico pelo ID."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM historico_voos WHERE id = ?", (registro_id,))
        conn.commit()

def limpar_todo_historico_db():
    """Apaga todos os registros da tabela historico_voos."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM historico_voos")
        conn.commit()

# Inicializa a estrutura do banco ao iniciar o app
init_db()

# ==========================================
# 2. RENDERIZAÇÃO DE GRÁFICOS E MÉTRICAS
# ==========================================
def renderizar_grafico_evolucao(df):
    """Gera o painel de métricas de tendência e o gráfico de linha Plotly."""
    if df.empty:
        st.info("📌 Nenhum histórico disponível para exibir o gráfico.")
        return

    # Formatação de colunas
    df["Rota"] = df["origem"] + " ➔ " + df["destino"]
    df["Data_Consulta_DT"] = pd.to_datetime(df["data_consulta"])
    df["Preço (R$)"] = df["preco"]

    rotas_disponiveis = df["Rota"].unique()
    rota_selecionada = st.selectbox("Selecione a Rota:", rotas_disponiveis, key="select_rota_grafico")

    df_rota = df[df["Rota"] == rota_selecionada]
    datas_voo_disponiveis = df_rota["data_voo"].dropna().unique()
    
    if len(datas_voo_disponiveis) > 0:
        data_voo_selecionada = st.selectbox("Selecione a Data do Voo:", datas_voo_disponiveis, key="select_data_grafico")
        df_grafico = df_rota[df_rota["data_voo"] == data_voo_selecionada].sort_values("Data_Consulta_DT")
    else:
        df_grafico = df_rota.sort_values("Data_Consulta_DT")
        data_voo_selecionada = "Não informada"

    if df_grafico.empty:
        st.warning("Sem dados suficientes para gerar o gráfico com estes filtros.")
        return

    # Métricas de Tendência
    preco_inicial = df_grafico["Preço (R$)"].iloc[0]
    preco_atual = df_grafico["Preço (R$)"].iloc[-1]
    variacao = preco_atual - preco_inicial
    percentual = (variacao / preco_inicial) * 100 if preco_inicial > 0 else 0

    m1, m2, m3 = st.columns(3)
    m1.metric("Preço Atual (Última Busca)", f"R$ {preco_atual:.2f}", delta=f"{variacao:+.2f} ({percentual:+.1f}%)", delta_color="inverse")
    m2.metric("Menor Preço Histórico", f"R$ {df_grafico['Preço (R$)'].min():.2f}")
    m3.metric("Maior Preço Histórico", f"R$ {df_grafico['Preço (R$)'].max():.2f}")

    # Gráfico de Linha Interativo
    fig = px.line(
        df_grafico,
        x="Data_Consulta_DT",
        y="Preço (R$)",
        markers=True,
        title=f"Histórico de Menor Preço: {rota_selecionada} (Voo em: {data_voo_selecionada})",
        labels={"Data_Consulta_DT": "Data/Hora da Busca", "Preço (R$)": "Preço Mínimo (R$)"}
    )

    fig.update_traces(line_color="#1f77b4", line_width=3, marker_size=8)
    fig.update_layout(hovermode="x unified", yaxis_tickprefix="R$ ")

    st.plotly_chart(fig, use_container_width=True)

# ==========================================
# 3. CONFIGURAÇÃO E INTEGRAÇÃO SERPAPI
# ==========================================
st.set_page_config(page_title="PousaAqui - Painel de Monitoramento", page_icon="✈️", layout="wide")
st.title("✈️ PousaAqui - Painel de Monitoramento")
st.write("Digite o nome ou código de qualquer cidade ou aeroporto!")


def formatar_duracao(minutos):
    try:
        minutos = int(minutos)
    except (TypeError, ValueError):
        return "N/A"
    horas, mins = divmod(minutos, 60)
    if horas and mins:
        return f"{horas}h {mins:02d}min"
    return f"{horas}h" if horas else f"{mins}min"


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


def montar_dados_voo(voo, origem_query, destino_query, data_voo=None):
    trechos = voo.get("flights", [])
    if not trechos:
        return None

    partida = trechos[0].get("departure_airport", {})
    chegada = trechos[-1].get("arrival_airport", {})
    companhias = list(dict.fromkeys(t.get("airline") for t in trechos if t.get("airline")))

    return {
        "origem": partida.get("id", origem_query),
        "destino": chegada.get("id", destino_query),
        "preco": voo["_preco"],
        "companhia": ", ".join(companhias) or "N/A",
        "saida": partida.get("time", ""),
        "chegada": chegada.get("time", ""),
        "duracao": voo.get("_duracao", 0),
        "escalas": max(len(trechos) - 1, 0),
        "data_voo": data_voo,
    }


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
        preco_ref = res_geral.get("price_insights", {}).get("lowest_price")
        if preco_ref:
            try:
                precos_ref_google.append(float(preco_ref))
            except ValueError:
                pass

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
                    preco_ind = res_ind.get("price_insights", {}).get("lowest_price")
                    if preco_ind:
                        try:
                            precos_ref_google.append(float(preco_ind))
                        except ValueError:
                            pass

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

        v_barato = montar_dados_voo(min(voos_unicos, key=lambda x: x["_preco"]), origem_query, destino_query, data_ida)
        v_rapido = montar_dados_voo(min(voos_unicos, key=lambda x: x["_duracao"]), origem_query, destino_query, data_ida)

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
                candidatos.append({
                    "origem": deal.get("departure_airport_code", origem_query),
                    "destino": dest,
                    "preco": preco,
                    "companhia": deal.get("airline", "Google Flights"),
                    "saida": "",
                    "chegada": "",
                    "duracao": deal.get("flight_duration", 0),
                    "escalas": deal.get("stops", 0),
                    "data_voo": data_ida,
                    "fonte": "Google Flights Deals",
                    "preco_referencia_google": preco,
                    "quantidade_voos_analisados": 0,
                    "menores_por_busca": [],
                })
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
                candidatos.append({
                    "origem": p.get("id", origem_query),
                    "destino": c.get("id", destino_query),
                    "preco": preco,
                    "companhia": voo.get("airline", "Google Travel Explore"),
                    "saida": "",
                    "chegada": "",
                    "duracao": voo.get("duration", 0),
                    "escalas": voo.get("number_of_stops", 0),
                    "data_voo": data_ida,
                    "fonte": "Google Travel Explore",
                    "preco_referencia_google": preco,
                    "quantidade_voos_analisados": len(voos),
                    "menores_por_busca": [{"rota": f"Google Travel Explore: {origem_query} → {destino_query}", "preco": preco}],
                })
            except (KeyError, TypeError, ValueError):
                continue

        return min(candidatos, key=lambda x: x["preco"]) if candidatos else None
    except Exception:
        return None

# ==========================================
# 4. AUXILIAR DE INTERFACE (CARDS DE VOO)
# ==========================================
def exibir_card_voo(voo, titulo, cor_badge, chave_btn):
    if not voo:
        return

    if cor_badge == "success":
        st.success(f"🏷️ **{titulo}**")
    else:
        st.info(f"⚡ **{titulo}**")

    preco_fmt = f"R$ {voo['preco']:,.0f}".replace(",", ".")
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

    escalas_txt = "Sem escalas" if voo["escalas"] == 0 else f"{voo['escalas']} escala(s)"
    st.caption(f"⏱️ Duração: {formatar_duracao(voo['duracao'])} • {escalas_txt}")

    if "quantidade_voos_analisados" in voo:
        with st.expander("🔎 Detalhes da busca"):
            st.write(f"Voos analisados: **{voo.get('quantidade_voos_analisados', 0)}**")
            st.write(f"Menor preço com voo detalhado: **{preco_fmt}**")
            preco_g = voo.get("preco_referencia_google")
            st.write(f"Menor preço indicado pelo Google: **{f'R$ {preco_g:,.0f}'.replace(',', '.') if preco_g else 'não informado pela API'}**")

            if voo.get("menores_por_busca"):
                st.write("**Menor preço por pesquisa:**")
                for item in voo["menores_por_busca"]:
                    st.write(f"• {item['rota']}: **R$ {item['preco']:,.0f}**".replace(",", "."))

    if st.button(f"💾 Salvar {titulo.split()[-1]}", key=chave_btn):
        salvar_historico_db(
            origem=voo["origem"],
            destino=voo["destino"],
            preco=voo["preco"],
            companhia=voo["companhia"],
            duracao=voo.get("duracao"),
            escalas=voo.get("escalas"),
            data_voo=voo.get("data_voo")
        )
        st.success("✅ Voo salvo no Banco de Dados!")
        st.rerun()

# ==========================================
# 5. INTERFACE DO USUÁRIO (LAYOUT PRINCIPAL)
# ==========================================
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

    # Exibição dos resultados da busca
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
    st.subheader("📊 Painel de Histórico")
    
    # Carrega os dados mais recentes do SQLite
    df_hist = carregar_historico_db()

    tab_grafico, tab_tabela = st.tabs(["📈 Evolução de Preços", "📋 Tabela e Gerenciamento"])

    with tab_grafico:
        renderizar_grafico_evolucao(df_hist)

    with tab_tabela:
        if not df_hist.empty:
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            
            st.write("---")
            col_down, col_del = st.columns([1, 1])
            
            with col_down:
                st.download_button(
                    label="📥 Baixar Histórico (CSV)",
                    data=df_hist.to_csv(index=False).encode("utf-8"),
                    file_name=f"historico_pousaaqui_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv",
                    use_container_width=True
                )
            
            with col_del:
                # Exclusão individual por ID
                id_para_deletar = st.selectbox(
                    "Selecione o ID para excluir:",
                    options=df_hist["id"].tolist(),
                    key="select_del_id"
                )
                if st.button("🗑️ Excluir Item Selecionado", type="secondary", use_container_width=True):
                    deletar_registro_db(id_para_deletar)
                    st.success(f"✅ Registro #{id_para_deletar} excluído!")
                    st.rerun()

            # Opção de reset completo
            with st.expander("⚠️ Zona de Perigo"):
                st.caption("A ação abaixo removerá todos os registros salvos permanentemente.")
                if st.button("🚨 Apagar TODO o Histórico", type="primary"):
                    limpar_todo_historico_db()
                    st.success("✅ Todo o histórico foi zerado!")
                    st.rerun()
        else:
            st.info("Nenhum registro no banco de dados até o momento.")