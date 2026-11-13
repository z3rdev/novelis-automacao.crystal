from pathlib import Path
from typing import Any

from app.automation.flows.flow_events import Emit, emit_step


async def emit_completed_summary(emit: Emit, run_id: str, plan_file: Path, plan: dict[str, Any]) -> None:
    errors = plan.get("errors") or []
    message = "Iniciar automação finalizado sem erros." if not errors else f"Iniciar automação finalizado com {len(errors)} erro(s)."
    await emit_step(
        emit,
        run_id,
        "pendentes.completed",
        message,
        {"planFile": str(plan_file), "prontosChamado": plan["prontosChamado"], "errors": errors},
    )


async def emit_plan_summary(emit: Emit, plan: dict[str, Any], run_id: str, label: str) -> None:
    await emit_step(
        emit,
        run_id,
        "pendentes.plan",
        (
            f"{label}: total={plan['total']} | "
            f"faltando_pdf={len(plan['faltandoPdf'])} | "
            f"faltando_xml={len(plan['faltandoXml'])} | "
            f"faltando_comprovante={len(plan['faltandoComprovante'])} | "
            f"prontos={len(plan['prontosChamado'])}."
        ),
        {
            "sourceFile": plan["sourceFile"],
            "sheetName": plan["sheetName"],
            "faltandoPdf": plan["faltandoPdf"],
            "faltandoXml": plan["faltandoXml"],
            "faltandoComprovante": plan["faltandoComprovante"],
            "prontosComprovante": plan["prontosComprovante"],
            "prontosChamado": plan["prontosChamado"],
        },
    )
