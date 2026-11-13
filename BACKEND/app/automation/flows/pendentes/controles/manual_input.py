import asyncio
import base64
import binascii
import re
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.automation.cancellation import run_blocking
from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.data.consulta_db import fetch_rows_by_documents
from app.data.consulta_reader import read_rows
from app.domain.models import ManualSpreadsheetInput, RunStartRequest
from app.infrastructure.json_store import write_json

MAX_SPREADSHEET_BYTES = 12 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xlsm"}


class ManualInputResolver:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

    async def apply(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
        db_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        sequence_rows = self._rows_from_sequence(request.manual_ctes, config)
        spreadsheet_rows, spreadsheet_file, sheet_name = self._rows_from_spreadsheet(
            request.manual_spreadsheet,
            config,
        )
        rows = self._dedupe_rows([*spreadsheet_rows, *sequence_rows])
        if not rows:
            return config
        rows = await self._enrich_from_sql(rows, db_config or {}, run_id)

        output_file = self._manual_json_file(run_id)
        write_json(
            output_file,
            {
                "generatedAt": datetime.now(UTC).isoformat(),
                "sourceKind": "manual_operador",
                "sourceFile": str(spreadsheet_file or output_file),
                "sheetName": sheet_name or "Sequência manual",
                "sequenceCount": len(sequence_rows),
                "spreadsheetCount": len(spreadsheet_rows),
                "cteIdCount": self._cte_id_count(rows),
                "total": len(rows),
                "rows": rows,
            },
        )
        await emit_step(
            self.emit,
            run_id,
            "pendentes.manual_input",
            f"Entrada manual carregada: {len(rows)} CTE(s).",
            {
                "sourceJson": str(output_file),
                "spreadsheetFile": str(spreadsheet_file or ""),
                "sequenceCount": len(sequence_rows),
                "spreadsheetCount": len(spreadsheet_rows),
                "cteIdCount": self._cte_id_count(rows),
                "total": len(rows),
            },
        )
        return {
            **config,
            "sourceJson": str(output_file),
            "refreshSql": False,
            "refreshNovelisRelatorio": False,
            "refreshNovelisRelatorioAfterChamados": False,
        }

    async def _enrich_from_sql(
        self,
        rows: list[dict[str, Any]],
        db_config: dict[str, Any],
        run_id: str,
    ) -> list[dict[str, Any]]:
        missing = [row for row in rows if not self._first(row, "cteId", "CTE_ID")]
        if not missing:
            return rows
        if not db_config.get("enabled"):
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.manual_sql_disabled",
                f"Entrada manual tem {len(missing)} CTE(s) sem CTE_ID; consulta SQL esta desabilitada.",
            )
            return rows
        bound_seconds = (
            int(db_config.get("connectionTimeoutMs") or 15_000)
            + int(db_config.get("requestTimeoutMs") or 20_000)
        ) / 1000 + 10
        try:
            result = await asyncio.wait_for(
                run_blocking(fetch_rows_by_documents, db_config, missing),
                timeout=bound_seconds,
            )
        except TimeoutError:
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.manual_sql_timeout",
                (
                    f"Consulta SQL para completar CTE_ID nao respondeu em {bound_seconds:.0f}s "
                    "(banco pode estar inacessivel). Continuando sem enriquecimento."
                ),
            )
            return rows
        except Exception as exc:
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.manual_sql_failed",
                f"Consulta SQL para completar CTE_ID falhou: {exc}",
            )
            return rows

        error_count = int(result.source.get("manualLookupErrorCount") or 0)
        if error_count:
            await emit_warn(
                self.emit,
                run_id,
                "pendentes.manual_sql_partial_failed",
                f"Consulta SQL manual teve {error_count} falha(s) isolada(s); o lote continuou.",
                {"source": result.source},
            )

        enriched = self._merge_sql_rows(rows, result.rows)
        found = self._cte_id_count(enriched) - self._cte_id_count(rows)
        still_missing = len([row for row in enriched if not self._first(row, "cteId", "CTE_ID")])
        await emit_step(
            self.emit,
            run_id,
            "pendentes.manual_sql",
            f"Consulta SQL manual: {found} CTE_ID encontrado(s), {still_missing} sem chave.",
            {"found": found, "missing": still_missing, "source": result.source},
        )
        return enriched

    def _merge_sql_rows(
        self,
        manual_rows: list[dict[str, Any]],
        sql_rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        sql_by_key = {self._row_key(row): row for row in sql_rows}
        merged_rows: list[dict[str, Any]] = []
        for row in manual_rows:
            sql_row = sql_by_key.get(self._row_key(row))
            if not sql_row:
                merged_rows.append(row)
                continue
            cte_id = self._first(row, "cteId", "CTE_ID") or self._first(sql_row, "cteId", "CTE_ID")
            merged = {
                **sql_row,
                **row,
                "status": row.get("status") or "AGUARDANDO_MANUAL",
                "__sql": {**sql_row.get("__sql", {}), "manualLookup": True},
            }
            if cte_id:
                merged["cteId"] = cte_id
                merged["CTE_ID"] = cte_id
            merged_rows.append(merged)
        return merged_rows

    def _rows_from_sequence(self, raw_value: str, config: dict[str, Any]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for item in re.split(r"[\r\n,]+", str(raw_value or "")):
            scanned = self._scan_cte_rows(item)
            if len(scanned) > 1:
                rows.extend({**row, "sourceKind": "manual_sequence"} for row in scanned)
                continue
            row = self._normalize_manual_row(item, config)
            if row:
                rows.append({**row, "sourceKind": "manual_sequence"})
            elif scanned:
                rows.extend({**item, "sourceKind": "manual_sequence"} for item in scanned)
        return rows

    def _rows_from_spreadsheet(
        self,
        spreadsheet: ManualSpreadsheetInput | None,
        config: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], Path | None, str]:
        if spreadsheet is None:
            return [], None, ""
        file_path = self._save_spreadsheet(spreadsheet)
        rows, sheet_name = read_rows(file_path)
        header_index = self._header_index(rows)
        headers = self._headers(rows[header_index]) if header_index >= 0 else []
        data_rows = rows[header_index + 1 :] if header_index >= 0 else rows
        parsed: list[dict[str, Any]] = []
        for offset, row in enumerate(data_rows, start=(header_index + 2 if header_index >= 0 else 1)):
            if not row or all(not str(value or "").strip() for value in row):
                continue
            row_map = self._row_map(headers, row)
            item = self._normalize_manual_row(row_map, config)
            if item:
                parsed.append(
                    {
                        **row_map,
                        **item,
                        "sourceKind": "manual_spreadsheet",
                        "sourceSheet": sheet_name,
                        "sheetRow": offset,
                    }
                )
        return parsed, file_path, sheet_name

    def _save_spreadsheet(self, spreadsheet: ManualSpreadsheetInput) -> Path:
        filename = self._safe_filename(spreadsheet.filename)
        suffix = Path(filename).suffix.lower() or ".xlsx"
        if suffix not in SUPPORTED_EXTENSIONS:
            raise RuntimeError("Planilha manual precisa ser .xlsx, .xlsm ou .csv.")
        content = self._decode_base64(spreadsheet.content_base64)
        if not content:
            raise RuntimeError("Planilha manual está vazia.")
        if len(content) > MAX_SPREADSHEET_BYTES:
            raise RuntimeError("Planilha manual excede 12 MB.")
        output_dir = self.cwd / "captures" / "pendentes" / "manual-inputs"
        output_dir.mkdir(parents=True, exist_ok=True)
        target = output_dir / f"{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{filename}"
        target.write_bytes(content)
        return target

    def _decode_base64(self, raw_value: str) -> bytes:
        raw = str(raw_value or "").strip()
        if "," in raw and "base64" in raw.split(",", 1)[0].lower():
            raw = raw.split(",", 1)[1]
        try:
            return base64.b64decode(raw, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise RuntimeError("Conteúdo da planilha manual está inválido.") from exc

    def _normalize_manual_row(self, value: Any, config: dict[str, Any]) -> dict[str, Any] | None:
        if isinstance(value, dict):
            return self._normalize_dict_row(value, config)
        row = self._row_from_cte(str(value or ""), config)
        return {**row, "status": "AGUARDANDO_MANUAL"} if row else None

    def _normalize_dict_row(self, row: dict[str, Any], config: dict[str, Any]) -> dict[str, Any] | None:
        cte_id_row = self._row_from_cte(self._first(row, "CTE_ID", "ID_CTE", "CHAVE_ACESSO", "ID"), config)
        cte_text_row = self._row_from_cte(self._first(row, "CTE", "NUMERO_CTE", "NUMEROCTE"), config)
        parsed = cte_id_row or cte_text_row or {}
        filial = self._part(self._first(row, "FILIAL") or parsed.get("filial") or config.get("defaultFilial"))
        serie = self._part(self._first(row, "SERIE") or parsed.get("serie") or config.get("defaultSerie") or "10")
        documento = self._part(
            self._first(row, "DOCUMENTO", "NCT", "N_CT", "NUMERO", "NROCTE", "CTRC")
            or parsed.get("documento")
        )
        if not filial or not serie or not documento:
            return None
        out = {
            "filial": filial,
            "serie": serie,
            "documento": documento,
            "status": self._first(row, "STATUS", "FEITO") or "AGUARDANDO_MANUAL",
        }
        cte_id = parsed.get("cteId")
        if cte_id:
            out["cteId"] = cte_id
        return out

    def _row_from_cte(self, raw_value: Any, config: dict[str, Any]) -> dict[str, Any] | None:
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
        parts = [part for part in re.split(r"[-/;\s]+", raw) if part]
        if len(parts) >= 3:
            return {"filial": self._part(parts[0]), "serie": self._part(parts[1]), "documento": self._part(parts[2])}
        if len(parts) == 1 and parts[0].isdigit() and config.get("defaultFilial"):
            return {
                "filial": self._part(config.get("defaultFilial")),
                "serie": self._part(config.get("defaultSerie") or "10"),
                "documento": self._part(parts[0]),
            }
        return None

    def _scan_cte_rows(self, raw_value: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for match in re.finditer(r"(?<!\d)(\d{1,6})[-/;\s]+(\d{1,4})[-/;\s]+(\d{1,12})(?!\d)", raw_value):
            rows.append(
                {
                    "filial": self._part(match.group(1)),
                    "serie": self._part(match.group(2)),
                    "documento": self._part(match.group(3)),
                    "status": "AGUARDANDO_MANUAL",
                }
            )
        return rows

    def _header_index(self, rows: list[list[Any]]) -> int:
        known = {"FILIAL", "SERIE", "DOCUMENTO", "NCT", "N_CT", "CTE", "CTE_ID", "CHAVE_ACESSO", "ID"}
        for index, row in enumerate(rows[:10]):
            headers = set(self._headers(row))
            if headers & known:
                return index
        return -1

    def _headers(self, row: list[Any]) -> list[str]:
        return [self._header(value) or f"COL_{index + 1}" for index, value in enumerate(row)]

    def _row_map(self, headers: list[str], row: list[Any]) -> dict[str, Any]:
        if not headers:
            headers = ["FILIAL", "SERIE", "DOCUMENTO"]
        out: dict[str, Any] = {}
        for index, value in enumerate(row):
            key = headers[index] if index < len(headers) else f"COL_{index + 1}"
            out[key] = value
        return out

    def _dedupe_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        seen: set[str] = set()
        for row in rows:
            key = f"{row['filial']}|{row['serie']}|{row['documento']}"
            if key in seen:
                continue
            seen.add(key)
            out.append({**row, "cte": f"{row['filial']}-{row['serie']}-{row['documento']}", "key": key})
        return out

    def _cte_id_count(self, rows: list[dict[str, Any]]) -> int:
        return len([row for row in rows if self._first(row, "cteId", "CTE_ID")])

    def _row_key(self, row: dict[str, Any]) -> str:
        return f"{self._part(row.get('filial'))}|{self._part(row.get('serie'))}|{self._part(row.get('documento'))}"

    def _manual_json_file(self, run_id: str) -> Path:
        safe_run_id = re.sub(r"[^A-Za-z0-9_.-]+", "-", run_id).strip("-") or "run"
        return self.cwd / "captures" / "pendentes" / "manual-inputs" / f"{safe_run_id}.json"

    def _first(self, row: dict[str, Any], *keys: str) -> str:
        for key in keys:
            value = row.get(key)
            if value is not None and str(value).strip():
                return str(value).strip()
        return ""

    def _part(self, value: Any) -> str:
        digits = re.sub(r"\D+", "", str(value or ""))
        return digits.lstrip("0") or digits or str(value or "").strip().upper()

    def _header(self, value: Any) -> str:
        text = unicodedata.normalize("NFD", str(value or ""))
        text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
        return re.sub(r"[^A-Z0-9]+", "_", text.upper()).strip("_")

    def _safe_filename(self, value: str) -> str:
        name = Path(str(value or "planilha-manual.xlsx")).name
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip(".-")
        return safe or "planilha-manual.xlsx"
