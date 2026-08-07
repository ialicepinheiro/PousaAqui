import pandas as pd


def formatar_duracao(minutos):
    """Transforma minutos em horas e minutos."""
    try:
        minutos = int(minutos)
    except (TypeError, ValueError):
        return "N/A"

    horas, minutos_restantes = divmod(minutos, 60)
    if horas and minutos_restantes:
        return f"{horas}h {minutos_restantes:02d}min"
    return f"{horas}h" if horas else f"{minutos_restantes}min"


def formatar_preco(valor):
    """Formata um valor como preço em reais."""
    if valor is None or pd.isna(valor):
        return "N/A"
    return f"R$ {float(valor):,.0f}".replace(",", ".")


def formatar_escalas(escalas):
    """Transforma a quantidade de escalas em texto."""
    if escalas is None or pd.isna(escalas):
        return "N/A"

    quantidade = int(escalas)
    if quantidade == 0:
        return "Sem escalas"
    if quantidade == 1:
        return "1 escala"
    return f"{quantidade} escalas"