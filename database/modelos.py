from datetime import datetime

from sqlalchemy import Column, DateTime, Float, Integer, String

from database.conexao import Base


class HistoricoPreco(Base):
    """Representa um preço salvo no histórico de monitoramento."""

    __tablename__ = "historico_precos"

    id = Column(Integer, primary_key=True, autoincrement=True)
    origem = Column(String(10), nullable=False)
    destino = Column(String(10), nullable=False)
    preco = Column(Float, nullable=False)
    companhia = Column(String(100), nullable=True)
    duracao = Column(Integer, nullable=True)
    escalas = Column(Integer, nullable=True)
    data_voo = Column(DateTime, nullable=True)
    data_consulta = Column(DateTime, default=datetime.now)