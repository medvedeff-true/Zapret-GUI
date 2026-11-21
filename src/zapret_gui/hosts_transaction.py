"""Atomic hosts/cache publication without weakening system-file permissions."""
from __future__ import annotations

from contextlib import contextmanager
import ctypes
from ctypes import wintypes
import os
from pathlib import Path
import tempfile


@contextmanager
def hosts_lock():
    if os.name != "nt":
        yield
        return
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
    kernel.CreateMutexW.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.ReleaseMutex.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateMutexW(None, False, "Local\\ZapretGUI.AiDNS.Hosts")
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    acquired = False
    try:
        acquired = kernel.WaitForSingleObject(handle, 10000) in (0, 0x80)
        if not acquired:
            raise TimeoutError("Другая операция Ai DNS ещё выполняется")
        yield
    finally:
        if acquired:
            kernel.ReleaseMutex(handle)
        kernel.CloseHandle(handle)


def atomic_write(path: str | Path, data: bytes, *, system: bool = False) -> None:
    path = Path(path).absolute()
    path.parent.mkdir(parents=True, exist_ok=True)
    previous = path.read_bytes() if path.exists() else None
    if previous == data:
        return
    if system and path.exists():
        stat = path.lstat()
        if path.is_symlink() or getattr(stat, "st_file_attributes", 0) & 0x400:
            raise OSError("The system hosts file must not be a link")
    descriptor, name = tempfile.mkstemp(prefix="." + path.name + "-", suffix=".tmp", dir=path.parent)
    temp = Path(name)
    backup = Path(name + ".rollback")
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if (path.read_bytes() if path.exists() else None) != previous:
            raise OSError("hosts изменился во время записи. Повторите операцию.")
        if system and os.name == "nt" and previous is not None:
            # ReplaceFile preserves the destination DACL/attributes. Do not
            # chmod hosts, disable certificate checks or truncate in place.
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel.ReplaceFileW.argtypes = [wintypes.LPCWSTR] * 3 + [wintypes.DWORD, ctypes.c_void_p, ctypes.c_void_p]
            kernel.ReplaceFileW.restype = wintypes.BOOL
            if not kernel.ReplaceFileW(str(path), str(temp), str(backup), 0, None, None):
                error = ctypes.WinError(ctypes.get_last_error())
                # Windows may have moved the original to backup on a partial
                # failure. Restore only if no other writer published a file.
                if not path.exists() and backup.exists():
                    os.replace(backup, path)
                raise error
        else:
            os.replace(temp, path)
        if path.read_bytes() != data:
            raise OSError("Не удалось подтвердить запись hosts")
    finally:
        temp.unlink(missing_ok=True)
        backup.unlink(missing_ok=True)
