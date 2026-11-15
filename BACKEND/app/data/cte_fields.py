"""Canonical business fields for SQL rows, plans and messages; raw SQL stays intact."""

from app.data.consulta_reader import parse_decimal, parse_observacao

ALIASES = {
    "vlrTar": "VLR_TAR",
    "vlrTotal": "VLR_TOTAL",
    "freval": "FREVAL",
    "outros": "OUTROS",
    "vlrFretePeso": "VLR_FRETE_PESO",
    "remCidade": "REM_CIDADE",
    "desCidade": "DES_CIDADE",
    "estCol": "ESTCOL",
    "estDes": "ESTDES",
    "veiCodigo": "VEI_CODIGO",
    "data": "DATA",
}
MONEY = {"vlrTar", "vlrTotal", "freval", "outros", "vlrFretePeso"}


def enrich(row):
    result = dict(row)
    sql = row.get("__sql") if isinstance(row.get("__sql"), dict) else {}
    for key, source in ALIASES.items():
        value = row.get(source, sql.get(source))
        if value is None or value == "":
            value = row.get(key)
        if value is not None and value != "":
            result[key] = parse_decimal(value) if key in MONEY else str(value)
    parsed = [
        parse_observacao(value)
        for value in (
            row.get("OBSERVACAO", sql.get("OBSERVACAO")),
            row.get("OBSCON", sql.get("OBSCON")),
            row.get("observacao"),
        )
        if value
    ]
    for key in (
        "observacao",
        "percurso",
        "id",
        "ton",
        "tonRaw",
        "cteOrigem",
        "idTarifarioObservacao",
    ):
        value = next(
            (item[key] for item in parsed if item.get(key) is not None and item.get(key) != ""),
            None,
        )
        if value is not None:
            result[key] = value
    if any(item.get("isCteComplementarFrete") for item in parsed):
        result["isCteComplementarFrete"] = True
    observed = next((item.get("tonRaw") for item in parsed if item.get("tonRaw") is not None), None)
    result["tonObservacaoOriginal"] = (
        observed if observed is not None else row.get("tonObservacaoOriginal", result.get("tonRaw"))
    )
    return result
