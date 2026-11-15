"""Materialize only the unified PDF and remove only verified managed network files."""

import hashlib
import json

from app.domain.chat import ChatStorageError
from app.services.chat_files import MANIFEST, atomic_write


class ChatNetworkDelivery:
    def __init__(self, files):
        self.files = files

    @staticmethod
    def manifest(base):
        try:
            with (base / MANIFEST).open("rb") as stream:
                data = stream.read(32769)
            value = json.loads(data) if len(data) <= 32768 else None
            if not isinstance(value, dict) or not isinstance(value.get("files"), dict):
                raise ChatStorageError(
                    "O índice dos documentos na rede é inválido. Arquivos preservados."
                )
            return value
        except FileNotFoundError:
            return {}
        except (ValueError, UnicodeError):
            raise ChatStorageError(
                "O índice dos documentos na rede é inválido. Arquivos preservados."
            ) from None

    def publish(self, row):
        if not row.get("combined"):
            return
        try:
            base = self.files.directory(row["cte"])
            previous = self.manifest(base)
            metadata = row["combined"]
            target = base / f"GNR_CMP_{row['cte']}.pdf"
            data = self.files.read(row["cte"], metadata)
            atomic_write(target, data)
            entry = {"relative_path": target.name, "sha256": metadata["sha256"]}
            atomic_write(
                base / MANIFEST,
                json.dumps(
                    {
                        "schema": 1,
                        "cte": row["cte"],
                        "generation": str(row["generation"]),
                        "storage": "minio",
                        "files": {kind: entry for kind in ("guia", "comprovante", "combined")},
                    }
                ).encode("utf-8"),
            )
            # Migration removes only the old files identified by our previous manifest.
            if previous.get("cte") == row["cte"]:
                self.remove_entries(base, previous, keep={target.resolve()})
        except OSError:
            raise ChatStorageError(
                "PDF unificado salvo no MinIO; entrega na pasta de rede pendente."
            ) from None

    @staticmethod
    def remove_entries(base, manifest, keep=None):
        keep = keep or set()
        base = base.resolve()
        for entry in manifest.get("files", {}).values():
            path = (base / entry["relative_path"]).resolve()
            if not path.is_relative_to(base):
                raise ChatStorageError("Caminho de limpeza do documento inválido.")
            if path in keep or not path.is_file():
                continue
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ChatStorageError(
                    "Um documento da pasta de rede foi alterado. A limpeza ficou pendente."
                )
            path.unlink()
            parent = path.parent
            while parent != base and parent.is_relative_to(base):
                try:
                    parent.rmdir()
                except OSError:
                    break
                parent = parent.parent
        for prefix, kind in (("GNR", "guia"), ("CMP", "comprovante"), ("GNR_CMP", "combined")):
            entry = manifest.get("files", {}).get(kind)
            path = base / f"{prefix}_{manifest.get('cte')}.pdf"
            if (
                entry
                and path.resolve() not in keep
                and path.is_file()
                and hashlib.sha256(path.read_bytes()).hexdigest() == entry["sha256"]
            ):
                path.unlink()

    def cleanup(self, row):
        try:
            base = self.files.directory(row["cte"])
            manifest = self.manifest(base)
            if not manifest:
                return
            if manifest.get("cte") != row["cte"] or manifest.get("generation") != str(
                row["generation"]
            ):
                raise ChatStorageError(
                    "A pasta de rede contém outra revisão do documento. A limpeza ficou pendente."
                )
            for kind in ("guia", "comprovante", "combined"):
                if row.get(kind):
                    self.files.read(row["cte"], row[kind])
            self.remove_entries(base, manifest)
            (base / MANIFEST).unlink(missing_ok=True)
            try:
                base.rmdir()
            except OSError:
                pass
        except OSError:
            raise ChatStorageError(
                "Chamado confirmado; limpeza da cópia de rede pendente."
            ) from None
