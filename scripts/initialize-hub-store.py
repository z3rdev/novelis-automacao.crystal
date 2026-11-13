"""Initialize the shared SQLite and import read-only snapshots of existing data."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "BACKEND"))

from app.config.legacy_config import LegacyConfig
from app.config.settings import Settings
from app.data.chamados_log import read_processed_ctes
from app.infrastructure.operations_store import OperationsStore
from app.services.hub_service import HubService


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", required=True, type=Path)
    args = parser.parse_args()
    settings = Settings()
    config = LegacyConfig(settings)
    store = OperationsStore(args.database)
    store.initialize()
    try:
        hub = HubService(settings, config, store, None, None)
        ctes, chamados = hub.ctes(), hub.chamados()
        processed = read_processed_ctes(config.novelis().get("chamadosLogFile"))
        if processed:
            store.snapshot("processed_ctes_import", processed)
        print(json.dumps({**store.health(), "ctes": len(ctes), "chamados": len(chamados),
                          "processed_imported": len(processed)}, ensure_ascii=False))
    finally:
        store.close()


if __name__ == "__main__":
    main()
