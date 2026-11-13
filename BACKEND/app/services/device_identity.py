"""Identify the Windows account and active network interfaces of this backend."""
import ctypes
import getpass
import os
import re
import socket

import psutil


def windows_user() -> str:
    if os.name != "nt":
        return getpass.getuser()
    function = ctypes.WinDLL("secur32.dll", use_last_error=True).GetUserNameExW
    function.argtypes = [ctypes.c_int, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
    function.restype = ctypes.c_int
    buffer = ctypes.create_unicode_buffer(1024)
    size = ctypes.c_ulong(len(buffer))
    if not function(2, buffer, ctypes.byref(size)):
        raise OSError("Nao foi possivel identificar a conta Windows atual.")
    return buffer.value


def device_identity() -> dict:
    addresses = set()
    stats = psutil.net_if_stats()
    for interface, values in psutil.net_if_addrs().items():
        if interface not in stats or not stats[interface].isup:
            continue
        for value in values:
            address = value.address.replace("-", ":").upper()
            if (value.family == psutil.AF_LINK and re.fullmatch(r"(?:[0-9A-F]{2}:){5}[0-9A-F]{2}", address)
                    and address != "00:00:00:00:00:00" and not int(address[:2], 16) & 1):
                addresses.add(address)
    return {"windows_user": windows_user(), "computer_name": socket.gethostname(),
            "mac_addresses": sorted(addresses)}
