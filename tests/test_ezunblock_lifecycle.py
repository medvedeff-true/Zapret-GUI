from __future__ import annotations

import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings

import EzUnBlock as app


class AiDnsBundleTests(unittest.TestCase):
    def test_current_gemini_mapping_wins_over_supplementary_duplicate(self) -> None:
        bundle = (
            "62.133.62.97 gemini.google.com\n"
            "192.0.2.9 gemini.google.com\n"
            "62.133.62.97 generativelanguage.googleapis.com\n"
            "193.233.112.68 chatgpt.com\n"
            "203.0.113.5 api.github.com\n"
        )

        result = app._filter_dns_malw_hosts_bundle(bundle)

        self.assertIn("62.133.62.97 gemini.google.com", result)
        self.assertIn("generativelanguage.googleapis.com", result)
        self.assertNotIn("192.0.2.9 gemini.google.com", result)
        self.assertNotIn("api.github.com", result)

    def test_offline_seed_contains_the_gemini_service_chain(self) -> None:
        seed = Path(app._bundled_path("core", "lists", "dns_malw_hosts_seed.txt"))
        self.assertTrue(seed.is_file())
        text = seed.read_text(encoding="utf-8")
        for hostname in (
            "gemini.google.com",
            "aistudio.google.com",
            "generativelanguage.googleapis.com",
            "notebooklm.google.com",
        ):
            self.assertIn(hostname, text)


class LifecycleTests(unittest.TestCase):
    def test_start_minimized_requires_the_scheduler_marker(self) -> None:
        self.assertFalse(app._should_start_minimized(True, False))
        self.assertFalse(app._should_start_minimized(False, True))
        self.assertTrue(app._should_start_minimized(True, True))
        self.assertTrue(app._was_started_by_autostart(["--AUTOSTART"]))
        self.assertFalse(app._was_started_by_autostart(["--other-option"]))

    def test_autostart_task_command_marks_only_the_scheduler_launch(self) -> None:
        command = app._build_autostart_task_command(
            executable=r"C:\Program Files\Zapret GUI\ZapretGUI.exe",
            app_dir=r"C:\Program Files\Zapret GUI",
            frozen=True,
        )
        self.assertIn("--autostart", command)
        self.assertIn("--app-dir=", command)
        self.assertIn('"C:\\Program Files\\Zapret GUI\\ZapretGUI.exe"', command)
        self.assertTrue(app._was_started_after_update(["--POST-UPDATE"]))

    def test_runtime_version_marker_is_written_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            marker = Path(root) / ".app_version"
            with mock.patch.object(app, "VERSION_FILE", str(marker)):
                app._write_runtime_version_strict("9.8.7")
            self.assertEqual("9.8.7", marker.read_text(encoding="utf-8").strip())
            self.assertFalse(any(path.name.startswith(".app_version-") for path in Path(root).iterdir()))

    def test_runtime_migration_rolls_back_and_does_not_commit_version(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source = root_path / "bundle"
            target = root_path / "app"
            for base in (source, target):
                for relative in app.MANAGED_RUNTIME_CRITICAL_FILES:
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(("new-" if base == source else "old-").encode() + relative.encode())
                (base / "flags").mkdir(parents=True, exist_ok=True)
                (base / "core" / "fast").mkdir(parents=True, exist_ok=True)
            (source / "core" / "fast" / "uninstall.bat").write_text("new uninstall", encoding="utf-8")
            (target / "uninstall.bat").write_text("old uninstall", encoding="utf-8")
            (target / "core" / "my custom strategy.bat").write_text(
                ":: custom user strategy\n",
                encoding="utf-8",
            )
            (target / "settings.ini").write_text("keep", encoding="utf-8")
            user_dir = target / "user"
            user_dir.mkdir()
            (user_dir / "data.txt").write_text("keep", encoding="utf-8")

            original_replace = os.replace

            def fail_marker(source_path, destination_path):
                if os.path.normcase(str(destination_path)) == os.path.normcase(str(target / ".app_version")):
                    raise PermissionError("marker locked")
                return original_replace(source_path, destination_path)

            with (
                mock.patch.object(app, "APP_DIR", str(target)),
                mock.patch.object(app, "USER_DIR", str(user_dir)),
                mock.patch.object(app, "USER_STRATEGY_BACKUP_DIR", str(user_dir / "strategy-backups")),
                mock.patch.object(app, "VERSION_FILE", str(target / ".app_version")),
                mock.patch.object(app, "os", wraps=os) as os_module,
            ):
                os_module.replace.side_effect = fail_marker
                with self.assertRaises(app.RuntimeMigrationError):
                    app._migrate_bundled_runtime(str(source), "1.0.0")

            self.assertTrue((target / "core" / "bin" / "winws.exe").read_bytes().startswith(b"old-"))
            self.assertEqual("keep", (target / "settings.ini").read_text(encoding="utf-8"))
            self.assertEqual("keep", (user_dir / "data.txt").read_text(encoding="utf-8"))
            self.assertEqual(
                ":: custom user strategy\n",
                (target / "core" / "my custom strategy.bat").read_text(encoding="utf-8"),
            )
            self.assertFalse((target / ".app_version").exists())

    def test_runtime_migration_installs_bundle_and_preserves_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source = root_path / "bundle"
            target = root_path / "app"
            for base in (source, target):
                for relative in app.MANAGED_RUNTIME_CRITICAL_FILES:
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(("new-" if base == source else "old-").encode() + relative.encode())
                (base / "flags").mkdir(parents=True, exist_ok=True)
                (base / "core" / "fast").mkdir(parents=True, exist_ok=True)
            (source / "core" / "fast" / "uninstall.bat").write_text("new uninstall", encoding="utf-8")
            (target / "uninstall.bat").write_text("old uninstall", encoding="utf-8")
            (target / "settings.ini").write_text("keep", encoding="utf-8")
            user_dir = target / "user"
            user_dir.mkdir()
            (user_dir / "data.txt").write_text("keep", encoding="utf-8")

            with (
                mock.patch.object(app, "APP_DIR", str(target)),
                mock.patch.object(app, "USER_DIR", str(user_dir)),
                mock.patch.object(app, "USER_STRATEGY_BACKUP_DIR", str(user_dir / "strategy-backups")),
                mock.patch.object(app, "VERSION_FILE", str(target / ".app_version")),
            ):
                app._migrate_bundled_runtime(str(source), "1.0.0")

            self.assertTrue((target / "core" / "bin" / "winws.exe").read_bytes().startswith(b"new-"))
            self.assertEqual("keep", (target / "settings.ini").read_text(encoding="utf-8"))
            self.assertEqual("keep", (user_dir / "data.txt").read_text(encoding="utf-8"))
            self.assertEqual(app.APP_VERSION, (target / ".app_version").read_text(encoding="utf-8").strip())
            self.assertFalse(any(path.name.startswith(".runtime-update-") for path in target.iterdir()))

    def test_runtime_migration_commits_when_acl_repair_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source = root_path / "bundle"
            target = root_path / "app"
            for base in (source, target):
                for relative in app.MANAGED_RUNTIME_CRITICAL_FILES:
                    path = base / relative
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(("new-" if base == source else "old-").encode() + relative.encode())
                (base / "flags").mkdir(parents=True, exist_ok=True)
                (base / "core" / "fast").mkdir(parents=True, exist_ok=True)
            (source / "core" / "fast" / "uninstall.bat").write_text("new uninstall", encoding="utf-8")
            (target / "uninstall.bat").write_text("old uninstall", encoding="utf-8")

            with (
                mock.patch.object(app, "APP_DIR", str(target)),
                mock.patch.object(app, "USER_DIR", str(target / "user")),
                mock.patch.object(app, "USER_STRATEGY_BACKUP_DIR", str(target / "user" / "strategy-backups")),
                mock.patch.object(app, "VERSION_FILE", str(target / ".app_version")),
                mock.patch.object(app, "_make_runtime_tree_accessible", return_value=False),
            ):
                app._migrate_bundled_runtime(str(source), "2.1.1")

            self.assertEqual(app.APP_VERSION, (target / ".app_version").read_text(encoding="utf-8").strip())
            self.assertTrue((target / "core" / "bin" / "winws.exe").read_bytes().startswith(b"new-"))

    def test_same_version_with_a_broken_runtime_is_repaired(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            source = root_path / "bundle"
            target = root_path / "app"
            user_dir = target / "user"
            for relative in app.MANAGED_RUNTIME_CRITICAL_FILES:
                path = source / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"new-" + relative.encode())
            (source / "flags").mkdir(parents=True, exist_ok=True)
            (source / "core" / "fast").mkdir(parents=True, exist_ok=True)
            (source / "core" / "fast" / "uninstall.bat").write_text("uninstall", encoding="utf-8")
            (target / "core").mkdir(parents=True, exist_ok=True)
            (target / "core" / "bin").write_text("broken directory placeholder", encoding="utf-8")
            user_dir.mkdir(parents=True)
            (user_dir / "keep.txt").write_text("keep", encoding="utf-8")
            (target / ".app_version").write_text(app.APP_VERSION, encoding="utf-8")

            with (
                mock.patch.object(app, "APP_DIR", str(target)),
                mock.patch.object(app, "USER_DIR", str(user_dir)),
                mock.patch.object(app, "USER_STRATEGY_BACKUP_DIR", str(user_dir / "strategy-backups")),
                mock.patch.object(app, "VERSION_FILE", str(target / ".app_version")),
                mock.patch.object(app, "_force_stop_blockers"),
                mock.patch.object(app.sys, "_MEIPASS", str(source), create=True),
            ):
                app.wipe_app_dir_if_new_version()

            self.assertTrue((target / "core" / "bin" / "winws.exe").is_file())
            self.assertEqual("keep", (user_dir / "keep.txt").read_text(encoding="utf-8"))

    def test_same_version_with_an_inaccessible_runtime_is_left_alone(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            marker = root_path / ".app_version"
            marker.write_text(app.APP_VERSION, encoding="utf-8")
            with (
                mock.patch.object(app, "APP_DIR", str(root_path)),
                mock.patch.object(app, "VERSION_FILE", str(marker)),
                mock.patch.object(app, "_force_stop_blockers") as stop_blockers,
                mock.patch.object(app, "_migrate_bundled_runtime") as migrate,
                mock.patch.object(app.sys, "_MEIPASS", str(root_path), create=True),
                mock.patch.object(app.os.path, "lexists", side_effect=PermissionError("access denied")),
            ):
                app.wipe_app_dir_if_new_version()

            stop_blockers.assert_not_called()
            migrate.assert_not_called()

    def test_same_version_with_a_denied_runtime_repairs_its_access_before_copying(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            marker = root_path / ".app_version"
            marker.write_text(app.APP_VERSION, encoding="utf-8")
            for folder in app.MANAGED_RUNTIME_DIRS:
                (root_path / folder).mkdir()

            real_scandir = os.scandir

            def denied_scandir(path):
                if os.path.normcase(str(path)) == os.path.normcase(str(root_path / "core")):
                    raise PermissionError("access denied")
                return real_scandir(path)

            with (
                mock.patch.object(app, "APP_DIR", str(root_path)),
                mock.patch.object(app, "VERSION_FILE", str(marker)),
                mock.patch.object(app, "_make_runtime_tree_accessible") as make_accessible,
                mock.patch.object(app, "_force_stop_blockers") as stop_blockers,
                mock.patch.object(app, "_migrate_bundled_runtime") as migrate,
                mock.patch.object(app.sys, "_MEIPASS", str(root_path), create=True),
                mock.patch.object(app.os, "scandir", side_effect=denied_scandir),
            ):
                app.wipe_app_dir_if_new_version()

            self.assertEqual(
                [mock.call(str(root_path / folder)) for folder in app.MANAGED_RUNTIME_DIRS],
                make_accessible.call_args_list,
            )
            stop_blockers.assert_not_called()
            migrate.assert_not_called()

    def test_gui_update_is_prepared_without_starting_updater_early(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            archive = Path(root) / "update.zip"
            with zipfile.ZipFile(archive, "w") as package:
                package.writestr("ZapretGUI.exe", b"MZ" + b"x" * 2048)
            with (
                mock.patch.object(app, "_current_gui_executable_path", return_value=str(Path(root) / "ZapretGUI.exe")),
                mock.patch.object(app, "_download_gui_update_archive", return_value=str(archive)),
                mock.patch.object(app, "_write_gui_update_script", return_value=str(Path(root) / "apply.ps1")),
                mock.patch.object(app.subprocess, "Popen") as popen,
            ):
                result = app._schedule_gui_update_restart(
                    "3.1.0",
                    "https://example.invalid/update.zip",
                    "a" * 64,
                )
            self.assertTrue(result["ok"])
            self.assertEqual("gui-update-ready", result["status"])
            with mock.patch.object(app, "APP_DIR", root):
                script_path = app._write_gui_update_script()
                self.assertIn("--post-update", Path(script_path).read_text(encoding="utf-8"))
            popen.assert_not_called()

    def test_flowseal_core_update_rolls_back_when_the_archive_is_incomplete(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            core = root_path / "core"
            (core / "bin").mkdir(parents=True)
            (core / "service.bat").write_text('set "LOCAL_VERSION=old"\n', encoding="utf-8")
            (core / "bin" / "winws.exe").write_bytes(b"old-winws")
            (core / "bin" / "WinDivert64.sys").write_bytes(b"old-driver")
            (core / "custom.bat").write_text(":: custom\n", encoding="utf-8")

            archive_path = root_path / "incomplete.zip"
            with zipfile.ZipFile(archive_path, "w") as package:
                package.writestr("flowseal/service.bat", 'set "LOCAL_VERSION=new"\n')

            with zipfile.ZipFile(archive_path) as package:
                with self.assertRaisesRegex(RuntimeError, "flowseal-archive-missing"):
                    app._replace_core_from_archive(package, str(core))

            self.assertEqual(b"old-winws", (core / "bin" / "winws.exe").read_bytes())
            self.assertEqual(":: custom\n", (core / "custom.bat").read_text(encoding="utf-8"))
            self.assertFalse(any(path.name.startswith(".flowseal-update-") for path in root_path.iterdir()))

    def test_flowseal_core_update_is_staged_and_preserves_custom_strategies(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            core = root_path / "core"
            (core / "bin").mkdir(parents=True)
            (core / "service.bat").write_text('set "LOCAL_VERSION=old"\n', encoding="utf-8")
            (core / "bin" / "winws.exe").write_bytes(b"old-winws")
            (core / "bin" / "WinDivert64.sys").write_bytes(b"old-driver")
            (core / "custom.bat").write_text(":: custom\n", encoding="utf-8")
            (core / "lists").mkdir()
            (core / "lists" / "telegram-domains.txt").write_text("telegram.example\n", encoding="utf-8")
            (core / "fast").mkdir()
            (core / "fast" / "update_service.bat").write_text("@echo off\n", encoding="utf-8")

            archive_path = root_path / "complete.zip"
            with zipfile.ZipFile(archive_path, "w") as package:
                package.writestr("flowseal/service.bat", 'set "LOCAL_VERSION=new"\n')
                package.writestr("flowseal/bin/winws.exe", b"new-winws")
                package.writestr("flowseal/general.bat", "@echo off\n")

            with mock.patch.object(app, "USER_STRATEGY_BACKUP_DIR", str(root_path / "strategy-backups")):
                with zipfile.ZipFile(archive_path) as package:
                    app._replace_core_from_archive(package, str(core))

            self.assertEqual(b"new-winws", (core / "bin" / "winws.exe").read_bytes())
            self.assertEqual(b"old-driver", (core / "bin" / "WinDivert64.sys").read_bytes())
            self.assertEqual(":: custom\n", (core / "custom.bat").read_text(encoding="utf-8"))
            self.assertEqual(
                "telegram.example\n",
                (core / "lists" / "telegram-domains.txt").read_text(encoding="utf-8"),
            )
            self.assertEqual(
                "@echo off\n",
                (core / "fast" / "update_service.bat").read_text(encoding="utf-8"),
            )
            self.assertFalse(any(path.name.startswith(".flowseal-update-") for path in root_path.iterdir()))

    def test_installed_flowseal_version_wins_over_a_stale_setting(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            core = root_path / "core"
            core.mkdir()
            (core / "service.bat").write_text('set "LOCAL_VERSION=1.10.2"\n', encoding="utf-8")
            settings = QSettings(str(root_path / "settings.ini"), QSettings.Format.IniFormat)
            settings.setValue(app.FLOWSEAL_VER_KEY, "1.9.8b")
            settings.sync()

            with mock.patch.object(app, "APP_DIR", str(root_path)):
                detected = app._detect_runtime_core_version(settings)

            self.assertEqual("1.10.2", detected)
            self.assertEqual("1.10.2", settings.value(app.FLOWSEAL_VER_KEY))

    def test_gui_archive_requires_a_trusted_sha256(self) -> None:
        class FakeResponse:
            headers = {"Content-Length": "2048"}
            text = ""

            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def raise_for_status():
                pass

            @staticmethod
            def iter_content(chunk_size):
                del chunk_size
                yield b"x" * 2048

        with tempfile.TemporaryDirectory() as root:
            with (
                mock.patch.object(app, "APP_DIR", root),
                mock.patch.object(app.requests, "get", return_value=FakeResponse()),
            ):
                with self.assertRaisesRegex(RuntimeError, "trusted-sha256"):
                    app._download_gui_update_archive("https://example.invalid/update.zip", "3.1.0")

    def test_second_instance_requests_activation_without_a_restart_prompt(self) -> None:
        fake_app = object()
        with (
            mock.patch.object(app, "_try_acquire_single_instance_lock", return_value=(False, None, "already-running")),
            mock.patch.object(app, "_notify_existing_instance_to_activate", return_value=True) as notify,
        ):
            self.assertFalse(app._handle_existing_instance_before_start(fake_app))
        notify.assert_called_once()

    def test_second_instance_can_activate_a_window_that_has_never_been_shown(self) -> None:
        class FakeFunction:
            def __init__(self, result):
                self.result = result
                self.calls = []

            def __call__(self, *args):
                self.calls.append(args)
                return self.result

        class FakeKernel32:
            def __init__(self):
                self.OpenEventW = FakeFunction(9876)
                self.SetEvent = FakeFunction(True)
                self.CloseHandle = FakeFunction(True)

        kernel32 = FakeKernel32()

        def fake_windll(name, **_kwargs):
            if name == "kernel32":
                return kernel32
            raise AssertionError("FindWindow fallback must not be needed")

        with (
            mock.patch.object(app.sys, "platform", "win32"),
            mock.patch.object(app.ctypes, "WinDLL", side_effect=fake_windll),
        ):
            self.assertTrue(app._notify_existing_instance_to_activate(retries=1))

        self.assertEqual(
            [(0x0002, False, app.SINGLE_INSTANCE_ACTIVATE_EVENT_NAME)],
            kernel32.OpenEventW.calls,
        )
        self.assertEqual([(9876,)], kernel32.SetEvent.calls)
        self.assertEqual([(9876,)], kernel32.CloseHandle.calls)

    def test_external_restore_delegates_to_tray_restore(self) -> None:
        class FakeWindow:
            _external_restore_queued = True

            def __init__(self):
                self.tray_restore_calls = 0

            def show_from_tray(self):
                self.tray_restore_calls += 1

        window = FakeWindow()
        app.MainWindow._restore_from_external_activation(window)

        self.assertFalse(window._external_restore_queued)
        self.assertEqual(1, window.tray_restore_calls)

    def test_starting_hidden_does_not_force_creation_of_a_native_hwnd(self) -> None:
        source = Path(app.MainWindow.__module__.replace(".", os.sep))
        del source  # The class is assembled from fragments; inspect its constructor instead.
        import inspect

        constructor = inspect.getsource(app.MainWindow.__init__)
        self.assertNotIn("self.winId()", constructor)

    def test_update_check_stops_bypass_before_checking_core(self) -> None:
        checked = []
        with (
            mock.patch.object(app, "_is_winws_running_silent", side_effect=[True, True, False]),
            mock.patch.object(app, "_ensure_background_service") as ensure_service,
            mock.patch.object(app, "_force_stop_blockers") as stop_blockers,
            mock.patch.object(
                app,
                "_check_flowseal_update_async",
                side_effect=lambda *_args, **_kwargs: checked.append(True) or {"ok": True, "status": "up-to-date"},
            ),
        ):
            result = app._check_flowseal_update_with_winws_recovery()

        stop_blockers.assert_called_once()
        self.assertEqual([True], checked)
        self.assertTrue(result["bypass_stopped"])
        self.assertFalse(result["winws_reset"])

    def test_update_check_resets_and_retries_after_recoverable_error(self) -> None:
        with (
            mock.patch.object(app, "_is_winws_running_silent", return_value=False),
            mock.patch.object(app, "_force_stop_blockers") as stop_blockers,
            mock.patch.object(
                app,
                "_check_flowseal_update_async",
                side_effect=[
                    {"ok": False, "status": "offline", "error": "first attempt"},
                    {"ok": True, "status": "up-to-date"},
                ],
            ) as check,
        ):
            result = app._check_flowseal_update_with_winws_recovery()

        self.assertEqual(2, check.call_count)
        stop_blockers.assert_called_once()
        self.assertTrue(result["winws_reset"])
        self.assertTrue(result["update_retried"])

    def test_startup_list_sync_retries_transient_failure_and_keeps_cached_lists(self) -> None:
        emitted = []
        worker = app.ListsUpdateWorker("", "")
        worker.finished_sync.connect(emitted.append)
        app.APP_SHUTTING_DOWN.clear()
        try:
            with (
                mock.patch.object(app, "LISTS_STARTUP_RETRY_DELAYS_SECONDS", (0.0, 0.0)),
                mock.patch.object(
                    app,
                    "_sync_flowseal_lists",
                    side_effect=[
                        {"ok": False, "offline": True, "error": "network is initializing"},
                        {"ok": False, "offline": True, "error": "network is initializing"},
                        {"ok": True, "offline": False},
                    ],
                ) as sync,
                mock.patch.object(app, "_sync_ai_dns_if_enabled", return_value={"error": ""}),
            ):
                worker.run()
        finally:
            app.APP_SHUTTING_DOWN.clear()

        self.assertEqual(3, sync.call_count)
        self.assertEqual(1, len(emitted))
        self.assertTrue(emitted[0]["ok"])
        self.assertEqual(3, emitted[0]["startup_attempts"])
        self.assertFalse(emitted[0]["used_cached_lists"])

    def test_startup_list_sync_failure_does_not_open_a_network_warning(self) -> None:
        class FakeWindow:
            _lists_worker = object()
            _pending_toggle_state = None
            settings = object()

            @staticmethod
            def _set_lists_sync_ui_busy(_busy):
                pass

            @staticmethod
            def _maybe_offer_startup_gui_update(_result):
                return False

            @staticmethod
            def _run_pending_autostart_if_needed():
                pass

            @staticmethod
            def _resume_pending_toggle_if_ready():
                pass

            def _show_lists_sync_network_notice(self):
                self.warning_count += 1

        window = FakeWindow()
        window.warning_count = 0
        with (
            mock.patch.object(app, "_ensure_user_lists_initialized"),
            mock.patch.object(app, "_rebuild_runtime_lists"),
        ):
            app.MainWindow._on_lists_sync_finished(
                window,
                {"ok": False, "offline": True, "error": "transient startup failure", "gui_update": {}},
            )
        self.assertEqual(0, window.warning_count)

    def test_system_shutdown_quits_immediately_without_waiting_for_winws(self) -> None:
        class FakeApplication:
            def __init__(self):
                self.quit_called = False

            def quit(self):
                self.quit_called = True

        class FakeWindow:
            _exiting = False
            _system_shutdown_requested = True
            _adaptive_worker = None
            _auto_worker = None
            _bypass_toggle_worker = None
            _background_setup_worker = None
            tray = mock.Mock()

            def hide(self):
                self.hidden = True

        window = FakeWindow()
        fake_app = FakeApplication()
        app.APP_SHUTTING_DOWN.clear()
        try:
            with (
                mock.patch.object(app.QApplication, "instance", return_value=fake_app),
                mock.patch.object(app, "_force_stop_blockers") as stop,
                mock.patch.object(app._bypass_service, "close") as close_service,
                mock.patch.object(app.QTimer, "singleShot") as single_shot,
            ):
                app.MainWindow._shutdown_and_quit(window)
        finally:
            app.APP_SHUTTING_DOWN.clear()

        self.assertTrue(window._exiting)
        self.assertTrue(window.hidden)
        self.assertTrue(fake_app.quit_called)
        window.tray.hide.assert_called_once()
        close_service.assert_called_once()
        stop.assert_not_called()
        single_shot.assert_not_called()

    def test_stop_recovers_a_broken_service_pipe_before_reporting_failure(self) -> None:
        with (
            mock.patch.object(app._bypass_service, "stop", side_effect=[BrokenPipeError("pipe lost"), None]) as stop,
            mock.patch.object(app, "_wait_for_winws_exit", side_effect=[False, True]),
            mock.patch.object(app, "_ensure_background_service") as ensure,
        ):
            app._force_stop_blockers(r"C:\core", timeout=5)

        self.assertEqual(2, stop.call_count)
        ensure.assert_called_once_with(r"C:\core")

    def test_expected_update_stop_does_not_show_a_bypass_crash_popup(self) -> None:
        class FakeProcess:
            @staticmethod
            def poll():
                return 1

        class FakeWindow:
            process = FakeProcess()
            _bypass_toggle_busy = False
            _game_mode_restart_worker = None
            _exiting = False
            _suppress_bypass_exit_notification = True

            def __init__(self):
                self.visual_state = None
                self.status = ""
                self.tray_updates = 0

            @staticmethod
            def t(key):
                return key

            def _set_main_toggle_checked_visual(self, checked, animated=False):
                self.visual_state = (checked, animated)

            def update_tray_status(self):
                self.tray_updates += 1

        window = FakeWindow()
        window.status_lbl = mock.Mock()
        with mock.patch.object(app, "_show_centered_message") as show_error:
            app.MainWindow._refresh_bypass_process_state(window)

        self.assertIsNone(window.process)
        self.assertEqual((False, True), window.visual_state)
        self.assertFalse(window._suppress_bypass_exit_notification)
        window.status_lbl.setText.assert_called_once_with("Off")
        show_error.assert_not_called()

    def test_stop_worker_reports_success_after_background_cleanup(self) -> None:
        emitted: list[tuple[str, dict]] = []
        worker = app.BypassToggleWorker("stop", settings_path="test-settings.ini")
        worker.finished_bypass.connect(lambda action, result: emitted.append((action, result)))
        with (
            mock.patch.object(app, "_force_stop_blockers"),
            mock.patch.object(app, "_is_winws_running_silent", return_value=False),
            mock.patch.object(app, "_release_adaptive_profile_hosts_after_stop", return_value=""),
        ):
            worker.run()

        self.assertEqual(len(emitted), 1)
        self.assertEqual(emitted[0][0], "stop")
        self.assertTrue(emitted[0][1]["ok"])

    def test_stop_worker_preserves_running_state_when_access_is_denied(self) -> None:
        emitted = []
        worker = app.BypassToggleWorker("stop", settings_path="test-settings.ini")
        worker.finished_bypass.connect(lambda action, result: emitted.append(result))
        with (
            mock.patch.object(app, "_ensure_background_service"),
            mock.patch.object(app, "_force_stop_blockers", side_effect=PermissionError("Access denied")),
            mock.patch.object(app, "_is_winws_running_silent", return_value=True),
        ):
            worker.run()
        self.assertFalse(emitted[0]["ok"])
        self.assertTrue(emitted[0]["running"])
        self.assertIn("Access denied", emitted[0]["error"])

    def test_launcher_never_executes_a_bat_after_service_failure(self) -> None:
        with (
            mock.patch.object(app.APP_SHUTTING_DOWN, "is_set", return_value=False),
            mock.patch.object(app, "_build_game_mode_winws_command", return_value='"C:\\core\\bin\\winws.exe" --wf-tcp=443'),
            mock.patch.object(app._bypass_service, "start", side_effect=RuntimeError("UAC cancelled")),
            mock.patch.object(app.subprocess, "Popen") as popen,
        ):
            with self.assertRaisesRegex(RuntimeError, "UAC cancelled"):
                app._launch_profile_process_core("test.bat", r"C:\core")
        popen.assert_not_called()

    def test_adaptive_hosts_helper_keeps_ownership_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            script = Path(root) / "adaptive.bat"
            script.write_text(
                ":: ZAPRETGUI_ADAPTIVE_PROFILE=1\n"
                ":: ZAPRETGUI_ADAPTIVE_TELEGRAM_HOSTS=1\n",
                encoding="utf-8",
            )
            settings = QSettings(str(Path(root) / "settings.ini"), QSettings.Format.IniFormat)
            with (
                mock.patch.object(app, "_read_hosts_file_strict", return_value=""),
                mock.patch.object(app, "_apply_flowseal_telegram_hosts", return_value=True) as apply_hosts,
            ):
                self.assertTrue(app._prepare_adaptive_profile_hosts_for_launch(str(script), settings))
            apply_hosts.assert_called_once_with(True, settings)


if __name__ == "__main__":
    unittest.main()
