"""Prepare one real Novelis ticket over HTTP; --send performs the single save POST."""

import argparse
import asyncio
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))

from app.automation.cancellation import run_blocking
from app.config.legacy_config import LegacyConfig
from app.config.settings import get_settings
from app.infrastructure.operations_store import OperationsStore
from app.services.novelis_chamado_http import ChamadoHttpError
from app.services.novelis_chamado_http.runner import probe, record, run_ticket_test


async def run(args, output):
    settings = get_settings()
    config = LegacyConfig(settings)
    if not args.cte:
        return await probe(config, output)
    store = OperationsStore(settings.novelis_sqlite_path)
    try:
        config.values.update(await run_blocking(store.preferences))
    finally:
        store.close()
    return await run_ticket_test(settings, config, args.cte, output, send=args.send)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cte", help="filial-serie-numero; omit to check only the authenticated form"
    )
    parser.add_argument(
        "--send",
        action="store_true",
        help="Create the real ticket with the configured message and attachments",
    )
    args = parser.parse_args()
    if args.send and not args.cte:
        parser.error("O envio real exige --cte filial-serie-numero.")
    if args.cte and not re.fullmatch(r"\d+-\d+-\d+", args.cte):
        parser.error("Informe o CT-e completo no formato filial-serie-numero.")
    if args.cte:
        args.cte = "-".join(str(int(value)) for value in args.cte.split("-"))
    output = (
        ROOT
        / "runtime/chamado-http-tests"
        / f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid4().hex[:8]}"
    )
    output.mkdir(parents=True, exist_ok=True)
    try:
        print(json.dumps(asyncio.run(run(args, output)), ensure_ascii=False))
    except Exception as exc:  # noqa: BLE001 - redact driver and HTTP exceptions at the CLI boundary
        result = {
            "status": "failed",
            "exception": type(exc).__name__,
            "message": str(exc)
            if isinstance(exc, ChamadoHttpError)
            else "Teste interrompido. Consulte o resultado de envio antes de repetir.",
        }
        record(output / "error.json", result)
        print(json.dumps(result, ensure_ascii=False))
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
