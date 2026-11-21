import os
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from urllib.parse import parse_qs, urlsplit

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import EzUnBlock as app
from tg_ws_proxy_vendor.proxy import tg_ws_proxy
from zapret_gui.telegram_proxy import TelegramProxyController, TelegramProxyOptions


class TelegramSettingsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = app.QApplication.instance() or app.QApplication([])

    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.settings = app.QSettings(
            str(Path(directory.name) / "settings.ini"), app.QSettings.Format.IniFormat,
        )
        self.settings.setValue(app.TELEGRAM_MODE_PROXY_SECRET_KEY, "a1" * 16)
        self.settings.sync()

    def test_form_saves_values_and_reset_restores_legacy_secret(self):
        owner = app.QWidget()
        owner.lang = "ru"
        owner.settings = self.settings
        owner.apply_telegram_proxy_settings = mock.Mock(
            side_effect=lambda options, action: app._save_telegram_proxy_options(self.settings, options),
        )
        dialog = app.TelegramModeSettingsDialog(owner)
        self.assertEqual(dialog.secret.text(), "a1" * 16)
        dialog.port.setValue(2443)
        dialog.host.setText("0.0.0.0")
        dialog.secret.setText("b2" * 16)
        dialog.dc_rules.setPlainText("203:91.105.192.100")
        dialog.cf_enabled.setChecked(False)
        dialog.verbose.setChecked(True)
        dialog.pool_size.setValue(0)
        dialog.save_btn.click()
        saved = app._get_telegram_proxy_options(self.settings)
        self.assertEqual((saved.host, saved.port, saved.secret), ("0.0.0.0", 2443, "b2" * 16))
        self.assertEqual(saved.dc_rules, ("203:91.105.192.100",))
        self.assertFalse(saved.cf_enabled)
        self.assertTrue(saved.verbose)
        self.assertEqual(saved.pool_size, 0)
        self.assertEqual(parse_qs(urlsplit(saved.link()).query), {
            "server": ["127.0.0.1"], "port": ["2443"], "secret": ["dd" + saved.secret],
        })
        dialog.reset_btn.click()
        self.assertEqual(app._get_telegram_proxy_options(self.settings), TelegramProxyOptions(secret="a1" * 16))

    def test_saved_settings_reach_runtime_and_failed_restart_keeps_previous_options(self):
        old = app._get_telegram_proxy_options(self.settings)
        options = replace(
            old, port=33443, dc_rules=("203:91.105.192.100",),
            custom_cf=True, cf_domains=("relay.example",),
            custom_worker=True, worker_domains=("worker.example",),
            disable_tls=True, buffer_kib=512, pool_size=7,
        )
        controller = mock.Mock()
        worker = app.TelegramModeWorker("restart", controller, options=options)
        with (
            mock.patch.object(app, "SETTINGS_FILE", self.settings.fileName()),
            mock.patch.object(app, "_apply_telegram_runtime_files") as lists,
            mock.patch.object(app, "_apply_flowseal_telegram_hosts") as hosts,
        ):
            app._set_telegram_mode_enabled(True, self.settings)
            worker.run()
            controller.restart.assert_called_once_with(options, cancelled=mock.ANY)
            self.settings.sync()
            self.assertEqual(app._get_telegram_proxy_options(self.settings), options)
            configured = TelegramProxyController()
            configured._options = options
            with mock.patch("zapret_gui.telegram_proxy.proxy_config", new=mock.Mock()) as config:
                configured._configure_flowseal_proxy()
                self.assertEqual(config.dc_redirects, {203: "91.105.192.100"})
                self.assertEqual(config.cfproxy_user_domains, ["relay.example"])
                self.assertEqual(config.cfproxy_worker_domains, ["worker.example"])
                self.assertTrue(config.disable_secure)
                self.assertEqual(config.buffer_size, 512 * 1024)
                self.assertEqual(config.pool_size, 7)
            controller.restart.side_effect = OSError("address already in use")
            app.TelegramModeWorker("restart", controller, options=old).run()
            self.settings.sync()
            self.assertEqual(app._get_telegram_proxy_options(self.settings), options)
            self.assertTrue(app._is_telegram_mode_enabled(self.settings))
            lists.assert_not_called()
            hosts.assert_not_called()

    def test_open_in_telegram_restarts_only_if_options_changed_or_proxy_stopped(self):
        options = app._get_telegram_proxy_options(self.settings)
        proxy = mock.Mock(options=options)
        window = SimpleNamespace(
            _exiting=False, _telegram_mode_busy=False, _telegram_mode_worker=None,
            telegram_proxy=proxy, settings=self.settings,
            _start_telegram_mode_worker=mock.Mock(), _open_telegram_proxy_link=mock.Mock(return_value=True),
        )
        apply = app.MainWindow.apply_telegram_proxy_settings
        self.assertFalse(apply(window, options, "open"))
        window._open_telegram_proxy_link.assert_called_once()
        window._start_telegram_mode_worker.assert_not_called()

        changed = replace(options, port=2443)
        self.assertTrue(apply(window, changed, "open"))
        window._start_telegram_mode_worker.assert_called_once_with("restart", options=changed, open_link=True)
        # The old link isn't opened while the new listener is still starting.
        window._open_telegram_proxy_link.assert_called_once()
        proxy.is_running.return_value = False
        self.assertTrue(apply(window, options, "open"))
        window._start_telegram_mode_worker.assert_called_with("restart", options=options, open_link=True)

    def test_proxy_restores_real_loopback_listener_on_occupied_port(self):
        with socket.socket() as address:
            address.bind(("127.0.0.1", 0))
            port = address.getsockname()[1]
        options = TelegramProxyOptions(port=port, cf_enabled=False, dc_rules=())
        proxy = TelegramProxyController()
        with socket.socket() as occupied:
            occupied.bind(("127.0.0.1", 0))
            occupied.listen()
            with mock.patch.object(tg_ws_proxy, "start_cfproxy_domain_refresh") as refresh:
                proxy.start(options=options)
                try:
                    with self.assertRaises(app.TelegramProxyError):
                        proxy.restart(replace(options, port=occupied.getsockname()[1]))
                    self.assertEqual(proxy.options, options)
                    self.assertTrue(proxy.is_running())
                    with socket.create_connection(("127.0.0.1", port), timeout=2):
                        pass
                finally:
                    proxy.stop()
                refresh.assert_not_called()


class UpdaterEnvironmentTests(unittest.TestCase):
    def test_launcher_excludes_old_onefile_environment_without_mutating_gui(self):
        original = {
            "_PYI_APPLICATION_HOME_DIR": r"C:\Temp\_MEIold",
            "_pyi_parent_process_level": "1",
            "_MEIPASS2": "obsolete",
            "APPDATA": r"C:\Users\Test\AppData\Roaming",
        }
        with (
            mock.patch.dict(os.environ, original, clear=True),
            mock.patch.object(app.subprocess, "Popen") as spawn,
        ):
            app._launch_gui_updater_process(["powershell.exe"], r"C:\Test")
            self.assertEqual(dict(os.environ), {key.upper(): value for key, value in original.items()})
        env = spawn.call_args.kwargs["env"]
        self.assertEqual(env, {"APPDATA": original["APPDATA"], "PYINSTALLER_RESET_ENVIRONMENT": "1"})

    def test_script_cleans_legacy_environment_before_launch_or_rollback(self):
        with tempfile.TemporaryDirectory() as root, mock.patch.object(app, "APP_DIR", root):
            script = Path(app._write_gui_update_script()).read_text(encoding="utf-8")
        clean = script.index('$env:PYINSTALLER_RESET_ENVIRONMENT = "1"')
        self.assertIn('"_PYI_*"', script[:clean])
        self.assertIn('"_MEIPASS2"', script[:clean])
        self.assertLess(clean, script.index("Start-Process -FilePath $OldExePath"))
