import asyncio
import hashlib
import subprocess
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import httpx
from pydantic import ValidationError

from app.services.releases.config import BUCKET, ENDPOINT, MANIFEST_URL, PREFIX, DeveloperConfig
from app.services.releases.manifest import ReleaseManifest, version_parts
from app.services.releases.storage import ReleaseStorage


def verify_package(path: Path, release: ReleaseManifest) -> None:
    if path.stat().st_size != release.size:
        raise ValueError("O tamanho do instalador difere do manifesto.")
    with path.open("rb") as stream:
        if stream.read(2) != b"MZ":
            raise ValueError("O arquivo recebido não é um executável Windows.")
        stream.seek(0)
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    if digest != release.sha256.lower():
        raise ValueError("A verificação SHA-256 do instalador falhou.")


def launch_installer(path: Path, root: Path) -> subprocess.Popen:
    if sys.platform != "win32":
        raise ValueError("A instalação está disponível no Windows.")
    return subprocess.Popen([str(path), f"/DIR={root}", "/CLOSEAPPLICATIONS", "/NORESTART"],
                     cwd=path.parent, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL,
                     creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)


class ReleaseService:
    def __init__(self, root: Path, current_version: str, transport=None):
        self.root = root
        self.current_version = current_version
        self.cache = root / "runtime" / "updates"
        self.transport = transport
        self.storage = ReleaseStorage(DeveloperConfig(root / "BACKEND"))
        self.release: ReleaseManifest | None = None
        self.status = "unchecked"
        self.message = ""
        self.received = 0
        self.checked_at: str | None = None
        self.task: asyncio.Task | None = None
        self.installer: subprocess.Popen | None = None
        self._check_lock = asyncio.Lock()
        self._install_lock = asyncio.Lock()

    def snapshot(self) -> dict:
        if self.status == "installing" and self.installer and self.installer.poll() is not None:
            self.installer = None
            self.status = "ready"
            self.message = "O assistente foi encerrado. Você pode abri-lo novamente ou reiniciar o Cargo Hub."
        return {"status": self.status, "current_version": self.current_version,
                "release": self.release.model_dump(mode="json") if self.release else None,
                "received_bytes": self.received, "checked_at": self.checked_at,
                "message": self.message,
                "can_install": (self.root / ".automacao-novelis-install").is_file()}

    async def _fetch_manifest(self) -> ReleaseManifest | None:
        if self.storage.enabled():
            release, _ = await asyncio.to_thread(self.storage.read_manifest)
            return release
        async with (
            httpx.AsyncClient(transport=self.transport, timeout=12, follow_redirects=False) as client,
            client.stream("GET", MANIFEST_URL, headers={"Cache-Control": "no-cache"}) as response,
        ):
            if response.status_code == 404:
                return None
            if response.status_code in {401, 403}:
                raise ValueError("O servidor exige autorização para leitura das atualizações.")
            response.raise_for_status()
            content = bytearray()
            async for chunk in response.aiter_bytes():
                content.extend(chunk)
                if len(content) > 65536:
                    raise ValueError("O manifesto de atualização excede o tamanho permitido.")
        return ReleaseManifest.model_validate_json(content)

    async def check(self) -> dict:
        if self._check_lock.locked():
            async with self._check_lock:
                return self.snapshot()
        async with self._check_lock:
            if self.status in {"downloading", "ready", "installing"}:
                return self.snapshot()
            release = None
            try:
                release = await self._fetch_manifest()
                if release is None:
                    status, message = "not_published", "O servidor ainda não possui um manifesto de atualização publicado."
                elif version_parts(release.version) <= version_parts(self.current_version):
                    release = None
                    status, message = "up_to_date", "O Cargo Hub está atualizado."
                else:
                    status, message = "available", "Uma nova versão está disponível."
            except ValidationError:
                status, message = "error", "O manifesto de atualização possui formato inválido."
            except ValueError as exc:
                status, message = "error", str(exc)
            except httpx.HTTPError:
                status, message = "error", "Não foi possível consultar o servidor de atualizações. Tente novamente."
            # A download or installation may have started while the HTTP request awaited IO.
            if self.status in {"downloading", "ready", "installing"}:
                return self.snapshot()
            self.release = release
            self.status, self.message = status, message
            self.received = 0
            self.checked_at = datetime.now(UTC).isoformat()
            return self.snapshot()

    def package_path(self, release: ReleaseManifest) -> Path:
        return self.cache / release.sha256.lower() / release.file

    def start_download(self) -> dict:
        if self.status in {"downloading", "ready", "installing"}:
            return self.snapshot()
        if not self.release or self.status != "available":
            raise ValueError("Consulte uma atualização disponível antes de baixar.")
        self.status, self.message, self.received = "downloading", "Baixando o instalador…", 0
        self.task = asyncio.create_task(self._download(self.release))
        return self.snapshot()

    async def _package_chunks(self, release: ReleaseManifest):
        if self.storage.enabled():
            async for chunk in self.storage.chunks(release):
                yield chunk
            return
        url = f"{ENDPOINT}/{BUCKET}/{PREFIX}{release.package_key()}"
        async with (
            httpx.AsyncClient(transport=self.transport, timeout=60, follow_redirects=False) as client,
            client.stream("GET", url) as response,
        ):
            response.raise_for_status()
            async for chunk in response.aiter_bytes(65536):
                yield chunk

    async def _download(self, release: ReleaseManifest) -> None:
        target = self.package_path(release)
        temporary = target.with_suffix(f".{uuid.uuid4().hex}.partial")
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            if target.is_file():
                try:
                    await asyncio.to_thread(verify_package, target, release)
                    self.received = release.size
                    self.status, self.message = "ready", "Instalador baixado e integridade conferida."
                    return
                except ValueError:
                    target.unlink()
            digest = hashlib.sha256()
            with temporary.open("xb") as stream:
                async for chunk in self._package_chunks(release):
                    self.received += len(chunk)
                    if self.received > release.size:
                        raise ValueError("O instalador recebido excede o tamanho declarado.")
                    digest.update(chunk)
                    stream.write(chunk)
            if self.received != release.size or digest.hexdigest() != release.sha256.lower():
                raise ValueError("A verificação de tamanho ou SHA-256 do instalador falhou.")
            await asyncio.to_thread(verify_package, temporary, release)
            temporary.replace(target)
            self.status, self.message = "ready", "Instalador baixado e integridade conferida."
        except asyncio.CancelledError:
            self.status, self.message = "available", "Download interrompido. Você pode tentar novamente."
            raise
        except ValueError as exc:
            self.status, self.message = "error", str(exc)
        except (OSError, httpx.HTTPError):
            self.status, self.message = "error", "Falha no download. Verifique a rede e o espaço em disco."
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass

    async def install(self) -> dict:
        async with self._install_lock:
            if self.status == "installing":
                return self.snapshot()
            if not self.snapshot()["can_install"]:
                raise ValueError("A instalação de atualizações está disponível na cópia instalada do Cargo Hub.")
            if self.status != "ready" or not self.release:
                raise ValueError("Baixe e valide o instalador antes de instalar.")
            self.status, self.message = "installing", "Abrindo o assistente de atualização…"
            try:
                path = self.package_path(self.release)
                await asyncio.to_thread(verify_package, path, self.release)
                self.installer = launch_installer(path, self.root)
            except (OSError, ValueError):
                self.status, self.message = "error", "Não foi possível abrir o instalador validado. Consulte e baixe novamente."
                raise ValueError(self.message) from None
            return self.snapshot()

    async def close(self) -> None:
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
