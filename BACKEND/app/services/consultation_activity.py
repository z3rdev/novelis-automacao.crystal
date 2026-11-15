"""Keep data queries, portal report checks and filesystem checks visibly distinct."""


def activity(kind, payload):
    source = payload.get("querySource")
    if kind.startswith(("pendentes.sql", "pendentes.manual_sql")):
        source = "sql"
    elif kind.startswith(("novelis_relatorio.", "pendentes.novelis_relatorio")):
        source = "novelis"
    elif kind in {"pendentes.plan", "pendentes.files_check"}:
        source = "arquivos"
    return {"sql": "SQL Server", "novelis": "Relatório Novelis", "arquivos": "Arquivos"}.get(source)


def finished(kind):
    return kind in {
        "pendentes.plan",
        "novelis_relatorio.filtered",
        "pendentes.novelis_relatorio_final",
    }
