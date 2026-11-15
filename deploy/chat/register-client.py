"""Run on the VPS to issue an installation profile without printing its token."""

import argparse
import hashlib
import json
import os
import secrets
import tempfile
from pathlib import Path
from uuid import uuid4

parser = argparse.ArgumentParser()
parser.add_argument("--registry", type=Path, required=True)
parser.add_argument("--computer", required=True)
parser.add_argument("--windows-user", required=True)
parser.add_argument("--output", type=Path, required=True)
parser.add_argument("--url", default="https://chat-server-db-cargohub.appsy.app.br")
args = parser.parse_args()
if os.name == "nt":
    parser.error("Execute este comando na VPS Linux.")

import fcntl

identifier, token = str(uuid4()), secrets.token_urlsafe(48)
with args.registry.with_suffix(".lock").open("a") as lock:
    fcntl.flock(lock, fcntl.LOCK_EX)
    registry = json.loads(args.registry.read_text(encoding="utf-8-sig"))
    registry.setdefault("clients", []).append(
        {
            "id": identifier,
            "token_sha256": hashlib.sha256(token.encode()).hexdigest(),
            "computer_name": args.computer,
            "windows_users": [args.windows_user],
            "enabled": True,
        }
    )
    descriptor = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    temporary = None
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(
                {"url": args.url, "client_id": identifier, "token": token},
                output,
                indent=2,
            )
        with tempfile.NamedTemporaryFile(
            mode="w", dir=args.registry.parent, delete=False
        ) as pending:
            temporary = Path(pending.name)
            json.dump(registry, pending, indent=2)
        os.chmod(temporary, 0o400)
        os.chown(temporary, 10001, 10001)
        temporary.replace(args.registry)
    except BaseException:
        args.output.unlink(missing_ok=True)
        raise
    finally:
        if temporary:
            temporary.unlink(missing_ok=True)
print(
    "Perfil privado criado. Recrie o container chat para carregar o cadastro atualizado."
)
