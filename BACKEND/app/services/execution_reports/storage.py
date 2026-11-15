"""Private S3 archives; signing credentials never reach the app or report catalog API."""

import json
from datetime import UTC, datetime, timedelta
from fnmatch import fnmatchcase
from hashlib import sha256
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

import httpx

from app.services.releases.config import BUCKET, ENDPOINT, DeveloperConfig, s3_client

PREFIX = "cargo-hub/reports/executions/"
DAILY_PREFIX = "cargo-hub/reports/daily/"
MAX_BYTES = 50 * 1024 * 1024


def valid_file(path, digest):
    return path.is_file() and sha256(path.read_bytes()).hexdigest() == digest


class ReportStorage:
    def __init__(self, backend_root, config):
        self.root, self.config = backend_root, config

    def client(self):
        if path := self.config.get("EXECUTION_REPORT_S3_CREDENTIALS_FILE"):
            path = Path(path)
            return s3_client(path if path.is_absolute() else self.root / path)
        developer = DeveloperConfig(self.root)
        return developer.client() if developer.enabled() else None

    @staticmethod
    def ensure_private(client, key):
        from botocore.exceptions import ClientError

        try:
            policy = json.loads(client.get_bucket_policy(Bucket=BUCKET)["Policy"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") == "NoSuchBucketPolicy":
                return
            raise RuntimeError(
                "Não foi possível conferir a privacidade do prefixo de relatórios."
            ) from None
        for rule in policy.get("Statement", []):
            principal = rule.get("Principal")
            public = (
                principal == "*"
                or isinstance(principal, dict)
                and "*"
                in (
                    [principal.get("AWS")]
                    if isinstance(principal.get("AWS"), str)
                    else principal.get("AWS", [])
                )
            )
            actions, resources = rule.get("Action", []), rule.get("Resource", [])
            actions = [actions] if isinstance(actions, str) else actions
            resources = [resources] if isinstance(resources, str) else resources
            if (
                rule.get("Effect") == "Allow"
                and public
                and any(fnmatchcase("s3:GetObject", item) for item in actions)
                and any(fnmatchcase(f"arn:aws:s3:::{BUCKET}/{key}", item) for item in resources)
            ):
                raise RuntimeError(
                    "O prefixo de relatórios permite leitura pública; mantenha-o privado antes do envio."
                )

    def publish(self, value, file):
        client = self.client()
        if client is None:
            raise RuntimeError(
                "Envio pendente: configure um publicador S3 autorizado para os relatórios."
            )
        date = datetime.fromisoformat(value.get("report_date") or value["generated_at"])
        key = (
            f"{DAILY_PREFIX}{date:%Y/%m/%d}/report.xlsx"
            if value.get("kind") == "daily"
            else f"{PREFIX}{date:%Y/%m}/{value['id']}/report.xlsx"
        )
        self.ensure_private(client, key)
        if not valid_file(file, value["sha256"]):
            raise RuntimeError("A integridade do Excel local não foi confirmada.")
        client.upload_file(
            str(file),
            BUCKET,
            key,
            ExtraArgs={
                "ContentType": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                "Metadata": {"sha256": value["sha256"]},
                "CacheControl": "private, no-store",
            },
        )
        head = client.head_object(Bucket=BUCKET, Key=key)
        metadata = {key.lower(): item for key, item in head.get("Metadata", {}).items()}
        if (
            metadata.get("sha256") != value["sha256"]
            or head.get("ContentLength") != file.stat().st_size
        ):
            raise RuntimeError("O MinIO não confirmou a integridade do relatório enviado.")
        expires = datetime.now(UTC) + timedelta(days=7)
        return {
            **value,
            "object_key": key,
            "share_status": "shared",
            "share_message": "Disponível no MinIO.",
            "private_url": client.generate_presigned_url(
                "get_object", Params={"Bucket": BUCKET, "Key": key}, ExpiresIn=604800
            ),
            "private_url_expires": expires.isoformat(),
        }

    def retrieve(self, value, cache):
        url = value.get("private_url")
        if url and value.get("private_url_expires", "") > datetime.now(UTC).isoformat():
            parsed = urlsplit(url)
            if not str(value.get("object_key", "")).startswith((PREFIX, DAILY_PREFIX)):
                raise RuntimeError("Prefixo do relatório inválido.")
            expected = f"/{BUCKET}/{value.get('object_key', '')}"
            if (
                parsed.scheme != "https"
                or parsed.netloc != urlsplit(ENDPOINT).netloc
                or unquote(parsed.path) != expected
            ):
                raise RuntimeError("Endereço do relatório inválido.")
            temporary = cache.with_name(cache.name + "." + uuid4().hex + ".download")
            try:
                cache.parent.mkdir(parents=True, exist_ok=True)
                size = 0
                with httpx.stream("GET", url, timeout=60, follow_redirects=False) as response:
                    response.raise_for_status()
                    with temporary.open("wb") as file:
                        for chunk in response.iter_bytes():
                            size += len(chunk)
                            if size > MAX_BYTES:
                                raise RuntimeError("O relatório excedeu o limite de download.")
                            file.write(chunk)
                if not valid_file(temporary, value["sha256"]):
                    raise RuntimeError("A integridade do relatório baixado não foi confirmada.")
                temporary.replace(cache)
                return cache
            except httpx.HTTPError:
                pass  # Shared network cache remains available during a MinIO outage.
            finally:
                temporary.unlink(missing_ok=True)
        if valid_file(cache, value["sha256"]):
            return cache
        raise RuntimeError(
            "Excel indisponível. Verifique o MinIO e a pasta compartilhada de relatórios."
        )
