"""Interactive SSH authentication and scoped Cargo Hub deployment commands."""

import getpass
import json
import shlex
import time
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent.parent
CONTROL = ROOT / "runtime/chat-vps"
HOST = "69.62.97.245"


def save(value):
    target = CONTROL / "status.json"
    temporary = target.with_suffix(".tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    temporary.replace(target)


def run(client, command):
    _, output, errors = client.exec_command(command, timeout=1800)
    stdout, stderr = (
        output.read().decode(errors="replace"),
        errors.read().decode(errors="replace"),
    )
    code = output.channel.recv_exit_status()
    return {"exit_code": code, "output": stdout[-20000:], "errors": stderr[-12000:]}


def main():
    CONTROL.mkdir(parents=True, exist_ok=True)
    client = paramiko.SSHClient()
    client.load_system_host_keys()
    client.load_host_keys(str(Path.home() / ".ssh/known_hosts"))
    client.set_missing_host_key_policy(paramiko.RejectPolicy())
    print(f"Cargo Hub — implantação do chat em root@{HOST}")
    print("Digite a senha SSH nesta janela. Ela será usada apenas em memória.")
    save({"status": "waiting_for_password", "host": HOST})
    for attempt in range(3):
        password = getpass.getpass("Senha SSH: ")
        try:
            client.connect(
                HOST,
                username="root",
                password=password,
                timeout=15,
                allow_agent=False,
                look_for_keys=False,
            )
            break
        except paramiko.AuthenticationException:
            print("Autenticação recusada. Tente novamente.")
        finally:
            password = None
    else:
        save({"status": "authentication_failed"})
        return
    client.get_transport().set_keepalive(20)
    result = run(client, "install -d -m 700 /opt/cargo-hub-chat")
    if result["exit_code"]:
        raise RuntimeError("A pasta de implantação não pôde ser criada.")
    print("Conectado. Mantenha esta janela aberta durante a implantação.")
    preflight = run(
        client,
        "uname -s; command -v docker; docker compose version; docker ps --format '{{.Names}}|{{.Image}}|{{.Ports}}'; docker network ls --format '{{.Name}}'; ss -ltn '( sport = :80 or sport = :443 or sport = :18437 )'",
    )
    save({"status": "connected", "preflight": preflight})
    last_job = None
    try:
        while client.get_transport().is_active():
            job_path = CONTROL / "job.json"
            if not job_path.exists():
                time.sleep(1)
                continue
            job = json.loads(job_path.read_text(encoding="utf-8-sig"))
            if job.get("id") == last_job:
                time.sleep(1)
                continue
            last_job = job["id"]
            action = job.get("action")
            if action == "close":
                break
            if action == "upload":
                archive = Path(job["archive"]).resolve()
                if (
                    not archive.is_relative_to((ROOT / "runtime").resolve())
                    or archive.suffix != ".gz"
                ):
                    raise ValueError("Pacote de implantação fora da pasta autorizada.")
                remote = "/opt/cargo-hub-chat"
                run(client, "install -d -m 700 /opt/cargo-hub-chat")
                with client.open_sftp() as sftp:
                    sftp.put(str(archive), remote + "/deployment.tar.gz")
                    sftp.chmod(remote + "/deployment.tar.gz", 0o600)
                result = run(
                    client,
                    "cd /opt/cargo-hub-chat && tar -xzf deployment.tar.gz && chmod 700 secrets && chown 10001:10001 secrets/* && chmod 400 secrets/*",
                )
            elif action == "execute":
                # Commands are authored in the local workspace and restricted to this deployment.
                script = Path(job["script"]).resolve()
                allowed = (ROOT / "runtime/chat-vps").resolve()
                if not script.is_relative_to(allowed) or script.suffix != ".sh":
                    raise ValueError("Script remoto fora da pasta de implantação.")
                remote = "/opt/cargo-hub-chat/operation.sh"
                with client.open_sftp() as sftp:
                    sftp.put(str(script), remote)
                    sftp.chmod(remote, 0o700)
                result = run(
                    client, "cd /opt/cargo-hub-chat && bash " + shlex.quote(remote)
                )
            else:
                raise ValueError("Operação de implantação inválida.")
            save({"status": "connected", "job_id": last_job, "result": result})
    finally:
        client.close()
        save({"status": "closed", "last_job": last_job})


if __name__ == "__main__":
    try:
        main()
    except Exception as error:  # noqa: BLE001 - keep authentication and network details private
        save({"status": "failed", "error_type": type(error).__name__})
        print("A sessão SSH foi interrompida. Consulte o status da implantação.")
        input("Pressione Enter para fechar.")
