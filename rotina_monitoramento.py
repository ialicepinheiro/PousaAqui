import os
from pathlib import Path
import requests
from datetime import datetime
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from serpapi import GoogleSearch

# Importa os modelos do seu app.py existente
from app import HistoricoPreco, DATABASE_URL, _params_base, extrair_voos, salvar_historico_db

# Garante que o Python encontre o .env na mesma pasta deste script
env_path = Path(__file__).resolve().parent / ".env"
load_dotenv(dotenv_path=env_path)

# Configurações do Telegram e SerpApi
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
SERPAPI_KEY = os.getenv("SERP_API_KEY") or os.getenv("SERPAPI_KEY")

def enviar_mensagem_telegram(mensagem: str):
    """Envia notificação formatada para o bot do Telegram."""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Token do Telegram ou Chat ID não configurados!")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": mensagem,
        "parse_mode": "Markdown"
    }
    
    try:
        resposta = requests.post(url, json=payload)
        if resposta.status_code == 200:
            print("✅ Notificação enviada ao Telegram com sucesso!")
        else:
            print(f"❌ Erro ao enviar para o Telegram: {resposta.text}")
    except Exception as erro:
        print(f"❌ Falha de conexão com o Telegram: {erro}")


def executar_verificacao_automatica():
    """Busca as rotas cadastradas no banco e envia alertas no Telegram."""
    engine = create_engine(DATABASE_URL)
    Session = sessionmaker(bind=engine)
    session = Session()

    print(f"🔄 [{datetime.now().strftime('%d/%m/%Y %H:%M')}] Iniciando verificação de preços...")

    # 1. Pega todas as combinações únicas de (Origem, Destino, Data do Voo) gravadas no banco
    rotas_monitoradas = (
        session.query(
            HistoricoPreco.origem, 
            HistoricoPreco.destino, 
            HistoricoPreco.data_voo
        )
        .filter(HistoricoPreco.data_voo.isnot(None))
        .group_by(HistoricoPreco.origem, HistoricoPreco.destino, HistoricoPreco.data_voo)
        .all()
    )

    if not rotas_monitoradas:
        print("ℹ️ Nenhuma rota encontrada no banco para monitorar.")
        session.close()
        return

    for origem, destino, data_voo in rotas_monitoradas:
        # Busca o menor preço gravado historicamente para essa rota e data
        menor_preco_historico = (
            session.query(HistoricoPreco.preco)
            .filter(
                HistoricoPreco.origem == origem,
                HistoricoPreco.destino == destino,
                HistoricoPreco.data_voo == data_voo
            )
            .order_by(HistoricoPreco.preco.asc())
            .first()
        )
        menor_preco_reg = menor_preco_historico[0] if menor_preco_historico else float("inf")

        # Configura a busca na SerpApi
        params = _params_base(origem, data_voo)
        params.update({
            "engine": "google_flights",
            "arrival_id": destino,
            "sort_by": 2,
            "no_cache": "true",
            "api_key": SERPAPI_KEY
        })

        try:
            res = GoogleSearch(params).get_dict()
            voos = []
            for chave in ["best_flights", "other_flights"]:
                for v in res.get(chave, []) or []:
                    if "price" in v:
                        voos.append(v)

            if not voos:
                continue

            # Pega o voo mais barato encontrado agora
            voo_mais_barato = min(voos, key=lambda x: float(x["price"]))
            preco_atual = float(voo_mais_barato["price"])
            
            trechos = voo_mais_barato.get("flights", [])
            companhia = trechos[0].get("airline", "Companhia Aérea") if trechos else "N/A"
            duracao = voo_mais_barato.get("total_duration", 0)
            escalas = max(len(trechos) - 1, 0)

            # Salva a nova busca no banco de dados automaticamente
            salvar_historico_db(
                origem=origem,
                destino=destino,
                preco=preco_atual,
                companhia=companhia,
                duracao=duracao,
                escalas=escalas,
                data_voo=data_voo
            )

            # Se o preço for menor do que o histórico salvo, dispara a notificação no Telegram!
            if preco_atual <= menor_preco_reg:
                msg = (
                    f"✈️ **ALERTA DE PREÇO BAIXO!** ✈️\n\n"
                    f"📍 **Rota:** {origem} ➔ {destino}\n"
                    f"📅 **Data do Voo:** {data_voo.strftime('%d/%m/%Y')}\n"
                    f"💵 **Preço Atual:** R$ {preco_atual:.2f}\n"
                    f"📉 **Menor Preço Anterior:** R$ {menor_preco_reg:.2f}\n"
                    f"🏢 **Companhia:** {companhia}\n\n"
                    f"🔥 *Hora de garantir a sua passagem!*"
                )
                enviar_mensagem_telegram(msg)
            else:
                print(f"ℹ️ {origem} ➔ {destino}: Preço atual R$ {preco_atual:.2f} (sem queda em relação aos R$ {menor_preco_reg:.2f} do histórico).")

        except Exception as erro:
            print(f"❌ Erro ao consultar {origem} -> {destino}: {erro}")

    session.close()
    print("✅ Verificação concluída!")


if __name__ == "__main__":
    executar_verificacao_automatica()