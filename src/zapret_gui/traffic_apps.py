"""Application/process selection primitives for traffic processing modes.

This module deliberately has no GUI, WinDivert, service, or command-builder
dependencies.  It provides the state and discovery layer that those parts can
use later:

* executable paths are normalized and de-duplicated across all UI sources;
* selections are persisted as a small, versioned JSON document;
* unavailable files never make the application crash and are excluded from the
  effective selection until they become available again;
* process discovery uses psutil and has a native Windows image-path fallback;
* installed applications are read from the Windows uninstall registry keys.

The store keeps a selection enabled even while its file is missing.  This is
intentional: a selected process may disappear and return later, while a
manually selected application may be temporarily unavailable after an update.
``selected_paths()`` is the only method that returns paths suitable for
runtime use and therefore filters unavailable files.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
from typing import Any, Iterable, Iterator, Mapping

try:  # psutil is a normal project dependency, but keep import failures clear.
    import psutil
except ImportError:  # pragma: no cover - exercised only in broken deployments
    psutil = None  # type: ignore[assignment]

if sys.platform == "win32":  # pragma: no cover - registry code is Windows-only
    import winreg
else:  # pragma: no cover - used by cross-platform unit tests/dev tooling
    winreg = None  # type: ignore[assignment]


TRAFFIC_APPS_SCHEMA_VERSION = 1
DEFAULT_STORAGE_FILENAME = "traffic_apps.json"

SOURCE_INSTALLED = "installed"
SOURCE_PROCESS = "process"
SOURCE_FILE = "file"
KNOWN_SOURCES = frozenset({SOURCE_INSTALLED, SOURCE_PROCESS, SOURCE_FILE})

_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_WINDOWS_MAX_PATH = 32768


def default_storage_path() -> Path:
    """Return the user-scoped default selection file path.

    The caller can always pass an explicit path to :class:`TrafficAppStore`.
    Keeping the default here rather than importing application configuration
    avoids a dependency cycle and makes this module usable by tests and future
    management dialogs.
    """

    root = (
        os.environ.get("LOCALAPPDATA")
        or os.environ.get("APPDATA")
        or str(Path.home())
    )
    return Path(root) / "ZapretGUI" / DEFAULT_STORAGE_FILENAME


def normalize_executable_path(path: str | os.PathLike[str]) -> str:
    """Return an absolute, normalized path without requiring it to exist.

    ``realpath`` is used only for existing files so symlink/junction aliases
    can be de-duplicated.  Missing paths are still normalized and retained in
    the JSON store; this is necessary for process selections to recover when a
    process starts again.
    """

    raw = str(path or "").strip().strip('"')
    if not raw:
        return ""

    raw = os.path.expandvars(os.path.expanduser(raw))
    if not os.path.isabs(raw):
        raw = os.path.abspath(raw)
    # Windows paths are case-insensitive even when the test/runtime host is
    # Linux.  Do not use a host-specific normcase result as the canonical
    # persisted representation.
    if os.name == "nt":
        raw = raw.replace("/", "\\")
    normalized = os.path.normpath(raw)
    if os.path.isfile(normalized):
        normalized = os.path.realpath(normalized)
    return normalized


def executable_path_key(path: str | os.PathLike[str]) -> str:
    """Return the comparison key used for path de-duplication."""

    normalized = normalize_executable_path(path)
    if not normalized:
        return ""
    return os.path.normcase(normalized)


def _display_label(path: str, label: str | None = None) -> str:
    value = str(label or "").strip()
    return value or Path(path).name or path


def _is_available_file(path: str) -> bool:
    try:
        return bool(path and os.path.isfile(path))
    except (OSError, ValueError):
        return False


@dataclass
class AppRecord:
    """A de-duplicated application selection.

    ``sources`` records where the item was discovered/added.  A path selected
    from both the installed-app list and the process list remains one record,
    so removing it from one view does not accidentally remove the other
    source's selection.
    """

    path: str
    label: str
    enabled: bool = True
    sources: set[str] = field(default_factory=set)

    @property
    def available(self) -> bool:
        return _is_available_file(self.path)

    @property
    def missing(self) -> bool:
        return not self.available

    @property
    def key(self) -> str:
        return executable_path_key(self.path)

    def to_json(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "label": self.label,
            "enabled": bool(self.enabled),
            "sources": sorted(source for source in self.sources if source in KNOWN_SOURCES),
        }


@dataclass(frozen=True)
class ProcessInfo:
    """A point-in-time process entry.

    Selections must use ``path`` rather than ``pid`` because PIDs are not
    stable across restarts.  ``session_id == 0`` is exposed as a conservative
    service/system-process hint; it is not treated as a security guarantee.
    """

    pid: int
    name: str
    path: str = ""
    username: str = ""
    status: str = ""
    parent_pid: int | None = None
    session_id: int | None = None
    is_service: bool = False

    @property
    def path_key(self) -> str:
        return executable_path_key(self.path)

    @property
    def selectable(self) -> bool:
        return bool(self.path_key)


@dataclass(frozen=True)
class InstalledApplication:
    """An application discovered from Windows' Add/Remove Programs data."""

    name: str
    path: str = ""
    publisher: str = ""
    version: str = ""
    install_location: str = ""
    registry_source: str = ""

    @property
    def path_key(self) -> str:
        return executable_path_key(self.path)

    @property
    def selectable(self) -> bool:
        return bool(self.path_key)


@dataclass(frozen=True)
class ServiceInfo:
    """A Windows service snapshot with its best-effort executable path."""

    name: str
    display_name: str
    path: str = ""
    status: str = ""
    start_type: str = ""
    username: str = ""
    pid: int | None = None
    description: str = ""

    @property
    def path_key(self) -> str:
        return executable_path_key(self.path)

    @property
    def selectable(self) -> bool:
        return bool(self.path_key)


class TrafficAppStore:
    """Thread-safe persistent store for selected application paths."""

    def __init__(
        self,
        storage_path: str | os.PathLike[str] | None = None,
        *,
        auto_save: bool = True,
    ) -> None:
        self.storage_path = Path(storage_path) if storage_path else default_storage_path()
        self.auto_save = bool(auto_save)
        self._records: dict[str, AppRecord] = {}
        self._lock = threading.RLock()
        self.last_load_error = ""
        self.load()

    def load(self) -> list[AppRecord]:
        """Load records, tolerating a missing or malformed file."""

        with self._lock:
            self._records.clear()
            self.last_load_error = ""
            if not self.storage_path.is_file():
                return self.records()

            try:
                with self.storage_path.open("r", encoding="utf-8") as stream:
                    payload = json.load(stream)
                raw_records = payload.get("records", []) if isinstance(payload, dict) else payload
                if not isinstance(raw_records, list):
                    raise ValueError("records must be a list")
                self._merge_json_records(raw_records)
            except (OSError, ValueError, TypeError, json.JSONDecodeError) as exc:
                # A corrupt settings file must not prevent the GUI from
                # starting.  Do not overwrite it until the user changes a
                # selection, preserving a chance to recover it manually.
                self.last_load_error = str(exc)
            return self.records()

    def save(self) -> None:
        """Atomically save the current selection document."""

        with self._lock:
            parent = self.storage_path.parent
            parent.mkdir(parents=True, exist_ok=True)
            payload = {
                "schema_version": TRAFFIC_APPS_SCHEMA_VERSION,
                "updated_at": datetime.now(timezone.utc).isoformat(),
                "records": [
                    record.to_json()
                    for record in sorted(
                        self._records.values(),
                        key=lambda item: (item.label.casefold(), item.path.casefold()),
                    )
                ],
            }
            temporary_name = ""
            try:
                with tempfile.NamedTemporaryFile(
                    mode="w",
                    encoding="utf-8",
                    newline="\n",
                    prefix=f".{self.storage_path.name}.",
                    suffix=".tmp",
                    dir=str(parent),
                    delete=False,
                ) as stream:
                    temporary_name = stream.name
                    json.dump(payload, stream, ensure_ascii=False, indent=2)
                    stream.write("\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                os.replace(temporary_name, self.storage_path)
            finally:
                if temporary_name:
                    try:
                        os.unlink(temporary_name)
                    except FileNotFoundError:
                        pass

    def records(
        self,
        *,
        source: str | None = None,
        include_missing: bool = True,
    ) -> list[AppRecord]:
        """Return a stable copy of records for UI/model consumers."""

        with self._lock:
            result = []
            for record in self._records.values():
                if source and source not in record.sources:
                    continue
                if not include_missing and record.missing:
                    continue
                result.append(
                    AppRecord(
                        path=record.path,
                        label=record.label,
                        enabled=record.enabled,
                        sources=set(record.sources),
                    )
                )
            return sorted(
                result,
                key=lambda item: (item.label.casefold(), item.path.casefold()),
            )

    def get(self, path: str | os.PathLike[str]) -> AppRecord | None:
        key = executable_path_key(path)
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return None
            return AppRecord(
                path=record.path,
                label=record.label,
                enabled=record.enabled,
                sources=set(record.sources),
            )

    def add(
        self,
        path: str | os.PathLike[str],
        *,
        source: str = SOURCE_FILE,
        label: str | None = None,
        enabled: bool = True,
    ) -> AppRecord | None:
        """Add or merge one path and persist it when ``auto_save`` is enabled."""

        normalized = normalize_executable_path(path)
        key = executable_path_key(normalized)
        if not key:
            return None
        source = str(source or SOURCE_FILE).strip().lower()
        if source not in KNOWN_SOURCES:
            raise ValueError(f"unknown application source: {source}")

        with self._lock:
            record = self._records.get(key)
            if record is None:
                record = AppRecord(
                    path=normalized,
                    label=_display_label(normalized, label),
                    enabled=bool(enabled),
                    sources={source},
                )
                self._records[key] = record
            else:
                record.sources.add(source)
                if label and (not record.label or record.label == Path(record.path).name):
                    record.label = _display_label(record.path, label)
                # Explicitly adding a path is an affirmative user action and
                # re-enables a previously unavailable/disabled selection.
                if enabled:
                    record.enabled = True
            self._commit()
            return self.get(normalized)

    def remove(
        self,
        path: str | os.PathLike[str],
        *,
        source: str | None = None,
    ) -> bool:
        """Remove a path, or only one contributing source, from the store."""

        key = executable_path_key(path)
        if not key:
            return False
        if source is not None:
            source = str(source).strip().lower()
            if source not in KNOWN_SOURCES:
                raise ValueError(f"unknown application source: {source}")

        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            if source is None:
                del self._records[key]
            else:
                record.sources.discard(source)
                if not record.sources:
                    del self._records[key]
            self._commit()
            return True

    def set_enabled(self, path: str | os.PathLike[str], enabled: bool) -> bool:
        key = executable_path_key(path)
        if not key:
            return False
        with self._lock:
            record = self._records.get(key)
            if record is None:
                return False
            record.enabled = bool(enabled)
            self._commit()
            return True

    def selected_paths(self) -> list[str]:
        """Return enabled, currently existing paths for runtime use."""

        with self._lock:
            return [
                record.path
                for record in sorted(
                    self._records.values(),
                    key=lambda item: (item.label.casefold(), item.path.casefold()),
                )
                if record.enabled and record.available
            ]

    def missing_records(self) -> list[AppRecord]:
        return [record for record in self.records() if record.missing]

    def _commit(self) -> None:
        if self.auto_save:
            self.save()

    def _merge_json_records(self, raw_records: Iterable[Any]) -> None:
        for raw in raw_records:
            if not isinstance(raw, Mapping):
                continue
            path = raw.get("path")
            if not isinstance(path, str):
                continue
            normalized = normalize_executable_path(path)
            key = executable_path_key(normalized)
            if not key:
                continue
            sources_raw = raw.get("sources", [SOURCE_FILE])
            if isinstance(sources_raw, str):
                sources_raw = [sources_raw]
            sources = {
                str(item).strip().lower()
                for item in (sources_raw if isinstance(sources_raw, Iterable) else [])
                if str(item).strip().lower() in KNOWN_SOURCES
            }
            if not sources:
                sources = {SOURCE_FILE}
            label = _display_label(normalized, raw.get("label") if isinstance(raw.get("label"), str) else None)
            enabled = bool(raw.get("enabled", True))
            existing = self._records.get(key)
            if existing is None:
                self._records[key] = AppRecord(
                    path=normalized,
                    label=label,
                    enabled=enabled,
                    sources=sources,
                )
            else:
                existing.sources.update(sources)
                existing.enabled = existing.enabled or enabled
                if existing.label == Path(existing.path).name and label:
                    existing.label = label


def _query_process_image_path(pid: int) -> str:
    """Query a process image path using native Windows APIs.

    psutil normally handles this itself.  The fallback is useful for processes
    where the regular ``exe()`` call is denied but the limited-information
    process handle is still available.
    """

    if sys.platform != "win32" or not pid:
        return ""
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(
            _PROCESS_QUERY_LIMITED_INFORMATION,
            False,
            int(pid),
        )
        if not handle:
            return ""
        try:
            size = wintypes.DWORD(_WINDOWS_MAX_PATH)
            buffer = ctypes.create_unicode_buffer(_WINDOWS_MAX_PATH)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(size)):
                return normalize_executable_path(buffer.value)
        finally:
            kernel32.CloseHandle(handle)
    except (AttributeError, OSError, TypeError, ValueError):
        return ""
    return ""


def _query_process_session_id(pid: int) -> int | None:
    """Return a Windows session id without requiring psutil support."""

    if sys.platform != "win32" or not pid:
        return None
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.ProcessIdToSessionId.argtypes = [
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.ProcessIdToSessionId.restype = wintypes.BOOL
        result = wintypes.DWORD()
        if kernel32.ProcessIdToSessionId(int(pid), ctypes.byref(result)):
            return int(result.value)
    except (AttributeError, OSError, TypeError, ValueError):
        pass
    return None


def enumerate_processes(
    *,
    include_unresolved: bool = False,
    resolve_unresolved: bool = True,
) -> list[ProcessInfo]:
    """Return a stable snapshot of currently running processes.

    Access-denied and already-exited processes are skipped rather than
    aborting the complete snapshot.  Duplicate executable paths are retained
    because separate PIDs may be useful in the process-management view.
    """

    if psutil is None:  # pragma: no cover - only broken installations
        raise RuntimeError("psutil is required for process enumeration")

    result: list[ProcessInfo] = []
    try:
        iterator = psutil.process_iter(
            ["pid", "name", "exe", "username", "status", "ppid"]
        )
    except (OSError, RuntimeError):
        return result

    for process in iterator:
        try:
            info = process.info
            pid = int(info.get("pid") or process.pid)
            path = normalize_executable_path(info.get("exe") or "")
            if not path:
                process_exe = getattr(process, "exe", None)
                if callable(process_exe):
                    try:
                        path = normalize_executable_path(process_exe())
                    except (
                        psutil.AccessDenied,
                        psutil.NoSuchProcess,
                        psutil.ZombieProcess,
                        OSError,
                    ):
                        path = ""
            if not path and resolve_unresolved:
                path = _query_process_image_path(pid)
            if not path and not include_unresolved:
                continue

            session_id: int | None
            try:
                session_getter = getattr(process, "session_id", None)
                session_id = (
                    int(session_getter()) if callable(session_getter) else None
                )
            except (AttributeError, psutil.Error, OSError, ValueError):
                session_id = None
            if session_id is None:
                session_id = _query_process_session_id(pid)

            result.append(
                ProcessInfo(
                    pid=pid,
                    name=str(info.get("name") or Path(path).name or f"PID {pid}"),
                    path=path,
                    username=str(info.get("username") or ""),
                    status=str(info.get("status") or ""),
                    parent_pid=_optional_int(info.get("ppid")),
                    session_id=session_id,
                    is_service=session_id == 0,
                )
            )
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, OSError, ValueError):
            continue

    return sorted(
        result,
        key=lambda item: (item.name.casefold(), item.path.casefold(), item.pid),
    )


def _optional_int(value: Any) -> int | None:
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _extract_executable_path(value: str | None) -> str:
    """Extract a file path from a registry ``DisplayIcon`` value."""

    text = os.path.expandvars(str(value or "").strip())
    if not text:
        return ""
    if text.startswith('"'):
        closing_quote = text.find('"', 1)
        candidate = text[1:closing_quote] if closing_quote > 1 else text.strip('"')
    else:
        candidate = text.split(",", 1)[0].strip()
        match = re.match(r"(?i)^(.+?\.exe)(?:\s|$)", candidate)
        if match:
            candidate = match.group(1)
    candidate = candidate.strip().strip('"')
    return normalize_executable_path(candidate) if _is_available_file(candidate) else ""


def _extract_command_executable_path(value: str | None) -> str:
    """Extract an executable from a Windows command line.

    Service ``binpath`` values commonly contain quotes and arguments.  The
    path is returned only when it points to a real file; unresolved services
    remain visible in ``enumerate_services`` but are not selectable.
    """

    text = os.path.expandvars(str(value or "").strip())
    if not text:
        return ""
    if text.startswith('"'):
        closing_quote = text.find('"', 1)
        candidate = text[1:closing_quote] if closing_quote > 1 else text.strip('"')
    else:
        match = re.match(r"(?is)^(.+?\.exe)(?:\s|$)", text)
        candidate = match.group(1) if match else text.split(None, 1)[0]
    candidate = candidate.strip().strip('"')
    return normalize_executable_path(candidate) if _is_available_file(candidate) else ""


def _find_install_location_executable(
    install_location: str,
    display_name: str,
) -> str:
    location = normalize_executable_path(install_location)
    if not location or not os.path.isdir(location):
        return ""
    directory = Path(location)
    wanted = re.sub(r"[^a-z0-9]+", "", display_name.casefold())
    candidates: list[Path] = []
    try:
        for entry in directory.iterdir():
            if entry.is_file() and entry.suffix.casefold() == ".exe":
                candidates.append(entry)
                if len(candidates) >= 128:
                    break
    except OSError:
        return ""
    candidates.sort(
        key=lambda item: (
            0 if wanted and wanted in re.sub(r"[^a-z0-9]+", "", item.stem.casefold()) else 1,
            item.name.casefold(),
        )
    )
    return str(candidates[0]) if candidates else ""


def _registry_uninstall_entries() -> Iterator[dict[str, str]]:
    """Yield normalized uninstall entries from HKCU/HKLM and both views."""

    if winreg is None:
        return

    uninstall_key = r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
    roots = (
        ("HKCU", winreg.HKEY_CURRENT_USER),
        ("HKLM", winreg.HKEY_LOCAL_MACHINE),
    )
    views = [0]
    for name in ("KEY_WOW64_64KEY", "KEY_WOW64_32KEY"):
        value = getattr(winreg, name, 0)
        if value and value not in views:
            views.append(value)

    for root_name, root in roots:
        for view in views:
            access = winreg.KEY_READ | view
            try:
                with winreg.OpenKey(root, uninstall_key, 0, access) as parent:
                    index = 0
                    while True:
                        try:
                            child_name = winreg.EnumKey(parent, index)
                        except OSError:
                            break
                        index += 1
                        try:
                            with winreg.OpenKey(parent, child_name, 0, access) as child:
                                values: dict[str, str] = {}
                                for value_name in (
                                    "DisplayName",
                                    "DisplayIcon",
                                    "InstallLocation",
                                    "Publisher",
                                    "DisplayVersion",
                                ):
                                    try:
                                        value, _ = winreg.QueryValueEx(child, value_name)
                                    except OSError:
                                        value = ""
                                    values[value_name] = str(value or "").strip()
                                if values["DisplayName"]:
                                    values["_registry_source"] = f"{root_name}:{view}:{child_name}"
                                    yield values
                        except OSError:
                            continue
            except OSError:
                continue


def enumerate_installed_applications(
    *,
    include_unresolved: bool = True,
    resolve_install_locations: bool = True,
) -> list[InstalledApplication]:
    """Enumerate Add/Remove Programs entries with best-effort executable paths.

    Registry records without a usable executable are retained by default so a
    future UI can display the complete installed-program list while disabling
    its selection checkbox.  Set ``include_unresolved=False`` to return only
    entries that can be selected by path.
    """

    merged: dict[str, InstalledApplication] = {}
    for entry in _registry_uninstall_entries():
        name = entry.get("DisplayName", "").strip()
        if not name:
            continue
        install_location = entry.get("InstallLocation", "").strip()
        path = _extract_executable_path(entry.get("DisplayIcon"))
        if not path and resolve_install_locations:
            path = _find_install_location_executable(install_location, name)
        if not path and not include_unresolved:
            continue

        application = InstalledApplication(
            name=name,
            path=path,
            publisher=entry.get("Publisher", "").strip(),
            version=entry.get("DisplayVersion", "").strip(),
            install_location=install_location,
            registry_source=entry.get("_registry_source", ""),
        )
        key = application.path_key or f"name:{name.casefold()}"
        existing = merged.get(key)
        if existing is None:
            merged[key] = application
        elif not existing.path and application.path:
            merged[key] = application

    return sorted(
        merged.values(),
        key=lambda item: (item.name.casefold(), item.path.casefold()),
    )


def enumerate_services(*, include_unresolved: bool = True) -> list[ServiceInfo]:
    """Return a stable Windows service snapshot when psutil supports it.

    Services are intentionally separate from ordinary processes.  A service
    can share one host executable with many other services, and selecting the
    executable therefore affects that host process as a whole.  Callers
    should present this distinction before allowing a service selection.
    """

    if sys.platform != "win32" or psutil is None:
        return []
    service_iter = getattr(psutil, "win_service_iter", None)
    if not callable(service_iter):
        return []

    result: list[ServiceInfo] = []
    try:
        services = service_iter()
    except (OSError, RuntimeError):
        return result

    for service in services:
        try:
            info = service.as_dict()
            name = str(info.get("name") or "").strip()
            display_name = str(info.get("display_name") or name).strip()
            if not name:
                continue
            path = _extract_command_executable_path(info.get("binpath"))
            if not path and not include_unresolved:
                continue
            result.append(
                ServiceInfo(
                    name=name,
                    display_name=display_name,
                    path=path,
                    status=str(info.get("status") or "").strip(),
                    start_type=str(info.get("start_type") or "").strip(),
                    username=str(info.get("username") or "").strip(),
                    pid=_optional_int(info.get("pid")),
                    description=str(info.get("description") or "").strip(),
                )
            )
        except (AttributeError, OSError, TypeError, ValueError):
            continue

    return sorted(
        result,
        key=lambda item: (item.display_name.casefold(), item.name.casefold()),
    )


__all__ = [
    "AppRecord",
    "InstalledApplication",
    "ProcessInfo",
    "ServiceInfo",
    "SOURCE_FILE",
    "SOURCE_INSTALLED",
    "SOURCE_PROCESS",
    "TrafficAppStore",
    "default_storage_path",
    "enumerate_installed_applications",
    "enumerate_processes",
    "enumerate_services",
    "executable_path_key",
    "normalize_executable_path",
]
