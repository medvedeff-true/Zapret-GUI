# --- Process and bundled-runtime bootstrap ---------------------------------

def _app_dir_from_cli_or_default() -> str:
    default_dir = os.path.join(os.path.expanduser('~'), 'ZapretGUI')
    prefix = "--app-dir="
    try:
        for arg in sys.argv[1:]:
            if not str(arg).startswith(prefix):
                continue
            candidate = os.path.abspath(os.path.expandvars(str(arg)[len(prefix):].strip().strip('"')))
            if candidate:
                return candidate
    except Exception:
        pass
    return default_dir

def _run_hidden(args, cwd=None, timeout=None):
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE

        return subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=timeout,
            startupinfo=si,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None


def _telegram_desktop_process_is_running() -> bool:
    try:
        import psutil
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                name = os.path.basename(str(proc.info.get("name") or proc.info.get("exe") or "")).casefold()
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            if name == "telegram.exe":
                return True
    except Exception:
        pass

    try:
        completed = _run_hidden(["tasklist", "/FI", "IMAGENAME eq Telegram.exe", "/NH"], timeout=4)
        output = ((completed.stdout if completed is not None else "") or "").casefold()
        return "telegram.exe" in output
    except Exception:
        return False


def _telegram_desktop_has_local_proxy_connection(port: int) -> bool:
    try:
        target_port = int(port or 0)
    except Exception:
        target_port = 0
    if target_port <= 0:
        return False

    try:
        import psutil
        established = {getattr(psutil, "CONN_ESTABLISHED", "ESTABLISHED"), "ESTABLISHED"}
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                name = os.path.basename(str(proc.info.get("name") or proc.info.get("exe") or "")).casefold()
                if name != "telegram.exe":
                    continue
                conns = proc.net_connections(kind="inet")
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
            except Exception:
                continue

            for conn in conns:
                try:
                    raddr = conn.raddr
                    if not raddr:
                        continue
                    host = str(getattr(raddr, "ip", raddr[0]) or "").strip().lower()
                    rport = int(getattr(raddr, "port", raddr[1]) or 0)
                    if (
                        rport == target_port
                        and host in {"127.0.0.1", "::1"}
                        and str(conn.status) in established
                    ):
                        return True
                except Exception:
                    continue
    except Exception:
        pass
    return False


def _telegram_executable_from_command(command: str) -> str:
    command = (command or "").strip()
    if not command:
        return ""
    if command.startswith('"'):
        match = re.match(r'"([^"]+)"', command)
        candidate = match.group(1).strip() if match else ""
    else:
        candidate = command.split(maxsplit=1)[0].strip()
    candidate = os.path.expandvars(candidate.strip('"'))
    if candidate and os.path.exists(candidate):
        return candidate
    return ""


def _find_telegram_desktop_executable() -> str:
    if sys.platform.startswith("win"):
        try:
            import winreg
            for root in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                for key_path in (
                    r"Software\Classes\tg\shell\open\command",
                    r"SOFTWARE\Classes\tg\shell\open\command",
                ):
                    try:
                        with winreg.OpenKey(root, key_path) as key:
                            command, _ = winreg.QueryValueEx(key, "")
                        exe = _telegram_executable_from_command(str(command or ""))
                        if exe and os.path.basename(exe).casefold() == "telegram.exe":
                            return exe
                    except Exception:
                        pass
        except Exception:
            pass

    candidates = []
    appdata = os.environ.get("APPDATA", "")
    localappdata = os.environ.get("LOCALAPPDATA", "")
    program_files = [os.environ.get("ProgramFiles", ""), os.environ.get("ProgramFiles(x86)", "")]
    if appdata:
        candidates.append(os.path.join(appdata, "Telegram Desktop", "Telegram.exe"))
    if localappdata:
        candidates.extend((
            os.path.join(localappdata, "Programs", "Telegram Desktop", "Telegram.exe"),
            os.path.join(localappdata, "Telegram Desktop", "Telegram.exe"),
        ))
    for root in program_files:
        if root:
            candidates.append(os.path.join(root, "Telegram Desktop", "Telegram.exe"))

    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return candidate
    return ""


def _launch_telegram_desktop_app() -> bool:
    if _telegram_desktop_process_is_running():
        return True

    exe = _find_telegram_desktop_executable()
    if not exe:
        return False

    try:
        subprocess.Popen(
            [exe],
            cwd=os.path.dirname(exe),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )
        return True
    except Exception:
        try:
            os.startfile(exe)
            return True
        except Exception:
            return False

def extract_files_from_meipass():
    base_src = (
        _bundled_root_dir()
        if "_bundled_root_dir" in globals()
        else (
            sys._MEIPASS
            if hasattr(sys, "_MEIPASS")
            else str(Path(__file__).resolve().parents[2] / "resources")
        )
    )

    # Version migration installs these directories transactionally.  This
    # copy-if-missing path remains only for an initial/incomplete same-version
    # extraction and must never be used to mix two bundled runtimes.
    for folder in ("flags", "core", "background_service"):
        _safe_copy_tree(
            os.path.join(base_src, folder),
            os.path.join(APP_DIR, folder),
            overwrite=False
        )

    try:
        src_uninstall = os.path.join(base_src, "core", "fast", "uninstall.bat")
        if os.path.exists(src_uninstall) and (not os.path.exists(REMOVE_BAT)):
            _safe_copy_file(src_uninstall, REMOVE_BAT, overwrite=False)
    except Exception:
        pass

    if hasattr(sys, "_MEIPASS"):
        # Core can legitimately be newer than the GUI bundle after a separate
        # core update. Same-version startup therefore checks completeness only;
        # byte-for-byte bundle verification is reserved for GUI migration.
        _validate_runtime_tree(APP_DIR)

def unblock_core_tree(core_dir: str) -> None:
    if not os.path.isdir(core_dir):
        return
    try:
        _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                (
                    f"Get-ChildItem -LiteralPath '{core_dir}' -Recurse -File "
                    "| Unblock-File -ErrorAction SilentlyContinue"
                )
            ]
        )
    except Exception:
        pass

def _safe_copy_file(src: str, dst: str, overwrite: bool = False) -> bool:
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if (not overwrite) and os.path.exists(dst):
        return False

    try:
        shutil.copy2(src, dst)
        return True
    except PermissionError:
        return False
    except OSError:
        return False


def _safe_copy_tree(src_root: str, dst_root: str, overwrite: bool = False) -> None:
    if not os.path.isdir(src_root):
        return

    for root, _, files in os.walk(src_root):
        rel = os.path.relpath(root, src_root)
        target_dir = dst_root if rel == "." else os.path.join(dst_root, rel)
        try:
            os.makedirs(target_dir, exist_ok=True)
        except OSError:
            # Не трогаем уже установленный runtime, если у процесса нет прав.
            # Иначе обычный запуск превращается в необработанное исключение.
            return

        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(target_dir, f)
            _safe_copy_file(s, d, overwrite=overwrite)


MANAGED_RUNTIME_DIRS = ("flags", "core", "background_service")
MANAGED_RUNTIME_CRITICAL_FILES = (
    os.path.join("core", "bin", "winws.exe"),
    os.path.join("core", "bin", "cygwin1.dll"),
    os.path.join("core", "bin", "WinDivert.dll"),
    os.path.join("core", "bin", "WinDivert64.sys"),
    os.path.join("background_service", "ZapretGUI.Service.exe"),
)


class RuntimeMigrationError(RuntimeError):
    """The bundled runtime could not be installed as one consistent unit."""


def _runtime_tree_is_accessible(path: str) -> bool:
    try:
        with os.scandir(path):
            pass
        return True
    except OSError:
        return False


def _make_runtime_tree_accessible(path: str) -> bool:
    """Делает установленный runtime доступным обычному пользователю Windows."""
    if not os.path.lexists(path) or _runtime_tree_is_accessible(path):
        return True
    if not sys.platform.startswith("win"):
        return False
    try:
        user = os.environ.get("USERNAME", "").strip()
        if not user:
            return False
        result = _run_hidden(
            [
                "icacls.exe",
                path,
                "/inheritance:e",
                "/grant:r",
                f"{user}:(OI)(CI)F",
                "/T",
                "/C",
            ],
            timeout=30,
        )
        if result is None or result.returncode != 0:
            return False
    except Exception:
        return False
    return _runtime_tree_is_accessible(path)


def _copy_tree_strict(src_root: str, dst_root: str) -> None:
    if not os.path.isdir(src_root) or os.path.islink(src_root):
        raise RuntimeMigrationError(f"Bundled runtime directory is missing: {src_root}")
    os.makedirs(dst_root, exist_ok=True)
    for root, dirs, files in os.walk(src_root, followlinks=False):
        for name in dirs:
            source = os.path.join(root, name)
            if os.path.islink(source):
                raise RuntimeMigrationError(f"Bundled runtime contains a link: {source}")
            os.makedirs(os.path.join(dst_root, os.path.relpath(source, src_root)), exist_ok=True)
        for name in files:
            source = os.path.join(root, name)
            if os.path.islink(source):
                raise RuntimeMigrationError(f"Bundled runtime contains a link: {source}")
            target = os.path.join(dst_root, os.path.relpath(source, src_root))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            try:
                shutil.copy2(source, target)
            except OSError as error:
                raise RuntimeMigrationError(f"Could not stage runtime file {source}: {error}") from error


def _sha256_file_strict(path: str) -> str:
    try:
        digest = hashlib.sha256()
        with open(path, "rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError as error:
        raise RuntimeMigrationError(f"Could not read runtime file {path}: {error}") from error


def _validate_runtime_tree(runtime_root: str, compare_to: str | None = None) -> None:
    for folder in MANAGED_RUNTIME_DIRS:
        path = os.path.join(runtime_root, folder)
        if not os.path.isdir(path):
            raise RuntimeMigrationError(f"Runtime directory is missing: {path}")
    for relative in MANAGED_RUNTIME_CRITICAL_FILES:
        path = os.path.join(runtime_root, relative)
        if not os.path.isfile(path) or os.path.getsize(path) <= 0:
            raise RuntimeMigrationError(f"Critical runtime file is missing or empty: {path}")
        if compare_to:
            expected = os.path.join(compare_to, relative)
            if _sha256_file_strict(path) != _sha256_file_strict(expected):
                raise RuntimeMigrationError(f"Runtime hash mismatch: {relative}")


def _read_core_strategy_files_strict(core_dir: str) -> dict[str, dict]:
    files: dict[str, dict] = {}
    if not os.path.isdir(core_dir):
        return files
    for name in os.listdir(core_dir):
        if not _is_core_strategy_bat_name(name):
            continue
        path = os.path.join(core_dir, name)
        if not os.path.isfile(path):
            continue
        try:
            with open(path, "rb") as stream:
                files[name.lower()] = {"name": name, "data": stream.read()}
        except OSError as error:
            raise RuntimeMigrationError(f"Could not preserve user strategy {path}: {error}") from error
    return files


def _backup_core_strategy_files_strict(strategy_files: dict[str, dict], reason: str) -> str:
    if not strategy_files:
        return ""
    backup_dir = _safe_strategy_backup_folder(reason)
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for item in strategy_files.values():
            name = os.path.basename(str(item.get("name") or ""))
            data = item.get("data")
            if not name or not isinstance(data, (bytes, bytearray)):
                raise RuntimeMigrationError("Invalid user strategy backup entry")
            target = os.path.join(backup_dir, name)
            with open(target, "wb") as stream:
                stream.write(bytes(data))
            if _read_file_bytes(target) != bytes(data):
                raise RuntimeMigrationError(f"Strategy backup verification failed: {name}")
        return backup_dir
    except RuntimeMigrationError:
        raise
    except OSError as error:
        raise RuntimeMigrationError(f"Could not create strategy backup: {error}") from error


def _restore_custom_strategy_files_strict(
    core_dir: str,
    strategy_files: dict[str, dict],
    replacement_strategy_names: set[str],
) -> int:
    replacement_names = {str(x).lower() for x in (replacement_strategy_names or set())}
    expected = [item for low, item in strategy_files.items() if low not in replacement_names]
    restored = 0
    for item in expected:
        name = os.path.basename(str(item.get("name") or ""))
        data = item.get("data")
        if not name or not isinstance(data, (bytes, bytearray)):
            raise RuntimeMigrationError("Invalid preserved strategy")
        target = _unique_strategy_restore_path(core_dir, name)
        try:
            with open(target, "wb") as stream:
                stream.write(bytes(data))
            if _read_file_bytes(target) != bytes(data):
                raise RuntimeMigrationError(f"Strategy restore verification failed: {name}")
        except RuntimeMigrationError:
            raise
        except OSError as error:
            raise RuntimeMigrationError(f"Could not restore user strategy {name}: {error}") from error
        restored += 1
    if restored != len(expected):
        raise RuntimeMigrationError("Not all user strategies were restored")
    return restored


def _remove_path_strict(path: str) -> None:
    if not os.path.lexists(path):
        return
    try:
        if os.path.isdir(path) and not os.path.islink(path):
            shutil.rmtree(path, ignore_errors=False)
        else:
            os.remove(path)
    except OSError as error:
        raise RuntimeMigrationError(f"Could not remove managed runtime path {path}: {error}") from error


def _write_runtime_version_strict(version: str) -> None:
    os.makedirs(os.path.dirname(VERSION_FILE), exist_ok=True)
    fd, temp_path = tempfile.mkstemp(prefix=".app_version-", suffix=".tmp", dir=os.path.dirname(VERSION_FILE))
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(str(version).strip() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temp_path, VERSION_FILE)
    except OSError as error:
        try:
            os.remove(temp_path)
        except OSError:
            pass
        raise RuntimeMigrationError(f"Could not commit runtime version marker: {error}") from error


def _migrate_bundled_runtime(base_src: str, previous_version: str) -> None:
    os.makedirs(APP_DIR, exist_ok=True)
    source_root = os.path.abspath(base_src)
    _validate_runtime_tree(source_root)
    source_uninstall = os.path.join(source_root, "core", "fast", "uninstall.bat")
    if not os.path.isfile(source_uninstall):
        raise RuntimeMigrationError(f"Bundled uninstall script is missing: {source_uninstall}")

    current_strategy_files = _read_core_strategy_files_strict(os.path.join(APP_DIR, "core"))
    replacement_names = _strategy_bat_names_from_dir(os.path.join(source_root, "core"))
    _backup_core_strategy_files_strict(
        current_strategy_files,
        f"gui-{previous_version or 'unknown'}-to-{APP_VERSION}",
    )

    stage_root = tempfile.mkdtemp(prefix=".runtime-update-temp-", dir=APP_DIR)
    backup_root = tempfile.mkdtemp(prefix=".runtime-update-backup-", dir=APP_DIR)
    moved_originals: list[str] = []
    installed: list[str] = []
    committed = False
    try:
        for folder in MANAGED_RUNTIME_DIRS:
            _copy_tree_strict(os.path.join(source_root, folder), os.path.join(stage_root, folder))
        _restore_custom_strategy_files_strict(
            os.path.join(stage_root, "core"),
            current_strategy_files,
            replacement_names,
        )
        shutil.copy2(source_uninstall, os.path.join(stage_root, "uninstall.bat"))
        _validate_runtime_tree(stage_root, source_root)

        for name in [*MANAGED_RUNTIME_DIRS, "uninstall.bat"]:
            destination = os.path.join(APP_DIR, name)
            old_path = os.path.join(backup_root, name)
            if os.path.lexists(destination):
                os.rename(destination, old_path)
                moved_originals.append(name)
            try:
                if os.path.lexists(destination):
                    _remove_path_strict(destination)
                os.rename(os.path.join(stage_root, name), destination)
            except Exception:
                if os.path.lexists(old_path) and not os.path.lexists(destination):
                    os.rename(old_path, destination)
                    moved_originals.remove(name)
                raise
            installed.append(name)

        # The staged files were created by this unelevated process and are
        # already usable by it. ACL repair is only a compatibility measure for
        # older installations and must not turn a successfully installed
        # runtime into a permanent startup/retry loop.
        for folder in MANAGED_RUNTIME_DIRS:
            destination = os.path.join(APP_DIR, folder)
            try:
                _make_runtime_tree_accessible(destination)
            except Exception:
                pass
        _validate_runtime_tree(APP_DIR, source_root)
        if _sha256_file_strict(os.path.join(APP_DIR, "uninstall.bat")) != _sha256_file_strict(source_uninstall):
            raise RuntimeMigrationError("Uninstall script verification failed")
        _write_runtime_version_strict(APP_VERSION)
        committed = True
    except Exception as error:
        rollback_errors = []
        for name in reversed(installed):
            destination = os.path.join(APP_DIR, name)
            try:
                _remove_path_strict(destination)
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        for name in reversed(moved_originals):
            destination = os.path.join(APP_DIR, name)
            old_path = os.path.join(backup_root, name)
            try:
                if os.path.lexists(destination):
                    _remove_path_strict(destination)
                if os.path.lexists(old_path):
                    os.rename(old_path, destination)
            except Exception as rollback_error:
                rollback_errors.append(str(rollback_error))
        detail = str(error)
        if rollback_errors:
            detail += "; rollback failed: " + "; ".join(rollback_errors)
        raise RuntimeMigrationError(detail) from error
    finally:
        if committed:
            try:
                shutil.rmtree(backup_root, ignore_errors=False)
            except OSError:
                pass
        try:
            shutil.rmtree(stage_root, ignore_errors=False)
        except OSError:
            pass
