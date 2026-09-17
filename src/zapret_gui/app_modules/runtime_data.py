# --- Runtime files, user lists, and mode settings ---------------------------

def _save_autotest_result(best: str | None, good: list[str], bad: list[str]) -> None:
    try:
        data = {
            "best": best or "",
            "good": list(good or []),
            "bad": list(bad or []),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(AUTORESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_autotest_result() -> dict:
    try:
        with open(AUTORESULT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}


def _save_adaptive_strategy_info(path: str, methods: list[str]) -> None:
    try:
        data = {
            "path": str(path or ""),
            "name": os.path.splitext(os.path.basename(str(path or "")))[0],
            "methods": list(dict.fromkeys(str(item) for item in methods if item)),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(os.path.join(USER_DIR, "adaptive-strategy-last.json"), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_adaptive_strategy_info() -> dict:
    try:
        with open(os.path.join(USER_DIR, "adaptive-strategy-last.json"), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}

def _sha256_bytes(data: bytes) -> str:
    try:
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return ""


def _read_file_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return b""


def _atomic_write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
        return
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    with open(path, "wb") as f:
        f.write(data)

def _read_lines_utf8(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f.read().splitlines()]
    except Exception:
        return []


def _write_lines_utf8(path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    uniq = []
    seen = set()
    for x in lines:
        s = (x or "").strip()
        if not s or s.startswith("#"):
            continue
        k = s.casefold()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(s)

    content = "\n".join(uniq) + ("\n" if uniq else "")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, path)
        return
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def _copy_if_missing(src: str, dst: str) -> None:
    try:
        if os.path.exists(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    except Exception:
        pass


def _bundled_root_dir() -> str:
    """Return the read-only bundled resource root in dev and frozen builds."""
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    # Source files live below ``src/zapret_gui`` while bundled resources are
    # kept in the repository's ``resources`` directory.
    source_root = Path(__file__).resolve().parents[2]
    resources_root = source_root / "resources"
    if resources_root.is_dir():
        return str(resources_root)
    return os.path.dirname(__file__)


def _bundled_path(*parts: str) -> str:
    return os.path.join(_bundled_root_dir(), *parts)


def _flowseal_source_path(filename: str) -> str:
    return os.path.join(USER_DIR, f"{FLOWSEAL_SOURCE_PREFIX}{filename}")


def _flowseal_base_paths(filename: str) -> tuple[str, ...]:
    return (
        _flowseal_source_path(filename),
        _bundled_path("core", "lists", filename),
        os.path.join(APP_DIR, "core", "lists", filename),
    )


def _immutable_seeded_base_paths(filename: str) -> list[str]:
    paths = []
    seen = set()
    for path in (
        _flowseal_source_path(filename),
        _bundled_path("core", "lists", filename),
    ):
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def _read_flowseal_base_lines(filename: str) -> list[str]:
    for path in _flowseal_base_paths(filename):
        if os.path.exists(path):
            lines = _read_lines_utf8(path)
            if lines or path != _flowseal_source_path(filename):
                return lines
    return []


def _load_icon_preserving_modes(path: str, fallback: QIcon | None = None) -> QIcon:
    pixmap = QPixmap(path) if os.path.exists(path) else QPixmap()
    if pixmap.isNull():
        return fallback if fallback is not None else QIcon()

    icon = QIcon()
    for mode in (
        QIcon.Mode.Normal,
        QIcon.Mode.Disabled,
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
    ):
        for state in (QIcon.State.Off, QIcon.State.On):
            icon.addPixmap(pixmap, mode, state)
    return icon


def _runtime_user_list_paths() -> tuple[str, ...]:
    return (
        RUNTIME_GENERAL_USER_FILE,
        RUNTIME_EXCLUDE_USER_FILE,
        RUNTIME_IP_ALL_USER_FILE,
        RUNTIME_IP_EXCLUDE_USER_FILE,
    )


def _normalized_value_keys(lines: list[str]) -> set[str]:
    out = set()
    for line in lines:
        s = (line or "").strip()
        if not s or s.startswith("#"):
            continue
        out.add(s.casefold())
    return out


def _ensure_flowseal_source_lists() -> None:
    runtime_lists_dir = os.path.join(APP_DIR, "core", "lists")

    for filename in FLOWSEAL_LIST_FILES:
        dst = _flowseal_source_path(filename)
        if os.path.exists(dst):
            continue

        copied = False
        for src in (
            _bundled_path("core", "lists", filename),
            os.path.join(runtime_lists_dir, filename),
        ):
            if os.path.exists(src):
                try:
                    _copy_if_missing(src, dst)
                    copied = os.path.exists(dst)
                    if copied:
                        break
                except Exception:
                    copied = False

        if not copied:
            try:
                _write_lines_utf8(dst, [])
            except Exception:
                pass


def _flowseal_source_lists_are_ready() -> bool:
    try:
        for filename in FLOWSEAL_LIST_FILES:
            path = _flowseal_source_path(filename)
            if not os.path.exists(path):
                return False
            if os.path.getsize(path) <= 0:
                return False
        return True
    except Exception:
        return False


def _backup_user_list_before_migration(path: str) -> None:
    backup_path = path + USER_LIST_SEEDED_BACKUP_SUFFIX
    try:
        if os.path.exists(path) and not os.path.exists(backup_path):
            shutil.copy2(path, backup_path)
    except Exception:
        pass


def _prune_seeded_user_file(user_path: str, base_paths: list[str]) -> bool:
    current_lines = _read_lines_utf8(user_path)
    current_keys = _normalized_value_keys(current_lines)
    if not current_keys:
        return False

    base_keys = set()
    for base_path in base_paths:
        base_keys.update(_normalized_value_keys(_read_lines_utf8(base_path)))

    if not base_keys:
        return False

    overlap = current_keys & base_keys
    if not overlap:
        return False

    overlap_ratio = len(overlap) / max(1, len(current_keys))
    if overlap_ratio < USER_LIST_SEEDED_OVERLAP_RATIO and len(overlap) != len(current_keys):
        return False

    filtered_lines = [
        line for line in current_lines
        if (line or "").strip().casefold() not in base_keys
    ]
    if len(filtered_lines) == len(current_lines):
        return False

    try:
        _backup_user_list_before_migration(user_path)
        _write_lines_utf8(user_path, filtered_lines)
        return True
    except Exception:
        return False


def _migrate_seeded_user_lists() -> None:
    _ensure_flowseal_source_lists()

    _prune_seeded_user_file(
        USER_GENERAL_FILE,
        _immutable_seeded_base_paths("list-general.txt")
    )
    _prune_seeded_user_file(
        USER_EXCLUDE_FILE,
        _immutable_seeded_base_paths("list-exclude.txt")
    )
    _prune_seeded_user_file(
        USER_IP_ALL_FILE,
        _immutable_seeded_base_paths("ipset-all.txt")
    )
    _prune_seeded_user_file(
        USER_IP_EXCLUDE_FILE,
        _immutable_seeded_base_paths("ipset-exclude.txt")
    )


def _ensure_user_lists_initialized() -> None:
    os.makedirs(USER_DIR, exist_ok=True)
    _ensure_flowseal_source_lists()
    _ensure_telegram_runtime_files()

    if not os.path.exists(USER_GENERAL_FILE):
        try:
            _write_lines_utf8(USER_GENERAL_FILE, [])
        except Exception:
            pass
    if not os.path.exists(USER_EXCLUDE_FILE):
        try:
            _write_lines_utf8(USER_EXCLUDE_FILE, [])
        except Exception:
            pass
    if not os.path.exists(USER_IP_ALL_FILE):
        try:
            _write_lines_utf8(USER_IP_ALL_FILE, [])
        except Exception:
            pass
    if not os.path.exists(USER_IP_EXCLUDE_FILE):
        try:
            _write_lines_utf8(USER_IP_EXCLUDE_FILE, [])
        except Exception:
            pass

    try:
        _migrate_seeded_user_lists()
    except Exception:
        pass


def _load_settings_if_needed(settings: QSettings | None = None) -> QSettings:
    return settings if settings is not None else QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)


def _safe_int_setting(qs: QSettings, key: str, default: int = 0) -> int:
    try:
        return int(qs.value(key, default) or default)
    except Exception:
        return default


def _is_telegram_mode_enabled(settings: QSettings | None = None) -> bool:
    try:
        qs = _load_settings_if_needed(settings)
        return bool(qs.value(TELEGRAM_MODE_ENABLED_KEY, False, type=bool))
    except Exception:
        return False


def _set_telegram_mode_enabled(enabled: bool, settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    qs.setValue(TELEGRAM_MODE_ENABLED_KEY, bool(enabled))
    qs.setValue(TELEGRAM_MODE_PROXY_ENABLED_KEY, bool(enabled))
    port = _safe_int_setting(qs, TELEGRAM_MODE_PROXY_PORT_KEY, 1443)
    if port <= 0 or port > 65535 or port == 1080:
        qs.setValue(TELEGRAM_MODE_PROXY_PORT_KEY, 1443)
    if not _is_valid_telegram_proxy_secret(str(qs.value(TELEGRAM_MODE_PROXY_SECRET_KEY, "") or "")):
        qs.setValue(TELEGRAM_MODE_PROXY_SECRET_KEY, os.urandom(16).hex())
    qs.sync()


def _get_telegram_proxy_port(settings: QSettings | None = None) -> int:
    qs = _load_settings_if_needed(settings)
    port = _safe_int_setting(qs, TELEGRAM_MODE_PROXY_PORT_KEY, 1443)
    if port <= 0 or port > 65535 or port == 1080:
        port = 1443
    return port


def _is_valid_telegram_proxy_secret(value: str) -> bool:
    value = str(value or "").strip().lower()
    if value.startswith("dd") and len(value) == 34:
        value = value[2:]
    if len(value) != 32:
        return False
    try:
        bytes.fromhex(value)
        return True
    except Exception:
        return False


def _get_telegram_proxy_secret(settings: QSettings | None = None) -> str:
    qs = _load_settings_if_needed(settings)
    secret = str(qs.value(TELEGRAM_MODE_PROXY_SECRET_KEY, "") or "").strip().lower()
    if secret.startswith("dd") and len(secret) == 34:
        secret = secret[2:]
    if not _is_valid_telegram_proxy_secret(secret):
        secret = os.urandom(16).hex()
        qs.setValue(TELEGRAM_MODE_PROXY_SECRET_KEY, secret)
        qs.sync()
    return secret


def _get_telegram_proxy_link(settings: QSettings | None = None) -> str:
    return (
        "tg://proxy?server=127.0.0.1"
        f"&port={int(_get_telegram_proxy_port(settings))}"
        f"&secret=dd{_get_telegram_proxy_secret(settings)}"
    )


def _set_telegram_last_error(error: str, settings: QSettings | None = None) -> None:
    try:
        qs = _load_settings_if_needed(settings)
        qs.setValue(TELEGRAM_MODE_LAST_ERROR_KEY, str(error or "").strip())
        qs.sync()
    except Exception:
        pass


def _hosts_contains_flowseal_telegram_block(text: str) -> bool:
    hay = (text or "").casefold()
    return (
        (
            FLOWSEAL_TELEGRAM_HOSTS_BEGIN.casefold() in hay
            and FLOWSEAL_TELEGRAM_HOSTS_END.casefold() in hay
        )
        or (
            "# ZapretGUI Telegram Web hosts begin".casefold() in hay
            and "# ZapretGUI Telegram Web hosts end".casefold() in hay
        )
    )


def _is_telegram_hosts_enabled_by_app(settings: QSettings | None = None) -> bool:
    try:
        qs = _load_settings_if_needed(settings)
        if bool(qs.value(TELEGRAM_MODE_HOSTS_ENABLED_KEY, False, type=bool)):
            return True
    except Exception:
        pass

    try:
        return _hosts_contains_flowseal_telegram_block(_read_hosts_file(DNS_MALW_HOSTS_PATH))
    except Exception:
        return False


def _set_telegram_hosts_enabled_by_app(enabled: bool, settings: QSettings | None = None) -> None:
    try:
        qs = _load_settings_if_needed(settings)
        qs.setValue(TELEGRAM_MODE_HOSTS_ENABLED_KEY, bool(enabled))
        qs.sync()
    except Exception:
        pass


def _set_telegram_hosts_action_status(ok: bool, error: str = "", settings: QSettings | None = None) -> None:
    try:
        qs = _load_settings_if_needed(settings)
        qs.setValue(TELEGRAM_MODE_HOSTS_LAST_ATTEMPT_KEY, int(time.time()))
        qs.setValue(TELEGRAM_MODE_HOSTS_LAST_STATUS_KEY, "ok" if ok else "error")
        qs.setValue(TELEGRAM_MODE_HOSTS_LAST_ERROR_KEY, str(error or "").strip())
        qs.sync()
    except Exception:
        pass


def _ensure_telegram_runtime_files() -> None:
    try:
        _write_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE, _read_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE))
        _write_lines_utf8(RUNTIME_TELEGRAM_IP_FILE, _read_lines_utf8(RUNTIME_TELEGRAM_IP_FILE))
    except Exception:
        pass


def _strip_flowseal_telegram_hosts_block(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    patterns = (
        re.compile(
            rf"(?ms)^{re.escape(FLOWSEAL_TELEGRAM_HOSTS_BEGIN)}\n.*?"
            rf"^{re.escape(FLOWSEAL_TELEGRAM_HOSTS_END)}(?:\n|$)"
        ),
        re.compile(
            r"(?ms)^# ZapretGUI Telegram Web hosts begin\n.*?"
            r"^# ZapretGUI Telegram Web hosts end(?:\n|$)"
        ),
    )
    cleaned = normalized
    for pattern in patterns:
        cleaned = pattern.sub("", cleaned)
    cleaned = cleaned.rstrip()
    return cleaned + ("\n" if cleaned else "")


def _flowseal_telegram_hosts_block() -> str:
    lines = [
        FLOWSEAL_TELEGRAM_HOSTS_BEGIN,
        "# Telegram Web hosts from Flowseal/zapret-discord-youtube .service/hosts",
    ]
    lines.extend(f"{ip} {host}" for ip, host in FLOWSEAL_TELEGRAM_WEB_HOSTS)
    lines.append(FLOWSEAL_TELEGRAM_HOSTS_END)
    return "\n".join(lines).rstrip() + "\n"


def _apply_flowseal_telegram_hosts(enabled: bool, settings: QSettings | None = None) -> bool:
    try:
        try:
            current_hosts = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
        except FileNotFoundError:
            current_hosts = ""

        updated = _strip_flowseal_telegram_hosts_block(current_hosts)
        if enabled:
            if updated and not updated.endswith("\n"):
                updated += "\n"
            updated += _flowseal_telegram_hosts_block()

        if updated != current_hosts:
            if _bypass_service.pipe is not None:
                _bypass_service.telegram_hosts(bool(enabled))
            else:
                _write_hosts_file(updated, DNS_MALW_HOSTS_PATH)
        _run_hidden(["ipconfig", "/flushdns"], timeout=8)
        _set_telegram_hosts_enabled_by_app(bool(enabled), settings)
        _set_telegram_hosts_action_status(True, "", settings)
        _set_telegram_last_error("", settings)
        return True
    except Exception as e:
        error = str(e)
        _set_telegram_hosts_action_status(False, error, settings)
        _set_telegram_last_error(error, settings)
        print("Flowseal Telegram hosts error:", e)
        return False


def _write_telegram_managed_lists() -> None:
    _write_lines_utf8(USER_TELEGRAM_DOMAIN_FILE, list(TELEGRAM_WEB_DOMAINS))
    _write_lines_utf8(USER_TELEGRAM_IP_FILE, list(TELEGRAM_IP_RANGES))


def _clear_telegram_managed_lists() -> None:
    _write_lines_utf8(USER_TELEGRAM_DOMAIN_FILE, [])
    _write_lines_utf8(USER_TELEGRAM_IP_FILE, [])
    _write_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE, [])
    _write_lines_utf8(RUNTIME_TELEGRAM_IP_FILE, [])


def _sync_telegram_runtime_lists(settings: QSettings | None = None) -> None:
    try:
        if _is_telegram_mode_enabled(settings):
            if not os.path.exists(USER_TELEGRAM_DOMAIN_FILE) or not os.path.exists(USER_TELEGRAM_IP_FILE):
                _write_telegram_managed_lists()
            domains = _read_lines_utf8(USER_TELEGRAM_DOMAIN_FILE)
            ip_ranges = _read_lines_utf8(USER_TELEGRAM_IP_FILE)
        else:
            domains = []
            ip_ranges = []

        _write_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE, domains)
        _write_lines_utf8(RUNTIME_TELEGRAM_IP_FILE, ip_ranges)
    except Exception as e:
        _set_telegram_last_error(str(e), settings)


def _apply_telegram_mode_files(enabled: bool, settings: QSettings | None = None) -> bool:
    if enabled:
        _write_telegram_managed_lists()
    else:
        _clear_telegram_managed_lists()
    _sync_telegram_runtime_lists(settings)
    return _apply_flowseal_telegram_hosts(enabled, settings)

