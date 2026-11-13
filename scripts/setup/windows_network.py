"""Native Windows credential dialog, validated before Windows persists credentials."""
import ctypes
from ctypes import wintypes


class CredentialInfo(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("parent", wintypes.HWND),
                ("message", wintypes.LPCWSTR), ("caption", wintypes.LPCWSTR),
                ("banner", wintypes.HBITMAP)]


class NetworkResource(ctypes.Structure):
    _fields_ = [("scope", wintypes.DWORD), ("kind", wintypes.DWORD),
                ("display", wintypes.DWORD), ("usage", wintypes.DWORD),
                ("local", wintypes.LPCWSTR), ("remote", wintypes.LPCWSTR),
                ("comment", wintypes.LPCWSTR), ("provider", wintypes.LPCWSTR)]


def windows_functions():
    ui, network = ctypes.WinDLL("credui.dll"), ctypes.WinDLL("mpr.dll")
    prompt, confirm = ui.CredUIPromptForCredentialsW, ui.CredUIConfirmCredentialsW
    parse, connect = ui.CredUIParseUserNameW, network.WNetAddConnection2W
    prompt.argtypes = [ctypes.POINTER(CredentialInfo), wintypes.LPCWSTR, ctypes.c_void_p,
                      wintypes.DWORD, wintypes.LPWSTR, wintypes.ULONG,
                      wintypes.LPWSTR, wintypes.ULONG, ctypes.POINTER(wintypes.BOOL), wintypes.DWORD]
    confirm.argtypes = [wintypes.LPCWSTR, wintypes.BOOL]
    parse.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, wintypes.ULONG, wintypes.LPWSTR, wintypes.ULONG]
    connect.argtypes = [ctypes.POINTER(NetworkResource), wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    for function in (prompt, confirm, parse, connect):
        function.restype = wintypes.DWORD
    return prompt, confirm, parse, connect


def authenticate_share(share: str, probe, initial_error: int) -> int:
    prompt, confirm, parse, connect = windows_functions()
    server = share.split("\\")[2]
    info = CredentialInfo(ctypes.sizeof(CredentialInfo), None,
        "Informe uma conta autorizada a acessar " + share + ".",
        "Novelis Cargo Hub - acesso ao banco compartilhado", None)
    resource = NetworkResource(0, 1, 0, 0, None, share, None, None)
    # Windows owns persistence. The operator chooses the Save checkbox.
    expect_confirmation, show_save, server_credential, exclude_certificates = 0x20000, 0x40, 0x4000, 0x8
    code = initial_error
    for _attempt in range(3):
        username, password = ctypes.create_unicode_buffer(514), ctypes.create_unicode_buffer(514)
        account, domain = ctypes.create_unicode_buffer(514), ctypes.create_unicode_buffer(338)
        save = wintypes.BOOL(False)
        prompted = False
        validated = False
        try:
            code = prompt(ctypes.byref(info), server, None, code, username, len(username),
                          password, len(password), ctypes.byref(save),
                          expect_confirmation | show_save | server_credential | exclude_certificates)
            if code:
                return code
            prompted = True
            code = parse(username, account, len(account), domain, len(domain))
            if code == 0:
                identity = domain.value + "\\" + account.value if domain.value else account.value
                code = connect(ctypes.byref(resource), password, identity, 0)
            if code == 0:
                try:
                    probe()
                    validated = True
                except OSError as error:
                    code = getattr(error, "winerror", None) or error.errno or 1
            if validated or code not in {5, 86, 1326, 1330}:
                return code
        finally:
            try:
                if prompted:
                    confirm(server, validated)
            finally:
                for buffer in (password, username, account, domain):
                    ctypes.memset(ctypes.addressof(buffer), 0, ctypes.sizeof(buffer))
    return code
