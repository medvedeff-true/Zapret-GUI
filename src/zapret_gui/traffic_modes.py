"""Traffic processing mode state and runtime helpers.

The stock winws binary opens WinDivert at the NETWORK layer. A NETWORK packet
does not contain a process id, so a raw filter made from the selected
processes' current sockets is only a snapshot of those sockets. It cannot
implement an application scope for browsers: a new tab creates new sockets
whose first packets are outside that snapshot.

Applications mode uses the separate process-aware engine instead of building
an address snapshot in the GUI.
"""

from __future__ import annotations

import ipaddress
import json
import os
import re
from pathlib import Path
from typing import Iterable

try:
    import psutil
except Exception:  # pragma: no cover - optional on non-Windows test hosts
    psutil = None


TRAFFIC_MODE_ALL = "all"
TRAFFIC_MODE_APPLICATIONS = "applications"
TRAFFIC_MODE_LISTS = "lists"
TRAFFIC_MODES = (TRAFFIC_MODE_ALL, TRAFFIC_MODE_APPLICATIONS, TRAFFIC_MODE_LISTS)

TRAFFIC_MODE_KEY = "traffic_processing/mode"
TRAFFIC_LIST_DOMAINS_ADD_KEY = "traffic_processing/lists/domains_add"
TRAFFIC_LIST_DOMAINS_EXCLUDE_KEY = "traffic_processing/lists/domains_exclude"
TRAFFIC_LIST_IP_ADD_KEY = "traffic_processing/lists/ip_add"
TRAFFIC_LIST_IP_EXCLUDE_KEY = "traffic_processing/lists/ip_exclude"
TRAFFIC_APPS_KEY = "traffic_processing/apps"

LIST_OPTIONS = {
    "domains_add": TRAFFIC_LIST_DOMAINS_ADD_KEY,
    "domains_exclude": TRAFFIC_LIST_DOMAINS_EXCLUDE_KEY,
    "ip_add": TRAFFIC_LIST_IP_ADD_KEY,
    "ip_exclude": TRAFFIC_LIST_IP_EXCLUDE_KEY,
}

_PATH_RECORD_RE = re.compile(r"^\s*(?P<path>.+?)\s*$")
# WinDivert's filter compiler has a considerably smaller practical expression
# limit than the command/service protocol.  Keeping the generated expression
# below 5 KiB leaves room for the parser's internal representation.  The
# previous 96-endpoint/14 KiB bound produced a syntactically balanced string
# which WinDivert nevertheless rejected with ERROR_INVALID_PARAMETER (87).
_MAX_FILTER_ENDPOINTS = 32
_MAX_FILTER_LENGTH = 5000
APPLICATION_SCOPE_MAX_APPS = 256
APPLICATION_MODE_UNAVAILABLE_REASON = "Не найден полный комплект medvedeff-winws."


def normalize_traffic_mode(value: object) -> str:
    """Normalize a persisted mode and keep unknown values fail-safe."""

    normalized = str(value or "").strip().casefold()
    aliases = {
        "all": TRAFFIC_MODE_ALL,
        "full": TRAFFIC_MODE_ALL,
        "весь трафик": TRAFFIC_MODE_ALL,
        "applications": TRAFFIC_MODE_APPLICATIONS,
        "application": TRAFFIC_MODE_APPLICATIONS,
        "apps": TRAFFIC_MODE_APPLICATIONS,
        "приложения": TRAFFIC_MODE_APPLICATIONS,
        "lists": TRAFFIC_MODE_LISTS,
        "list": TRAFFIC_MODE_LISTS,
        "только списки": TRAFFIC_MODE_LISTS,
    }
    return aliases.get(normalized, TRAFFIC_MODE_ALL)


def mode_index(mode: object) -> int:
    return TRAFFIC_MODES.index(normalize_traffic_mode(mode))


def mode_from_index(index: object) -> str:
    try:
        index = int(index)
    except (TypeError, ValueError):
        return TRAFFIC_MODE_ALL
    if not 0 <= index < len(TRAFFIC_MODES):
        return TRAFFIC_MODE_ALL
    return TRAFFIC_MODES[index]


def settings_bool(settings, key: str, default: bool = False) -> bool:
    """Read a QSettings-like value while tolerating simple test doubles."""

    try:
        value = settings.value(key, default, type=bool)
    except TypeError:
        try:
            value = settings.value(key, default)
        except Exception:
            return bool(default)
    except Exception:
        return bool(default)
    if isinstance(value, str):
        lowered = value.strip().casefold()
        if lowered in {"0", "false", "no", "off", "нет"}:
            return False
        if lowered in {"1", "true", "yes", "on", "да"}:
            return True
    return bool(value)


def settings_mode(settings, key: str, default: str = TRAFFIC_MODE_ALL) -> str:
    try:
        value = settings.value(key, default)
    except Exception:
        value = default
    return normalize_traffic_mode(value)


def normalize_executable_path(path: str | os.PathLike[str]) -> str:
    value = os.path.abspath(os.path.expandvars(os.path.expanduser(str(path or "").strip())))
    try:
        value = os.path.realpath(value)
    except OSError:
        pass
    return os.path.normcase(value)


def display_executable_name(path: str) -> str:
    return os.path.basename(str(path).rstrip("\\/")) or str(path)


def _path_is_executable(path: str) -> bool:
    return bool(path) and os.path.isfile(path) and os.path.splitext(path)[1].casefold() == ".exe"


def load_app_records(settings) -> list[dict]:
    raw = settings.value(TRAFFIC_APPS_KEY, "[]")
    # The management dialog keeps its canonical, atomically written store in
    # <app-dir>/user.  Read it at launch as well, so selecting applications
    # does not require opening Settings again before the next bypass start.
    try:
        settings_file = Path(str(settings.fileName()))
        store_path = settings_file.parent / "user" / "traffic_apps.json"
        if store_path.is_file():
            raw = json.loads(store_path.read_text(encoding="utf-8")).get("records", [])
    except (AttributeError, OSError, TypeError, ValueError, json.JSONDecodeError):
        pass
    if isinstance(raw, list):
        values = raw
    else:
        try:
            values = json.loads(str(raw or "[]"))
        except (TypeError, ValueError):
            values = []
    if not isinstance(values, list):
        values = []
    result: list[dict] = []
    seen: set[str] = set()
    for item in values:
        if isinstance(item, str):
            item = {"path": item, "enabled": True, "source": "file"}
        if not isinstance(item, dict):
            continue
        path = normalize_executable_path(item.get("path", ""))
        if not path or path in seen:
            continue
        seen.add(path)
        result.append({
            "path": path,
            "label": str(item.get("label") or display_executable_name(path)),
            "source": str(item.get("source") or "file"),
            "enabled": bool(item.get("enabled", True)),
            "missing": not _path_is_executable(path),
        })
    return result


def save_app_records(settings, records: Iterable[dict]) -> list[dict]:
    merged: dict[str, dict] = {}
    for item in records or ():
        if isinstance(item, str):
            item = {"path": item}
        if not isinstance(item, dict):
            continue
        path = normalize_executable_path(item.get("path", ""))
        if not path:
            continue
        old = merged.get(path, {})
        merged[path] = {
            **old,
            **item,
            "path": path,
            "label": str(item.get("label") or old.get("label") or display_executable_name(path)),
            "enabled": bool(item.get("enabled", old.get("enabled", True))),
            "missing": not _path_is_executable(path),
        }
    result = list(merged.values())
    settings.setValue(TRAFFIC_APPS_KEY, json.dumps(result, ensure_ascii=False, separators=(",", ":")))
    settings.sync()
    return result


def selected_app_paths(settings) -> list[str]:
    return [
        item["path"] for item in load_app_records(settings)
        if item.get("enabled") and _path_is_executable(item.get("path", ""))
    ]


def effective_application_paths(settings) -> list[str]:
    """Return canonical, bounded paths for the process-aware backend."""

    result: list[str] = []
    seen: set[str] = set()
    for path in selected_app_paths(settings):
        normalized = normalize_executable_path(path)
        key = os.path.normcase(normalized)
        if not normalized or key in seen:
            continue
        seen.add(key)
        result.append(normalized)
    return result


def selected_list_enabled(settings, key: str) -> bool:
    return bool(settings.value(LIST_OPTIONS[key], False, type=bool))


def list_has_values(path: str | os.PathLike[str]) -> bool:
    try:
        with open(path, "r", encoding="utf-8-sig", errors="ignore") as stream:
            for raw in stream:
                line = raw.split("#", 1)[0].split(";", 1)[0].strip()
                if line:
                    return True
    except (OSError, UnicodeError):
        return False
    return False


def _safe_endpoint(connection) -> tuple[str, str, int, str, int] | None:
    try:
        remote = connection.raddr
        local = connection.laddr
        if not remote or not local:
            return None
        remote_address = str(remote.ip if hasattr(remote, "ip") else remote[0])
        remote_port = int(remote.port if hasattr(remote, "port") else remote[1])
        local_address = str(local.ip if hasattr(local, "ip") else local[0])
        local_port = int(local.port if hasattr(local, "port") else local[1])
        remote_ip = ipaddress.ip_address(remote_address)
        local_ip = ipaddress.ip_address(local_address)
        if remote_ip.version != local_ip.version:
            return None
        proto = "tcp" if int(connection.type) == 1 else "udp" if int(connection.type) == 2 else ""
        if not proto or not (0 < remote_port <= 65535) or not (0 < local_port <= 65535):
            return None
        # Loopback/link-local/multicast sockets are local IPC or discovery
        # traffic.  They cannot benefit from DPI desync and only consume a
        # scarce slot in the bounded WinDivert filter.
        if (
            local_ip.is_unspecified
            or remote_ip.is_unspecified
            or remote_ip.is_loopback
            or remote_ip.is_link_local
            or remote_ip.is_multicast
        ):
            return None
        return proto, str(local_ip), local_port, str(remote_ip), remote_port
    except (AttributeError, TypeError, ValueError, OSError):
        return None


def collect_application_endpoints(settings, max_endpoints: int = _MAX_FILTER_ENDPOINTS) -> list[tuple[str, str, int, str, int]]:
    if psutil is None:
        return []
    selected = set(selected_app_paths(settings))
    if not selected:
        return []
    endpoints: set[tuple[str, str, int, str, int]] = set()

    # Prefer querying each selected process directly.  On Windows,
    # psutil.net_connections() can return pid=None (or omit the PID entirely)
    # for connections belonging to an ordinary user process, while
    # Process.net_connections() still returns that process' sockets.  The old
    # global-only implementation consequently produced ``false`` for a
    # correctly selected browser and silently captured no traffic.
    try:
        processes = psutil.process_iter(["pid", "exe"])
    except (OSError, psutil.Error):
        processes = ()
    for process in processes:
        try:
            info = getattr(process, "info", {}) or {}
            path = normalize_executable_path(info.get("exe") or process.exe())
            if path not in selected:
                continue
            connections = process.net_connections(kind="inet")
        except (AttributeError, OSError, psutil.Error):
            continue
        for connection in connections:
            endpoint = _safe_endpoint(connection)
            if endpoint:
                endpoints.add(endpoint)
                if len(endpoints) >= max(1, int(max_endpoints)):
                    return sorted(endpoints)

    # Keep the system-wide query as a fallback for platforms/psutil versions
    # where per-process socket enumeration is unavailable.
    try:
        connections = psutil.net_connections(kind="inet")
    except (OSError, psutil.Error):
        return sorted(endpoints)
    pid_paths: dict[int, str] = {}
    for connection in connections:
        pid = getattr(connection, "pid", None)
        if not pid:
            continue
        path = pid_paths.get(pid)
        if path is None:
            try:
                path = normalize_executable_path(psutil.Process(pid).exe())
            except (OSError, psutil.Error):
                path = ""
            pid_paths[pid] = path
        if path not in selected:
            continue
        endpoint = _safe_endpoint(connection)
        if endpoint:
            endpoints.add(endpoint)
            if len(endpoints) >= max(1, int(max_endpoints)):
                break
    return sorted(endpoints)


def build_application_raw_filter(settings, max_endpoints: int = _MAX_FILTER_ENDPOINTS) -> str:
    endpoints = collect_application_endpoints(settings, max_endpoints=max_endpoints)
    if not endpoints:
        # ``0`` is not a valid WinDivert filter expression.  It is parsed as
        # an invalid token and causes winws to exit with ERROR_INVALID_PARAMETER
        # before it can start.  ``false`` is the documented fail-closed
        # boolean expression.
        return "false"
    clauses = []
    for proto, local_address, local_port, remote_address, remote_port in endpoints:
        version = ipaddress.ip_address(local_address).version
        field = "ip" if version == 4 else "ipv6"
        # DPI desync is applied to outbound client traffic.  Capturing the
        # reverse direction doubles the expression without helping the
        # desync decision and was the main reason browser-sized snapshots
        # exceeded WinDivert's parser limit.
        clause = (
            f"({proto} and outbound and {field}.SrcAddr == {local_address} and "
            f"{proto}.SrcPort == {local_port} and {field}.DstAddr == {remote_address} and "
            f"{proto}.DstPort == {remote_port})"
        )
        # Do not slice a completed filter at an arbitrary character.  The
        # previous implementation could cut through an IP/parenthesis when a
        # browser had many connections, producing an invalid --wf-raw filter
        # and making application mode fail to start.  Keep only complete
        # clauses within the service/engine bound; this remains fail-closed
        # and leaves the periodic refresh to pick up the rest later.
        candidate_length = (
            2
            + sum(len(item) for item in clauses)
            + 4 * len(clauses)  # separators: " or "
            + len(clause)
        )
        if candidate_length > _MAX_FILTER_LENGTH:
            break
        clauses.append(clause)
    if not clauses:
        return "false"
    return "(" + " or ".join(clauses) + ")"


def application_filter_signature(settings) -> tuple[str, ...]:
    return tuple(
        f"{proto}:{local_address}:{local_port}:{remote_address}:{remote_port}"
        for proto, local_address, local_port, remote_address, remote_port
        in collect_application_endpoints(settings)
    )


def selected_application_pids(settings) -> tuple[int, ...]:
    """Return current PIDs whose executable path is selected by the user.

    PIDs are sent only as a launch-time hint to the SYSTEM-side FLOW tracker.
    The tracker still receives the authoritative process ownership from
    WinDivert FLOW events; a PID is never persisted as application identity.
    """
    if psutil is None:
        return ()
    selected = set(selected_app_paths(settings))
    if not selected:
        return ()
    result: set[int] = set()
    try:
        processes = psutil.process_iter(["pid", "exe"])
    except (OSError, psutil.Error):
        return ()
    for process in processes:
        try:
            path = normalize_executable_path(process.info.get("exe") or "")
            if path in selected:
                result.add(int(process.info["pid"]))
        except (KeyError, TypeError, ValueError, OSError, psutil.Error):
            continue
    return tuple(sorted(pid for pid in result if 0 < pid <= 0xFFFFFFFF))


def list_mode_files(settings, user_dir: str | os.PathLike[str]) -> dict[str, str]:
    root = Path(user_dir)
    return {
        "domains_add": str(root / "list-general-user.txt"),
        "domains_exclude": str(root / "list-exclude-user.txt"),
        "ip_add": str(root / "ipset-all-user.txt"),
        "ip_exclude": str(root / "ipset-exclude-user.txt"),
    }


def enabled_nonempty_list_files(settings, user_dir: str | os.PathLike[str]) -> dict[str, str]:
    return {
        key: path
        for key, path in list_mode_files(settings, user_dir).items()
        if selected_list_enabled(settings, key) and list_has_values(path)
    }


def mark_missing_records(records: Iterable[dict]) -> list[dict]:
    result = []
    for item in records or ():
        if not isinstance(item, dict):
            continue
        copy = dict(item)
        copy["missing"] = not _path_is_executable(str(copy.get("path", "")))
        if copy["missing"]:
            copy["enabled"] = False
        result.append(copy)
    return result


def application_mode_available(core_bin: str | os.PathLike[str]) -> bool:
    """Check local runtime files; the service reports actual startup readiness."""
    from bypass_service import application_engine_present

    return application_engine_present(core_bin)
