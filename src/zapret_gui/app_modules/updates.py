# --- Winws lifecycle, core migration, and update workflows ------------------

_PENDING_STRATEGY_RESTORE: dict | None = None

FLOWSEAL_CORE_PRESERVE_PATHS = (
    os.path.join("bin", "game_filter.enabled"),
    os.path.join("bin", "tls_clienthello_sochi_park.bin"),
    "cloudflare_switch.bat",
    os.path.join("fast", "clean_mei.bat"),
    os.path.join("fast", "Uninstall.bat"),
    os.path.join("fast", "update_service.bat"),
    os.path.join("files", "list-youtube.txt"),
    os.path.join("files", "quic_initial_www_google_com.bin"),
    os.path.join("lists", "dns_malw_hosts_seed.txt"),
    os.path.join("lists", "ipset-all-user.txt"),
    os.path.join("lists", "ipset-all.txt.backup"),
    os.path.join("lists", "ipset-cloudflare.txt"),
    os.path.join("lists", "ipset-exclude-user.txt"),
    os.path.join("lists", "list-discord.txt"),
    os.path.join("lists", "list-exclude-user.txt"),
    os.path.join("lists", "list-general-user.txt"),
    os.path.join("lists", "telegram-domains.txt"),
    os.path.join("lists", "telegram-ipset.txt"),
    os.path.join("user", "medvedeff-game-ipset.txt"),
    os.path.join("user", "medvedeff-game-list-all.txt"),
    os.path.join("utils", "check_updates.enabled"),
)


def _read_preserved_core_files(core_dir: str) -> dict[str, bytes]:
    files: dict[str, bytes] = {}
    for relative in FLOWSEAL_CORE_PRESERVE_PATHS:
        path = os.path.join(core_dir, relative)
        try:
            if os.path.isfile(path):
                with open(path, "rb") as stream:
                    files[relative] = stream.read()
        except OSError:
            continue
    return files


def _restore_preserved_core_files(core_dir: str, files: dict[str, bytes]) -> int:
    restored = 0
    for relative, data in (files or {}).items():
        if relative not in FLOWSEAL_CORE_PRESERVE_PATHS or not isinstance(data, bytes):
            continue
        target = os.path.join(core_dir, relative)
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as stream:
            stream.write(data)
        restored += 1
    return restored


def _is_core_strategy_bat_name(name: str) -> bool:
    low = os.path.basename(name or "").lower()
    if not low.endswith(".bat"):
        return False
    if low.startswith("__noupdate__"):
        return False
    return low not in CORE_STRATEGY_RESERVED_BAT_NAMES


def _strategy_bat_names_from_dir(core_dir: str) -> set[str]:
    names: set[str] = set()
    try:
        for name in os.listdir(core_dir):
            if _is_core_strategy_bat_name(name):
                names.add(name.lower())
    except Exception:
        pass
    return names


def _read_core_strategy_files(core_dir: str) -> dict[str, dict]:
    files: dict[str, dict] = {}
    try:
        for name in os.listdir(core_dir):
            if not _is_core_strategy_bat_name(name):
                continue
            path = os.path.join(core_dir, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "rb") as f:
                    files[name.lower()] = {"name": name, "data": f.read()}
            except Exception:
                pass
    except Exception:
        pass
    return files


def _safe_strategy_backup_folder(reason: str) -> str:
    safe_reason = re.sub(r"[^A-Za-z0-9_.-]+", "_", reason or "update").strip("_") or "update"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(USER_STRATEGY_BACKUP_DIR, f"{safe_reason}-{stamp}")
    path = base
    n = 2
    while os.path.exists(path):
        path = f"{base}-{n}"
        n += 1
    return path


def _backup_core_strategy_files(strategy_files: dict[str, dict], reason: str) -> str:
    if not strategy_files:
        return ""

    backup_dir = _safe_strategy_backup_folder(reason)
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for item in strategy_files.values():
            name = os.path.basename(str(item.get("name") or ""))
            data = item.get("data")
            if not name or not isinstance(data, (bytes, bytearray)):
                continue
            with open(os.path.join(backup_dir, name), "wb") as f:
                f.write(bytes(data))
        return backup_dir
    except Exception:
        return ""


def _unique_strategy_restore_path(core_dir: str, name: str) -> str:
    stem, ext = os.path.splitext(os.path.basename(name))
    ext = ext or ".bat"
    candidate = os.path.join(core_dir, stem + ext)
    if not os.path.exists(candidate):
        return candidate

    n = 2
    while True:
        candidate = os.path.join(core_dir, f"{stem} (user {n}){ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _restore_custom_strategy_files(
    core_dir: str,
    strategy_files: dict[str, dict],
    replacement_strategy_names: set[str],
) -> int:
    if not strategy_files:
        return 0

    os.makedirs(core_dir, exist_ok=True)
    restored = 0
    replacement_strategy_names = {str(x).lower() for x in (replacement_strategy_names or set())}

    for low, item in strategy_files.items():
        if low in replacement_strategy_names:
            continue
        name = os.path.basename(str(item.get("name") or ""))
        data = item.get("data")
        if not name or not isinstance(data, (bytes, bytearray)):
            continue
        try:
            dst = _unique_strategy_restore_path(core_dir, name)
            with open(dst, "wb") as f:
                f.write(bytes(data))
            restored += 1
        except Exception:
            pass

    return restored


def wipe_app_dir_if_new_version():
    if not hasattr(sys, "_MEIPASS"):
        return

    prev = (_read_text(VERSION_FILE) if os.path.exists(VERSION_FILE) else "").strip()
    if prev == APP_VERSION:
        # Временная папка PyInstaller может иметь отдельный ACL. При прежней
        # миграции он попадал в core/flags и запуск падал ещё до интерфейса.
        # Не пытаемся поверх такой папки что-либо копировать: сначала вернём
        # права, затем обычный запуск продолжится со старым рабочим runtime.
        inaccessible = False
        for folder in MANAGED_RUNTIME_DIRS:
            path = os.path.join(APP_DIR, folder)
            try:
                exists = os.path.lexists(path)
            except OSError:
                inaccessible = True
                break
            if not exists:
                continue
            try:
                with os.scandir(path):
                    pass
            except PermissionError:
                inaccessible = True
                break
            except OSError:
                inaccessible = True
                break
        if inaccessible:
            for folder in MANAGED_RUNTIME_DIRS:
                path = os.path.join(APP_DIR, folder)
                try:
                    exists = os.path.lexists(path)
                except OSError:
                    continue
                if exists and not _make_runtime_tree_accessible(path):
                    raise RuntimeMigrationError(f"Could not repair access to runtime directory: {path}")
            return

    runtime_needs_repair = False
    try:
        for folder in MANAGED_RUNTIME_DIRS:
            path = os.path.join(APP_DIR, folder)
            if not os.path.lexists(path) or not os.path.isdir(path):
                runtime_needs_repair = True
                break
        if not runtime_needs_repair:
            for relative in MANAGED_RUNTIME_CRITICAL_FILES:
                path = os.path.join(APP_DIR, relative)
                if not os.path.isfile(path) or os.path.getsize(path) <= 0:
                    runtime_needs_repair = True
                    break
    except PermissionError:
        runtime_needs_repair = False
    except OSError:
        runtime_needs_repair = False

    if prev == APP_VERSION and not runtime_needs_repair:
        return

    _force_stop_blockers(os.path.join(APP_DIR, "core"))
    _migrate_bundled_runtime(sys._MEIPASS, prev)


def restore_pending_user_strategies_after_extract() -> None:
    global _PENDING_STRATEGY_RESTORE

    pending = _PENDING_STRATEGY_RESTORE
    _PENDING_STRATEGY_RESTORE = None
    if not pending:
        return

    try:
        restored = _restore_custom_strategy_files(
            os.path.join(APP_DIR, "core"),
            pending.get("files") or {},
            pending.get("replacement_names") or set(),
        )
        if restored:
            print(f"Restored custom strategy bat files: {restored}")
    except Exception as e:
        print("Strategy restore error:", e)


def update_domain_files():
    try:
        import psutil

        def is_winws_running() -> bool:
            try:
                out = subprocess.check_output(
                    'tasklist /FI "IMAGENAME eq winws.exe" /NH',
                    shell=True,
                    text=True
                )
                return "winws.exe" in out.lower()
            except Exception:
                return False

        if is_winws_running():
            QMessageBox.warning(
                None,
                "Обновление",
                "Сейчас запущен обход (winws.exe).\n\n"
                "Перед обновлением нажмите красную кнопку (выключить обход), "
                "закройте/остановите winws.exe и повторите."
            )
            return

        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)

        def _detect_local_core_version() -> str:
            try:
                svc = os.path.join(APP_DIR, "core", "service.bat")
                if not os.path.exists(svc):
                    return ""
                raw = _read_text(svc)
                m = re.search(r'(?im)^\s*set\s+"LOCAL_VERSION\s*=\s*([^"]+)"\s*$', raw)
                return (m.group(1).strip() if m else "")
            except Exception:
                return ""

        current_ver = _detect_local_core_version().strip()
        if not current_ver:
            current_ver = str(settings.value(FLOWSEAL_VER_KEY, "")).strip()
        if not current_ver:
            current_ver = FLOWSEAL_DEFAULT_VER
        settings.setValue(FLOWSEAL_VER_KEY, current_ver)
        settings.sync()

        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}

        _repair_dns_malw_hosts_for_app_network(settings)
        data = _fetch_latest_flowseal_release_payload(headers, timeout=20)

        tag = (data.get("tag_name") or "").strip()
        latest_ver = tag[1:] if tag.startswith("v") else tag
        if not latest_ver:
            QMessageBox.warning(None, "Обновление", "Не удалось определить версию последнего релиза.")
            return

        try:
            is_newer = _version_key(latest_ver) > _version_key(current_ver)
        except Exception:
            is_newer = (latest_ver != current_ver)

        if not is_newer:
            lists_result = _sync_flowseal_lists(settings)
            _sync_ai_dns_if_enabled(settings)
            if lists_result.get("offline"):
                QMessageBox.warning(
                    None,
                    "Обновление",
                    f"У вас уже актуальная версия: {current_ver}\nНе удалось проверить списки, проверьте интернет-соединение."
                )
            else:
                QMessageBox.information(
                    None,
                    "Обновление",
                    f"У вас уже актуальная версия: {current_ver}\n{_format_lists_status_text(lists_result, 'ru')}"
                )
            return

        msg = QMessageBox()
        msg.setWindowTitle("Обновление")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(
            f"Доступен новый релиз: {latest_ver}\n"
            f"Текущая версия: {current_ver}\n\n"
            "Будет обновлена папка core, при этом пользовательская папка user сохранится.\n"
            "Продолжить?"
        )
        btn_yes = msg.addButton("Да", QMessageBox.ButtonRole.YesRole)
        btn_no = msg.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        msg.exec()
        if msg.clickedButton() != btn_yes:
            return

        download_url = None
        assets = data.get("assets") or []
        for a in assets:
            name = (a.get("name") or "").lower()
            if name.endswith(".zip"):
                download_url = a.get("browser_download_url")
                break
        if not download_url:
            download_url = data.get("zipball_url")

        if not download_url:
            QMessageBox.warning(None, "Обновление", "Не найден файл для скачивания в релизе.")
            return

        zr = requests.get(download_url, headers=headers, timeout=60)
        zr.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(zr.content))

        core_target = os.path.join(APP_DIR, "core")
        os.makedirs(core_target, exist_ok=True)
        os.makedirs(USER_DIR, exist_ok=True)
        replaced = _replace_core_from_archive(z, core_target)

        settings.setValue(FLOWSEAL_VER_KEY, latest_ver)
        settings.sync()

        _apply_game_mode_state_to_core(settings)
        lists_result = _sync_flowseal_lists(settings)
        _sync_ai_dns_if_enabled(settings)
        list_status = _format_lists_status_text(lists_result, "ru")
        if lists_result.get("offline"):
            list_status = "Обновлено, но список не удалось проверить/обновить: проверьте интернет-соединение."
        elif lists_result.get("error"):
            list_status = "Обновлено, но произошла ошибка при проверке списков."

        QMessageBox.information(
            None,
            "Обновление завершено",
            f"Обновлено до: {latest_ver}\n"
            f"Файлов распаковано: {replaced}\n\n"
            f"{list_status}\n"
            f"Путь: {core_target}"
        )

    except requests.exceptions.ConnectionError:
        QMessageBox.warning(None, "Ошибка обновления", "Отсутствует подключение к интернету.")
    except requests.HTTPError as e:
        QMessageBox.critical(None, "Ошибка обновления", f"HTTP ошибка:\n{e}")
    except PermissionError as e:
        QMessageBox.critical(
            None,
            "Ошибка обновления",
            "Не удалось очистить/записать файлы в папку core.\n"
            "НАЖМИТЕ НА КНОПКУ Сбросить соединения winws.\n\n"
            f"Детали: {e}"
        )
    except zipfile.BadZipFile:
        QMessageBox.critical(None, "Ошибка обновления", "Скачанный архив повреждён или не является zip.")
    except Exception as e:
        QMessageBox.critical(None, "Ошибка обновления", f"Произошла ошибка:\n{e}")


def _detect_runtime_core_version(settings: QSettings | None = None) -> str:
    qs = _load_settings_if_needed(settings)

    current_ver = ""
    try:
        svc = os.path.join(APP_DIR, "core", "service.bat")
        if os.path.exists(svc):
            raw = _read_text(svc)
            m = re.search(r'(?im)^\s*set\s+"LOCAL_VERSION\s*=\s*([^"]+)"\s*$', raw)
            current_ver = (m.group(1).strip() if m else "")
    except Exception:
        current_ver = ""

    if not current_ver:
        try:
            current_ver = str(qs.value(FLOWSEAL_VER_KEY, "") or "").strip()
        except Exception:
            current_ver = ""

    if not current_ver:
        current_ver = FLOWSEAL_DEFAULT_VER

    try:
        qs.setValue(FLOWSEAL_VER_KEY, current_ver)
        qs.sync()
    except Exception:
        pass

    return current_ver


def _find_flowseal_download_url(release_payload: dict) -> str:
    assets = release_payload.get("assets") or []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = (asset.get("name") or "").lower()
        if name.endswith(".zip"):
            return str(asset.get("browser_download_url") or "").strip()
    return str(release_payload.get("zipball_url") or "").strip()


def _flowseal_archive_url(version: str) -> str:
    tag = (version or "").strip()
    if not tag:
        return ""
    return f"https://github.com/{FLOWSEAL_REPO}/archive/refs/tags/{tag}.zip"


def _fetch_latest_flowseal_release_payload(headers: dict, timeout: float = 20) -> dict:
    api_url = f"https://api.github.com/repos/{FLOWSEAL_REPO}/releases/latest"
    try:
        response = requests.get(api_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    except requests.exceptions.RequestException:
        pass

    version_response = requests.get(
        FLOWSEAL_VERSION_URL,
        headers={"User-Agent": headers.get("User-Agent", "ZapretGUI-Updater"), "Cache-Control": "no-cache"},
        timeout=min(float(timeout or 20), 12),
    )
    version_response.raise_for_status()
    latest_ver = (version_response.text or "").strip()
    if not latest_ver:
        raise RuntimeError("latest-version-missing")
    return {
        "tag_name": latest_ver,
        "assets": [],
        "zipball_url": _flowseal_archive_url(latest_ver),
        "zapretgui_fallback": "raw-version",
    }


def _fetch_latest_gui_release_payload(headers: dict, timeout: float = 20) -> dict:
    api_url = f"https://api.github.com/repos/{GUI_REPO}/releases/latest"
    response = requests.get(api_url, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("latest-gui-release-missing")
    return payload


def _find_gui_download_url(release_payload: dict) -> str:
    assets = release_payload.get("assets") or []
    preferred = []
    fallback = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        lower = name.lower()
        url = str(asset.get("browser_download_url") or "").strip()
        if not url or not lower.endswith(".zip"):
            continue
        if "zapret" in lower and "gui" in lower:
            preferred.append(url)
        else:
            fallback.append(url)
    if preferred:
        return preferred[0]
    if fallback:
        return fallback[0]
    return ""


def _find_gui_update_metadata(release_payload: dict) -> dict:
    """Return the selected GUI asset and an optional release SHA-256."""
    assets = release_payload.get("assets") or []
    candidates = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        lower = name.lower()
        url = str(asset.get("browser_download_url") or "").strip()
        if url and lower.endswith(".zip"):
            priority = 0 if ("zapret" in lower and "gui" in lower) else 1
            candidates.append((priority, asset))
    if not candidates:
        return {"download_url": "", "sha256": "", "checksum_url": ""}

    candidates.sort(key=lambda item: item[0])
    asset = candidates[0][1]
    digest = str(asset.get("digest") or "").strip().lower()
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1].strip()
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        digest = ""

    selected_name = str(asset.get("name") or "").lower()
    checksum_url = ""
    checksum_names = {
        selected_name + ".sha256",
        selected_name + ".sha256.txt",
        os.path.splitext(selected_name)[0] + ".sha256",
        os.path.splitext(selected_name)[0] + ".sha256.txt",
    }
    for candidate in assets:
        if not isinstance(candidate, dict):
            continue
        name = str(candidate.get("name") or "").lower()
        url = str(candidate.get("browser_download_url") or "").strip()
        if url and name in checksum_names:
            checksum_url = url
            break

    return {
        "download_url": str(asset.get("browser_download_url") or "").strip(),
        "sha256": digest,
        "checksum_url": checksum_url,
    }


def _normalize_release_version(tag: str) -> str:
    version = (tag or "").strip()
    if version.startswith(("v", "V")):
        version = version[1:].strip()
    return version


def _check_gui_update_available(
    settings: QSettings | None = None,
    respect_skipped: bool = False,
    timeout: float = 20,
) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "current_ver": APP_VERSION,
        "latest_ver": "",
        "download_url": "",
        "release_url": GUI_RELEASES_URL,
        "skipped": False,
    }

    try:
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        _repair_dns_malw_hosts_for_app_network(qs)
        payload = _fetch_latest_gui_release_payload(headers, timeout=timeout)

        latest_ver = _normalize_release_version(str(payload.get("tag_name") or ""))
        if not latest_ver:
            result["status"] = "error"
            result["error"] = "latest-gui-version-missing"
            return result

        result["latest_ver"] = latest_ver

        try:
            is_newer = _version_key(latest_ver) > _version_key(APP_VERSION)
        except Exception:
            is_newer = latest_ver != APP_VERSION

        if not is_newer:
            result["ok"] = True
            result["status"] = "up-to-date"
            return result

        skipped_ver = ""
        if respect_skipped:
            try:
                skipped_ver = str(qs.value(GUI_SKIPPED_UPDATE_KEY, "") or "").strip()
            except Exception:
                skipped_ver = ""
            if skipped_ver and skipped_ver == latest_ver:
                result["ok"] = True
                result["status"] = "skipped"
                result["skipped"] = True
                return result

        asset = _find_gui_update_metadata(payload)
        download_url = str(asset.get("download_url") or "")
        if not download_url:
            result["status"] = "error"
            result["error"] = "gui-download-url-missing"
            return result

        result["ok"] = True
        result["status"] = "update-available"
        result["download_url"] = download_url
        result["archive_sha256"] = str(asset.get("sha256") or "")
        result["checksum_url"] = str(asset.get("checksum_url") or "")
        return result

    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


def _check_startup_gui_update_if_due(
    settings: QSettings | None = None,
    timeout: float = 6,
    min_interval_seconds: int = GUI_UPDATE_STARTUP_MIN_INTERVAL_SECONDS,
) -> dict:
    qs = _load_settings_if_needed(settings)
    now = int(time.time())
    last_check = _safe_int_setting(qs, GUI_UPDATE_STARTUP_LAST_CHECK_KEY, 0)
    if last_check > 0 and (now - last_check) < max(60, int(min_interval_seconds or 0)):
        return {
            "ok": True,
            "status": "skipped-recent",
            "offline": False,
            "skipped": True,
            "current_ver": APP_VERSION,
            "latest_ver": APP_VERSION,
            "download_url": "",
            "release_url": GUI_RELEASES_URL,
            "error": "",
        }

    try:
        qs.setValue(GUI_UPDATE_STARTUP_LAST_CHECK_KEY, now)
        qs.sync()
    except Exception:
        pass
    return _check_gui_update_available(qs, respect_skipped=True, timeout=timeout)


def _check_tg_ws_proxy_update_available(timeout: float = 12) -> dict:
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "current_ver": TG_WS_PROXY_VENDOR_VERSION,
        "latest_ver": "",
        "release_url": TG_WS_PROXY_RELEASES_URL,
        "manual": True,
    }
    try:
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        api_url = f"https://api.github.com/repos/{TG_WS_PROXY_REPO}/releases/latest"
        response = requests.get(api_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("latest-tg-ws-proxy-release-missing")
        latest_ver = _normalize_release_version(str(payload.get("tag_name") or ""))
        if not latest_ver:
            raise RuntimeError("latest-tg-ws-proxy-version-missing")
        result["latest_ver"] = latest_ver
        try:
            is_newer = _version_key(latest_ver) > _version_key(TG_WS_PROXY_VENDOR_VERSION)
        except Exception:
            is_newer = latest_ver != TG_WS_PROXY_VENDOR_VERSION
        result["ok"] = True
        result["status"] = "update-available" if is_newer else "up-to-date"
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


def _check_all_updates_async(
    settings: QSettings | None = None,
    should_cancel=None,
    phase_callback=None,
) -> dict:
    def _phase(name: str) -> None:
        try:
            if phase_callback:
                phase_callback(name)
        except Exception:
            pass

    qs = _load_settings_if_needed(settings)
    _phase("gui-version")
    gui_result = _check_gui_update_available(qs, respect_skipped=False, timeout=20)
    if gui_result.get("ok") and gui_result.get("status") == "update-available":
        return {
            "ok": True,
            "status": "gui-update-available",
            "current_ver": str(gui_result.get("current_ver") or APP_VERSION),
            "latest_ver": str(gui_result.get("latest_ver") or ""),
            "download_url": str(gui_result.get("download_url") or ""),
            "archive_sha256": str(gui_result.get("archive_sha256") or ""),
            "checksum_url": str(gui_result.get("checksum_url") or ""),
            "release_url": str(gui_result.get("release_url") or GUI_RELEASES_URL),
            "gui_result": gui_result,
        }

    core_result = _check_flowseal_update_with_winws_recovery(
        qs,
        should_cancel=should_cancel,
        phase_callback=phase_callback,
    )
    core_result["gui_checked"] = bool(gui_result.get("ok"))
    core_result["gui_current_ver"] = APP_VERSION
    core_result["gui_latest_ver"] = str(gui_result.get("latest_ver") or APP_VERSION)
    core_result["gui_error"] = str(gui_result.get("error") or "")
    core_result["gui_offline"] = bool(gui_result.get("offline"))
    return core_result


def _current_gui_executable_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.realpath(sys.executable)
    return os.path.realpath(sys.argv[0])


def _verify_gui_install_location_writable(current_exe: str) -> None:
    install_dir = os.path.dirname(os.path.abspath(current_exe))
    if not os.path.isdir(install_dir):
        raise PermissionError(f"GUI install directory does not exist: {install_dir}")
    probe_path = ""
    try:
        fd, probe_path = tempfile.mkstemp(prefix=".zapretgui-update-write-", dir=install_dir)
        os.close(fd)
        os.remove(probe_path)
        probe_path = ""
    except OSError as error:
        raise PermissionError(
            "Zapret GUI is installed in a protected directory. "
            "Move it to a user-writable folder before using automatic updates."
        ) from error
    finally:
        if probe_path:
            try:
                os.remove(probe_path)
            except OSError:
                pass


def _download_gui_update_archive(
    download_url: str,
    latest_ver: str,
    expected_sha256: str = "",
    checksum_url: str = "",
    progress_callback=None,
) -> str:
    update_dir = os.path.join(APP_DIR, "updates")
    os.makedirs(update_dir, exist_ok=True)

    safe_ver = re.sub(r"[^A-Za-z0-9_.-]+", "_", latest_ver or "latest")
    fd, part_path = tempfile.mkstemp(prefix=f"ZapretGUI-{safe_ver}-", suffix=".zip.part", dir=update_dir)
    os.close(fd)
    final_path = part_path[:-5]

    headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/octet-stream"}
    try:
        with requests.get(download_url, headers=headers, timeout=90, stream=True) as response:
            response.raise_for_status()
            total = int(response.headers.get("Content-Length") or 0)
            downloaded = 0
            with open(part_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_callback:
                            progress_callback(downloaded, total)
        if os.path.getsize(part_path) < 1024:
            raise RuntimeError("downloaded-gui-archive-too-small")
        if os.path.exists(final_path):
            os.remove(final_path)
        os.replace(part_path, final_path)

        expected = str(expected_sha256 or "").strip().lower()
        if not re.fullmatch(r"[0-9a-f]{64}", expected) and checksum_url:
            checksum_response = requests.get(
                checksum_url,
                headers={"User-Agent": "ZapretGUI-Updater", "Accept": "text/plain"},
                timeout=20,
            )
            checksum_response.raise_for_status()
            match = re.search(r"\b([0-9a-fA-F]{64})\b", checksum_response.text or "")
            expected = match.group(1).lower() if match else ""
        if not re.fullmatch(r"[0-9a-f]{64}", expected):
            raise RuntimeError("gui-update-has-no-trusted-sha256")
        actual = _sha256_file_strict(final_path)
        if actual != expected:
            raise RuntimeError("downloaded-gui-archive-sha256-mismatch")
        return final_path
    except Exception:
        try:
            if os.path.exists(part_path):
                os.remove(part_path)
        except Exception:
            pass
        raise


def _write_gui_update_script() -> str:
    script_dir = os.path.join(APP_DIR, "updates")
    os.makedirs(script_dir, exist_ok=True)
    script_path = os.path.join(script_dir, "apply_gui_update.ps1")
    script = r'''
param(
    [Parameter(Mandatory=$true)][string]$ArchivePath,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [Parameter(Mandatory=$true)][string]$OldExePath,
    [Parameter(Mandatory=$true)][string]$AppDir,
    [Parameter(Mandatory=$true)][int]$CurrentPid,
    [string]$NewVersion = "",
    [string]$ExpectedSha256 = "",
    [string]$ChecksumUrl = ""
)

$ErrorActionPreference = "Stop"
$LogPath = Join-Path $InstallDir "ZapretGUI-update.log"

function Write-UpdateLog([string]$Message) {
    try {
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -LiteralPath $LogPath -Value "[$stamp] $Message" -Encoding UTF8
    } catch {}
}

function Quote-WindowsArgument([string]$Value) {
    return '"' + [regex]::Replace(
        [regex]::Replace($Value, '(\\*)"', '$1$1\"'), '(\\+)$', '$1$1'
    ) + '"'
}

function Update-ZapretShortcuts([string]$OldExe, [string]$NewExe, [string]$WorkDir) {
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcutRoots = @(
            [Environment]::GetFolderPath("Desktop"),
            [Environment]::GetFolderPath("CommonDesktopDirectory"),
            [Environment]::GetFolderPath("Programs"),
            [Environment]::GetFolderPath("Startup")
        ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique

        foreach ($root in $shortcutRoots) {
            Get-ChildItem -LiteralPath $root -Filter "*.lnk" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
                try {
                    $lnk = $shell.CreateShortcut($_.FullName)
                    $target = [string]$lnk.TargetPath
                    $name = [string]$_.Name
                    $targetName = [IO.Path]::GetFileName($target)
                    $shouldUpdate = $false
                    if ($target -and ([string]::Compare($target, $OldExe, $true) -eq 0)) { $shouldUpdate = $true }
                    if ($name -match "Zapret.?GUI|Zapret GUI") { $shouldUpdate = $true }
                    if ($targetName -match "Zapret.?GUI|Zapret GUI") { $shouldUpdate = $true }
                    if ($shouldUpdate) {
                        $lnk.TargetPath = $NewExe
                        $lnk.WorkingDirectory = $WorkDir
                        $lnk.IconLocation = $NewExe
                        $lnk.Save()
                    }
                } catch {}
            }
        }

        $desktop = [Environment]::GetFolderPath("Desktop")
        if ($desktop -and (Test-Path -LiteralPath $desktop)) {
            $mainShortcut = Join-Path $desktop "Zapret GUI.lnk"
            $lnk = $shell.CreateShortcut($mainShortcut)
            $lnk.TargetPath = $NewExe
            $lnk.WorkingDirectory = $WorkDir
            $lnk.IconLocation = $NewExe
            $lnk.Save()
        }
    } catch {
        Write-UpdateLog ("Shortcut update failed: " + $_.Exception.Message)
    }
}

    $tempRoot = ""
    $backupPath = ""
    try {
    Write-UpdateLog "GUI update started"
    $deadline = (Get-Date).AddSeconds(45)
    while ($true) {
        $oldProcess = Get-Process -Id $CurrentPid -ErrorAction SilentlyContinue
        if (!$oldProcess) { break }
        if ((Get-Date) -ge $deadline) { throw "Old GUI process did not exit before timeout" }
        Start-Sleep -Milliseconds 250
    }
    # Re-check after the timeout loop. Replacement is forbidden while the old
    # process still exists, even if it cannot be queried consistently.
    if (Get-Process -Id $CurrentPid -ErrorAction SilentlyContinue) {
        throw "Old GUI process is still running"
    }
    Start-Sleep -Milliseconds 500

    if (!(Test-Path -LiteralPath $ArchivePath)) { throw "Archive not found: $ArchivePath" }
    if (!(Test-Path -LiteralPath $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }
    if (!(Test-Path -LiteralPath $OldExePath)) { throw "Current GUI executable not found: $OldExePath" }

    $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("ZapretGUI-update-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ArchivePath, $tempRoot)

    $exeCandidates = Get-ChildItem -LiteralPath $tempRoot -Recurse -File -Filter "*.exe" | Sort-Object `
        @{ Expression = { if ($_.Name -match "Zapret.?GUI|Zapret GUI") { 0 } else { 1 } } }, FullName
    if (!$exeCandidates -or $exeCandidates.Count -lt 1) { throw "No exe file found in archive" }

    $sourceExe = $exeCandidates[0].FullName
    if ((Get-Item -LiteralPath $sourceExe).Length -lt 1MB) { throw "Updated exe is unexpectedly small" }
    $expected = $ExpectedSha256.Trim().ToLowerInvariant()
    if (!$expected -and $ChecksumUrl) {
        try {
            $checksumText = (Invoke-WebRequest -UseBasicParsing -Uri $ChecksumUrl -TimeoutSec 20).Content
            if ($checksumText -match '(?i)\b([0-9a-f]{64})\b') { $expected = $Matches[1].ToLowerInvariant() }
        } catch { throw "Could not verify GUI update checksum" }
    }
    if (!$expected -or $expected -notmatch '^[0-9a-f]{64}$') { throw "GUI update has no trusted SHA-256" }
    $actual = (Get-FileHash -LiteralPath $ArchivePath -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actual -ne $expected) { throw "GUI archive SHA-256 mismatch" }

    # Portable update: replace only the running executable. Runtime migration
    # is performed transactionally by the new GUI on its first start.
    $backupPath = $OldExePath + ".update-backup-" + [Guid]::NewGuid().ToString("N")
    Move-Item -LiteralPath $OldExePath -Destination $backupPath -Force
    try {
        Copy-Item -LiteralPath $sourceExe -Destination $OldExePath -Force
        if (!(Test-Path -LiteralPath $OldExePath)) { throw "Updated exe was not installed" }
    } catch {
        if (Test-Path -LiteralPath $OldExePath) { Remove-Item -LiteralPath $OldExePath -Force }
        if (Test-Path -LiteralPath $backupPath) { Move-Item -LiteralPath $backupPath -Destination $OldExePath -Force }
        $backupPath = ""
        throw
    }

    Update-ZapretShortcuts -OldExe $OldExePath -NewExe $OldExePath -WorkDir $InstallDir

    try {
        $runKey = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run'
        if (Get-ItemProperty -LiteralPath $runKey -Name 'ZapretGUI' -ErrorAction SilentlyContinue) {
            Set-ItemProperty -LiteralPath $runKey -Name 'ZapretGUI' -Value (
                (Quote-WindowsArgument $OldExePath) + ' ' +
                (Quote-WindowsArgument "--app-dir=$AppDir") + ' --autostart'
            )
        }
    } catch {
        Write-UpdateLog ("Autostart update failed: " + $_.Exception.Message)
    }

    try { Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue } catch {}
    try { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue } catch {}

    Write-UpdateLog "Starting updated GUI: $OldExePath --post-update"
    $launchArgs = (Quote-WindowsArgument "--app-dir=$AppDir") + " --post-update"
    $newProcess = Start-Process -FilePath $OldExePath -ArgumentList $launchArgs -WorkingDirectory $InstallDir -PassThru
    $markerPath = Join-Path $AppDir ".app_version"
    $readyDeadline = (Get-Date).AddSeconds(45)
    while ((Get-Date) -lt $readyDeadline) {
        if ($newProcess.HasExited) {
            $markerValue = ""
            try { $markerValue = (Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop).Trim() } catch {}
            if ($markerValue -ne $NewVersion) { throw "Updated GUI exited before runtime migration completed" }
            break
        }
        $markerValue = ""
        try { $markerValue = (Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop).Trim() } catch {}
        if ($markerValue -eq $NewVersion) { break }
        Start-Sleep -Milliseconds 250
    }
    $finalMarker = ""
    try { $finalMarker = (Get-Content -LiteralPath $markerPath -Raw -ErrorAction Stop).Trim() } catch {}
    if ($finalMarker -eq $NewVersion -and $backupPath) {
        try { Remove-Item -LiteralPath $backupPath -Force -ErrorAction SilentlyContinue } catch {}
        $backupPath = ""
    } else {
        Write-UpdateLog "Runtime migration confirmation was not received; keeping executable backup"
    }
} catch {
    if ($backupPath -and (Test-Path -LiteralPath $backupPath)) {
        try {
            if (Test-Path -LiteralPath $OldExePath) { Remove-Item -LiteralPath $OldExePath -Force }
            Move-Item -LiteralPath $backupPath -Destination $OldExePath -Force
            Start-Process -FilePath $OldExePath -ArgumentList (Quote-WindowsArgument "--app-dir=$AppDir") -WorkingDirectory $InstallDir
        } catch {
            Write-UpdateLog ("Rollback failed: " + $_.Exception.Message)
        }
    }
    Write-UpdateLog ("GUI update failed: " + $_.Exception.Message)
    try {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "Zapret GUI update failed. Details are in:`n$LogPath",
            "Zapret GUI updater"
        ) | Out-Null
    } catch {}
} finally {
    if ($tempRoot -and (Test-Path -LiteralPath $tempRoot)) {
        try { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue } catch {}
    }
}
'''
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script.lstrip())
    return script_path


def _schedule_gui_update_restart(
    latest_ver: str,
    download_url: str,
    expected_sha256: str = "",
    checksum_url: str = "",
    progress_callback=None,
) -> dict:
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "latest_ver": latest_ver,
        "download_url": download_url,
    }

    try:
        current_exe = _current_gui_executable_path()
        if not current_exe.lower().endswith(".exe"):
            result["status"] = "unsupported"
            result["error"] = "gui-self-update-requires-exe"
            return result

        _verify_gui_install_location_writable(current_exe)
        archive_path = _download_gui_update_archive(
            download_url,
            latest_ver,
            expected_sha256=expected_sha256,
            checksum_url=checksum_url,
            progress_callback=progress_callback,
        )
        with zipfile.ZipFile(archive_path, "r") as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise zipfile.BadZipFile(f"bad member: {bad_member}")
        script_path = _write_gui_update_script()
        install_dir = os.path.dirname(current_exe)
        verified_sha256 = _sha256_file_strict(archive_path)

        args = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", script_path,
            "-ArchivePath", archive_path,
            "-InstallDir", install_dir,
            "-OldExePath", current_exe,
            "-AppDir", APP_DIR,
            "-CurrentPid", str(os.getpid()),
            "-NewVersion", latest_ver,
            "-ExpectedSha256", verified_sha256,
            "-ChecksumUrl", str(checksum_url or ""),
        ]
        result["updater_args"] = args
        # The caller launches this only after the bypass, workers and service
        # pipe have been shut down. Preparing the updater must not race GUI
        # shutdown or start replacement too early.
        result["archive_sha256"] = verified_sha256
        result["checksum_url"] = str(checksum_url or "")
        result["ok"] = True
        result["status"] = "gui-update-ready"
        result["archive_path"] = archive_path
        result["script_path"] = script_path
        result["install_dir"] = install_dir
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except zipfile.BadZipFile:
        result["status"] = "bad-zip"
        result["error"] = "bad-zip"
    except PermissionError as e:
        result["status"] = "permission"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


def _launch_gui_updater_process(updater_args: list[str], install_dir: str) -> None:
    if not updater_args:
        raise RuntimeError("GUI updater command is missing")
    subprocess.Popen(
        updater_args,
        cwd=install_dir,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        close_fds=True,
    )


def _prepare_gui_update_shutdown(parent, result: dict) -> None:
    if parent is None or not hasattr(parent, "_begin_gui_update_install"):
        raise RuntimeError("Main window cannot prepare GUI update shutdown")
    parent._begin_gui_update_install(
        list(result.get("updater_args") or []),
        str(result.get("install_dir") or ""),
    )


def _prepare_post_update_runtime() -> None:
    """Finish runtime/service validation before showing the post-update GUI."""
    if not _was_started_after_update():
        return
    _ensure_background_service(os.path.join(APP_DIR, "core"))


def _replace_core_from_archive(archive: zipfile.ZipFile, core_target: str) -> int:
    driver_names = {"windivert64.sys", "windivert32.sys"}
    driver_backups: dict[str, bytes] = {}

    names = [name for name in archive.namelist() if name and not name.startswith("__MACOSX/")]
    top_levels = set()
    for name in names:
        segment = name.split("/", 1)[0]
        if segment:
            top_levels.add(segment)

    root_prefix = ""
    if len(top_levels) == 1:
        root_prefix = next(iter(top_levels)) + "/"

    current_strategy_files = _read_core_strategy_files(core_target)
    preserved_core_files = _read_preserved_core_files(core_target)
    _backup_core_strategy_files(current_strategy_files, "core-update")
    replacement_strategy_names: set[str] = set()
    for member in names:
        if member.endswith("/"):
            continue
        if root_prefix and not member.startswith(root_prefix):
            continue
        rel = member[len(root_prefix):] if root_prefix else member
        if not rel or "/" in rel or "\\" in rel:
            continue
        if _is_core_strategy_bat_name(rel):
            replacement_strategy_names.add(os.path.basename(rel).lower())

    bin_dir = os.path.join(core_target, "bin")
    for driver in driver_names:
        path = os.path.join(bin_dir, driver)
        try:
            with open(path, "rb") as f:
                driver_backups[driver] = f.read()
        except Exception:
            pass

    parent_dir = os.path.dirname(os.path.abspath(core_target))
    os.makedirs(parent_dir, exist_ok=True)
    stage_target = tempfile.mkdtemp(prefix=".flowseal-update-temp-", dir=parent_dir)
    backup_target = tempfile.mkdtemp(prefix=".flowseal-update-backup-", dir=parent_dir)
    backup_core = os.path.join(backup_target, "core")
    replaced = 0
    extracted_drivers: set[str] = set()
    core_root = os.path.abspath(stage_target)
    core_prefix = core_root + os.sep
    committed = False
    moved_original = False
    try:
        for member in names:
            if member.endswith("/"):
                continue
            if root_prefix and not member.startswith(root_prefix):
                continue

            rel = member[len(root_prefix):] if root_prefix else member
            if not rel:
                continue

            dst_path = os.path.abspath(os.path.join(stage_target, rel))
            if dst_path != core_root and not dst_path.startswith(core_prefix):
                continue

            os.makedirs(os.path.dirname(dst_path), exist_ok=True)
            with archive.open(member) as src, open(dst_path, "wb") as dst:
                shutil.copyfileobj(src, dst)

            if os.path.basename(dst_path).lower() in driver_names:
                extracted_drivers.add(os.path.basename(dst_path).lower())
            replaced += 1

        stage_bin_dir = os.path.join(stage_target, "bin")
        for driver, data in driver_backups.items():
            if driver in extracted_drivers:
                continue
            path = os.path.join(stage_bin_dir, driver)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            replaced += 1

        replaced += _restore_custom_strategy_files(
            stage_target,
            current_strategy_files,
            replacement_strategy_names,
        )
        replaced += _restore_preserved_core_files(stage_target, preserved_core_files)

        for relative in ("service.bat", os.path.join("bin", "winws.exe")):
            path = os.path.join(stage_target, relative)
            if not os.path.isfile(path) or os.path.getsize(path) <= 0:
                raise RuntimeError(f"flowseal-archive-missing:{relative}")

        if os.path.lexists(core_target):
            os.rename(core_target, backup_core)
            moved_original = True
        try:
            os.rename(stage_target, core_target)
        except Exception:
            if moved_original and os.path.lexists(backup_core) and not os.path.lexists(core_target):
                os.rename(backup_core, core_target)
                moved_original = False
            raise
        committed = True
        return replaced
    except Exception:
        if committed and os.path.lexists(core_target):
            _remove_path_strict(core_target)
        if moved_original and os.path.lexists(backup_core) and not os.path.lexists(core_target):
            os.rename(backup_core, core_target)
        raise
    finally:
        if os.path.lexists(stage_target):
            shutil.rmtree(stage_target, ignore_errors=True)
        # Never delete the only remaining copy of the old core if rollback
        # itself was blocked. A later/manual recovery can still restore it.
        if committed or not os.path.lexists(backup_core):
            shutil.rmtree(backup_target, ignore_errors=True)


def _check_flowseal_update_async(
    settings: QSettings | None = None,
    should_cancel=None,
    phase_callback=None,
) -> dict:
    def _cancelled() -> bool:
        try:
            return bool(should_cancel and should_cancel())
        except Exception:
            return False

    def _phase(name: str) -> None:
        try:
            if phase_callback:
                phase_callback(name)
        except Exception:
            pass

    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "current_ver": "",
        "latest_ver": "",
        "download_url": "",
        "lists_result": {},
        "ai_dns_error": "",
    }

    _phase("version")

    if _is_winws_running_silent():
        result["status"] = "winws-running"
        result["error"] = "winws-running"
        return result

    try:
        if _cancelled():
            result["status"] = "cancelled"
            result["error"] = "cancelled"
            return result

        current_ver = _detect_runtime_core_version(qs)
        result["current_ver"] = current_ver

        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        _repair_dns_malw_hosts_for_app_network(qs)
        payload = _fetch_latest_flowseal_release_payload(headers, timeout=20)

        if _cancelled():
            result["status"] = "cancelled"
            result["error"] = "cancelled"
            return result

        tag = (payload.get("tag_name") or "").strip()
        latest_ver = tag[1:] if tag.startswith("v") else tag
        latest_ver = (latest_ver or "").strip()
        if not latest_ver:
            result["status"] = "error"
            result["error"] = "latest-version-missing"
            return result

        result["latest_ver"] = latest_ver

        try:
            is_newer = _version_key(latest_ver) > _version_key(current_ver)
        except Exception:
            is_newer = latest_ver != current_ver

        if is_newer:
            download_url = _find_flowseal_download_url(payload)
            if not download_url:
                result["status"] = "error"
                result["error"] = "download-url-missing"
                return result

            result["ok"] = True
            result["status"] = "update-available"
            result["download_url"] = download_url
            return result

        if _cancelled():
            result["status"] = "cancelled"
            result["error"] = "cancelled"
            return result

        _phase("lists")
        lists_result = _sync_flowseal_lists(qs)
        ai_result = _sync_ai_dns_if_enabled(qs)
        result["ok"] = True
        result["status"] = "up-to-date"
        result["lists_result"] = lists_result
        result["ai_dns_error"] = str(ai_result.get("error") or "")
        return result

    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


def _apply_flowseal_update_async(latest_ver: str, download_url: str, settings: QSettings | None = None) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "latest_ver": latest_ver,
        "replaced": 0,
        "core_target": os.path.join(APP_DIR, "core"),
        "lists_result": {},
        "ai_dns_error": "",
    }

    if _is_winws_running_silent():
        result["status"] = "winws-running"
        result["error"] = "winws-running"
        return result

    try:
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        response = requests.get(download_url, headers=headers, timeout=60)
        response.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(response.content))

        core_target = os.path.join(APP_DIR, "core")
        os.makedirs(core_target, exist_ok=True)
        os.makedirs(USER_DIR, exist_ok=True)
        replaced = _replace_core_from_archive(archive, core_target)

        qs.setValue(FLOWSEAL_VER_KEY, latest_ver)
        qs.sync()

        _apply_game_mode_state_to_core(qs)
        lists_result = _sync_flowseal_lists(qs)
        ai_result = _sync_ai_dns_if_enabled(qs)

        result["ok"] = True
        result["status"] = "updated"
        result["replaced"] = replaced
        result["lists_result"] = lists_result
        result["ai_dns_error"] = str(ai_result.get("error") or "")
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except zipfile.BadZipFile:
        result["status"] = "bad-zip"
        result["error"] = "bad-zip"
    except PermissionError as e:
        result["status"] = "permission"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


def _version_key(v: str):
    s = (v or "").strip()
    if s.startswith(("v", "V")):
        s = s[1:].strip()

    m = re.match(r"^\s*(\d+(?:\.\d+){0,3})(.*)\s*$", s)
    if not m:
        return ((0, 0, 0, 0), 0, ("",))

    num_part = m.group(1).strip()
    suffix = (m.group(2) or "").strip()

    nums = []
    for p in num_part.split("."):
        try:
            nums.append(int(p))
        except Exception:
            nums.append(0)
    while len(nums) < 4:
        nums.append(0)
    nums = tuple(nums[:4])

    suffix = re.sub(r"^[\s\-\._]+", "", suffix)

    has_suffix = 1 if suffix else 0

    if not suffix:
        suffix_key = ("",)
    else:
        toks = []
        for t in re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", suffix):
            if t.isdigit():
                toks.append((1, int(t)))
            else:
                toks.append((0, t.casefold()))
        suffix_key = tuple(toks)

    return (nums, has_suffix, suffix_key)

def _get_latest_flowseal_release_silent() -> str:
    try:
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        data = _fetch_latest_flowseal_release_payload(headers, timeout=12)
        tag = (data.get("tag_name") or "").strip()
        latest_ver = tag[1:] if tag.startswith("v") else tag
        return (latest_ver or "").strip()
    except Exception:
        return ""

def _cleanup_noupdate_files(core_dir: str) -> None:
    try:
        if not os.path.isdir(core_dir):
            return
        for fn in os.listdir(core_dir):
            if fn.lower().startswith("__noupdate__") and fn.lower().endswith(".bat"):
                try:
                    os.remove(os.path.join(core_dir, fn))
                except Exception:
                    pass
    except Exception:
        pass

def _patch_profiles_if_core_outdated(core_dir: str, settings: QSettings) -> None:
    try:
        if not os.path.isdir(core_dir):
            return

        latest = _get_latest_flowseal_release_silent()
        if not latest:
            return

        def _detect_local_core_version() -> str:
            try:
                svc = os.path.join(core_dir, "service.bat")
                if not os.path.exists(svc):
                    return ""
                raw = _read_text(svc)
                m = re.search(r'(?im)^\s*set\s+"LOCAL_VERSION\s*=\s*([^"]+)"\s*$', raw)
                return (m.group(1).strip() if m else "")
            except Exception:
                return ""

        current = _detect_local_core_version().strip()
        if not current:
            current = str(settings.value(FLOWSEAL_VER_KEY, FLOWSEAL_DEFAULT_VER)).strip() or FLOWSEAL_DEFAULT_VER

        try:
            outdated = _version_key(latest) > _version_key(current)
        except Exception:
            outdated = (latest != current)

        try:
            settings.setValue(FLOWSEAL_VER_KEY, current)
            settings.sync()
        except Exception:
            pass

        if not outdated:
            _cleanup_noupdate_files(core_dir)
            return

        _cleanup_noupdate_files(core_dir)

        for fn in os.listdir(core_dir):
            if not fn.lower().endswith(".bat"):
                continue
            low = fn.lower()
            if low in ("service.bat", "cloudflare_switch.bat"):
                continue
            _patch_bat_inplace_remove_updates(os.path.join(core_dir, fn))

    except Exception:
        pass

def create_delete_bat():
    delete_bat_path = os.path.join(APP_DIR, "Delete.bat")

    content = r'''@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

net session >nul 2>&1 || (
  powershell -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)

tasklist /FI "IMAGENAME eq winws.exe" | find /I "winws.exe" > nul
if !errorlevel!==0 exit /b

sc stop zapret >nul 2>&1
sc delete zapret >nul 2>&1
sc stop zapret_discord >nul 2>&1
sc delete zapret_discord >nul 2>&1
net stop "WinDivert" >nul 2>&1 & sc delete "WinDivert" >nul 2>&1
net stop "WinDivert14" >nul 2>&1 & sc delete "WinDivert14" >nul 2>&1

if exist "%~dp0background_service\ZapretGUI.Service.exe" (
  "%~dp0background_service\ZapretGUI.Service.exe" --uninstall __BYPASS_SID__
  if errorlevel 1 exit /b 1
)
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v ZapretGUI /f >nul 2>&1

ping 127.0.0.1 -n 3 >nul
set SCRIPT_PATH="%~f0"
set FOLDER_PATH=%~dp0
cd /d "%TEMP%"
echo @echo off > zapret_clean.bat
echo rmdir /s /q "%FOLDER_PATH%" >> zapret_clean.bat
echo del /f /q "%SCRIPT_PATH%" >> zapret_clean.bat
echo del /f /q zapret_clean.bat >> zapret_clean.bat
echo exit >> zapret_clean.bat
start /b cmd /c zapret_clean.bat
exit /b
'''
    from bypass_service import current_user_sid
    content = content.replace("__BYPASS_SID__", current_user_sid())
    with open(delete_bat_path, 'w', encoding='utf-8') as f:
        f.write(content)


translations = {
    'ru': {
        'Settings': 'Настройки',
        'Autostart program': 'Автозапуск программы',
        'Start minimized': 'Запускать свернутым',
        'Autostart profile': 'Профиль для автозагрузки',
        'Service mode': 'Сервисный режим',
        'Install Service': 'Установить сервис',
        'Remove Services': 'Сбросить соединения winws',
        'Check Updates': 'Проверить обновления',
        'About:': 'Подробнее:',
        'Off': 'Выключен',
        'On: {}': 'Включён: {}',
        'Instruction': 'Инструкция',
        'Sites': 'Сайты',
        'Add': 'Добавить',
        'Exclude': 'Исключить',
        'Enable': 'Включить',
        'Disable': 'Выключить',
        'Telegram Mode': 'Telegram Mode',
        'Add Domain': 'Добавить домен',
        'Exclude Domain': 'Исключить домен',
        'Add IP': 'Добавить IP',
        'Exclude IP': 'Исключить IP',
        'Game Mode': 'Игровой режим',
        'Game Mode Settings': 'Настройки игрового режима',
        'Game Mode Placeholder': 'Настройки игрового режима появятся позже.',
        'Instruction Text': """
        <b>1.</b> Выберите из выпадающего списка <b>профиль настроек</b>, затем нажмите на <span style="display:inline-block; padding:2px 8px; border-radius:8px; background:#d94b4b; color:white;"><b>большую красную кнопку</b></span>, чтобы запустить обход блокировок. Если выбранный профиль не сработал, переходите к следующему.<br><br>
        <b>2.</b> Проверить, работает ли текущий профиль можно, например на: <a href="https://www.youtube.com">@YouTube</a> или <a href="https://discord.com/">@Discord</a><br><br>
        <b>3.</b> В настройках можно включить <b>Автозапуск</b> вместе с Windows и выбрать профиль для автозапуска. А также проверить обновления списков и приложения.<br><br>
        <b>4.</b> Игровой режим <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>G</b></span> активирует Game Filters, чтобы обходить блокировки игровых сервисов. Его можно настроить по <b>шестерёнке</b> рядом с ним.<br><br>
        <b>5.</b> Кнопка <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>A</b></span> открывает два режима автоподбора: перебор готовых стратегий и создание новой адаптивной стратегии с проверкой подключения.<br><br>
        <b>6.</b> Кнопка <span style="display:inline-block; min-width:22px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>Ai</b></span> открывает для доступ к недоступным нейросетям БЕЗ VPN.<br><br>
        <b>7.</b> Инструкцию по использованию Менеджера сайтов можно открыть по кнопке <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>i</b></span> внутри окна, либо по этой кнопке:
        <a href="app://site-manager-tutorial" style="display:inline-block; padding:3px 10px; border-radius:8px; background:#2db45f; color:white; text-decoration:none;"><b>Нажми сюда</b></a>
        """,
        'Enable bypass': 'Включить обход',
        'Disable bypass': 'Выключить обход',
        'Select profile': 'Выбрать конфиг',
        'Exit': 'Выход',
        'Open': 'Открыть',
        'Minimize to tray': 'Свернуть в трей',
    },
    'en': {
        'Settings': 'Settings',
        'Autostart program': 'Autostart program',
        'Start minimized': 'Start minimized',
        'Autostart profile': 'Autostart profile',
        'Service mode': 'Service mode',
        'Install Service': 'Install Service',
        'Remove Services': 'Reset winws connections',
        'Check Updates': 'Check Updates',
        'About:': 'About:',
        'Off': 'Off',
        'On: {}': 'On: {}',
        'Instruction': 'Instruction',
        'Sites': 'Sites',
        'Add': 'Add',
        'Exclude': 'Exclude',
        'Enable': 'Enable',
        'Disable': 'Disable',
        'Telegram Mode': 'Telegram Mode',
        'Add Domain': 'Add domain',
        'Exclude Domain': 'Exclude domain',
        'Add IP': 'Add IP',
        'Exclude IP': 'Exclude IP',
        'Game Mode': 'Game mode',
        'Game Mode Settings': 'Game mode settings',
        'Game Mode Placeholder': 'Game mode settings will be added later.',
        'Instruction Text': """
        <b>1.</b> Select a <b>profile</b> from the dropdown list, then click the <span style="display:inline-block; padding:2px 8px; border-radius:8px; background:#d94b4b; color:white;"><b>big red button</b></span> to start the bypass. <i>By default, profile <b>General (ALT)</b> is used.</i><br><br>
        <b>2.</b> If the selected profile does not work, stop bypass with the <span style="display:inline-block; padding:2px 8px; border-radius:8px; background:#2db45f; color:white;"><b>green button</b></span> and choose another profile.<br><br>
        <b>3.</b> In settings you can enable <b>Autostart</b> with Windows and choose a profile for autostart.<br><br>
        <b>4.</b> To check if bypass works — try opening websites that were blocked for you, or test on: <a href="https://www.youtube.com">@YouTube</a> or <a href="https://discord.com/">@Discord</a><br><br>
        <b>5.</b> Game mode <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>G</b></span> enables Game Filters for blocked game services. Use the gear button next to it for settings.<br><br>
        <b>6.</b> Button <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>A</b></span> opens two modes: a scan of ready-made strategies and a new adaptive strategy builder with connection validation.<br><br>
        <b>7.</b> Button <span style="display:inline-block; min-width:22px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>Ai</b></span> enables Ai DNS for restricted neural-network services.<br><br>
        <b>8.</b> You can open the Site Manager guide from the <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>i</b></span> button inside that window, or by pressing this button:
        <a href="app://site-manager-tutorial" style="display:inline-block; padding:3px 10px; border-radius:8px; background:#2db45f; color:white; text-decoration:none;"><b>Click here</b></a>
        """,
        'Enable bypass': 'Enable bypass',
        'Disable bypass': 'Disable bypass',
        'Select profile': 'Select profile',
        'Exit': 'Exit',
        'Open': 'Open',
        'Minimize to tray': 'Minimize to tray',
    }
}

_DETACHED_UPDATE_WORKERS = []


def _show_gui_update_question(parent, lang: str, result: dict, allow_skip: bool = False) -> tuple[bool, bool]:
    latest_ver = str(result.get("latest_ver") or "")
    current_ver = str(result.get("current_ver") or APP_VERSION)
    release_url = str(result.get("release_url") or GUI_RELEASES_URL)

    msg = QMessageBox(parent)
    msg.setWindowTitle("Обновление GUI" if lang == "ru" else "GUI update")
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText(
        (
            f"Доступна новая версия GUI: {latest_ver}\n"
            f"Текущая версия GUI: {current_ver}\n\n"
            "Будет скачан zip-архив релиза, текущая версия закроется, "
            "файлы будут распакованы поверх запущенной версии, ярлык будет обновлён, "
            "после чего запустится новая версия.\n\n"
            "Обновить сейчас?"
        )
        if lang == "ru" else
        (
            f"New GUI version available: {latest_ver}\n"
            f"Current GUI version: {current_ver}\n\n"
            "The release zip will be downloaded, the current app will close, "
            "files will be unpacked over the running version, shortcuts will be updated, "
            "and the new version will be started.\n\n"
            "Update now?"
        )
    )
    msg.setInformativeText(release_url)
    skip_cb = None
    if allow_skip:
        skip_cb = QCheckBox("Пропустить это обновление" if lang == "ru" else "Skip this update")
        msg.setCheckBox(skip_cb)

    btn_yes = msg.addButton("Да" if lang == "ru" else "Yes", QMessageBox.ButtonRole.YesRole)
    msg.addButton("Нет" if lang == "ru" else "No", QMessageBox.ButtonRole.NoRole)
    msg.exec()

    update_now = msg.clickedButton() == btn_yes
    skip = bool(skip_cb and skip_cb.isChecked() and not update_now)
    return update_now, skip
