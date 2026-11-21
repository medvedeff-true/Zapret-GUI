"""Unprivileged service client: bounded JSON control frames + binary uploads."""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import stat as stat_module
import struct
import subprocess
import threading
import time
import zlib


PROTOCOL = 2
# Files are streamed, not allocated at these limits. Keep these in sync with
# Uploads in Service.cs. A bound still protects the SYSTEM staging volume.
MAX_PROFILE_BYTES = 8 * 1024 * 1024 * 1024
MAX_PROFILE_FILES = 256
MAX_PAYLOAD_BYTES = 16 * 1024 * 1024
MAX_APP_SCOPE_BYTES = 1 * 1024 * 1024
MAX_CONTROL_BYTES = 4 * 1024 * 1024
BLOCK_BYTES = 256 * 1024
BLOCK_HEADER = struct.Struct("<III")  # decoded length, wire length, codec (0/raw, 1/gzip)
STOCK_ENGINE_FILES = (
    "winws.exe",
    "cygwin1.dll",
    "WinDivert.dll",
    "WinDivert64.sys",
)
APP_ENGINE_FILES = (
    "medvedeff-winws/medvedeff-winws.exe",
    "medvedeff-winws/cygwin1.dll",
    "medvedeff-winws/cygz.dll",
    "medvedeff-winws/WinDivert.dll",
    "medvedeff-winws/WinDivert64.sys",
    "medvedeff-winws/LICENSE.txt",
    "medvedeff-winws/WINDIVERT-LICENSE.txt",
    "medvedeff-winws/CYGWIN-LICENSE.txt",
    "medvedeff-winws/ZLIB-LICENSE.txt",
    "medvedeff-winws/SOURCES.txt",
)
ENGINE_FILES = STOCK_ENGINE_FILES + APP_ENGINE_FILES
FILE_OPTIONS = {"hostlist", "hostlist-exclude", "ipset", "ipset-exclude"}
APP_SCOPE_FILE_OPTION = "app-scope-file"
ENGINE_NAMES = {"winws", "medvedeff-winws"}
PAYLOAD_OPTIONS = {
    "dpi-desync-split-seqovl-pattern", "dpi-desync-fakedsplit-pattern", "dpi-desync-udplen-pattern",
    *("dpi-desync-fake-" + name for name in (
        "http", "tls", "unknown", "syndata", "quic", "wireguard", "dht", "discord", "stun", "unknown-udp")),
}


class UploadError(ConnectionError):
    """An interrupted upload cannot be replayed or resumed on the same pipe."""


@dataclass(frozen=True)
class ProfileSource:
    path: Path
    size: int
    mtime_ns: int
    compress: bool


class ProfileRequest(dict):
    """Only metadata is serializable; local paths never cross the trust boundary."""

    def __init__(
        self,
        arguments: list[dict],
        files: list[dict],
        sources: list[ProfileSource],
        engine: str = "winws",
    ):
        super().__init__(op="start", args=arguments, files=files, engine=engine)
        self.sources = tuple(sources)
        self.cancel_event = None


def engine_fingerprint(directory: str | Path) -> str:
    root = Path(directory)
    files = ENGINE_FILES if application_engine_present(root) else STOCK_ENGINE_FILES
    manifest = "".join(
        name + ":" + hashlib.sha256((root / name).read_bytes()).hexdigest() + "\n"
        for name in files
    )
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def application_engine_present(core_bin: str | Path) -> bool:
    root = Path(core_bin)
    try:
        return all((root / name).is_file() and (root / name).stat().st_size > 0
                   for name in APP_ENGINE_FILES)
    except OSError:
        return False


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
    expected_paths = {
        os.path.normcase(os.path.abspath(Path(core_bin) / "winws.exe")): "winws",
        os.path.normcase(os.path.abspath(Path(core_bin) / "medvedeff-winws" / "medvedeff-winws.exe")): "medvedeff-winws",
    }
    if not parts:
        raise ValueError("Профиль не содержит исполняемый файл winws")
    executable_key = os.path.normcase(os.path.abspath(parts[0]))
    engine = expected_paths.get(executable_key)
    if engine is None:
        raise ValueError("Профиль должен запускать core/bin/winws.exe или core/bin/medvedeff-winws/medvedeff-winws.exe")
    arguments, files, sources, indices = [], [], [], {}
    app_scope_count = 0
    total = 0
    for token in parts[1:]:
        if not token.startswith("--"):
            raise ValueError("Неподдерживаемый аргумент профиля: " + token)
        name, separator, value = token[2:].partition("=")
        argument = {"name": name, "value": value if separator else None}
        path, prefix = None, ""
        if name in FILE_OPTIONS or name == APP_SCOPE_FILE_OPTION:
            path = value
            if name == APP_SCOPE_FILE_OPTION:
                app_scope_count += 1
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
                if not stat_module.S_ISREG(source.stat().st_mode):
                    raise ValueError(f"Ожидался обычный файл стратегии: {source.name}")
                with source.open("rb") as stream:
                    stat = os.fstat(stream.fileno())
                    gzipped = stream.read(2) == b"\x1f\x8b"
                total += stat.st_size
                if total > MAX_PROFILE_BYTES:
                    raise ValueError(
                        f"Общий размер файлов стратегии превышает {MAX_PROFILE_BYTES // (1024 ** 3)} ГиБ "
                        f"(файл: {source.name}, размер: {stat.st_size:,} байт)"
                    )
                if len(files) >= MAX_PROFILE_FILES:
                    raise ValueError(f"В стратегии больше {MAX_PROFILE_FILES} файлов")
                indices[key] = len(files)
                files.append({"size": stat.st_size, "gzip": gzipped})
                sources.append(ProfileSource(source, stat.st_size, stat.st_mtime_ns,
                                             name in FILE_OPTIONS and not gzipped))
            elif name in FILE_OPTIONS and not files[indices[key]]["gzip"]:
                # A file can appear as both a payload and a hostlist.
                index = indices[key]
                old = sources[index]
                sources[index] = ProfileSource(old.path, old.size, old.mtime_ns, True)
            if name not in FILE_OPTIONS and files[indices[key]]["size"] > MAX_PAYLOAD_BYTES:
                raise ValueError(f"Бинарный файл стратегии {source.name} превышает 16 МиБ (--{name})")
            if name == APP_SCOPE_FILE_OPTION:
                metadata = files[indices[key]]
                if metadata["gzip"] or not 1 <= metadata["size"] <= MAX_APP_SCOPE_BYTES:
                    raise ValueError("Application scope file must be plain UTF-8 (1 byte to 1 MiB)")
            argument = {"name": name, "file": indices[key], "prefix": prefix}
        arguments.append(argument)
    if engine == "medvedeff-winws" and app_scope_count != 1:
        raise ValueError("medvedeff-winws requires exactly one --app-scope-file")
    if engine == "winws" and app_scope_count:
        raise ValueError("--app-scope-file is only valid for medvedeff-winws")
    return ProfileRequest(arguments, files, sources, engine=engine)


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

    def _write(self, data: bytes) -> None:
        # One bounded ctypes copy, including when WriteFile completes partially.
        buffer = ctypes.create_string_buffer(data)
        offset = 0
        while offset < len(data):
            offset += self._io(ctypes.byref(buffer, offset), len(data) - offset, True)

    def _send_control(self, message: dict) -> None:
        body = json.dumps(message, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        if len(body) > MAX_CONTROL_BYTES:
            raise ValueError("Команда фоновой службе превышает 1 МиБ")
        self._write(struct.pack("<I", len(body)))
        self._write(body)

    def _reply(self) -> dict:
        size, = struct.unpack("<I", self._read(4))
        if not 0 < size <= MAX_CONTROL_BYTES:
            raise ValueError("Invalid service response length")
        reply = json.loads(self._read(size).decode("utf-8"))
        if not reply.get("ok"):
            raise RuntimeError(reply.get("error") or "Background service failed")
        return reply

    def _upload_file(self, source: ProfileSource, cancel_event=None) -> None:
        digest = hashlib.sha256()
        remaining = source.size
        try_compression = source.compress
        with source.path.open("rb") as stream:
            stat = os.fstat(stream.fileno())
            if (stat.st_size, stat.st_mtime_ns) != (source.size, source.mtime_ns):
                raise ValueError(f"Список изменился перед запуском: {source.path.name}. Повторите запуск.")
            while remaining:
                if cancel_event is not None and cancel_event.is_set():
                    raise UploadError("Передача файлов стратегии отменена")
                data = stream.read(min(BLOCK_BYTES, remaining))
                if not data:
                    raise ValueError(f"Файл был усечён при передаче: {source.path.name}")
                remaining -= len(data)
                digest.update(data)
                wire, codec = data, 0
                if try_compression:
                    # compressobj also supports Python 3.10; level 1 prioritizes
                    # latency, not maximum ratio. Already-gzipped files skip this.
                    compressor = zlib.compressobj(1, zlib.DEFLATED, 31)
                    compressed = compressor.compress(data) + compressor.flush()
                    if len(compressed) < len(data) * 0.95:
                        wire, codec = compressed, 1
                    else:
                        try_compression = False
                self._write(BLOCK_HEADER.pack(len(data), len(wire), codec))
                self._write(wire)
            extra = stream.read(1)
            stat = os.fstat(stream.fileno())
            if extra or (stat.st_size, stat.st_mtime_ns) != (source.size, source.mtime_ns):
                raise ValueError(f"Список изменился при передаче: {source.path.name}. Повторите запуск.")
        self._write(BLOCK_HEADER.pack(0, 0, 0))
        self._write(digest.digest())

    def request(self, message: dict) -> dict:
        if isinstance(message, ProfileRequest) and len(message["files"]) != len(message.sources):
            raise ValueError("Некорректное число файлов стратегии")
        self._send_control(message)
        reply = self._reply()
        if not isinstance(message, ProfileRequest):
            return reply
        if not reply.get("upload"):
            raise ValueError("Фоновая служба не поддерживает потоковую передачу списков")
        try:
            for index, source in enumerate(message.sources):
                self._upload_file(source, message.cancel_event)
                if self._reply().get("received") != index:
                    raise ValueError("Нарушен порядок передачи файлов стратегии")
        except Exception as exc:
            # The server may still be expecting binary data. Never send a JSON
            # command into that stream; disconnect rolls back the entire upload.
            self.close()
            raise UploadError(str(exc)) from exc
        # All binary input has been acknowledged. A normal launch/validation
        # failure does not corrupt the connection and must remain retryable.
        return self._reply()


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
        self._cancel_transfer = threading.Event()

    def snapshot(self) -> dict:
        # Assignment of the entire dictionary is atomic; never block Qt on pipe I/O.
        return dict(self.state)

    def _request(self, message: dict) -> dict:
        try:
            if isinstance(message, ProfileRequest):
                message.cancel_event = self._cancel_transfer
            result = self.pipe.request(message)
        except (OSError, ValueError, ConnectionError):
            self.pipe.close()
            self.pipe = None
            self.state = {"running": False, "error": "Потеряна связь с фоновой службой"}
            raise
        # Ai DNS is an acknowledgement-only control command. Its response
        # intentionally has no process snapshot and must not overwrite the
        # live winws state used by ServiceProcess.poll(). Other commands
        # (hello/status/start/stop) are authoritative service snapshots.
        if message.get("op") != "ai-dns-hosts":
            self.state = result
        return result

    def _connect_existing_service(self) -> bool:
        """Connect to an installed service without installing or changing it."""
        if self.pipe is not None:
            return True
        sid = current_user_sid()
        name = "ZapretGUI.Bypass." + sid
        try:
            service_pid(name, start=True)
        except OSError as exc:
            if getattr(exc, "winerror", None) == 1060:
                return False
            raise
        deadline = time.monotonic() + 15
        while True:
            try:
                self.pipe = Pipe(name)
                return True
            except OSError as exc:
                if exc.winerror not in (2, 231) or time.monotonic() >= deadline:
                    raise
                time.sleep(0.15)

    def ensure(
        self,
        helper: str | Path,
        core_bin: str | Path,
        *,
        _updated: bool = False,
        _require_helper: bool = False,
    ):
        with self.lock:
            if self.closed:
                raise RuntimeError("Application is shutting down")
            sid = current_user_sid()
            name = "ZapretGUI.Bypass." + sid
            fingerprint = engine_fingerprint(core_bin)
            # The helper is part of the installed privileged implementation,
            # not just an optional feature.  Comparing it only when
            # ``_require_helper`` was set allowed an older service to survive
            # a GUI/service update when the WinDivert engine files happened to
            # be unchanged.  That broke newer IPC operations (notably Ai DNS
            # and runtime ACL repair) until the user manually reinstalled the
            # service.  A hash mismatch now triggers the one intentional
            # elevation boundary for the new service version; unchanged
            # versions continue without UAC.
            helper_hash = hashlib.sha256(Path(helper).read_bytes()).hexdigest()
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
            if (
                status.get("protocol") != PROTOCOL
                or status.get("engine") != fingerprint
                or status.get("helper") != helper_hash
            ):
                if _updated:
                    raise RuntimeError("Версия установленной фоновой службы не совпадает с приложением")
                self._request({"op": "stop"})
                self.pipe.close()
                self.pipe = None
                install_service(helper, core_bin, sid)
                return self.ensure(helper, core_bin, _updated=True, _require_helper=_require_helper)
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
            self._cancel_transfer.clear()
            self.ensure(helper, core_bin)
            reply = self._request(request)
            if not reply.get("running") or not reply.get("pid"):
                raise RuntimeError("Служба не подтвердила запуск winws")
            return ServiceProcess(self, int(reply["pid"]))

    def stop(self):
        self._cancel_transfer.set()
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

    def ai_dns_hosts(self, content: str, expected_hash: str, mode: str, helper: str | Path, core_bin: str | Path) -> dict:
        """Ask the already-installed SYSTEM helper to publish hosts atomically."""
        if mode not in {"apply", "restore"}:
            raise ValueError("Invalid Ai DNS hosts operation")
        if not isinstance(content, str) or len(content.encode("utf-8")) > 2 * 1024 * 1024:
            raise ValueError("Ai DNS hosts content is too large")
        with self.lock:
            self.ensure(helper, core_bin)
            return self._request({
                "op": "ai-dns-hosts",
                "hosts": content,
                "hosts_hash": str(expected_hash or "").lower(),
                "hosts_mode": mode,
            })

    def repair_runtime_access(self, helper: str | Path, core_bin: str | Path) -> dict:
        """Repair ACLs of the user runtime through the already-installed SYSTEM service."""
        with self.lock:
            if not self._connect_existing_service():
                return {"ok": False, "installed": False}
            helper_hash = hashlib.sha256(Path(helper).read_bytes()).hexdigest()
            current = self._request({"op": "hello"})
            features = set(current.get("features") or [])
            if (
                current.get("protocol") != PROTOCOL
                or current.get("engine") != engine_fingerprint(core_bin)
                or "runtime-access" not in features
                or current.get("helper") != helper_hash
            ):
                self.pipe.close()
                self.pipe = None
                # This is the single intentional UAC boundary for a new
                # service/helper version. After this, repair and normal
                # operation continue through the installed SYSTEM service.
                self.ensure(helper, core_bin, _require_helper=True)
            return self._request({"op": "repair-runtime-access"})

    def disconnect(self):
        """Close only the current IPC session, keeping the controller reusable."""
        self._cancel_transfer.set()
        with self.lock:
            if self.pipe is not None:
                self.pipe.close()
                self.pipe = None
            self.state = {}

    def close(self):
        self._cancel_transfer.set()
        self.closed = True
        with self.lock:
            if self.pipe is not None:
                self.pipe.close()  # server finally + kill-on-close job handles GUI crashes too
                self.pipe = None


controller = Controller()
