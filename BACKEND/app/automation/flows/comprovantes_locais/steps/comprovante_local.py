import re
import shutil
from pathlib import Path
from typing import Any

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.data.consulta_reader import read_consulta_rows
from app.domain.models import RunStartRequest
from app.infrastructure.json_store import read_json, write_json


class ComprovanteLocalFlow:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

    async def run(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> dict[str, Any]:
        rows = self._load_rows(config, request)
        if not rows:
            await emit_warn(
                self.emit,
                run_id,
                "comprovante_local.no_rows",
                "Nenhum CTE encontrado para buscar comprovantes locais.",
            )
            return self._result(config, [], [], [])

        source_dir = self._resolve(config.get("sourceDir") or "")
        if not source_dir.exists():
            await emit_warn(
                self.emit,
                run_id,
                "comprovante_local.source_missing",
                f"Pasta de comprovantes não encontrada: {source_dir}",
            )
            return self._result(config, rows, [], rows)

        files = self._list_files(source_dir)
        prefixes = self._prefixes(config)
        copied: list[dict[str, str]] = []
        missing: list[dict[str, Any]] = []
        await emit_step(
            self.emit,
            run_id,
            "comprovante_local.started",
            f"Buscando comprovantes locais para {len(rows)} CTE(s).",
            {"sourceDir": str(source_dir), "prefixes": prefixes},
        )

        for index, row in enumerate(rows):
            cte = self._cte_code(row)
            await emit_step(
                self.emit,
                run_id,
                "comprovante_local.progress",
                f"Comprovantes {index + 1}/{len(rows)}: {cte}.",
                {"current": index + 1, "total": len(rows), "cte": cte},
            )
            await emit_step(
                self.emit,
                run_id,
                "comprovante_local.row_started",
                f"Buscando comprovantes para {cte}.",
                {"row": row, "cte": cte},
            )
            found = self._find_for_row(files, prefixes, row)
            if not found:
                missing.append(row)
                await emit_warn(
                    self.emit,
                    run_id,
                    "comprovante_local.row_missing",
                    f"Nenhum comprovante local encontrado para {cte}.",
                    {"row": row, "cte": cte},
                )
                continue
            target_dir = self._target_dir(config, row)
            await emit_step(
                self.emit,
                run_id,
                "comprovante_local.row_found",
                f"{len(found)} comprovante(s) encontrado(s) para {cte}.",
                {"row": row, "cte": cte, "targetDir": str(target_dir), "files": [str(file) for file in found]},
            )
            if request.dry_run:
                copied.extend(
                    {"cte": cte, "source": str(file), "target": str(target_dir / file.name)}
                    for file in found
                )
                continue
            target_dir.mkdir(parents=True, exist_ok=True)
            for file in found:
                target = target_dir / file.name
                if self._copy_if_needed(file, target):
                    copied.append({"cte": cte, "source": str(file), "target": str(target)})
                    await emit_step(
                        self.emit,
                        run_id,
                        "comprovante_local.file_copied",
                        f"Comprovante copiado: {target.name}.",
                        {"cte": cte, "source": str(file), "target": str(target)},
                    )
                else:
                    await emit_step(
                        self.emit,
                        run_id,
                        "comprovante_local.file_exists",
                        f"Comprovante já existia no destino: {target.name}.",
                        {"cte": cte, "source": str(file), "target": str(target)},
                    )

        result = self._result(config, rows, copied, missing)
        write_json(self._resolve(config.get("outputFile") or "captures/comprovantes-local.json"), result)
        await emit_step(
            self.emit,
            run_id,
            "comprovante_local.completed",
            (
                f"Comprovantes locais: verificados={len(rows)} | "
                f"encontrados={len(copied)} | sem_comprovante={len(missing)}."
            ),
            result,
        )
        return result
    def _load_rows(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
    ) -> list[dict[str, Any]]:
        config_rows = config.get("rows")
        if isinstance(config_rows, list) and config_rows:
            return [row for row in (self._normalize_row(item, config) for item in config_rows) if row]

        request_row = self._request_row(request, config)
        if request_row:
            return [request_row]

        result_file = self._resolve(config.get("resultFile") or "")
        payload = read_json(result_file, {})
        rows = payload.get("rows") if isinstance(payload, dict) else None
        if isinstance(rows, list) and rows:
            return [row for row in (self._normalize_row(item, config) for item in rows) if row]

        try:
            consulta = read_consulta_rows(config, self.cwd)
        except Exception:
            return []
        return [row for row in (self._normalize_row(item, config) for item in consulta.records) if row]

    def _request_row(
        self,
        request: RunStartRequest,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        cte_row = self._row_from_cte(request.sample_cte, config)
        if cte_row:
            return cte_row

        filial = request.sample_filial.strip()
        documento = request.sample_documento.strip()
        if not filial or not documento:
            return None
        return {
            "filial": filial,
            "serie": str(config.get("defaultSerie") or "10").strip(),
            "documento": documento,
        }

    def _row_from_cte(
        self,
        raw_value: str,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        raw = str(raw_value or "").strip()
        if not raw:
            return None
        digits = re.sub(r"\D+", "", raw.replace("CTe", ""))
        if len(digits) == 44:
            cnpj = digits[6:20]
            return {
                "filial": self._key_part(cnpj[8:12]),
                "serie": self._key_part(digits[22:25]),
                "documento": self._key_part(digits[25:34]),
            }
        parts = [part for part in re.split(r"[-/\s]+", raw) if part]
        if len(parts) >= 3:
            return {
                "filial": self._key_part(parts[0]),
                "serie": self._key_part(parts[1]),
                "documento": self._key_part("".join(parts[2:])),
            }
        if len(parts) == 1 and parts[0].isdigit() and config.get("defaultFilial"):
            return {
                "filial": str(config.get("defaultFilial") or "").strip(),
                "serie": str(config.get("defaultSerie") or "10").strip(),
                "documento": parts[0],
            }
        return None

    def _find_for_row(
        self,
        files: list[Path],
        prefixes: list[str],
        row: dict[str, Any],
    ) -> list[Path]:
        targets = {self._base_key(f"{prefix}_{self._cte_code(row)}") for prefix in prefixes}
        found = []
        for file in files:
            if self._base_key(file.stem) in targets:
                found.append(file)
        return found

    def _list_files(self, directory: Path) -> list[Path]:
        out: list[Path] = []
        stack = [directory]
        allowed = {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"}
        while stack:
            current = stack.pop()
            try:
                entries = list(current.iterdir())
            except OSError:
                continue
            for entry in entries:
                if entry.is_dir():
                    stack.append(entry)
                elif entry.is_file() and entry.suffix.lower() in allowed:
                    out.append(entry)
        return out

    def _copy_if_needed(self, source: Path, target: Path) -> bool:
        if target.exists():
            try:
                if target.stat().st_size == source.stat().st_size:
                    return False
            except OSError:
                pass
        shutil.copy2(source, target)
        return True

    def _target_dir(self, config: dict[str, Any], row: dict[str, Any]) -> Path:
        base = self._resolve(config.get("targetDir") or "captures/tarifario-downloads")
        return base / f"cte-{self._slug(row.get('documento'))}"

    def _normalize_row(
        self,
        row: dict[str, Any],
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        filial = str(row.get("filial") or row.get("FILIAL") or config.get("defaultFilial") or "").strip()
        serie = str(row.get("serie") or row.get("SERIE") or config.get("defaultSerie") or "10").strip()
        documento = str(row.get("documento") or row.get("DOCUMENTO") or row.get("nCT") or "").strip()
        if not filial or not serie or not documento:
            return None
        return {**row, "filial": filial, "serie": serie, "documento": documento}

    def _result(
        self,
        config: dict[str, Any],
        rows: list[dict[str, Any]],
        copied: list[dict[str, str]],
        missing: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "sourceDir": str(self._resolve(config.get("sourceDir") or "")),
            "targetDir": str(self._resolve(config.get("targetDir") or "")),
            "checked": len(rows),
            "found": len(copied),
            "missing": [self._cte_code(row) for row in missing],
            "files": copied,
        }

    def _prefixes(self, config: dict[str, Any]) -> list[str]:
        raw = str(config.get("prefixes") or "GNR,CMP")
        return [item.strip().upper() for item in raw.split(",") if item.strip()]

    def _cte_code(self, row: dict[str, Any]) -> str:
        return "-".join([self._key_part(row.get("filial")), self._key_part(row.get("serie")), self._key_part(row.get("documento"))])

    def _key_part(self, value: Any) -> str:
        digits = re.sub(r"\D+", "", str(value or ""))
        return digits.lstrip("0") or digits or str(value or "").strip().upper()

    def _base_key(self, value: str) -> str:
        return re.sub(r"[^A-Z0-9]+", "-", str(value or "").upper()).strip("-")

    def _slug(self, value: Any) -> str:
        return re.sub(r"[^a-z0-9]+", "-", str(value or "item").lower()).strip("-") or "item"

    def _resolve(self, value: str) -> Path:
        path = Path(str(value or ""))
        return path if path.is_absolute() else self.cwd / path
