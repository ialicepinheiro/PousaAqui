import csv
import os
from datetime import date, datetime

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st
from dotenv import load_dotenv
from serpapi import GoogleSearch
from streamlit_searchbox import st_searchbox

# Configurações iniciais
load_dotenv()
SERPAPI_KEY = os.getenv("SERP_API_KEY") or os.getenv("SERPAPI_KEY")
CSV_FILE = "historico_precos.csv"

st.set_page_config(
    page_title="PousaAqui - Painel de Monitoramento",
    page_icon="✈️",
    layout="wide",
)

st.title("✈️ PousaAqui - Painel de Monitoramento")
st.write("Digite o nome ou código de qualquer cidade ou aeroporto!")


# --- FUNÇÕES AUXILIARES ---

def formatar_duracao(minutos):
    """Converte a duração em minutos para o formato 'Xh Ymin'."""
    try:
        minutos = int(minutos)
    except (TypeError, ValueError):
        return "N/A"

    horas, minutos = divmod(minutos, 60)
    if horas and minutos:
        return f"{horas}h {minutos:02d}min"
    if horas:
        return f"{horas}h"
    return f"{minutos}min"


@st.cache_data(ttl=3600, show_spinner=False)
def buscar_locais(termo):
    """Busca cidades e aeroportos via Autocomplete da SerpApi."""
    termo = (termo or "").strip()
    if len(termo) < 3 or not SERPAPI_KEY:
        return []

    params = {
        "engine": "google_flights_autocomplete",
        "q": termo,
        "hl": "pt",
        "gl": "br",
        "api_key": SERPAPI_KEY,
    }

    try:
        sugestoes = GoogleSearch(params).get_dict().get("suggestions", [])
        opcoes = []
        ids_adicionados = set()

        for local in sugestoes:
            # Adiciona a Cidade/Região
            local_id = local.get("id")
            nome_local = local.get("name", termo)

            if local_id and local_id not in ids_adicionados:
                descricao = local.get("description", "")
                texto = f"📍 {nome_local} - Todos os aeroportos"
                if descricao:
                    texto += f" ({descricao})"

                opcoes.append((
                    texto,
                    {
                        "id": local_id,
                        "nome": nome_local,
                        "tipo": local.get("type", "cidade"),
                    },
                ))
                ids_adicionados.add(local_id)

            # Adiciona Aeroportos individuais da cidade
            for aeroporto in local.get("airports", []):
                codigo = aeroporto.get("id")
                if not codigo or codigo in ids_adicionados:
                    continue

                nome_aeroporto = aeroporto.get("name", "")
                cidade = aeroporto.get("city", "")
                texto = f"✈️ {codigo} - {nome_aeroporto}"
                if cidade:
                    texto += f" ({cidade})"

                opcoes.append((
                    texto,
                    {
                        "id": codigo,
                        "nome": f"{codigo} - {nome_aeroporto}",
                        "tipo": "aeroporto",
                    },
                ))
                ids_adicionados.add(codigo)

        return opcoes[:12]
    except Exception:
        return []


def consultar_voo(origem_query, destino_query, data_ida, data_volta=None):
    """Realiza a busca de ofertas de voos no Google Flights."""
    if not SERPAPI_KEY:
        st.error("❌ Chave da SerpApi não encontrada no arquivo .env.")
        return None

    params = {
        "engine": "google_flights",
        "departure_id": origem_query,
        "arrival_id": destino_query,
        "outbound_date": data_ida.strftime("%Y-%m-%d"),
        "type": 1 if data_volta else 2,  # 1 = Ida/Volta, 2 = Somente Ida
        "travel_class": 1,
        "adults": 1,
        "currency": "BRL",
        "gl": "br",
        "hl": "pt",
        "sort_by": 2,  # Ordena por preço
        "deep_search": "true",
        "show_hidden": "true",
        "api_key": SERPAPI_KEY,
    }

    if data_volta:
        params["return_date"] = data_volta.strftime("%Y-%m-%d")

    try:
        resultados = GoogleSearch(params).get_dict()
        if resultados.get("error"):
            st.error(f"❌ Erro da SerpApi: {resultados['error']}")
            return None

        todos_voos = resultados.get("best_flights", []) + resultados.get("other_flights", [])
        voos_validos = []

        for voo in todos_voos:
            try:
                voo_copia = voo.copy()
                voo_copia["_preco"] = float(voo["price"])
                voos_validos.append(voo_copia)
            except (KeyError, TypeError, ValueError):
                continue

        if not voos_validos:
            return None

        melhor_voo = min(voos_validos, key=lambda v: v["_preco"])
        trechos = melhor_voo.get("flights", [])
        if not trechos:
            return None

        partida = trechos[0].get("departure_airport", {})
        chegada = trechos[-1].get("arrival_airport", {})

        # Identifica companhias aéreas sem duplicatas
        companhias = list(dict.fromkeys(
            t.get("airline") for t in trechos if t.get("airline")
        ))

        return {
            "origem": partida.get("id", origem_query),
            "destino": chegada.get("id", destino_query),
            "preco": melhor_voo["_preco"],
            "companhia": ", ".join(companhias) or "N/A",
            "saida": partida.get("time", ""),
            "chegada": chegada.get("time", ""),
            "duracao": melhor_voo.get("total_duration"),
            "escalas": max(len(trechos) - 1, 0),
            "menor_preco_indicado_google": resultados.get("price_insights", {}).get("lowest_price"),
        }
    except Exception as erro:
        st.error(f"❌ Erro durante a consulta: {erro}")
        return None


# --- GERENCIAMENTO DE HISTÓRICO ---

def salvar_historico(data_consulta, origem, destino, preco):
    """Salva a consulta realizada em um arquivo CSV."""
    existe = os.path.exists(CSV_FILE)
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as arquivo:
        writer = csv.writer(arquivo)
        if not existe:
            writer.writerow(["Data", "Origem", "Destino", "Preco"])
        writer.writerow([data_consulta, origem, destino, preco])


def exibir_grafico_historico(origem_filtro, destino_filtro):
    """Exibe o gráfico de linhas e a tabela baseados nos filtros de origem/destino."""
    if not os.path.exists(CSV_FILE):
        st.info("ℹ️ Nenhum histórico encontrado. Faça uma busca e salve para ver o gráfico!")
        return

    try:
        df = pd.read_csv(CSV_FILE)
    except Exception:
        st.info("ℹ️ Arquivo de histórico ainda não possui registros.")
        return

    if df.empty:
        st.info("ℹ️ Histórico de preços está vazio.")
        return

    if origem_filtro and destino_filtro:
        origem_ok = df["Origem"].astype(str).str.upper().str.strip() == str(origem_filtro).upper().strip()
        destino_ok = df["Destino"].astype(str).str.upper().str.strip() == str(destino_filtro).upper().strip()
        df = df[origem_ok & destino_ok].copy()

    if df.empty:
        st.info("ℹ️ Nenhum histórico registrado para essa rota ainda.")
        return

    df["Preco"] = pd.to_numeric(df["Preco"], errors="coerce")
    df = df.dropna(subset=["Preco"])

    if df.empty:
        return

    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(df["Data"].astype(str), df["Preco"], marker="o", linewidth=2.5)
    ax.set_title("Evolução do Preço das Passagens")
    ax.set_xlabel("Data da Consulta")
    ax.set_ylabel("Preço (R$)")
    ax.grid(True, linestyle="--", alpha=0.6)
    plt.xticks(rotation=45)
    plt.tight_layout()

    st.pyplot(fig)
    plt.close(fig)
    st.dataframe(df, use_container_width=True)


# --- INTERFACE (STREAMLIT) ---

col_esquerda, col_direita = st.columns([1, 1])

with col_esquerda:
    st.subheader("🔍 Buscar Passagem")
    col1, col2 = st.columns(2)

    with col1:
        origem_input = st_searchbox(
            buscar_locais,
            label="📍 Cidade de Origem:",
            placeholder="Digite pelo menos 3 letras...",
            key="origem_busca",
            debounce=350,
            edit_after_submit="option",
        )
        data_ida = st.date_input("📅 Data de Ida:", value=None, min_value=date.today(), format="DD/MM/YYYY")
        tem_volta = st.checkbox("Incluir Data de Volta", value=False)

    with col2:
        destino_input = st_searchbox(
            buscar_locais,
            label="🎯 Cidade de Destino:",
            placeholder="Digite pelo menos 3 letras...",
            key="destino_busca",
            debounce=350,
            edit_after_submit="option",
        )
        data_volta = None
        if tem_volta:
            data_volta = st.date_input(
                "📅 Data de Volta:",
                value=None,
                min_value=data_ida if data_ida else date.today(),
                format="DD/MM/YYYY",
            )

    if st.button("🔍 Buscar Melhor Preço", type="primary", use_container_width=True):
        st.session_state["ultimo_voo"] = None

        # Validações de entrada
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
            st.info(f"Buscando o menor preço de **{origem_input['nome']}** para **{destino_input['nome']}**...")
            with st.spinner("Consultando ofertas do Google Flights..."):
                voo = consultar_voo(origem_input["id"], destino_input["id"], data_ida, data_volta)

            if voo:
                st.session_state["ultimo_voo"] = voo
            else:
                st.warning("⚠️ Nenhum voo encontrado para a rota e data informadas.")

    # Exibição do Resultado
    voo = st.session_state.get("ultimo_voo")
    if voo:
        st.success("🎉 **Melhor Voo Encontrado!**")
        resultado1, resultado2 = st.columns(2)

        with resultado1:
            st.metric(f"Preço ({voo['companhia']})", f"R$ {voo['preco']:,.0f}".replace(",", "."))
        with resultado2:
            st.write(f"✈️ **Saindo de:** {voo['origem']}")
            st.write(f"🎯 **Indo para:** {voo['destino']}")

        if voo["saida"]:
            st.write(f"🕒 **Saída:** {voo['saida']}")
        if voo["chegada"]:
            st.write(f"🕒 **Chegada:** {voo['chegada']}")

        escalas = "Sem escalas" if voo["escalas"] == 0 else f"{voo['escalas']} escala(s)"
        st.caption(f"Duração: {formatar_duracao(voo['duracao'])} • {escalas}")

        preco_google = voo.get("menor_preco_indicado_google")
        if preco_google is not None:
            try:
                preco_google = float(preco_google)
                if preco_google < voo["preco"]:
                    st.caption(f"ℹ️ Google Flights indica preços a partir de R$ {preco_google:,.0f}".replace(",", "."))
            except (TypeError, ValueError):
                pass

        if st.button("💾 Salvar no Monitoramento"):
            salvar_historico(
                datetime.now().strftime("%d/%m/%Y %H:%M"),
                voo["origem"],
                voo["destino"],
                voo["preco"],
            )
            st.success("✅ Preço salvo no histórico!")
            st.rerun()

with col_direita:
    st.subheader("📈 Histórico de Preços Monitorados")
    voo = st.session_state.get("ultimo_voo")
    origem_h = voo["origem"] if voo else ""
    destino_h = voo["destino"] if voo else ""
    exibir_grafico_historico(origem_h, destino_h)