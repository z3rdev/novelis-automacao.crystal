"""Import changed source files once and serve paginated records from PostgreSQL."""
import asyncio
import hashlib
import json
import logging
import threading
import time
from datetime import UTC, datetime
from pathlib import Path

from app.infrastructure.chamados_postgres import ChamadosPostgres, CommunicationUnavailable

logger = logging.getLogger(__name__)
_catalogs = {}


def current_catalog(workspace=None):
    if workspace is not None:
        return _catalogs.get(str(Path(workspace).resolve()).casefold())
    return next((catalog for catalog in _catalogs.values() if catalog.repository.enabled), None)


class ChamadosCatalog:
    def __init__(self, workspace, config):
        self.workspace, self.config = workspace, config
        self.repository = ChamadosPostgres(config)
        self._lock = threading.RLock()
        self._ready, self._checked = False, 0.0
        self._signature = None
        self.last_error = None
        self.task = None
        if self.repository.enabled:
            _catalogs[str(workspace.resolve()).casefold()] = self

    def sync(self, force=False):
        if not self.repository.enabled:
            return
        from app.data.chamados_reader import _source_files, read_chamados_payload
        with self._lock:
            if not force and time.monotonic() - self._checked < 30:
                return
            if not self._ready:
                self.repository.initialize()
                self._ready = True
            paths = _source_files(self.workspace, self.config.novelis().get("relatorioCteXmlJsonFile"))
            existing = {key: path for key, path in paths.items() if path.is_file()}
            stats = [(key, str(path), path.stat().st_size, path.stat().st_mtime_ns) for key, path in existing.items()]
            fingerprint = hashlib.sha256(json.dumps(["catalog-v3-source-status", stats]).encode()).hexdigest()
            identifier = hashlib.sha256(str(self.workspace.resolve()).casefold().encode()).hexdigest()
            if existing and fingerprint != self._signature and not self.repository.imported(identifier, fingerprint):
                payload = read_chamados_payload(self.workspace, self.config.novelis().get("relatorioCteXmlJsonFile"))
                # A stale machine must not overwrite newer updates already in the catalog.
                source_at = datetime.fromtimestamp(max(path.stat().st_mtime for path in existing.values()), UTC)
                self.repository.import_rows(payload.get("rows", []), identifier, fingerprint, source_at)
            self._signature, self._checked, self.last_error = fingerprint, time.monotonic(), None

    def page(self, **options):
        if not self.repository.enabled:
            raise CommunicationUnavailable("Configure o PostgreSQL de comunicação para consultar os chamados centralizados.")
        # Imports run in a background worker; requests only read the database.
        if not self._ready:
            self.sync()
        return self.repository.page(**options)

    def all_raw(self):
        self.sync()
        return self.repository.all_raw()

    def detail(self, identifier):
        from app.services.chamado_details import detail_view
        if not self.repository.enabled:
            raise CommunicationUnavailable("Configure o banco de comunicação dos chamados.")
        if not self._ready:
            self.sync()
        record = self.repository.detail(identifier)
        return detail_view(record, self.config) if record else None

    def opened_identities(self, rows):
        # Queue polling only performs indexed reads. Report imports belong to the background sync.
        return self.repository.opened_identities(rows)

    def record_processed(self, row, status, number):
        if not number:
            return
        self.repository.record_processed({"cte": "-".join(str(row.get(key) or "") for key in ("filial", "serie", "documento")),
            "cteId": row.get("cteId", ""), "chamadoNumero": number,
            "status": status, "processedAt": datetime.now(UTC).isoformat()})

    async def loop(self):
        while True:
            try:
                await asyncio.to_thread(self.sync)
            except (CommunicationUnavailable, OSError, ValueError):
                self.last_error = "Sincronização de chamados aguardando banco ou relatório compartilhado."
                logger.warning(self.last_error)
            await asyncio.sleep(30)

    def start(self):
        if self.repository.enabled:
            self.task = asyncio.create_task(self.loop())

    async def close(self):
        if self.task:
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        key = str(self.workspace.resolve()).casefold()
        if _catalogs.get(key) is self:
            _catalogs.pop(key)
