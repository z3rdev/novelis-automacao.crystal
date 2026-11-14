"""Backend heartbeats independent of the visibility of the desktop window."""
import asyncio
import json
import logging
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from uuid import NAMESPACE_DNS, uuid4, uuid5

from app.api.routers.health import _read_release_version
from app.services.session_audit import STATES

logger = logging.getLogger(__name__)


class DevicePresence:
    def __init__(self, audit, root, run_state, clock=lambda: datetime.now(UTC)):
        self.audit, self.root, self.run_state, self.clock = audit, root, run_state, clock
        self.started_at = clock().isoformat()
        self.instance_id = str(uuid4())
        self.task = None

    def device(self, snapshot: dict, *, stopped=False) -> dict:
        identity = self.audit.identity()
        machine = identity["computer_name"].casefold()
        installed = ((self.root / ".automacao-novelis-install").is_file()
                     and (self.root / "installed-release.json").is_file())
        kind = "installed" if installed else "development"
        timestamp = self.clock().isoformat()
        return {"id": str(uuid5(NAMESPACE_DNS, f"cargo-hub:{machine}:{kind}")),
                "machine_id": machine, **identity, "mac_addresses": json.dumps(identity["mac_addresses"]),
                "version": _read_release_version(self.root), "installation_kind": kind,
                "install_root": str(self.root), "first_seen_at": self.started_at,
                "last_seen_at": timestamp, "instance_id": self.instance_id,
                "backend_started_at": self.started_at, "backend_status": "stopped" if stopped else "online",
                "automation_status": STATES[snapshot["status"]], "run_id": snapshot.get("id"),
                "updated_at": timestamp}

    async def tick(self, *, stopped=False):
        snapshot = (await self.run_state.get()).model_dump(mode="json")
        await asyncio.to_thread(self.audit.heartbeat, self.device(snapshot, stopped=stopped), snapshot)

    async def loop(self):
        while True:
            try:
                await self.tick()
            except (OSError, RuntimeError, sqlite3.Error):
                logger.warning("O sinal de atividade aguarda disponibilidade do registro local.")
            await asyncio.sleep(30)

    def start(self):
        self.task = asyncio.create_task(self.loop())

    async def close(self):
        if self.task:
            self.task.cancel()
            with suppress(asyncio.CancelledError):
                await self.task
        await self.tick(stopped=True)
