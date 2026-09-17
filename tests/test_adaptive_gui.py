from __future__ import annotations

import os
import inspect
import re
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QCoreApplication, QEvent, QPoint, QSettings, Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QCheckBox, QComboBox, QLabel, QWidget

import EzUnBlock as app


_QAPP = QApplication.instance() or QApplication([])


class AdaptiveDialogTests(unittest.TestCase):
    def test_game_obstacles_use_tspu_letters(self) -> None:
        source = inspect.getsource(app.AdaptiveSearchVisual._draw_game_layer)
        self.assertIn('("Т", "С", "П", "У")', source)
        self.assertNotIn('("R", "K", "N")', source)

    def test_visual_mode_cards_have_no_number_badge_or_clicked_focus_outline(self) -> None:
        source = inspect.getsource(app.AutoModeCardButton)
        self.assertIn("FocusPolicy.NoFocus", source)
        self.assertNotIn('"01"', source)
        self.assertNotIn('"02"', source)
        self.assertNotIn("DashLine", source)

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.dialog = app.AutoProgressDialog(
            "Автоподбор профиля",
            "Тестируем профили…",
            "Отмена",
            lang="ru",
            strategy_dir=self.temp.name,
        )

    def tearDown(self) -> None:
        self.dialog.close()
        self.dialog.deleteLater()
        _QAPP.processEvents()
        self.temp.cleanup()

    def test_adaptive_page_hides_advanced_configuration(self) -> None:
        self.dialog.begin_adaptive_test()
        self.dialog.set_adaptive_progress(0.55, "internal-candidate-id")
        labels = "\n".join(label.text() for label in self.dialog.findChildren(QLabel))
        self.assertEqual(self.dialog.findChildren(QCheckBox), [])
        self.assertNotIn("5.0", labels)
        self.assertNotIn("youtube.com/generate_204", labels)
        self.assertNotIn("QUIC", labels)
        self.assertEqual(self.dialog.adaptive_percent_label.text(), "55%")
        self.assertEqual(self.dialog.adaptive_stage_label.text(), "")
        self.assertTrue(self.dialog.adaptive_stage_label.isHidden())
        self.assertEqual(self.dialog.adaptive_hint_label.text(), "Не закрывайте программу до завершения автоподбора")
        self.assertEqual(self.dialog.adaptive_stage_label.toolTip(), "internal-candidate-id")

    def test_adaptive_eta_uses_the_same_compact_format_as_standard_scan(self) -> None:
        self.assertEqual(app.MainWindow._format_eta(65, "ru"), "≈ 01:05")
        self.assertEqual(app.MainWindow._format_eta(9, "en"), "≈ 00:09")

    def test_standard_scan_uses_the_new_heading(self) -> None:
        labels = [label.text() for label in self.dialog.progress_page.findChildren(QLabel)]
        self.assertIn("Перебор стандартных стратегий", labels)
        self.assertNotIn("Перебор готовых стратегий", labels)

    def test_tray_profile_menu_scrolls_a_single_combined_list(self) -> None:
        owner = QWidget()
        owner.lang = "ru"
        selected: list[str] = []
        owner.select_preset_from_tray = selected.append
        menu = app.ScrollingProfileMenu(owner, visible_profiles=10)
        profiles = [f"Profile {index:02d}" for index in range(1, 26)]
        menu.set_profiles(profiles, "Profile 03")

        stable_profile_actions = list(menu._profile_actions)
        self.assertEqual(11, len(menu.actions()))
        self.assertEqual(("scroll", 1), menu.actions()[-1].data())
        self.assertTrue(menu.actions()[2].isChecked())

        menu._on_action_hovered(menu.actions()[-1])
        QTest.qWait(700)
        self.assertGreaterEqual(menu._offset, 2)
        self.assertEqual(stable_profile_actions, menu._profile_actions)
        self.assertIs(menu._scroll_action, menu.actions()[-1])
        while menu._offset < 15:
            menu._scroll_once()
        self.assertEqual(stable_profile_actions, menu._profile_actions)
        self.assertEqual(("scroll", -1), menu.actions()[0].data())
        self.assertIs(menu._scroll_action, menu.actions()[0])
        self.assertEqual("Profile 25", menu.actions()[-1].text())

        next(action for action in menu.actions() if action.text() == "Profile 20").trigger()
        self.assertEqual(["Profile 20"], selected)
        menu.deleteLater()
        owner.deleteLater()

    def test_window_is_frameless_before_its_fixed_geometry_is_used(self) -> None:
        self.assertTrue(self.dialog.windowFlags() & Qt.WindowType.FramelessWindowHint)
        self.assertEqual(self.dialog.minimumSize(), self.dialog.maximumSize())
        self.assertEqual((620, 430), (self.dialog.width(), self.dialog.height()))

    def test_network_error_keeps_actions_inside_the_fixed_dialog(self) -> None:
        self.dialog.show()
        QTest.qWait(80)
        self.dialog.show_adaptive_error(
            "Не удалось проверить подключение. Возможно, включён VPN. "
            "Отключите VPN и повторите подбор.",
            "Подробный отчёт: C:/test/adaptive-search-last.json",
        )
        QTest.qWait(80)

        self.assertTrue(self.dialog.adaptive_retry_btn.isVisible())
        self.assertTrue(self.dialog.adaptive_result_back_btn.isVisible())
        self.assertLessEqual(
            self.dialog.adaptive_retry_btn.geometry().bottom(),
            self.dialog.height(),
        )
        self.assertLessEqual(
            self.dialog.adaptive_result_back_btn.geometry().bottom(),
            self.dialog.height(),
        )

    def test_empty_and_cyrillic_names_are_valid_but_symbols_are_not(self) -> None:
        self.dialog.show_adaptive_name()
        self.assertRegex(
            self.dialog._adaptive_default_filename,
            r"^NewAdaptiveBAT_\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}\.bat$",
        )
        self.assertTrue(self.dialog._validate_adaptive_name())
        self.dialog.adaptive_name_edit.setText("Моя стратегия (дом)")
        self.assertTrue(self.dialog._validate_adaptive_name())
        self.dialog.adaptive_name_edit.setText("bad/name🔥")
        self.assertFalse(self.dialog._validate_adaptive_name())
        self.assertTrue(self.dialog.adaptive_name_error.text())

    def test_double_clicking_success_text_requests_the_folder(self) -> None:
        path = str(Path(self.temp.name) / "Моя стратегия.bat")
        emitted: list[bool] = []
        self.dialog.adaptive_open_folder_requested.connect(lambda: emitted.append(True))
        self.dialog.show_adaptive_success(path)
        self.dialog.show()
        QTest.qWait(280)
        QTest.mouseDClick(
            self.dialog.adaptive_result_heading,
            Qt.MouseButton.LeftButton,
        )
        self.assertEqual(emitted, [True])
        self.assertTrue(self.dialog.adaptive_open_btn.isHidden())
        self.assertFalse(self.dialog.adaptive_done_btn.isHidden())

    def test_space_starts_and_restarts_the_adaptive_mini_game_without_resetting_progress(self) -> None:
        self.dialog.show()
        QTest.qWait(20)
        self.dialog.begin_adaptive_test()
        self.dialog.set_adaptive_progress(0.45, "test")
        before = self.dialog.adaptive_visual.getProgress()

        QTest.keyClick(self.dialog, Qt.Key.Key_Space)
        self.assertTrue(self.dialog.adaptive_visual._game_active)
        self.assertEqual(before, self.dialog.adaptive_visual.getProgress())
        self.assertGreaterEqual(self.dialog.adaptive_visual.width(), 500)

        normal_x = self.dialog.adaptive_visual.width() / 2.0
        QTest.qWait(320)
        self.assertLess(self.dialog.adaptive_visual.getGamePlayerX(), normal_x / 2.0)

        # A jump reaches well above the tallest generated obstacle before collision checks run.
        self.dialog.adaptive_visual._jump()
        self.dialog.adaptive_visual._advance_game()
        self.assertLess(self.dialog.adaptive_visual._game_player_offset, 0.0)

        center, ground_y, _radius = self.dialog.adaptive_visual._game_geometry()
        self.dialog.adaptive_visual._game_player_offset = -70.0
        self.dialog.adaptive_visual._game_velocity = 0.0
        self.dialog.adaptive_visual._game_spawn_after = 99.0
        self.dialog.adaptive_visual._game_obstacles = [{
            "x": center.x() - 4.0,
            "width": 12.0,
            "height": 22.0,
        }]
        self.dialog.adaptive_visual._advance_game()
        self.assertTrue(self.dialog.adaptive_visual._game_active)

        self.dialog.adaptive_visual._game_player_offset = 0.0
        self.dialog.adaptive_visual._game_velocity = 0.0
        self.dialog.adaptive_visual._game_obstacles = [{
            "x": center.x() - 4.0,
            "width": 12.0,
            "height": ground_y - center.y() + 3.0,
        }]
        self.dialog.adaptive_visual._advance_game()
        self.assertFalse(self.dialog.adaptive_visual._game_active)
        self.assertTrue(self.dialog.adaptive_visual._game_over)

    def test_space_starts_the_mini_game_during_the_ready_made_profile_scan(self) -> None:
        self.dialog.show()
        QTest.qWait(20)
        self.dialog.begin_legacy_test()
        self.dialog.set_progress(1, 4)
        before = self.dialog.spinner.getProgress()

        QTest.keyClick(self.dialog, Qt.Key.Key_Space)

        self.assertTrue(self.dialog.spinner._game_active)
        self.assertEqual(before, self.dialog.spinner.getProgress())
        self.assertNotIn("Mini-game", self.dialog.adaptive_hint_label.text())
        self.assertNotIn("Score:", self.dialog.adaptive_hint_label.text())

        QTest.keyClick(self.dialog, Qt.Key.Key_Space)
        self.assertTrue(self.dialog.spinner._game_active)
        self.assertEqual(self.dialog.spinner._game_score, 0)

    def test_space_hint_is_overlay_only_and_stops_after_eight_seconds(self) -> None:
        self.dialog.show()
        self.dialog.begin_adaptive_test()
        visual = self.dialog.adaptive_visual
        geometry = visual.geometry()
        self.assertTrue(visual._hint_visible)
        self.assertEqual(8_000, visual._space_hint_timer.interval())

        visual._hide_space_hint()
        self.assertFalse(visual._hint_visible)
        self.assertEqual(geometry, visual.geometry())

        # Retrying in the same dialog must not expose the Easter-egg hint
        # again; a new dialog instance starts a new eight-second window.
        visual.stop()
        visual.start()
        self.assertFalse(visual._hint_visible)


class AdaptiveMainWindowMethodTests(unittest.TestCase):
    def tearDown(self) -> None:
        for widget in list(_QAPP.topLevelWidgets()):
            if isinstance(widget, (app.ProfileComboBox, app.ProfileScopeSwitch)):
                widget.close()
                widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        _QAPP.processEvents()

    def test_profile_scope_switch_changes_source_with_a_handled_click(self) -> None:
        switch = app.ProfileScopeSwitch("standard")
        emitted: list[str] = []
        switch.scopeChanged.connect(emitted.append)
        switch.show()
        QTest.mouseClick(switch, Qt.MouseButton.LeftButton, pos=QPoint(switch.width() - 17, switch.height() // 2))
        self.assertEqual(switch.scope(), "user")
        self.assertEqual(emitted, ["user"])

    def test_reload_presets_separates_user_profiles_from_built_in_profiles(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            core = root_path / "core"
            adaptive = root_path / "user" / "adaptive-strategies"
            core.mkdir()
            adaptive.mkdir(parents=True)
            (core / "general.bat").write_text("@echo off", encoding="utf-8")
            (core / "general (ALT11).bat").write_text("@echo off", encoding="utf-8")
            generated = adaptive / "Домашняя.bat"
            generated.write_text("@echo off", encoding="utf-8")

            settings = QSettings(str(root_path / "settings.ini"), QSettings.Format.IniFormat)
            dummy = types.SimpleNamespace(
                core_dir=str(core),
                cb=app.ProfileComboBox(),
                settings=settings,
                preset_menu=None,
                action_start=None,
                presets={},
                standard_presets={},
                user_presets={},
                profile_scope="standard",
                last_profile="General",
                last_standard_profile="General",
                last_user_profile="",
                on_profile_changed=lambda _text: None,
            )
            with mock.patch.object(app, "USER_PROFILE_DIR", str(adaptive)):
                app.MainWindow.reload_presets(dummy)

            self.assertNotIn(generated.stem, [dummy.cb.itemText(i) for i in range(dummy.cb.count())])
            dummy.profile_scope = "user"
            app.MainWindow._populate_profile_combo(dummy)
            self.assertEqual(dummy.cb.itemData(0, app.PROFILE_ROW_KIND_ROLE), app.PROFILE_ROW_ADD)

            self.assertEqual(dummy.presets["Домашняя"], str(generated.resolve()))
            self.assertIn("Домашняя", [dummy.cb.itemText(i) for i in range(dummy.cb.count())])

    def test_empty_user_profile_dropdown_uses_non_selectable_placeholder(self) -> None:
        dummy = types.SimpleNamespace(
            cb=app.ProfileComboBox(),
            profile_scope="user",
            standard_presets={"General": "general.bat"},
            user_presets={},
            last_user_profile="",
            last_standard_profile="General",
            last_profile="General",
        )

        app.MainWindow._populate_profile_combo(dummy)

        self.assertEqual(dummy.cb.itemData(0, app.PROFILE_ROW_KIND_ROLE), app.PROFILE_ROW_ADD)
        self.assertEqual(dummy.cb.model().item(0).flags(), Qt.ItemFlag.NoItemFlags)
        self.assertEqual(dummy.cb.itemData(1, app.PROFILE_ROW_KIND_ROLE), app.PROFILE_ROW_EMPTY)
        self.assertEqual(dummy.cb.currentIndex(), -1)
        self.assertTrue(dummy.cb.itemText(1))

    def test_main_window_builds_the_compact_user_profile_selector(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            core = root_path / "core"
            core.mkdir()
            (core / "general.bat").write_text("@echo off", encoding="utf-8")
            imported_source = root_path / "manual.bat"
            imported_source.write_text("@echo off", encoding="utf-8")
            settings = QSettings(str(root_path / "settings.ini"), QSettings.Format.IniFormat)
            settings.setValue("profile_scope", "user")

            with (
                mock.patch.object(app, "APP_DIR", str(root_path)),
                mock.patch.object(app, "USER_DIR", str(root_path / "user")),
                mock.patch.object(app, "USER_PROFILE_DIR", str(root_path / "user" / "adaptive-strategies")),
                mock.patch.object(app, "ADAPTIVE_STRATEGY_DIR", str(root_path / "user" / "adaptive-strategies")),
                mock.patch.object(app, "_ensure_user_lists_initialized"),
                mock.patch.object(app, "_apply_game_mode_state_to_core"),
                mock.patch.object(app, "_sync_telegram_runtime_lists"),
                mock.patch.object(app, "_rebuild_runtime_lists"),
                mock.patch.object(app.MainWindow, "set_autostart"),
                mock.patch.object(app.MainWindow, "init_tray_icon"),
                mock.patch.object(app.MainWindow, "is_winws_running", return_value=False),
                mock.patch.object(app.QTimer, "singleShot"),
            ):
                window = app.MainWindow(settings)
                try:
                    self.assertIsInstance(window.cb, app.ProfileComboBox)
                    self.assertEqual(window.profile_scope_switch.size(), app.QSize(74, 26))
                    switch_parent = window.profile_scope_switch.parentWidget()
                    self.assertIsNotNone(switch_parent)
                    self.assertAlmostEqual(
                        window.profile_scope_switch.geometry().center().x(),
                        switch_parent.rect().center().x(),
                        delta=1,
                    )
                    self.assertEqual(window.cb.itemData(0, app.PROFILE_ROW_KIND_ROLE), app.PROFILE_ROW_ADD)
                    self.assertEqual(window.cb.itemData(1, app.PROFILE_ROW_KIND_ROLE), app.PROFILE_ROW_EMPTY)
                    with mock.patch.object(app.QFileDialog, "getOpenFileName", return_value=(str(imported_source), "BAT files (*.bat)")):
                        window._add_user_profile()
                    imported_destination = root_path / "user" / "adaptive-strategies" / "manual.bat"
                    self.assertTrue(imported_destination.is_file())
                    self.assertIn("manual", window.user_presets)
                    self.assertEqual(window.cb.currentText(), "manual")
                finally:
                    window.close()
                    window.deleteLater()

    def test_adaptive_telegram_hosts_are_owned_and_released(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            script = root_path / "adaptive.bat"
            script.write_text(
                ":: ZAPRETGUI_ADAPTIVE_PROFILE=1\n"
                ":: ZAPRETGUI_ADAPTIVE_TELEGRAM_HOSTS=1\n",
                encoding="utf-8",
            )
            settings = QSettings(str(root_path / "settings.ini"), QSettings.Format.IniFormat)
            dummy = types.SimpleNamespace(
                settings=settings,
                lang="ru",
                _adaptive_active_profile_script="",
                _adaptive_hosts_owned=False,
            )
            dummy._release_adaptive_profile_hosts = types.MethodType(
                app.MainWindow._release_adaptive_profile_hosts,
                dummy,
            )
            writes: list[bool] = []
            with (
                mock.patch.object(app, "_read_hosts_file_strict", return_value=""),
                mock.patch.object(app, "_apply_flowseal_telegram_hosts", side_effect=lambda enabled, _settings: writes.append(enabled) or True),
            ):
                app.MainWindow._prepare_adaptive_profile_hosts(dummy, str(script))
                self.assertTrue(dummy._adaptive_hosts_owned)
                app.MainWindow._release_adaptive_profile_hosts(dummy)

            self.assertEqual(writes, [True, False])
            self.assertFalse(dummy._adaptive_hosts_owned)

    def test_auto_pick_discards_stale_workers_and_releases_closed_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            root_path = Path(root)
            core = root_path / "core"
            core.mkdir()
            (core / "general.bat").write_text("@echo off", encoding="utf-8")
            settings = QSettings(str(root_path / "settings.ini"), QSettings.Format.IniFormat)

            with (
                mock.patch.object(app, "APP_DIR", str(root_path)),
                mock.patch.object(app, "USER_DIR", str(root_path / "user")),
                mock.patch.object(app, "USER_PROFILE_DIR", str(root_path / "user" / "adaptive-strategies")),
                mock.patch.object(app, "ADAPTIVE_STRATEGY_DIR", str(root_path / "user" / "adaptive-strategies")),
                mock.patch.object(app, "_ensure_user_lists_initialized"),
                mock.patch.object(app, "_apply_game_mode_state_to_core"),
                mock.patch.object(app, "_sync_telegram_runtime_lists"),
                mock.patch.object(app, "_rebuild_runtime_lists"),
                mock.patch.object(app.MainWindow, "set_autostart"),
                mock.patch.object(app.MainWindow, "init_tray_icon"),
                mock.patch.object(app.MainWindow, "is_winws_running", return_value=False),
                mock.patch.object(app.QTimer, "singleShot"),
            ):
                window = app.MainWindow(settings)
                try:
                    window._auto_worker = types.SimpleNamespace(isRunning=lambda: False)
                    window._adaptive_worker = types.SimpleNamespace(isRunning=lambda: False)
                    window.on_auto_pick_profile()
                    dialog = window._auto_progress
                    self.assertIsNotNone(dialog)
                    self.assertIsNone(window._auto_worker)
                    self.assertIsNone(window._adaptive_worker)

                    dialog.close()
                    _QAPP.processEvents()
                    self.assertIsNone(window._auto_progress)

                    window.on_auto_pick_profile()
                    self.assertIsNotNone(window._auto_progress)
                    self.assertIsNot(window._auto_progress, dialog)
                finally:
                    if window._auto_progress is not None:
                        window._auto_progress.close()
                    window.close()
                    window.deleteLater()


if __name__ == "__main__":
    unittest.main()
