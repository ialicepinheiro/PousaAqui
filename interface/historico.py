import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from database.repositorio_precos import carregar_historico
from utils.formatadores import formatar_duracao, formatar_escalas, formatar_preco


def exibir_grafico_historico(
    origem_filtro=None,
    destino_filtro=None,
    data_voo_filtro=None,
):
    """Exibe métricas, gráfico e tabela do histórico da viagem atual."""
    dataframe = carregar_historico()

    if dataframe.empty:
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
        dataframe[coluna_data] = pd.to_datetime(
            dataframe[coluna_data], errors="coerce"
        )

    origem_ok = (
        dataframe["Origem"].astype(str).str.upper().str.strip()
        == origem_alvo
    )
    destino_ok = (
        dataframe["Destino"].astype(str).str.upper().str.strip()
        == destino_alvo
    )
    data_ok = dataframe["Data Voo"].dt.date == data_alvo

    dataframe_filtrado = dataframe[
        origem_ok & destino_ok & data_ok
    ].copy()

    if dataframe_filtrado.empty:
        st.info(
            f"ℹ️ Ainda não há preços salvos para "
            f"**{origem_alvo} ➔ {destino_alvo}** "
            f"com viagem em **{data_alvo.strftime('%d/%m/%Y')}**.\n\n"
            "Salve o voo encontrado para iniciar o histórico."
        )
        return

    dataframe_filtrado = (
        dataframe_filtrado
        .dropna(subset=["Data Consulta", "Preco"])
        .sort_values("Data Consulta")
        .reset_index(drop=True)
    )

    if dataframe_filtrado.empty:
        st.info("ℹ️ Não há dados válidos suficientes para gerar o gráfico.")
        return

    preco_inicial = float(dataframe_filtrado.iloc[0]["Preco"])
    preco_atual = float(dataframe_filtrado.iloc[-1]["Preco"])
    menor_preco = float(dataframe_filtrado["Preco"].min())
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
        st.metric("Preço mais recente", formatar_preco(preco_atual))
    with metrica2:
        st.metric("Menor preço registrado", formatar_preco(menor_preco))
    with metrica3:
        st.metric(
            "Variação desde o 1º registro",
            f"R$ {variacao_reais:+,.0f}".replace(",", "."),
            delta=f"{variacao_percentual:+.1f}%",
        )

    dataframe_filtrado["Rotulo Consulta"] = (
        dataframe_filtrado["Data Consulta"].dt.strftime("%d/%m\n%H:%M")
    )

    figura, eixo = plt.subplots(figsize=(8.5, 4.8))
    eixo.plot(
        dataframe_filtrado["Rotulo Consulta"],
        dataframe_filtrado["Preco"],
        marker="o",
        linewidth=2.2,
        markersize=6,
    )

    indice_menor = dataframe_filtrado["Preco"].idxmin()
    eixo.scatter(
        dataframe_filtrado.loc[indice_menor, "Rotulo Consulta"],
        dataframe_filtrado.loc[indice_menor, "Preco"],
        s=90,
        zorder=3,
        label="Menor preço",
    )

    eixo.set_title(
        "Evolução do preço da passagem",
        fontsize=12,
        fontweight="bold",
        pad=12,
    )
    eixo.set_xlabel("Data e hora da consulta", fontsize=10)
    eixo.set_ylabel("Preço (R$)", fontsize=10)
    eixo.grid(True, linestyle="--", alpha=0.35)

    if len(dataframe_filtrado) > 1:
        eixo.legend()

    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.yticks(fontsize=9)
    plt.tight_layout()
    st.pyplot(figura)
    plt.close(figura)

    if len(dataframe_filtrado) == 1:
        st.caption(
            "💡 Há apenas 1 preço salvo para esta viagem. "
            "Quando novos preços forem registrados, "
            "a linha de evolução será formada automaticamente."
        )

    tabela = dataframe_filtrado.copy()
    tabela["Data Consulta"] = tabela["Data Consulta"].dt.strftime(
        "%d/%m/%Y %H:%M"
    )
    tabela["Data Voo"] = tabela["Data Voo"].dt.strftime("%d/%m/%Y")
    tabela["Preco"] = tabela["Preco"].apply(formatar_preco)
    tabela["Duracao"] = tabela["Duracao"].apply(formatar_duracao)
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
                by="Data Consulta", ascending=False
            ),
            use_container_width=True,
            hide_index=True,
        )