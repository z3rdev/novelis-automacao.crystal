import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.automation.flows.flow_events import Emit, emit_step, emit_warn
from app.automation.flows.novelis_chamados.steps.novelis import NovelisFlow
from app.domain.models import RunStartRequest
from app.infrastructure.json_store import read_json, write_json
from app.services.browser_driver import BrowserDriver


class ChamadoNovelisFlow:
    def __init__(self, cwd: Path, emit: Emit) -> None:
        self.cwd = cwd
        self.emit = emit

    async def run(
        self,
        browser: BrowserDriver | None,
        config: dict[str, Any],
        request: RunStartRequest,
        run_id: str,
    ) -> list[dict[str, Any]]:
        row = self._resolve_row(config, request)
        if not row:
            await emit_warn(
                self.emit,
                run_id,
                "chamado_novelis.no_cte",
                "Informe um CTE teste para abrir chamado Novelis.",
            )
            return []

        output_file = self._write_temp_tarifario(config, row)
        flow_config = {
            **config,
            "currentDocumento": row["documento"],
            "documentoFilter": row["documento"],
            "enableTarifarioStep": False,
            "openChamadoAfterTarifario": True,
            "tarifarioOutputFile": str(output_file),
            "chamadoTarifarioResultFile": str(output_file),
            "evidence": config.get("evidence", {}),
        }
        await emit_step(
            self.emit,
            run_id,
            "chamado_novelis.prepared",
            f"Chamado Novelis preparado para CTE {row['numeroCte']}.",
            {"row": row, "tarifarioOutputFile": str(output_file)},
        )
        result = await NovelisFlow(self.cwd, self.emit).run(browser, flow_config, request, run_id)
        return result or [row]

    def _resolve_row(
        self,
        config: dict[str, Any],
        request: RunStartRequest,
    ) -> dict[str, Any] | None:
        cte = str(config.get("ctes") or request.sample_cte or "").strip()
        target = self._parse_cte(cte, config)
        if not target:
            return None
        from_sources = self._lookup_sources(config, target)
        return {
            **from_sources,
            **target,
            "numeroCte": target["cte"],
            "rota": from_sources.get("rota") or self._route(from_sources),
        }

    def _lookup_sources(
        self,
        config: dict[str, Any],
        target: dict[str, Any],
    ) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for key in ("sourceJson", "tarifarioJson"):
            raw_path = str(config.get(key) or "").strip()
            if not raw_path:
                continue
            path = self._resolve(raw_path)
            if not path.is_file():
                continue
            payload = read_json(path, {})
            rows = payload.get("rows") if isinstance(payload, dict) else payload if isinstance(payload, list) else []
            for row in rows if isinstance(rows, list) else []:
                parsed = self._parse_cte(row, config)
                if parsed and parsed.get("key") == target["key"]:
                    out.update(row)
        return out

    def _parse_cte(
        self,
        value: Any,
        config: dict[str, Any],
    ) -> dict[str, Any] | None:
        if isinstance(value, dict):
            filial = self._part(value.get("filial") or value.get("FILIAL") or "")
            serie = self._part(value.get("serie") or value.get("SERIE") or config.get("defaultSerie") or "10")
            doc = self._part(
                value.get("documento") or value.get("DOCUMENTO") or value.get("nCT") or value.get("numeroCte") or ""
            )
        else:
            raw = str(value or "").strip()
            digits = re.sub(r"\D+", "", raw.replace("CTe", ""))
            if len(digits) == 44:
                cnpj = digits[6:20]
                filial, serie, doc = cnpj[8:12], digits[22:25], digits[25:34]
            else:
                parts = [part for part in re.split(r"[-/\s,;]+", raw) if part]
                if len(parts) >= 3:
                    filial, serie, doc = parts[0], parts[1], "".join(parts[2:])
                elif len(parts) == 1 and parts[0].isdigit() and config.get("defaultFilial"):
                    filial, serie, doc = config.get("defaultFilial"), config.get("defaultSerie") or "10", parts[0]
                else:
                    return None
            filial, serie, doc = self._part(filial), self._part(serie), self._part(doc)
        if not filial or not serie or not doc:
            return None
        cte = f"{filial}-{serie}-{doc}"
        return {"filial": filial, "serie": serie, "documento": doc, "cte": cte, "key": cte.replace("-", "|")}

    def _write_temp_tarifario(self, config: dict[str, Any], row: dict[str, Any]) -> Path:
        output_dir = self._resolve(config.get("outputDir") or "captures/novelis-chamados-direto")
        output_dir.mkdir(parents=True, exist_ok=True)
        path = output_dir / f"tarifario-{self._safe(row['numeroCte'])}.json"
        write_json(
            path,
            {
                "generatedAt": datetime.now(timezone.utc).isoformat(),
                "sourceKind": "python_chamado_novelis",
                "total": 1,
                "rows": [row],
            },
        )
        return path

    def _route(self, row: dict[str, Any]) -> str:
        origem = str(row.get("remCidade") or row.get("origem") or "").strip()
        destino = str(row.get("desCidade") or row.get("destino") or "").strip()
        return f"{origem} X {destino}" if origem and destino else ""

    def _part(self, value: Any) -> str:
        digits = re.sub(r"\D+", "", str(value or ""))
        return digits.lstrip("0") or digits or str(value or "").strip().upper()

    def _safe(self, value: Any) -> str:
        return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(value or "cte")).strip("_")

    def _resolve(self, value: str) -> Path:
        path = Path(str(value or ""))
        return path if path.is_absolute() else self.cwd / path
