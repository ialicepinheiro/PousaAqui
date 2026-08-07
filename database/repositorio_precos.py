from datetime import date, datetime

import pandas as pd

from database.conexao import SessionLocal
from database.modelos import HistoricoPreco


def converter_data_voo(data_voo):
    """Converte date em datetime para armazenamento no banco."""
    if (
        data_voo
        and isinstance(data_voo, date)
        and not isinstance(data_voo, datetime)
    ):
        return datetime.combine(data_voo, datetime.min.time())
    return data_voo


def salvar_historico(
    origem,
    destino,
    preco,
    companhia,
    duracao=None,
    escalas=None,
    data_voo=None,
):
    """Salva um voo e retorna False quando o registro já existe."""
    data_voo = converter_data_voo(data_voo)

    with SessionLocal() as session:
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

        try:
            session.add(registro)
            session.commit()
            return True
        except Exception:
            session.rollback()
            raise


def carregar_historico():
    """Carrega o histórico completo como DataFrame."""
    with SessionLocal() as session:
        registros = session.query(HistoricoPreco).order_by(
            HistoricoPreco.data_consulta.asc()
        ).all()

        dados = [
            {
                "Data Consulta": registro.data_consulta,
                "Data Voo": registro.data_voo,
                "Origem": registro.origem,
                "Destino": registro.destino,
                "Preco": registro.preco,
                "Companhia": registro.companhia,
                "Duracao": registro.duracao,
                "Escalas": registro.escalas,
            }
            for registro in registros
        ]

    return pd.DataFrame(dados)