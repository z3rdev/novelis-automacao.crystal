"""Translate existing operational data to the Cargo Hub presentation contract."""

from hashlib import sha256
from unicodedata import normalize

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


def chamado_status(row: dict) -> str:
    # The old "aberturaNovelis=SOLUCIONADO" means a ticket exists, not that it is closed.
    status = normalize("NFKD", str(row.get("andamento") or row.get("aberturaNovelis") or "")).encode("ascii", "ignore").decode().upper()
    if any(word in status for word in ("SOLUCION", "ENCERR", "CONCLU")):
        return "solucionado"
    if "ERRO" in status or "FALH" in status:
        return "falhou"
    if "ANAL" in status or "PEND" in status and row.get("chamado"):
        return "em_analise"
    return "aberto" if row.get("chamado") else "na_fila"


def chamado_view(row: dict) -> dict:
    andamento = chamado_status(row)
    opened = row.get("abertoEm")
    if not opened and str(row.get("aberturaNovelis") or "")[:4].isdigit():
        opened = row["aberturaNovelis"]
    return {"cte": row.get("cte", ""), "data": row.get("dataSort") or row.get("data") or "",
            "valorTotal": number(row["vlrTotal"]) if row.get("vlrTotal") is not None else None,
            "aberturaNovelis": opened,
            "idTarifario": str(row.get("idTarifario") or ""), "chamado": row.get("chamado"),
            "jda": row.get("jda"), "andamento": andamento, "responsavel": row.get("responsavel", ""),
            "origem": row.get("origem", ""), "destino": row.get("destino", "")}


def run_view(snapshot: dict, events: list[dict]) -> dict:
    from app.services.consultation_activity import activity, finished
    stages = {key: {"id": key, "state": "aguardando", "done": 0, "total": 0} for key in STAGES}
    current = None
    workflow_stages = None
    cte = None
    xml_failures, xml_saved = {}, set()
    xml_batch_done = None
    flow = {"pendentes": "completo", "xml-sefaz": "somente_xml", "chamado-novelis": "somente_chamados", "chamado-http": "somente_chamados",
            "consulta-pendentes": "consulta", "consulta": "consulta"}.get(snapshot["flow"], "completo")
    for event in events:
        kind, payload = event.get("kind", ""), event.get("payload", {})
        if kind == "run.started":
            if snapshot["flow"] == "workflow":
                from app.domain.scheduled_workflow import NODE_STAGES
                flow = "personalizado"
                workflow_stages = {NODE_STAGES[node["kind"]] for node in (payload.get("workflow") or {}).get("nodes", [])}
            scope = payload.get("execution_scope", "full")
            flow = {"pdf": "somente_pdf", "xml": "somente_xml", "comprovantes": "somente_comprovantes", "chamados": "somente_chamados", "documents": "documentos"}.get(scope, flow)
        key = (payload.get("stage") if kind.startswith("workflow.node.") else "pdf" if kind.startswith("crystal_pdf.") else "xml" if kind.startswith(("xml_sefaz.", "pendentes.xml_"))
               else "comprovantes" if kind.startswith("comprovante_local.")
               else "chamados" if kind.startswith(("chamado_novelis.", "novelis."))
               else "consulta" if activity(kind, payload) or kind.startswith(("pendentes.manual", "consulta.")) else None)
        if not key:
            continue
        if key != "consulta" and stages["consulta"]["state"] == "executando":
            stages["consulta"].update(state="concluida", done=stages["consulta"]["total"])
        current = key
        stage = stages[key]
        if key == "xml":
            if kind == "xml_sefaz.error":
                xml_failures[payload.get("cte") or "xml"] = event.get("message", "")
            elif kind == "xml_sefaz.batch_failed":
                for failed_cte in payload.get("failedCtes", ["xml"]):
                    xml_failures.setdefault(failed_cte, event.get("message", ""))
                xml_batch_done = int(payload.get("done", 0))
            elif kind in {"xml_sefaz.saved", "xml_sefaz.reused"} and payload.get("cte"):
                xml_saved.add(payload["cte"])
                xml_failures.pop(payload["cte"], None)
        stage["state"] = "falhou" if event.get("level") == "error" or kind.endswith(".error") else "executando"
        if kind == "workflow.node.completed":
            stage["state"] = "concluida"
            stage["done"] = stage["total"]
        if kind.startswith("workflow.node."):
            stage["detalhe"] = event.get("message", "")
        if label := activity(kind, payload):
            if label != stage.get("atividade"):
                stage.update(done=0, total=0)
            stage.update(atividade=label, detalhe=event.get("message", ""))
        if finished(kind):
            stage["state"] = "concluida"
        if kind in {"pendentes.xml_skip", "crystal_pdf.skip"}:
            stage["state"] = "concluida"
            stage["detalhe"] = event.get("message", "Documentos ja disponiveis.")
            stage["reaproveitados"] = payload.get("available", 0)
        if payload.get("total") is not None:
            stage["total"] = int(payload["total"])
        if payload.get("current"):
            stage["done"] = max(0, int(payload["current"]) - 1)
        if kind.endswith((".saved", ".reused")) or kind in {"novelis.save", "novelis.chamado_exists"}:
            stage["done"] += 1
            if stage["total"] and stage["done"] >= stage["total"]:
                stage["state"] = "concluida"
        cte = payload.get("cte") or cte
        if cte:
            stage["atual"] = cte
        if finished(kind):
            stage["done"] = stage["total"]
        if key == "xml" and payload.get("done") is not None:
            stage["done"] = int(payload["done"])
        if kind == "xml_sefaz.batch_completed":
            stage["state"] = "concluida"
        if key == "xml" and xml_failures:
            stage.update(state="falhou", done=xml_batch_done if xml_batch_done is not None else len(xml_saved),
                         detalhe=next(iter(xml_failures.values())), atual=next(iter(xml_failures)))
    if snapshot["flow"] == "buscar-chamados":
        flow = "buscar_chamados"
    allowed = {"consulta": {"consulta"}, "somente_pdf": {"consulta", "pdf"}, "somente_xml": {"consulta", "xml"},
               "somente_comprovantes": {"consulta", "comprovantes"}, "buscar_chamados": {"consulta"},
               "somente_chamados": {"consulta", "chamados"}, "documentos": set(STAGES) - {"chamados"}}.get(flow, set(STAGES))
    if workflow_stages is not None:
        allowed = workflow_stages
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
    if snapshot["status"] == "failed" and xml_failures:
        current, cte = "xml", next(iter(xml_failures))
    stage = stages[current] if current else stages["consulta"]
    result = {"id": snapshot["id"] if snapshot["status"] != "idle" else None,
            "flow": flow if snapshot["status"] != "idle" else None, "state": RUN_STATES[snapshot["status"]],
            "etapaAtual": current, "cteAtual": cte, "processados": stage["done"], "total": stage["total"],
            "iniciadoEm": snapshot.get("started_at"), "finalizadoEm": snapshot.get("finished_at"), "stages": list(stages.values())}
    if snapshot["flow"] == "workflow":
        from app.services.workflow_view import workflow_view
        result["flow"] = "personalizado"
        result["workflow"] = workflow_view(snapshot, events)
    return result


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
