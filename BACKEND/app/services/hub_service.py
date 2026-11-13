import asyncio
import json
import re

from app.api.routers.pendentes import _load_plan_rows
from app.data.chamados_reader import read_chamados_payload
from app.domain.models import RunStartRequest
from app.services.hub_views import chamado_view, cte_view, job_views, run_view
from app.services.pending_documents import refresh_files
from app.services.session_audit import operator_session


class HubService:
    def __init__(self, settings, config, store, automation, event_bus, audit=None):
        self.settings, self.config, self.store = settings, config, store
        self.automation, self.event_bus = automation, event_bus
        self.audit = audit

    def ctes(self):
        source = self.settings.backend_root.parent / "captures/pendentes/latest-python.json"
        if source.is_file():
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
        else:
            payload = self.store.local_snapshot("pending_plan") or self.store.snapshot("pending_plan") or {}
        if "checked" not in payload and payload.get("rows"):
            payload = {**payload, "checked": [{"cte": row["cte"], "row": row} for row in payload["rows"]]}
        if "checked" in payload:
            payload = refresh_files(payload, self.config, self.settings.backend_root.parent)
            meta, rows = _load_plan_rows(self.settings, payload)
            self.store.local_snapshot("pending_plan", {**payload, **meta, "rows": rows})
        else:
            meta, _ = _load_plan_rows(self.settings, payload)
            rows = payload.get("rows", [])
        result = [cte_view(row) for row in rows]
        if payload.get("checked"):
            indexed = {item["cte"]: item.get("row", {}) for item in payload.get("checked", [])}
            for item in result:
                raw = indexed.get(item["id"], {})
                item["chave"] = str(raw.get("cteId") or raw.get("CTE_ID") or "").removeprefix("CTe")
                for target, candidates in {"origem": ["origem"], "destino": ["destino"],
                                           "remetente": ["remetente"], "destinatario": ["destinatario"]}.items():
                    item[target] = next((str(raw[key]) for key in candidates if raw.get(key)), "")
        return result

    def chamados(self):
        config = self.config.novelis()
        payload = read_chamados_payload(self.settings.backend_root.parent, config.get("relatorioCteXmlJsonFile"))
        if payload.get("sourceFile"):
            self.store.snapshot("chamados", payload)
        else:
            payload = self.store.snapshot("chamados") or payload
        return [chamado_view(row) for row in payload.get("rows", [])]

    async def run(self):
        snapshot = (await self.automation.current()).model_dump(mode="json")
        events = await asyncio.to_thread(self.store.events, snapshot["id"])
        return run_view(snapshot, events)

    async def start(self, flow: str, ctes: list[str], days: int, session_id: str | None = None):
        known = {"completo", "documentos", "somente_pdf", "somente_xml", "somente_chamados", "consulta"}
        if flow not in known:
            raise ValueError("Fluxo nao suportado.")
        if any(not re.fullmatch(r"[0-9]{1,3}-[0-9]{1,3}-[0-9]{1,9}", value)
               or int(value.split("-")[0]) < 1 or int(value.split("-")[2]) < 1 for value in ctes):
            raise ValueError("CT-e invalido. Use filial-serie-numero em todos os itens.")
        ctes = list(dict.fromkeys("-".join(str(int(part)) for part in cte.split("-")) for cte in ctes))
        selected = {"somente_chamados": "chamado-novelis",
                    "consulta": "consulta-pendentes"}.get(flow, "pendentes")
        scope = {"somente_pdf": "pdf", "somente_xml": "xml", "documentos": "documents"}.get(flow, "full")
        request = RunStartRequest(flow=selected, dry_run=False, manual_ctes="\n".join(ctes),
                                  sample_cte=",".join(ctes) if selected != "pendentes" else "",
                                  pendentes_sql_days_back=days, execution_scope=scope)
        if session_id and self.audit and not await asyncio.to_thread(self.audit.session, session_id):
            raise ValueError("Sessao encerrada. Entre novamente com o nome do operador.")
        token = operator_session.set(session_id)
        try:
            await self.automation.start(request)
        finally:
            operator_session.reset(token)
        return await self.run()

    async def overview(self):
        rows = await asyncio.to_thread(self.ctes)
        meta = await asyncio.to_thread(self.store.local_snapshot, "pending_plan") or {}
        return {"naFila": len(rows), "pdfFaltando": sum(row["pdf"] == "faltando" for row in rows),
                "xmlFaltando": sum(row["xml"] == "faltando" for row in rows),
                "comprovanteFaltando": sum(row["comprovante"] == "faltando" for row in rows),
                "prontosChamado": sum(row["prontoChamado"] for row in rows), "ultimaAtualizacao": meta.get("generatedAt", ""),
                "execucao": await self.run()}

    def jobs(self):
        return job_views(self.store.events(limit=1000))

    def logs(self, since: str | None):
        levels = {"warn": "aviso", "error": "erro", "info": "info", "debug": "debug"}
        return [{"id": str(event["id"]), "time": event["created_at"],
                 "severity": levels[event["level"]], "source": event["kind"], "message": event["message"],
                 "details": json.dumps(event.get("payload", {}), ensure_ascii=False)}
                for event in self.store.events(limit=500) if not since or event["id"] > int(since)]

    def config_groups(self):
        labels = {"XML_SEFAZ_CERTIFICATE_CNPJ": "CNPJ do certificado (14 digitos)",
                  "XML_SEFAZ_CERTIFICATE_THUMBPRINT": "Impressao digital (opcional, para desempate)"}
        groups = [{"id": "banco", "titulo": "Banco operacional SQLite", "fields": [
            {"key": "NOVELIS_SQLITE_PATH", "label": "Arquivo compartilhado", "value": str(self.store.path),
             "readOnly": True, "hint": "Backend local com transacoes coordenadas entre computadores"}]}]
        if self.audit:
            groups[0]["fields"].append({"key": "LOGIN_AUDIT_DB_PATH", "label": "Logs de sessoes e automacao",
                                        "value": str(self.audit.shared_path), "readOnly": True})
        for group, title, keys in [
            ("documentos", "Geracao de documentos", ["CRYSTAL_PDF_ENGINE", "CRYSTAL_QR_PROVIDER"]),
            ("caminhos", "Pastas de documentos", ["RODOPAR_PDF_DOWNLOAD_TARGET_DIR", "XML_SEFAZ_DOWNLOAD_DIR"]),
            ("automacoes", "Automacao", ["PENDENTES_STOP_ON_ERROR"]),
            ("sefaz", "SEFAZ · certificado instalado no Windows", ["XML_SEFAZ_CERTIFICATE_CNPJ", "XML_SEFAZ_CERTIFICATE_THUMBPRINT"]),
        ]:
            groups.append({"id": group, "titulo": title, "fields": [
                {"key": key, "label": labels.get(key, key), "value": self.config.get(key)} for key in keys]})
        return groups

    def save_config(self, groups):
        allowed = {field["key"] for group in self.config_groups() for field in group["fields"]
                   if not field.get("readOnly")}
        values = {field["key"]: field["value"] for group in groups for field in group["fields"]
                  if field["key"] in allowed}
        if values.get("CRYSTAL_PDF_ENGINE", "windows") not in {"windows", "native"}:
            raise ValueError("Mecanismo PDF invalido.")
        if values.get("CRYSTAL_QR_PROVIDER", "python") not in {"python", "report"}:
            raise ValueError("Gerador QR invalido.")
        cnpj = re.sub(r"\D", "", values.get("XML_SEFAZ_CERTIFICATE_CNPJ", ""))
        if cnpj and len(cnpj) != 14:
            raise ValueError("CNPJ do certificado deve ter 14 digitos.")
        thumb = values.get("XML_SEFAZ_CERTIFICATE_THUMBPRINT", "").replace(" ", "").upper()
        if thumb and not re.fullmatch(r"[A-F0-9]{40}", thumb):
            raise ValueError("Impressao digital do certificado deve ter 40 caracteres hexadecimais.")
        if "XML_SEFAZ_CERTIFICATE_CNPJ" in values:
            values["XML_SEFAZ_CERTIFICATE_CNPJ"] = cnpj
        if "XML_SEFAZ_CERTIFICATE_THUMBPRINT" in values:
            values["XML_SEFAZ_CERTIFICATE_THUMBPRINT"] = thumb
        self.config.values.update(self.store.preferences(values))

    def database_health(self):
        from app.services.sefaz_certificate import configure_certificate

        health = self.store.health()
        result = [{"id": "sqlite", "grupo": "Persistencia", "nome": "SQLite compartilhado", "status": "ok",
                   "detalhe": f"{health['path']} · journal={health['journal_mode']} · schema={health['schema_version']}"}]
        status, detail = "aviso", "Selecao manual; informe o CNPJ nas configuracoes SEFAZ para selecionar automaticamente."
        try:
            cert = configure_certificate({"certificateCnpj": self.config.get("XML_SEFAZ_CERTIFICATE_CNPJ"),
                                          "certificateThumbprint": self.config.get("XML_SEFAZ_CERTIFICATE_THUMBPRINT")})
            if cert:
                status, detail = "ok", f"{cert['subjectCN']} · valido ate {cert['notAfter'][:10]} · chave no Windows"
        except (OSError, ValueError, RuntimeError) as exc:
            status, detail = "erro", str(exc)
        result.append({"id": "sefaz-cert", "grupo": "SEFAZ", "nome": "Certificado instalado", "status": status, "detalhe": detail})
        return result
