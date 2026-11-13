"""Translate existing operational data to the Cargo Hub presentation contract."""

from hashlib import sha256

STAGES = ["consulta", "pdf", "xml", "comprovantes", "chamados"]
RUN_STATES = {"idle": "aguardando", "running": "executando", "stopping": "parando",
              "completed": "concluida", "failed": "falhou", "cancelled": "cancelada"}


def number(value):
    try:
        return float(value or 0)
    except (ValueError, TypeError):
        return 0


def cte_view(row: dict) -> dict:
    return {"id": row["cte"], "filial": int(number(row["filial"])),
            "serie": int(number(row["serie"])), "numero": int(number(row["documento"])),
            "chave": "", "emissao": "", "valor": None, "remetente": "", "destinatario": "",
            "origem": "", "destino": "", "pdf": "faltando" if row["faltaPdf"] else "disponivel",
            "xml": "faltando" if row["faltaXml"] else "disponivel",
            "comprovante": row["comprovanteStatus"].replace("ok", "disponivel").replace("falta", "faltando"),
            "prontoChamado": row["prontoChamado"], "historico": []}


def chamado_view(row: dict) -> dict:
    status = str(row.get("aberturaNovelis") or row.get("andamento") or "").upper()
    andamento = ("solucionado" if "SOLUCION" in status else "falhou" if "ERRO" in status
                 else "em_analise" if "ANAL" in status else "aberto" if row.get("chamado") else "na_fila")
    return {"cte": row.get("cte", ""), "data": row.get("dataSort") or row.get("data") or "",
            "valorTotal": number(row["vlrTotal"]) if row.get("vlrTotal") is not None else None,
            "aberturaNovelis": row.get("aberturaNovelis"),
            "idTarifario": str(row.get("idTarifario") or ""), "chamado": row.get("chamado"),
            "jda": row.get("jda"), "andamento": andamento, "responsavel": row.get("responsavel", ""),
            "origem": row.get("origem", ""), "destino": row.get("destino", "")}


def run_view(snapshot: dict, events: list[dict]) -> dict:
    stages = {key: {"id": key, "state": "aguardando", "done": 0, "total": 0} for key in STAGES}
    current = None
    cte = None
    flow = {"pendentes": "completo", "xml-sefaz": "somente_xml", "chamado-novelis": "somente_chamados",
            "consulta-pendentes": "consulta", "consulta": "consulta"}.get(snapshot["flow"], "completo")
    for event in events:
        kind, payload = event.get("kind", ""), event.get("payload", {})
        if kind == "run.started":
            scope = payload.get("execution_scope", "full")
            flow = {"pdf": "somente_pdf", "xml": "somente_xml", "documents": "documentos"}.get(scope, flow)
        key = ("pdf" if kind.startswith("crystal_pdf.") else "xml" if kind.startswith(("xml_sefaz.", "pendentes.xml_"))
               else "comprovantes" if kind.startswith("comprovante_local.")
               else "chamados" if kind.startswith("chamado_novelis.")
               else "consulta" if kind.startswith(("pendentes.sql", "pendentes.plan", "pendentes.manual", "consulta.")) else None)
        if not key:
            continue
        if key != "consulta" and stages["consulta"]["state"] == "executando":
            stages["consulta"].update(state="concluida", done=stages["consulta"]["total"])
        current = key
        stage = stages[key]
        stage["state"] = "falhou" if event.get("level") == "error" or kind.endswith(".error") else "executando"
        if kind in {"pendentes.xml_skip", "crystal_pdf.skip"}:
            stage["state"] = "concluida"
            stage["detalhe"] = event.get("message", "Documentos ja disponiveis.")
            stage["reaproveitados"] = payload.get("available", 0)
        if payload.get("total"):
            stage["total"] = int(payload["total"])
        if payload.get("current"):
            stage["done"] = max(0, int(payload["current"]) - 1)
        if kind.endswith((".saved", ".reused")):
            stage["done"] += 1
            if stage["total"] and stage["done"] >= stage["total"]:
                stage["state"] = "concluida"
        cte = payload.get("cte") or cte
        if cte:
            stage["atual"] = cte
    allowed = {"consulta": {"consulta"}, "somente_pdf": {"consulta", "pdf"}, "somente_xml": {"consulta", "xml"},
               "somente_chamados": {"chamados"}, "documentos": set(STAGES) - {"chamados"}}.get(flow, set(STAGES))
    for key, stage in stages.items():
        if key not in allowed:
            stage["state"] = "ignorada"
        elif snapshot["status"] == "completed":
            stage["state"] = "concluida"
            stage["done"] = stage["total"]
        elif snapshot["status"] == "cancelled" and stage["state"] not in {"concluida", "falhou"}:
            stage["state"] = "cancelada"
        elif snapshot["status"] == "stopping" and stage["state"] == "executando":
            stage["state"] = "parando"
        elif snapshot["status"] == "failed" and stage["state"] == "executando":
            stage["state"] = "falhou"
    stage = stages[current] if current else stages["consulta"]
    return {"id": snapshot["id"] if snapshot["status"] != "idle" else None,
            "flow": flow if snapshot["status"] != "idle" else None, "state": RUN_STATES[snapshot["status"]],
            "etapaAtual": current, "cteAtual": cte, "processados": stage["done"], "total": stage["total"],
            "iniciadoEm": snapshot.get("started_at"), "stages": list(stages.values())}


def job_views(events: list[dict]) -> list[dict]:
    jobs = {}
    stopped = {}
    for event in events:
        kind, payload = event.get("kind", ""), event.get("payload", {})
        if kind in {"run.stop_requested", "run.cancelled", "run.failed"} and (
            kind != "run.stop_requested" or event.get("run_id") not in stopped
        ):
            stopped[event.get("run_id")] = {"run.stop_requested": "parando", "run.cancelled": "cancelada",
                                             "run.failed": "falhou"}[kind]
        if not kind.startswith("crystal_pdf.") or not payload.get("cte"):
            continue
        key = (event.get("run_id"), payload["cte"])
        identifier = sha256(f"{key[0]}:{key[1]}".encode()).hexdigest()[:24]
        job = jobs.setdefault(key, {"id": identifier, "cte": payload["cte"], "metodo": "crystal", "state": "executando",
                                    "etapa": "Gerando PDF", "qrCode": "pendente", "codigoBarras": "pendente"})
        if kind == "crystal_pdf.saved":
            job.update(state="concluida", etapa="Arquivo salvo e codigos conferidos", arquivo=payload["pdfFile"],
                       qrCode="ok", codigoBarras="ok", geradoEm=event["created_at"])
        elif kind == "crystal_pdf.error":
            job.update(state="falhou", etapa="Falha na geracao", erro=payload.get("error", event["message"]))
    for (run_id, _cte), job in jobs.items():
        if run_id in stopped and job["state"] == "executando":
            job.update(state=stopped[run_id], etapa="Execucao interrompida")
    return list(reversed(list(jobs.values())))
