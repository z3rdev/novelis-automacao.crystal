import asyncio
import hashlib
import json
import re
import struct
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field, ValidationError

from app.services.releases.config import BUCKET
from app.services.releases.manifest import VERSION_PATTERN, ReleaseManifest, version_parts
from app.services.releases.storage import ReleaseStorage, storage_error


class PublishRequest(BaseModel):
    installer_path: str = Field(min_length=1, max_length=1024)
    version: str = Field(pattern=VERSION_PATTERN, max_length=50)
    notes: str = Field(min_length=1, max_length=10000)
    distribution_authorized: bool = False


def inspect_package(path: Path, version: str) -> dict:
    if not path.is_absolute() or not path.is_file():
        raise ValueError("Selecione um instalador local existente.")
    if not re.fullmatch(r"NovelisCargoHubSetup-" + re.escape(version) + r"(?:-[A-Za-z0-9._-]+)?\.exe", path.name):
        raise ValueError("O nome do instalador deve corresponder à versão informada.")
    if any(marker in path.name.upper() for marker in ("PRIVADO", "TESTE", "NAODISTRIBUIR")):
        raise ValueError("Este pacote está marcado como privado ou teste. A publicação depende da liberação de distribuição definida para o projeto.")
    receipt = {}
    receipt_path = path.with_suffix(".manifest.json")
    if receipt_path.is_file():
        if receipt_path.stat().st_size > 2 * 1024**2:
            raise ValueError("O inventário de distribuição excede o tamanho permitido.")
        try:
            receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            raise ValueError("O inventário de distribuição do instalador está inválido.") from None
        if not isinstance(receipt, dict) or not isinstance(receipt.get("operational_configuration", {}), dict):
            raise ValueError("O inventário de distribuição do instalador está inválido.")
        if (receipt.get("build_mode") == "development" or receipt.get("production_ready") is False
                or receipt.get("operational_configuration", {}).get("contains_operational_credentials")
                or receipt.get("operational_configuration", {}).get("included")):
            raise ValueError("O inventário identifica um pacote com distribuição pendente ou configuração privada.")
        if receipt.get("sha256") is not None and not isinstance(receipt["sha256"], str):
            raise ValueError("O inventário de distribuição possui SHA-256 inválido.")
        if receipt.get("filename") and receipt["filename"] != path.name:
            raise ValueError("O nome do instalador difere do inventário de distribuição.")
        receipt_version = receipt.get("app_version")
        if receipt_version and not isinstance(receipt_version, str):
            raise ValueError("O inventário de distribuição possui versão inválida.")
        if receipt_version and receipt.get("installer_revision"):
            receipt_version += "-" + str(receipt["installer_revision"])
        if receipt_version and receipt_version != version:
            raise ValueError("A versão informada difere do inventário de distribuição.")
    with path.open("rb") as stream:
        header = stream.read(64)
        if len(header) < 64 or header[:2] != b"MZ":
            raise ValueError("O arquivo selecionado não é um instalador Windows válido.")
        offset = struct.unpack_from("<I", header, 60)[0]
        stream.seek(offset)
        pe = stream.read(6)
        if len(pe) != 6 or pe[:4] != b"PE\0\0" or struct.unpack_from("<H", pe, 4)[0] not in {0x14c, 0x8664}:
            raise ValueError("O executável selecionado possui estrutura PE incompatível.")
    if not 0 < path.stat().st_size <= 3 * 1024**3:
        raise ValueError("O tamanho do instalador excede o limite de 3 GB.")
    return receipt


class ReleasePublisher:
    def __init__(self, root: Path, storage: ReleaseStorage):
        self.root = root / "runtime" / "release-publish"
        self.storage = storage
        self.task: asyncio.Task | None = None
        self.request: PublishRequest | None = None
        self.cancel = threading.Event()
        self.lock = threading.Lock()
        self.data = {"status": "idle", "sent_bytes": 0, "total_bytes": 0, "version": None,
                     "filename": None, "message": "", "release": None}

    def snapshot(self) -> dict:
        with self.lock:
            return dict(self.data)

    def update(self, **values) -> None:
        with self.lock:
            self.data.update(values)

    def start(self, body: PublishRequest) -> dict:
        if not self.storage.enabled():
            raise PermissionError("Modo desenvolvedor desativado.")
        if not body.distribution_authorized:
            raise ValueError("Confirme a autorização de distribuição deste pacote antes de publicar.")
        if self.task and not self.task.done():
            if self.request == body:
                return self.snapshot()
            raise ValueError("Uma publicação já está em andamento.")
        self.request = body
        self.cancel.clear()
        self.update(status="validating", sent_bytes=0, total_bytes=0, version=body.version,
                    filename=Path(body.installer_path).name, message="Validando o instalador…", release=None)
        self.task = asyncio.create_task(self._run(body))
        return self.snapshot()

    def checkpoint(self) -> None:
        if self.cancel.is_set() or not self.storage.enabled():
            raise ValueError("Publicação interrompida. O modo desenvolvedor precisa permanecer ativo.")

    def progress(self, amount: int) -> None:
        self.checkpoint()
        with self.lock:
            self.data["sent_bytes"] = max(0, min(self.data["total_bytes"], self.data["sent_bytes"] + amount))

    async def _run(self, body: PublishRequest) -> None:
        try:
            await asyncio.to_thread(self._publish, body)
        except ValidationError:
            self.update(status="error", message="Os metadados da publicação possuem formato inválido.")
        except (ValueError, OSError) as exc:
            message = str(exc) if isinstance(exc, ValueError) else "Falha ao ler ou preparar o instalador local."
            self.update(status="error", message=message)

    def _publish(self, body: PublishRequest) -> None:
        try:
            from boto3.exceptions import S3UploadFailedError
            from boto3.s3.transfer import TransferConfig
            from botocore.exceptions import BotoCoreError, ClientError
        except ImportError:
            raise ValueError("Instale a dependência de desenvolvimento boto3.") from None
        source = Path(body.installer_path)
        receipt = inspect_package(source, body.version)
        folder = self.root / uuid.uuid4().hex
        stage = folder / source.name
        folder.mkdir(parents=True)
        try:
            digest = hashlib.sha256()
            size = source.stat().st_size
            self.update(total_bytes=size)
            with source.open("rb") as original, stage.open("xb") as target:
                while chunk := original.read(1024 * 1024):
                    self.checkpoint()
                    digest.update(chunk)
                    target.write(chunk)
            if stage.stat().st_size != size:
                raise ValueError("O instalador foi alterado durante a preparação. Selecione o arquivo novamente.")
            inspect_package(stage, body.version)
            sha256 = digest.hexdigest()
            if receipt.get("sha256") and receipt["sha256"].lower() != sha256:
                raise ValueError("O SHA-256 do instalador difere do inventário de distribuição.")
            release = ReleaseManifest(version=body.version, title=f"Cargo Hub {body.version}", notes=body.notes.strip(),
                published_at=datetime.now(UTC), file=source.name, sha256=sha256, size=size,
                object_key=f"packages/{sha256}/{source.name}")
            client = self.storage.config.client()
            current, _ = self.storage.read_manifest(client)
            if current and current.version == release.version and current.sha256.lower() == sha256:
                self.update(status="published", sent_bytes=size, message="Esta atualização já está publicada.", release=current.model_dump(mode="json"))
                return
            if current and version_parts(release.version) <= version_parts(current.version):
                raise ValueError("Publique uma versão superior à atualização disponível no servidor.")
            self.checkpoint()
            self.update(status="uploading", message="Enviando o instalador ao servidor…")
            client.upload_file(str(stage), BUCKET, self.storage.prefix + release.package_key(),
                ExtraArgs={"ContentType": "application/vnd.microsoft.portable-executable", "Metadata": {"sha256": sha256}},
                Callback=self.progress, Config=TransferConfig(max_concurrency=2, multipart_chunksize=8 * 1024**2))
            self.checkpoint()
            remote = client.head_object(Bucket=BUCKET, Key=self.storage.prefix + release.package_key())
            metadata = {key.lower(): value for key, value in remote.get("Metadata", {}).items()}
            if remote["ContentLength"] != size or metadata.get("sha256") != sha256:
                raise ValueError("O servidor não confirmou os metadados do instalador enviado.")
            self.update(status="publishing", sent_bytes=size, message="Publicando o manifesto da atualização…")
            active = self.storage.commit_manifest(client, release)
            message = "Atualização publicada com sucesso." if active.version == release.version else f"Pacote enviado. A versão mais recente do servidor é {active.version}."
            self.update(status="published", message=message, release=active.model_dump(mode="json"))
        except (BotoCoreError, ClientError, S3UploadFailedError) as exc:
            raise storage_error(exc) from None
        finally:
            try:
                stage.unlink(missing_ok=True)
                folder.rmdir()
            except OSError:
                pass

    async def close(self) -> None:
        self.cancel.set()
        if self.task and not self.task.done():
            await self.task
