"""Read SQL and a fresh Novelis report; optionally persist the unopened CT-e queue."""
import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))


class QueueInputError(RuntimeError):
    pass


def main():
    from app.config.settings import get_settings
    from app.config.legacy_config import LegacyConfig
    from app.data.consulta_db import fetch_last_5_days_rows
    from app.data.chamados_reader import read_chamados_payload
    from app.infrastructure.operations_store import OperationsStore
    from app.services.chamados_catalog import ChamadosCatalog
    from app.services.pending_queue import PendingQueueService

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=2, choices=range(0,91))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    settings = get_settings()
    if not settings.novelis_sqlite_path:
        raise QueueInputError("Banco compartilhado não configurado.")
    config = LegacyConfig(settings)
    store = OperationsStore(settings.novelis_sqlite_path)
    store.initialize()
    try:
        config.values.update(store.preferences())
        report_path = Path(config.novelis().get("relatorioCteXmlJsonFile") or "")
        if not report_path.is_file():
            raise QueueInputError("Relatório Novelis compartilhado indisponível.")
        report = json.loads(report_path.read_text(encoding="utf-8-sig"))
        generated = datetime.fromisoformat(str(report.get("generatedAt") or "").replace("Z","+00:00"))
        if generated.tzinfo is None:
            generated = generated.replace(tzinfo=UTC)
        if generated < datetime.now(UTC)-timedelta(hours=24) or not report.get("rows"):
            raise QueueInputError("Atualize o relatório Novelis antes de inicializar a fila.")
        sql = fetch_last_5_days_rows(config.consulta_db(), args.days)
        catalog = ChamadosCatalog(settings.backend_root.parent, config)
        service = PendingQueueService(settings,config,store,catalog)
        known = service.known_opened(sql.rows) + read_chamados_payload(settings.backend_root.parent,report_path).get("rows",[])
        remaining = service.unopened(sql.rows,known)
        timestamp = datetime.now(UTC).isoformat()
        if args.apply:
            service.repository.ingest({"generatedAt":timestamp,"rows":remaining},"initial-sql-backlog")
            service.load()
        result = {"status":"ok", "checked_at":timestamp, "days_back":args.days,
                  "sql_rows":len(sql.rows),"already_opened":len(sql.rows)-len(remaining),
                  "unopened_in_period":len(remaining),"applied":args.apply,
                  "queue_total":len(service.repository.rows()) if args.apply else None,
                  "report_generated_at":generated.isoformat(),"ticket_creation_executed":False}
    finally:
        store.close()
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding="utf-8")
    print(json.dumps(result,ensure_ascii=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Never print database driver exceptions or a connection string.
        text = str(exc) if isinstance(exc, QueueInputError) else "Não foi possível inicializar a fila. Verifique SQL, relatório e banco compartilhado."
        print(json.dumps({"status":"error","message":text},ensure_ascii=False))
        raise SystemExit(1) from None
