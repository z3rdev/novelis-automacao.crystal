"""Operational MinIO access, independent of release publishing permissions."""

from pathlib import Path

from app.services.releases.config import s3_client


def operational_client(root: Path, config, purpose: str = ""):
    configured = config.get(purpose) if purpose else ""
    configured = configured or config.get("MINIO_CREDENTIALS_FILE")
    if configured:
        path = Path(configured)
        return s3_client(path if path.is_absolute() else root / path)
    for filename in ("minio.credentials.json", "credentials.json"):
        path = root / filename
        if path.is_file():
            return s3_client(path)
    return None
