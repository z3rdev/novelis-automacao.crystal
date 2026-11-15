import asyncio
import json
import re
from copy import deepcopy
from threading import Lock

from app.data.chamados_reader import read_chamados_payload
from app.domain.models import RunStartRequest
from app.services.hub_views import chamado_view, job_views, run_view
from app.services.session_audit import operator_session


class HubService:
    def __init__(self, settings, config, store, automation, event_bus, audit=None):
        self.settings, self.config, self.store = settings, config, store
        self.automation, self.event_bus = automation, event_bus
        self.audit = audit
        self._files_lock = Lock()
        self._files_revision = 0
        self._files_rows = []
        from app.services.chamados_catalog import ChamadosCatalog
        self.chamados_catalog = ChamadosCatalog(settings.backend_root.parent, config)
        from app.services.pending_queue import PendingQueueService
        self.pending_queue = PendingQueueService(settings, config, store, self.chamados_catalog)

    def ctes(self):
        revision = self._files_revision
        with self._files_lock:
            if revision != self._files_revision:
                return deepcopy(self._files_rows)
            rows = self._read_ctes()
            self._files_rows = deepcopy(rows)
            self._files_revision += 1
            return rows

    def _read_ctes(self):
        return self.pending_queue.load()

    def chamados(self):
        if self.chamados_catalog.repository.enabled:
            return [chamado_view(row) for row in self.chamados_catalog.all_raw()]
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
        if snapshot["flow"] == "workflow":
            durable = await asyncio.to_thread(self.store.workflow_events, snapshot["id"])
            events = sorted({event["id"]: event for event in [*events, *durable]}.values(), key=lambda event: event["id"])
        return run_view(snapshot, events)

    async def start(self, flow: str, ctes: list[str], days: int, session_id: str | None = None, *, include_progress: bool = True, date_start=None, date_end=None, http_test=False, workflow=None):
        if self.config and self.store and self.store.ready:
            self.config.values.update(await asyncio.to_thread(self.store.preferences))
        known = {"completo", "documentos", "somente_pdf", "somente_xml", "somente_comprovantes", "buscar_chamados", "somente_chamados", "consulta", "personalizado"}
        if flow not in known:
            raise ValueError("Fluxo nao suportado.")
        if any(not re.fullmatch(r"[0-9]{1,3}-[0-9]{1,3}-[0-9]{1,9}", value)
               or int(value.split("-")[0]) < 1 or int(value.split("-")[2]) < 1 for value in ctes):
            raise ValueError("CT-e invalido. Use filial-serie-numero em todos os itens.")
        ctes = list(dict.fromkeys("-".join(str(int(part)) for part in cte.split("-")) for cte in ctes))
        selected = {"buscar_chamados": "buscar-chamados", "personalizado": "workflow",
                    "consulta": "consulta-pendentes"}.get(flow, "pendentes")
        scope = {"somente_pdf": "pdf", "somente_xml": "xml", "somente_comprovantes": "comprovantes", "somente_chamados": "chamados", "documentos": "documents"}.get(flow, "full")
        allow_missing = bool(self.config) and str(self.config.get("NOVELIS_CHAMADO_ALLOW_MISSING_COMPROVANTE")).lower() in {"true", "1", "sim", "yes"}
        request = RunStartRequest(flow=selected, workflow=workflow, dry_run=False, manual_ctes="\n".join(ctes),
                                  sample_cte=",".join(ctes) if selected != "pendentes" else "",
                                  pendentes_sql_days_back=days, execution_scope=scope,
                                  consulta_data_inicio=date_start, consulta_data_fim=date_end,
                                  pendentes_skip_chamado_missing_comprovante=not allow_missing)
        if session_id and self.audit and not await asyncio.to_thread(self.audit.session, session_id):
            raise ValueError("Sessao encerrada. Entre novamente com o nome do operador.")
        token = operator_session.set(session_id)
        try:
            snapshot = await self.automation.start(request)
        finally:
            operator_session.reset(token)
        if not include_progress:
            return snapshot.model_dump(mode="json")
        return await self.run()

    async def overview(self):
        rows = await asyncio.to_thread(self.ctes)
        meta = await asyncio.to_thread(self.store.local_snapshot, "pending_plan") or {}
        return {"naFila": len(rows), "pdfFaltando": sum(row["pdf"] == "faltando" for row in rows),
                "xmlFaltando": sum(row["xml"] == "faltando" for row in rows),
                "comprovanteFaltando": sum(row["comprovante"] == "faltando" for row in rows),
                "prontosChamado": sum(row["prontoChamado"] for row in rows), "ultimaAtualizacao": await asyncio.to_thread(self.pending_queue.repository.last_seen) or meta.get("generatedAt", ""),
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
                  "LOCAL_DOCUMENT_RETENTION_ENABLED": "Limpeza semanal de PDF/XML locais (true/false)",
                  "XML_SEFAZ_CERTIFICATE_THUMBPRINT": "Impressao digital (opcional, para desempate)",
                  "NOVELIS_RELATORIO_CTE_XML_EXCEL_FILE": "Relatório Novelis compartilhado (Excel)",
                  "NOVELIS_RELATORIO_CTE_XML_JSON_FILE": "Relatório Novelis compartilhado (JSON)"}
        groups = [{"id": "banco", "titulo": "Banco operacional SQLite", "fields": [
            {"key": "NOVELIS_SQLITE_PATH", "label": "Arquivo compartilhado", "value": str(self.store.path),
             "readOnly": True, "hint": "Backend local com transacoes coordenadas entre computadores"}]}]
        if self.audit:
            groups[0]["fields"].append({"key": "LOGIN_AUDIT_DB_PATH", "label": "Logs de sessoes e automacao",
                                        "value": str(self.audit.shared_path), "readOnly": True})
        for group, title, keys in [
            ("documentos", "Geracao de documentos", ["CRYSTAL_PDF_ENGINE", "CRYSTAL_QR_PROVIDER"]),
            ("caminhos", "Pastas e relatórios compartilhados", ["RODOPAR_PDF_DOWNLOAD_TARGET_DIR", "XML_SEFAZ_DOWNLOAD_DIR",
                "NOVELIS_RELATORIO_CTE_XML_EXCEL_FILE", "NOVELIS_RELATORIO_CTE_XML_JSON_FILE"]),
            ("automacoes", "Automacao", ["PENDENTES_STOP_ON_ERROR", "LOCAL_DOCUMENT_RETENTION_ENABLED"]),
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
        catalog = self.chamados_catalog
        configured = catalog.repository.enabled
        plain = self.config.get("CHAMADOS_PG_SSLMODE") == "disable"
        detail = (catalog.last_error or ("Histórico centralizado; busca e paginação no servidor. " +
                  ("Conexão sem SSL conforme perfil privado." if plain else "Conexão com TLS."))) if configured else "Configure CHAMADOS_PG_* no perfil privado."
        result.append({"id": "chamados-pg", "grupo": "Comunicação", "nome": "Chamados PostgreSQL",
                       "status": "erro" if catalog.last_error else "aviso" if not configured or plain else "ok", "detalhe": detail})
        return result
