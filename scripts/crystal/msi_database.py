"""Read-only Windows Installer API. Secrets are never included in returned audits."""
import ctypes as c
from pathlib import Path
from crystal.sequence import verify_execute_sequence


class Database:
    def __init__(self, path: Path):
        self.api = c.WinDLL("msi")
        self.api.MsiOpenDatabaseW.argtypes = [c.c_wchar_p, c.c_void_p, c.POINTER(c.c_uint)]
        self.api.MsiDatabaseOpenViewW.argtypes = [c.c_uint, c.c_wchar_p, c.POINTER(c.c_uint)]
        self.api.MsiRecordGetStringW.argtypes = [c.c_uint, c.c_uint, c.c_wchar_p, c.POINTER(c.c_uint)]
        self.handle = c.c_uint()
        self._check(self.api.MsiOpenDatabaseW(str(path), None, c.byref(self.handle)))

    @staticmethod
    def _check(code):
        if code:
            raise RuntimeError("Falha Windows Installer API (" + str(code) + ").")

    def rows(self, query: str):
        view = c.c_uint()
        self._check(self.api.MsiDatabaseOpenViewW(self.handle, query, c.byref(view)))
        try:
            self._check(self.api.MsiViewExecute(view, 0))
            while True:
                record = c.c_uint()
                code = self.api.MsiViewFetch(view, c.byref(record))
                if code == 259:
                    break
                self._check(code)
                try:
                    values = []
                    for i in range(1, self.api.MsiRecordGetFieldCount(record) + 1):
                        size = c.c_uint(65536)
                        buffer = c.create_unicode_buffer(size.value)
                        self._check(self.api.MsiRecordGetStringW(record, i, buffer, c.byref(size)))
                        values.append(buffer.value)
                    yield values
                finally:
                    self.api.MsiCloseHandle(record)
        finally:
            self.api.MsiViewClose(view)
            self.api.MsiCloseHandle(view)

    def close(self):
        self.api.MsiCloseHandle(self.handle)


def inspect_package(path: Path, key: str) -> dict:
    db = Database(path)
    try:
        props = dict(db.rows("SELECT Property, Value FROM Property"))
        files = {name.split("|")[-1].lower(): version for name, version in db.rows("SELECT FileName, Version FROM File")}
        required = ("craxddrt.dll", "craxdrt.dll", "crpe32.dll", "crdb_ado.dll", "u2lcom.dll", "crxf_pdf.dll")
        if any(files.get(name) != "11.5.0.313" for name in required):
            raise ValueError("MSI nao contem o conjunto de DLLs homologado.")
        if "crw32.exe" in files or any(int(row[0] or 0) & 256 for row in db.rows("SELECT Attributes FROM Component")):
            raise ValueError("MSI inclui editor completo ou componente de arquitetura incorreta.")
        key_names = [name for name, value in props.items() if name.startswith("PIDKEY") and value == key]
        hidden = set(props.get("MsiHiddenProperties", "").split(";"))
        if not key_names or not set(key_names).issubset(hidden):
            raise ValueError("Configuracao de PIDKEY ou protecao de logs incompleta.")
        if any(props.get(name) != "1" for name in ("InstallCRDB_ADO", "InstallU2FPDF")):
            raise ValueError("Driver ADO ou exportador PDF nao habilitado.")
        file_rows = list(db.rows("SELECT File, Component_, FileName FROM File"))
        design_files = {row[0] for row in file_rows if row[2].split("|")[-1].lower() == "craxddrt.dll"}
        self_reg = {row[0] for row in db.rows("SELECT File_, Cost FROM SelfReg")}
        if not design_files or not design_files.issubset(self_reg):
            raise ValueError("Registro COM original do modulo Designtime ausente.")
        sequence = verify_execute_sequence(db.rows("SELECT Action, Condition, Sequence FROM InstallExecuteSequence"))
        return {"product_code": props["ProductCode"], "product_version": props["ProductVersion"],
                "required_dll_versions": {name: files[name] for name in required},
                "full_editor_included": False, "pidkey_configured": True,
                "pidkey_properties_hidden": True, "native_action_logging_validated": False,
                "driver_ado_enabled": True, "pdf_exporter_enabled": True,
                "design_com_self_registration_preserved": True,
                "execute_sequence_verified": True, "standard_action_sequence": sequence,
                "self_registering_file_count": len(self_reg), "file_count": len(files)}
    finally:
        db.close()
