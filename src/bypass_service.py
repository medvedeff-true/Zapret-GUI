"""Unprivileged client for ZapretGUI.Service.exe (length-framed JSON, no pickle)."""
from __future__ import annotations

import base64
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import threading
import time


PROTOCOL = 1
ENGINE_FILES = ("winws.exe", "cygwin1.dll", "WinDivert.dll", "WinDivert64.sys")
FILE_OPTIONS = {"hostlist", "hostlist-exclude", "ipset", "ipset-exclude"}
PAYLOAD_OPTIONS = {
    "dpi-desync-split-seqovl-pattern", "dpi-desync-fakedsplit-pattern", "dpi-desync-udplen-pattern",
    *("dpi-desync-fake-" + name for name in (
        "http", "tls", "unknown", "syndata", "quic", "wireguard", "dht", "discord", "stun", "unknown-udp")),
}


def engine_fingerprint(directory: str | Path) -> str:
    manifest = "".join(
        name + ":" + hashlib.sha256((Path(directory) / name).read_bytes()).hexdigest() + "\n"
        for name in ENGINE_FILES
    )
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def split_commandline(command: str) -> list[str]:
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell.CommandLineToArgvW.argtypes = [wintypes.LPCWSTR, ctypes.POINTER(ctypes.c_int)]
    shell.CommandLineToArgvW.restype = ctypes.POINTER(wintypes.LPWSTR)
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    count = ctypes.c_int()
    result = shell.CommandLineToArgvW(command, ctypes.byref(count))
    if not result:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return [result[index] for index in range(count.value)]
    finally:
        kernel.LocalFree(result)


def profile_request(command: str, core_bin: str | Path) -> dict:
    """Read inputs as the GUI user. The service never opens a client-supplied path."""
    parts = split_commandline(command)
    expected = os.path.normcase(os.path.abspath(Path(core_bin) / "winws.exe"))
    if not parts or os.path.normcase(os.path.abspath(parts[0])) != expected:
        raise ValueError("Профиль должен запускать core/bin/winws.exe")
    arguments, files, indices = [], [], {}
    total = 0
    for token in parts[1:]:
        if not token.startswith("--"):
            raise ValueError("Неподдерживаемый аргумент профиля: " + token)
        name, separator, value = token[2:].partition("=")
        argument = {"name": name, "value": value if separator else None}
        path, prefix = None, ""
        if name in FILE_OPTIONS:
            path = value
        elif name in PAYLOAD_OPTIONS:
            if not re.fullmatch(r"0x[0-9a-fA-F]+|!(?:\+[0-9]+)?", value):
                match = re.fullmatch(r"(\+[0-9]+)?@(.+)", value)
                prefix, path = (match.group(1) or "", match.group(2)) if match else ("", value)
        elif name in {"wf-raw", "wf-raw-part"} and value.startswith("@"):
            path = value[1:]
        if path is not None:
            if not path:
                raise ValueError("Не указан файл для --" + name)
            source = Path(path)
            if not source.is_absolute():
                source = Path(core_bin) / source
            key = os.path.normcase(os.path.abspath(source))
            if key not in indices:
                with source.open("rb") as stream:
                    data = stream.read(32 * 1024 * 1024 + 1)
                total += len(data)
                if total > 32 * 1024 * 1024:
                    raise ValueError("Файлы стратегии превышают 32 МиБ")
                indices[key] = len(files)
                files.append(base64.b64encode(data).decode("ascii"))
            argument = {"name": name, "file": indices[key], "prefix": prefix}
        arguments.append(argument)
    return {"op": "start", "args": arguments, "files": files}


def current_user_sid() -> str:
    advapi = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    advapi.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    advapi.ConvertSidToStringSidW.argtypes = [ctypes.c_void_p, ctypes.POINTER(wintypes.LPWSTR)]
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.LocalFree.argtypes = [ctypes.c_void_p]
    token, needed = wintypes.HANDLE(), wintypes.DWORD()
    if not advapi.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        advapi.GetTokenInformation(token, 1, None, 0, ctypes.byref(needed))
        buffer = ctypes.create_string_buffer(needed.value)
        if not advapi.GetTokenInformation(token, 1, buffer, needed, ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        sid = ctypes.cast(buffer, ctypes.POINTER(ctypes.c_void_p))[0]
        text = wintypes.LPWSTR()
        if not advapi.ConvertSidToStringSidW(sid, ctypes.byref(text)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            return text.value
        finally:
            kernel.LocalFree(text)
    finally:
        kernel.CloseHandle(token)


def service_pid(name: str, start: bool = False) -> int:
    """SCM authenticates the pipe server, and can start an installed stopped service."""
    api = ctypes.WinDLL("advapi32", use_last_error=True)
    api.OpenSCManagerW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR, wintypes.DWORD]
    api.OpenSCManagerW.restype = wintypes.HANDLE
    api.OpenServiceW.argtypes = [wintypes.HANDLE, wintypes.LPCWSTR, wintypes.DWORD]
    api.OpenServiceW.restype = wintypes.HANDLE
    api.StartServiceW.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p]
    api.QueryServiceStatusEx.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    api.CloseServiceHandle.argtypes = [wintypes.HANDLE]
    scm = api.OpenSCManagerW(None, None, 1)
    if not scm:
        raise ctypes.WinError(ctypes.get_last_error())
    service = None
    try:
        service = api.OpenServiceW(scm, name, 4 | (16 if start else 0))
        if not service:
            raise ctypes.WinError(ctypes.get_last_error())
        if start and not api.StartServiceW(service, 0, None) and ctypes.get_last_error() != 1056:
            raise ctypes.WinError(ctypes.get_last_error())
        status = (wintypes.DWORD * 9)()
        needed = wintypes.DWORD()
        if not api.QueryServiceStatusEx(service, 0, status, ctypes.sizeof(status), ctypes.byref(needed)):
            raise ctypes.WinError(ctypes.get_last_error())
        return int(status[7]) if status[1] == 4 else 0
    finally:
        if service:
            api.CloseServiceHandle(service)
        api.CloseServiceHandle(scm)


class _Overlapped(ctypes.Structure):
    _fields_ = [("Internal", ctypes.c_size_t), ("InternalHigh", ctypes.c_size_t),
                ("Offset", wintypes.DWORD), ("OffsetHigh", wintypes.DWORD), ("hEvent", wintypes.HANDLE)]


class Pipe:
    def __init__(self, name: str, *, authenticate: bool = True):
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        api = self.api
        api.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
        api.CreateFileW.restype = wintypes.HANDLE
        api.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        api.CreateEventW.restype = wintypes.HANDLE
        api.CloseHandle.argtypes = [wintypes.HANDLE]
        api.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        api.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Overlapped)]
        api.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(_Overlapped), ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
        api.GetNamedPipeServerProcessId.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
        for op in (api.ReadFile, api.WriteFile):
            op.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD), ctypes.POINTER(_Overlapped)]
        # SQOS=IDENTIFICATION: a spoofed pipe cannot impersonate an elevated GUI.
        self.handle = api.CreateFileW("\\\\.\\pipe\\" + name, 0x100083, 0, None, 3, 0x40110000, None)
        if self.handle == ctypes.c_void_p(-1).value:
            self.handle = None
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            pid = wintypes.DWORD()
            if not api.GetNamedPipeServerProcessId(self.handle, ctypes.byref(pid)):
                raise ctypes.WinError(ctypes.get_last_error())
            if authenticate and pid.value != service_pid(name):
                raise RuntimeError("Не удалось подтвердить подлинность фоновой службы")
        except Exception:
            self.close()
            raise

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None

    def _io(self, buffer, size: int, write: bool) -> int:
        event = self.api.CreateEventW(None, True, False, None)
        if not event:
            raise ctypes.WinError(ctypes.get_last_error())
        pending = _Overlapped(hEvent=event)
        transferred = wintypes.DWORD()
        try:
            ok = (self.api.WriteFile if write else self.api.ReadFile)(
                self.handle, buffer, size, ctypes.byref(transferred), ctypes.byref(pending))
            if not ok:
                if ctypes.get_last_error() != 997:
                    raise ctypes.WinError(ctypes.get_last_error())
                if self.api.WaitForSingleObject(event, 20000) != 0:
                    self.api.CancelIoEx(self.handle, ctypes.byref(pending))
                    self.api.GetOverlappedResult(self.handle, ctypes.byref(pending), ctypes.byref(transferred), True)
                    raise TimeoutError("Фоновая служба не ответила за 20 секунд")
                if not self.api.GetOverlappedResult(self.handle, ctypes.byref(pending), ctypes.byref(transferred), False):
                    raise ctypes.WinError(ctypes.get_last_error())
            if transferred.value == 0:
                raise ConnectionError("Соединение с фоновой службой закрыто")
            return transferred.value
        finally:
            self.api.CloseHandle(event)

    def _read(self, size: int) -> bytes:
        result = bytearray()
        while len(result) < size:
            buffer = ctypes.create_string_buffer(min(65536, size - len(result)))
            count = self._io(buffer, len(buffer), False)
            result.extend(buffer.raw[:count])
        return bytes(result)

    def request(self, message: dict) -> dict:
        body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > 48 * 1024 * 1024:
            raise ValueError("Profile request exceeds 48 MiB")
        body = struct.pack("<I", len(body)) + body
        offset = 0
        while offset < len(body):
            chunk = body[offset:offset + 65536]
            offset += self._io(ctypes.create_string_buffer(chunk), len(chunk), True)
        size, = struct.unpack("<I", self._read(4))
        if not 0 < size <= 1024 * 1024:
            raise ValueError("Invalid service response length")
        reply = json.loads(self._read(size).decode("utf-8"))
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error") or "Background service failed")
        return reply


def install_service(helper: str | Path, core_bin: str | Path, sid: str) -> None:
    """The only elevation boundary; ShellExecute elevates a GUI-subsystem installer."""
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("fMask", wintypes.ULONG), ("hwnd", wintypes.HWND),
                    ("lpVerb", wintypes.LPCWSTR), ("lpFile", wintypes.LPCWSTR), ("lpParameters", wintypes.LPCWSTR),
                    ("lpDirectory", wintypes.LPCWSTR), ("nShow", ctypes.c_int), ("hInstApp", wintypes.HINSTANCE),
                    ("lpIDList", ctypes.c_void_p), ("lpClass", wintypes.LPCWSTR), ("hkeyClass", wintypes.HKEY),
                    ("dwHotKey", wintypes.DWORD), ("hIcon", wintypes.HANDLE), ("hProcess", wintypes.HANDLE)]
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    shell.ShellExecuteExW.argtypes = [ctypes.POINTER(ExecuteInfo)]
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    info = ExecuteInfo()
    info.cbSize = ctypes.sizeof(info)
    info.fMask = 0x40 | 0x100  # NOCLOSEPROCESS | NOASYNC
    info.lpVerb = "runas"
    info.lpFile = str(Path(helper).resolve())
    info.lpParameters = subprocess.list2cmdline(["--install", str(Path(core_bin).resolve()), sid])
    info.lpDirectory = str(Path(helper).resolve().parent)
    if not shell.ShellExecuteExW(ctypes.byref(info)):
        code = ctypes.get_last_error()
        if code == 1223:
            raise RuntimeError("Установка фоновой службы отменена. Для работы обхода нужно однократное разрешение администратора.")
        raise ctypes.WinError(code)
    try:
        # UAC/installer runs in a worker. Never launch another process on timeout.
        if kernel.WaitForSingleObject(info.hProcess, 180000) != 0:
            raise TimeoutError("Установка службы ещё не завершена. Дождитесь её завершения и повторите запуск.")
        code = wintypes.DWORD()
        if not kernel.GetExitCodeProcess(info.hProcess, ctypes.byref(code)):
            raise ctypes.WinError(ctypes.get_last_error())
        if code.value:
            raise RuntimeError("Не удалось установить фоновую службу (код " + str(code.value) + ")")
    finally:
        kernel.CloseHandle(info.hProcess)


class ServiceProcess:
    def __init__(self, controller: "Controller", pid: int):
        self.controller, self.pid = controller, pid

    def poll(self):
        status = self.controller.snapshot()
        if status.get("pid") != self.pid:
            return 1
        return None if status.get("running") else status.get("exit_code", 1)

    def kill(self):
        self.controller.stop()

    terminate = kill


class Controller:
    def __init__(self):
        self.lock = threading.RLock()
        self.pipe = None
        self.state = {}
        self.closed = False
        self.monitor = None

    def snapshot(self) -> dict:
        # Assignment of the entire dictionary is atomic; never block Qt on pipe I/O.
        return dict(self.state)

    def _request(self, message: dict) -> dict:
        try:
            result = self.pipe.request(message)
        except (OSError, ValueError, ConnectionError):
            self.pipe.close()
            self.pipe = None
            self.state = {"running": False, "error": "Потеряна связь с фоновой службой"}
            raise
        self.state = result
        return result

    def ensure(self, helper: str | Path, core_bin: str | Path, *, _updated: bool = False):
        with self.lock:
            if self.closed:
                raise RuntimeError("Application is shutting down")
            sid = current_user_sid()
            name = "ZapretGUI.Bypass." + sid
            fingerprint = engine_fingerprint(core_bin)
            if self.pipe is None:
                try:
                    service_pid(name, start=True)
                except OSError as exc:
                    if exc.winerror != 1060:
                        raise
                    install_service(helper, core_bin, sid)
                deadline = time.monotonic() + 15
                while True:
                    try:
                        self.pipe = Pipe(name)
                        break
                    except OSError as exc:
                        if exc.winerror not in (2, 231) or time.monotonic() >= deadline:
                            raise
                        time.sleep(0.15)
            status = self._request({"op": "hello"})
            if (status.get("protocol") != PROTOCOL or status.get("engine") != fingerprint
                    or status.get("helper") != hashlib.sha256(Path(helper).read_bytes()).hexdigest()):
                if _updated:
                    raise RuntimeError("Версия установленной фоновой службы не совпадает с приложением")
                self._request({"op": "stop"})
                self.pipe.close()
                self.pipe = None
                install_service(helper, core_bin, sid)
                return self.ensure(helper, core_bin, _updated=True)
            if self.monitor is None:
                self.monitor = threading.Thread(target=self._monitor, name="bypass-service-status", daemon=True)
                self.monitor.start()

    def _monitor(self):
        while not self.closed:
            time.sleep(2)
            with self.lock:
                if self.pipe is not None:
                    try:
                        self._request({"op": "status"})
                    except Exception as exc:
                        self.state = {"running": False, "error": str(exc)}

    def start(self, command: str, core_bin: str | Path, helper: str | Path) -> ServiceProcess:
        request = profile_request(command, core_bin)
        with self.lock:
            self.ensure(helper, core_bin)
            reply = self._request(request)
            if not reply.get("running") or not reply.get("pid"):
                raise RuntimeError("Служба не подтвердила запуск winws")
            return ServiceProcess(self, int(reply["pid"]))

    def stop(self):
        with self.lock:
            if self.pipe is not None:
                reply = self._request({"op": "stop"})
                if reply.get("running"):
                    raise RuntimeError("Служба не подтвердила остановку winws")

    def telegram_hosts(self, enabled: bool):
        with self.lock:
            if self.pipe is None:
                raise RuntimeError("Фоновая служба не подключена")
            self._request({"op": "telegram-hosts-on" if enabled else "telegram-hosts-off"})

    def disconnect(self):
        """Close only the current IPC session, keeping the controller reusable."""
        with self.lock:
            if self.pipe is not None:
                self.pipe.close()
                self.pipe = None
            self.state = {}

    def close(self):
        with self.lock:
            self.closed = True
            if self.pipe is not None:
                self.pipe.close()  # server finally + kill-on-close job handles GUI crashes too
                self.pipe = None


controller = Controller()
