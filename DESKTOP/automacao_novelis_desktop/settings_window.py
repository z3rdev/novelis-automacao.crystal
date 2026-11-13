import re
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from .api_client import ApiClient
from .config import APP_VERSION, save_settings, set_password
from .config_bundle import export_config_bundle, import_config_bundle
from .env_file import read_env_values, update_env_values
from .process_manager import request_service_stop


WEEKDAYS = [
    ("Seg", 0),
    ("Ter", 1),
    ("Qua", 2),
    ("Qui", 3),
    ("Sex", 4),
    ("Sab", 5),
    ("Dom", 6),
]


ENV_FIELDS = {
    "Geral": [
        ("RODOPAR_PDF_DOWNLOAD_TARGET_DIR", "Downloads PDF Rodopar"),
        ("XML_SEFAZ_DOWNLOAD_DIR", "Downloads XML Sefaz"),
        ("NOVELIS_CHAMADO_DOWNLOAD_TARGET_DIR", "Downloads chamados"),
        ("COMPROVANTE_SOURCE_DIR", "Pasta/URL de comprovantes"),
        ("NOVELIS_RELATORIO_CTE_XML_EXCEL_FILE", "Relatório Novelis Excel"),
        ("NOVELIS_RELATORIO_CTE_XML_JSON_FILE", "Relatório Novelis JSON"),
    ],
    "URLs": [
        ("PRE_URL", "URL Rodopar"),
        ("PRE_HTML5_URL", "URL HTML5 Rodopar"),
        ("NOVELIS_LOGIN_URL", "URL Novelis"),
        ("NOVELIS_CHAMADO_DIRETO_URL", "URL abertura chamados"),
        ("NOVELIS_RELATORIO_CTE_XML_URL", "URL relatório Novelis"),
        ("XML_SEFAZ_URL", "URL Sefaz"),
    ],
    "Usuários": [
        ("PRE_USER", "Usuário primeiro acesso Rodopar"),
        ("PRE_PASS", "Senha primeiro acesso Rodopar"),
        ("NOVELIS_USER", "Usuário Novelis"),
        ("NOVELIS_PASS", "Senha Novelis"),
    ],
}


BROWSER_ENV_FIELDS = [
    ("BROWSER_DOWNLOADS_DIR", "Downloads gerais"),
    ("BROWSER_PLAYWRIGHT_PATH", "Pasta Playwright"),
    ("WINDOW_WIDTH", "Largura do preview"),
    ("WINDOW_HEIGHT", "Altura do preview"),
    ("BROWSER_WINDOW_WIDTH", "Largura da janela"),
    ("BROWSER_WINDOW_HEIGHT", "Altura da janela"),
    ("BROWSER_DEFAULT_TIMEOUT_MS", "Timeout padrão (ms)"),
    ("BROWSER_NAVIGATION_TIMEOUT_MS", "Timeout navegação (ms)"),
]


BG = "#eef3f8"
SURFACE = "#ffffff"
BORDER = "#d7e1ec"
TEXT = "#0f172a"
MUTED = "#5f6f85"
PRIMARY = "#2563eb"


class SettingsWindow(tk.Toplevel):
    def __init__(self, app: tk.Tk, root_path: Path, settings: dict) -> None:
        super().__init__(app)
        self.app = app
        self.root_path = root_path
        self.settings = settings
        self.env_values = read_env_values(root_path)
        self.vars: dict[str, tk.Variable] = {}
        self.readonly_vars: dict[str, tk.StringVar] = {}
        self.env_vars: dict[str, tk.StringVar] = {}
        self.db_vars: dict[str, tk.StringVar] = {}
        self.weekday_vars: dict[int, tk.BooleanVar] = {}
        self.title("Configurações")
        self.geometry("1080x760")
        self.minsize(980, 700)
        self.configure(bg=BG)
        self._configure_styles()
        self._build()

    def _build(self) -> None:
        root = ttk.Frame(self, style="SettingsRoot.TFrame")
        root.pack(fill="both", expand=True)
        header = ttk.Frame(root, style="SettingsHeader.TFrame", padding=(18, 14, 18, 10))
        header.pack(fill="x")
        ttk.Label(
            header,
            text="Configurações",
            style="SettingsTitle.TLabel",
        ).pack(anchor="w")
        ttk.Label(
            header,
            text="Ajustes locais da automação, ambiente, navegador e serviços.",
            style="SettingsHint.TLabel",
        ).pack(anchor="w", pady=(2, 0))

        tabs = ttk.Notebook(root, style="Settings.TNotebook")
        tabs.pack(fill="both", expand=True, padx=16, pady=(0, 12))
        self._general_tab(tabs)
        self._env_tabs(tabs)
        self._comprovantes_tab(tabs)
        self._browser_tab(tabs)
        self._database_tab(tabs)
        self._system_tab(tabs)
        self._password_tab(tabs)
        self._backup_tab(tabs)
        self._buttons()

    def _general_tab(self, tabs: ttk.Notebook) -> None:
        frame = self._tab(tabs, "Instalação")
        self._readonly(frame, "Local instalado", str(self.root_path))
        self._readonly(frame, "Versão local", str(self.settings.get("app_version") or APP_VERSION))
        self._entry(frame, "Backend URL", "backend_url")
        self._entry(frame, "Frontend URL", "frontend_url")

    def _env_tabs(self, tabs: ttk.Notebook) -> None:
        for title, fields in ENV_FIELDS.items():
            frame = self._tab(tabs, title)
            for key, label in fields:
                self._env_entry(frame, label, key, show="*" if key.endswith(("PASS", "PASSWORD")) else "")
            if title == "Geral":
                self._extra_scan_dirs_section(frame)

    def _extra_scan_dirs_section(self, frame: ttk.Frame) -> None:
        ttk.Label(
            frame,
            text="Pastas extras para procurar PDFs já baixados",
            style="SettingsLabel.TLabel",
        ).pack(anchor="w", pady=(14, 2))
        ttk.Label(
            frame,
            text=(
                "Além das pastas padrão (Downloads do Windows, pasta de destino, etc.), a automação "
                "também procura o PDF do CTRC nessas pastas extras antes de desistir."
            ),
            style="SettingsHint.TLabel",
            wraplength=820,
        ).pack(anchor="w", pady=(0, 8))

        self.extra_dirs_frame = ttk.Frame(frame, style="SettingsTab.TFrame")
        self.extra_dirs_frame.pack(anchor="w", fill="x", pady=(0, 8))

        self.extra_dir_rows: list[tuple[tk.StringVar, ttk.Frame]] = []
        raw = self.env_values.get("RODOPAR_PDF_EXTRA_DOWNLOAD_DIRS", "")
        for path in [item.strip() for item in raw.split(";") if item.strip()]:
            self._add_extra_dir_row(path)

        add_row = ttk.Frame(frame, style="SettingsTab.TFrame")
        add_row.pack(anchor="w", pady=(4, 0))
        self.new_extra_dir_var = tk.StringVar(value="")
        ttk.Entry(add_row, textvariable=self.new_extra_dir_var, width=60).pack(side="left")
        ttk.Button(add_row, text="Procurar...", command=self._browse_extra_dir).pack(side="left", padx=(8, 0))
        ttk.Button(add_row, text="Adicionar pasta", command=self._add_new_extra_dir).pack(side="left", padx=(8, 0))

    def _add_extra_dir_row(self, path: str) -> None:
        path = path.strip()
        if not path:
            return
        row = ttk.Frame(self.extra_dirs_frame, style="SettingsTab.TFrame")
        row.pack(anchor="w", fill="x", pady=2)
        var = tk.StringVar(value=path)
        ttk.Entry(row, textvariable=var, width=60).pack(side="left")
        ttk.Button(row, text="Remover", command=lambda r=row, v=var: self._remove_extra_dir(r, v)).pack(
            side="left",
            padx=(8, 0),
        )
        self.extra_dir_rows.append((var, row))

    def _remove_extra_dir(self, row: ttk.Frame, var: tk.StringVar) -> None:
        self.extra_dir_rows = [(v, r) for v, r in self.extra_dir_rows if r is not row]
        row.destroy()

    def _browse_extra_dir(self) -> None:
        path = filedialog.askdirectory(title="Escolher pasta extra")
        if path:
            self.new_extra_dir_var.set(path)

    def _add_new_extra_dir(self) -> None:
        path = self.new_extra_dir_var.get().strip()
        if not path:
            return
        self.new_extra_dir_var.set("")
        self._add_extra_dir_row(path)

    def _extra_download_dirs_value(self) -> str:
        return ";".join(var.get().strip() for var, _ in self.extra_dir_rows if var.get().strip())

    def _comprovantes_tab(self, tabs: ttk.Notebook) -> None:
        frame = self._tab(tabs, "Comprovantes")
        ttk.Label(
            frame,
            text="Regra de nome do arquivo: PREFIXO_FILIAL_SERIE_CTRC (ex.: GNR_0001_10_123456.pdf).",
            style="SettingsLabel.TLabel",
        ).pack(anchor="w", pady=(0, 2))
        ttk.Label(
            frame,
            text=(
                "Buscar: procura o arquivo na pasta de comprovantes "
                f"({self.env_values.get('COMPROVANTE_SOURCE_DIR', '')}). "
                "Incluir no ZIP: anexa esse arquivo no ZIP enviado antes de abrir o chamado na Novelis. "
                "Adicione novos prefixos abaixo."
            ),
            style="SettingsHint.TLabel",
            wraplength=820,
        ).pack(anchor="w", pady=(0, 10))

        self.prefix_list_frame = ttk.Frame(frame, style="SettingsTab.TFrame")
        self.prefix_list_frame.pack(anchor="w", fill="x", pady=(0, 10))

        header = ttk.Frame(self.prefix_list_frame, style="SettingsTab.TFrame")
        header.pack(anchor="w", fill="x", pady=(0, 4))
        ttk.Label(header, text="Prefixo", style="SettingsLabel.TLabel", width=24).pack(side="left")
        ttk.Label(header, text="Buscar", style="SettingsLabel.TLabel", width=10).pack(side="left")
        ttk.Label(header, text="Incluir no ZIP", style="SettingsLabel.TLabel", width=14).pack(side="left")

        self.prefix_search_vars: dict[str, tk.BooleanVar] = {}
        self.prefix_zip_vars: dict[str, tk.BooleanVar] = {}
        search_raw = self.env_values.get("COMPROVANTE_PREFIXES", "GNR,CMP")
        zip_raw = self.env_values.get("COMPROVANTE_ZIP_PREFIXES", search_raw)
        search_existing = [item.strip().upper() for item in search_raw.split(",") if item.strip()]
        zip_existing = [item.strip().upper() for item in zip_raw.split(",") if item.strip()]
        for prefix in dict.fromkeys([*search_existing, *zip_existing, "GNR", "CMP", "PDF"]):
            self._add_prefix_row(prefix, prefix in search_existing, prefix in zip_existing)

        add_row = ttk.Frame(frame, style="SettingsTab.TFrame")
        add_row.pack(anchor="w", pady=(6, 0))
        self.new_prefix_var = tk.StringVar(value="")
        ttk.Entry(add_row, textvariable=self.new_prefix_var, width=16).pack(side="left")
        ttk.Button(add_row, text="Adicionar prefixo", command=self._add_new_prefix).pack(side="left", padx=(8, 0))

    def _add_prefix_row(self, prefix: str, search_checked: bool, zip_checked: bool) -> None:
        prefix = prefix.strip().upper()
        if not prefix or prefix in self.prefix_search_vars:
            return
        search_var = tk.BooleanVar(value=search_checked)
        zip_var = tk.BooleanVar(value=zip_checked)
        self.prefix_search_vars[prefix] = search_var
        self.prefix_zip_vars[prefix] = zip_var
        row = ttk.Frame(self.prefix_list_frame, style="SettingsTab.TFrame")
        row.pack(anchor="w", fill="x", pady=2)
        ttk.Label(row, text=f"{prefix}_FILIAL_SERIE_CTRC", style="SettingsHint.TLabel", width=24).pack(side="left")
        ttk.Checkbutton(row, variable=search_var, style="Settings.TCheckbutton", width=10).pack(side="left")
        ttk.Checkbutton(row, variable=zip_var, style="Settings.TCheckbutton", width=14).pack(side="left")
        ttk.Button(row, text="Remover", command=lambda p=prefix, r=row: self._remove_prefix(p, r)).pack(
            side="left",
            padx=(8, 0),
        )

    def _remove_prefix(self, prefix: str, row: ttk.Frame) -> None:
        self.prefix_search_vars.pop(prefix, None)
        self.prefix_zip_vars.pop(prefix, None)
        row.destroy()

    def _add_new_prefix(self) -> None:
        prefix = re.sub(r"[^A-Z0-9]+", "", self.new_prefix_var.get().strip().upper())
        if not prefix:
            return
        self.new_prefix_var.set("")
        if prefix in self.prefix_search_vars:
            self.prefix_search_vars[prefix].set(True)
            self.prefix_zip_vars[prefix].set(True)
            return
        self._add_prefix_row(prefix, True, True)

    def _comprovante_prefixes_value(self) -> str:
        items = [prefix for prefix, var in self.prefix_search_vars.items() if var.get()]
        if not items:
            items = ["GNR", "CMP"]
        return ",".join(items)

    def _comprovante_zip_prefixes_value(self) -> str:
        items = [prefix for prefix, var in self.prefix_zip_vars.items() if var.get()]
        if not items:
            items = ["GNR", "CMP"]
        return ",".join(items)

    def _system_tab(self, tabs: ttk.Notebook) -> None:
        frame = self._tab(tabs, "Sistema")
        frame.columnconfigure(0, weight=1)
        frame.columnconfigure(1, weight=1)

        self.vars["auto"] = tk.BooleanVar(value=bool(self.settings.get("auto_run_enabled")))
        self.vars["auto_consult"] = tk.BooleanVar(value=bool(self.settings.get("auto_consult_enabled")))
        self.vars["update_enabled"] = tk.BooleanVar(value=bool(self.settings.get("update_enabled", True)))

        automation = self._section(frame, "Automação", "Controle do início automático e consulta recorrente.")
        automation.grid(row=0, column=0, sticky="new", padx=(0, 8), pady=(0, 10))
        automation.columnconfigure(0, weight=1)
        ttk.Checkbutton(
            automation,
            text="Iniciar automação automaticamente",
            variable=self.vars["auto"],
            style="Settings.TCheckbutton",
        ).grid(row=1, column=0, sticky="w")
        ttk.Checkbutton(
            automation,
            text="Consultar automaticamente",
            variable=self.vars["auto_consult"],
            style="Settings.TCheckbutton",
        ).grid(row=2, column=0, sticky="w", pady=(8, 0))

        updates = self._section(frame, "Atualizações", "Busca novas versões na pasta compartilhada.")
        updates.grid(row=0, column=1, sticky="new", padx=(8, 0), pady=(0, 10))
        updates.columnconfigure(0, weight=1)
        updates.columnconfigure(1, weight=0)
        ttk.Checkbutton(
            updates,
            text="Verificar atualizações automaticamente",
            variable=self.vars["update_enabled"],
            style="Settings.TCheckbutton",
        ).grid(row=1, column=0, columnspan=2, sticky="w")
        self._grid_entry(updates, "Pasta de atualizações", "update_source_dir", 2, 0, columnspan=2)
        self._grid_entry(updates, "Intervalo de verificação (segundos)", "update_check_interval_seconds", 4, 0)

        schedule = self._section(frame, "Agendamento", "Horários e intervalos usados pelo serviço persistente.")
        schedule.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        schedule.columnconfigure(0, weight=1)
        schedule.columnconfigure(1, weight=1)
        self._grid_entry(schedule, "Horário de início (HH:MM)", "start_time", 1, 0)
        self._grid_entry(schedule, "Atraso para iniciar (minutos)", "start_delay_minutes", 1, 1)
        self._grid_entry(
            schedule,
            "Rodar automação a cada (minutos, 0 = uma vez por dia)",
            "automation_interval_minutes",
            3,
            0,
        )
        self._grid_entry(
            schedule,
            "Consultar a cada (minutos, 0 = desligado)",
            "consult_interval_minutes",
            3,
            1,
        )

        days_box = self._section(frame, "Dias da semana", "Dias permitidos para rodar automaticamente.")
        days_box.grid(row=2, column=0, columnspan=2, sticky="ew")
        for index in range(len(WEEKDAYS)):
            days_box.columnconfigure(index, weight=1)
        selected = set(self.settings.get("weekdays", []))
        for index, (label, value) in enumerate(WEEKDAYS):
            var = tk.BooleanVar(value=value in selected)
            self.weekday_vars[value] = var
            ttk.Checkbutton(days_box, text=label, variable=var, style="Settings.TCheckbutton").grid(
                row=1,
                column=index,
                sticky="w",
                pady=(6, 0),
            )

    def _browser_tab(self, tabs: ttk.Notebook) -> None:
        frame = self._tab(tabs, "Navegador")
        self.vars["browser_headless"] = tk.BooleanVar(value=self._env_bool("BROWSER_HEADLESS", False))
        self.vars["consulta_headless"] = tk.BooleanVar(
            value=self._env_bool("CONSULTA_BROWSER_HEADLESS", False)
        )
        ttk.Checkbutton(
            frame,
            text="Executar navegador geral sem tela (headless)",
            variable=self.vars["browser_headless"],
            style="Settings.TCheckbutton",
        ).pack(anchor="w")
        ttk.Checkbutton(
            frame,
            text="Consultar sem mostrar navegador (headless)",
            variable=self.vars["consulta_headless"],
            style="Settings.TCheckbutton",
        ).pack(anchor="w", pady=(0, 10))
        for key, label in BROWSER_ENV_FIELDS:
            self._env_entry(frame, label, key)

    def _database_tab(self, tabs: ttk.Notebook) -> None:
        frame = self._tab(tabs, "Banco de dados")
        host, port = self._split_server(self.env_values.get("CONSULTA_DB_SERVER", ""))
        host = self.env_values.get("CONSULTA_DB_HOST") or host
        port = self.env_values.get("CONSULTA_DB_PORT") or port
        self._db_entry(frame, "Host / servidor", "host", host)
        self._db_entry(frame, "Porta", "port", port)
        self._db_entry(frame, "Usuário", "user", self.env_values.get("CONSULTA_DB_USER", ""))
        self._db_entry(frame, "Senha", "pass", self.env_values.get("CONSULTA_DB_PASS", ""), show="*")
        self._db_entry(
            frame,
            "Database",
            "database",
            self.env_values.get("CONSULTA_DB_DATABASE", "db_visual_dellmar"),
        )

    def _password_tab(self, tabs: ttk.Notebook) -> None:
        frame = self._tab(tabs, "Senha e serviço")
        self.vars["new_password"] = tk.StringVar(value="")
        self.vars["confirm_password"] = tk.StringVar(value="")
        self._password_entry(frame, "Nova senha das configurações", "new_password")
        self._password_entry(frame, "Confirmar nova senha", "confirm_password")
        ttk.Button(frame, text="Encerrar serviço persistente", command=self.stop_service).pack(anchor="w", pady=16)

    def _backup_tab(self, tabs: ttk.Notebook) -> None:
        frame = self._tab(tabs, "Backup")
        ttk.Label(
            frame,
            text=(
                "Exporta ou importa um pacote único com usuários/senhas do Rodopar e Novelis, "
                "configurações do app e todos os mapas de passos (captures/*.json)."
            ),
            style="SettingsHint.TLabel",
            wraplength=760,
        ).pack(anchor="w", pady=(0, 4))
        ttk.Label(
            frame,
            text="O arquivo exportado tem as senhas em texto simples — guarde e compartilhe com cuidado.",
            style="SettingsHint.TLabel",
            wraplength=760,
        ).pack(anchor="w", pady=(0, 14))
        ttk.Button(frame, text="Exportar configuração...", command=self.export_bundle).pack(anchor="w", pady=(0, 8))
        ttk.Button(frame, text="Importar configuração...", command=self.import_bundle).pack(anchor="w")

    def export_bundle(self) -> None:
        path = filedialog.asksaveasfilename(
            title="Exportar configuração",
            defaultextension=".json",
            filetypes=[("JSON", "*.json")],
            initialfile=f"automacao-novelis-config-{datetime.now():%Y%m%d-%H%M%S}.json",
        )
        if not path:
            return
        try:
            bundle = export_config_bundle(self.root_path, Path(path))
        except Exception as exc:
            messagebox.showerror("Exportar configuração", str(exc))
            return
        total_captures = len(bundle.get("captureFiles") or {})
        messagebox.showinfo(
            "Exportar configuração",
            f"Configuração exportada para:\n{path}\n\n{total_captures} mapa(s) de passos incluído(s).",
        )

    def import_bundle(self) -> None:
        path = filedialog.askopenfilename(title="Importar configuração", filetypes=[("JSON", "*.json")])
        if not path:
            return
        if not messagebox.askyesno(
            "Importar configuração",
            "Isso substitui usuários/senhas, configurações e mapas de passos atuais pelos do arquivo. Continuar?",
        ):
            return
        try:
            applied = import_config_bundle(self.root_path, Path(path))
        except Exception as exc:
            messagebox.showerror("Importar configuração", str(exc))
            return
        self.env_values = read_env_values(self.root_path)
        messagebox.showinfo(
            "Importar configuração",
            "Importado:\n" + "\n".join(applied) + "\n\nFeche e abra as Configurações de novo para ver os valores atualizados.",
        )

    def _buttons(self) -> None:
        buttons = ttk.Frame(self, style="SettingsFooter.TFrame", padding=(16, 0, 16, 14))
        buttons.pack(fill="x")
        tk.Button(
            buttons,
            text="Salvar",
            command=self.save,
            bg=PRIMARY,
            fg="#ffffff",
            activebackground="#1d4ed8",
            activeforeground="#ffffff",
            relief="flat",
            padx=22,
            pady=7,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        ).pack(side="left")
        ttk.Button(buttons, text="Fechar", command=self.destroy).pack(side="right")

    def _tab(self, tabs: ttk.Notebook, title: str) -> ttk.Frame:
        frame = ttk.Frame(tabs, padding=16, style="SettingsTab.TFrame")
        tabs.add(frame, text=title)
        return frame

    def _section(self, parent: ttk.Frame, title: str, hint: str = "") -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=title, padding=14, style="SettingsCard.TLabelframe")
        if hint:
            ttk.Label(frame, text=hint, style="SettingsHint.TLabel").grid(
                row=0,
                column=0,
                columnspan=4,
                sticky="w",
                pady=(0, 12),
            )
        return frame

    def _readonly(self, frame: ttk.Frame, label: str, value: str) -> None:
        ttk.Label(frame, text=label, style="SettingsLabel.TLabel").pack(anchor="w")
        var = tk.StringVar(value=value)
        self.readonly_vars[label] = var
        entry = ttk.Entry(frame, textvariable=var)
        entry.configure(state="readonly")
        entry.pack(fill="x", pady=(0, 8))

    def _entry(self, frame: ttk.Frame, label: str, key: str) -> None:
        ttk.Label(frame, text=label, style="SettingsLabel.TLabel").pack(anchor="w")
        var = tk.StringVar(value=str(self.settings.get(key, "")))
        self.vars[key] = var
        ttk.Entry(frame, textvariable=var).pack(fill="x", pady=(0, 8))

    def _grid_entry(
        self,
        frame: ttk.Frame,
        label: str,
        key: str,
        row: int,
        column: int,
        columnspan: int = 1,
    ) -> None:
        ttk.Label(frame, text=label, style="SettingsLabel.TLabel").grid(
            row=row,
            column=column,
            columnspan=columnspan,
            sticky="w",
            padx=(0 if column == 0 else 8, 0),
            pady=(10, 2),
        )
        var = tk.StringVar(value=str(self.settings.get(key, "")))
        self.vars[key] = var
        ttk.Entry(frame, textvariable=var).grid(
            row=row + 1,
            column=column,
            columnspan=columnspan,
            sticky="ew",
            padx=(0 if column == 0 else 8, 0),
        )

    def _env_entry(self, frame: ttk.Frame, label: str, key: str, show: str = "") -> None:
        ttk.Label(frame, text=label, style="SettingsLabel.TLabel").pack(anchor="w")
        var = tk.StringVar(value=self.env_values.get(key, ""))
        self.env_vars[key] = var
        ttk.Entry(frame, textvariable=var, show=show).pack(fill="x", pady=(0, 8))

    def _password_entry(self, frame: ttk.Frame, label: str, key: str) -> None:
        ttk.Label(frame, text=label, style="SettingsLabel.TLabel").pack(anchor="w")
        ttk.Entry(frame, textvariable=self.vars[key], show="*").pack(fill="x", pady=(0, 8))

    def _db_entry(self, frame: ttk.Frame, label: str, key: str, value: str, show: str = "") -> None:
        ttk.Label(frame, text=label, style="SettingsLabel.TLabel").pack(anchor="w")
        var = tk.StringVar(value=value)
        self.db_vars[key] = var
        ttk.Entry(frame, textvariable=var, show=show).pack(fill="x", pady=(0, 8))

    def save(self) -> None:
        try:
            self._save_settings()
            env_updates = {key: var.get() for key, var in self.env_vars.items()}
            env_updates["SYSTEM_UPDATE_SOURCE_DIR"] = str(self.vars["update_source_dir"].get())
            env_updates["SYSTEM_UPDATE_CHECK_INTERVAL_SECONDS"] = str(
                self.vars["update_check_interval_seconds"].get()
            )
            env_updates["BROWSER_HEADLESS"] = self._bool_env(self.vars["browser_headless"].get())
            env_updates["CONSULTA_BROWSER_HEADLESS"] = self._bool_env(self.vars["consulta_headless"].get())
            env_updates["COMPROVANTE_PREFIXES"] = self._comprovante_prefixes_value()
            env_updates["COMPROVANTE_ZIP_PREFIXES"] = self._comprovante_zip_prefixes_value()
            env_updates["RODOPAR_PDF_EXTRA_DOWNLOAD_DIRS"] = self._extra_download_dirs_value()
            env_updates.update(self._database_env_updates())
            update_env_values(self.root_path, env_updates)
        except ValueError as exc:
            messagebox.showerror("Configurações", str(exc))
            return
        self.app.settings = self.settings
        self.app.client = ApiClient(str(self.settings["backend_url"]))
        messagebox.showinfo("Configurações", "Configurações salvas. Reinicie o backend para recarregar o .env.")

    def _save_settings(self) -> None:
        self.settings["auto_run_enabled"] = bool(self.vars["auto"].get())
        self.settings["auto_consult_enabled"] = bool(self.vars["auto_consult"].get())
        self.settings["update_enabled"] = bool(self.vars["update_enabled"].get())
        self.settings["backend_url"] = str(self.vars["backend_url"].get()).strip()
        self.settings["frontend_url"] = str(self.vars["frontend_url"].get()).strip()
        self.settings["update_source_dir"] = str(self.vars["update_source_dir"].get()).strip()
        for key in (
            "start_delay_minutes",
            "automation_interval_minutes",
            "consult_interval_minutes",
            "update_check_interval_seconds",
        ):
            self.settings[key] = int(str(self.vars[key].get() or "0"))
        self.settings["start_time"] = str(self.vars["start_time"].get()).strip()
        self.settings["weekdays"] = [day for day, var in self.weekday_vars.items() if var.get()]
        new_password = str(self.vars["new_password"].get())
        confirm = str(self.vars["confirm_password"].get())
        if new_password:
            if new_password != confirm:
                raise ValueError("Confirmação de senha não confere.")
            set_password(self.settings, new_password)
        save_settings(self.root_path, self.settings)

    def stop_service(self) -> None:
        request_service_stop(self.root_path)
        messagebox.showinfo("Serviço", "Sinal de encerramento enviado ao serviço.")

    def _env_bool(self, key: str, default: bool) -> bool:
        raw = self.env_values.get(key)
        if raw is None:
            return default
        return raw.strip().lower() in {"1", "true", "sim", "yes", "on"}

    def _database_env_updates(self) -> dict[str, str]:
        host = str(self.db_vars["host"].get()).strip()
        port = str(self.db_vars["port"].get()).strip()
        server = host
        if host and port:
            server = f"{host},{port}"
        return {
            "CONSULTA_DB_HOST": host,
            "CONSULTA_DB_PORT": port,
            "CONSULTA_DB_SERVER": server,
            "CONSULTA_DB_USER": str(self.db_vars["user"].get()).strip(),
            "CONSULTA_DB_PASS": str(self.db_vars["pass"].get()).strip(),
            "CONSULTA_DB_DATABASE": str(self.db_vars["database"].get()).strip(),
        }

    @staticmethod
    def _split_server(server: str) -> tuple[str, str]:
        value = str(server or "").strip()
        if "," not in value:
            return value, ""
        host, port = value.rsplit(",", 1)
        return host.strip(), port.strip()

    @staticmethod
    def _bool_env(value: object) -> str:
        return "true" if bool(value) else "false"

    def _configure_styles(self) -> None:
        style = ttk.Style(self)
        for theme in ("vista", "xpnative", "default"):
            try:
                style.theme_use(theme)
                break
            except tk.TclError:
                continue
        style.configure("SettingsRoot.TFrame", background=BG)
        style.configure("SettingsHeader.TFrame", background=BG)
        style.configure("SettingsFooter.TFrame", background=BG)
        style.configure("SettingsTab.TFrame", background=BG)
        style.configure("SettingsTitle.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 16, "bold"))
        style.configure("SettingsHint.TLabel", background=BG, foreground=MUTED, font=("Segoe UI", 9))
        style.configure("SettingsLabel.TLabel", background=BG, foreground=TEXT, font=("Segoe UI", 9, "bold"))
        style.configure("Settings.TCheckbutton", background=BG, foreground=TEXT, font=("Segoe UI", 9))
        style.map("Settings.TCheckbutton", background=[("active", BG)])
        style.configure("Settings.TNotebook", background=BG, borderwidth=0, tabmargins=(0, 0, 0, 0))
        style.configure(
            "Settings.TNotebook.Tab",
            padding=(14, 8),
            background="#e6edf5",
            foreground=TEXT,
            font=("Segoe UI", 9),
            borderwidth=0,
            relief="flat",
        )
        style.map(
            "Settings.TNotebook.Tab",
            background=[("selected", SURFACE), ("active", "#f8fafc")],
            foreground=[("selected", PRIMARY)],
        )
        style.configure(
            "SettingsCard.TLabelframe",
            background=BG,
            bordercolor=BORDER,
            lightcolor=BORDER,
            darkcolor=BORDER,
            borderwidth=1,
            relief="flat",
        )
        style.configure(
            "SettingsCard.TLabelframe.Label",
            background=BG,
            foreground=TEXT,
            font=("Segoe UI", 10, "bold"),
        )
