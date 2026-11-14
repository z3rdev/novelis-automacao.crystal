import json
from pathlib import Path

from dotenv import dotenv_values

ENDPOINT = "https://s3.nexusnerds.com.br"
BUCKET = "z3-releases"
PREFIX = "cargo-hub/"
MANIFEST_URL = f"{ENDPOINT}/{BUCKET}/{PREFIX}latest.json"


class DeveloperConfig:
    def __init__(self, backend_root: Path):
        self.root = backend_root

    def enabled(self) -> bool:
        marker = self.root / "CONFIG.dev"
        if not marker.is_file() or not (self.root / "credentials.json").is_file():
            return False
        try:
            return str(dotenv_values(marker).get("DEVMODE", "")).lower() in {"1", "true", "on"}
        except (OSError, UnicodeError):
            return False

    def status(self) -> dict:
        return {"enabled": self.enabled(), "endpoint": ENDPOINT, "bucket": BUCKET,
                "prefix": PREFIX, "manifest_url": MANIFEST_URL}

    def probe(self) -> dict:
        from app.services.releases.storage import ReleaseStorage

        return ReleaseStorage(self).probe()

    def client(self):
        if not self.enabled():
            raise PermissionError("Modo desenvolvedor desativado.")
        try:
            import boto3
            from botocore.config import Config
        except ImportError:
            raise ValueError("Instale a dependência de desenvolvimento boto3.") from None
        try:
            credentials = json.loads((self.root / "credentials.json").read_text(encoding="utf-8-sig"))
            if credentials.get("url", "").rstrip("/") != ENDPOINT:
                raise ValueError("O endpoint das credenciais difere do servidor de releases.")
            if not credentials.get("accessKey") or not credentials.get("secretKey"):
                raise ValueError("Credenciais locais incompletas.")
            return boto3.client("s3", endpoint_url=ENDPOINT, region_name=credentials.get("region", "us-east-1"),
                aws_access_key_id=credentials["accessKey"], aws_secret_access_key=credentials["secretKey"],
                config=Config(signature_version="s3v4", connect_timeout=5, read_timeout=60,
                    retries={"max_attempts": 1, "mode": "standard"}, s3={"addressing_style": "path"},
                    request_checksum_calculation="when_required", response_checksum_validation="when_required"))
        except (OSError, json.JSONDecodeError, TypeError, AttributeError):
            raise ValueError("Não foi possível ler as credenciais locais de releases.") from None
