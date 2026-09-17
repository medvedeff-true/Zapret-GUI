# --- Single-instance guard and application entry point ----------------------

def _same_file_path(left: str, right: str) -> bool:
    try:
        return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))
    except Exception:
        return os.path.normcase(str(left or "")) == os.path.normcase(str(right or ""))


def _find_existing_app_processes() -> list[dict]:
    try:
        import psutil
    except Exception:
        return []

    rows = []
    current_pid = os.getpid()
    current_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    current_script = os.path.abspath(sys.argv[0])
    frozen_name = "ZapretGUI.exe".casefold()

    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            if int(proc.info.get("pid") or 0) == current_pid:
                continue
            name = str(proc.info.get("name") or "")
            exe = str(proc.info.get("exe") or "")
            cmdline = [str(x) for x in (proc.info.get("cmdline") or [])]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        matched = False
        if exe and _same_file_path(exe, current_exe):
            matched = True
        elif name.casefold() == frozen_name and os.path.basename(exe or name).casefold() == frozen_name:
            matched = True
        elif not getattr(sys, "frozen", False):
            for part in cmdline:
                if part and _same_file_path(part, current_script):
                    matched = True
                    break

        if matched:
            rows.append({"pid": int(proc.info.get("pid") or 0), "name": name or os.path.basename(exe), "exe": exe})
    return rows


def _terminate_existing_app_processes(processes: list[dict], timeout: float = 4.0) -> tuple[bool, str]:
    try:
        import psutil
    except Exception as e:
        return False, str(e)

    targets = []
    for row in processes:
        try:
            pid = int(row.get("pid") or 0)
            if pid and pid != os.getpid():
                targets.append(psutil.Process(pid))
        except Exception:
            pass

    if not targets:
        return True, ""

    errors = []
    for proc in targets:
        try:
            proc.terminate()
        except Exception as e:
            errors.append(str(e))

    try:
        gone, alive = psutil.wait_procs(targets, timeout=timeout)
    except Exception:
        alive = targets

    for proc in alive:
        try:
            proc.kill()
        except Exception as e:
            errors.append(str(e))

    try:
        _, alive = psutil.wait_procs(alive, timeout=2.0)
    except Exception:
        pass

    still_alive = []
    for proc in targets:
        try:
            if proc.is_running():
                still_alive.append(str(proc.pid))
        except Exception:
            pass

    if still_alive:
        return False, "; ".join(errors) or ("still running: " + ", ".join(still_alive))
    return True, ""


SINGLE_INSTANCE_MUTEX_NAME = "Local\\ZapretGUI_SingleInstance"
SINGLE_INSTANCE_ACTIVATE_EVENT_NAME = "Local\\ZapretGUI_SingleInstance_Activate"


def _try_acquire_single_instance_lock() -> tuple[bool, int | None, str]:
    if not sys.platform.startswith("win"):
        return True, None, ""

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool

        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
        err = ctypes.get_last_error()
        if not handle:
            return True, None, f"CreateMutexW failed: {err}"
        if err == 183:  # ERROR_ALREADY_EXISTS
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
            return False, None, "already-running"
        return True, int(handle), ""
    except Exception as e:
        return True, None, str(e)


def _release_single_instance_lock(handle: int | None) -> None:
    if not handle or not sys.platform.startswith("win"):
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle(ctypes.c_void_p(int(handle)))
    except Exception:
        pass


def _keep_single_instance_lock(app: QApplication, handle: int | None) -> None:
    if not handle:
        return
    try:
        app._zapret_single_instance_mutex = handle
        app.aboutToQuit.connect(lambda h=handle: _release_single_instance_lock(h))
    except Exception:
        pass
    if sys.platform.startswith("win"):
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.CreateEventW.argtypes = [
                ctypes.c_void_p,
                ctypes.c_bool,
                ctypes.c_bool,
                ctypes.c_wchar_p,
            ]
            kernel32.CreateEventW.restype = ctypes.c_void_p
            event_handle = kernel32.CreateEventW(
                None,
                False,  # auto-reset
                False,
                SINGLE_INSTANCE_ACTIVATE_EVENT_NAME,
            )
            if event_handle:
                app._zapret_single_instance_activate_event = int(event_handle)
                app.aboutToQuit.connect(
                    lambda h=int(event_handle): _release_single_instance_lock(h)
                )
        except Exception:
            pass


def _install_single_instance_activation_listener(
    app: QApplication,
    window: "MainWindow",
) -> None:
    """Poll the named event on Qt's thread and restore the tray window safely."""
    handle = int(getattr(app, "_zapret_single_instance_activate_event", 0) or 0)
    if not handle or not sys.platform.startswith("win"):
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        kernel32.WaitForSingleObject.restype = ctypes.c_uint
    except Exception:
        return

    timer = QTimer(app)
    timer.setInterval(75)

    def poll_activation_event() -> None:
        try:
            if kernel32.WaitForSingleObject(ctypes.c_void_p(handle), 0) == 0:
                window._restore_from_external_activation()
        except Exception:
            pass

    timer.timeout.connect(poll_activation_event)
    timer.start()
    app._zapret_single_instance_activate_timer = timer


def _notify_existing_instance_to_activate(retries: int = 8) -> bool:
    if not sys.platform.startswith("win"):
        return False
    for _ in range(max(1, int(retries))):
        # This does not require a visible or even fully-created HWND, so it also
        # works when the first instance started directly in the tray.
        try:
            kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            kernel32.OpenEventW.argtypes = [
                ctypes.c_uint,
                ctypes.c_bool,
                ctypes.c_wchar_p,
            ]
            kernel32.OpenEventW.restype = ctypes.c_void_p
            kernel32.SetEvent.argtypes = [ctypes.c_void_p]
            kernel32.SetEvent.restype = wintypes.BOOL
            kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel32.CloseHandle.restype = wintypes.BOOL
            event_handle = kernel32.OpenEventW(
                0x0002,  # EVENT_MODIFY_STATE
                False,
                SINGLE_INSTANCE_ACTIVATE_EVENT_NAME,
            )
            if event_handle:
                try:
                    if kernel32.SetEvent(event_handle):
                        return True
                finally:
                    kernel32.CloseHandle(event_handle)
        except Exception:
            pass
        time.sleep(0.09)
    return False


def _handle_existing_instance_before_start(app: QApplication) -> bool:
    acquired, handle, _error = _try_acquire_single_instance_lock()
    if acquired:
        _keep_single_instance_lock(app, handle)
        return True

    if _notify_existing_instance_to_activate():
        return False

    # The first instance can be exiting while its mutex is still alive.  In
    # that brief gap, try to become the owner instead of displaying a false
    # "already running" error.
    for _ in range(8):
        time.sleep(0.12)
        acquired, handle, _error = _try_acquire_single_instance_lock()
        if acquired:
            _keep_single_instance_lock(app, handle)
            return True

    # Do not show an "already running" error: the first instance may still be
    # closing, or Windows may briefly keep a stale mutex/window handle.
    return False


def main():
    dns_cli_action = None
    telegram_hosts_cli_action = None
    for arg in sys.argv[1:]:
        if arg.startswith("--dns-malw-link-action="):
            dns_cli_action = arg.split("=", 1)[1].strip().lower()
            break
        if arg.startswith("--telegram-mode-hosts-action="):
            telegram_hosts_cli_action = arg.split("=", 1)[1].strip().lower()
            break

    if dns_cli_action in {"enable", "disable"}:
        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
        if dns_cli_action == "enable":
            _enable_dns_malw_link(settings)
        else:
            _disable_dns_malw_link(settings)
        return

    if telegram_hosts_cli_action in {"enable", "disable"}:
        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
        _apply_flowseal_telegram_hosts(telegram_hosts_cli_action == "enable", settings)
        return

    if sys.platform.startswith("win"):
        try:
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            ctypes.windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            )
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    try:
        # Не даём Qt криво округлять scale factor на 125/150/175/200%
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    _apply_unified_qt_style(app)
    if not _handle_existing_instance_before_start(app):
        return
    post_update_splash = None
    if _was_started_after_update():
        post_update_splash = QLabel(
            "Завершение обновления…\nПроверка системного компонента…"
        )
        post_update_splash.setWindowTitle("Zapret GUI")
        post_update_splash.setAlignment(Qt.AlignmentFlag.AlignCenter)
        post_update_splash.setFixedSize(390, 120)
        post_update_splash.setStyleSheet(
            "QLabel { background:#171717; color:#f2f2f2; "
            "font: 600 11pt 'Segoe UI'; border:1px solid rgba(255,255,255,0.14); "
            "border-radius:12px; padding:18px; }"
        )
        post_update_splash.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        post_update_splash.show()
        app.processEvents()
    try:
        wipe_app_dir_if_new_version()
        extract_files_from_meipass()
    except (RuntimeMigrationError, OSError) as error:
        QMessageBox.critical(
            None,
            "Ошибка обновления runtime" if str(sys.argv).lower().find("ru") >= 0 else "Runtime update error",
            "Не удалось полностью обновить компоненты Zapret GUI.\n"
            "Изменения отменены, старая рабочая версия сохранена. "
            "Повторите запуск программы.\n\n"
            f"Детали: {error}",
        )
        return
    restore_pending_user_strategies_after_extract()
    unblock_core_tree(os.path.join(APP_DIR, "core"))
    create_delete_bat()
    settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
    _patch_profiles_if_core_outdated(os.path.join(APP_DIR, "core"), settings)
    _patch_profiles_hide_windows(os.path.join(APP_DIR, "core"))
    _ensure_user_lists_initialized()
    _rebuild_runtime_lists(settings)
    if _was_started_after_update():
        try:
            _prepare_post_update_runtime()
        except Exception as error:
            QMessageBox.warning(
                None,
                "Обновление завершено не полностью",
                "Новая версия Zapret GUI установлена, но системный компонент "
                "не удалось проверить или обновить.\n\n"
                "Программа продолжит работать. При следующем запуске обхода "
                "можно повторить установку компонента.\n\n"
                f"Детали: {error}",
            )
    win = MainWindow(settings, launched_by_autostart=_was_started_by_autostart())
    _install_single_instance_activation_listener(app, win)
    if post_update_splash is not None:
        post_update_splash.close()
    try:
        app.commitDataRequest.connect(win._handle_system_shutdown_request)
    except Exception:
        pass
    icon_path = os.path.join(APP_DIR, 'flags', 'z.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    exit_code = app.exec()
    sys.exit(exit_code)
