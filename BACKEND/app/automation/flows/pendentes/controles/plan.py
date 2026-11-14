import os
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.automation.cancellation import check_cancelled, run_blocking
from app.automation.flows.flow_events import Emit, emit_warn
from app.data.chamados_log import read_processed_ctes
from app.data.chamados_reader import load_chamado_rows, search_chamado_rows
from app.data.consulta_reader import read_consulta_rows
from app.domain.models import RunStartRequest
from app.infrastructure.json_store import read_json
from app.services.cte_xml_files import matching_xml_files
from app.services.cte_pdf_files import find_pdf_evidence


class PendentesPlanBuilder:
    def __init__(self, cwd: Path, emit: Emit, *, cache_directories: bool = False) -> None:
        self.cwd = cwd
        self.emit = emit
        self._directory_files = {} if cache_directories else None

    async def build(
        self,
        config: dict[str, Any],
        rodopar_config: dict[str, Any],
        xml_config: dict[str, Any],
        comprovante_config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        chamado_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        target_row = self._request_row(request, rodopar_config)
        rows, source_file, sheet_name = await self._input_rows(config, rodopar_config, run_id, target_row)
        normalized_rows = [row for row in (self._normalize_row(item, rodopar_config) for item in rows) if row]
        if target_row:
            target_key = self._row_key(target_row)
            selected_rows = [row for row in normalized_rows if self._row_key(row) == target_key]
            normalized_rows = selected_rows or [target_row]
        total_consultados = len(normalized_rows)

        # Everything below is synchronous filesystem/network I/O (the ledger file,
        # the existing-chamado report/snapshot, and — the expensive part — an
        # iterdir() per row per evidence directory against a \\...\ network share).
        # Run it off-thread: done inline, it blocks the whole event loop for as
        # long as the network scan takes, which starves other requests on this
        # same process — including the desktop wrapper's own health-check ping,
        # which reads that as "backend is dead" and force-kills it mid-run.
        normalized_rows, checked = await run_blocking(
            self._filter_and_check_rows,
            normalized_rows,
            target_row,
            chamado_config,
            rodopar_config,
            xml_config,
            comprovante_config,
            request.execution_scope == "xml" and bool(request.manual_ctes or request.manual_spreadsheet),
        )

        faltando_pdf = [item["cte"] for item in checked if not item["evidence"]["pdfFile"]]
        faltando_xml = [item["cte"] for item in checked if not item["evidence"]["xmlFile"]]
        faltando_comprovante = [
            item["cte"]
            for item in checked
            if self._has_pdf_xml(item) and not item["evidence"]["comprovanteOk"]
        ]
        skip_chamado_missing_comprovante = request.pendentes_skip_chamado_missing_comprovante
        prontos_chamado = [
            item["cte"]
            for item in checked
            if self._has_pdf_xml(item)
            and (item["evidence"]["comprovanteOk"] or not skip_chamado_missing_comprovante)
        ]

        return {
            "generatedAt": datetime.now(UTC).isoformat(),
            "sourceFile": source_file,
            "sheetName": sheet_name,
            "consultados": total_consultados,
            "filtradosFora": total_consultados - len(normalized_rows),
            "total": len(checked),
            "faltandoPdf": faltando_pdf,
            "faltandoXml": faltando_xml,
            "faltandoComprovante": faltando_comprovante,
            "prontosComprovante": [item["cte"] for item in checked if self._has_pdf_xml(item)],
            "prontosChamado": prontos_chamado,
            "skipChamadoMissingComprovante": skip_chamado_missing_comprovante,
            "rows": [item["row"] for item in checked],
            "checked": checked,
        }

    def _filter_and_check_rows(
        self,
        normalized_rows: list[dict[str, Any]],
        target_row: dict[str, Any] | None,
        chamado_config: dict[str, Any] | None,
        rodopar_config: dict[str, Any],
        xml_config: dict[str, Any],
        comprovante_config: dict[str, Any],
        explicit_xml: bool = False,
    ) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        check_cancelled()
        if target_row or explicit_xml:
            # Modo teste / campos manuais: the user explicitly named this one CTE, so
            # none of the "already done" bookkeeping below (pending-row status, the
            # processed-chamado ledger, the existing-chamado exclusion) should silently
            # drop it — that would defeat the point of a deliberate manual test run.
            pass
        else:
            normalized_rows = self._pending_rows(normalized_rows)

            processed = read_processed_ctes((chamado_config or {}).get("chamadosLogFile"))
            if processed:
                normalized_rows = [
                    row for row in normalized_rows if not self._is_already_processed(row, processed)
                ]

            normalized_rows = self._exclude_existing_chamados(normalized_rows, chamado_config)

        checked = []
        for normalized in self._dedupe_rows(normalized_rows):
            check_cancelled()
            cte = self._cte_key(normalized)
            row = {**normalized, "cte": cte, "key": self._row_key(normalized)}
            evidence = self.resolve_evidence(row, rodopar_config, xml_config, comprovante_config)
            checked.append({"cte": cte, "row": row, "evidence": evidence})
        return normalized_rows, checked

    async def _input_rows(
        self,
        config: dict[str, Any],
        rodopar_config: dict[str, Any],
        run_id: str,
        fallback_row: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], str, str]:
        source_json = self._resolve(config.get("sourceJson") or "")
        if source_json.is_file():
            rows = self._rows_from_json(source_json)
            return rows, str(source_json), "JSON"
        return await self._consulta_rows(rodopar_config, run_id, fallback_row)

    def _rows_from_json(self, source_json: Path) -> list[dict[str, Any]]:
        payload = read_json(source_json, {})
        if isinstance(payload, list):
            return [row for row in payload if isinstance(row, dict)]
        if not isinstance(payload, dict):
            return []
        rows = payload.get("rows") or payload.get("needed") or payload.get("items")
        return [row for row in rows if isinstance(row, dict)] if isinstance(rows, list) else []

    async def _consulta_rows(
        self,
        rodopar_config: dict[str, Any],
        run_id: str,
        fallback_row: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], str, str]:
        try:
            consulta = await run_blocking(read_consulta_rows, rodopar_config, self.cwd)
        except Exception as exc:
            await emit_warn(self.emit, run_id, "pendentes.consulta_failed", f"CONSULTA falhou: {exc}")
            if fallback_row:
                return [fallback_row], "", ""
            raise RuntimeError(
                "Fonte de consulta indisponivel. Verifique a configuracao SQL e o arquivo CONSULTA."
            ) from exc
        return consulta.records, consulta.source_file, consulta.sheet_name

    def _has_pdf_xml(self, item: dict[str, Any]) -> bool:
        evidence = item["evidence"]
        return bool(evidence["pdfFile"] and evidence["xmlFile"])

    def resolve_evidence(
        self,
        row: dict[str, Any],
        rodopar_config: dict[str, Any],
        xml_config: dict[str, Any],
        comprovante_config: dict[str, Any],
    ) -> dict[str, Any]:
        pdf_file = find_pdf_evidence(
            self._resolve(rodopar_config.get("downloadTargetDir") or "captures/rodopar-pdfs-downloads"), row,
        )
        xml_directory = self._resolve(xml_config.get("downloadDir") or "captures/cte-fazenda-downloads")
        xml_files = matching_xml_files(xml_directory, row, entries=(
            self._all_files(xml_directory, {".xml"}) if self._directory_files is not None else None))
        comprovante_files = self._files_for_row(
            row,
            [self._resolve(comprovante_config.get("targetDir") or "captures/tarifario-downloads")],
            {".pdf", ".png", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".webp"},
        )
        zip_prefixes = self._prefixes(comprovante_config.get("zipPrefixes") or comprovante_config.get("prefixes"))
        comprovante_zip_files = [
            file for file in comprovante_files if self._matches_prefix(file.name, zip_prefixes)
        ]
        requires_comprovante = self._requires_comprovante(row)
        has_guia = any(self._matches_prefix(file.name, ["GNR"]) for file in comprovante_files)
        has_comprovante_file = any(self._matches_prefix(file.name, ["CMP"]) for file in comprovante_files)
        comprovante_ok = not requires_comprovante or (has_guia and has_comprovante_file)
        return {
            "pdfFile": str(pdf_file or ""),
            "xmlFile": str(next(iter(xml_files), "")),
            "comprovanteFiles": [str(file) for file in comprovante_files],
            "comprovanteZipFiles": [str(file) for file in comprovante_zip_files],
            "requiresComprovante": requires_comprovante,
            "hasGuia": has_guia,
            "hasComprovanteFile": has_comprovante_file,
            "comprovanteOk": comprovante_ok,
        }

    def _requires_comprovante(self, row: dict[str, Any]) -> bool:
        if "requiresComprovante" in row:
            return bool(row["requiresComprovante"])
        value = (
            row.get("nmgnre")
            or row.get("NMGNRE")
            or row.get("nmgre")
            or row.get("NMGRE")
        )
        return bool(str(value or "").strip())

    def _prefixes(self, raw: Any) -> list[str]:
        return [item.strip().upper() for item in str(raw or "").split(",") if item.strip()]

    def _matches_prefix(self, filename: str, prefixes: list[str]) -> bool:
        if not prefixes:
            return True
        stem = re.sub(r"[^A-Z0-9]+", "_", Path(filename).stem.upper()).strip("_")
        return any(stem == prefix or stem.startswith(f"{prefix}_") for prefix in prefixes)

    def _files_for_row(self, row: dict[str, Any], roots: list[Path], extensions: set[str]) -> list[Path]:
        files = []
        doc = self._part(row.get("documento"))
        for directory in roots:
            check_cancelled()
            if not directory.exists():
                continue
            files.extend(self._matched_files(directory, doc, extensions))
            cte_dir = directory / f"cte-{self._slug(doc)}"
            if cte_dir.exists():
                files.extend(self._all_files(cte_dir, extensions))
        return self._dedupe_files(files)

    def _matched_files(self, directory: Path, doc: str, extensions: set[str]) -> list[Path]:
        if not doc:
            return []
        entries = self._all_files(directory, extensions)
        return [item for item in entries if doc in self._part(item.name)]

    def _all_files(self, directory: Path, extensions: set[str]) -> list[Path]:
        cache_key = (directory, tuple(sorted(extensions)))
        if self._directory_files is not None and cache_key in self._directory_files:
            return self._directory_files[cache_key]
        try:
            files = []
            with os.scandir(directory) as entries:
                for entry in entries:
                    check_cancelled()
                    item = Path(entry.path)
                    if item.suffix.lower() in extensions and entry.is_file():
                        files.append(item)
            if self._directory_files is not None:
                self._directory_files[cache_key] = files
            return files
        except FileNotFoundError:
            return []
        except OSError:
            if self._directory_files is not None:
                raise
            return []

    def _request_row(self, request: RunStartRequest, config: dict[str, Any]) -> dict[str, Any] | None:
        cte_row = self._row_from_cte(request.sample_cte, config)
        if cte_row:
            return cte_row
        filial = str(request.sample_filial or "").strip()
        documento = str(request.sample_documento or "").strip()
        if not filial or not documento:
            return None
        return {
            "filial": self._part(filial),
            "serie": self._part(config.get("defaultSerie") or "10"),
            "documento": self._part(documento),
        }

    def _row_from_cte(self, raw_value: str, config: dict[str, Any]) -> dict[str, Any] | None:
        raw = str(raw_value or "").strip()
        if not raw:
            return None
        digits = re.sub(r"\D+", "", raw.replace("CTe", ""))
        if len(digits) == 44:
            cnpj = digits[6:20]
            return {
                "filial": self._part(cnpj[8:12]),
                "serie": self._part(digits[22:25]),
                "documento": self._part(digits[25:34]),
                "cteId": digits,
            }
        parts = [part for part in re.split(r"[-/\s,;]+", raw) if part]
        if len(parts) >= 3:
            return {
                "filial": self._part(parts[0]),
                "serie": self._part(parts[1]),
                "documento": self._part("".join(parts[2:])),
            }
        if len(parts) == 1 and parts[0].isdigit() and config.get("defaultFilial"):
            return {
                "filial": self._part(config.get("defaultFilial")),
                "serie": self._part(config.get("defaultSerie") or "10"),
                "documento": self._part(parts[0]),
            }
        return None

    def _normalize_row(self, row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
        filial = self._part(row.get("filial") or row.get("FILIAL") or config.get("defaultFilial") or "")
        serie = self._part(row.get("serie") or row.get("SERIE") or config.get("defaultSerie") or "10")
        documento = self._part(
            row.get("documento")
            or row.get("DOCUMENTO")
            or row.get("nCT")
            or row.get("NCT")
            or row.get("numeroCte")
            or ""
        )
        if not filial or not serie or not documento:
            return None
        return {**row, "filial": filial, "serie": serie, "documento": documento}

    def _pending_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [row for row in rows if self._is_pending_row(row)]

    def _is_pending_row(self, row: dict[str, Any]) -> bool:
        novelis = row.get("__novelis") if isinstance(row.get("__novelis"), dict) else {}
        if novelis.get("alreadyExists"):
            return False
        if self._has_chamado(row):
            return False
        status = self._row_status(row)
        if not status or "AGUARDANDO" in status:
            return True
        done_tokens = ("CONCLUID", "SOLUCIONAD", "FINALIZAD", "PROCESSAD", "FEITO")
        return not any(token in status for token in done_tokens)

    def _has_chamado(self, row: dict[str, Any]) -> bool:
        chamado = self._status_token(row.get("chamado") or row.get("CHAMADO") or "")
        if not chamado or chamado in {"NAO", "N", "FALSE"}:
            return False
        if chamado.startswith("SIM"):
            return True
        chamado_id = row.get("chamadoNumero") or row.get("chamadoId") or row.get("CHAMADO_ID")
        if str(chamado_id or "").strip():
            return True
        return chamado not in {"SEM_CHAMADO", "NAO_CONSTA", "PENDENTE"}

    def _row_status(self, row: dict[str, Any]) -> str:
        return self._status_token(row.get("status") or row.get("STATUS") or row.get("feito") or row.get("FEITO"))

    def _status_token(self, value: Any) -> str:
        text = unicodedata.normalize("NFD", str(value or ""))
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")

    def _dedupe_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = self._row_key(row)
            if key in seen:
                continue
            seen.add(key)
            out.append(row)
        return out

    def _dedupe_files(self, files: list[Path]) -> list[Path]:
        out: list[Path] = []
        seen: set[str] = set()
        for file in files:
            key = str(file.resolve(strict=False)).lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(file)
        return out

    def _exclude_existing_chamados(
        self,
        rows: list[dict[str, Any]],
        chamado_config: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        # Catches chamados the automation's own ledger doesn't know about yet (opened
        # manually, opened before that ledger existed, or opened by another machine
        # whose local pendentes cache never reached this one) so the PDF/XML never even
        # get downloaded for a CTE that already has a chamado in Novelis.
        config = chamado_config or {}
        report_path = config.get("relatorioCteXmlJsonFile")
        snapshot_path = config.get("chamadosSnapshotFile")
        try:
            chamado_rows = load_chamado_rows(self.cwd, report_path, snapshot_path)
        except Exception:
            return rows
        kept = []
        for row in rows:
            check_cancelled()
            hit = search_chamado_rows(
                chamado_rows, row.get("filial"), row.get("serie"), row.get("documento"), row.get("cteId")
            )
            if hit:
                continue
            kept.append(row)
        return kept

    def _is_already_processed(self, row: dict[str, Any], processed: dict[str, dict[str, Any]]) -> bool:
        entry = processed.get(self._cte_key(row))
        if not entry:
            return False
        row_cte_id = self._part(row.get("cteId"))
        entry_cte_id = self._part(entry.get("cteId"))
        if row_cte_id and entry_cte_id:
            # Same reuse problem as _exclude_existing_chamados: serie+documento
            # numbers get recycled across branches/years, so an old ledger entry
            # sharing that pair isn't proof it's the same CT-e. Once both sides
            # carry the actual chave, that's the only thing worth trusting.
            return row_cte_id == entry_cte_id
        return True

    def _cte_key(self, row: dict[str, Any]) -> str:
        return f"{self._part(row.get('filial'))}-{self._part(row.get('serie'))}-{self._part(row.get('documento'))}"

    def _row_key(self, row: dict[str, Any]) -> str:
        return self._cte_key(row).replace("-", "|")

    def _part(self, value: Any) -> str:
        digits = "".join(ch for ch in str(value or "") if ch.isdigit())
        return digits.lstrip("0") or digits or str(value or "").strip().upper()

    def _slug(self, value: Any) -> str:
        text = str(value or "item").strip().lower()
        return re.sub(r"[^a-z0-9]+", "-", text).strip("-") or "item"

    def _resolve(self, value: str) -> Path:
        path = Path(str(value or ""))
        return path if path.is_absolute() else self.cwd / path
