import argparse
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path

from .api_client import ApiClient, ApiError
from .config import APP_VERSION, load_settings, save_settings
from .process_manager import ensure_local_stack


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=str(Path(__file__).resolve().parents[2]))
    args = parser.parse_args()
    run_service(Path(args.root).resolve())


def run_service(root: Path) -> None:
    log_path = root / "runtime" / "desktop-service.log"
    stop_path = root / "runtime" / "desktop-service.stop"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("Serviço Automação Novelis iniciado.")
    if stop_path.exists():
        stop_path.unlink()
    try:
        ensure_local_stack(root, expected_version=APP_VERSION)
        logging.info("Backend/frontend locais iniciados pelo serviço.")
    except Exception as exc:
        logging.exception("Falha ao iniciar backend/frontend pelo serviço: %s", exc)
    while True:
        if stop_path.exists():
            stop_path.unlink()
            logging.info("Serviço encerrado por sinal local.")
            return
        try:
            ensure_local_stack(root, expected_version=APP_VERSION)
            tick(root)
        except Exception as exc:
            logging.exception("Falha no ciclo do serviço: %s", exc)
        time.sleep(30)


def tick(root: Path) -> None:
    settings = load_settings(root)
    if not settings.get("auto_run_enabled") and not settings.get("auto_consult_enabled"):
        return
    now = datetime.now()
    if now.weekday() not in settings.get("weekdays", []):
        return
    scheduled = scheduled_datetime(now, str(settings.get("start_time", "08:00")))
    delay = int(settings.get("start_delay_minutes") or 0)
    if now < scheduled + timedelta(minutes=delay):
        return

    logging.info("Agendamento elegível.")
    client = ApiClient(str(settings.get("backend_url")))
    current = client.current_run()
    if current.get("status") in {"running", "stopping"}:
        logging.info("Automação já está em execução; ciclo ignorado.")
        return
    if settings.get("auto_run_enabled") and automation_due(settings, now):
        start_and_track(root, settings, client, "automation")
        return
    if settings.get("auto_consult_enabled") and interval_due(
        str(settings.get("last_consult_at") or ""),
        int(settings.get("consult_interval_minutes") or 0),
        now,
    ):
        start_and_track(root, settings, client, "consulta")


def start_and_track(root: Path, settings: dict, client: ApiClient, mode: str) -> None:
    try:
        result = client.start_automation() if mode == "automation" else client.start_consulta()
        logging.info("%s iniciado pelo serviço: %s", mode, result.get("id"))
        wait_run_finish(client)
        status = client.current_run().get("status", "")
        now = datetime.now()
        if mode == "automation":
            settings["last_auto_run_date"] = now.strftime("%Y-%m-%d")
            settings["last_auto_run_at"] = now.isoformat(timespec="seconds")
            settings["last_auto_run_status"] = status
        else:
            settings["last_consult_at"] = now.isoformat(timespec="seconds")
        save_settings(root, settings)
    except ApiError as exc:
        logging.error("Falha ao iniciar %s: %s", mode, exc)


def automation_due(settings: dict, now: datetime) -> bool:
    interval = int(settings.get("automation_interval_minutes") or 0)
    if interval > 0:
        return interval_due(str(settings.get("last_auto_run_at") or ""), interval, now)
    return settings.get("last_auto_run_date") != now.strftime("%Y-%m-%d")


def interval_due(last_at: str, interval_minutes: int, now: datetime) -> bool:
    if interval_minutes <= 0:
        return False
    if not last_at:
        return True
    try:
        previous = datetime.fromisoformat(last_at)
    except ValueError:
        return True
    return now >= previous + timedelta(minutes=interval_minutes)


def scheduled_datetime(now: datetime, start_time: str) -> datetime:
    hour_text, minute_text = (start_time.split(":", 1) + ["00"])[:2]
    hour = int(hour_text)
    minute = int(minute_text)
    return now.replace(hour=hour, minute=minute, second=0, microsecond=0)


def wait_run_finish(client: ApiClient) -> None:
    while True:
        time.sleep(10)
        status = client.current_run().get("status")
        if status not in {"running", "stopping"}:
            logging.info("Automação finalizada com status %s.", status)
            return


if __name__ == "__main__":
    main()
