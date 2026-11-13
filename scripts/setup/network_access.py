"""Check the configured operational folder before starting the installed API."""
import os
import stat
from pathlib import Path, PureWindowsPath

AUTH_ERRORS = {5, 86, 1326, 1330, 1331, 1385, 1909}
MESSAGES = {
    "network_authentication_required": "Autentique esta conta do Windows no servidor do banco compartilhado.",
    "network_authentication_cancelled": "A autenticacao de rede foi cancelada. Execute o instalador novamente para autenticar.",
    "network_session_conflict": "O Windows tem uma conexao com esse servidor usando outra conta. Regularize essa sessao de rede e tente novamente.",
    "network_share_unavailable": "A pasta do banco compartilhado esta indisponivel. Verifique conexao, caminho e permissoes.",
}


class NetworkAccessError(RuntimeError):
    def __init__(self, reason: str, code: int):
        super().__init__(MESSAGES[reason])
        self.reason = reason
        self.checks = {"network_winerror": code}


def database_folder(root: Path) -> Path | None:
    from dotenv import dotenv_values

    configured = os.environ.get("NOVELIS_SQLITE_PATH")
    if configured is None:
        configured = dotenv_values(root / "BACKEND/.env").get("NOVELIS_SQLITE_PATH")
    if not configured:
        return None
    path = Path(configured)
    return (path if path.is_absolute() else root / "BACKEND" / path).parent


def probe_folder(folder: Path) -> None:
    if not stat.S_ISDIR(folder.stat().st_mode):
        raise NotADirectoryError("Operational folder unavailable")


def ensure_database_access(root: Path, *, interactive: bool = False) -> dict:
    folder = database_folder(root)
    if folder is None:
        return {"configured": False}
    try:
        probe_folder(folder)
        return {"configured": True, "folder_accessible": True, "credential_prompted": False}
    except OSError as error:
        code = getattr(error, "winerror", None) or error.errno or 1
    anchor = PureWindowsPath(str(folder)).anchor
    if anchor.upper().startswith("\\\\?\\UNC\\"):
        anchor = "\\\\" + anchor[8:]
    if os.name == "nt" and anchor.startswith("\\\\") and code in AUTH_ERRORS and interactive:
        from windows_network import authenticate_share

        code = authenticate_share(anchor.rstrip("\\"), lambda: probe_folder(folder), code)
        if code == 0:
            return {"configured": True, "folder_accessible": True, "credential_prompted": True}
    reason = ("network_session_conflict" if code == 1219 else
              "network_authentication_cancelled" if code == 1223 else
              "network_authentication_required" if code in AUTH_ERRORS else "network_share_unavailable")
    raise NetworkAccessError(reason, code) from None
