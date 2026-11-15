"""Fill authorization metadata for the queue created by older application versions."""

from datetime import UTC, datetime

from app.data.consulta_db import fetch_rows_by_documents
from app.domain.cte_authorization import authorization_status


def refresh_queue_authorization(repository, db_config, rows):
    missing = [row for row in rows if not authorization_status(row)]
    if not missing or not db_config.get("enabled"):
        return rows
    try:
        result = fetch_rows_by_documents(db_config, missing)
    except RuntimeError:
        return rows
    checked = [row for row in result.rows if authorization_status(row)]
    if checked:
        repository.ingest(
            {"rows": checked, "generatedAt": datetime.now(UTC).isoformat()},
            f"authorization:{repository.store.machine_id}",
        )
        return repository.rows()
    return rows
