"""Plain text templates: no expressions, attributes or executable formatting."""
from string import Formatter

DEFAULT_MESSAGE = """PREZADOS,

SEGUE O CTE, ACOMPANHADO DO XML E DO TARIFARIO CORRESPONDENTE.

PERCURSO {percurso}
TON: {ton}
ID: {id}
ID TARIFARIO: {idTarifario}
ROTA: {rota}
N DO CTE: {cte}

Att,
{assinatura}"""
DEFAULT_COMPLEMENT = DEFAULT_MESSAGE.replace("SEGUE O CTE,", "SEGUE O CTE COMPLEMENTAR,").replace(
    "\n\nAtt,", "\nN CTE DE ORIGEM: {cteOrigem}\nN DO CHAMADO: {chamadoOrigem}\n\nAtt,")
FIELDS = {"cte", "percurso", "ton", "id", "idTarifario", "rota", "cteOrigem", "chamadoOrigem", "assinatura"}


def validate_template(value: str):
    if not value.strip() or len(value) > 10000:
        raise ValueError("Informe uma mensagem com até 10 mil caracteres.")
    for _, field, spec, conversion in Formatter().parse(value):
        if field is not None and (field not in FIELDS or spec or conversion):
            raise ValueError("Variável de mensagem inválida. Use apenas os campos apresentados na tela.")


def render_message(data: dict, signature: str, template: str) -> str:
    validate_template(template)
    values = {field: str(data.get(field) or "") for field in FIELDS}
    values.update(cte="-".join(str(data.get(key) or "") for key in ("filial", "serie", "documento") if data.get(key)),
        rota=str(data.get("rota") or f"{data.get('remCidade', '')} x {data.get('desCidade', '')}".strip()),
        ton=str(data.get("ton") or data.get("tonRaw") or ""), assinatura=signature)
    return template.format_map(values)
