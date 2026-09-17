# --- Tray profile menu -----------------------------------------------------

class ScrollingProfileMenu(QMenu):
    """Compact tray menu that scrolls a profile window while hovering ellipses."""

    def __init__(self, parent=None, visible_profiles: int = 10):
        super().__init__(parent)
        self._profile_names = []
        self._current_profile = ""
        self._offset = 0
        self._visible_profiles = max(1, int(visible_profiles))
        self._scroll_direction = 0
        self._navigation_direction = 1
        self._profile_actions = []
        self._scroll_action = None
        self._scroll_timer = QTimer(self)
        self._scroll_timer.setInterval(220)
        self._scroll_timer.timeout.connect(self._scroll_once)
        self.hovered.connect(self._on_action_hovered)
        self.aboutToHide.connect(self._stop_scrolling)

    def set_profiles(self, names, current: str = "") -> None:
        self._profile_names = list(dict.fromkeys(str(name) for name in names if str(name)))
        self._current_profile = str(current or "")
        max_offset = max(0, len(self._profile_names) - self._visible_profiles)
        self._offset = max(0, min(self._offset, max_offset))
        if self._offset <= 0:
            self._navigation_direction = 1
        elif self._offset >= max_offset:
            self._navigation_direction = -1
        self._rebuild()

    def _set_scroll_action(self, action: QAction, direction: int) -> None:
        action.setText("…")
        action.setData(("scroll", int(direction)))
        action.setEnabled(True)
        action.setToolTip(
            ("Показать профили выше" if direction < 0 else "Показать профили ниже")
            if getattr(self.parent(), "lang", "ru") == "ru"
            else ("Show previous profiles" if direction < 0 else "Show more profiles")
        )

    def _rebuild(self) -> None:
        """Build the menu structure once; scrolling only updates existing actions."""
        self.clear()
        self._profile_actions = []
        self._scroll_action = None
        total = len(self._profile_names)
        if not total:
            empty = QAction("—", self)
            empty.setEnabled(False)
            self.addAction(empty)
            return

        if total <= self._visible_profiles:
            for name in self._profile_names:
                self._profile_actions.append(self._create_profile_action(name))
            self._update_profile_actions()
            self._set_fixed_width()
            return

        for name in self._profile_names[:self._visible_profiles]:
            self._profile_actions.append(self._create_profile_action(name))
        for action in self._profile_actions:
            self.addAction(action)
        self._scroll_action = QAction("…", self)
        self.addAction(self._scroll_action)
        self._update_profile_actions()
        self._set_fixed_width()

    def _create_profile_action(self, name: str) -> QAction:
        action = QAction(name, self)
        action.setCheckable(True)
        action.setData(("profile", name))
        parent = self.parent()
        if parent is not None and hasattr(parent, "select_preset_from_tray"):
            action.triggered.connect(
                lambda _checked=False, profile_action=action, owner=parent:
                owner.select_preset_from_tray(str(profile_action.data()[1]))
            )
        return action

    def _update_profile_actions(self) -> None:
        total = len(self._profile_names)
        if total <= self._visible_profiles:
            for index, action in enumerate(self._profile_actions):
                name = self._profile_names[index]
                action.setText(name)
                action.setData(("profile", name))
                action.setChecked(name == self._current_profile)
            return

        max_offset = max(0, total - self._visible_profiles)
        if self._offset <= 0:
            self._navigation_direction = 1
        elif self._offset >= max_offset:
            self._navigation_direction = -1
        self._place_scroll_action(self._navigation_direction)

        for index, action in enumerate(self._profile_actions):
            profile_index = self._offset + index
            if profile_index < total:
                name = self._profile_names[profile_index]
                action.setText(name)
                action.setData(("profile", name))
                action.setChecked(name == self._current_profile)
                action.setEnabled(True)
            else:
                action.setText("")
                action.setData(("profile", ""))
                action.setChecked(False)
                action.setEnabled(False)

    def _place_scroll_action(self, direction: int) -> None:
        if self._scroll_action is None or not self._profile_actions:
            return
        direction = -1 if direction < 0 else 1
        self._set_scroll_action(self._scroll_action, direction)
        actions = self.actions()
        if direction < 0 and actions and actions[0] is not self._scroll_action:
            self.removeAction(self._scroll_action)
            self.insertAction(self._profile_actions[0], self._scroll_action)
        elif direction > 0 and actions and actions[-1] is not self._scroll_action:
            self.removeAction(self._scroll_action)
            self.addAction(self._scroll_action)

    def _set_fixed_width(self) -> None:
        if not self._profile_names:
            return
        metrics = self.fontMetrics()
        widest = max(metrics.horizontalAdvance(name) for name in self._profile_names)
        self.setFixedWidth(max(190, widest + 64))

    def _on_action_hovered(self, action: QAction) -> None:
        data = action.data()
        if isinstance(data, tuple) and len(data) == 2 and data[0] == "scroll":
            direction = int(data[1])
            self._navigation_direction = direction
            if direction != self._scroll_direction:
                self._scroll_direction = direction
                self._scroll_timer.start()
            return
        self._stop_scrolling()

    def _scroll_once(self) -> None:
        max_offset = max(0, len(self._profile_names) - self._visible_profiles)
        direction = int(self._scroll_direction)
        next_offset = max(0, min(max_offset, self._offset + direction))
        if next_offset == self._offset:
            self._stop_scrolling()
            return
        self._navigation_direction = direction
        self._offset = next_offset
        self._update_profile_actions()
        # Keep the same profile QActions and fixed geometry. The ellipsis moves
        # to the opposite edge only once, when an endpoint is reached.
        self._scroll_direction = direction
        if next_offset not in (0, max_offset):
            self._scroll_timer.start()
        else:
            self._stop_scrolling()

    def _stop_scrolling(self) -> None:
        self._scroll_timer.stop()
        self._scroll_direction = 0

    def leaveEvent(self, event) -> None:
        self._stop_scrolling()
        super().leaveEvent(event)


# --- Main application window -----------------------------------------------

class MainWindow(QWidget):
    def __init__(self, settings, launched_by_autostart: bool = False):
        super().__init__()
        self._exiting = False
        self._system_shutdown_requested = False
        self._manual_close_requested = False
        self._in_init = True
        self.settings = settings
        self.lang = settings.value('lang', 'ru')
        self.autostart = settings.value('autostart', False, type=bool)
        self.minimized = settings.value('minimized', False, type=bool)
        self.launched_by_autostart = bool(launched_by_autostart)
        self.last_profile = settings.value('last_profile', 'General (ALT)')
        saved_scope = str(settings.value("profile_scope", "standard") or "standard")
        self.profile_scope = "user" if saved_scope == "user" else "standard"
        self.last_standard_profile = str(settings.value("last_standard_profile", self.last_profile) or "")
        self.last_user_profile = str(settings.value("last_user_profile", "") or "")

        self.core_dir = os.path.join(APP_DIR, 'core')
        self.core_lists_dir = os.path.join(self.core_dir, "lists")
        self.user_lists_dir = USER_DIR

        self.presets = {}
        self.standard_presets = {}
        self.user_presets = {}
        self.process = None
        self._bypass_toggle_busy = False
        self._bypass_toggle_worker = None
        self._suppress_bypass_exit_notification = False
        self._auto_cancelled = False
        self._auto_done = 0
        self._auto_total = 0
        self._eta_ms_per_profile = None
        self._eta_last_done = 0
        self._eta_last_elapsed_ms = 0
        self._auto_progress = None
        self._auto_worker = None
        self._eta_timer = None
        self._adaptive_worker = None
        self._adaptive_outcome = None
        self._adaptive_progress_value = 0.0
        self._adaptive_elapsed = None
        self._adaptive_eta_timer = None
        self._adaptive_eta_seconds = None
        self._adaptive_eta_anchor = 0.0
        self._adaptive_result_path = ""
        self._adaptive_active_profile_script = ""
        self._adaptive_hosts_owned = False
        self._external_restore_queued = False

        self._lists_check_in_progress = False
        self._lists_worker = None
        self._gui_update_busy = False
        self._gui_update_worker = None
        self._pending_gui_updater_args = []
        self._pending_gui_updater_install_dir = ""
        self._gui_update_shutdown = False
        self._pending_autostart = False
        self._pending_autostart_profile = " "
        self._site_manager_dlg = None
        self._instruction_dialog = None
        self._settings_dlg = None
        self._settings_guard_installed = False
        self._adaptive_guard_installed = False
        self._game_settings_dlg = None
        self._telegram_help_msg = None
        self.game_mode_enabled = _is_game_mode_enabled(self.settings)
        self.telegram_mode_enabled = _is_telegram_mode_enabled(self.settings)
        self._telegram_mode_busy = False
        self._telegram_mode_worker = None
        self._telegram_mode_hosts_poll_timer = None
        self._telegram_mode_hosts_poll_attempts = 0
        self._telegram_mode_hosts_poll_anchor = 0
        self._telegram_mode_hosts_expected_enabled = False
        self._telegram_mode_hosts_pending_action = ""
        self._telegram_proxy_autoconnect_generation = 0
        self._telegram_help_proxy_link_sent_this_session = False
        self.telegram_proxy = TelegramProxyController()
        self.dns_malw_link_active = False
        self._dns_malw_link_busy = False
        self._dns_malw_link_worker = None
        self._dns_malw_link_show_errors = False
        self._dns_malw_link_poll_timer = None
        self._dns_malw_link_poll_attempts = 0
        self._dns_malw_link_pending_action = ""
        self._dns_malw_link_poll_anchor = 0
        self._pending_toggle_state = None
        self._pending_toggle_profile = " "
        self._pending_toggle_starting = False
        self._game_mode_restart_timer = QTimer(self)
        self._game_mode_restart_timer.setSingleShot(True)
        self._game_mode_restart_timer.setInterval(180)
        self._game_mode_restart_timer.timeout.connect(self._start_game_mode_restart_worker)
        self._game_mode_restart_worker = None

        self.tray = None
        self.tray_menu = None
        self.action_open = None
        self.action_start = None
        self.action_stop = None
        self.ai_dns_menu = None
        self.action_ai_dns_enable = None
        self.action_ai_dns_disable = None
        self.telegram_menu = None
        self.action_telegram_enable = None
        self.action_telegram_disable = None
        self.game_mode_menu = None
        self.action_game_mode_enable = None
        self.action_game_mode_disable = None
        self.action_game_mode_settings = None
        self.sites_menu = None
        self.action_sites_open = None
        self.action_sites_add = None
        self.action_sites_exclude = None
        self.action_sites_add_ip = None
        self.action_sites_exclude_ip = None
        self.preset_menu = None
        self.exit_action = None

        _ensure_user_lists_initialized()
        _apply_game_mode_state_to_core(self.settings)
        _sync_telegram_runtime_lists(self.settings)
        _rebuild_runtime_lists(self.settings)

        self.init_ui()
        self.retranslate_ui()

        if hasattr(self, "_update_autotest_info_button"):
            try:
                self._update_autotest_info_button()
            except Exception:
                pass

        self.set_autostart(self.autostart, provision=self.autostart and not self.launched_by_autostart)
        self.init_tray_icon()
        self._bypass_status_timer = QTimer(self)
        self._bypass_status_timer.timeout.connect(self._refresh_bypass_process_state)
        self._bypass_status_timer.start(1500)

        if _should_start_minimized(self.minimized, self.launched_by_autostart):
            self.hide()
        else:
            self.show()

        autostart_profile = settings.value('autostart_profile', ' ')
        autostart_enabled = settings.value('autostart_profile_enabled', False, type=bool)

        if (
            self.launched_by_autostart
            and self.autostart
            and autostart_enabled
            and autostart_profile in self.presets
        ):
            self._pending_autostart = True
            self._pending_autostart_profile = autostart_profile

        QTimer.singleShot(0, self.start_lists_sync)
        QTimer.singleShot(150, self.refresh_dns_malw_link_indicator)
        QTimer.singleShot(250, self.restore_telegram_mode_if_enabled)

        self._in_init = False

    def _tray_icon_path(self, running: bool) -> str:
        on_p = os.path.join(APP_DIR, "flags", "tray-on.ico")
        off_p = os.path.join(APP_DIR, "flags", "tray-off.ico")
        fallback = os.path.join(APP_DIR, "flags", "z.ico")

        if running and os.path.exists(on_p):
            return on_p
        if (not running) and os.path.exists(off_p):
            return off_p
        return fallback

    def show_from_tray(self):
        if getattr(self, "_exiting", False):
            return
        self.showNormal()
        self.show()
        self.raise_()
        self.activateWindow()
        QTimer.singleShot(0, self._resume_main_window_ui)
        QTimer.singleShot(50, self._resume_main_window_ui)

    def _resume_main_window_ui(self) -> None:
        if self.isMinimized() or not self.isVisible():
            return
        self._schedule_overlay_mode_buttons_position()
        for widget in self.findChildren(QWidget):
            widget.update()
        self.update()

    def _restore_from_external_activation(self) -> None:
        self._external_restore_queued = False
        self.show_from_tray()

    def _reflect_bypass_stopped_for_update(self) -> None:
        """Keep the main window in sync after the update worker stops winws."""
        owned_hosts = bool(getattr(self, "_adaptive_hosts_owned", False))
        if owned_hosts:
            cleanup_error = _release_adaptive_profile_hosts_after_stop(owned_hosts, self.settings)
            if cleanup_error:
                print(cleanup_error)
        self.process = None
        self._adaptive_hosts_owned = False
        self._adaptive_active_profile_script = ""
        self._suppress_bypass_exit_notification = False
        self._set_main_toggle_checked_visual(False, animated=True)
        self.status_lbl.setText(self.t("Off"))
        self.update_tray_status()

    def _prepare_bypass_for_update_check(self) -> None:
        """Suppress the expected-exit popup while an update check stops winws."""
        if self.process is not None and self.is_winws_running():
            self._suppress_bypass_exit_notification = True

    def _clear_update_check_bypass_exit_suppression(self) -> None:
        self._suppress_bypass_exit_notification = False

    def _request_manual_close(self) -> None:
        self._manual_close_requested = True
        self.close()

    def keyPressEvent(self, event) -> None:
        if (
            event.key() == Qt.Key.Key_F4
            and event.modifiers() & Qt.KeyboardModifier.AltModifier
        ):
            self._request_manual_close()
            event.accept()
            return
        super().keyPressEvent(event)

    def _is_settings_dialog_object(self, obj) -> bool:
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is None or not dlg.isVisible():
            return False
        if obj is dlg:
            return True
        if isinstance(obj, QWidget):
            try:
                if obj.window() is dlg:
                    return True
            except Exception:
                pass
        current = obj
        while current is not None:
            if current is dlg:
                return True
            try:
                current = current.parent()
            except Exception:
                return False
        return False

    def _active_auto_dialog(self):
        dlg = getattr(self, "_auto_progress", None)
        if dlg is None or not dlg.isVisible() or not bool(getattr(dlg, "_progress_active", False)):
            return None
        return dlg

    def _is_settings_dialog_event_target(self, obj, event) -> bool:
        if self._is_settings_dialog_object(obj):
            return True
        try:
            if hasattr(event, "globalPosition"):
                pos = event.globalPosition().toPoint()
            elif hasattr(event, "globalPos"):
                pos = event.globalPos()
            else:
                return False
            return self._is_settings_dialog_object(QApplication.widgetAt(pos))
        except Exception:
            return False

    def _nudge_settings_dialog(self) -> None:
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is None or not dlg.isVisible():
            return
        try:
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            pass
        try:
            if hasattr(dlg, "flash_attention"):
                dlg.flash_attention()
        except Exception:
            pass

    def eventFilter(self, obj, event):
        adaptive_dlg = self._active_auto_dialog()
        if adaptive_dlg is not None and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Space:
                visual = (
                    adaptive_dlg.adaptive_visual
                    if adaptive_dlg._active_mode == "adaptive"
                    else adaptive_dlg.spinner
                )
                visual.toggle_game()
                adaptive_dlg.raise_()
                adaptive_dlg.activateWindow()
                event.accept()
                return True
        adaptive_target = self._is_dialog_event_target(adaptive_dlg, obj, event) if adaptive_dlg is not None else False
        if (
            adaptive_dlg is not None
            and event.type() in (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride)
            and self._is_dialog_keyboard_target(adaptive_dlg)
        ):
            adaptive_target = True
        if adaptive_dlg is not None and not adaptive_target:
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.Wheel,
                QEvent.Type.KeyPress,
                QEvent.Type.ShortcutOverride,
            ):
                adaptive_dlg.raise_()
                adaptive_dlg.activateWindow()
                adaptive_dlg.flash_attention()
                return True
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is not None and dlg.isVisible() and not self._is_settings_dialog_event_target(obj, event):
            if event.type() in (
                QEvent.Type.MouseButtonPress,
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.Wheel,
                QEvent.Type.KeyPress,
                QEvent.Type.ShortcutOverride,
            ):
                self._nudge_settings_dialog()
                return True
        return super().eventFilter(obj, event)

    def _is_dialog_event_target(self, dialog, obj, event) -> bool:
        if obj is dialog:
            return True
        if isinstance(obj, QWidget):
            try:
                if obj.window() is dialog:
                    return True
            except Exception:
                pass
        if event.type() not in (
            QEvent.Type.MouseButtonPress,
            QEvent.Type.MouseButtonDblClick,
            QEvent.Type.Wheel,
        ):
            return False
        try:
            if hasattr(event, "globalPosition"):
                target = QApplication.widgetAt(event.globalPosition().toPoint())
            elif hasattr(event, "globalPos"):
                target = QApplication.widgetAt(event.globalPos())
            else:
                return False
            return target is not None and target.window() is dialog
        except Exception:
            return False

    @staticmethod
    def _is_dialog_keyboard_target(dialog) -> bool:
        try:
            if QApplication.activeWindow() is dialog:
                return True
            focus = QApplication.focusWidget()
            return focus is not None and focus.window() is dialog
        except Exception:
            return False

    def _sync_adaptive_dialog_guard(self) -> None:
        app = QApplication.instance()
        should_guard = self._active_auto_dialog() is not None
        if app is None:
            return
        if should_guard and not self._adaptive_guard_installed:
            app.installEventFilter(self)
            self._adaptive_guard_installed = True
        elif not should_guard and self._adaptive_guard_installed:
            app.removeEventFilter(self)
            self._adaptive_guard_installed = False

    @staticmethod
    def _worker_is_running(worker) -> bool:
        if worker is None:
            return False
        try:
            return bool(worker.isRunning())
        except RuntimeError:
            # Qt may delete the underlying C++ QThread before the deferred
            # Python reference is cleared.
            return False

    def _discard_finished_auto_workers(self) -> None:
        for attribute in ("_auto_worker", "_adaptive_worker"):
            worker = getattr(self, attribute, None)
            if worker is not None and not self._worker_is_running(worker):
                setattr(self, attribute, None)

    def _available_screen_geometry(self):
        screen = self.screen() if hasattr(self, "screen") else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else self.frameGeometry()

    def _center_dialog_on_screen(self, dialog: QDialog) -> None:
        geom = self._available_screen_geometry()
        frame = dialog.frameGeometry()
        frame.moveCenter(geom.center())
        dialog.move(frame.topLeft())

    def init_tray_icon(self):
        self.tray = QSystemTrayIcon(QIcon(self._tray_icon_path(self.toggle_btn.isChecked())), self)

        self.tray_menu = QMenu()
        self.action_open = QAction(self.t('Open'), self)
        self.action_open.triggered.connect(self.show_from_tray)
        self.tray_menu.addAction(self.action_open)
        self.tray_menu.addSeparator()

        self.action_start = QAction(self.t('Enable bypass'), self)
        self.action_start.triggered.connect(lambda: self.toggle_tray(True))
        self.tray_menu.addAction(self.action_start)

        self.action_stop = QAction(self.t('Disable bypass'), self)
        self.action_stop.triggered.connect(lambda: self.toggle_tray(False))
        self.tray_menu.addAction(self.action_stop)

        self.tray_menu.addSeparator()
        self.ai_dns_menu = QMenu("Ai DNS", self)
        self.action_ai_dns_enable = QAction(self.t('Enable'), self)
        self.action_ai_dns_enable.triggered.connect(lambda: self.set_ai_dns_from_tray(True))
        self.ai_dns_menu.addAction(self.action_ai_dns_enable)
        self.action_ai_dns_disable = QAction(self.t('Disable'), self)
        self.action_ai_dns_disable.triggered.connect(lambda: self.set_ai_dns_from_tray(False))
        self.ai_dns_menu.addAction(self.action_ai_dns_disable)
        self.tray_menu.addMenu(self.ai_dns_menu)

        self.telegram_menu = QMenu(self.t('Telegram Mode'), self)
        self.action_telegram_enable = QAction(self.t('Enable'), self)
        self.action_telegram_enable.triggered.connect(lambda: self.set_telegram_mode_from_tray(True))
        self.telegram_menu.addAction(self.action_telegram_enable)
        self.action_telegram_disable = QAction(self.t('Disable'), self)
        self.action_telegram_disable.triggered.connect(lambda: self.set_telegram_mode_from_tray(False))
        self.telegram_menu.addAction(self.action_telegram_disable)
        self.tray_menu.addMenu(self.telegram_menu)

        self.game_mode_menu = QMenu(self.t('Game Mode'), self)
        self.action_game_mode_enable = QAction(self.t('Enable'), self)
        self.action_game_mode_enable.triggered.connect(lambda: self.set_game_mode_from_tray(True))
        self.game_mode_menu.addAction(self.action_game_mode_enable)
        self.action_game_mode_disable = QAction(self.t('Disable'), self)
        self.action_game_mode_disable.triggered.connect(lambda: self.set_game_mode_from_tray(False))
        self.game_mode_menu.addAction(self.action_game_mode_disable)
        self.game_mode_menu.addSeparator()
        self.action_game_mode_settings = QAction(self.t('Game Mode Settings'), self)
        self.action_game_mode_settings.triggered.connect(self.open_game_mode_settings)
        self.game_mode_menu.addAction(self.action_game_mode_settings)
        self.tray_menu.addMenu(self.game_mode_menu)

        self.tray_menu.addSeparator()
        self.sites_menu = QMenu(self.t('Sites'), self)
        self.action_sites_open = QAction(self.t('Open'), self)
        self.action_sites_open.triggered.connect(self.open_site_manager_from_tray)
        self.sites_menu.addAction(self.action_sites_open)
        self.action_sites_add = QAction(self.t('Add Domain'), self)
        self.action_sites_add.triggered.connect(lambda: self.open_site_domain_input_from_tray(USER_GENERAL_FILE))
        self.sites_menu.addAction(self.action_sites_add)
        self.action_sites_exclude = QAction(self.t('Exclude Domain'), self)
        self.action_sites_exclude.triggered.connect(lambda: self.open_site_domain_input_from_tray(USER_EXCLUDE_FILE))
        self.sites_menu.addAction(self.action_sites_exclude)
        self.action_sites_add_ip = QAction(self.t('Add IP'), self)
        self.action_sites_add_ip.triggered.connect(lambda: self.open_site_domain_input_from_tray(USER_IP_ALL_FILE))
        self.sites_menu.addAction(self.action_sites_add_ip)
        self.action_sites_exclude_ip = QAction(self.t('Exclude IP'), self)
        self.action_sites_exclude_ip.triggered.connect(lambda: self.open_site_domain_input_from_tray(USER_IP_EXCLUDE_FILE))
        self.sites_menu.addAction(self.action_sites_exclude_ip)
        self.tray_menu.addMenu(self.sites_menu)

        self.tray_menu.addSeparator()
        self.preset_menu = ScrollingProfileMenu(self, visible_profiles=10)
        self.preset_menu.setTitle(self.t('Select profile'))
        self.tray_menu.addMenu(self.preset_menu)

        self.tray_menu.addSeparator()
        self.exit_action = QAction(self.t('Exit'), self)
        self.exit_action.triggered.connect(self.tray_exit)
        self.tray_menu.addAction(self.exit_action)

        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self.on_tray_activated)
        self.tray.show()

        self.update_tray_presets()
        self.update_tray_status()

    def retranslate_tray(self):
        self.action_open.setText(self.t('Open'))
        self.action_start.setText(self.t('Enable bypass'))
        self.action_stop.setText(self.t('Disable bypass'))
        self.ai_dns_menu.setTitle("Ai DNS")
        self.action_ai_dns_enable.setText(self.t('Enable'))
        self.action_ai_dns_disable.setText(self.t('Disable'))
        self.telegram_menu.setTitle(self.t('Telegram Mode'))
        self.action_telegram_enable.setText(self.t('Enable'))
        self.action_telegram_disable.setText(self.t('Disable'))
        self.game_mode_menu.setTitle(self.t('Game Mode'))
        self.action_game_mode_enable.setText(self.t('Enable'))
        self.action_game_mode_disable.setText(self.t('Disable'))
        self.action_game_mode_settings.setText(self.t('Game Mode Settings'))
        self.sites_menu.setTitle(self.t('Sites'))
        self.action_sites_open.setText(self.t('Open'))
        self.action_sites_add.setText(self.t('Add Domain'))
        self.action_sites_exclude.setText(self.t('Exclude Domain'))
        self.action_sites_add_ip.setText(self.t('Add IP'))
        self.action_sites_exclude_ip.setText(self.t('Exclude IP'))
        self.preset_menu.setTitle(self.t('Select profile'))
        self.exit_action.setText(self.t('Exit'))

    def update_tray_status(self):
        if self.tray is None or self.action_start is None or self.action_stop is None:
            return

        running = self.toggle_btn.isChecked()
        pending_start = getattr(self, "_pending_toggle_state", None) is True
        bypass_busy = bool(getattr(self, "_bypass_toggle_busy", False))

        self.action_start.setEnabled((not running) and (not pending_start) and (not bypass_busy))
        self.action_stop.setEnabled(running and (not pending_start) and (not bypass_busy))

        ai_busy = bool(getattr(self, "_dns_malw_link_busy", False))
        ai_active = bool(getattr(self, "dns_malw_link_active", False))
        if self.action_ai_dns_enable is not None and self.action_ai_dns_disable is not None:
            self.action_ai_dns_enable.setEnabled((not ai_busy) and (not ai_active))
            self.action_ai_dns_disable.setEnabled((not ai_busy) and ai_active)

        telegram_busy = bool(getattr(self, "_telegram_mode_busy", False))
        telegram_active = bool(getattr(self, "telegram_mode_enabled", False))
        if self.action_telegram_enable is not None and self.action_telegram_disable is not None:
            self.action_telegram_enable.setEnabled((not telegram_busy) and (not telegram_active))
            self.action_telegram_disable.setEnabled((not telegram_busy) and telegram_active)

        game_active = bool(getattr(self, "game_mode_enabled", False))
        if self.action_game_mode_enable is not None and self.action_game_mode_disable is not None:
            self.action_game_mode_enable.setEnabled(not game_active)
            self.action_game_mode_disable.setEnabled(game_active)

        try:
            self.tray.setIcon(QIcon(self._tray_icon_path(running)))
        except Exception:
            pass
        self.tray.setToolTip(self.get_tray_tooltip())

        self.update_tray_presets()

    def set_ai_dns_from_tray(self, enabled: bool) -> None:
        if bool(getattr(self, "_dns_malw_link_busy", False)):
            return
        self.refresh_dns_malw_link_indicator()
        if bool(getattr(self, "dns_malw_link_active", False)) == bool(enabled):
            self.update_tray_status()
            return
        self.on_ai_mode_clicked(bool(enabled))

    def set_telegram_mode_from_tray(self, enabled: bool) -> None:
        if bool(getattr(self, "_telegram_mode_busy", False)):
            return
        if bool(getattr(self, "telegram_mode_enabled", False)) == bool(enabled):
            self.update_tray_status()
            return
        self._start_telegram_mode_worker("enable" if enabled else "disable")

    def set_game_mode_from_tray(self, enabled: bool) -> None:
        self.set_game_mode_enabled(bool(enabled), restart_if_running=True)
        self.update_tray_status()

    def _set_lists_sync_ui_busy(self, busy: bool):
        self._lists_check_in_progress = bool(busy)

        try:
            self.game_mode_btn.update()
            self.game_settings_btn.update()
            self.telegram_mode_btn.update()
        except Exception:
            pass

        try:
            self.cb.setEnabled(not bool(getattr(self, "_pending_toggle_state", None)))
        except Exception:
            pass

        if getattr(self, "_pending_toggle_state", None) is True:
            self.status_lbl.setText(
                "Подготовка к запуску обхода..." if self.lang == "ru" else "Preparing bypass..."
            )
        elif busy:
            self.status_lbl.setText(
                "Проверка списков..." if self.lang == "ru" else "Checking lists..."
            )
        else:
            self.retranslate_ui()

        self._schedule_overlay_mode_buttons_position()
        self.update_tray_status()

    def _show_lists_sync_network_notice(self):
        # List refresh at startup is best-effort.  A transient DNS/network
        # initialization failure must never alarm the user or block startup:
        # cached and bundled lists continue to be used.
        return

    def _startup_blockers_active(self) -> bool:
        return bool(
            getattr(self, "_lists_check_in_progress", False)
            or getattr(self, "_gui_update_busy", False)
            or getattr(self, "_dns_malw_link_busy", False)
            or getattr(self, "_telegram_mode_busy", False)
            or getattr(self, "_bypass_toggle_busy", False)
        )

    def _select_profile_for_programmatic_start(self, profile: str) -> None:
        if profile not in self.presets:
            return
        target_scope = "user" if profile in getattr(self, "user_presets", {}) else "standard"
        if target_scope != getattr(self, "profile_scope", "standard"):
            self.profile_scope = target_scope
            self.settings.setValue("profile_scope", target_scope)
            switch = getattr(self, "profile_scope_switch", None)
            if switch is not None:
                switch.setScope(target_scope, animated=False, emit=False)
            self._populate_profile_combo(profile)
        try:
            self.cb.blockSignals(True)
            self.cb.setCurrentText(profile)
        finally:
            try:
                self.cb.blockSignals(False)
            except Exception:
                pass
        self.settings.setValue("last_profile", profile)
        self.update_tray_presets()

    def _set_main_toggle_checked_visual(self, checked: bool, animated: bool = True) -> None:
        try:
            self.toggle_btn.blockSignals(True)
            self.toggle_btn.setChecked(bool(checked))
            self.toggle_btn.blockSignals(False)
            if hasattr(self.toggle_btn, "syncVisualState"):
                self.toggle_btn.syncVisualState(animated=animated)
        except Exception:
            try:
                self.toggle_btn.blockSignals(False)
            except Exception:
                pass

    def _set_pending_start_ui(self, active: bool, animated: bool | None = None) -> None:
        if animated is None:
            animated = not active
        self._set_main_toggle_checked_visual(False, animated=bool(animated))
        try:
            self.toggle_btn.setEnabled(not active)
        except Exception:
            pass

        try:
            self.cb.setEnabled(not active)
        except Exception:
            pass

        if active:
            self.status_lbl.setText(
                "Подготовка к запуску обхода..." if self.lang == "ru" else "Preparing bypass..."
            )
        else:
            self.retranslate_ui()
        self._schedule_overlay_mode_buttons_position()
        self.update_tray_status()

    def _queue_toggle_start(self, profile: str) -> None:
        self._pending_toggle_state = True
        self._pending_toggle_profile = profile
        self._pending_toggle_starting = False
        self._set_pending_start_ui(True)

    def _resume_pending_toggle_if_ready(self) -> None:
        if getattr(self, "_pending_toggle_state", None) is not True:
            return
        if self._startup_blockers_active():
            self._set_pending_start_ui(True)
            return

        profile = self._pending_toggle_profile
        self._pending_toggle_state = None
        self._pending_toggle_profile = " "
        self._set_pending_start_ui(False, animated=False)

        self._start_main_bypass_after_button_animation(profile)

    def _start_main_bypass_after_button_animation(self, profile: str) -> None:
        if profile in self.presets:
            self._select_profile_for_programmatic_start(profile)
        else:
            profile = self.cb.currentText()

        self._pending_toggle_starting = True
        self._set_main_toggle_checked_visual(True, animated=True)
        self.status_lbl.setText(
            "Запуск обхода..." if self.lang == "ru" else "Starting bypass..."
        )
        self._schedule_overlay_mode_buttons_position()
        self.update_tray_status()

        def _start_without_waiting_for_animation() -> None:
            self._pending_toggle_starting = False
            if not hasattr(self, "toggle_btn") or not self.toggle_btn.isChecked():
                self.update_tray_status()
                return
            if profile in self.presets:
                self._select_profile_for_programmatic_start(profile)
            if self._startup_blockers_active():
                self._queue_toggle_start(self.cb.currentText())
                return
            self.on_toggle(True)

        # Let Qt paint the state change first, then run the real startup in its
        # worker.  The animation must not be a delay before starting the bypass.
        QTimer.singleShot(0, _start_without_waiting_for_animation)

    def _run_pending_autostart_if_needed(self):
        if getattr(self, "_pending_toggle_state", None) is True:
            self._pending_autostart = False
            self._pending_autostart_profile = " "
            return

        if not self._pending_autostart:
            return

        profile = self._pending_autostart_profile
        self._pending_autostart = False
        self._pending_autostart_profile = " "

        if profile in self.presets:
            self._start_main_bypass_after_button_animation(profile)

    def start_lists_sync(self):
        if getattr(self, "_lists_check_in_progress", False):
            return

        self._set_lists_sync_ui_busy(True)

        self._lists_worker = ListsUpdateWorker(
            self.core_lists_dir,
            self.user_lists_dir,
            parent=self
        )
        self._lists_worker.finished_sync.connect(self._on_lists_sync_finished)
        self._lists_worker.start()

    def _on_lists_sync_finished(self, result: dict):
        self._set_lists_sync_ui_busy(False)

        try:
            self._lists_worker = None
        except Exception:
            pass

        _ensure_user_lists_initialized()
        _rebuild_runtime_lists(self.settings)

        # Startup synchronization is deliberately silent: cached/bundled lists
        # stay active if Windows networking or a remote host is not ready yet.

        if self._maybe_offer_startup_gui_update(result.get("gui_update") or {}):
            return

        self._run_pending_autostart_if_needed()
        self._resume_pending_toggle_if_ready()

    def _maybe_offer_startup_gui_update(self, gui_result: dict) -> bool:
        if not isinstance(gui_result, dict):
            return False
        if not (gui_result.get("ok") and gui_result.get("status") == "update-available"):
            return False

        update_now, skip = _show_gui_update_question(self, self.lang, gui_result, allow_skip=True)
        latest_ver = str(gui_result.get("latest_ver") or "")
        if skip and latest_ver:
            try:
                self.settings.setValue(GUI_SKIPPED_UPDATE_KEY, latest_ver)
                self.settings.sync()
            except Exception:
                pass

        if update_now and str(gui_result.get("download_url") or ""):
            self._start_gui_update_worker(
                latest_ver,
                str(gui_result.get("download_url") or ""),
                str(gui_result.get("archive_sha256") or ""),
                str(gui_result.get("checksum_url") or ""),
            )
            return True

        return False

    def _start_gui_update_worker(
        self,
        latest_ver: str,
        download_url: str,
        archive_sha256: str = "",
        checksum_url: str = "",
    ) -> None:
        if getattr(self, "_gui_update_busy", False):
            return

        self._gui_update_busy = True
        try:
            self.status_lbl.setText(
                "Скачивание обновления GUI..." if self.lang == "ru" else "Downloading GUI update..."
            )
        except Exception:
            pass
        self._schedule_overlay_mode_buttons_position()

        worker = ReleaseUpdateWorker(
            "apply-gui",
            latest_ver,
            download_url,
            archive_sha256,
            checksum_url,
            self,
        )
        self._gui_update_worker = worker
        worker.finished_update.connect(self._on_gui_update_worker_finished)
        worker.download_progress.connect(self._on_startup_gui_update_download_progress)
        worker.start()

    def _on_startup_gui_update_download_progress(self, downloaded: int, total: int) -> None:
        if total > 0:
            percent = max(0, min(100, int(downloaded * 100 / total)))
            text = (
                f"Скачивание обновления GUI... {percent}%"
                if self.lang == "ru" else
                f"Downloading GUI update... {percent}%"
            )
        else:
            megabytes = max(0.0, float(downloaded) / (1024 * 1024))
            text = (
                f"Скачивание обновления GUI... {megabytes:.1f} МБ"
                if self.lang == "ru" else
                f"Downloading GUI update... {megabytes:.1f} MB"
            )
        self.status_lbl.setText(text)
        self._schedule_overlay_mode_buttons_position()

    def _on_gui_update_worker_finished(self, mode: str, result: dict) -> None:
        del mode
        self._gui_update_busy = False
        self._gui_update_worker = None

        if result.get("ok") and result.get("status") == "gui-update-ready":
            self.status_lbl.setText(
                "GUI обновляется, перезапуск..." if self.lang == "ru" else "GUI is updating, restarting..."
            )
            self._schedule_overlay_mode_buttons_position()
            try:
                _prepare_gui_update_shutdown(self, result)
            except Exception as error:
                self._gui_update_busy = False
                QMessageBox.warning(
                    self,
                    "Обновление GUI" if self.lang == "ru" else "GUI update",
                    str(error),
                )
                self._run_pending_autostart_if_needed()
                self._resume_pending_toggle_if_ready()
            return

        status = str(result.get("status") or "")
        if status == "unsupported":
            text = (
                "Автообновление GUI доступно только для exe-версии приложения."
                if self.lang == "ru" else
                "GUI auto-update is available only for the exe build."
            )
        elif status == "offline":
            text = (
                "Не удалось скачать обновление GUI: проверьте интернет-соединение."
                if self.lang == "ru" else
                "Could not download the GUI update: check your internet connection."
            )
        else:
            text = (
                f"Не удалось обновить GUI:\n{result.get('error') or status}"
                if self.lang == "ru" else
                f"Could not update GUI:\n{result.get('error') or status}"
            )
        QMessageBox.warning(self, "Обновление GUI" if self.lang == "ru" else "GUI update", text)
        self._run_pending_autostart_if_needed()
        self._resume_pending_toggle_if_ready()

    def is_admin(self) -> bool:
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except Exception:
            return False

    def get_tray_tooltip(self):
        if hasattr(self, 'toggle_btn') and self.toggle_btn.isChecked():
            return self.t('On: {}', self.cb.currentText())
        return self.t('Off')

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_from_tray()

    def update_tray_presets(self):
        if self.preset_menu is None:
            return
        if not hasattr(self, "cb"):
            return

        current = self.cb.currentText()
        self.preset_menu.set_profiles(self.presets, current)

    def select_preset_from_tray(self, name):
        self._select_profile_for_programmatic_start(name)
        self.on_profile_changed(name)

    def on_auto_pick_profile(self):
        title = "Автоподбор профиля" if self.lang == "ru" else "Auto profile selection"
        self._discard_finished_auto_workers()
        dlg = getattr(self, "_auto_progress", None)
        worker = getattr(self, "_auto_worker", None)
        adaptive_worker = getattr(self, "_adaptive_worker", None)
        any_worker_running = bool(
            self._worker_is_running(worker)
            or self._worker_is_running(adaptive_worker)
        )

        if dlg is not None and dlg.lang != self.lang and not any_worker_running:
            try:
                dlg.close()
                dlg.deleteLater()
            except Exception:
                pass
            dlg = None
            self._auto_progress = None

        if dlg is None:
            dlg = AutoProgressDialog(
                title=title,
                left_text="Тестируем профили..." if self.lang == "ru" else "Testing profiles...",
                cancel_text="Отмена" if self.lang == "ru" else "Cancel",
                lang=self.lang,
                strategy_dir=ADAPTIVE_STRATEGY_DIR,
                parent=self,
            )
            dlg.legacy_requested.connect(self._start_legacy_auto_test)
            dlg.new_requested.connect(self._start_adaptive_auto_test)
            dlg.adaptive_save_requested.connect(self._save_adaptive_strategy)
            dlg.adaptive_retry_requested.connect(self._start_adaptive_auto_test)
            dlg.adaptive_open_folder_requested.connect(self._open_adaptive_strategy_folder)
            dlg.adaptive_canceled.connect(self._on_adaptive_test_cancel)
            dlg.canceled.connect(self._on_auto_test_cancel)
            dlg.finished.connect(lambda _=0, dialog=dlg: self._on_auto_dialog_finished(dialog))
            dlg.destroyed.connect(lambda _=None, dialog=dlg: self._on_auto_dialog_destroyed(dialog))
            self._auto_progress = dlg

        if dlg.isVisible():
            dlg.raise_()
            dlg.activateWindow()
            dlg.flash_attention()
            return

        if not any_worker_running:
            message = ""
            warning = False
            if getattr(self, "_lists_check_in_progress", False):
                message = (
                    "Проверка списков ещё выполняется. Выбрать режим можно сейчас, запуск станет доступен после её завершения."
                    if self.lang == "ru" else
                    "The list check is still running. You can choose a mode now and start it when the check finishes."
                )
                warning = True
            dlg.show_selection(message, warning=warning)

        dlg.show()
        dlg.raise_()
        dlg.activateWindow()
        self._sync_adaptive_dialog_guard()

    def _on_auto_dialog_finished(self, dialog) -> None:
        self._sync_adaptive_dialog_guard()
        if getattr(self, "_auto_progress", None) is not dialog:
            return
        if not (
            self._worker_is_running(getattr(self, "_auto_worker", None))
            or self._worker_is_running(getattr(self, "_adaptive_worker", None))
        ):
            self._auto_progress = None
            try:
                dialog.deleteLater()
            except RuntimeError:
                pass

    def _on_auto_dialog_destroyed(self, dialog) -> None:
        if getattr(self, "_auto_progress", None) is dialog:
            self._auto_progress = None
        self._sync_adaptive_dialog_guard()

    def _start_adaptive_auto_test(self) -> None:
        dlg = getattr(self, "_auto_progress", None)
        if dlg is None:
            return

        adaptive_worker = getattr(self, "_adaptive_worker", None)
        legacy_worker = getattr(self, "_auto_worker", None)
        if self._worker_is_running(adaptive_worker):
            return
        if self._worker_is_running(legacy_worker):
            dlg.show_selection(
                "Сначала дождитесь завершения перебора готовых стратегий."
                if self.lang == "ru" else
                "Wait for the ready-made strategy scan to finish first.",
                warning=True,
            )
            return
        if getattr(self, "_lists_check_in_progress", False):
            dlg.show_selection(
                "Дождитесь завершения проверки списков, затем создайте новую стратегию."
                if self.lang == "ru" else
                "Wait for the list check to finish, then create a new strategy.",
                warning=True,
            )
            return
        if self.is_winws_running():
            dlg.show_selection(
                "Сначала выключите обход (красная кнопка), затем запустите создание стратегии."
                if self.lang == "ru" else
                "Stop the bypass first (red button), then create a strategy.",
                warning=True,
            )
            return
        if not self.is_admin():
            dlg.show_selection(
                "Создание стратегии требует запуск приложения от администратора. Закройте программу и запустите EXE через ПКМ → Запуск от имени администратора."
                if self.lang == "ru" else
                "Creating a strategy requires Administrator privileges. Close the app and use Right click → Run as Administrator.",
                warning=True,
            )
            return

        self._adaptive_outcome = None
        self._adaptive_result_path = ""
        self._adaptive_progress_value = 0.0
        self._adaptive_eta_seconds = None
        self._adaptive_eta_anchor = time.monotonic()
        if self._adaptive_eta_timer is not None:
            self._adaptive_eta_timer.stop()

        dlg.begin_adaptive_test()
        self._sync_adaptive_dialog_guard()
        self._adaptive_elapsed = QElapsedTimer()
        self._adaptive_elapsed.start()
        self._adaptive_eta_timer = QTimer(self)
        self._adaptive_eta_timer.setInterval(750)
        self._adaptive_eta_timer.timeout.connect(self._update_adaptive_eta)
        self._adaptive_eta_timer.start()

        worker = AdaptiveSearchWorker(
            app_dir=APP_DIR,
            runtime_source=_bundled_path("adaptive-runtime"),
            runtime_destination=ADAPTIVE_RUNTIME_DIR,
            report_path=ADAPTIVE_REPORT_FILE,
            parent=self,
        )
        worker.progress_update.connect(self._on_adaptive_progress)
        worker.completed.connect(self._on_adaptive_search_completed)
        worker.failed.connect(self._on_adaptive_search_failed)
        worker.cancelled.connect(self._on_adaptive_search_cancelled)
        worker.finished.connect(lambda w=worker: self._on_adaptive_worker_finished(w))
        self._adaptive_worker = worker
        worker.start()

    def _on_adaptive_progress(self, fraction: float, label: str) -> None:
        value = max(self._adaptive_progress_value, min(1.0, max(0.0, float(fraction))))
        self._adaptive_progress_value = value
        elapsed_seconds = (
            max(0.0, float(self._adaptive_elapsed.elapsed()) / 1000.0)
            if self._adaptive_elapsed is not None else 0.0
        )
        if 0.04 <= value < 0.995 and elapsed_seconds >= 2.0:
            raw_eta = elapsed_seconds * (1.0 - value) / max(value, 0.01)
            raw_eta = max(1.0, min(3600.0, raw_eta))
            if self._adaptive_eta_seconds is None:
                self._adaptive_eta_seconds = raw_eta
            else:
                self._adaptive_eta_seconds = self._adaptive_eta_seconds * 0.72 + raw_eta * 0.28
            self._adaptive_eta_anchor = time.monotonic()

        dlg = getattr(self, "_auto_progress", None)
        if dlg is not None:
            dlg.set_adaptive_progress(value, label)
        self._update_adaptive_eta()

    @staticmethod
    def _format_eta(seconds: float, lang: str) -> str:
        seconds = max(1, int(round(float(seconds))))
        minutes, rest = divmod(seconds, 60)
        return f"≈ {minutes:02d}:{rest:02d}"

    def _update_adaptive_eta(self) -> None:
        dlg = getattr(self, "_auto_progress", None)
        if dlg is None or not dlg.isVisible():
            return
        if self._adaptive_progress_value >= 0.995:
            dlg.set_adaptive_eta_text("≈ 00:00")
            return
        if self._adaptive_eta_seconds is None:
            dlg.set_adaptive_eta_text("≈ —")
            return
        elapsed_since_estimate = max(0.0, time.monotonic() - float(self._adaptive_eta_anchor or time.monotonic()))
        remaining = max(1.0, float(self._adaptive_eta_seconds) - elapsed_since_estimate)
        dlg.set_adaptive_eta_text(self._format_eta(remaining, self.lang))

    def _stop_adaptive_eta(self) -> None:
        timer = getattr(self, "_adaptive_eta_timer", None)
        if timer is not None:
            timer.stop()

    def _adaptive_outcome_details(self, outcome) -> str:
        lines = []
        validation = list(getattr(outcome, "validation", []) or [])
        failed = [item for item in validation if not getattr(item, "success", False)]
        if failed:
            lines.append("Не прошли итоговую проверку:" if self.lang == "ru" else "Failed final validation:")
            for probe in failed[:12]:
                target = getattr(probe, "target", None)
                url = getattr(target, "url", "") or getattr(target, "hostname", "") or "—"
                error = str(getattr(probe, "error", "") or "").strip()
                code = getattr(probe, "http_code", None)
                detail = error or (f"HTTP {code}" if code is not None else "no response")
                lines.append(f"• {url}: {detail}")
        report_label = "Подробный отчёт" if self.lang == "ru" else "Detailed report"
        lines.append(f"{report_label}: {ADAPTIVE_REPORT_FILE}")
        return "\n".join(line for line in lines if line)

    def _on_adaptive_search_completed(self, outcome) -> None:
        self._stop_adaptive_eta()
        dlg = getattr(self, "_auto_progress", None)
        if outcome is not None and bool(getattr(outcome, "success", False)):
            self._adaptive_outcome = outcome
            self._adaptive_progress_value = 1.0
            if dlg is not None:
                dlg.set_adaptive_progress(1.0, "Готово")
                dlg.show_adaptive_name()
                self._sync_adaptive_dialog_guard()
            return

        self._adaptive_outcome = None
        message = str(getattr(outcome, "message", "") or "").strip()
        if not message:
            message = (
                "Для этого подключения не удалось подтвердить рабочую комбинацию методов."
                if self.lang == "ru" else
                "No working combination could be confirmed for this connection."
            )
        if dlg is not None:
            dlg.show_adaptive_error(message, self._adaptive_outcome_details(outcome))
        self._sync_adaptive_dialog_guard()

    def _on_adaptive_search_failed(self, error: str) -> None:
        self._stop_adaptive_eta()
        self._adaptive_outcome = None
        dlg = getattr(self, "_auto_progress", None)
        if dlg is None:
            return
        message = (
            "Во время подбора произошла внутренняя ошибка. Ни один непроверенный профиль не был сохранён."
            if self.lang == "ru" else
            "An internal error occurred during selection. No unverified profile was saved."
        )
        details = f"{error}\n\n" + (
            f"Подробный отчёт: {ADAPTIVE_REPORT_FILE}"
            if self.lang == "ru" else
            f"Detailed report: {ADAPTIVE_REPORT_FILE}"
        )
        dlg.show_adaptive_error(message, details)
        self._sync_adaptive_dialog_guard()

    def _on_adaptive_search_cancelled(self) -> None:
        self._stop_adaptive_eta()
        self._adaptive_outcome = None
        dlg = getattr(self, "_auto_progress", None)
        if dlg is not None and dlg.isVisible():
            dlg.show_selection(
                "Создание стратегии остановлено. Непроверенный профиль не сохранён."
                if self.lang == "ru" else
                "Strategy creation was stopped. No unverified profile was saved."
            )
        self._sync_adaptive_dialog_guard()

    def _on_adaptive_test_cancel(self) -> None:
        worker = getattr(self, "_adaptive_worker", None)
        if worker is not None:
            try:
                worker.stop()
            except Exception:
                pass

    def _on_adaptive_worker_finished(self, worker) -> None:
        if getattr(self, "_adaptive_worker", None) is worker:
            self._adaptive_worker = None
        try:
            worker.deleteLater()
        except Exception:
            pass

    def _save_adaptive_strategy(self, requested_name: str) -> None:
        dlg = getattr(self, "_auto_progress", None)
        outcome = getattr(self, "_adaptive_outcome", None)
        if dlg is None or outcome is None or not bool(getattr(outcome, "success", False)):
            if dlg is not None:
                dlg.set_adaptive_save_error(
                    "Результат подбора больше недоступен. Повторите проверку."
                    if self.lang == "ru" else
                    "The selection result is no longer available. Run the check again."
                )
            return

        ok, error, filename = validate_strategy_name(
            requested_name,
            Path(USER_PROFILE_DIR),
            lang=self.lang,
        )
        if not ok:
            dlg.set_adaptive_save_error(error)
            return

        try:
            paths = AdaptiveRuntimePaths.for_zapret_gui(
                Path(APP_DIR),
                Path(ADAPTIVE_RUNTIME_DIR),
            )
            generator = ZapretGuiBatGenerator(paths, Path(USER_PROFILE_DIR))
            destination = generator.generate(outcome, filename, lang=self.lang)
        except Exception as exc:
            dlg.set_adaptive_save_error(str(exc))
            return

        self._adaptive_result_path = str(destination)
        methods = []
        for strategy in list(getattr(outcome, "tcp_profiles", {}).values()) + list(getattr(outcome, "quic_profiles", {}).values()):
            method = str(getattr(strategy, "name", "") or getattr(strategy, "id", "")).strip()
            if method:
                methods.append(method)
        _save_adaptive_strategy_info(str(destination), methods)
        self._update_autotest_info_button()
        self.reload_presets()
        profile_name = self._profile_name_for_bat(str(destination))
        if profile_name:
            self._set_profile_scope("user")
            self.last_user_profile = profile_name
            self.last_profile = profile_name
            self.settings.setValue("last_user_profile", profile_name)
            self.settings.setValue("last_profile", profile_name)
            self._populate_profile_combo(profile_name)
            self.settings.sync()
            self.update_tray_presets()
        dlg.show_adaptive_success(str(destination))
        self._sync_adaptive_dialog_guard()

    def _open_adaptive_strategy_folder(self) -> None:
        path = Path(getattr(self, "_adaptive_result_path", "") or ADAPTIVE_STRATEGY_DIR)
        folder = path if path.is_dir() else path.parent
        try:
            folder.mkdir(parents=True, exist_ok=True)
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))
        except Exception as exc:
            QMessageBox.warning(
                self,
                "Автоподбор профиля" if self.lang == "ru" else "Auto profile selection",
                (f"Не удалось открыть папку:\n{exc}" if self.lang == "ru" else f"Could not open folder:\n{exc}"),
            )

    def _start_legacy_auto_test(self):
        dlg = getattr(self, "_auto_progress", None)
        if dlg is None:
            return

        worker = getattr(self, "_auto_worker", None)
        if self._worker_is_running(worker):
            return
        adaptive_worker = getattr(self, "_adaptive_worker", None)
        if self._worker_is_running(adaptive_worker):
            dlg.show_selection(
                "Сначала дождитесь завершения создания новой стратегии."
                if self.lang == "ru" else
                "Wait for the new strategy creation to finish first.",
                warning=True,
            )
            return

        if getattr(self, "_lists_check_in_progress", False):
            dlg.show_selection(
                "Дождитесь завершения проверки списков, затем запустите перебор стратегий."
                if self.lang == "ru" else
                "Wait for the list check to finish, then start the strategy scan.",
                warning=True,
            )
            return

        if self.is_winws_running():
            dlg.show_selection(
                "Сначала выключите обход (красная кнопка), затем запустите перебор стратегий."
                if self.lang == "ru" else
                "Stop the bypass first (red button), then run the strategy scan.",
                warning=True,
            )
            return

        self._auto_cancelled = False
        if self._eta_timer is not None:
            self._eta_timer.stop()

        dlg.begin_legacy_test()
        self._sync_adaptive_dialog_guard()

        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(200)

        self._elapsed = QElapsedTimer()
        self._elapsed.start()

        def update_eta_tick():
            dlg = getattr(self, "_auto_progress", None)
            if dlg is None or (not dlg.isVisible()):
                return

            total = int(getattr(self, "_auto_total", 0))
            done = int(getattr(self, "_auto_done", 0))

            if total <= 0:
                dlg.set_eta_text("≈ —")
                return

            if done >= total:
                dlg.set_eta_text("≈ 00:00")
                return

            elapsed_ms = int(self._elapsed.elapsed()) if hasattr(self, "_elapsed") else 0
            if done <= 0:
                dlg.set_eta_text("≈ —")
                return

            raw_ms_per = max(200, elapsed_ms // done)
            if self._eta_ms_per_profile is None:
                self._eta_ms_per_profile = raw_ms_per
            else:
                alpha = 0.35 if done < 6 else (0.20 if done < 20 else 0.15)
                self._eta_ms_per_profile = int(self._eta_ms_per_profile * (1 - alpha) + raw_ms_per * alpha)

            left_profiles = total - done
            left_ms = left_profiles * int(self._eta_ms_per_profile)
            if left_ms < 1000:
                left_ms = 1000

            s = left_ms // 1000
            m = s // 60
            s = s % 60
            dlg.set_eta_text(f"≈ {m:02d}:{s:02d}")

        self._update_eta_tick = update_eta_tick
        self._eta_timer.timeout.connect(update_eta_tick)
        self._eta_timer.start()
        update_eta_tick()

        self._auto_done = 0
        self._auto_total = len(self.standard_presets)
        self._eta_ms_per_profile = None
        self._eta_last_done = 0
        self._eta_last_elapsed_ms = 0
        worker = AutoTestWorker(self.core_dir, self.standard_presets, parent=self)
        worker.finished_ok.connect(self._on_auto_test_done)
        worker.finished_err.connect(self._on_auto_test_err)
        worker.progress.connect(self._on_auto_test_progress)
        worker.finished.connect(lambda w=worker: self._on_auto_worker_thread_finished(w))
        self._auto_worker = worker
        worker.start()

    def _on_auto_worker_thread_finished(self, worker):
        if getattr(self, "_auto_worker", None) is worker:
            self._auto_worker = None
        try:
            worker.deleteLater()
        except Exception:
            pass

    def _profile_name_for_bat(self, config_name: str) -> str:
        wanted = os.path.basename(str(config_name or "")).strip().casefold()
        if not wanted:
            return ""
        for profile, filename in self.presets.items():
            if os.path.basename(str(filename)).casefold() == wanted:
                return profile
        stem = os.path.splitext(os.path.basename(str(config_name or "")))[0]
        return stem if stem in self.presets else ""

    def _profiles_from_ranked_configs(self, ranked: list[dict]) -> tuple[list[str], list[str]]:
        good = []
        bad = []
        for item in ranked or []:
            profile = self._profile_name_for_bat(str(item.get("config") or ""))
            if not profile:
                continue
            ok_count = int(item.get("ok", 0) or 0)
            if ok_count > 0:
                if profile not in good:
                    good.append(profile)
            elif profile not in bad:
                bad.append(profile)
        return good, bad

    def _on_auto_test_progress(self, done: int, total: int, prof: str):
        self._auto_done = int(done)
        self._auto_total = int(total)

        dlg = getattr(self, "_auto_progress", None)
        if dlg is None:
            return

        dlg.set_progress(done, total)
        dlg.set_current_profile(prof)

        try:
            cb = getattr(self, "_update_eta_tick", None)
            if cb:
                cb()
        except Exception:
            pass

    def _on_auto_test_cancel(self):
        self._auto_cancelled = True
        w = getattr(self, "_auto_worker", None)
        if w is not None:
            try:
                w.stop()
            except Exception:
                pass

        # The worker's finally block stops its service-owned process and waits
        # for completion; a medium-integrity taskkill cannot stop SYSTEM winws.
        if w is not None:
            try:
                w.finished_ok.disconnect(self._on_auto_test_done)
            except Exception:
                pass
            try:
                w.finished_err.disconnect(self._on_auto_test_err)
            except Exception:
                pass
        if self._eta_timer is not None:
            self._eta_timer.stop()

        dlg = getattr(self, "_auto_progress", None)
        if dlg is not None and dlg.isVisible():
            dlg.show_selection(
                "Перебор остановлен. Можно выбрать другой режим."
                if self.lang == "ru" else
                "The scan was stopped. You can choose another mode."
            )
        self._sync_adaptive_dialog_guard()

    def _on_auto_test_err(self, err: str):
        if getattr(self, "_auto_cancelled", False):
            return
        if self._eta_timer is not None:
            self._eta_timer.stop()

        dlg = getattr(self, "_auto_progress", None)
        if dlg is not None:
            dlg.show_error(
                "Не удалось завершить перебор" if self.lang == "ru" else "The scan could not be completed",
                (
                    f"Ошибка при выполнении тестов:\n{err}\n\nЛог автотеста: {AUTOLOG_FILE}"
                    if self.lang == "ru" else
                    f"Auto test error:\n{err}\n\nLog file: {AUTOLOG_FILE}"
                ),
            )

    def _on_auto_test_done(self, result: dict):
        if getattr(self, "_auto_cancelled", False):
            return
        if self._eta_timer is not None:
            self._eta_timer.stop()

        elapsed_ms = int(self._elapsed.elapsed()) if hasattr(self, "_elapsed") else 0

        total = max(1, len(self.standard_presets))
        ms_per_profile = max(300, elapsed_ms // total)

        prev = int(self.settings.value("auto_test_avg_ms_per_profile", 0))
        new_avg = ms_per_profile if prev <= 0 else int(prev * 0.7 + ms_per_profile * 0.3)

        self.settings.setValue("auto_test_avg_ms_per_profile", new_avg)
        self.settings.sync()

        try:
            self._auto_progress.set_progress(self._auto_total, self._auto_total)
        except Exception:
            pass

        good = result.get("good", [])
        bad = result.get("bad", [])
        raw = result.get("raw", "")
        extra_err = result.get("error", "")

        best = good[0] if good else None
        _save_autotest_result(best, good, bad)
        self._update_autotest_info_button()

        if self.lang == "ru":
            best_line = f"<b>Самый лучший для Вас профиль:</b> {best}" if best else "<b>Самый лучший для Вас профиль:</b> не найден"
            good_line = "<b>Профили, которые также будут работать:</b><br>" + ("<br>".join(good) if good else "—")
            bad_line = "<b>Профили, которые у Вас не сработают:</b><br>" + ("<br>".join(bad) if bad else "—")
        else:
            best_line = f"<b>Best profile for you:</b> {best}" if best else "<b>Best profile for you:</b> not found"
            good_line = "<b>Profiles that should work:</b><br>" + ("<br>".join(good) if good else "—")
            bad_line = "<b>Profiles that won't work:</b><br>" + ("<br>".join(bad) if bad else "—")

        html = "<div style='font-family:Segoe UI; font-size:10.5pt'>"
        if extra_err:
            html += f"<div style='color:#cc0000;'><b>{extra_err}</b></div><br>"
        html += f"{best_line}<br><br>{good_line}<br><br>{bad_line}"
        if extra_err and raw:
            tail = raw[-4000:]
            html += "<br><br><b>Лог тестов:</b><br><pre style='white-space:pre-wrap;'>" + tail + "</pre>"
        html += "</div>"

        dlg = getattr(self, "_auto_progress", None)
        if dlg is not None:
            dlg.show_results(html)
        self._sync_adaptive_dialog_guard()

        if best and best in self.presets:
            self._select_profile_for_programmatic_start(best)
            self.on_profile_changed(best)

    def toggle_tray(self, state: bool):
        if self.toggle_btn.isChecked() != state:
            self.toggle_btn.setChecked(state)
            self.on_toggle(state)
        self.update_tray_status()

    def _shutdown_and_quit(self):
        if getattr(self, "_exiting", False):
            return
        self._exiting = True
        APP_SHUTTING_DOWN.set()

        self._shutdown_pending_workers = []
        for worker_name in (
            "_adaptive_worker",
            "_auto_worker",
            "_bypass_toggle_worker",
            "_background_setup_worker",
            "_dns_malw_link_worker",
            "_game_mode_restart_worker",
            "_gui_update_worker",
            "_lists_worker",
            "_telegram_mode_worker",
        ):
            worker = getattr(self, worker_name, None)
            if worker is None or not worker.isRunning():
                continue
            self._shutdown_pending_workers.append(worker)
            try:
                worker.stop()
            except Exception:
                pass
            try:
                worker.requestInterruption()
            except Exception:
                pass

        self.hide()
        if getattr(self, "_system_shutdown_requested", False):
            # Windows is ending the session: never wait for network/UAC/worker
            # operations and never show a dialog. Process exit closes the
            # named-pipe handle; the service owns winws in a kill-on-close job
            # and its owner watcher also terminates it independently.
            try:
                _bypass_service.close()
            except Exception:
                pass
            try:
                if self.tray is not None:
                    self.tray.hide()
            except Exception:
                pass
            QApplication.instance().quit()
            return
        QTimer.singleShot(0, self._finish_shutdown_when_idle)

    def _begin_gui_update_install(self, updater_args: list[str], install_dir: str) -> None:
        if not updater_args or not install_dir:
            raise RuntimeError("GUI updater was not prepared correctly")
        self._pending_gui_updater_args = list(updater_args)
        self._pending_gui_updater_install_dir = os.path.abspath(install_dir)
        self._gui_update_shutdown = True
        self._gui_update_shutdown_deadline = time.monotonic() + 20.0
        try:
            self.settings.sync()
        except Exception:
            pass
        self._shutdown_and_quit()

    def _handle_system_shutdown_request(self, *_args) -> None:
        """Qt session-manager callback, received before Windows forces exit."""
        self._system_shutdown_requested = True
        self._shutdown_and_quit()

    def _finish_shutdown_when_idle(self):
        for worker in self._shutdown_pending_workers:
            try:
                running = worker.isRunning()
            except RuntimeError:
                running = False  # QObject has already been deleted after finished.
            if running:
                if (
                    getattr(self, "_gui_update_shutdown", False)
                    and time.monotonic() >= float(getattr(self, "_gui_update_shutdown_deadline", 0.0) or 0.0)
                ):
                    self._exiting = False
                    self._gui_update_shutdown = False
                    APP_SHUTTING_DOWN.clear()
                    self.show()
                    _show_centered_message(
                        self,
                        QMessageBox.Icon.Critical,
                        "Ошибка обновления" if self.lang == "ru" else "Update error",
                        (
                            "Не удалось дождаться завершения фоновых операций. "
                            "Обновление GUI не запущено."
                            if self.lang == "ru" else
                            "Background operations did not stop in time. "
                            "The GUI update was not started."
                        ),
                    )
                    return
                QTimer.singleShot(100, self._finish_shutdown_when_idle)
                return
        stop_error = ""
        try:
            _force_stop_blockers(self.core_dir)
        except Exception as error:
            stop_error = str(error)

        if getattr(self, "_gui_update_shutdown", False):
            try:
                winws_still_running = _is_winws_running_silent()
            except Exception:
                winws_still_running = True
            if stop_error or winws_still_running:
                self._exiting = False
                self._gui_update_shutdown = False
                self._pending_gui_updater_args = []
                self._pending_gui_updater_install_dir = ""
                APP_SHUTTING_DOWN.clear()
                self.show()
                _show_centered_message(
                    self,
                    QMessageBox.Icon.Critical,
                    "Ошибка обновления" if self.lang == "ru" else "Update error",
                    (
                        "Не удалось полностью остановить обход. Обновление GUI не запущено.\n\n"
                        + (stop_error or "winws всё ещё работает.")
                    )
                    if self.lang == "ru" else
                    (
                        "The bypass could not be stopped completely. The GUI update was not started.\n\n"
                        + (stop_error or "winws is still running.")
                    ),
                )
                return

        # Closing IPC makes the service stop its job. A GUI crash closes IPC in
        # the kernel too, independently of Python/Qt cleanup.
        if not getattr(self, "_system_shutdown_requested", False):
            try:
                self._release_adaptive_profile_hosts()
            except Exception:
                pass

        if not getattr(self, "_system_shutdown_requested", False):
            try:
                self.telegram_proxy.stop()
            except Exception:
                pass

        if getattr(self, "_gui_update_shutdown", False):
            _bypass_service.disconnect()
        else:
            _bypass_service.close()

        if getattr(self, "_gui_update_shutdown", False):
            updater_args = list(getattr(self, "_pending_gui_updater_args", []) or [])
            install_dir = str(getattr(self, "_pending_gui_updater_install_dir", "") or "")
            try:
                self.settings.sync()
                _launch_gui_updater_process(updater_args, install_dir)
            except Exception as error:
                self._exiting = False
                self._gui_update_shutdown = False
                APP_SHUTTING_DOWN.clear()
                self.show()
                _show_centered_message(
                    self,
                    QMessageBox.Icon.Critical,
                    "Ошибка обновления" if self.lang == "ru" else "Update error",
                    str(error),
                )
                return

        try:
            if self.tray is not None:
                self.tray.hide()
        except Exception:
            pass

        QApplication.instance().quit()

    def tray_exit(self):
        if self.is_winws_running():
            title = "Выход из программы" if self.lang == 'ru' else "Exit"
            text = (
                "Обход сейчас активен. Остановить его и выйти?"
                if self.lang == 'ru'
                else "Bypass is active. Stop it and exit?"
            )

            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setText(text)
            msg.setIcon(QMessageBox.Icon.Warning)

            if self.lang == 'ru':
                btn_yes = msg.addButton("Да", QMessageBox.ButtonRole.YesRole)
                btn_no = msg.addButton("Нет", QMessageBox.ButtonRole.NoRole)
            else:
                btn_yes = msg.addButton("Yes", QMessageBox.ButtonRole.YesRole)
                btn_no = msg.addButton("No", QMessageBox.ButtonRole.NoRole)

            msg.exec()
            if msg.clickedButton() != btn_yes:
                return

        self._shutdown_and_quit()

    @staticmethod
    def _profile_sort_key(name: str):
        alt_re = re.compile(r"\(\s*([A-Za-z\-]*ALT)\s*(\d*)\s*\)\s*$", re.IGNORECASE)
        value = str(name or "").strip()
        match = alt_re.search(value)
        if match:
            alt_tag = (match.group(1) or "").casefold()
            number = (match.group(2) or "").strip()
            alt_number = int(number) if number.isdigit() else 1
            base = value[:match.start()].rstrip()
            parts = [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", base)]
            return (parts, 0, alt_tag, alt_number)
        parts = [int(part) if part.isdigit() else part.casefold() for part in re.split(r"(\d+)", value)]
        return (parts, 1, "", 0)

    @staticmethod
    def _next_unique_profile_label(name: str, occupied: set[str]) -> str:
        candidate = str(name or "").strip() or "Profile"
        if candidate.casefold() not in occupied:
            return candidate
        number = 2
        while f"{candidate} [{number}]".casefold() in occupied:
            number += 1
        return f"{candidate} [{number}]"

    def _active_profile_source(self) -> dict:
        return self.user_presets if getattr(self, "profile_scope", "standard") == "user" else self.standard_presets

    def _profile_script_path(self, profile: str) -> str:
        filename = str(getattr(self, "presets", {}).get(profile, "") or "")
        if not filename:
            return ""
        return filename if os.path.isabs(filename) else os.path.join(self.core_dir, filename)

    def _populate_profile_combo(self, preferred: str = "") -> None:
        combo = getattr(self, "cb", None)
        if combo is None:
            return
        scope = "user" if getattr(self, "profile_scope", "standard") == "user" else "standard"
        source = self.user_presets if scope == "user" else self.standard_presets
        preferred = str(preferred or "")
        if not preferred:
            preferred = str(
                getattr(self, "last_user_profile", "") if scope == "user"
                else getattr(self, "last_standard_profile", getattr(self, "last_profile", ""))
            )

        combo.blockSignals(True)
        try:
            if isinstance(combo, ProfileComboBox):
                combo.setProfileMode(scope)
                combo.setEmptyDisplayText(
                    "Сгенерируйте или добавьте стратегию" if scope == "user" and not source else ""
                )
            combo.clear()

            if scope == "user" and isinstance(combo, ProfileComboBox):
                combo.addItem("Добавить .bat")
                combo.setItemData(0, PROFILE_ROW_ADD, PROFILE_ROW_KIND_ROLE)
                combo.setItemData(0, "", PROFILE_ROW_PATH_ROLE)
                add_item = combo.model().item(0)
                if add_item is not None:
                    # It is a real button row handled by the viewport filter,
                    # never a selectable profile value.
                    add_item.setFlags(Qt.ItemFlag.NoItemFlags)
                if not source:
                    combo.addItem("Сгенерируйте или добавьте стратегию")
                    combo.setItemData(1, PROFILE_ROW_EMPTY, PROFILE_ROW_KIND_ROLE)
                    combo.setItemData(1, "", PROFILE_ROW_PATH_ROLE)
                    item = combo.model().item(1)
                    if item is not None:
                        item.setFlags(Qt.ItemFlag.NoItemFlags)
                    combo.setCurrentIndex(-1)
                else:
                    for name, path in source.items():
                        combo.addItem(name)
                        row = combo.count() - 1
                        combo.setItemData(row, PROFILE_ROW_PROFILE, PROFILE_ROW_KIND_ROLE)
                        combo.setItemData(row, path, PROFILE_ROW_PATH_ROLE)
                    if preferred in source:
                        combo.setCurrentText(preferred)
                    else:
                        combo.setCurrentIndex(1)
            else:
                combo.addItems(source.keys())
                if preferred in source:
                    combo.setCurrentText(preferred)
                elif combo.count():
                    combo.setCurrentIndex(0)
                else:
                    combo.setCurrentIndex(-1)
        finally:
            combo.blockSignals(False)

    def _set_profile_scope(self, scope: str) -> None:
        scope = "user" if scope == "user" else "standard"
        if scope == getattr(self, "profile_scope", "standard"):
            return
        self.profile_scope = scope
        self.settings.setValue("profile_scope", scope)
        switch = getattr(self, "profile_scope_switch", None)
        if switch is not None:
            switch.setScope(scope, animated=True, emit=False)
        self._populate_profile_combo()
        if getattr(self, "preset_menu", None) is not None:
            self.update_tray_presets()
        if getattr(self, "action_start", None) is not None:
            self.update_tray_status()

    def reload_presets(self):
        standard = {"General": "general.bat"}
        core_items = []
        try:
            for filename in os.listdir(self.core_dir):
                low = filename.casefold()
                if (
                    not low.endswith(".bat")
                    or low.startswith("__noupdate__")
                    or low in ("general.bat", "discord.bat", "service.bat", "cloudflare_switch.bat")
                ):
                    continue
                core_items.append((Path(filename).stem, filename))
        except (FileNotFoundError, OSError):
            pass

        for name, filename in sorted(core_items, key=lambda item: MainWindow._profile_sort_key(item[0])):
            standard[name] = filename

        user_items = []
        try:
            profile_dir = Path(USER_PROFILE_DIR)
            if profile_dir.is_dir():
                for item in profile_dir.iterdir():
                    if item.is_file() and item.suffix.casefold() == ".bat":
                        user_items.append((item.stem, str(item.resolve())))
        except OSError as exc:
            print("User profile scan error:", exc)

        occupied = {name.casefold() for name in standard}
        user = {}
        for name, filename in sorted(user_items, key=lambda item: MainWindow._profile_sort_key(item[0])):
            display_name = MainWindow._next_unique_profile_label(name, occupied)
            user[display_name] = filename
            occupied.add(display_name.casefold())

        self.standard_presets = standard
        self.user_presets = user
        self.presets = {**standard, **user}
        MainWindow._populate_profile_combo(self)

        if getattr(self, "preset_menu", None) is not None:
            self.update_tray_presets()
        if getattr(self, "action_start", None) is not None:
            self.update_tray_status()

    @staticmethod
    def _user_profile_root() -> Path:
        return Path(USER_PROFILE_DIR).resolve()

    def _user_profile_action_path(self, display_name: str, reported_path: str) -> Path | None:
        expected = str(getattr(self, "user_presets", {}).get(display_name, "") or "")
        if not expected or not reported_path:
            return None
        try:
            candidate = Path(reported_path).resolve()
            root = self._user_profile_root()
            if candidate != Path(expected).resolve() or candidate.parent != root or candidate.suffix.casefold() != ".bat":
                return None
            return candidate
        except (OSError, RuntimeError):
            return None

    def _show_user_profile_message(self, text: str) -> None:
        message = QMessageBox(self)
        message.setWindowTitle("Пользовательские профили" if self.lang == "ru" else "User profiles")
        message.setIcon(QMessageBox.Icon.NoIcon)
        message.setText(text)
        message.addButton("OK", QMessageBox.ButtonRole.AcceptRole)
        message.exec()

    def _add_user_profile(self) -> None:
        source_name, _ = QFileDialog.getOpenFileName(
            self,
            "Добавить стратегию" if self.lang == "ru" else "Add strategy",
            "",
            "BAT files (*.bat)",
        )
        if not source_name:
            return
        source = Path(source_name)
        if not source.is_file() or source.suffix.casefold() != ".bat":
            self._show_user_profile_message(
                "Выберите файл стратегии в формате .bat." if self.lang == "ru" else "Select a strategy file in .bat format."
            )
            return

        try:
            destination_dir = self._user_profile_root()
            destination_dir.mkdir(parents=True, exist_ok=True)
            destination = destination_dir / source.name
            number = 2
            while destination.exists():
                destination = destination_dir / f"{source.stem} ({number}){source.suffix}"
                number += 1
            shutil.copy2(source, destination)
        except (OSError, shutil.Error) as exc:
            self._show_user_profile_message(
                f"Не удалось добавить стратегию:\n{exc}" if self.lang == "ru" else f"Could not add the strategy:\n{exc}"
            )
            return

        self.reload_presets()
        profile_name = self._profile_name_for_bat(str(destination))
        self._set_profile_scope("user")
        if profile_name:
            self.last_user_profile = profile_name
            self.last_profile = profile_name
            self.settings.setValue("last_user_profile", profile_name)
            self.settings.setValue("last_profile", profile_name)
            self._populate_profile_combo(profile_name)
        self.settings.sync()

    def _rename_user_profile(self, display_name: str, reported_path: str) -> None:
        source = self._user_profile_action_path(display_name, reported_path)
        if source is None or not source.exists():
            self.reload_presets()
            return
        if getattr(self, "toggle_btn", None) is not None and self.toggle_btn.isChecked():
            self._show_user_profile_message(
                "Сначала выключите обход, затем измените профиль." if self.lang == "ru" else "Turn off the bypass before renaming a profile."
            )
            return

        dialog = TextInputDialog(
            "Переименовать стратегию" if self.lang == "ru" else "Rename strategy",
            "Новое название" if self.lang == "ru" else "New name",
            "Сохранить" if self.lang == "ru" else "Save",
            "Отмена" if self.lang == "ru" else "Cancel",
            self,
        )
        dialog.setTextValue(source.stem)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        ok, error, filename = validate_strategy_name(dialog.textValue(), lang=self.lang)
        if not ok:
            self._show_user_profile_message(error)
            return
        destination = self._user_profile_root() / filename
        try:
            if destination.resolve() == source.resolve():
                return
            if destination.exists():
                self._show_user_profile_message(
                    "Стратегия с таким именем уже существует." if self.lang == "ru" else "A strategy with this name already exists."
                )
                return
            source.rename(destination)
        except OSError as exc:
            self._show_user_profile_message(
                f"Не удалось переименовать стратегию:\n{exc}" if self.lang == "ru" else f"Could not rename the strategy:\n{exc}"
            )
            return

        self.reload_presets()
        profile_name = self._profile_name_for_bat(str(destination))
        self._set_profile_scope("user")
        if profile_name:
            self.last_user_profile = profile_name
            self.last_profile = profile_name
            self.settings.setValue("last_user_profile", profile_name)
            self.settings.setValue("last_profile", profile_name)
            self._populate_profile_combo(profile_name)
        self.settings.sync()

    def _delete_user_profile(self, display_name: str, reported_path: str) -> None:
        source = self._user_profile_action_path(display_name, reported_path)
        if source is None or not source.exists():
            self.reload_presets()
            return
        if getattr(self, "toggle_btn", None) is not None and self.toggle_btn.isChecked():
            self._show_user_profile_message(
                "Сначала выключите обход, затем удалите профиль." if self.lang == "ru" else "Turn off the bypass before deleting a profile."
            )
            return

        prompt = QMessageBox(self)
        prompt.setWindowTitle("Удалить стратегию" if self.lang == "ru" else "Delete strategy")
        prompt.setIcon(QMessageBox.Icon.NoIcon)
        prompt.setText(
            f"Удалить «{source.stem}»?" if self.lang == "ru" else f"Delete “{source.stem}”?"
        )
        prompt.setInformativeText(
            "Файл стратегии будет удалён." if self.lang == "ru" else "The strategy file will be removed."
        )
        cancel = prompt.addButton("Отмена" if self.lang == "ru" else "Cancel", QMessageBox.ButtonRole.RejectRole)
        remove = prompt.addButton("Удалить" if self.lang == "ru" else "Delete", QMessageBox.ButtonRole.DestructiveRole)
        prompt.setDefaultButton(cancel)
        prompt.exec()
        if prompt.clickedButton() is not remove:
            return

        try:
            source.unlink()
        except OSError as exc:
            self._show_user_profile_message(
                f"Не удалось удалить стратегию:\n{exc}" if self.lang == "ru" else f"Could not delete the strategy:\n{exc}"
            )
            return

        if self.last_user_profile == display_name:
            self.last_user_profile = ""
            self.settings.setValue("last_user_profile", "")
        self.reload_presets()
        self._set_profile_scope("user")
        self.settings.sync()

    def on_profile_changed(self, text):
        text = str(text or "")
        if not text or text not in self.presets:
            self.update_tray_status()
            return
        self.last_profile = text
        self.settings.setValue("last_profile", text)
        if getattr(self, "profile_scope", "standard") == "user":
            self.last_user_profile = text
            self.settings.setValue("last_user_profile", text)
        else:
            self.last_standard_profile = text
            self.settings.setValue("last_standard_profile", text)

        if getattr(self, "_in_init", False):
            self.update_tray_status()
            return

        if getattr(self, "_switching_profile", False):
            self.update_tray_status()
            return

        self._switching_profile = True
        try:
            if self.toggle_btn.isChecked():

                self.toggle_btn.setChecked(False)
                self.on_toggle(False)


                self.toggle_btn.setChecked(True)
                self.on_toggle(True)
            else:

                self.toggle_btn.setChecked(True)
                self.on_toggle(True)
        finally:
            self._switching_profile = False

        self.update_tray_status()

    def unblock_executables(self):
        bin_dir = os.path.join(self.core_dir, 'bin')
        if not os.path.exists(bin_dir):
            return

        for file in os.listdir(bin_dir):
            if file.lower().endswith('.exe'):
                exe_path = os.path.join(bin_dir, file)
                try:
                    subprocess.run([
                        "powershell", "-Command",
                        f"if (Test-Path '{exe_path}') {{ Unblock-File -Path '{exe_path}' }}"
                    ], check=True)
                    print(f"Unblocked: {exe_path}")
                except Exception as e:
                    print(f"Failed to unblock {exe_path}: {e}")

    def _side_dialog_target_pos(self, dialog: QDialog, side: str, gap: int = 8) -> QPoint:
        main = self.frameGeometry()
        y = main.top()

        if side == "left":
            x = main.left() - gap - dialog.width()
        else:
            x = main.right() + gap

        return QPoint(int(x), int(y))

    def _side_dialog_start_pos(self, dialog: QDialog, side: str) -> QPoint:
        main = self.frameGeometry()
        y = main.top()

        if side == "left":
            x = main.left() + 10
        else:
            x = main.right() - dialog.width() - 10

        return QPoint(int(x), int(y))

    def _animate_side_dialog_open(self, dialog: QDialog, side: str, gap: int = 8) -> None:
        end_pos = self._side_dialog_target_pos(dialog, side, gap=gap)
        start_pos = self._side_dialog_start_pos(dialog, side)

        dialog.move(start_pos)
        try:
            dialog.setWindowOpacity(0.0)
        except Exception:
            pass

        pos_anim = QPropertyAnimation(dialog, b"pos", dialog)
        pos_anim.setDuration(260)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(dialog, b"windowOpacity", dialog)
        op_anim.setDuration(220)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(dialog)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)

        # чтобы анимации не умирали сборщиком мусора
        dialog._open_anim_grp = grp
        dialog._open_anim_pos = pos_anim  #
        dialog._open_anim_op = op_anim

        grp.start()

    def _animate_dialog_move(self, dialog: QDialog, end_pos: QPoint, duration: int = 260) -> None:
        pos_anim = QPropertyAnimation(dialog, b"pos", dialog)
        pos_anim.setDuration(duration)
        pos_anim.setStartValue(dialog.pos())
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        dialog._move_anim = pos_anim
        pos_anim.start()

    def _bottom_dialog_target_pos(self, dialog: QDialog, gap: int = 8) -> QPoint:
        main = self.frameGeometry()
        x = main.left()
        y = main.bottom() + gap
        return QPoint(int(x), int(y))

    def _bottom_dialog_start_pos(self, dialog: QDialog) -> QPoint:
        main = self.frameGeometry()
        x = main.left()
        y = int(main.center().y() - dialog.height() / 2) + 18
        return QPoint(int(x), int(y))

    def _animate_bottom_dialog_open(self, dialog: QDialog, gap: int = 8) -> None:
        end_pos = self._bottom_dialog_target_pos(dialog, gap=gap)
        start_pos = self._bottom_dialog_start_pos(dialog)

        dialog.move(start_pos)
        try:
            dialog.setWindowOpacity(0.0)
        except Exception:
            pass

        pos_anim = QPropertyAnimation(dialog, b"pos", dialog)
        pos_anim.setDuration(280)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(dialog, b"windowOpacity", dialog)
        op_anim.setDuration(220)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(dialog)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)

        dialog._open_anim_grp = grp
        dialog._open_anim_pos = pos_anim
        dialog._open_anim_op = op_anim

        grp.start()

    def refresh_runtime_lists_after_user_change(self):
        _rebuild_runtime_lists(self.settings)

    def _restore_instruction_position_if_needed(self, gap: int = 8) -> None:
        instruction = self._instruction_dialog
        if instruction is None or not instruction.isVisible():
            return

        main_geom = self.frameGeometry()
        instruction_target = QPoint(
            int(main_geom.left() - gap - instruction.width()),
            int(main_geom.top()),
        )
        self._animate_dialog_move(instruction, instruction_target)

    def open_site_manager(self):
        if self._site_manager_dlg is not None and self._site_manager_dlg.isVisible():
            self._site_manager_dlg.raise_()
            self._site_manager_dlg.activateWindow()
            return

        gap = 8
        dlg = SiteManagerDialog(self, self.settings)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        self._site_manager_dlg = dlg
        def _after_close(_=0):
            try:
                self._site_manager_dlg = None
            except Exception:
                pass
            self._restore_instruction_position_if_needed(gap=gap)

        dlg.finished.connect(_after_close)
        dlg.show()

        main_geom = self.frameGeometry()
        target_x = main_geom.left() - gap - dlg.width()
        target_y = main_geom.top()
        target_pos = QPoint(int(target_x), int(target_y))

        instruction = self._instruction_dialog
        if instruction is not None and instruction.isVisible():
            instruction_target = QPoint(
                int(target_pos.x() - gap - instruction.width()),
                int(target_y),
            )
            self._animate_dialog_move(instruction, instruction_target)

        start_pos = self._side_dialog_start_pos(dlg, side="left")
        dlg.move(start_pos)
        try:
            dlg.setWindowOpacity(0.0)
        except Exception:
            pass

        pos_anim = QPropertyAnimation(dlg, b"pos", dlg)
        pos_anim.setDuration(260)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(target_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(dlg, b"windowOpacity", dlg)
        op_anim.setDuration(220)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(dlg)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)

        dlg._open_anim_grp = grp
        dlg._open_anim_pos = pos_anim
        dlg._open_anim_op = op_anim

        grp.start()

    def open_instruction(self):
        if self._instruction_dialog is not None and self._instruction_dialog.isVisible():
            self._instruction_dialog.raise_()
            self._instruction_dialog.activateWindow()
            return

        dialog = StyledDialog(self)
        dialog.setWindowTitle(self.t('Instruction'))

        dialog.setFixedSize(450, 530 if self.lang == 'ru' else 500)

        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        dialog.setModal(False)

        frame = _make_window_root_layout(dialog)
        dialog.install_title_bar(frame, dialog.windowTitle())
        layout = _make_window_content_layout(frame, dialog, margins=(12, 10, 12, 12), spacing=8)

        lists_dir = USER_DIR
        lists_url = lists_dir.replace("\\", "/")
        instruction_html = self.t('Instruction Text', lists_url, lists_dir)

        browser = QTextBrowser(dialog)
        browser.setHtml(
            "<html><body style='font-family:Segoe UI; font-size:10.5pt; line-height:1.34;'>"
            f"{instruction_html}"
            "</body></html>"
        )
        browser.setOpenExternalLinks(False)
        browser.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        browser.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        browser.anchorClicked.connect(self._handle_instruction_link)
        browser.setStyleSheet("""
            QTextBrowser {
                border: 1px solid rgba(120,120,120,70);
                border-radius: 8px;
                padding: 8px 10px;
                background: rgba(255,255,255,0.025);
            }
            QScrollBar:vertical {
                background: rgba(255,255,255,0.04);
                width: 11px;
                margin: 3px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical {
                background: #2db45f;
                min-height: 34px;
                border-radius: 5px;
            }
            QScrollBar::handle:vertical:hover { background: #47d078; }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
                border: none;
                background: transparent;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
        """)
        layout.addWidget(browser)

        scroll_hint = QLabel(
            "↓ Листайте вниз, там есть ещё пункты"
            if self.lang == "ru" else
            "↓ Scroll down for more"
        )
        scroll_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        scroll_hint.setStyleSheet("""
            QLabel {
                color: rgba(45,180,95,0.98);
                font-weight: 700;
                padding: 5px 8px;
                border: 1px solid rgba(45,180,95,0.35);
                border-radius: 8px;
                background: rgba(45,180,95,0.08);
            }
        """)
        layout.addWidget(scroll_hint)

        def _update_instruction_scroll_hint():
            try:
                sb = browser.verticalScrollBar()
                scroll_hint.setVisible(sb.maximum() > 0 and sb.value() < sb.maximum() - 4)
            except Exception:
                pass

        browser.verticalScrollBar().valueChanged.connect(lambda _=0: _update_instruction_scroll_hint())
        QTimer.singleShot(0, _update_instruction_scroll_hint)
        QTimer.singleShot(250, _update_instruction_scroll_hint)

        self._instruction_dialog = dialog
        dialog.finished.connect(lambda _=0: setattr(self, "_instruction_dialog", None))
        dialog.show()

        gap = 8
        main_geom = self.frameGeometry()
        target_y = main_geom.top()

        manager = self._site_manager_dlg
        if manager is not None and manager.isVisible():
            manager_target = QPoint(
                int(main_geom.left() - gap - manager.width()),
                int(target_y),
            )
            self._animate_dialog_move(manager, manager_target)
            instruction_target = QPoint(
                int(manager_target.x() - gap - dialog.width()),
                int(target_y),
            )
        else:
            instruction_target = QPoint(
                int(main_geom.left() - gap - dialog.width()),
                int(target_y),
            )

        start_pos = self._side_dialog_start_pos(dialog, side="left")
        dialog.move(start_pos)
        try:
            dialog.setWindowOpacity(0.0)
        except Exception:
            pass

        pos_anim = QPropertyAnimation(dialog, b"pos", dialog)
        pos_anim.setDuration(260)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(instruction_target)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(dialog, b"windowOpacity", dialog)
        op_anim.setDuration(220)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(dialog)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)

        dialog._open_anim_grp = grp
        dialog._open_anim_pos = pos_anim
        dialog._open_anim_op = op_anim

        grp.start()

    def _handle_instruction_link(self, url: QUrl) -> None:
        if not url.isValid():
            return
        if url.scheme() == "app" and url.host() == "site-manager-tutorial":
            self.open_site_manager_tutorial_from_instruction()
            return
        instruction = self._instruction_dialog
        if instruction is not None and instruction.isVisible():
            instruction.close()
        QDesktopServices.openUrl(url)

    def open_site_manager_tutorial_from_instruction(self) -> None:
        instruction = self._instruction_dialog
        if instruction is not None and instruction.isVisible():
            instruction.close()

        manager_was_closed = not (self._site_manager_dlg is not None and self._site_manager_dlg.isVisible())
        self.open_site_manager()

        def _open_tutorial():
            if self._site_manager_dlg is not None:
                self._site_manager_dlg.open_tutorial()

        if manager_was_closed:
            QTimer.singleShot(320, _open_tutorial)
        else:
            _open_tutorial()

    def t(self, key, *args):
        return translations[self.lang].get(key, key).format(*args)

    def change_lang(self, lang_code):
        self.lang = lang_code
        self.settings.setValue('lang', lang_code)
        self.retranslate_ui()
        self.retranslate_tray()
        self.update_tray_presets()
        self.update_tray_status()

        try:
            if self._site_manager_dlg is not None and self._site_manager_dlg.isVisible():
                self._site_manager_dlg.close()
                self._site_manager_dlg = None
        except Exception:
            pass

    def init_ui(self):
        self.setFixedSize(300, 390)
        self.setObjectName("mainWindowRoot")
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.FramelessWindowHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)

        frame = _make_window_root_layout(self)

        self.title_bar = CustomTitleBar("Zapret GUI", self, allow_minimize=True)
        try:
            self.title_bar.min_btn.clicked.disconnect()
        except Exception:
            pass
        self.title_bar.min_btn.clicked.connect(self.hide)
        frame.addWidget(self.title_bar)
        layout = _make_window_content_layout(frame, self, margins=(12, 6, 12, 8), spacing=5)
        layout.setAlignment(Qt.AlignmentFlag.AlignTop)

        self.status_lbl = QLabel()
        self.status_lbl.setObjectName("statusLabel")
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_lbl.setFixedHeight(18)
        self.status_lbl.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.status_lbl)

        icon_off_path = _bundled_path('flags', 'toggle-off.ico')
        icon_on_path = _bundled_path('flags', 'toggle-on.ico')

        icon_off = QIcon(icon_off_path) if os.path.exists(icon_off_path) else QIcon()
        icon_on = QIcon(icon_on_path) if os.path.exists(icon_on_path) else QIcon()

        legacy_path = _bundled_path('flags', 'toggle.ico')
        if icon_off.isNull() or icon_on.isNull():
            legacy = QIcon(legacy_path) if os.path.exists(legacy_path) else QIcon.fromTheme("media-playback-start")
            if icon_off.isNull():
                icon_off = legacy
            if icon_on.isNull():
                icon_on = legacy

        self.toggle_btn = AnimatedPowerToggleButton(icon_off=icon_off, icon_on=icon_on, parent=self)
        self.toggle_btn.setFixedSize(110, 110)
        self.toggle_btn.clicked.connect(self.on_toggle)

        self.auto_btn = SmallCircleButton("A", "text", self)
        self.auto_btn.setFixedSize(28, 28)
        self.auto_btn.setToolTip("Режимы автоматического подбора" if self.lang == "ru" else "Automatic selection modes")
        self.auto_btn.clicked.connect(self.on_auto_pick_profile)

        self.auto_info_btn = SmallCircleButton("i", "text", self)
        self.auto_info_btn.setFixedSize(24, 24)
        self.auto_info_btn.setToolTip(
            "Последняя информация автоподбора" if self.lang == "ru" else "Latest auto-selection information"
        )
        self.auto_info_btn.clicked.connect(self.show_autotest_info)
        self.auto_info_btn.hide()

        self.ai_mode_btn = SmallCircleButton("Ai", "text", self)
        self.ai_mode_btn.setCheckable(True)
        self.ai_mode_btn.setFixedSize(28, 28)
        self.ai_mode_btn.clicked.connect(self.on_ai_mode_clicked)

        self.telegram_mode_btn = SmallCircleButton("", "pixmap", self)
        self.telegram_mode_btn.setCheckable(True)
        self.telegram_mode_btn.setFixedSize(32, 32)
        tg_icon_path = _bundled_path("flags", "tg.png")
        if not os.path.exists(tg_icon_path):
            tg_icon_path = os.path.join(APP_DIR, "flags", "tg.png")
        self.telegram_mode_btn.setPixmapPath(tg_icon_path)
        self.telegram_mode_btn.setPixmapTuning(scale=0.86, offset_x=0, offset_y=0)
        self.telegram_mode_btn.clicked.connect(self.on_telegram_mode_clicked)

        self.telegram_help_btn = SmallCircleButton("?", "text", self)
        self.telegram_help_btn.setFixedSize(22, 22)
        self.telegram_help_btn.clicked.connect(self.show_telegram_mode_help)

        self.game_settings_btn = SmallCircleButton("", "gear")
        self.game_settings_btn.setFixedSize(24, 24)
        self.game_settings_btn.clicked.connect(self.open_game_mode_settings)

        self.game_mode_btn = SmallCircleButton("", "pixmap")
        self.game_mode_btn.setCheckable(True)
        self.game_mode_btn.setFixedSize(32, 32)
        joy_icon_path = _bundled_path("flags", "joy.png")
        if not os.path.exists(joy_icon_path):
            joy_icon_path = os.path.join(APP_DIR, "flags", "joy.png")
        if os.path.exists(joy_icon_path):
            self.game_mode_btn.setPixmapPath(joy_icon_path)
            self.game_mode_btn.setPixmapTuning(scale=0.92, offset_x=0, offset_y=0)
        else:
            self.game_mode_btn.setIconKind("gamepad")
        self.game_mode_btn.clicked.connect(self.on_game_mode_clicked)

        top_widget = QWidget(self)
        top_widget.setFixedHeight(34)
        top_row = QHBoxLayout(top_widget)
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(0)

        # Matching side slots keep the source switch truly centred between
        # automatic selection and game-mode controls.
        left_slot = QWidget(top_widget)
        left_slot.setFixedWidth(60)
        left_row = QHBoxLayout(left_slot)
        left_row.setContentsMargins(0, 0, 0, 0)
        left_row.setSpacing(4)
        left_row.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        left_row.addWidget(self.auto_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        left_row.addWidget(self.auto_info_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        game_slot = QWidget(top_widget)
        game_slot.setFixedWidth(60)
        game_row = QHBoxLayout(game_slot)
        game_row.setContentsMargins(0, 0, 0, 0)
        game_row.setSpacing(4)
        game_row.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        game_row.addWidget(self.game_settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        game_row.addWidget(self.game_mode_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.profile_scope_switch = ProfileScopeSwitch(self.profile_scope, top_widget)
        self.profile_scope_switch.scopeChanged.connect(self._set_profile_scope)
        top_row.addWidget(left_slot, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addStretch(1)
        top_row.addWidget(self.profile_scope_switch, 0, Qt.AlignmentFlag.AlignCenter)
        top_row.addStretch(1)
        top_row.addWidget(game_slot, 0, Qt.AlignmentFlag.AlignVCenter)

        toggle_widget = QWidget(self)
        toggle_widget.setFixedHeight(114)
        hl = QHBoxLayout(toggle_widget)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addStretch()
        hl.addWidget(self.toggle_btn)
        hl.addStretch()
        layout.addWidget(toggle_widget)
        layout.addWidget(top_widget)

        self.cb = ProfileComboBox()
        self.cb.setObjectName("profileCombo")
        self.cb.setFixedHeight(31)
        self.cb.addRequested.connect(self._add_user_profile)
        self.cb.renameRequested.connect(self._rename_user_profile)
        self.cb.deleteRequested.connect(self._delete_user_profile)
        self.reload_presets()
        self.cb.currentTextChanged.connect(self.on_profile_changed)
        layout.addWidget(self.cb)

        self.settings_btn = AnimatedActionButton()
        self.settings_btn.setObjectName("primaryActionButton")
        self.settings_btn.setFixedHeight(32)
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        self.instruction_btn = AnimatedActionButton("Инструкция")
        self.instruction_btn.setObjectName("primaryActionButton")
        self.instruction_btn.setFixedHeight(32)
        self.instruction_btn.clicked.connect(self.open_instruction)
        layout.addWidget(self.instruction_btn)

        self.site_manager_btn = AnimatedActionButton("Менеджер сайтов" if self.lang == "ru" else "Site manager")
        self.site_manager_btn.setObjectName("primaryActionButton")
        self.site_manager_btn.setFixedHeight(32)
        self.site_manager_btn.clicked.connect(self.open_site_manager)
        layout.addWidget(self.site_manager_btn)

        self.powered_lbl = QLabel(
            'Powered by '
            '<span style="color:#2ecc71;">Medvedeff</span>'
            ' & '
            '<span style="color:#e74c3c;">Zapret</span>'
            ' & '
            '<span style="color:#2ecc71;">Flowseal</span>'
        )

        self.powered_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.powered_lbl.setObjectName("poweredLabel")
        layout.addWidget(self.powered_lbl)

        self.blink_on = False
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.update_blink)
        self.blink_timer.start(800)
        self._position_ai_mode_button()
        self._position_telegram_mode_button()
        self.ai_mode_btn.raise_()
        self.telegram_help_btn.raise_()
        self.telegram_mode_btn.raise_()
        self._update_small_circle_buttons_ui()
        self._update_ai_mode_ui()
        self._update_telegram_mode_ui()
        self._update_game_mode_ui()
        self._apply_main_window_style()
        QTimer.singleShot(0, self._position_overlay_mode_buttons)

    def _status_overlay_y(self, button_height: int, fallback_y: int) -> int:
        title_bottom = 0
        if hasattr(self, "title_bar"):
            try:
                title_bottom = int(self.title_bar.y() + self.title_bar.height())
            except Exception:
                title_bottom = 0

        status_y = fallback_y
        status_h = 18
        if hasattr(self, "status_lbl"):
            try:
                status_h = max(1, int(self.status_lbl.height() or self.status_lbl.sizeHint().height() or 18))
                candidate_y = int(self.status_lbl.y())
                max_reasonable_y = title_bottom + 36
                if title_bottom <= candidate_y <= max_reasonable_y:
                    status_y = candidate_y
                else:
                    status_y = title_bottom + 6
            except Exception:
                status_y = title_bottom + 6

        y = int(status_y + (status_h - int(button_height)) / 2)
        min_y = max(8, title_bottom + 4)
        max_y = max(min_y, int(self.height()) - int(button_height) - 8)
        return max(min_y, min(y, max_y))

    def _schedule_overlay_mode_buttons_position(self) -> None:
        self._position_overlay_mode_buttons()
        QTimer.singleShot(0, self._position_overlay_mode_buttons)

    def _apply_main_window_style(self) -> None:
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setStyleSheet("""
            QWidget#mainWindowRoot {
                color: #f2f2f2;
            }
            QLabel#statusLabel {
                color: #f4f4f4;
                font-size: 12px;
                font-weight: 600;
                padding: 0;
                margin: 0;
                min-height: 18px;
            }
            QLabel#poweredLabel {
                color: rgba(220,220,220,0.94);
                font-size: 11px;
                padding-top: 0;
            }
            QComboBox#profileCombo, QComboBox#stableComboBox {
                min-height: 31px;
                max-height: 31px;
                padding: 0;
                border: none;
                border-radius: 8px;
                background: transparent;
                color: #f5f5f5;
                selection-background-color: #2db45f;
                selection-color: white;
                font-size: 12px;
                combobox-popup: 0;
            }
            QComboBox#profileCombo:hover, QComboBox#stableComboBox:hover {
                background: transparent;
            }
            QComboBox#profileCombo:on, QComboBox#stableComboBox:on {
                background: transparent;
            }
            QComboBox#profileCombo::drop-down, QComboBox#stableComboBox::drop-down {
                width: 0px;
                border: none;
                background: transparent;
            }
            QComboBox#profileCombo::down-arrow, QComboBox#stableComboBox::down-arrow {
                image: none;
                width: 0px;
                height: 0px;
            }
            QPushButton#primaryActionButton {
                min-height: 32px;
                max-height: 32px;
                border: 1px solid rgba(255,255,255,0.12);
                border-radius: 8px;
                background: rgba(255,255,255,0.04);
                color: #f6f6f6;
                font-size: 12px;
                font-weight: 600;
                padding: 0 10px;
            }
            QPushButton#primaryActionButton:hover {
                border-color: rgba(255,255,255,0.18);
                background: rgba(255,255,255,0.06);
            }
            QPushButton#primaryActionButton:pressed {
                border-color: rgba(255,255,255,0.20);
                background: rgba(255,255,255,0.08);
            }
            QPushButton#primaryActionButton:disabled {
                color: #9e9e9e;
                border-color: rgba(255,255,255,0.08);
                background: rgba(255,255,255,0.025);
            }
        """)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_app_surface(painter, QRectF(self.rect()), accented=True)
        painter.end()

    def retranslate_ui(self):
        self.setWindowTitle('Zapret GUI')
        if hasattr(self, "title_bar"):
            self.title_bar.setTitle(self.windowTitle())
        if self.toggle_btn.isChecked():
            self.status_lbl.setText(self.t('On: {}', self.cb.currentText()))
        else:
            self.status_lbl.setText(self.t('Off'))
        self.settings_btn.setText(self.t('Settings'))
        self.instruction_btn.setText(self.t('Instruction'))
        self.site_manager_btn.setText("Менеджер сайтов" if self.lang == "ru" else "Site manager")
        if hasattr(self, "profile_source_label"):
            self.profile_source_label.setText("Профили" if self.lang == "ru" else "Profiles")
        self._position_ai_mode_button()
        self._position_telegram_mode_button()
        self._update_small_circle_buttons_ui()
        self._update_ai_mode_ui()
        self._update_telegram_mode_ui()
        self._update_game_mode_ui()
        self._schedule_overlay_mode_buttons_position()

    def _position_overlay_mode_buttons(self) -> None:
        try:
            if self.layout() is not None:
                self.layout().activate()
        except Exception:
            pass
        self._position_ai_mode_button()
        self._position_telegram_mode_button()

    def _position_ai_mode_button(self) -> None:
        if not hasattr(self, "ai_mode_btn"):
            return
        x = 12
        y = self._status_overlay_y(self.ai_mode_btn.height(), 40)
        self.ai_mode_btn.move(x, y)
        self.ai_mode_btn.raise_()

    def _position_telegram_mode_button(self) -> None:
        if not hasattr(self, "telegram_mode_btn"):
            return
        x = max(8, self.width() - self.telegram_mode_btn.width() - 12)
        y = self._status_overlay_y(self.telegram_mode_btn.height(), 38)
        self.telegram_mode_btn.move(x, y)
        self.telegram_mode_btn.raise_()
        if hasattr(self, "telegram_help_btn"):
            gap = 5
            help_y = y + int((self.telegram_mode_btn.height() - self.telegram_help_btn.height()) / 2)
            help_x = max(8, x - self.telegram_help_btn.width() - gap)
            self.telegram_help_btn.move(help_x, help_y)
            self.telegram_help_btn.raise_()

    def _apply_small_circle_button_state(self, button, active: bool, text: str | None = None, icon_kind: str | None = None) -> None:
        if button is None:
            return
        if text is not None:
            button.setText(text)
        if icon_kind is not None and hasattr(button, "setIconKind"):
            button.setIconKind(icon_kind)
        if hasattr(button, "setVisualActive"):
            button.setVisualActive(active)
        button.update()

    def _update_small_circle_buttons_ui(self) -> None:
        if hasattr(self, "auto_btn"):
            self._apply_small_circle_button_state(self.auto_btn, True, "A", "text")
            self.auto_btn.setToolTip("Режимы автоматического подбора" if self.lang == "ru" else "Automatic selection modes")

        if hasattr(self, "auto_info_btn"):
            self._apply_small_circle_button_state(self.auto_info_btn, True, "i", "text")
            self.auto_info_btn.setToolTip(
                "Последняя информация автоподбора"
                if self.lang == "ru" else
                "Latest auto-selection information"
            )

        if hasattr(self, "game_settings_btn"):
            self._apply_small_circle_button_state(self.game_settings_btn, True, "", "gear")

        if hasattr(self, "telegram_mode_btn"):
            self._apply_small_circle_button_state(
                self.telegram_mode_btn,
                bool(getattr(self, "telegram_mode_enabled", False)),
                "",
                "pixmap",
            )

        if hasattr(self, "telegram_help_btn"):
            self._apply_small_circle_button_state(self.telegram_help_btn, True, "?", "text")
            self.telegram_help_btn.setToolTip(
                "Как настроить Telegram Desktop"
                if self.lang == "ru" else
                "How to configure Telegram Desktop"
            )

    def _update_ai_mode_ui(self) -> None:
        if not hasattr(self, "ai_mode_btn"):
            return

        active = bool(self.dns_malw_link_active)
        busy = bool(self._dns_malw_link_busy)
        self.ai_mode_btn.setText("Ai")
        self.ai_mode_btn.blockSignals(True)
        self.ai_mode_btn.setChecked(active)
        self.ai_mode_btn.blockSignals(False)
        self.ai_mode_btn.setEnabled(not busy)
        if hasattr(self.ai_mode_btn, "setBusy"):
            self.ai_mode_btn.setBusy(busy)
        self._apply_small_circle_button_state(self.ai_mode_btn, active, "Ai", "text")

        if busy:
            tooltip = (
                "Ai DNS: выполняется настройка dns.malw.link"
                if self.lang == "ru" else
                "Ai DNS: configuring dns.malw.link"
            )
        elif active:
            tooltip = (
                "Ai DNS активен. Нажмите, чтобы восстановить предыдущие DNS-настройки."
                if self.lang == "ru" else
                "Ai DNS is active. Click to restore the previous DNS settings."
            )
        else:
            tooltip = (
                "Ai DNS: открывает доступ к недоступным нейросетям"
                if self.lang == "ru" else
                "Ai DNS: open access to restricted neural networks"
            )
        self.ai_mode_btn.setToolTip(tooltip)
        self.update_tray_status()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        _update_rounded_window_mask(self)
        self._position_overlay_mode_buttons()

    def showEvent(self, event):
        super().showEvent(event)
        QTimer.singleShot(0, self._resume_main_window_ui)

    def event(self, event):
        if event.type() in (QEvent.Type.LayoutRequest, QEvent.Type.ShowToParent):
            QTimer.singleShot(0, self._position_overlay_mode_buttons)
        return super().event(event)

    def refresh_dns_malw_link_indicator(self) -> None:
        try:
            self.settings.sync()
            managed = _is_dns_malw_link_enabled_by_app(self.settings)
            status = _get_dns_malw_link_status()
            self.dns_malw_link_active = bool(managed and status.get("ok") and status.get("active"))
        except Exception:
            self.dns_malw_link_active = False
        self._update_ai_mode_ui()

    def _set_dns_malw_link_busy(self, busy: bool) -> None:
        self._dns_malw_link_busy = bool(busy)
        self._update_ai_mode_ui()

    def _start_dns_malw_link_worker(self, action: str, show_errors: bool = False) -> None:
        if self._dns_malw_link_worker is not None and self._dns_malw_link_worker.isRunning():
            return
        self._dns_malw_link_pending_action = action
        self._dns_malw_link_show_errors = bool(show_errors)
        self._set_dns_malw_link_busy(True)

        worker = DnsMalwLinkWorker(action, self)
        self._dns_malw_link_worker = worker
        worker.finished_dns.connect(self._on_dns_malw_link_worker_finished)
        worker.start()

    def _on_dns_malw_link_worker_finished(self, action: str, result: dict) -> None:
        try:
            self._dns_malw_link_worker = None
        except Exception:
            pass

        error = str(result.get("error") or "")
        if (not result.get("ok")) and _is_hosts_permission_error_message(error):
            launched = _run_self_as_admin_for_dns_action(action)
            if launched:
                self._start_dns_malw_link_poll(expected_active=(action == "enable"))
                return

        self._finish_dns_malw_link_action(action, result, show_errors=self._dns_malw_link_show_errors)
        self._resume_pending_toggle_if_ready()

    def _finish_dns_malw_link_action(self, action: str, result: dict, show_errors: bool = False) -> None:
        self._dns_malw_link_pending_action = ""
        self._set_dns_malw_link_busy(False)
        self.refresh_dns_malw_link_indicator()

        if result.get("ok"):
            self._resume_pending_toggle_if_ready()
            return

        if not show_errors:
            error = str(result.get("error") or "").strip()
            if error:
                print("Ai DNS error:", error)
            self._resume_pending_toggle_if_ready()
            return

        error = str(result.get("error") or "").strip()
        if error == "no-snapshot":
            text = (
                "Не удалось отключить Ai DNS: нет сохранённых исходных DNS-настроек для восстановления."
                if self.lang == "ru" else
                "Couldn't disable Ai DNS: there is no saved DNS snapshot to restore."
            )
        elif error == "no-clean-snapshot":
            text = (
                "Не удалось безопасно восстановить hosts: backup отсутствует или уже содержит Ai DNS записи."
                if self.lang == "ru" else
                "Couldn't safely restore hosts: the backup is missing or already contains Ai DNS entries."
            )
        elif error == "not-admin":
            text = (
                "Для этой операции нужны права администратора."
                if self.lang == "ru" else
                "Administrator rights are required for this action."
            )
        elif error == "timeout":
            text = (
                "Не удалось дождаться завершения настройки Ai DNS."
                if self.lang == "ru" else
                "Timed out while waiting for Ai DNS configuration to finish."
            )
        elif error == "status-check-failed":
            text = (
                "Настройка была запущена, но активное состояние Ai DNS не подтвердилось."
                if self.lang == "ru" else
                "The configuration was started, but Ai DNS did not become active."
            )
        elif error.startswith("ai-hosts-download-failed"):
            text = (
                "Не удалось скачать или загрузить встроенный hosts-бандл Ai DNS."
                if self.lang == "ru" else
                "Couldn't download or load the bundled Ai DNS hosts bundle."
            )
        elif action == "enable":
            text = (
                "Не удалось включить Ai DNS."
                if self.lang == "ru" else
                "Failed to enable Ai DNS."
            )
        else:
            text = (
                "Не удалось отключить Ai DNS."
                if self.lang == "ru" else
                "Failed to disable Ai DNS."
            )
        if error:
            shown_error = error[:700] + "..." if len(error) > 700 else error
            text = f"{text}\n\n{shown_error}"
        _show_centered_message(self, QMessageBox.Icon.Warning, "Ai DNS", text)
        self._resume_pending_toggle_if_ready()

    def _start_dns_malw_link_poll(self, expected_active: bool) -> None:
        if self._dns_malw_link_poll_timer is None:
            self._dns_malw_link_poll_timer = QTimer(self)
            self._dns_malw_link_poll_timer.setInterval(900)
            self._dns_malw_link_poll_timer.timeout.connect(self._poll_dns_malw_link_status)
        self._dns_malw_link_expected_active = bool(expected_active)
        self._dns_malw_link_poll_attempts = 150
        self._dns_malw_link_poll_anchor = _safe_int_setting(self.settings, DNS_MALW_LAST_ATTEMPT_KEY, 0)
        self._dns_malw_link_poll_timer.start()

    def _poll_dns_malw_link_status(self) -> None:
        self.refresh_dns_malw_link_indicator()
        last_attempt = _safe_int_setting(self.settings, DNS_MALW_LAST_ATTEMPT_KEY, 0)
        last_status = str(self.settings.value(DNS_MALW_LAST_STATUS_KEY, "") or "").strip().lower()
        last_error = str(self.settings.value(DNS_MALW_LAST_ERROR_KEY, "") or "").strip()
        self._dns_malw_link_poll_attempts -= 1
        if last_attempt > self._dns_malw_link_poll_anchor:
            if self._dns_malw_link_poll_timer is not None:
                self._dns_malw_link_poll_timer.stop()
            self._set_dns_malw_link_busy(False)
            if last_status == "ok" and self.dns_malw_link_active == getattr(self, "_dns_malw_link_expected_active", False):
                self._finish_dns_malw_link_action(
                    self._dns_malw_link_pending_action or ("enable" if self._dns_malw_link_expected_active else "disable"),
                    {"ok": True},
                    show_errors=self._dns_malw_link_show_errors,
                )
                return
            self._finish_dns_malw_link_action(
                self._dns_malw_link_pending_action or ("enable" if self._dns_malw_link_expected_active else "disable"),
                {"ok": False, "error": last_error or "status-check-failed"} if last_status != "ok" or not self.dns_malw_link_active == getattr(self, "_dns_malw_link_expected_active", False) else {"ok": True},
                show_errors=self._dns_malw_link_show_errors,
            )
            return
        if (
            self.dns_malw_link_active == getattr(self, "_dns_malw_link_expected_active", False)
            or self._dns_malw_link_poll_attempts <= 0
        ):
            if self._dns_malw_link_poll_timer is not None:
                self._dns_malw_link_poll_timer.stop()
            self._set_dns_malw_link_busy(False)
            if self._dns_malw_link_poll_attempts <= 0:
                self._finish_dns_malw_link_action(
                    self._dns_malw_link_pending_action or ("enable" if self._dns_malw_link_expected_active else "disable"),
                    {"ok": False, "error": last_error or "timeout"},
                    show_errors=self._dns_malw_link_show_errors,
                )
            else:
                self._finish_dns_malw_link_action(
                    self._dns_malw_link_pending_action or ("enable" if self._dns_malw_link_expected_active else "disable"),
                    {"ok": True},
                    show_errors=self._dns_malw_link_show_errors,
                )

    def on_ai_mode_clicked(self, checked: bool) -> None:
        if getattr(self, "_dns_malw_link_busy", False):
            return

        action = "disable" if self.dns_malw_link_active else "enable"
        self._dns_malw_link_pending_action = action
        self._dns_malw_link_show_errors = True
        self._set_dns_malw_link_busy(True)

        if self.is_admin():
            self._start_dns_malw_link_worker(action, show_errors=True)
            return

        launched = _run_self_as_admin_for_dns_action(action)
        if not launched:
            self._set_dns_malw_link_busy(False)
            self._update_ai_mode_ui()
            self._resume_pending_toggle_if_ready()
            return

        self._start_dns_malw_link_poll(expected_active=(action == "enable"))

    def _set_telegram_mode_busy(self, busy: bool) -> None:
        self._telegram_mode_busy = bool(busy)
        self._update_telegram_mode_ui()

    def _update_telegram_mode_ui(self) -> None:
        if not hasattr(self, "telegram_mode_btn"):
            return

        active = bool(getattr(self, "telegram_mode_enabled", False))
        busy = bool(getattr(self, "_telegram_mode_busy", False))
        self.telegram_mode_btn.blockSignals(True)
        self.telegram_mode_btn.setChecked(active)
        self.telegram_mode_btn.blockSignals(False)
        self.telegram_mode_btn.setEnabled(not busy)
        if hasattr(self.telegram_mode_btn, "setBusy"):
            self.telegram_mode_btn.setBusy(busy)
        self._apply_small_circle_button_state(self.telegram_mode_btn, active, "", "pixmap")

        last_error = str(self.settings.value(TELEGRAM_MODE_LAST_ERROR_KEY, "") or "").strip()
        if busy:
            tooltip = (
                "Telegram Mode: применяем изменения..."
                if self.lang == "ru" else
                "Telegram Mode: applying changes..."
            )
        elif last_error:
            tooltip = (
                f"Telegram Mode: ошибка: {last_error}"
                if self.lang == "ru" else
                f"Telegram Mode error: {last_error}"
            )
        elif active:
            tooltip = (
                "Telegram Mode включён: Web через hosts, Desktop через MTProto proxy"
                if self.lang == "ru" else
                "Telegram Mode enabled: Web via hosts, Desktop via MTProto proxy"
            )
        else:
            tooltip = (
                "Telegram Mode выключен"
                if self.lang == "ru" else
                "Telegram Mode disabled"
            )
        self.telegram_mode_btn.setToolTip(tooltip)
        self.update_tray_status()

    def restore_telegram_mode_if_enabled(self) -> None:
        self.telegram_mode_enabled = _is_telegram_mode_enabled(self.settings)
        _sync_telegram_runtime_lists(self.settings)
        self._update_telegram_mode_ui()
        if self.telegram_mode_enabled:
            self._start_telegram_mode_worker("restore")
        elif _is_telegram_hosts_enabled_by_app(self.settings):
            self._start_telegram_mode_worker("cleanup")

    def _start_telegram_mode_worker(self, action: str) -> None:
        if self._telegram_mode_worker is not None and self._telegram_mode_worker.isRunning():
            return
        self._set_telegram_mode_busy(True)
        worker = TelegramModeWorker(action, self.telegram_proxy, self)
        self._telegram_mode_worker = worker
        worker.finished_telegram.connect(self._on_telegram_mode_worker_finished)
        worker.start()

    def _on_telegram_mode_worker_finished(self, action: str, result: dict) -> None:
        try:
            self._telegram_mode_worker = None
        except Exception:
            pass

        self.settings.sync()
        self.telegram_mode_enabled = _is_telegram_mode_enabled(self.settings)

        error = str(result.get("error") or "").strip()
        hosts_permission_error = bool(result.get("hosts_permission_error")) or _is_hosts_permission_error_message(error)
        launched_hosts_helper = False
        if hosts_permission_error and action in {"enable", "disable"}:
            launched_hosts_helper = _run_self_as_admin_for_telegram_hosts_action(action)
            if launched_hosts_helper:
                self._start_telegram_hosts_poll(action, expected_enabled=(action == "enable"))

        if not launched_hosts_helper:
            self._set_telegram_mode_busy(False)

        should_show_error = bool(error) and action in {"enable", "disable"} and not launched_hosts_helper
        if should_show_error:
            title = "Telegram Mode"
            text = (
                f"Не удалось применить Telegram Mode:\n{error}"
                if self.lang == "ru" else
                f"Failed to apply Telegram Mode:\n{error}"
            )
            _show_centered_message(self, QMessageBox.Icon.Warning, title, text)

        if result.get("ok") and action == "enable" and result.get("proxy_running"):
            self._handle_telegram_proxy_ready_after_enable(int(result.get("proxy_port") or _get_telegram_proxy_port(self.settings)))

        self._update_telegram_mode_ui()
        if not launched_hosts_helper:
            self._resume_pending_toggle_if_ready()

    def _telegram_proxy_has_client_connection(self) -> bool:
        try:
            stats = self.telegram_proxy.stats()
            successful = (
                int(stats.get("connections_ws", 0) or 0)
                + int(stats.get("connections_tcp_fallback", 0) or 0)
                + int(stats.get("connections_cfproxy", 0) or 0)
            )
            if successful > 0:
                return True
        except Exception:
            pass
        return _telegram_desktop_has_local_proxy_connection(_get_telegram_proxy_port(self.settings))

    def _open_telegram_proxy_link(self) -> bool:
        try:
            return bool(QDesktopServices.openUrl(QUrl(_get_telegram_proxy_link(self.settings))))
        except Exception:
            return False

    def _handle_telegram_proxy_ready_after_enable(self, port: int) -> None:
        self._schedule_telegram_proxy_autoconnect(port)

    def _schedule_telegram_proxy_autoconnect(self, port: int) -> None:
        del port
        self._telegram_proxy_autoconnect_generation += 1
        generation = int(self._telegram_proxy_autoconnect_generation)

        def _check_existing_or_launch() -> None:
            if generation != int(getattr(self, "_telegram_proxy_autoconnect_generation", 0)):
                return
            if not _is_telegram_mode_enabled(self.settings):
                return
            if self._telegram_proxy_has_client_connection():
                return

            telegram_was_running = _telegram_desktop_process_is_running()
            if telegram_was_running:
                self._wait_for_telegram_proxy_connection_before_link(
                    generation,
                    deadline=time.monotonic() + 10.0,
                )
                return

            launched_plain = _launch_telegram_desktop_app()
            if launched_plain:
                self._wait_for_telegram_proxy_connection_before_link(
                    generation,
                    deadline=time.monotonic() + 14.0,
                )
                return

            self._send_telegram_proxy_link_if_still_needed(generation)

        QTimer.singleShot(1400, _check_existing_or_launch)

    def _wait_for_telegram_proxy_connection_before_link(self, generation: int, deadline: float) -> None:
        if generation != int(getattr(self, "_telegram_proxy_autoconnect_generation", 0)):
            return
        if not _is_telegram_mode_enabled(self.settings):
            return
        if self._telegram_proxy_has_client_connection():
            return
        if time.monotonic() < float(deadline):
            QTimer.singleShot(
                900,
                lambda: self._wait_for_telegram_proxy_connection_before_link(
                    generation,
                    deadline,
                ),
            )
            return
        self._send_telegram_proxy_link_if_still_needed(generation)

    def _send_telegram_proxy_link_if_still_needed(self, generation: int) -> None:
        if generation != int(getattr(self, "_telegram_proxy_autoconnect_generation", 0)):
            return
        if not _is_telegram_mode_enabled(self.settings):
            return
        if self._telegram_proxy_has_client_connection():
            return

        self._open_telegram_proxy_link()

    def _start_telegram_hosts_poll(self, action: str, expected_enabled: bool) -> None:
        if self._telegram_mode_hosts_poll_timer is None:
            self._telegram_mode_hosts_poll_timer = QTimer(self)
            self._telegram_mode_hosts_poll_timer.setInterval(900)
            self._telegram_mode_hosts_poll_timer.timeout.connect(self._poll_telegram_hosts_status)
        self._telegram_mode_hosts_pending_action = (action or "").strip().lower()
        self._telegram_mode_hosts_expected_enabled = bool(expected_enabled)
        self._telegram_mode_hosts_poll_attempts = 30
        self._telegram_mode_hosts_poll_anchor = _safe_int_setting(self.settings, TELEGRAM_MODE_HOSTS_LAST_ATTEMPT_KEY, 0)
        self._set_telegram_mode_busy(True)
        self._telegram_mode_hosts_poll_timer.start()

    def _poll_telegram_hosts_status(self) -> None:
        self.settings.sync()
        last_attempt = _safe_int_setting(self.settings, TELEGRAM_MODE_HOSTS_LAST_ATTEMPT_KEY, 0)
        last_status = str(self.settings.value(TELEGRAM_MODE_HOSTS_LAST_STATUS_KEY, "") or "").strip().lower()
        last_error = str(self.settings.value(TELEGRAM_MODE_HOSTS_LAST_ERROR_KEY, "") or "").strip()
        self._telegram_mode_hosts_poll_attempts -= 1

        if last_attempt <= self._telegram_mode_hosts_poll_anchor and self._telegram_mode_hosts_poll_attempts > 0:
            return

        if self._telegram_mode_hosts_poll_timer is not None:
            self._telegram_mode_hosts_poll_timer.stop()

        action = self._telegram_mode_hosts_pending_action
        expected_enabled = bool(self._telegram_mode_hosts_expected_enabled)
        hosts_enabled = _is_telegram_hosts_enabled_by_app(self.settings)
        ok = bool(last_status == "ok" and hosts_enabled == expected_enabled)
        timed_out = self._telegram_mode_hosts_poll_attempts <= 0 and last_attempt <= self._telegram_mode_hosts_poll_anchor

        if ok:
            if action == "disable":
                _set_telegram_last_error("", self.settings)
            elif action == "enable" and not self.telegram_proxy.is_running():
                _set_telegram_last_error("", self.settings)
        else:
            error = last_error or ("timeout" if timed_out else "status-check-failed")
            _set_telegram_last_error(error, self.settings)
            if action in {"enable", "disable"}:
                text = (
                    f"Не удалось изменить hosts для Telegram Mode:\n{error}"
                    if self.lang == "ru" else
                    f"Failed to update hosts for Telegram Mode:\n{error}"
                )
                _show_centered_message(self, QMessageBox.Icon.Warning, "Telegram Mode", text)

        self.telegram_mode_enabled = _is_telegram_mode_enabled(self.settings)
        self._telegram_mode_hosts_pending_action = ""
        self._set_telegram_mode_busy(False)
        self._update_telegram_mode_ui()
        self._resume_pending_toggle_if_ready()

    def show_telegram_mode_help(self) -> None:
        port = _get_telegram_proxy_port(self.settings)
        if (
            _is_telegram_mode_enabled(self.settings)
            and not bool(getattr(self, "_telegram_help_proxy_link_sent_this_session", False))
            and not self._telegram_proxy_has_client_connection()
        ):
            self._telegram_help_proxy_link_sent_this_session = True
            self._open_telegram_proxy_link()

        try:
            if self._telegram_help_msg is not None and self._telegram_help_msg.isVisible():
                self._telegram_help_msg.close()
        except Exception:
            pass

        text = (
            "Как это работает: приложение добавит записи для Telegram Web в hosts "
            "и запустит локальный MTProto proxy.\n\n"
            "После включения Telegram Mode, откроется Telegram Desktop(если скачен) и через несколько секунд появится запрос на подключение, нажмите 'Подключить'.\n"
            "Если автоматическое подключение не появилось, попробуйте нажать на 'вопросик'. Если и это не помогло, добавьте протокол вручную.\n\n"
            "Как добавить вручную: Настройки->Тип соединения->Использовать собственный прокси->MTProto proxy.\n"
            f"Сервер: 127.0.0.1\nПорт: {int(port)}\n"
            f"Secret: dd{_get_telegram_proxy_secret(self.settings)}"
            if self.lang == "ru" else
            "Enable Telegram Mode: the app will add Telegram Web hosts entries "
            "and start a local MTProto proxy. The main bypass is not started.\n\n"
            "Telegram Web: open web.telegram.org in your browser.\n\n"
            "Telegram Desktop: use MTProto proxy, not SOCKS5.\n"
            f"Server: 127.0.0.1\nPort: {int(port)}\n"
            f"Secret: dd{_get_telegram_proxy_secret(self.settings)}"
        )

        msg = QMessageBox(self)
        msg.setWindowTitle("Telegram Mode")
        msg.setIcon(QMessageBox.Icon.NoIcon)
        msg.setText(text)
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)
        msg.setWindowModality(Qt.WindowModality.NonModal)
        self._telegram_help_msg = msg
        msg.finished.connect(lambda _=0: setattr(self, "_telegram_help_msg", None))
        msg.adjustSize()
        _center_widget_on_screen(msg, self)
        msg.show()
        msg.raise_()
        msg.activateWindow()

    def _ensure_telegram_mode_ready_for_bypass(self) -> None:
        if not _is_telegram_mode_enabled(self.settings):
            _sync_telegram_runtime_lists(self.settings)
            return

        _apply_telegram_mode_files(True, self.settings)
        if not self.telegram_proxy.is_running():
            port = _get_telegram_proxy_port(self.settings)
            secret = _get_telegram_proxy_secret(self.settings)
            try:
                self.telegram_proxy.start(port, secret)
                _set_telegram_last_error("", self.settings)
            except Exception as e:
                _set_telegram_last_error(str(e), self.settings)
        self.telegram_mode_enabled = True
        self._update_telegram_mode_ui()

    def on_telegram_mode_clicked(self, checked: bool) -> None:
        if getattr(self, "_telegram_mode_busy", False):
            return
        action = "disable" if self.telegram_mode_enabled else "enable"
        self._start_telegram_mode_worker(action)

    def _update_game_mode_ui(self) -> None:
        if not hasattr(self, "game_mode_btn"):
            return

        self.game_mode_btn.blockSignals(True)
        self.game_mode_btn.setChecked(bool(self.game_mode_enabled))
        self.game_mode_btn.blockSignals(False)
        icon_kind = "pixmap" if getattr(self.game_mode_btn, "_pixmap", None) is not None else "gamepad"
        self._apply_small_circle_button_state(self.game_mode_btn, bool(self.game_mode_enabled), "", icon_kind)
        self.game_mode_btn.setToolTip(
            "Игровой режим"
            if self.lang == "ru" else
            "Game mode"
        )
        if hasattr(self, "game_settings_btn"):
            self.game_settings_btn.setToolTip(self.t('Game Mode Settings'))
            self._apply_small_circle_button_state(self.game_settings_btn, True, "", "gear")
        self.update_tray_status()

    def _schedule_game_mode_restart_after_change(self, status_text: str | None = None) -> None:
        if not hasattr(self, "toggle_btn") or not self.toggle_btn.isChecked():
            return
        try:
            self.status_lbl.setText(
                status_text or (
                    "Применение игрового режима..."
                    if self.lang == "ru" else
                    "Applying game mode..."
                )
            )
        except Exception:
            pass
        self._schedule_overlay_mode_buttons_position()
        self._game_mode_restart_timer.start()

    def _start_game_mode_restart_worker(self) -> None:
        if self._game_mode_restart_worker is not None:
            if self._game_mode_restart_worker.isRunning():
                return
            self._game_mode_restart_worker = None

        worker = GameModeRestartWorker(self)
        self._game_mode_restart_worker = worker
        worker.finished_restart.connect(self._on_game_mode_restart_stopped)
        worker.start()

    def _on_game_mode_restart_stopped(self, error: str) -> None:
        try:
            self._game_mode_restart_worker = None
        except Exception:
            pass

        if error:
            _show_centered_message(
                self,
                QMessageBox.Icon.Warning,
                "Игровой режим" if self.lang == "ru" else "Game mode",
                error,
            )
            self.retranslate_ui()
            return

        if not hasattr(self, "toggle_btn") or not self.toggle_btn.isChecked():
            self.retranslate_ui()
            return

        profile = self.cb.currentText()
        script = self._profile_script_path(profile)
        if not script:
            self.retranslate_ui()
            return

        if not os.path.exists(script):
            _show_centered_message(
                self,
                QMessageBox.Icon.Warning,
                "Ошибка" if self.lang == "ru" else "Error",
                f"Не найден файл:\n{script}" if self.lang == "ru" else f"File not found:\n{script}",
            )
            self.retranslate_ui()
            return

        self.status_lbl.setText("Запуск обхода..." if self.lang == "ru" else "Starting bypass...")
        self._start_bypass_toggle_worker("start", script)

    def apply_game_mode_preferences(
        self,
        main_bypass_enabled: bool,
        user_lists_enabled: bool,
        discord_enabled: bool,
        restart_if_running: bool = True,
    ) -> None:
        new_options = {
            "main_bypass_enabled": bool(main_bypass_enabled),
            "user_lists_enabled": bool(user_lists_enabled),
            "discord_enabled": bool(discord_enabled),
        }
        if _get_game_mode_options(self.settings) == new_options:
            return

        _set_game_mode_options(
            main_bypass_enabled=new_options["main_bypass_enabled"],
            user_lists_enabled=new_options["user_lists_enabled"],
            discord_enabled=new_options["discord_enabled"],
            settings=self.settings,
        )
        _rebuild_runtime_lists(self.settings)

        if restart_if_running and self.game_mode_enabled and hasattr(self, "toggle_btn") and self.toggle_btn.isChecked():
            self._schedule_game_mode_restart_after_change()

    def _prepare_adaptive_profile_hosts(self, script: str) -> None:
        resolved_script = os.path.abspath(str(script or ""))
        previous_script = os.path.abspath(self._adaptive_active_profile_script) if self._adaptive_active_profile_script else ""
        if previous_script and os.path.normcase(previous_script) != os.path.normcase(resolved_script):
            self._release_adaptive_profile_hosts()

        owned = _prepare_adaptive_profile_hosts_for_launch(resolved_script, self.settings)
        self._adaptive_hosts_owned = bool(self._adaptive_hosts_owned or owned)
        self._adaptive_active_profile_script = (
            resolved_script if profile_requires_telegram_hosts(resolved_script) else ""
        )

    def _release_adaptive_profile_hosts(self) -> None:
        owned = bool(getattr(self, "_adaptive_hosts_owned", False))
        self._adaptive_hosts_owned = False
        self._adaptive_active_profile_script = ""
        error = _release_adaptive_profile_hosts_after_stop(owned, self.settings)
        if error:
            print(error)

    def _launch_profile_process(self, script: str):
        self._prepare_adaptive_profile_hosts(script)
        try:
            return _launch_profile_process_core(script, self.core_dir, self.settings)
        except Exception:
            self._release_adaptive_profile_hosts()
            raise

    def set_game_mode_enabled(self, enabled: bool, restart_if_running: bool = True) -> None:
        enabled = bool(enabled)
        if self.game_mode_enabled == enabled:
            self._update_game_mode_ui()
            return

        self.game_mode_enabled = enabled
        _set_game_mode_enabled(enabled, self.settings)
        _apply_game_mode_state_to_core(self.settings)
        _rebuild_runtime_lists(self.settings)
        self._update_game_mode_ui()

        if restart_if_running and hasattr(self, "toggle_btn") and self.toggle_btn.isChecked():
            self._schedule_game_mode_restart_after_change()

    def on_game_mode_clicked(self, checked: bool) -> None:
        self.set_game_mode_enabled(checked, restart_if_running=True)

    def open_game_mode_settings(self) -> None:
        if self._game_settings_dlg is not None and self._game_settings_dlg.isVisible():
            self._game_settings_dlg.raise_()
            self._game_settings_dlg.activateWindow()
            return

        dlg = GameModeSettingsDialog(self)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        self._game_settings_dlg = dlg
        dlg.finished.connect(lambda _=0: setattr(self, "_game_settings_dlg", None))
        from_tray = not self.isVisible() or self.isMinimized()
        if from_tray:
            dlg.show()
            self._center_dialog_on_screen(dlg)
        else:
            dlg.move(self._bottom_dialog_start_pos(dlg))
            dlg.show()
            self._animate_bottom_dialog_open(dlg, gap=8)
        dlg.raise_()
        dlg.activateWindow()

    def update_blink(self):
        return

    def _update_autotest_info_button(self):
        has_data = bool(_load_autotest_result() or _load_adaptive_strategy_info())
        if hasattr(self, "auto_info_btn"):
            self.auto_info_btn.setText("i")
            self.auto_info_btn.setToolTip(
                "Последняя информация автоподбора"
                if self.lang == "ru" else
                "Latest auto-selection information"
            )
            self.auto_info_btn.setVisible(has_data)

    def show_autotest_info(self):
        standard = _load_autotest_result()
        adaptive = _load_adaptive_strategy_info()
        if not standard and not adaptive:
            return

        title = "Последняя информация автоподбора" if self.lang == "ru" else "Latest auto-selection information"
        dlg = StyledDialog(self)
        dlg.setWindowTitle(title)
        dlg.setFixedSize(680, 390)
        root = _make_window_root_layout(dlg)
        dlg.install_title_bar(root, title)
        layout = _make_window_content_layout(root, dlg, margins=(16, 12, 16, 14), spacing=12)
        columns = QHBoxLayout()
        columns.setSpacing(12)

        def make_panel(heading: str) -> tuple[QFrame, QVBoxLayout]:
            panel = QFrame(dlg)
            panel.setStyleSheet(
                "QFrame { background:rgba(8,16,12,145); border:1px solid rgba(91,224,142,78); border-radius:8px; }"
            )
            panel_layout = QVBoxLayout(panel)
            panel_layout.setContentsMargins(13, 12, 13, 12)
            panel_layout.setSpacing(8)
            label = QLabel(heading, panel)
            label.setStyleSheet("color:#f2f7f3; font-size:14px; font-weight:700; border:none; background:transparent;")
            panel_layout.addWidget(label)
            return panel, panel_layout

        standard_panel, standard_layout = make_panel(
            "Стандартный перебор" if self.lang == "ru" else "Ready-made strategy scan"
        )
        best = str(standard.get("best", "") or "")
        good = list(standard.get("good", []) or [])
        bad = list(standard.get("bad", []) or [])
        if not standard:
            no_data = QLabel("Ещё не запускался." if self.lang == "ru" else "Has not been run yet.", standard_panel)
            no_data.setStyleSheet("color:rgba(218,225,220,185); border:none; background:transparent;")
            standard_layout.addWidget(no_data)
        else:
            best_label = QLabel(
                ("Лучший профиль\n" if self.lang == "ru" else "Best profile\n") + (best or "—"), standard_panel
            )
            best_label.setWordWrap(True)
            best_label.setStyleSheet("color:#a5f2c1; font-size:13px; font-weight:700; border:none; background:transparent;")
            standard_layout.addWidget(best_label)
            for label_text, items in (
                ("Рабочие" if self.lang == "ru" else "Working", good),
                ("Нерабочие" if self.lang == "ru" else "Not working", bad),
            ):
                shown = items[:3]
                section = QLabel(f"{label_text}: " + (", ".join(shown) if shown else "—"), standard_panel)
                section.setWordWrap(True)
                section.setStyleSheet("color:rgba(231,240,234,225); border:none; background:transparent;")
                standard_layout.addWidget(section)
                if len(items) > 3:
                    more = QPushButton("Показать весь список" if self.lang == "ru" else "Show full list", standard_panel)
                    more.setStyleSheet("QPushButton { color:#7ce7a7; text-align:left; border:none; background:transparent; padding:0; }")
                    more.clicked.connect(lambda _=False, values=items, caption=label_text: _show_centered_message(
                        dlg, QMessageBox.Icon.NoIcon, caption, "\n".join(values)
                    ))
                    standard_layout.addWidget(more)
            updated = str(standard.get("updated_at", "") or "")
            if updated:
                stamp = QLabel(updated, standard_panel)
                stamp.setStyleSheet("color:rgba(190,201,194,155); font-size:10px; border:none; background:transparent;")
                standard_layout.addWidget(stamp)
        standard_layout.addStretch(1)

        adaptive_panel, adaptive_layout = make_panel(
            "Пользовательская стратегия" if self.lang == "ru" else "Generated strategy"
        )
        adaptive_path = str(adaptive.get("path", "") or "")
        if not adaptive:
            no_data = QLabel("Ещё не создавалась." if self.lang == "ru" else "Has not been created yet.", adaptive_panel)
            no_data.setStyleSheet("color:rgba(218,225,220,185); border:none; background:transparent;")
            adaptive_layout.addWidget(no_data)
        else:
            name_row = QHBoxLayout()
            name = QLabel(str(adaptive.get("name", "") or "—"), adaptive_panel)
            name.setWordWrap(True)
            name.setStyleSheet("color:#a5f2c1; font-size:13px; font-weight:700; border:none; background:transparent;")
            name_row.addWidget(name, 1)
            folder = QToolButton(adaptive_panel)
            folder.setText("📁")
            folder.setToolTip("Открыть папку" if self.lang == "ru" else "Open folder")
            folder.setFixedSize(28, 28)
            folder.setStyleSheet("QToolButton { color:#75dca0; border:1px solid rgba(98,216,145,95); border-radius:6px; background:transparent; }")
            folder.clicked.connect(lambda: QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(adaptive_path).parent))))
            name_row.addWidget(folder)
            adaptive_layout.addLayout(name_row)
            methods = list(adaptive.get("methods", []) or [])
            methods_label = QLabel(
                ("Методы: " if self.lang == "ru" else "Methods: ") + (", ".join(methods) if methods else "—"), adaptive_panel
            )
            methods_label.setWordWrap(True)
            methods_label.setStyleSheet("color:rgba(231,240,234,225); border:none; background:transparent;")
            adaptive_layout.addWidget(methods_label)
            stamp = QLabel(str(adaptive.get("updated_at", "") or ""), adaptive_panel)
            stamp.setStyleSheet("color:rgba(190,201,194,155); font-size:10px; border:none; background:transparent;")
            adaptive_layout.addWidget(stamp)
        adaptive_layout.addStretch(1)
        columns.addWidget(standard_panel, 1)
        columns.addWidget(adaptive_panel, 1)
        layout.addLayout(columns, 1)
        close = QPushButton("Готово" if self.lang == "ru" else "Done", dlg)
        close.setFixedSize(104, 32)
        close.clicked.connect(dlg.accept)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        buttons.addWidget(close)
        layout.addLayout(buttons)
        self._center_dialog_on_screen(dlg)
        dlg.exec()

    def is_winws_running(self):
        return _is_winws_running_silent()

    def _refresh_bypass_process_state(self) -> None:
        if (self.process is None or getattr(self, "_bypass_toggle_busy", False)
                or getattr(self, "_game_mode_restart_worker", None) is not None
                or getattr(self, "_exiting", False)):
            return
        if self.process.poll() is None:
            return
        if getattr(self, "_suppress_bypass_exit_notification", False):
            # The update worker intentionally stopped winws. Its completion
            # handler will finish normal cleanup; do not show a false error.
            self.process = None
            self._suppress_bypass_exit_notification = False
            self._set_main_toggle_checked_visual(False, animated=True)
            self.status_lbl.setText(self.t("Off"))
            self.update_tray_status()
            return
        state = _bypass_service.snapshot()
        self.process = None
        self._set_main_toggle_checked_visual(False, animated=True)
        self.status_lbl.setText("Обход завершился" if self.lang == "ru" else "Bypass exited")
        self.update_tray_status()
        error = state.get("error") or state.get("log") or "winws exited"
        _show_centered_message(self, QMessageBox.Icon.Warning,
                               "Ошибка обхода" if self.lang == "ru" else "Bypass error", str(error))

    def _set_bypass_toggle_busy(self, busy: bool) -> None:
        self._bypass_toggle_busy = bool(busy)
        try:
            self.toggle_btn.setEnabled(not busy)
            self.cb.setEnabled(not busy)
        except Exception:
            pass
        self._schedule_overlay_mode_buttons_position()
        self.update_tray_status()

    def _start_bypass_toggle_worker(self, action: str, script: str = "") -> None:
        worker = getattr(self, "_bypass_toggle_worker", None)
        if worker is not None and worker.isRunning():
            return

        self._set_bypass_toggle_busy(True)
        worker = BypassToggleWorker(
            action=action,
            script=script,
            core_dir=self.core_dir,
            settings_path=SETTINGS_FILE,
            adaptive_hosts_owned=bool(getattr(self, "_adaptive_hosts_owned", False)),
            telegram_proxy=self.telegram_proxy,
            parent=self,
        )
        self._bypass_toggle_worker = worker
        worker.finished_bypass.connect(self._on_bypass_toggle_worker_finished)
        worker.start()

    def _on_bypass_toggle_worker_finished(self, action: str, result: dict) -> None:
        worker = getattr(self, "_bypass_toggle_worker", None)
        self._bypass_toggle_worker = None
        self._set_bypass_toggle_busy(False)
        try:
            if worker is not None:
                worker.deleteLater()
        except Exception:
            pass

        if getattr(self, "_exiting", False):
            return

        error = str(result.get("error") or "").strip()
        hosts_error = str(result.get("adaptive_hosts_error") or "").strip()
        if hosts_error:
            print(hosts_error)

        if action == "start" and result.get("ok"):
            self.process = result.get("process")
            self._suppress_bypass_exit_notification = False
            self._adaptive_hosts_owned = bool(result.get("adaptive_hosts_owned", False))
            self._adaptive_active_profile_script = (
                os.path.abspath(self._profile_script_path(self.cb.currentText()))
                if profile_requires_telegram_hosts(self._profile_script_path(self.cb.currentText()))
                else ""
            )
            self._update_telegram_mode_ui()
            self.status_lbl.setText(self.t("On: {}", self.cb.currentText()))
        elif action == "stop" and result.get("ok"):
            self.process = None
            self._adaptive_hosts_owned = False
            self._adaptive_active_profile_script = ""
            self.status_lbl.setText(self.t("Off"))
        else:
            if result.get("running", action == "stop"):
                # A failed stop means the bypass may still be active; return the
                # button to its real state instead of leaving a false "off" UI.
                self._set_main_toggle_checked_visual(True, animated=True)
                self.status_lbl.setText("Обход всё ещё работает" if self.lang == "ru" else "Bypass is still running")
            else:
                self.process = None
                self._adaptive_hosts_owned = False
                self._adaptive_active_profile_script = ""
                self._set_main_toggle_checked_visual(False, animated=True)
                self.status_lbl.setText(self.t("Off"))
            if error and error != "cancelled":
                _show_centered_message(
                    self,
                    QMessageBox.Icon.Warning,
                    "Ошибка" if self.lang == "ru" else "Error",
                    error,
                )
        self.update_tray_status()

    def on_toggle(self, checked):
        if (not checked) and getattr(self, "_pending_toggle_state", None) is True:
            self._pending_toggle_state = None
            self._pending_toggle_profile = " "
            self._set_pending_start_ui(False)
            return

        if getattr(self, "_bypass_toggle_busy", False):
            return

        profile = self.cb.currentText()

        if checked and self._startup_blockers_active():
            self._queue_toggle_start(profile)
            return

        if checked:
            script = self._profile_script_path(profile)
            if not script:
                self.status_lbl.setText(
                    "Сгенерируйте или добавьте стратегию" if self.lang == "ru" else "Generate or add a strategy"
                )
                self._set_main_toggle_checked_visual(False, animated=True)
                self.update_tray_status()
                return
            self.settings.setValue("last_profile", profile)
            if not os.path.exists(script):
                _show_centered_message(
                    self,
                    QMessageBox.Icon.Warning,
                    "Ошибка" if self.lang == "ru" else "Error",
                    f"Не найден файл:\n{script}" if self.lang == "ru" else f"File not found:\n{script}",
                )
                self._set_main_toggle_checked_visual(False, animated=True)
                self.update_tray_status()
                return
            self.status_lbl.setText("Запуск обхода..." if self.lang == "ru" else "Starting bypass...")
            self._start_bypass_toggle_worker("start", script)

        else:
            self.status_lbl.setText("Остановка обхода..." if self.lang == "ru" else "Stopping bypass...")
            self._start_bypass_toggle_worker("stop")

    def open_settings(self):
        if getattr(self, "_settings_dlg", None) is not None and self._settings_dlg.isVisible():
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return

        dlg = SettingsDialog(self, self.settings)
        dlg.profile_cb.clear()
        dlg.profile_cb.addItem(" ")
        dlg.profile_cb.addItems([p for p in self.presets if p != " "])
        dlg.profile_cb.setCurrentText(self.settings.value('autostart_profile', ' '))

        dlg.setWindowModality(Qt.WindowModality.NonModal)

        self._settings_dlg = dlg
        app = QApplication.instance()
        if app is not None and not self._settings_guard_installed:
            try:
                app.installEventFilter(self)
                self._settings_guard_installed = True
            except Exception:
                pass

        start_pos = self._side_dialog_start_pos(dlg, side="right")
        dlg.move(start_pos)
        try:
            dlg.setWindowOpacity(0.0)
        except Exception:
            pass

        def _after_close(_=0):
            self.autostart = self.settings.value('autostart', False, type=bool)
            self.set_autostart(self.autostart, provision=self.autostart)
            try:
                self._settings_dlg = None
            except Exception:
                pass
            app = QApplication.instance()
            if app is not None and self._settings_guard_installed:
                try:
                    app.removeEventFilter(self)
                except Exception:
                    pass
                self._settings_guard_installed = False

        dlg.finished.connect(_after_close)

        dlg.show()
        QTimer.singleShot(0, lambda d=dlg: self._animate_side_dialog_open(d, side="right", gap=8))

    def open_site_manager_centered(self):
        if self._site_manager_dlg is not None and self._site_manager_dlg.isVisible():
            self._center_dialog_on_screen(self._site_manager_dlg)
            self._site_manager_dlg.raise_()
            self._site_manager_dlg.activateWindow()
            return

        dlg = SiteManagerDialog(self, self.settings)
        dlg.setWindowModality(Qt.WindowModality.NonModal)
        self._site_manager_dlg = dlg
        dlg.finished.connect(lambda _=0: setattr(self, "_site_manager_dlg", None))
        dlg.show()
        self._center_dialog_on_screen(dlg)
        dlg.raise_()
        dlg.activateWindow()

    def open_site_manager_from_tray(self):
        self.open_site_manager_centered()

    def open_site_domain_input_from_tray(self, target_file: str) -> None:
        is_ip = _entity_kind_for_target_file(target_file) == "ip"
        is_add = target_file in (USER_GENERAL_FILE, USER_IP_ALL_FILE)
        title = (
            "Добавить IP" if is_ip and is_add and self.lang == "ru" else
            "Исключить IP" if is_ip and self.lang == "ru" else
            "Добавить сайт" if is_add and self.lang == "ru" else
            "Исключить сайт" if self.lang == "ru" else
            "Add IP" if is_ip and is_add else
            "Exclude IP" if is_ip else
            "Add site" if is_add else
            "Exclude site"
        )
        label = (
            "Введите IP или подсеть:" if is_ip and self.lang == "ru" else
            "Введите домен или сайт:" if self.lang == "ru" else
            "Enter IP or subnet:" if is_ip else
            "Enter domain or site:"
        )

        dlg = TextInputDialog(
            title,
            label,
            ok_text="OK",
            cancel_text="Отмена" if self.lang == "ru" else "Cancel",
            parent=self,
        )
        dlg.setTextValue("")
        self._center_dialog_on_screen(dlg)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        value = _normalize_value_for_target_file(target_file, dlg.textValue())
        if not _is_valid_value_for_target_file(target_file, value):
            _show_centered_message(
                self,
                QMessageBox.Icon.Warning,
                "Ошибка" if self.lang == "ru" else "Error",
                "Некорректный IP или подсеть."
                if is_ip and self.lang == "ru" else
                "Некорректный домен."
                if self.lang == "ru" else
                "Invalid IP or subnet."
                if is_ip else
                "Invalid domain."
            )
            return

        lines = _read_lines_utf8(target_file)
        lines = _merge_unique(lines, [value])
        _write_lines_utf8(target_file, lines)
        _rebuild_runtime_lists(self.settings)

        if self._site_manager_dlg is not None and self._site_manager_dlg.isVisible():
            self._site_manager_dlg.lazy_loaded[target_file] = True
            if self._site_manager_dlg.current_file == target_file:
                self._site_manager_dlg.reload_current_file()

    def set_autostart(self, enable: bool, provision: bool = False):
        try:
            import winreg
            with winreg.CreateKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run") as key:
                if enable:
                    winreg.SetValueEx(key, "ZapretGUI", 0, winreg.REG_SZ, _build_autostart_task_command())
                else:
                    try:
                        winreg.DeleteValue(key, "ZapretGUI")
                    except FileNotFoundError:
                        pass
            # Best effort migration; the elevated service installer also removes
            # the old task when its ACL prevents the ordinary GUI from doing so.
            _run_hidden(["schtasks", "/Delete", "/TN", "ZapretGUI", "/F"], timeout=5)
            if enable and provision and getattr(self, "_background_setup_worker", None) is None:
                worker = BackgroundSetupWorker(self.core_dir, self)
                self._background_setup_worker = worker
                worker.completed.connect(self._on_background_setup_finished)
                worker.finished.connect(worker.deleteLater)
                worker.start()
        except Exception as error:
            self.autostart = False
            self.settings.setValue("autostart", False)
            _show_centered_message(self, QMessageBox.Icon.Warning,
                                   "Автозапуск" if self.lang == "ru" else "Autostart", str(error))

    def _on_background_setup_finished(self, error: str) -> None:
        self._background_setup_worker = None
        if getattr(self, "_exiting", False):
            return
        if error:
            self.autostart = False
            self.settings.setValue("autostart", False)
            self.set_autostart(False)
            _show_centered_message(self, QMessageBox.Icon.Warning,
                                   "Автозапуск" if self.lang == "ru" else "Autostart", error)

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                QTimer.singleShot(0, self.hide)
                event.accept()
                return
            QTimer.singleShot(0, self._resume_main_window_ui)
        super().changeEvent(event)

    def closeEvent(self, event):
        if getattr(self, "_exiting", False):
            event.accept()
            return

        manual_close = bool(
            getattr(self, "_manual_close_requested", False)
            or self.isActiveWindow()
        )
        system_shutdown = bool(getattr(self, "_system_shutdown_requested", False))
        try:
            system_shutdown = system_shutdown or bool(QGuiApplication.isSavingSession())
        except Exception:
            pass
        if system_shutdown or not manual_close:
            # A non-interactive WM_CLOSE is how Task Manager asks a GUI process
            # to exit.  Treat it like session shutdown: no prompt and no waits.
            self._system_shutdown_requested = True
            self._shutdown_and_quit()
            event.accept()
            return

        if self.is_winws_running():
            title = "Выход из программы" if self.lang == 'ru' else "Exit"
            text = (
                "Обход сейчас активен. Остановить его и выйти?"
                if self.lang == 'ru'
                else "Bypass is active. Stop it and exit?"
            )

            msg = QMessageBox(self)
            msg.setWindowTitle(title)
            msg.setText(text)
            msg.setIcon(QMessageBox.Icon.Warning)

            if self.lang == 'ru':
                btn_yes = msg.addButton("Да", QMessageBox.ButtonRole.YesRole)
                btn_no = msg.addButton("Нет", QMessageBox.ButtonRole.NoRole)
            else:
                btn_yes = msg.addButton("Yes", QMessageBox.ButtonRole.YesRole)
                btn_no = msg.addButton("No", QMessageBox.ButtonRole.NoRole)

            msg.exec()
            if msg.clickedButton() != btn_yes:
                self._manual_close_requested = False
                event.ignore()
                return

        self._shutdown_and_quit()
        event.accept()
