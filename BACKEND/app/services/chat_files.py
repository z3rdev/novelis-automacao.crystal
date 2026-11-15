import hashlib
import io
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from app.domain.chat import ChatError, ChatStorageError, cte_code

MAX_UPLOAD = 20 * 1024 * 1024
VERSION_DIR = ".cargo-hub-versions"
MANIFEST = ".cargo-hub-documents.json"


def pdf_bytes(data: bytes, name: str) -> bytes:
    if not data or len(data) > MAX_UPLOAD:
        raise ChatError("Envie um arquivo com até 20 MB.")
    try:
        if data.startswith(b"%PDF-"):
            from pypdf import PdfReader

            pdf = PdfReader(io.BytesIO(data))
            if pdf.is_encrypted or not 0 < len(pdf.pages) <= 200:
                raise ValueError("pdf")
            return data
        if Path(name).suffix.lower() not in {".png", ".jpg", ".jpeg"}:
            raise ValueError("format")
        from PIL import Image

        with Image.open(io.BytesIO(data)) as image:
            if image.format not in {"PNG", "JPEG"} or image.width * image.height > 40_000_000:
                raise ValueError("image")
            output = io.BytesIO()
            image.convert("RGB").save(
                output, format="PDF", resolution=150, creationDate=None, modDate=None
            )
            return output.getvalue()
    except Exception:  # noqa: BLE001 - untrusted PDF/image parsers have multiple error families
        raise ChatError("Envie um PDF válido, sem senha, ou uma imagem PNG/JPG.") from None


def merge_pdfs(guia: bytes, comprovante: bytes) -> bytes:
    from pypdf import PdfWriter

    writer, output = PdfWriter(), io.BytesIO()
    writer.append(io.BytesIO(guia))
    writer.append(io.BytesIO(comprovante))
    writer.write(output)
    writer.close()
    return output.getvalue()


def atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
    try:
        with temporary.open("xb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


class ChatFiles:
    def __init__(self, root, objects=None):
        self._root = root
        self.objects = objects

    @property
    def root(self):
        return Path(self._root() if callable(self._root) else self._root)

    def directory(self, cte):
        base = self.root.resolve()
        target = (base / cte_code(cte)).resolve()
        if not target.is_relative_to(base):
            raise ChatError("Pasta do CT-e inválida.")
        return target

    def path(self, cte, metadata):
        identifier = str(UUID(metadata["id"]))
        kind = metadata["kind"]
        prefix = {"guia": "GNR", "comprovante": "CMP", "combined": "GNR_CMP"}[kind]
        base = self.directory(cte)
        path = (base / VERSION_DIR / identifier / f"{prefix}_{cte_code(cte)}.pdf").resolve()
        if not path.is_relative_to(base):
            raise ChatError("Arquivo do CT-e inválido.")
        return path

    def write(self, cte, metadata, data):
        if self.objects:
            self.objects.write(cte, metadata, data)
            return
        try:
            atomic_write(self.path(cte, metadata), data)
        except OSError:
            raise ChatStorageError(
                "Não foi possível salvar o documento na pasta compartilhada."
            ) from None

    def read(self, cte, metadata):
        if metadata.get("expires_at") and datetime.fromisoformat(
            metadata["expires_at"]
        ) <= datetime.now(UTC):
            raise ChatStorageError("O prazo de armazenamento de 30 dias deste documento terminou.")
        if metadata.get("object_key"):
            if not self.objects:
                raise ChatStorageError("O armazenamento MinIO está indisponível.")
            return self.objects.read(cte, metadata)
        try:
            data = self.path(cte, metadata).read_bytes()
        except OSError:
            raise ChatStorageError(
                "O documento está indisponível na pasta compartilhada."
            ) from None
        if hashlib.sha256(data).hexdigest() != metadata["sha256"]:
            raise ChatStorageError(
                "O documento foi alterado na pasta compartilhada. Envie-o novamente."
            )
        return data

    def publish(self, row):
        if self.objects:
            from app.services.chat_network import ChatNetworkDelivery

            ChatNetworkDelivery(self).publish(row)
            return
        try:
            base, entries = self.directory(row["cte"]), {}
            for kind in ("guia", "comprovante", "combined"):
                metadata = row.get(kind)
                if metadata:
                    source = self.path(row["cte"], metadata)
                    atomic_write(base / source.name, self.read(row["cte"], metadata))
                    entries[kind] = {
                        "relative_path": str(source.relative_to(base)),
                        "sha256": metadata["sha256"],
                    }
            value = {
                "schema": 1,
                "cte": row["cte"],
                "generation": str(row["generation"]),
                "files": entries,
            }
            atomic_write(base / MANIFEST, json.dumps(value).encode("utf-8"))
        except OSError:
            raise ChatStorageError(
                "Entrega aguardando acesso à pasta compartilhada. Tente atualizar a conversa."
            ) from None


def published_documents(root, cte):
    try:
        base = Path(root) / cte_code(cte)
        with (base / MANIFEST).open("rb") as stream:
            content = stream.read(32769)
        if len(content) > 32768:
            return {}
        value = json.loads(content)
        if value.get("schema") != 1 or value.get("cte") != cte_code(cte):
            return {}
        result = {}
        for kind, entry in value["files"].items():
            if kind not in {"guia", "comprovante", "combined"}:
                continue
            path = (base / entry["relative_path"]).resolve()
            if path.is_relative_to(base.resolve()) and path.is_file():
                result[kind] = path
        return result
    except (OSError, ValueError, KeyError, TypeError, RuntimeError):
        return {}


def verify_managed_document(path):
    """Check managed content once when assembling the upload, outside list polling."""
    path = Path(path)
    base = path.parent.parent.parent if path.parent.parent.name == VERSION_DIR else path.parent
    if path.parent.parent.name != VERSION_DIR and not (base / MANIFEST).is_file():
        return
    try:
        with (base / MANIFEST).open("rb") as stream:
            content = stream.read(32769)
        value = json.loads(content)
        relative = str(path.relative_to(base))
        entry = next(item for item in value["files"].values() if item["relative_path"] == relative)
        if len(content) > 32768 or hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
            raise ValueError("digest")
    except (OSError, ValueError, KeyError, TypeError, StopIteration):
        raise RuntimeError(
            "Documento GNRE alterado ou indisponível. Confira a solicitação no chat."
        ) from None
