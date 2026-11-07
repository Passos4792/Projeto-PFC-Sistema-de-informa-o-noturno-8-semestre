
from calendar import monthrange
from datetime import date, timedelta


def limites_periodo(periodo, referencia):
    if periodo == 'SEMANAL':
        inicio = referencia - timedelta(days=referencia.weekday())
        return inicio, inicio + timedelta(days=6)
    meses = {'MENSAL': 1, 'TRIMESTRAL': 3, 'SEMESTRAL': 6}
    if periodo not in meses:
        raise ValueError('Período inválido.')
    tamanho = meses[periodo]
    mes = ((referencia.month - 1) // tamanho) * tamanho + 1
    ultimo = mes + tamanho - 1
    return date(referencia.year, mes, 1), date(referencia.year, ultimo, monthrange(referencia.year, ultimo)[1])
