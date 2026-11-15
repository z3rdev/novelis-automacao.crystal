import json
import time
from pathlib import Path

from app.services.pending_plan_view import _load_plan_rows
from app.data.chamados_reader import read_chamados_payload
from app.data.chamados_log import read_processed_ctes
from app.infrastructure.operations_store import OperationsStore
from app.infrastructure.pending_queue import PendingQueue, access_key, cte_number, identity
from app.services.hub_views import cte_view, number
from app.domain.cte_authorization import authorization_status
from app.services.pending_authorization import refresh_queue_authorization


def eligible_plan(payload, request=None):
    if request and any(getattr(request, name, None) for name in ("manual_ctes", "manual_spreadsheet", "sample_cte", "sample_documento", "sample_filial")):
        return False
    if "queueEligible" in payload:
        return payload["queueEligible"] is True
    source = str(payload.get("sourceFile") or "").lower()
    if "novelis-filtered" in source or payload.get("sourceKind") == "python_pendentes_novelis_filtered":
        return True
    rows = [item.get("row", {}) for item in payload.get("checked", [])] if "checked" in payload else payload.get("rows", [])
    return not any("SQL_ULTIMOS" in str(row.get("status") or "") for row in rows)


def record_plan(settings, payload):
    path = getattr(settings, "novelis_sqlite_path", None)
    if not path or not eligible_plan(payload):
        return
    store = OperationsStore(Path(path))
    store.initialize()
    try:
        PendingQueue(store).ingest(payload, f"plan:{store.machine_id}")
    finally:
        store.close()


class PendingQueueService:
    def __init__(self, settings, config, store, catalog):
        self.settings, self.config, self.store, self.catalog = settings, config, store, catalog
        self.root = settings.backend_root.parent
        self.repository = PendingQueue(store)
        self._known, self._checked, self._identities = [], 0.0, None
        self._authorization_checked = None
        from app.services.tariffs.audit import TariffAuditService
        self.tariffs = TariffAuditService(config)

    def known_opened(self, rows):
        signature = tuple(sorted(identity(row) for row in rows))
        if time.monotonic() - self._checked > 20 or signature != self._identities:
            if self.catalog.repository.enabled:
                self._known = self.catalog.opened_identities(rows)
            else:
                self._known = read_chamados_payload(self.root, self.config.novelis().get("relatorioCteXmlJsonFile")).get("rows", [])
            self._checked = time.monotonic()
            self._identities = signature
        # The local ledger sees successful creation before a report is downloaded again.
        cfg = self.config.chamado_novelis() if hasattr(self.config, "chamado_novelis") else {}
        processed = read_processed_ctes(cfg.get("chamadosLogFile"))
        ledger = [{**value, "chamado": value.get("chamadoNumero")} for value in processed.values() if value.get("chamadoNumero")]
        return self._known + ledger

    @staticmethod
    def unopened(rows, known):
        keys = {access_key(row) for row in known if row.get("chamado") and access_key(row)}
        numbers_without_keys = {cte_number(row) for row in known if row.get("chamado") and not access_key(row)}
        numbers = {cte_number(row) for row in known if row.get("chamado")}
        return [row for row in rows if access_key(row) not in keys and
                cte_number(row) not in (numbers_without_keys if access_key(row) else numbers)]

    def load(self):
        from app.services.pending_documents import refresh_files
        payloads = [self.store.local_snapshot("pending_plan"), self.store.snapshot("pending_plan")]
        sources = [self.root / "captures/pendentes/latest-python.json", self.root / "captures/pendentes/novelis-filtered.json",
                   self.root / "captures/pendentes/sql-ultimos-5-dias.json"]
        for source in sources:
            if source.is_file():
                payloads.append(json.loads(source.read_text(encoding="utf-8-sig")))
        for index, payload in enumerate(payloads):
            if payload and eligible_plan(payload):
                self.repository.ingest(payload, f"legacy:{self.store.machine_id}:{index}")
            elif payload:
                candidates = [item.get("row", {}) for item in payload.get("checked", [])] if "checked" in payload else payload.get("rows", [])
                excluded = [row for row in candidates if authorization_status(row) == "N"]
                if excluded:
                    self.repository.ingest({"rows": excluded, "generatedAt": payload.get("generatedAt")},
                                           f"unauthorized:{self.store.machine_id}:{index}")
        rows = self.repository.rows()
        if rows and (self._authorization_checked is None or time.monotonic() - self._authorization_checked > 60):
            self._authorization_checked = time.monotonic()
            db_config = self.config.consulta_db() if hasattr(self.config, "consulta_db") else {}
            rows = refresh_queue_authorization(self.repository, db_config, rows)
        if not rows:
            return []
        remaining = self.unopened(rows, self.known_opened(rows))
        keep = {identity(row) for row in remaining}
        self.repository.close([identity(row) for row in rows if identity(row) not in keep])
        payload = refresh_files({"checked": [{"cte": cte_number(row), "row": row} for row in remaining]}, self.config, self.root)
        _, plan_rows = _load_plan_rows(self.settings, payload)
        raw_by_number = {cte_number(row): row for row in remaining}
        audits = self.tariffs.rows(remaining)
        result = []
        for row in plan_rows:
            value, raw = cte_view(row), raw_by_number[row["cte"]]
            value["tariffAudit"] = audits.get(identity(raw))
            value.update(chave=access_key(raw), emissao=str(raw.get("data") or raw.get("DATA") or ""),
                         valor=number(raw.get("VLR_TOTAL")) if raw.get("VLR_TOTAL") is not None else None)
            for field in ("origem", "destino", "remetente", "destinatario"):
                value[field] = str(raw.get(field) or "")
            result.append(value)
        return sorted(result, key=lambda row: (row["emissao"], row["id"]), reverse=True)
