# --- Worker threads and settings dialog -------------------------------------

class SettingsDialog(StyledDialog):
    NORMAL_HEIGHT = 360
    STATUS_HEIGHT = 460

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.lang = settings.value('lang', 'ru')
        self._update_worker = None
        self._update_close_after_finish = False
        self.init_ui()
        self.load_settings()
        self.retranslate_ui()

    def t(self, key, *args):
        return translations[self.lang].get(key, key).format(*args)

    def init_ui(self):
        self.setWindowTitle('')
        self.setFixedSize(400, self.NORMAL_HEIGHT)
        root = _make_window_root_layout(self)
        self.install_title_bar(root, self.t('Settings'))
        layout = _make_window_content_layout(root, self, margins=(12, 10, 12, 12), spacing=8)

        hl = QHBoxLayout()
        hl.addStretch()
        flag_dir = os.path.join(APP_DIR, 'flags')
        for code in ('ru', 'en'):
            pix = QPixmap(os.path.join(flag_dir, f'{code}.png')).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            btn = QPushButton()
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(24, 24))

            btn.setFixedSize(32, 32)

            btn.setStyleSheet("""
            QPushButton {
                padding: 0px;
                margin: 0px;
                border: none;
                border-radius: 8px;
                background: transparent;
                min-height: 0px;
                min-width: 0px;
            }
            QPushButton:hover {
                background: rgba(255,255,255,18);
            }
            """)

            btn.clicked.connect(lambda _, c=code: self.change_lang(c))
            hl.addWidget(btn)

        hl.addStretch()
        layout.addLayout(hl)

        cb_layout = QHBoxLayout()
        self.autostart_cb = ModernCheckBox()
        self.minimized_cb = ModernCheckBox()
        cb_layout.addWidget(self.autostart_cb)
        cb_layout.addWidget(self.minimized_cb)
        cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(cb_layout)

        self.autostart_cb.toggled.connect(self.update_profile_autostart_ui)

        self.autostart_profile_label = QLabel("Профиль для автозагрузки")
        self.autostart_profile_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.autostart_profile_label)

        profile_row = QHBoxLayout()
        profile_row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.profile_cb = StableComboBox()
        self.profile_cb.addItem(" ")
        self.profile_cb.currentIndexChanged.connect(self.on_autostart_profile_selected)
        self.profile_enable_cb = ModernCheckBox()
        self.profile_enable_cb.setEnabled(False)
        profile_row.addWidget(self.profile_cb)
        profile_row.addWidget(self.profile_enable_cb)
        self.profile_enable_cb.setStyleSheet("padding-right: 4px;")
        layout.addLayout(profile_row)

        self.svc_btn = QPushButton()
        self.svc_btn.setFixedHeight(30)
        self.svc_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid #2db45f;
                border-radius: 8px;
                background: transparent;
                color: #f3f3f3;
                font-weight: 600;
                padding: 0 10px;
            }
            QPushButton:hover {
                background: rgba(45,180,95,0.10);
            }
            QPushButton:pressed {
                background: rgba(45,180,95,0.18);
            }
        """)
        self.svc_btn.clicked.connect(self.on_service_mode)
        layout.addWidget(self.svc_btn)

        self.remove_btn = QPushButton("Удалить сервисы")
        self.remove_btn.setFixedHeight(30)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid red;
                border-radius: 4px;
            }
        """)
        self.remove_btn.clicked.connect(self.remove_service)
        layout.addWidget(self.remove_btn)

        self.update_btn = QPushButton()
        self.update_btn.setFixedHeight(30)
        self.update_btn.clicked.connect(self.check_updates)
        layout.addWidget(self.update_btn)

        self.update_status_box = QTextBrowser()
        self.update_status_box.setFixedHeight(68)
        self.update_status_box.setOpenExternalLinks(False)
        self.update_status_box.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.update_status_box.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.update_status_box.setStyleSheet("""
            QTextBrowser {
                border: none;
                background: transparent;
                color: rgba(180,180,180,0.95);
                font-size: 11px;
                padding: 0;
            }
        """)
        self.update_status_box.hide()
        layout.addWidget(self.update_status_box)

        self.about_label = QLabel()
        self.about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.about_label.setTextFormat(Qt.TextFormat.RichText)
        self.about_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.about_label.setOpenExternalLinks(True)
        layout.addWidget(self.about_label)

        self.version_label = QLabel()
        self.version_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.version_label.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.version_label)

    def update_profile_autostart_ui(self):
        enabled = self.autostart_cb.isChecked()
        self.autostart_profile_label.setEnabled(enabled)
        self.profile_cb.setEnabled(enabled)
        self.profile_enable_cb.setEnabled(enabled and self.profile_cb.currentText() != " ")

    def load_settings(self):
        self.autostart_cb.setChecked(self.settings.value('autostart', False, type=bool))
        self.minimized_cb.setChecked(self.settings.value('minimized', False, type=bool))
        self.profile_cb.setCurrentText(self.settings.value('autostart_profile', ' '))
        self.profile_enable_cb.setChecked(self.settings.value('autostart_profile_enabled', False, type=bool))
        self.update_profile_autostart_ui()

    def on_autostart_profile_selected(self):
        selected = self.profile_cb.currentText()
        enabled = selected != " "
        self.profile_enable_cb.setChecked(enabled)
        self.profile_enable_cb.setEnabled(False)

    def save_settings(self):
        self.settings.setValue('autostart', self.autostart_cb.isChecked())
        self.settings.setValue('minimized', self.minimized_cb.isChecked())
        self.settings.setValue('autostart_profile', self.profile_cb.currentText())
        self.settings.setValue('autostart_profile_enabled', self.profile_enable_cb.isChecked())

    def retranslate_ui(self):
        self.setWindowTitle(self.t('Settings'))
        self.autostart_cb.setText(self.t('Autostart program'))
        self.minimized_cb.setText(self.t('Start minimized'))
        self.svc_btn.setText(self.t('Service mode'))
        self.remove_btn.setText(self.t('Remove Services'))
        self.update_btn.setText(self.t('Check Updates'))
        self.autostart_profile_label.setText(self.t('Autostart profile'))
        self.about_label.setText(
            f'{self.t("About:")} '
            '<a href="https://github.com/bol-van" style="color:#3399ff;">Zapret</a> & '
            '<a href="https://github.com/medvedeff-true" style="color:#3399ff;">Medvedeff</a> & '
            '<a href="https://github.com/Flowseal" style="color:#3399ff;">Flowseal</a>'
        )

        core_ver = str(self.settings.value(FLOWSEAL_VER_KEY, FLOWSEAL_DEFAULT_VER)).strip()
        if not core_ver:
            core_ver = FLOWSEAL_DEFAULT_VER
        self.version_label.setText(f"GUI: {APP_VERSION} + Core: {core_ver}")
        if not self._is_update_running():
            self._set_update_status_text("")

    def change_lang(self, lang_code):
        self.lang = lang_code
        self.settings.setValue('lang', lang_code)
        self.retranslate_ui()
        parent = self.parent()
        if parent and hasattr(parent, 'change_lang'):
            parent.change_lang(lang_code)

    def on_service_mode(self):
        script = os.path.join(APP_DIR, 'core', 'service.bat')
        if os.path.exists(script):
            subprocess.Popen(
                ["cmd.exe", "/d", "/c", script],
                cwd=os.path.join(APP_DIR, "core"),
                creationflags=subprocess.CREATE_NEW_CONSOLE,
                close_fds=True
            )
        else:
            QMessageBox.warning(self, self.t('Settings'), 'service.bat не найден')

    def install_service(self):
        script = os.path.join(APP_DIR, 'core', 'fast', 'install_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'install_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)

    def install_discord_service(self):
        script = os.path.join(APP_DIR, 'core', 'fast', 'install_discord_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'install_discord_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)

    def remove_service(self):
        script = REMOVE_BAT  # APP_DIR/uninstall.bat
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'uninstall.bat не найден')
            return

        try:
            subprocess.Popen(
                ["cmd.exe", "/d", "/c", script],
                cwd=APP_DIR,
                creationflags=getattr(subprocess, "CREATE_NEW_CONSOLE", 0),
                close_fds=True
            )
        except Exception as e:
            QMessageBox.warning(self, self.t('Settings'), f"Не удалось запустить uninstall.bat:\n{e}")

    def _is_update_running(self) -> bool:
        return self._update_worker is not None and self._update_worker.isRunning()

    def _detach_running_update_check(self) -> None:
        worker = self._update_worker
        if worker is None:
            return

        self._update_worker = None
        self._update_close_after_finish = False
        try:
            worker.finished_update.disconnect(self._on_update_worker_finished)
        except Exception:
            pass
        try:
            worker.setParent(None)
        except Exception:
            pass

        _DETACHED_UPDATE_WORKERS.append(worker)

        def _cleanup_detached_worker():
            try:
                if worker in _DETACHED_UPDATE_WORKERS:
                    _DETACHED_UPDATE_WORKERS.remove(worker)
            except Exception:
                pass
            try:
                worker.deleteLater()
            except Exception:
                pass

        try:
            worker.finished.connect(_cleanup_detached_worker)
        except Exception:
            pass
        try:
            worker.requestInterruption()
        except Exception:
            pass
        self._set_update_busy(False, "")

    def _set_update_busy(self, busy: bool, text: str = "") -> None:
        self.update_btn.setEnabled(not busy)
        if text or not busy:
            self._set_update_status_text(text)

    def _set_update_status_text(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            self.update_status_box.clear()
            self.update_status_box.hide()
            self.setFixedSize(400, self.NORMAL_HEIGHT)
            return

        escaped = (
            text.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\n", "<br>")
        )
        self.update_status_box.setHtml(
            f"<div style='font-family:Segoe UI; font-size:11px; text-align:center; color:rgba(180,180,180,0.95);'>{escaped}</div>"
        )
        self.setFixedSize(400, self.STATUS_HEIGHT)
        self.update_status_box.show()

    def _start_update_worker(
        self,
        mode: str,
        latest_ver: str = "",
        download_url: str = "",
        archive_sha256: str = "",
        checksum_url: str = "",
    ) -> None:
        if self._is_update_running():
            return

        if mode == "apply-gui":
            text = (
                "Скачивание обновления GUI..." if self.lang == "ru" else "Downloading GUI update..."
            )
        elif mode == "apply":
            text = (
                "Обновление core..." if self.lang == "ru" else "Updating core..."
            )
        elif mode == "check-core":
            text = (
                "Проверка обновлений core..." if self.lang == "ru" else "Checking core updates..."
            )
        else:
            text = (
                "Проверка обновлений..." if self.lang == "ru" else "Checking updates..."
            )

        self._set_update_busy(True, text)
        worker = ReleaseUpdateWorker(
            mode,
            latest_ver,
            download_url,
            archive_sha256,
            checksum_url,
            self,
        )
        self._update_worker = worker
        worker.finished_update.connect(self._on_update_worker_finished)
        worker.download_progress.connect(self._on_gui_update_download_progress)
        worker.start()

    def _on_gui_update_download_progress(self, downloaded: int, total: int) -> None:
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
        self._set_update_status_text(text)

    def _format_update_result_text(self, result: dict) -> str:
        status = str(result.get("status") or "")
        current_ver = str(result.get("current_ver") or "")
        latest_ver = str(result.get("latest_ver") or "")
        lists_result = result.get("lists_result") or {}
        recovery_lines = []
        if result.get("bypass_stopped"):
            recovery_lines.append(
                "Обход был автоматически выключен для проверки обновлений."
                if self.lang == "ru" else
                "The bypass was automatically stopped for the update check."
            )
        if result.get("winws_reset"):
            recovery_lines.append(
                "Соединения winws автоматически сброшены, проверка повторена."
                if self.lang == "ru" else
                "winws connections were reset automatically and the check was retried."
            )

        def _with_recovery(text: str) -> str:
            return "\n".join([*recovery_lines, text]).strip()

        if self.lang == "ru":
            if status == "up-to-date":
                if result.get("gui_checked"):
                    gui_ver = str(result.get("gui_current_ver") or APP_VERSION)
                    head = f"GUI: актуальная версия {gui_ver}\nCore: актуальная версия {current_ver}"
                else:
                    head = f"У вас уже актуальная версия: {current_ver}"
                body = _format_lists_status_text(lists_result, "ru") if lists_result else ""
                return _with_recovery(f"{head}\n{body}".strip())
            if status == "updated":
                head = f"Core обновлён до: {latest_ver}"
                body = _format_lists_status_text(lists_result, "ru") if lists_result else ""
                return _with_recovery(f"{head}\n{body}".strip())
            if status in {"gui-restart-scheduled", "gui-update-ready"}:
                return _with_recovery("GUI обновляется. Приложение сейчас перезапустится.")
            if status == "unsupported":
                return _with_recovery("Автообновление GUI доступно только для exe-версии приложения.")
            if status == "winws-running":
                return _with_recovery("Не удалось автоматически остановить обход.")
            if status == "winws-reset-failed":
                return _with_recovery("Не удалось сбросить соединения winws: " + str(result.get("error") or ""))
            if status == "offline":
                return _with_recovery("Не удалось проверить обновления: проверьте интернет-соединение.")
            if status == "bad-zip":
                return _with_recovery("Скачанный архив повреждён или не является zip.")
            if status == "permission":
                return _with_recovery("Не удалось записать файлы core. Остановите обход и повторите.")
            return _with_recovery("Не удалось завершить проверку обновлений.")

        if status == "up-to-date":
            if result.get("gui_checked"):
                gui_ver = str(result.get("gui_current_ver") or APP_VERSION)
                head = f"GUI: latest version {gui_ver}\nCore: latest version {current_ver}"
            else:
                head = f"You already have the latest version: {current_ver}"
            body = _format_lists_status_text(lists_result, "en") if lists_result else ""
            return _with_recovery(f"{head}\n{body}".strip())
        if status == "updated":
            head = f"Core updated to: {latest_ver}"
            body = _format_lists_status_text(lists_result, "en") if lists_result else ""
            return _with_recovery(f"{head}\n{body}".strip())
        if status in {"gui-restart-scheduled", "gui-update-ready"}:
            return _with_recovery("The GUI is updating. The app will restart now.")
        if status == "unsupported":
            return _with_recovery("GUI auto-update is available only for the exe build.")
        if status == "winws-running":
            return _with_recovery("Could not stop the bypass automatically.")
        if status == "winws-reset-failed":
            return _with_recovery("Could not reset winws connections: " + str(result.get("error") or ""))
        if status == "offline":
            return _with_recovery("Could not check updates: check your internet connection.")
        if status == "bad-zip":
            return _with_recovery("The downloaded archive is damaged or is not a zip file.")
        if status == "permission":
            return _with_recovery("Could not write core files. Stop the bypass and try again.")
        return _with_recovery("Could not finish the update check.")

    def _finish_update_ui(self, result: dict) -> None:
        self._set_update_busy(False, self._format_update_result_text(result))
        parent = self.parent()
        if parent and hasattr(parent, "refresh_runtime_lists_after_user_change"):
            try:
                parent.refresh_runtime_lists_after_user_change()
            except Exception:
                pass
        try:
            core_ver = str(self.settings.value(FLOWSEAL_VER_KEY, FLOWSEAL_DEFAULT_VER)).strip() or FLOWSEAL_DEFAULT_VER
            self.version_label.setText(f"GUI: {APP_VERSION} + Core: {core_ver}")
        except Exception:
            pass

    def _on_update_worker_finished(self, mode: str, result: dict) -> None:
        if self.sender() is not self._update_worker:
            return
        self._update_worker = None
        parent = self.parent()
        if result.get("bypass_stopped") and parent and hasattr(parent, "_reflect_bypass_stopped_for_update"):
            try:
                parent._reflect_bypass_stopped_for_update()
            except Exception:
                pass
        elif parent and hasattr(parent, "_clear_update_check_bypass_exit_suppression"):
            try:
                parent._clear_update_check_bypass_exit_suppression()
            except Exception:
                pass

        if result.get("status") == "cancelled":
            self._set_update_busy(False, "")
            if self._update_close_after_finish:
                self.close()
            return

        if mode == "apply-gui":
            if result.get("ok") and result.get("status") == "gui-update-ready":
                self._set_update_busy(
                    True,
                    "Подготовка к установке обновления..."
                    if self.lang == "ru" else
                    "Preparing to install the update...",
                )
                try:
                    _prepare_gui_update_shutdown(parent, result)
                    self.close()
                except Exception as error:
                    self._finish_update_ui(
                        {"ok": False, "status": "error", "error": str(error)}
                    )
                return
            self._finish_update_ui(result)
            return

        if mode == "check" and result.get("ok") and result.get("status") == "gui-update-available":
            if self._update_close_after_finish:
                self._set_update_busy(False, "")
                self.close()
                return

            update_now, _skip = _show_gui_update_question(self, self.lang, result, allow_skip=False)
            if update_now and str(result.get("download_url") or ""):
                self._start_update_worker(
                    "apply-gui",
                    str(result.get("latest_ver") or ""),
                    str(result.get("download_url") or ""),
                    str(result.get("archive_sha256") or ""),
                    str(result.get("checksum_url") or ""),
                )
                return

            self._start_update_worker("check-core")
            return

        if mode in {"check", "check-core"} and result.get("ok") and result.get("status") == "update-available":
            latest_ver = str(result.get("latest_ver") or "")
            current_ver = str(result.get("current_ver") or "")
            download_url = str(result.get("download_url") or "")
            if self._update_close_after_finish:
                self._set_update_busy(False, "")
                self.close()
                return

            msg = QMessageBox(self)
            msg.setWindowTitle("Обновление" if self.lang == "ru" else "Update")
            msg.setIcon(QMessageBox.Icon.Question)
            msg.setText(
                (
                    f"Доступен новый релиз: {latest_ver}\n"
                    f"Текущая версия: {current_ver}\n\n"
                    "Будет обновлена папка core, пользовательская папка user сохранится.\n"
                    "Продолжить?"
                )
                if self.lang == "ru" else
                (
                    f"New release available: {latest_ver}\n"
                    f"Current version: {current_ver}\n\n"
                    "The core folder will be updated; your user folder will be kept.\n"
                    "Continue?"
                )
            )
            btn_yes = msg.addButton("Да" if self.lang == "ru" else "Yes", QMessageBox.ButtonRole.YesRole)
            msg.addButton("Нет" if self.lang == "ru" else "No", QMessageBox.ButtonRole.NoRole)
            msg.exec()

            if msg.clickedButton() == btn_yes and download_url:
                self._start_update_worker("apply", latest_ver, download_url)
                return

            result = {
                "ok": True,
                "status": "cancelled",
                "error": "",
            }
            self._set_update_busy(False, "Обновление отменено." if self.lang == "ru" else "Update cancelled.")
        else:
            self._finish_update_ui(result)

        if self._update_close_after_finish:
            self.close()

    def check_updates(self):
        self._update_close_after_finish = False
        parent = self.parent()
        if parent and hasattr(parent, "_prepare_bypass_for_update_check"):
            try:
                parent._prepare_bypass_for_update_check()
            except Exception:
                pass
        self._start_update_worker("check")

    def closeEvent(self, event):
        self.save_settings()
        if self._is_update_running():
            worker = self._update_worker
            mode = str(getattr(worker, "mode", "") or "")
            phase = str(getattr(worker, "phase", "") or "")
            if mode in {"check", "check-core"} and phase != "lists":
                self._detach_running_update_check()
                super().closeEvent(event)
                return

            self._update_close_after_finish = True
            self._set_update_status_text(
                "Дождитесь завершения установки обновлений..."
                if self.lang == "ru" else
                "Waiting for update installation to finish..."
            )
            event.ignore()
            return
        super().closeEvent(event)

class AutoTestWorker(QThread):
    progress = pyqtSignal(int, int, str)   # done, total, profile_name
    finished_ok = pyqtSignal(dict)
    finished_err = pyqtSignal(str)

    def __init__(self, core_dir: str, presets: dict, parent=None):
        super().__init__(parent)
        self.core_dir = core_dir
        self.presets = dict(presets)
        self._stop = False

    def stop(self):
        self._stop = True

    def run(self):
        try:
            good, bad = [], []
            names = list(self.presets.keys())
            total = len(names)

            for i, prof in enumerate(names, start=1):
                if self._stop:
                    return

                ok = self._test_profile_fast(prof, timeout_per_profile=10.0)
                if self._stop:
                    return

                if ok:
                    good.append(prof)
                else:
                    bad.append(prof)

                self.progress.emit(i, total, prof)

            self._kill_winws()
            self.finished_ok.emit({"good": good, "bad": bad, "raw": "", "error": ""})

        except Exception as e:
            try:
                self._kill_winws()
            except Exception as cleanup_error:
                self._alog("Cleanup failed: " + str(cleanup_error))
            self.finished_err.emit(str(e))

    def _test_profile_fast(self, profile_name: str, timeout_per_profile: float = 10.0) -> bool:
        _ensure_background_service(self.core_dir)
        self._kill_winws()
        try:
            time.sleep(0.4)
        except Exception:
            pass

        bat = os.path.join(self.core_dir, self.presets[profile_name])
        if not os.path.exists(bat):
            return False

        try:
            with open(AUTOLOG_FILE, "a", encoding="utf-8") as f:
                f.write(f"\n\n===== PROFILE: {profile_name} =====\n")
                f.write(f"BAT: {bat}\n")
                f.write(f"TIME: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        except Exception:
            pass

        proc = None
        try:
            proc = _launch_profile_process_core(bat, self.core_dir)

            start_deadline = time.time() + 12.0
            while time.time() < start_deadline:
                if self._stop:
                    return False
                if proc.poll() is None:
                    break
                time.sleep(0.1)
            else:
                self._alog("ERROR: winws.exe did not start within 12s")
                self._diag_winws_start_failure(bat)
                return False

            time.sleep(0.6)

            ok_discord = self._quick_https("https://discord.com/api/v9/experiments", timeout=3.5)
            ok_youtube = self._quick_https("https://www.youtube.com/generate_204", timeout=3.5)

            return (ok_discord or ok_youtube)

        finally:
            self._kill_winws()

    def _is_winws_running(self) -> bool:
        return _is_winws_running_silent()

    def _alog(self, line: str) -> None:
        try:
            with open(AUTOLOG_FILE, "a", encoding="utf-8") as f:
                f.write(line.rstrip("\n") + "\n")
        except Exception:
            pass

    def _diag_winws_start_failure(self, bat: str) -> None:
        self._alog("DIAG: " + str(_bypass_service.snapshot()))

    def _quick_https(self, url: str, timeout: float = 3.0) -> bool:
        headers = {"User-Agent": "ZapretGUI-Test"}
        for _ in range(2):
            try:
                s = requests.Session()
                s.trust_env = True
                r = s.get(url, timeout=timeout, headers=headers, stream=True, allow_redirects=False, verify=True)
                return (200 <= r.status_code < 500)
            except Exception as e:
                self._alog(f"HTTPS ERROR for {url}: {repr(e)}")
        return False

    def _kill_winws(self):
        _force_stop_blockers()


class AdaptiveSearchWorker(QThread):
    progress_update = pyqtSignal(float, str)
    completed = pyqtSignal(object)
    failed = pyqtSignal(str)
    cancelled = pyqtSignal()

    def __init__(
        self,
        app_dir: str,
        runtime_source: str,
        runtime_destination: str,
        report_path: str,
        parent=None,
    ):
        super().__init__(parent)
        self.app_dir = Path(app_dir)
        self.runtime_source = Path(runtime_source)
        self.runtime_destination = Path(runtime_destination)
        self.report_path = Path(report_path)
        self.cancel_event = threading.Event()
        self._progress_log: list[dict] = []
        self._started_at = 0.0
        self._last_progress = 0.0
        self._effective_targets: list[str] = []
        self._ignored_targets: list[str] = []

    def stop(self) -> None:
        self.cancel_event.set()

    def _emit_progress(self, value: float, label: str) -> None:
        value = max(self._last_progress, min(1.0, max(0.0, float(value))))
        self._last_progress = value
        elapsed = max(0.0, time.monotonic() - self._started_at)
        self._progress_log.append({
            "elapsed": round(elapsed, 3),
            "progress": round(value, 4),
            "label": str(label or ""),
        })
        if len(self._progress_log) > 600:
            del self._progress_log[:100]
        self.progress_update.emit(value, str(label or ""))

    def _install_progress(self, done: int, total: int, _name: str) -> None:
        if self.cancel_event.is_set():
            raise AdaptiveSearchCancelled()
        fraction = float(done) / float(max(1, total))
        self._emit_progress(0.009 * fraction, "Подготовка компонентов проверки")

    def _write_report(self, outcome=None, unexpected_error: str = "") -> None:
        try:
            payload = {
                "schema": 1,
                "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                "timeout_seconds": ADAPTIVE_TIMEOUT_SECONDS,
                "targets": list(ADAPTIVE_TARGET_URLS),
                "effective_targets": list(self._effective_targets),
                "ignored_targets": list(self._ignored_targets),
                "progress": list(self._progress_log),
                "unexpected_error": str(unexpected_error or ""),
                "outcome": outcome.to_dict() if outcome is not None else None,
            }
            data = json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")
            _atomic_write_bytes(str(self.report_path), data)
        except Exception as exc:
            print("Adaptive report write error:", exc)

    def run(self) -> None:
        self._started_at = time.monotonic()
        try:
            self._emit_progress(0.0, "Подготовка компонентов проверки")
            ensure_adaptive_runtime(
                self.runtime_source,
                self.runtime_destination,
                progress=self._install_progress,
                project_root=self.app_dir,
            )
            if self.cancel_event.is_set():
                raise AdaptiveSearchCancelled()

            paths = AdaptiveRuntimePaths.for_zapret_gui(
                self.app_dir,
                self.runtime_destination,
            )
            parsed_targets = parse_adaptive_targets(
                "\n".join(ADAPTIVE_TARGET_URLS),
                include_quic=True,
            )
            # Only YouTube and Discord have a complete, stable service matrix.
            # Generic sites belong in the domain lists; making one of them a
            # mandatory probe previously caused an unrelated RuTracker outage
            # to reject otherwise fully validated YouTube/Discord profiles.
            targets, ignored_targets = select_adaptive_profile_targets(parsed_targets)
            self._effective_targets = [target.url for target in targets]
            self._ignored_targets = [target.url for target in ignored_targets]
            if not targets:
                raise RuntimeError("Adaptive target matrix is empty")
            engine = AdaptiveSearchEngine(
                paths,
                timeout=ADAPTIVE_TIMEOUT_SECONDS,
                progress=self._emit_progress,
                cancel_event=self.cancel_event,
            )
            outcome = engine.run(targets)
            self._write_report(outcome=outcome)
            if self.cancel_event.is_set() or outcome.message == "Поиск отменён":
                self.cancelled.emit()
            else:
                self.completed.emit(outcome)
        except AdaptiveSearchCancelled:
            self._write_report(unexpected_error="Поиск отменён пользователем")
            self.cancelled.emit()
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            self._write_report(unexpected_error=detail)
            self.failed.emit(detail)

class ListsUpdateWorker(QThread):
    finished_sync = pyqtSignal(dict)

    def __init__(self, core_lists_dir: str, user_lists_dir: str, parent=None):
        super().__init__(parent)
        self.core_lists_dir = core_lists_dir
        self.user_lists_dir = user_lists_dir

    def run(self):
        try:
            settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
            attempts = 0
            result = {}
            for retry_delay in (0.0, *LISTS_STARTUP_RETRY_DELAYS_SECONDS):
                if self.isInterruptionRequested() or APP_SHUTTING_DOWN.is_set():
                    return
                if retry_delay:
                    deadline = time.monotonic() + retry_delay
                    while time.monotonic() < deadline:
                        if self.isInterruptionRequested() or APP_SHUTTING_DOWN.is_set():
                            return
                        time.sleep(min(0.2, deadline - time.monotonic()))

                attempts += 1
                result = _sync_flowseal_lists(settings, skip_recent=True)
                if result.get("ok"):
                    break

            # Startup synchronization is opportunistic: local/bundled lists
            # remain usable when Windows has not finished bringing networking up.
            result["startup_attempts"] = attempts
            result["used_cached_lists"] = not bool(result.get("ok"))
            ai_result = _sync_ai_dns_if_enabled(
                settings,
                min_retry_seconds=DNS_MALW_STARTUP_SYNC_MIN_INTERVAL_SECONDS,
            )
            result["ai_dns_error"] = str(ai_result.get("error") or "")
            result["gui_update"] = _check_startup_gui_update_if_due(settings)
        except Exception as e:
            result = {
                "ok": False,
                "offline": False,
                "flowseal_updated": 0,
                "flowseal_error": "",
                "flowseal_offline": False,
                "gaming_updated": 0,
                "gaming_error": "",
                "gaming_offline": False,
                "gaming_silent_missing": False,
                "skipped_recent": False,
                "ai_dns_error": "",
                "gui_update": {},
                "error": str(e),
            }

        self.finished_sync.emit(result)


class DnsMalwLinkWorker(QThread):
    finished_dns = pyqtSignal(str, dict)

    def __init__(self, action: str, parent=None):
        super().__init__(parent)
        self.action = (action or "").strip().lower()

    def run(self):
        if self.action == "disable":
            result = _disable_dns_malw_link()
        elif self.action == "enable":
            result = _enable_dns_malw_link()
        else:
            result = {"ok": False, "error": "invalid-action"}
        self.finished_dns.emit(self.action, result)


class BackgroundSetupWorker(QThread):
    completed = pyqtSignal(str)

    def __init__(self, core_dir: str, parent=None):
        super().__init__(parent)
        self.core_dir = core_dir

    def run(self):
        error = ""
        try:
            _ensure_background_service(self.core_dir)
        except Exception as exc:
            error = str(exc)
        self.completed.emit(error)


class BypassToggleWorker(QThread):
    """Perform the blocking part of turning the main bypass on or off.

    QProcess/subprocess setup, hosts writes and service termination can all wait
    on Windows.  Keeping them here lets the power-button animation start on the
    GUI thread immediately.
    """
    finished_bypass = pyqtSignal(str, dict)

    def __init__(
        self,
        action: str,
        script: str = "",
        core_dir: str = "",
        settings_path: str = SETTINGS_FILE,
        adaptive_hosts_owned: bool = False,
        telegram_proxy: TelegramProxyController | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.action = (action or "").strip().lower()
        self.script = str(script or "")
        self.core_dir = str(core_dir or "")
        self.settings_path = str(settings_path or SETTINGS_FILE)
        self.adaptive_hosts_owned = bool(adaptive_hosts_owned)
        self.telegram_proxy = telegram_proxy

    def _cancelled(self) -> bool:
        return bool(self.isInterruptionRequested() or APP_SHUTTING_DOWN.is_set())

    def run(self) -> None:
        result = {
            "ok": False,
            "error": "",
            "process": None,
            "adaptive_hosts_owned": False,
            "adaptive_hosts_error": "",
            "telegram_error": "",
        }
        owned_by_this_start = False
        settings = QSettings(self.settings_path, QSettings.Format.IniFormat)
        try:
            if self.action == "stop":
                if _is_winws_running_silent() and _bypass_service.pipe is None:
                    _ensure_background_service(self.core_dir)
                _force_stop_blockers(self.core_dir)
                if _is_winws_running_silent():
                    raise RuntimeError("winws process did not stop")
                result["adaptive_hosts_error"] = _release_adaptive_profile_hosts_after_stop(
                    self.adaptive_hosts_owned,
                    settings,
                )
                result["ok"] = True
            elif self.action == "start":
                if self._cancelled():
                    raise RuntimeError("cancelled")
                _ensure_background_service(self.core_dir)
                if self._cancelled():
                    raise RuntimeError("cancelled")
                _ensure_user_lists_initialized()
                _apply_game_mode_state_to_core(settings)

                if _is_telegram_mode_enabled(settings):
                    _apply_telegram_mode_files(True, settings)
                    if self.telegram_proxy is not None and not self.telegram_proxy.is_running():
                        try:
                            self.telegram_proxy.start(
                                _get_telegram_proxy_port(settings),
                                _get_telegram_proxy_secret(settings),
                            )
                            _set_telegram_last_error("", settings)
                        except Exception as error:
                            result["telegram_error"] = str(error)
                            _set_telegram_last_error(str(error), settings)

                _sync_telegram_runtime_lists(settings)
                _rebuild_runtime_lists(settings)
                if self._cancelled():
                    raise RuntimeError("cancelled")

                _force_stop_blockers(self.core_dir)
                if self._cancelled():
                    raise RuntimeError("cancelled")

                previous_hosts_error = _release_adaptive_profile_hosts_after_stop(
                    self.adaptive_hosts_owned,
                    settings,
                )
                if previous_hosts_error:
                    result["adaptive_hosts_error"] = previous_hosts_error

                owned_by_this_start = _prepare_adaptive_profile_hosts_for_launch(self.script, settings)
                if self._cancelled():
                    raise RuntimeError("cancelled")

                result["process"] = _launch_profile_process_core(self.script, self.core_dir, settings)
                if self._cancelled():
                    _bypass_service.stop()
                    raise RuntimeError("cancelled")
                result["adaptive_hosts_owned"] = bool(owned_by_this_start)
                result["ok"] = True
            else:
                result["error"] = "invalid-action"
        except Exception as error:
            result["error"] = str(error)
            try:
                result["running"] = _is_winws_running_silent()
            except Exception:
                result["running"] = True  # An unknown state must not claim a successful stop.
            if owned_by_this_start:
                cleanup_error = _release_adaptive_profile_hosts_after_stop(True, settings)
                if cleanup_error and not result["adaptive_hosts_error"]:
                    result["adaptive_hosts_error"] = cleanup_error
        self.finished_bypass.emit(self.action, result)


class ReleaseUpdateWorker(QThread):
    finished_update = pyqtSignal(str, dict)
    download_progress = pyqtSignal(int, int)

    def __init__(
        self,
        mode: str,
        latest_ver: str = "",
        download_url: str = "",
        archive_sha256: str = "",
        checksum_url: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.mode = (mode or "check").strip().lower()
        self.latest_ver = latest_ver
        self.download_url = download_url
        self.archive_sha256 = archive_sha256
        self.checksum_url = checksum_url
        self.phase = "version" if self.mode in {"check", "check-core"} else "apply"

    def run(self):
        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
        if self.mode == "apply":
            self.phase = "apply"
            result = _apply_flowseal_update_async(self.latest_ver, self.download_url, settings)
        elif self.mode == "apply-gui":
            self.phase = "apply-gui"
            result = _schedule_gui_update_restart(
                self.latest_ver,
                self.download_url,
                self.archive_sha256,
                self.checksum_url,
                progress_callback=lambda done, total: self.download_progress.emit(done, total),
            )
        elif self.mode == "check-core":
            result = _check_flowseal_update_with_winws_recovery(
                settings,
                should_cancel=self.isInterruptionRequested,
                phase_callback=lambda phase: setattr(self, "phase", phase),
            )
        else:
            result = _check_all_updates_async(
                settings,
                should_cancel=self.isInterruptionRequested,
                phase_callback=lambda phase: setattr(self, "phase", phase),
            )
        self.finished_update.emit(self.mode, result)


class GameModeRestartWorker(QThread):
    finished_restart = pyqtSignal(str)

    def run(self):
        error = ""
        try:
            _force_stop_blockers()
        except Exception as e:
            error = str(e)
        self.finished_restart.emit(error)


class TelegramModeWorker(QThread):
    finished_telegram = pyqtSignal(str, dict)

    def __init__(self, action: str, proxy_controller: TelegramProxyController | None, parent=None):
        super().__init__(parent)
        self.action = (action or "").strip().lower()
        self.proxy_controller = proxy_controller

    def run(self):
        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
        result = {
            "ok": False,
            "enabled": False,
            "proxy_running": False,
            "proxy_port": _get_telegram_proxy_port(settings),
            "proxy_secret": _get_telegram_proxy_secret(settings),
            "proxy_link": _get_telegram_proxy_link(settings),
            "hosts_ok": True,
            "hosts_error": "",
            "hosts_permission_error": False,
            "error": "",
        }

        def _record_hosts_result(hosts_ok: bool) -> None:
            result["hosts_ok"] = bool(hosts_ok)
            if hosts_ok:
                result["hosts_error"] = ""
                result["hosts_permission_error"] = False
                return
            hosts_error = str(
                settings.value(TELEGRAM_MODE_HOSTS_LAST_ERROR_KEY, "")
                or settings.value(TELEGRAM_MODE_LAST_ERROR_KEY, "")
                or ""
            ).strip()
            result["hosts_error"] = hosts_error
            result["hosts_permission_error"] = _is_hosts_permission_error_message(hosts_error)
            if hosts_error:
                result["error"] = hosts_error

        try:
            if self.action == "enable":
                _set_telegram_mode_enabled(True, settings)
                _set_telegram_last_error("", settings)
                _record_hosts_result(_apply_telegram_mode_files(True, settings))
                _rebuild_runtime_lists(settings)
                if self.proxy_controller is None:
                    raise RuntimeError("Telegram proxy controller is not available")
                self.proxy_controller.start(result["proxy_port"], result["proxy_secret"])
                result["enabled"] = True
                result["proxy_running"] = self.proxy_controller.is_running()
                result["proxy_link"] = self.proxy_controller.proxy_link()
                result["ok"] = True
            elif self.action == "disable":
                _set_telegram_mode_enabled(False, settings)
                if self.proxy_controller is not None:
                    self.proxy_controller.stop()
                _record_hosts_result(_apply_telegram_mode_files(False, settings))
                _rebuild_runtime_lists(settings)
                if result["hosts_ok"]:
                    _set_telegram_last_error("", settings)
                result["enabled"] = False
                result["proxy_running"] = False
                result["ok"] = bool(result["hosts_ok"])
            elif self.action == "restore":
                if _is_telegram_mode_enabled(settings):
                    _record_hosts_result(_apply_telegram_mode_files(True, settings))
                    _rebuild_runtime_lists(settings)
                    if self.proxy_controller is None:
                        raise RuntimeError("Telegram proxy controller is not available")
                    self.proxy_controller.start(result["proxy_port"], result["proxy_secret"])
                    result["enabled"] = True
                    result["proxy_running"] = self.proxy_controller.is_running()
                    result["proxy_link"] = self.proxy_controller.proxy_link()
                else:
                    _record_hosts_result(True)
                    _rebuild_runtime_lists(settings)
                    result["enabled"] = False
                    result["proxy_running"] = False
                if result["hosts_ok"]:
                    _set_telegram_last_error("", settings)
                result["ok"] = True
            elif self.action == "cleanup":
                _set_telegram_mode_enabled(False, settings)
                if self.proxy_controller is not None:
                    self.proxy_controller.stop()
                _record_hosts_result(_apply_telegram_mode_files(False, settings))
                _rebuild_runtime_lists(settings)
                if result["hosts_ok"]:
                    _set_telegram_last_error("", settings)
                result["enabled"] = False
                result["proxy_running"] = False
                result["ok"] = True
            else:
                raise RuntimeError("Unknown Telegram Mode action")
        except Exception as e:
            result["error"] = str(e)
            result["hosts_permission_error"] = _is_hosts_permission_error_message(result["error"])
            result["enabled"] = _is_telegram_mode_enabled(settings)
            try:
                result["proxy_running"] = bool(
                    self.proxy_controller is not None and self.proxy_controller.is_running()
                )
                if self.proxy_controller is not None and result["proxy_running"]:
                    result["proxy_link"] = self.proxy_controller.proxy_link()
            except Exception:
                result["proxy_running"] = False
            _set_telegram_last_error(result["error"], settings)

        self.finished_telegram.emit(self.action, result)
