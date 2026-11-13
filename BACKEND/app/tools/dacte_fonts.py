"""Register existing vendor TrueType fonts through Windows, without redistributing them."""

import ctypes
import hashlib
import os
import shutil
from pathlib import Path


def repair_qr_font() -> dict:
    import winreg

    from fontTools.ttLib import TTFont

    key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts"
    source = None
    aliases = []
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            for index in range(winreg.QueryInfoKey(key)[1]):
                name, value, _ = winreg.EnumValue(key, index)
                if name.casefold() in {"bcsqrcode", "bcsqrcode (truetype)"}:
                    aliases.append((name, value))
                    candidate = Path(os.path.expandvars(value))
                    if not candidate.is_absolute():
                        candidate = Path(os.environ["SystemRoot"]) / "Fonts" / candidate
                    if candidate.is_file():
                        source = source or candidate
    except FileNotFoundError:
        pass
    if source is None:
        return {"status": "missing", "message": "Instale a fonte BcsQrcode pelo pacote oficial."}
    with TTFont(source) as font:
        if font["name"].getDebugName(1) != "BcsQrcode":
            return {"status": "failed", "message": "A fonte registrada nao e a familia esperada."}
    destination = Path(os.environ["SystemRoot"]) / "Fonts" / "BcsQrcode.ttf"
    source_hash = hashlib.sha256(source.read_bytes()).hexdigest()
    if destination.is_file():
        if hashlib.sha256(destination.read_bytes()).hexdigest() != source_hash:
            return {"status": "conflict", "message": "Outra versao da fonte ja existe. Nenhuma fonte foi substituida."}
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            try:
                value, _ = winreg.QueryValueEx(key, "BcsQrcode (TrueType)")
                if (
                    Path(value).name.casefold() == destination.name.casefold()
                    and all(str(value).casefold() == destination.name.casefold() for _, value in aliases)
                ):
                    return {"status": "already_registered", "sha256": source_hash}
            except FileNotFoundError:
                pass
    if not ctypes.windll.shell32.IsUserAnAdmin():
        return {
            "status": "needs_admin",
            "message": "Registrar a mesma fonte BcsQrcode para o exportador PDF legado exige administrador.",
        }
    # Preserve the exact vendor bytes and variant; never change embedding flags.
    if not destination.is_file():
        shutil.copyfile(source, destination)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    add_font = gdi.AddFontResourceExW
    add_font.argtypes = [ctypes.c_wchar_p, ctypes.c_uint, ctypes.c_void_p]
    add_font.restype = ctypes.c_int
    if add_font(str(destination), 0, None) == 0:
        return {"status": "failed", "message": "O Windows recusou o registro da fonte."}
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path, 0, winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key, "BcsQrcode (TrueType)", 0, winreg.REG_SZ, destination.name)
        for name, _ in aliases:
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, destination.name)
    ctypes.windll.user32.SendMessageTimeoutW(0xFFFF, 0x001D, 0, 0, 2, 3000, None)
    return {
        "status": "registered", "sha256": source_hash, "recheck_required": True,
        "previous_registration": [{"name": name, "file": value} for name, value in aliases],
    }
