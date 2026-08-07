from sqlalchemy import inspect, text

from database import modelos  # Garante que o SQLAlchemy conheça os modelos.
from database.conexao import Base, engine


def atualizar_colunas():
    """Adiciona colunas ausentes em bancos criados por versões anteriores."""
    novas_colunas = {
        "duracao": "INTEGER",
        "escalas": "INTEGER",
        "data_voo": "DATETIME",
    }

    with engine.begin() as conexao:
        colunas_existentes = {
            coluna["name"]
            for coluna in inspect(conexao).get_columns("historico_precos")
        }

        for nome, tipo in novas_colunas.items():
            if nome not in colunas_existentes:
                conexao.execute(
                    text(
                        f"ALTER TABLE historico_precos "
                        f"ADD COLUMN {nome} {tipo}"
                    )
                )


def inicializar_banco():
    """Cria as tabelas e atualiza a estrutura do banco."""
    Base.metadata.create_all(engine)
    atualizar_colunas()