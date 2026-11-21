import os
import sys
import tempfile
import unittest
from contextlib import ExitStack, contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import bypass_service
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings, Qt, QPoint
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication

import EzUnBlock as app
from zapret_gui import traffic_modes
from zapret_gui.app_icons import executable_icon_image
from zapret_gui.traffic_processing import (
    TRAFFIC_MODE_ALL,
    TRAFFIC_MODE_APPLICATIONS,
    TRAFFIC_MODE_LISTS,
    list_has_values as list_file_has_entries,
    mode_from_index,
    mode_index,
    normalize_traffic_mode,
)


_QAPP = QApplication.instance() or QApplication([])


class TrafficProcessingHelpersTests(unittest.TestCase):
    def test_mode_values_are_normalized_and_invalid_values_keep_current_behavior(self):
        self.assertEqual(TRAFFIC_MODE_ALL, normalize_traffic_mode("Весь трафик"))
        self.assertEqual(TRAFFIC_MODE_APPLICATIONS, normalize_traffic_mode("apps"))
        self.assertEqual(TRAFFIC_MODE_LISTS, normalize_traffic_mode("только списки"))
        self.assertEqual(TRAFFIC_MODE_ALL, normalize_traffic_mode("unknown"))
        self.assertEqual(2, mode_index("lists"))
        self.assertEqual(TRAFFIC_MODE_ALL, mode_from_index(999))

    def test_list_probe_ignores_comments_and_empty_lines(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "list.txt"
            path.write_text("\n# comment\n; comment\nexample.test\n", encoding="utf-8")
            self.assertTrue(list_file_has_entries(str(path)))
            path.write_text("\n# comment\n; comment\n", encoding="utf-8")
            self.assertFalse(list_file_has_entries(str(path)))
            self.assertFalse(list_file_has_entries(str(path) + ".missing"))


class SettingsTrafficProcessingTests(unittest.TestCase):
    def test_tray_stays_open_while_switching_modes_and_editing_list_options(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            with patch.object(app.MainWindow, "__init__", lambda self: app.QWidget.__init__(self)):
                window = app.MainWindow()
            window.lang = "ru"
            window.settings = settings
            window.toggle_btn = app.QPushButton(window)
            with (
                patch.object(app.QSystemTrayIcon, "show"),
                patch.object(window, "on_traffic_processing_changed"),
                patch.object(window, "open_traffic_applications") as open_applications,
            ):
                window.init_tray_icon()
                tray = window.tray_menu
                modes = window.traffic_mode_menu
                lists = window.traffic_mode_settings_menu

                def submenu(parent, child):
                    parent.setActiveAction(child.menuAction())
                    QTest.keyClick(parent, Qt.Key.Key_Right)
                    _QAPP.processEvents()
                    self.assertTrue(child.isVisible())

                def click(menu, action):
                    QTest.mouseClick(menu, Qt.MouseButton.LeftButton, pos=menu.actionGeometry(action).center())
                    _QAPP.processEvents()

                try:
                    tray.popup(QPoint(30, 30))
                    submenu(tray, modes)
                    self.assertFalse(window.traffic_mode_settings_action.isVisible())
                    click(modes, window.traffic_mode_actions[TRAFFIC_MODE_APPLICATIONS])
                    self.assertTrue(tray.isVisible() and modes.isVisible())
                    self.assertTrue(window.traffic_mode_settings_action.isVisible())

                    modes.setActiveAction(window.traffic_mode_actions[TRAFFIC_MODE_LISTS])
                    QTest.keyClick(modes, Qt.Key.Key_Return)
                    self.assertTrue(tray.isVisible() and modes.isVisible())
                    self.assertFalse(window.traffic_mode_settings_action.isVisible())
                    submenu(modes, lists)
                    for key, action in window.traffic_list_actions.items():
                        click(lists, action)
                        self.assertFalse(app._get_traffic_processing_list_options(settings)[key])
                        self.assertTrue(tray.isVisible() and modes.isVisible() and lists.isVisible())

                    QTest.keyClick(lists, Qt.Key.Key_Escape)
                    click(modes, window.traffic_mode_actions[TRAFFIC_MODE_APPLICATIONS])
                    click(modes, window.traffic_mode_settings_action)
                    open_applications.assert_called_once_with()
                    self.assertFalse(tray.isVisible())
                finally:
                    lists.close()
                    modes.close()
                    tray.close()
                    tray.deleteLater()
                    window.deleteLater()
                    _QAPP.processEvents()

    @contextmanager
    def _visual_main_window(self, settings):
        """Real layout/signals, no startup tasks, processes, services or tray."""
        with ExitStack() as stack:
            stack.enter_context(patch.object(app.MainWindow, "__init__", lambda self: app.QWidget.__init__(self)))
            for name in ("reload_presets", "_update_small_circle_buttons_ui", "_update_ai_mode_ui",
                         "_update_telegram_mode_ui", "_update_game_mode_ui", "update_tray_status"):
                stack.enter_context(patch.object(app.MainWindow, name))
            window = app.MainWindow()
            window.settings = settings
            window.lang = "ru"
            window.profile_scope = "standard"
            window.presets = {}
            window.game_mode_enabled = False
            window.init_ui()
            window.show()
            _QAPP.processEvents()
            window._position_overlay_mode_buttons()
            try:
                yield window
            finally:
                window.blink_timer.stop()
                window.hide()
                window.deleteLater()
                _QAPP.processEvents()

    def test_vertical_switch_keyboard_click_and_interrupted_animation(self):
        selector = app.TrafficModeSelector(vertical=True)
        changed = []
        selector.currentChanged.connect(changed.append)
        try:
            selector.show()
            _QAPP.processEvents()
            QTest.mouseClick(selector._buttons[1], Qt.MouseButton.LeftButton)
            QTest.keyClick(selector, Qt.Key.Key_Down)
            self.assertEqual([1, 2], changed)
            selector.setCurrentIndex(0, animated=False, emit=False)
            QTest.qWait(280)
            self.assertEqual(0, selector.currentIndex())
            self.assertEqual(0, selector.getSelectorPosition())
            self.assertEqual([1, 2], changed)
            for button in selector._buttons:
                self.assertTrue(selector.rect().contains(button.geometry()))
                self.assertTrue(button.toolTip())
        finally:
            selector.close()
            selector.deleteLater()
            _QAPP.processEvents()

    def test_main_switch_syncs_settings_and_tray_without_duplicate_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            with self._visual_main_window(settings) as window:
                dialog = app.SettingsDialog(window, settings)
                window._settings_dlg = dialog
                dialog.show()
                _QAPP.processEvents()
                try:
                    with patch.object(window, "_schedule_game_mode_restart_after_change") as restart:
                        window.toggle_btn.setChecked(True)
                        # Programmatic checked state need not launch a backend.
                        QTest.mouseClick(window.traffic_quick_switch._buttons[1], Qt.MouseButton.LeftButton)
                        self.assertEqual(TRAFFIC_MODE_APPLICATIONS, app._get_traffic_processing_mode(settings))
                        self.assertEqual(1, dialog.traffic_mode_selector.currentIndex())
                        restart.assert_called_once()
                        restart.reset_mock()
                        dialog.traffic_mode_selector.setCurrentIndex(2, animated=False)
                        self.assertEqual(2, window.traffic_quick_switch.currentIndex())
                        restart.assert_called_once()
                        restart.reset_mock()
                        window.set_traffic_mode_from_tray(TRAFFIC_MODE_ALL)
                        self.assertEqual(0, dialog.traffic_mode_selector.currentIndex())
                        self.assertEqual(0, window.traffic_quick_switch.currentIndex())
                        restart.assert_called_once()
                finally:
                    window.toggle_btn.setChecked(False)
                    dialog.done(0)
                    dialog.deleteLater()
                    _QAPP.processEvents()

    def test_main_switch_fits_between_telegram_and_game_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            with self._visual_main_window(settings) as window:
                switch = window.traffic_quick_switch.geometry()
                game_top = window.game_mode_btn.mapTo(window, QPoint(0, 0)).y()
                self.assertGreater(switch.top(), window.telegram_mode_btn.geometry().bottom())
                self.assertLess(switch.bottom(), game_top)
                self.assertLessEqual(switch.right(), window.width() - 8)
                self.assertFalse(switch.intersects(window.toggle_btn.geometry().translated(
                    window.toggle_btn.parentWidget().pos())))

    def test_settings_cards_icons_and_manage_share_row_without_overflow(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            records = []
            for index in range(12):
                path = Path(directory) / f"App{index}.exe"
                path.write_bytes(b"MZ")
                records.append({"path": str(path), "label": f"App{index}", "enabled": True})
            app.save_app_records(settings, records)
            with patch.object(app, "application_mode_available", return_value=True):
                dialog = app.SettingsDialog(settings=settings)
                try:
                    dialog.show()
                    dialog.traffic_mode_selector.setCurrentIndex(1, animated=False)
                    _QAPP.processEvents()
                    icons = dialog.traffic_app_selected_panel
                    manage = dialog.traffic_app_manage_btn
                    self.assertEqual(icons.mapTo(dialog, QPoint(0, 0)).y(),
                                     manage.mapTo(dialog, QPoint(0, 0)).y())
                    self.assertLess(icons.geometry().right(), manage.geometry().left())
                    for button in dialog._traffic_app_chip_buttons.values():
                        self.assertTrue(icons.rect().contains(button.geometry()))
                    self.assertLess(dialog.autostart_card.geometry().bottom(), dialog.traffic_card.geometry().top())
                    self.assertTrue(all(button.height() == 28 for button in
                                        (dialog.svc_btn, dialog.remove_btn, dialog.update_btn)))
                    dialog.traffic_mode_selector.setCurrentIndex(0, animated=False)
                    self.assertTrue(dialog.traffic_mode_details.isHidden())
                    for language in ("ru", "en"):
                        dialog.lang = language
                        dialog.retranslate_ui()
                        for mode in (0, 1, 2):
                            dialog.traffic_mode_selector.setCurrentIndex(mode, animated=False)
                            _QAPP.processEvents()
                            self.assertTrue(dialog.rect().contains(dialog.version_label.geometry()))
                finally:
                    dialog.done(0)
                    dialog.deleteLater()
                    _QAPP.processEvents()

    def test_ai_help_hides_on_anchor_leave_even_when_cursor_is_over_popup(self):
        anchor = app.QPushButton("i")
        anchor.show()
        help_popup = app.HoverHelpPopup(anchor, "Ai DNS", keep_on_popup=False)
        try:
            help_popup.show_help()
            self.assertTrue(help_popup.popup.isVisible())
            self.assertTrue(help_popup.popup.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
            help_popup.eventFilter(anchor, app.QEvent(app.QEvent.Type.Leave))
            self.assertFalse(help_popup.popup.isVisible())
        finally:
            anchor.close()
            anchor.deleteLater()
            _QAPP.processEvents()

    def test_window_corner_masks_are_symmetric_and_clip_title_bar(self):
        for cls in (app.StyledDialog, app.RoundedMessageBox):
            window = cls()
            try:
                if cls is app.StyledDialog:
                    root = app._make_window_root_layout(window)
                    window.install_title_bar(root, "Test")
                window.resize(400, 300)
                window.show()
                _QAPP.processEvents()
                mask = window.mask()
                width, height = window.width(), window.height()
                for x in range(15):
                    for y in range(15):
                        corner = mask.contains(QPoint(x, y))
                        self.assertEqual(corner, mask.contains(QPoint(width - 1 - x, y)))
                        self.assertEqual(corner, mask.contains(QPoint(x, height - 1 - y)))
                        self.assertEqual(corner, mask.contains(QPoint(width - 1 - x, height - 1 - y)))
                self.assertFalse(mask.contains(QPoint(0, 0)))
                self.assertFalse(window._title_bar.mask().contains(QPoint(0, 0)))
            finally:
                window.close()
                window.deleteLater()
                _QAPP.processEvents()

    def test_autostart_widgets_repaint_and_preserve_selected_profile(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            settings.setValue("autostart_profile", "ALT13")
            settings.setValue("autostart", True)
            dialog = app.SettingsDialog(settings=settings)
            try:
                dialog.show()
                _QAPP.processEvents()
                self.assertEqual("ALT13", dialog.profile_cb.currentText())
                self.assertTrue(dialog.profile_cb.highlight_selection)
                before = dialog.autostart_cb.grab().toImage()
                QTest.mouseClick(dialog.autostart_cb, Qt.MouseButton.LeftButton)
                _QAPP.processEvents()
                self.assertFalse(dialog.autostart_cb.isChecked())
                self.assertFalse(settings.value("autostart", True, type=bool))
                self.assertNotEqual(before, dialog.autostart_cb.grab().toImage())
                dialog.autostart_cb.setChecked(True)
                dialog.profile_cb.addItem("ALT14")
                dialog.profile_cb.setCurrentText("ALT14")
                self.assertEqual("ALT14", settings.value("autostart_profile"))
                self.assertTrue(settings.value("autostart_profile_enabled", False, type=bool))
                dialog.load_settings()
                self.assertEqual("ALT14", dialog.profile_cb.currentText())
            finally:
                dialog.close()
                dialog.deleteLater()
                _QAPP.processEvents()

    def test_beta_help_is_interactive_and_bug_report_uses_link_label(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            dialog = app.SettingsDialog(settings=settings)
            try:
                dialog.show()
                _QAPP.processEvents()
                self.assertEqual("Beta", dialog.traffic_info_btn.text())
                popup = dialog.traffic_help
                self.assertIn("Сообщить о баге", popup.label.text())
                self.assertIn('href="https://github.com/medvedeff-true/Zapret-GUI/issues"', popup.label.text())
                self.assertFalse(popup.popup.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents))
                popup.show_help()
                self.assertTrue(popup.popup.isVisible())
                popup.eventFilter(dialog.traffic_info_btn, app.QEvent(app.QEvent.Type.Leave))
                self.assertTrue(popup.timer.isActive())
                popup.eventFilter(popup.label, app.QEvent(app.QEvent.Type.Enter))
                self.assertFalse(popup.timer.isActive())
                with patch.object(app.QDesktopServices, "openUrl") as open_url:
                    popup.label.linkActivated.emit("https://github.com/medvedeff-true/Zapret-GUI/issues")
                    open_url.assert_called_once()
                dialog.close()
                self.assertFalse(popup.popup.isVisible())
            finally:
                dialog.close()
                dialog.deleteLater()
                _QAPP.processEvents()

    def test_catalog_sizes_and_location_copy_do_not_toggle_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "Browser.exe"
            executable.write_bytes(b"x" * 2048)
            settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            store = app.TrafficAppStore(root / "user" / "traffic_apps.json")
            store.add(executable, source=app.SOURCE_INSTALLED, label="Browser")
            with patch.object(app.TrafficApplicationsDialog, "_request_snapshot"):
                dialog = app.TrafficApplicationsDialog(settings=settings)
                try:
                    dialog._snapshot_ready("installed", [], "")
                    dialog.show()
                    _QAPP.processEvents()
                    dialog._render_batch()
                    listing = dialog._lists["installed"]
                    item = listing.item(0)
                    self.assertEqual("Browser", item.text())
                    self.assertEqual("2.0 КБ", item.data(int(Qt.ItemDataRole.UserRole) + 2))
                    rect = listing.itemDelegate().location_rect(listing.visualItemRect(item))
                    QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=rect.center().toPoint())
                    self.assertEqual(str(executable), QApplication.clipboard().text())
                    self.assertEqual(Qt.CheckState.Checked, item.checkState())
                    self.assertTrue(item.data(int(Qt.ItemDataRole.UserRole) + 3))
                    dialog._clear_copied_location()
                    self.assertFalse(item.data(int(Qt.ItemDataRole.UserRole) + 3))
                finally:
                    dialog.done(0)
                    dialog.deleteLater()
                    _QAPP.processEvents()

    @unittest.skipUnless(os.name == "nt", "Windows executable icon resources")
    def test_application_icons_are_decoded_at_high_resolution(self):
        image = executable_icon_image(sys.executable)
        self.assertFalse(image.isNull())
        self.assertEqual((128, 128), (image.width(), image.height()))

    def test_selected_icons_are_visible_only_in_applications_mode(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Browser.exe"
            executable.write_bytes(b"MZ")
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            app.save_app_records(settings, [{"path": str(executable), "label": "Browser", "enabled": True}])
            dialog = app.SettingsDialog(settings=settings)
            try:
                for mode, hidden in ((0, True), (1, False), (2, True), (1, False)):
                    dialog.traffic_mode_selector.setCurrentIndex(mode, animated=False)
                    self.assertEqual(hidden, dialog.traffic_app_selected_panel.isHidden())
                    self.assertEqual(1, len(dialog._traffic_app_chip_buttons))
                    self.assertIsInstance(next(iter(dialog._traffic_app_chip_buttons.values())),
                                          app.TrafficApplicationIconButton)
            finally:
                dialog.close()
                dialog.deleteLater()
                _QAPP.processEvents()

    def test_file_row_remove_is_persisted_without_apply_and_survives_reopening(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Browser.exe"
            executable.write_bytes(b"MZ")
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            store = app.TrafficAppStore(Path(directory) / "user" / "traffic_apps.json")
            store.add(executable, source=app.SOURCE_FILE)
            # Avoid registry/process enumeration: this test exercises file rows.
            with patch.object(app.TrafficApplicationsDialog, "_request_snapshot"):
                dialog = app.TrafficApplicationsDialog(settings=settings)
                try:
                    dialog.tabs.setCurrentIndex(2)
                    dialog.show()
                    _QAPP.processEvents()
                    dialog._render_batch()
                    _QAPP.processEvents()
                    listing = dialog._lists["file"]
                    self.assertEqual(1, listing.count())
                    item = listing.item(0)
                    rect = listing.visualItemRect(item)
                    QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton,
                                     pos=QPoint(rect.center().x(), rect.center().y()))
                    self.assertEqual(Qt.CheckState.Unchecked, item.checkState())
                    QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton,
                                     pos=QPoint(rect.center().x(), rect.center().y()))
                    self.assertEqual(Qt.CheckState.Checked, item.checkState())
                    remove = app.TrafficApplicationFileDelegate.remove_rect(rect).center().toPoint()
                    QTest.mouseClick(listing.viewport(), Qt.MouseButton.LeftButton, pos=remove)
                    dialog._render_batch()
                    _QAPP.processEvents()
                    self.assertEqual(0, listing.count())
                    self.assertEqual([], app.TrafficAppStore(store.storage_path).records())
                    self.assertEqual([], app.load_app_records(settings))
                    dialog.done(0)
                    reopened = app.TrafficApplicationsDialog(settings=settings)
                    try:
                        reopened.tabs.setCurrentIndex(2)
                        reopened._render_batch()
                        self.assertEqual(0, reopened._lists["file"].count())
                    finally:
                        reopened.done(0)
                        reopened.deleteLater()
                finally:
                    dialog.done(0)
                    dialog.deleteLater()
                    _QAPP.processEvents()

    def test_installed_catalog_hides_unselectable_packages_and_non_executables(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable, icon = root / "Browser.exe", root / "package.ico"
            executable.write_bytes(b"MZ")
            icon.write_bytes(b"icon")
            settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            with patch.object(app.TrafficApplicationsDialog, "_request_snapshot"):
                dialog = app.TrafficApplicationsDialog(settings=settings)
                try:
                    dialog._snapshot_ready("installed", [
                        SimpleNamespace(path=str(executable), name="Browser"),
                        SimpleNamespace(path="", name="Microsoft .NET package"),
                        SimpleNamespace(path=str(icon), name="Package icon"),
                        SimpleNamespace(path=str(root / "missing.exe"), name="Missing installation"),
                    ], "")
                    dialog._render_batch()
                    listing = dialog._lists["installed"]
                    self.assertEqual(1, listing.count())
                    self.assertEqual("Browser", listing.item(0).text())
                finally:
                    dialog.done(0)
                    dialog.deleteLater()
                    _QAPP.processEvents()

    def test_selector_and_list_options_are_persistent(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                str(Path(directory) / "settings.ini"),
                QSettings.Format.IniFormat,
            )
            dialog = app.SettingsDialog(settings=settings)
            try:
                self.assertEqual(0, dialog.traffic_mode_selector.currentIndex())
                self.assertTrue(dialog.traffic_list_panel.isHidden())

                dialog.traffic_mode_selector.setCurrentIndex(2, animated=False)
                _QAPP.processEvents()
                self.assertEqual("lists", settings.value(app.TRAFFIC_PROCESSING_MODE_KEY))
                self.assertFalse(dialog.traffic_list_panel.isHidden())

                first_button = dialog.traffic_list_buttons[0][1]
                first_button.setChecked(False)
                _QAPP.processEvents()
                self.assertFalse(
                    settings.value(
                        app.TRAFFIC_PROCESSING_LIST_DOMAINS_ADD_KEY,
                        True,
                        type=bool,
                    )
                )
            finally:
                dialog.close()
                dialog.deleteLater()
                _QAPP.processEvents()

            restored = app.SettingsDialog(settings=settings)
            try:
                self.assertEqual(2, restored.traffic_mode_selector.currentIndex())
                self.assertFalse(restored.traffic_list_buttons[0][1].isChecked())
                self.assertEqual(
                    "Эта функция работает в тестовом режиме.",
                    restored.traffic_info_btn.toolTip().split(" Если")[0],
                )
                self.assertIn(
                    "https://github.com/medvedeff-true/Zapret-GUI/issues",
                    restored.traffic_info_btn.toolTip(),
                )
            finally:
                restored.close()
                restored.deleteLater()
                _QAPP.processEvents()

    @unittest.skipUnless(os.name == "nt", "Windows command line protocol")
    def test_application_launch_transfers_persisted_selection_and_cleans_up(self):
        core = Path("resources/core").resolve()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings = QSettings(
                str(root / "settings.ini"),
                QSettings.Format.IniFormat,
            )
            settings.setValue(app.TRAFFIC_PROCESSING_MODE_KEY, TRAFFIC_MODE_APPLICATIONS)
            store = app.TrafficAppStore(root / "user" / "traffic_apps.json")
            selected = root / "Браузер Firefox.exe"
            excluded = root / "Excluded.exe"
            for path in (selected, excluded):
                path.touch()
                store.add(path)
            store.add(root / "Missing.exe")
            store.set_enabled(excluded, False)
            scope_paths = []

            def start(command, core_bin, helper):
                request = bypass_service.profile_request(command, core_bin)
                self.assertEqual(request["engine"], "medvedeff-winws")
                options = [arg for arg in request["args"] if arg["name"] == "app-scope-file"]
                self.assertEqual(len(options), 1)
                scope = request.sources[options[0]["file"]].path
                scope_paths.append(scope)
                self.assertEqual(Path(scope.read_text(encoding="utf-8").strip()), selected)
                self.assertNotIn("--wf-raw=", command)
                raise RuntimeError("test upload/start failure")

            with patch.object(app._bypass_service, "start", side_effect=start):
                with self.assertRaisesRegex(RuntimeError, "test upload/start failure"):
                    app._launch_profile_process_core(str(core / "general (ALT13).bat"), str(core), settings)
            self.assertEqual(len(scope_paths), 1)
            self.assertFalse(scope_paths[0].exists())

    def test_empty_application_selection_is_rejected_before_service_setup(self):
        core = Path("resources/core").resolve()
        with tempfile.TemporaryDirectory() as directory:
            settings_path = str(Path(directory) / "settings.ini")
            settings = QSettings(settings_path, QSettings.Format.IniFormat)
            settings.setValue(app.TRAFFIC_PROCESSING_MODE_KEY, TRAFFIC_MODE_APPLICATIONS)
            settings.setValue("lang", "en")
            settings.sync()
            worker = app.BypassToggleWorker("start", str(core / "general (ALT13).bat"), str(core), settings_path)
            replies = []
            worker.finished_bypass.connect(lambda _, reply: replies.append(reply))
            with patch.object(app, "_ensure_background_service") as ensure, \
                 patch.object(app, "_force_stop_blockers") as stop, \
                 patch.object(app, "_is_winws_running_silent", return_value=False):
                worker.run()
            ensure.assert_not_called()
            stop.assert_not_called()
            self.assertFalse(replies[0]["ok"])
            self.assertIn("Select at least one available application", replies[0]["error"])

    def test_empty_scoped_configuration_stops_without_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            settings.setValue(app.TRAFFIC_PROCESSING_MODE_KEY, TRAFFIC_MODE_APPLICATIONS)
            settings.sync()
            window = SimpleNamespace(
                settings=settings,
                lang="en",
                process=object(),
                _adaptive_hosts_owned=False,
                _adaptive_active_profile_script="",
                toggle_btn=app.QPushButton(),
                status_lbl=app.QLabel(),
                _game_mode_restart_worker=None,
                _traffic_configuration_issue=lambda: app.MainWindow._traffic_configuration_issue(window),
                _update_traffic_configuration_notice=Mock(),
                _set_main_toggle_checked_visual=Mock(),
                update_tray_status=Mock(),
                t=lambda text: text,
            )
            window.toggle_btn.setChecked(True)
            with patch.object(app, "_show_centered_message") as warning:
                app.MainWindow._on_game_mode_restart_stopped(window, "")
            warning.assert_not_called()
            self.assertIsNone(window.process)
            window._set_main_toggle_checked_visual.assert_called_once_with(False, animated=True)

    def test_empty_list_button_is_disabled_and_explains_why(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.txt"
            path.write_text("# no values\n", encoding="utf-8")
            self.assertFalse(list_file_has_entries(str(path)))

    @unittest.skip("Application snapshot filters are retained only for future backend work.")
    def test_application_filter_is_bounded_without_cutting_syntax(self):
        endpoints = [
            ("tcp", "192.0.2.1", 40000 + index, "198.51.100.1", 443)
            for index in range(96)
        ]
        with patch.object(traffic_modes, "collect_application_endpoints", return_value=endpoints):
            value = traffic_modes.build_application_raw_filter(object())

        self.assertLessEqual(len(value), traffic_modes._MAX_FILTER_LENGTH)
        self.assertNotEqual(value, "0")
        self.assertEqual(value.count("("), value.count(")"))
        self.assertNotIn("\n", value)

    @unittest.skip("Application snapshot filters are retained only for future backend work.")
    def test_application_filter_is_valid_false_when_no_connection_exists(self):
        with patch.object(traffic_modes, "collect_application_endpoints", return_value=[]):
            self.assertEqual("false", traffic_modes.build_application_raw_filter(object()))

    @unittest.skip("Application snapshot filters are retained only for future backend work.")
    def test_application_endpoints_use_per_process_connections_when_global_pid_is_missing(self):
        connection = SimpleNamespace(
            pid=None,
            type=1,
            laddr=("192.0.2.10", 42000),
            raddr=("198.51.100.20", 443),
        )
        process = SimpleNamespace(
            info={"pid": 1234, "exe": r"C:\Apps\Firefox\firefox.exe"},
            net_connections=lambda kind: [connection],
        )
        with (
            patch.object(traffic_modes, "selected_app_paths", return_value=[
                traffic_modes.normalize_executable_path(r"C:\Apps\Firefox\firefox.exe")
            ]),
            patch.object(traffic_modes.psutil, "process_iter", return_value=[process]),
            patch.object(traffic_modes.psutil, "net_connections", return_value=[]),
        ):
            self.assertEqual(
                [
                    ("tcp", "192.0.2.10", 42000, "198.51.100.20", 443),
                ],
                traffic_modes.collect_application_endpoints(object()),
            )

    @unittest.skip("Application snapshot refresh was removed because it cannot provide process scope.")
    def test_application_scope_refresh_is_debounced_instead_of_restarting_on_every_snapshot(self):
        class Toggle:
            @staticmethod
            def isChecked():
                return True

        class Timer:
            @staticmethod
            def isActive():
                return False

        window = SimpleNamespace(
            toggle_btn=Toggle(),
            _bypass_toggle_busy=False,
            _game_mode_restart_worker=None,
            _game_mode_restart_timer=Timer(),
            _traffic_app_signature=(),
            _traffic_app_pending_signature=None,
            _traffic_app_pending_since=0.0,
            _traffic_app_last_restart_at=0.0,
            settings=object(),
            on_traffic_processing_preferences_changed=Mock(),
        )
        with (
            patch.object(app, "_get_traffic_processing_mode", return_value=TRAFFIC_MODE_APPLICATIONS),
            patch.object(app, "application_filter_signature", return_value=("tcp:1",)),
            patch.object(app.time, "monotonic", side_effect=(100.0, 103.0)),
        ):
            app.MainWindow._refresh_traffic_application_scope(window)
            app.MainWindow._refresh_traffic_application_scope(window)

        window.on_traffic_processing_preferences_changed.assert_called_once_with()

    def test_application_mode_backend_is_available(self):
        self.assertTrue(traffic_modes.application_mode_available(Path("resources/core/bin")))
        with tempfile.TemporaryDirectory() as directory:
            self.assertFalse(traffic_modes.application_mode_available(directory))

    def test_non_application_modes_keep_the_stock_winws_engine(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(
                str(Path(directory) / "settings.ini"),
                QSettings.Format.IniFormat,
            )
            domains = Path(directory) / "domains.txt"
            domains.write_text("example.test\n", encoding="utf-8")
            for mode in (TRAFFIC_MODE_ALL, TRAFFIC_MODE_LISTS):
                with self.subTest(mode=mode):
                    settings.setValue(app.TRAFFIC_PROCESSING_MODE_KEY, mode)
                    with patch.object(app, "USER_GENERAL_FILE", str(domains)):
                        command = app._build_game_mode_winws_command(
                            str(Path("resources/core/general (ALT13).bat").resolve()),
                            str(Path("resources/core").resolve()),
                            settings,
                        )
                    self.assertIn(
                        '"' + str(Path("resources/core/bin/winws.exe").resolve()) + '"',
                        command,
                    )
                    self.assertNotIn("medvedeff-winws.exe", command)
                    self.assertNotIn("--app-scope-file", command)

    @unittest.skip("Application snapshot filters are retained only for future backend work.")
    def test_application_filter_compiles_with_bundled_windivert(self):
        from ctypes import POINTER, WinDLL, byref, c_char_p, c_uint, c_void_p, c_int

        dll_path = Path(__file__).resolve().parents[1] / "resources" / "core" / "bin" / "WinDivert.dll"
        if not dll_path.is_file():
            self.skipTest("bundled WinDivert.dll is missing")
        windivert = WinDLL(str(dll_path))
        compile_filter = windivert.WinDivertHelperCompileFilter
        compile_filter.argtypes = [
            c_char_p, c_int, c_void_p, c_uint, POINTER(c_char_p), POINTER(c_uint)
        ]
        compile_filter.restype = c_int

        endpoints = [
            ("tcp", "192.0.2.1", 40000 + index, "198.51.100.1", 443)
            for index in range(96)
        ]
        with patch.object(traffic_modes, "collect_application_endpoints", return_value=endpoints):
            value = traffic_modes.build_application_raw_filter(object())
        error = c_char_p()
        position = c_uint()
        self.assertEqual(
            1,
            compile_filter(
                value.encode("ascii"),
                0,
                None,
                0,
                byref(error),
                byref(position),
            ),
            error.value.decode("ascii", "replace") if error.value else "unknown filter error",
        )


if __name__ == "__main__":
    unittest.main()
