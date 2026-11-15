from datetime import date, timedelta


def validate_period(start: date | None, end: date | None, *, today: date | None = None):
    if (start is None) != (end is None):
        raise ValueError("Informe a data inicial e a data final.")
    if start is None:
        return
    today = today or date.today()
    if start > end:
        raise ValueError("A data inicial deve ser anterior ou igual à final.")
    if start < today - timedelta(days=30) or end > today:
        raise ValueError("Consulte apenas datas entre hoje e 30 dias atrás.")
