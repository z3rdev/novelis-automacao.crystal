from contextlib import contextmanager
from hashlib import sha256

from app.infrastructure.sqlite_lease import WriterLease

from .daily_models import consolidate
from .daily_repository import DailyRepository
from .storage import valid_file
from .workbook import build


class DailyReports:
    def __init__(self, sources, root, storage):
        self.sources, self.storage = sources, storage
        self.repository = DailyRepository(sources.store)
        self.root = root / "daily"

    def file(self, value):
        return self.root / f"{value['report_date']}.xlsx"

    @contextmanager
    def locked(self, value):
        self.root.mkdir(parents=True, exist_ok=True)
        lease = WriterLease(self.file(value))
        lease.acquire(timeout=120)
        try:
            yield
        finally:
            lease.close()

    def refresh(self):
        days = consolidate(self.sources.completed())
        for day, candidate in days.items():
            # The same per-day lock also protects publishing and downloads on other PCs.
            with self.locked(candidate):
                current = self.repository.get(candidate["id"])
                # A different backend may have completed another run while we waited.
                value = consolidate(self.sources.completed())[day]
                path = self.file(value)
                if (
                    current
                    and current["source_revision"] == value["source_revision"]
                    and valid_file(path, current["sha256"])
                ):
                    continue
                build(value, path)
                value["sha256"] = sha256(path.read_bytes()).hexdigest()
                self.repository.save(value)

    def publish(self, report_id):
        value = self.repository.get(report_id)
        if not value:
            raise LookupError("Relatório diário não encontrado.")
        with self.locked(value):
            value = self.repository.get(report_id)
            updated = self.storage.publish(value, self.file(value))
            self.repository.save(updated)

    def download(self, report_id):
        value = self.repository.get(report_id)
        if not value:
            raise LookupError("Relatório diário não encontrado.")
        with self.locked(value):
            value = self.repository.get(report_id)
            return self.storage.retrieve(value, self.file(value))
