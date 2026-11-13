import os
import shlex
import subprocess
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, simpledialog, ttk
from typing import Callable

from .api_client import ApiClient, ApiError
from .config import APP_VERSION, load_settings, save_settings, set_password, verify_password
from .process_manager import (
    ensure_local_stack,
    force_stop_python_processes,
    open_frontend,
    restart_backend,
    restart_frontend,
    service_status,
)
from .settings_window import SettingsWindow
from .update_checker import UpdateInfo, check_for_update, mark_update_seen


class DesktopApp(tk.Tk):
    def __init__(self, root_path: Path) -> None:
        super().__init__()
        self.root_path = root_path
        self.log_path = root_path / "runtime" / "desktop-app.log"
        self.settings = load_settings(root_path)
        self.client = ApiClient(str(self.settings["backend_url"]))
        self.title("Automação Novelis")
        self.geometry("860x560")
        self.minsize(780, 520)
        self.status_var = tk.StringVar(value="Preparando ambiente local...")
        self.run_var = tk.StringVar(value="Execução: -")
        self.chamados_var = tk.StringVar(value="Chamados: -")
        self.service_var = tk.StringVar(value="Serviço: verificando...")
        self.last_run_status = ""
        self.update_window: tk.Toplevel | None = None
        self.update_notice_info: UpdateInfo | None = None
        self.update_check_running = False
        self._build_ui()
        self.after(200, lambda: self._run_thread(self.prepare_environment))
        self.after(4000, self.refresh_status_loop)
        self.after(3000, self.update_check_loop)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        header = ttk.Frame(self, padding=16)
        header.grid(row=0, column=0, sticky="ew")
        header.columnconfigure(0, weight=1)
        ttk.Label(header, text="Automação Novelis", font=("Segoe UI", 18, "bold")).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Label(header, textvariable=self.status_var).grid(row=1, column=0, sticky="w")

        controls = ttk.Frame(self, padding=(16, 6))
        controls.grid(row=1, column=0, sticky="ew")
        for index in range(3):
            controls.columnconfigure(index, weight=1)
        self._button(controls, "Iniciar automação", self.start_automation, 0, 0)
        self._button(controls, "Parar automação", self.stop_automation, 0, 1)
        self._button(controls, "Abrir lista Novelis", self.open_chamados, 0, 2, False)
        self._button(controls, "Consultar", self.consultar, 1, 0)
        self._button(controls, "Abrir painel", self.open_dashboard, 1, 1, False)
        self._button(controls, "Configurações", self.open_settings, 1, 2, False)
        self._button(controls, "Reiniciar servidor", self.restart_server, 2, 0)
        self._button(controls, "Reiniciar frontend", self.restart_front, 2, 1)
        self._button(controls, "Finalizar Python", self.confirm_force_python, 2, 2, False)

        cards = ttk.Frame(self, padding=(16, 8))
        cards.grid(row=2, column=0, sticky="ew")
        cards.columnconfigure(0, weight=1)
        cards.columnconfigure(1, weight=1)
        cards.columnconfigure(2, weight=1)
        ttk.Label(cards, textvariable=self.run_var, padding=12, relief="groove").grid(
            row=0, column=0, sticky="ew", padx=(0, 8)
        )
        ttk.Label(cards, textvariable=self.chamados_var, padding=12, relief="groove").grid(
            row=0, column=1, sticky="ew", padx=(0, 8)
        )
        ttk.Label(cards, textvariable=self.service_var, padding=12, relief="groove").grid(
            row=0, column=2, sticky="ew"
        )

        log_frame = ttk.Frame(self, padding=16)
        log_frame.grid(row=3, column=0, sticky="nsew")
        self.rowconfigure(3, weight=1)
        log_frame.rowconfigure(1, weight=1)
        log_frame.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(log_frame)
        toolbar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        ttk.Label(toolbar, text="Log").pack(side="left")
        ttk.Button(toolbar, text="Limpar", command=self.clear_log).pack(side="right")
        ttk.Button(toolbar, text="Abrir arquivo de log", command=self.open_log_file).pack(
            side="right", padx=(0, 6)
        )

        self.log = tk.Text(log_frame, height=12, wrap="word")
        self.log.grid(row=1, column=0, sticky="nsew")
        scrollbar = ttk.Scrollbar(log_frame, command=self.log.yview)
        scrollbar.grid(row=1, column=1, sticky="ns")
        self.log.configure(yscrollcommand=scrollbar.set)
        self.log.tag_configure("error", foreground="#b91c1c")
        self.log.tag_configure("warn", foreground="#b45309")
        self.log.tag_configure("success", foreground="#047857")
        self.log.tag_configure("info", foreground="#0f172a")
        self.log.configure(state="disabled")

        command_row = ttk.Frame(log_frame)
        command_row.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        command_row.columnconfigure(0, weight=1)
        self.command_var = tk.StringVar(value="")
        command_entry = ttk.Entry(command_row, textvariable=self.command_var)
        command_entry.grid(row=0, column=0, sticky="ew")
        command_entry.bind("<Return>", lambda event: self.run_command())
        ttk.Button(command_row, text="Executar", command=self.run_command).grid(
            row=0, column=1, padx=(8, 0)
        )

    def _button(
        self,
        parent: ttk.Frame,
        text: str,
        command: Callable[[], None],
        row: int,
        col: int,
        background: bool = True,
    ) -> None:
        handler = (lambda: self._run_thread(command)) if background else command
        ttk.Button(parent, text=text, command=handler).grid(
            row=row,
            column=col,
            sticky="ew",
            padx=4,
            pady=4,
        )

    def _run_thread(self, fn: Callable[[], None]) -> None:
        threading.Thread(target=self._safe_call, args=(fn,), daemon=True).start()

    def _safe_call(self, fn: Callable[[], None]) -> None:
        try:
            fn()
        except Exception as exc:
            self.write_log(f"Erro: {exc}")
            self.set_var(self.status_var, str(exc))

    def prepare_environment(self) -> None:
        ensure_local_stack(self.root_path, expected_version=APP_VERSION)
        self.set_var(self.status_var, "Ambiente local pronto.")
        self.refresh_status()
        self.refresh_chamados_summary()
        self.refresh_service_status()

    def start_automation(self) -> None:
        self.write_log("Iniciando automação completa.")
        result = self.client.start_automation()
        self.write_log(f"Execução criada: {result.get('id')}")
        self.refresh_status()

    def stop_automation(self) -> None:
        self.write_log("Solicitando parada da automação.")
        result = self.client.stop_automation()
        self.write_log(result.get("message", "Parada solicitada."))
        self.refresh_status()

    def open_chamados(self) -> None:
        open_frontend(str(self.settings["frontend_url"]), "chamados")
        self.write_log("Lista Novelis aberta no navegador.")

    def open_dashboard(self) -> None:
        open_frontend(str(self.settings["frontend_url"]))
        self.write_log("Painel aberto no navegador.")

    def consultar(self) -> None:
        self.write_log("Iniciando consulta SQL + relatório Novelis.")
        result = self.client.start_consulta()
        self.write_log(f"Consulta criada: {result.get('id')}")
        self.refresh_status()

    def restart_server(self) -> None:
        self.write_log("Reiniciando backend local.")
        restart_backend(self.root_path, expected_version=APP_VERSION)
        self.write_log("Backend reiniciado.")
        self.refresh_status()

    def restart_front(self) -> None:
        self.write_log("Reiniciando frontend local.")
        restart_frontend(self.root_path, expected_version=APP_VERSION)
        self.write_log("Frontend reiniciado.")

    def confirm_force_python(self) -> None:
        if not messagebox.askyesno(
            "Finalizar Python",
            "Isso vai encerrar processos python/pythonw locais. Continuar?",
        ):
            return
        self._run_thread(self.force_python)

    def force_python(self) -> None:
        self.write_log("Forçando finalização de processos Python.")
        self.write_log(force_stop_python_processes(self.root_path))
        self.refresh_status()

    def refresh_status_loop(self) -> None:
        self._run_thread(self.refresh_status)
        self._run_thread(self.refresh_service_status)
        self.after(8000, self.refresh_status_loop)

    def update_check_loop(self) -> None:
        if not self.update_check_running:
            self.update_check_running = True
            self._run_thread(self.check_updates)
        interval = int(self.settings.get("update_check_interval_seconds") or 20)
        self.after(max(interval, 5) * 1000, self.update_check_loop)

    def check_updates(self) -> None:
        try:
            self.settings = load_settings(self.root_path)
            info = check_for_update(self.root_path, self.settings)
            if info:
                self.after(0, lambda: self.show_update_notice(info))
        finally:
            self.update_check_running = False

    def show_update_notice(self, info: UpdateInfo) -> None:
        if self.update_window and self.update_window.winfo_exists():
            return
        self.update_notice_info = info
        self.write_log(f"Atualização encontrada: {info.version} em {info.source_dir}")
        window = tk.Toplevel(self)
        self.update_window = window
        window.title("Atualização disponível")
        window.geometry("520x300")
        window.minsize(480, 260)
        window.transient(self)
        window.grab_set()

        frame = ttk.Frame(window, padding=18)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=info.title, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(frame, text=f"Versão: {info.version}").pack(anchor="w", pady=(8, 0))
        ttk.Label(frame, text=f"Fonte: {info.source_dir}", wraplength=470).pack(anchor="w", pady=(4, 0))
        if info.notes:
            ttk.Label(frame, text=info.notes, wraplength=470).pack(anchor="w", pady=(10, 0))
        ttk.Label(
            frame,
            text="Abra a pasta da atualização para executar o instalador publicado.",
            wraplength=470,
        ).pack(anchor="w", pady=(10, 0))

        buttons = ttk.Frame(frame)
        buttons.pack(fill="x", side="bottom", pady=(18, 0))
        ttk.Button(buttons, text="Abrir atualização", command=lambda: self.open_update_target(info)).pack(side="left")
        ttk.Button(buttons, text="Fechar", command=self.close_update_notice).pack(side="right")
        window.protocol("WM_DELETE_WINDOW", self.close_update_notice)

    def open_update_target(self, info: UpdateInfo) -> None:
        target = Path(info.target_path)
        try:
            if not target.exists():
                os.startfile(str(Path(info.source_dir)))  # type: ignore[attr-defined]
                return
            if target.is_dir():
                os.startfile(str(target))  # type: ignore[attr-defined]
                return
            args = [str(target)]
            if (self.root_path / ".automacao-novelis-install").exists():
                args.append(f"/DIR={self.root_path}")
            subprocess.Popen(
                args,
                cwd=str(target.parent),
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
            )
            mark_update_seen(self.root_path, info.update_id)
            self.write_log("Instalador de atualização iniciado. Encerrando app atual.")
            self.after(300, self.destroy)
            self.after(800, lambda: os._exit(0))
        except OSError as exc:
            messagebox.showerror("Atualização", f"Não foi possível abrir a atualização: {exc}")

    def close_update_notice(self) -> None:
        if self.update_notice_info:
            mark_update_seen(self.root_path, self.update_notice_info.update_id)
        if self.update_window and self.update_window.winfo_exists():
            self.update_window.destroy()
        self.update_window = None
        self.update_notice_info = None

    def refresh_status(self) -> None:
        try:
            current = self.client.current_run()
            status = str(current.get("status") or "")
            self.set_var(self.run_var, f"Execução: {status} | {current.get('message')}")
            if self.last_run_status in {"running", "stopping"} and status not in {"running", "stopping"}:
                self.refresh_chamados_summary()
            self.last_run_status = status
        except ApiError as exc:
            self.set_var(self.run_var, "Execução: backend indisponível")
            self.write_log(str(exc))

    def refresh_chamados_summary(self) -> None:
        try:
            data = self.client.chamados()
            if data.get("sourceKind") == "relatorio":
                summary = (
                    f"Relatório: total {data.get('reportTotal', data.get('total', 0))} "
                    f"| fila {data.get('queueTotal', 0)}"
                )
            else:
                summary = f"Chamados: total {data.get('total', 0)} | pendentes {data.get('pendentes', 0)}"
            self.set_var(
                self.chamados_var,
                summary,
            )
            self.write_log(f"Lista local: {data.get('sourceFile') or 'sem arquivo'}")
        except ApiError as exc:
            self.write_log(str(exc))

    def refresh_service_status(self) -> None:
        self.set_var(self.service_var, f"Serviço: {service_status()}")

    def open_settings(self) -> None:
        password = simpledialog.askstring("Senha", "Senha das configurações:", show="*")
        if password is None:
            return
        self.settings = load_settings(self.root_path)
        if not verify_password(self.settings, password):
            messagebox.showerror("Acesso negado", "Senha inválida.")
            return
        SettingsWindow(self, self.root_path, self.settings)

    def run_command(self) -> None:
        raw = self.command_var.get().strip()
        if not raw:
            return
        self.command_var.set("")
        self.write_log(f"$ {self._redact_command(raw)}")
        self._run_thread(lambda: self._execute_command(raw))

    def _redact_command(self, raw: str) -> str:
        tokens = raw.split()
        if "-S" in tokens:
            index = tokens.index("-S")
            if index + 1 < len(tokens):
                tokens[index + 1] = "****"
        return " ".join(tokens)

    def _execute_command(self, raw: str) -> None:
        try:
            tokens = shlex.split(raw)
        except ValueError as exc:
            self.write_log(f"Erro: comando inválido ({exc}).")
            return
        if not tokens:
            return
        if tokens[0] == "--force-reset-password":
            self._command_reset_password(tokens[1:])
        else:
            self.write_log(f"Erro: comando desconhecido: {tokens[0]}")

    def _command_reset_password(self, args: list[str]) -> None:
        if "-S" not in args:
            self.write_log('Erro: uso --force-reset-password -S "NovaSenha"')
            return
        index = args.index("-S")
        if index + 1 >= len(args):
            self.write_log("Erro: informe a nova senha depois de -S.")
            return
        new_password = args[index + 1]
        if not new_password.strip():
            self.write_log("Erro: a nova senha não pode ser vazia.")
            return
        self.settings = load_settings(self.root_path)
        set_password(self.settings, new_password)
        save_settings(self.root_path, self.settings)
        self.write_log("Senha das configurações redefinida com sucesso.")

    def write_log(self, text: str) -> None:
        line = f"[{datetime.now():%H:%M:%S}] {text}"
        self._persist_log(line)
        self.log.after(0, lambda: self._append_log(line, text))

    def set_var(self, var: tk.StringVar, value: str) -> None:
        self.after(0, lambda: var.set(value))

    def _persist_log(self, line: str) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            with self.log_path.open("a", encoding="utf-8", errors="replace") as handle:
                handle.write(line + "\n")
        except OSError:
            pass

    def _append_log(self, line: str, original: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", f"{line}\n", self._log_tag(original))
        self.log.see("end")
        self._trim_log()
        self.log.configure(state="disabled")

    def _log_tag(self, text: str) -> str:
        lowered = text.lower()
        if lowered.startswith("erro") or "falhou" in lowered or "não foi possível" in lowered:
            return "error"
        if "atualização encontrada" in lowered or "aviso" in lowered:
            return "warn"
        if "concluíd" in lowered or "reiniciado" in lowered or "criada" in lowered or "criado" in lowered:
            return "success"
        return "info"

    def _trim_log(self, max_lines: int = 500) -> None:
        line_count = int(self.log.index("end-1c").split(".")[0])
        if line_count > max_lines:
            self.log.delete("1.0", f"{line_count - max_lines}.0")

    def clear_log(self) -> None:
        self.log.configure(state="normal")
        self.log.delete("1.0", "end")
        self.log.configure(state="disabled")

    def open_log_file(self) -> None:
        try:
            self.log_path.parent.mkdir(parents=True, exist_ok=True)
            if not self.log_path.exists():
                self.log_path.touch()
            os.startfile(str(self.log_path))  # type: ignore[attr-defined]
        except OSError as exc:
            messagebox.showerror("Log", f"Não foi possível abrir o log: {exc}")


def main(root_path: Path) -> None:
    app = DesktopApp(root_path)
    app.mainloop()
