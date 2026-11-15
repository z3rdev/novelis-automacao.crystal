"""Compare the original observation and SQL amounts against a uniquely identified contract."""

import re
import time

from app.data.cte_fields import enrich
from app.infrastructure.chamados_postgres import CommunicationUnavailable
from app.infrastructure.pending_queue import identity
from app.infrastructure.tariffs_postgres import TariffsPostgres

from .models import day, decimal
from .municipalities import city

CENT = decimal("0.01")


def route(row):
    def name(uf, town):
        town = str(town or "").strip()
        return (
            city(town if re.match(r"^[A-Z]{2}\s*-", town, re.IGNORECASE) else f"{uf}-{town}")[
                "label"
            ]
            if uf and town
            else ""
        )

    return (
        name(row.get("estCol"), row.get("remCidade") or row.get("origem")),
        name(row.get("estDes"), row.get("desCidade") or row.get("destino")),
    )


def issued(row):
    value = str(row.get("data") or row.get("dataBR") or "")
    return day(value[:10])


def close(a, b):
    return None if a is None or b is None else a.quantize(CENT) == b.quantize(CENT)


def candidate(value):
    return {
        key: value.get(key)
        for key in (
            "id",
            "idTarifa",
            "idRota",
            "origem",
            "destino",
            "tarifaTon",
            "valorTotal",
            "capacidadeTon",
            "veiculo",
            "operacao",
            "faturamento",
            "inicio",
            "fim",
        )
    }


def choose(row, values):
    ton = decimal(row.get("tonObservacaoOriginal"))
    if ton is not None:
        matching = [v for v in values if decimal(v.get("capacidadeTon")) == ton]
        if not matching:
            return None, "ton_sem_correspondencia"
        latest_id = max(int(v["idTarifa"]) for v in matching)
        latest = [v for v in matching if int(v["idTarifa"]) == latest_id]
        return (
            (latest[0], "maior_id_mesma_ton") if len(latest) == 1 else (None, "maior_id_duplicado")
        )
    explicit = row.get("idTarifarioObservacao")
    if explicit:
        exact = [v for v in values if v["idTarifa"] == explicit]
        return (exact[0], "id_observacao") if len(exact) == 1 else (None, "id_nao_confirmado")
    if len(values) == 1:
        return values[0], "rota_e_vigencia"
    freight = decimal(row.get("vlrTar"))
    value_matches = [
        v for v in values if freight is not None and close(decimal(v.get("valorTotal")), freight)
    ]
    if len(value_matches) == 1:
        return value_matches[0], "frete_sql"
    return None, "mais_de_uma_tarifa"


def check(row, values, catalog=None):
    row = enrich(row)
    origin, destination = route(row)
    date = issued(row)
    ton, freight = decimal(row.get("tonObservacaoOriginal")), decimal(row.get("vlrTar"))
    other, insurance, total = (decimal(row.get(k)) for k in ("outros", "freval", "vlrTotal"))
    result = {
        "status": "dados_incompletos",
        "origem": origin,
        "destino": destination,
        "dataReferencia": date.isoformat() if date else None,
        "tonObservacao": str(ton) if ton is not None else None,
        "freteSql": str(freight) if freight is not None else None,
        "outrosSql": str(other) if other is not None else None,
        "frevalSql": str(insurance) if insurance is not None else None,
        "totalSql": str(total) if total is not None else None,
        "selecionada": None,
        "tonConfere": None,
        "freteConfere": None,
        "composicaoConfere": None,
        "diferencaFrete": None,
        "diferencaTotal": None,
        "alertas": [],
        "candidatos": [],
        "totalCandidatos": 0,
        "catalogoAtualizadoEm": (catalog or {}).get("completed_at"),
        "catalogoStatus": (catalog or {}).get("state"),
    }
    result.update(
        idObservacao=row.get("id"), percursoObservacao=row.get("percurso"), totalReferencia=None
    )
    if not origin or not destination or not date:
        result["alertas"].append("Origem, destino/UF ou data de emissão não informados.")
        return result
    key = re.sub(r"\D", "", str(row.get("cteId") or row.get("CTE_ID") or ""))
    company = key[6:14] if len(key) == 44 else ""
    eligible = [
        v
        for v in values
        if v.get("origem") == origin
        and v.get("destino") == destination
        and v["vigenciaValida"]
        and day(v["inicio"]) <= date
        and (not v["fim"] or day(v["fim"]) >= date)
        and (not company or re.sub(r"\D", "", v.get("faturamento") or "")[:8] == company)
    ]
    result.update(candidatos=[candidate(v) for v in eligible[:12]], totalCandidatos=len(eligible))
    if not eligible:
        result.update(
            status="sem_tarifa",
            alertas=["Nenhuma tarifa da empresa para a rota na data de emissão."],
        )
        return result
    selected, criterion = choose(row, eligible)
    result["criterio"] = criterion
    if selected is None:
        result.update(
            status="sem_tarifa" if criterion == "ton_sem_correspondencia" else "ambiguo",
            alertas=[
                "Nenhuma tarifa elegível com a TON da observação."
                if criterion == "ton_sem_correspondencia"
                else "Mais de uma tarifa possível ou ID da observação não confirmado. Confira o contrato."
            ],
        )
        return result
    result["selecionada"] = candidate(selected)
    explicit = row.get("idTarifarioObservacao")
    id_conflict = bool(explicit and explicit != selected["idTarifa"])
    if id_conflict:
        result["alertas"].append(
            "ID tarifário da observação difere do maior ID elegível com a mesma TON."
        )
    expected = decimal(selected.get("valorTotal"))
    capacity = decimal(selected.get("capacidadeTon"))
    result["tonConfere"] = None if ton is None or capacity is None else ton == capacity
    result["freteConfere"] = close(freight, expected)
    if freight is not None and expected is not None:
        result["diferencaFrete"] = str((freight - expected).quantize(CENT))
    if all(value is not None for value in (freight, other, insurance, total)):
        result["composicaoConfere"] = close(total, freight + other + insurance)
        if expected is not None:
            result["totalReferencia"] = str((expected + other + insurance).quantize(CENT))
            result["diferencaTotal"] = str((total - expected - other - insurance).quantize(CENT))
    for label, key in (
        ("TON da observação", "tonConfere"),
        ("Frete SQL", "freteConfere"),
        ("Composição do total SQL", "composicaoConfere"),
    ):
        if result[key] is False:
            result["alertas"].append(label + " diverge da referência.")
        elif result[key] is None:
            result["alertas"].append(label + " não informado para conferência.")
    result["status"] = (
        "divergente"
        if id_conflict
        or any(result[k] is False for k in ("tonConfere", "freteConfere", "composicaoConfere"))
        else "conferido"
        if not result["alertas"]
        else "dados_incompletos"
    )
    return result


class TariffAuditService:
    def __init__(self, config, repository=None):
        self.repository = repository or TariffsPostgres(config if hasattr(config, "get") else None)
        self._signature, self._loaded, self._values, self._catalog = None, 0, [], {}

    def rows(self, rows):
        values = [enrich(row) for row in rows]
        routes = sorted({route(row) for row in values if all(route(row))})
        dates = sorted({issued(row) for row in values if issued(row)})
        signature = (tuple(routes), tuple(dates))
        if self.repository.enabled and routes and dates:
            try:
                if signature != self._signature or time.monotonic() - self._loaded > 30:
                    self._values, self._catalog = self.repository.audit_snapshot(
                        routes, dates[0], dates[-1]
                    )
                    self._signature, self._loaded = signature, time.monotonic()
            except CommunicationUnavailable:
                return {
                    identity(row): {
                        **check(row, []),
                        "status": "indisponivel",
                        "alertas": ["Catálogo de tarifas indisponível para conferência."],
                    }
                    for row in values
                }
        elif not self.repository.enabled:
            return {
                identity(row): {
                    **check(row, []),
                    "status": "indisponivel",
                    "alertas": ["Catálogo de tarifas não configurado."],
                }
                for row in values
            }
        return {identity(row): check(row, self._values, self._catalog) for row in values}


def message_fields(row, audit):
    result = enrich(row)
    if (row.get("tariffAudit") or {}).get("selecionada"):
        # A new ambiguous/unavailable check cannot silently reuse an old match.
        result["idTarifario"] = result.get("idTarifarioObservacao")
        result["ton"], result["tonRaw"] = (
            result.get("tonObservacaoOriginal"),
            result.get("tonObservacaoOriginal"),
        )
    result["tariffAudit"] = audit
    if selected := (audit or {}).get("selecionada"):
        result["idTarifario"] = selected["idTarifa"]
        result["tonTarifario"] = selected["capacidadeTon"]
        if selected["capacidadeTon"] is not None:
            result["ton"], result["tonRaw"] = selected["capacidadeTon"], selected["capacidadeTon"]
    return result


def annotate_plan(plan, config):
    rows = [item["row"] for item in plan.get("checked", [])]
    audits = TariffAuditService(config).rows(rows)
    for item in plan.get("checked", []):
        item["row"] = message_fields(item["row"], audits.get(identity(item["row"])))
    plan["rows"] = [item["row"] for item in plan.get("checked", [])]
    return plan
