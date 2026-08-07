import streamlit as st

from database.repositorio_precos import salvar_historico
from utils.formatadores import formatar_duracao, formatar_escalas, formatar_preco


def exibir_card_voo(voo, titulo, cor_badge, chave_btn):
    """Renderiza um card de resultado e seu botão de salvamento."""
    if not voo:
        return

    if cor_badge == "success":
        st.success(f"🏷️ **{titulo}**")
    else:
        st.info(f"⚡ **{titulo}**")

    preco_formatado = formatar_preco(voo["preco"])
    st.metric(f"Preço ({voo['companhia']})", preco_formatado)

    if voo.get("fonte") == "Google Flights Deals":
        st.caption("🔥 Preço encontrado na busca promocional do Google Flights")
    elif voo.get("fonte") == "Google Travel Explore":
        st.caption("🌎 Preço encontrado no Google Travel Explore")

    st.write(f"✈️ **Rota:** {voo['origem']} ➔ {voo['destino']}")
    if voo.get("saida"):
        st.write(f"🕒 **Saída:** {voo['saida']}")
    if voo.get("chegada"):
        st.write(f"🕒 **Chegada:** {voo['chegada']}")

    st.caption(
        f"⏱️ Duração: {formatar_duracao(voo.get('duracao'))} "
        f"• {formatar_escalas(voo.get('escalas'))}"
    )

    if "quantidade_voos_analisados" in voo:
        with st.expander("🔎 Detalhes da busca"):
            st.write(
                "Voos analisados: "
                f"**{voo.get('quantidade_voos_analisados', 0)}**"
            )
            st.write(f"Menor preço com voo detalhado: **{preco_formatado}**")

            preco_google = voo.get("preco_referencia_google")
            preco_google_formatado = (
                formatar_preco(preco_google)
                if preco_google is not None
                else "não informado pela API"
            )
            st.write(
                "Menor preço indicado pelo Google: "
                f"**{preco_google_formatado}**"
            )

            if voo.get("menores_por_busca"):
                st.write("**Menor preço por pesquisa:**")
                for item in voo["menores_por_busca"]:
                    st.write(
                        f"• {item['rota']}: "
                        f"**{formatar_preco(item['preco'])}**"
                    )

    if st.button(f"💾 Salvar {titulo.split()[-1]}", key=chave_btn):
        try:
            resultado = salvar_historico(
                origem=voo["origem"],
                destino=voo["destino"],
                preco=voo["preco"],
                companhia=voo["companhia"],
                duracao=voo.get("duracao"),
                escalas=voo.get("escalas"),
                data_voo=voo.get("data_voo"),
            )

            if resultado:
                st.success("✅ Voo salvo no Banco de Dados!")
                st.rerun()
            else:
                st.info("ℹ️ Este voo já está salvo no histórico.")
        except Exception as erro:
            st.error(f"Erro ao salvar no banco de dados: {erro}")