
import sys
import os
import subprocess
from PyQt6.QtCore import Qt, QSettings, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap, QAction
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QCheckBox, QMessageBox, QSizePolicy,
    QSystemTrayIcon, QMenu, QTextBrowser
)
import hashlib
import shutil
import requests
import zipfile
import io

def extract_files_from_meipass():
    if hasattr(sys, '_MEIPASS'):
        base_src = sys._MEIPASS
    else:
        base_src = os.path.dirname(__file__)

    for folder in ('core', 'flags'):
        src_path = os.path.join(base_src, folder)
        dst_path = os.path.join(APP_DIR, folder)

        for root, dirs, files in os.walk(src_path):
            rel = os.path.relpath(root, src_path)
            target = os.path.join(dst_path, rel)
            os.makedirs(target, exist_ok=True)

            for f in files:
                s = os.path.join(root, f)
                d = os.path.join(target, f)
                if not os.path.exists(d):
                    shutil.copy2(s, d)

APP_DIR = os.path.join(os.path.expanduser('~'), 'ZapretGUI')
os.makedirs(APP_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(APP_DIR, 'settings.ini')

def update_domain_files():
    try:
        print("[INFO] Проверка обновления файлов zapret...")
        url = "https://github.com/bol-van/zapret-win-bundle/archive/refs/heads/master.zip"
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        zip_content = response.content

        zip_hash = hashlib.sha256(zip_content).hexdigest()

        version_file = os.path.join(APP_DIR, 'core', 'files_version.txt')
        if os.path.exists(version_file):
            with open(version_file, 'r') as f:
                existing_hash = f.read().strip()
            if existing_hash == zip_hash:
                print("[INFO] Файлы актуальны, обновление не требуется.")
                return

        z = zipfile.ZipFile(io.BytesIO(zip_content))

        files_prefix = "zapret-win-bundle-master/zapret-winws/files/"
        target_dir = os.path.join(APP_DIR, 'core', 'files')
        os.makedirs(target_dir, exist_ok=True)

        updated_files = 0
        for file in z.namelist():
            if file.startswith(files_prefix) and not file.endswith('/'):
                relative_path = os.path.relpath(file, files_prefix)
                target_path = os.path.join(target_dir, relative_path)
                os.makedirs(os.path.dirname(target_path), exist_ok=True)
                with z.open(file) as src, open(target_path, "wb") as dst:
                    dst.write(src.read())
                updated_files += 1

        with open(version_file, 'w') as f:
            f.write(zip_hash)

        print(f"[INFO] Обновлено файлов: {updated_files}")

    except Exception as e:
        print(f"[ERROR] Не удалось обновить списки: {e}")
        from PyQt6.QtWidgets import QMessageBox
        msg = QMessageBox()
        msg.setIcon(QMessageBox.Icon.Warning)
        msg.setWindowTitle("Ошибка обновления")
        msg.setText("Обновление списков доменов не удалось выполнить из-за отсутствия подключения или ошибок системы.\nСледующее обновление будет выполнено при следующем запуске программы.")
        msg.setStandardButtons(QMessageBox.StandardButton.Ok)

        icon_path = os.path.join(APP_DIR, 'flags', 'z.ico')
        if os.path.exists(icon_path):
            msg.setWindowIcon(QIcon(icon_path))

        msg.exec()

translations = {
    'ru': {
        'Settings': 'Настройки',
        'Autostart program': 'Автозапуск программы',
        'Start minimized': 'Запускать свернутым',
        'Autostart profile': 'Профиль для автозагрузки',
        'Service mode': 'Сервисный режим',
        'Install Service': 'Установить сервис',
        'Remove Services': 'Сбросить соединения winws',
        'Check Updates': 'Проверить обновления Zapret',
        'About:': 'Подробнее:',
        'Off': 'Выключен',
        'On: {}': 'Включён: {}',
        'Instruction': 'Инструкция',
        'Instruction Text': """
        <b>1.</b> Выберите из выпадающего списка <b>профиль настроек</b>, затем нажмите на <span style="color:green;"><b>большую зелёную кнопку</b></span>, чтобы запустить обход блокировок. <i>(По умолчанию используется профиль <b>General</b>).</i><br><br>
        <b>2.</b> Если выбранный профиль не сработал — <span style="color:red;"><b>нажмите на красную кнопку</b></span> для отключения, выберите другой профиль и повторите запуск. Продолжайте, пока не найдёте рабочий вариант.<br><br>
        <b>3.</b> При проблемах с запуском или остановкой обхода откройте раздел <b>«Настройки»</b> и нажмите кнопку <b>"Сбросить соединения winws"</b>. Дождитесь закрытия консоли. Если вместо <b>Success</b> появится ошибка — полностью перезапустите приложение и повторите. Это сбросит конфигурации подключения и позволит всё запустить заново.<br><br>
        <b>4.</b> В разделе <b>«Настройки»</b> также можно включить <b>автоматический запуск обхода</b> при запуске программы. <u>Важно:</u> это работает только при включённой автозагрузке приложения. Отметьте <b>«Запускать вместе с системой»</b>, выберите нужный профиль — и при запуске Windows обход будет активен автоматически, в трее.<br><br>
        <span style="color:#cc0000;"><b>5. ПРИМЕЧАНИЕ:</b> Для обхода блокировки <b>Discord</b> рекомендуется использовать профиль <b>Discord</b>. Однако в некоторых случаях профиль <b>General</b> также обеспечивает корректную работу как <b>YouTube</b>, так и <b>Discord</b>.</span>
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
        'Check Updates': 'Check Updates Zapret',
        'About:': 'About:',
        'Off': 'Off',
        'On: {}': 'On: {}',
        'Instruction': 'Instruction',
        'Instruction Text': """
        <b>1.</b> Select a <b>profile</b> from the dropdown list, then click the <span style="color:green;"><b>big green button</b></span> to start the bypass. <i>(By default, the <b>General</b> profile is used.)</i><br><br>  
        <b>2.</b> If the selected profile doesn’t work — <span style="color:red;"><b>click the red button</b></span> to stop, choose another profile and try again. Repeat this process until you find one that works for you.<br><br>
        <b>3.</b> If you experience issues with enabling or disabling the bypass, go to the <b>“Settings”</b> section and click <b>“Reset winws connections”</b>. Wait until the console closes. If an error appears instead of <b>Success</b>, fully restart the application and try again. This process resets all bypass connection settings and should restore proper functionality.<br><br>
        <b>4.</b> In the <b>“Settings”</b> section, you can also enable <b>auto-start</b> for the bypass. <u>Note:</u> this only works if the app itself is enabled to auto-launch. Just check <b>“Run with system startup”</b>, choose your desired profile, and the bypass will automatically run in the system tray when Windows starts.<br><br>
        <span style="color:#cc0000;"><b>5. NOTE:</b> For bypassing <b>Discord</b>, it is recommended to use the <b>Discord</b> profile. However, in some cases, the <b>General</b> profile works fine for both <b>YouTube</b> and <b>Discord</b>.</span>
        """,
        'Enable bypass': 'Enable bypass',
        'Disable bypass': 'Disable bypass',
        'Select profile': 'Select profile',
        'Exit': 'Exit',
        'Open': 'Open',
        'Minimize to tray': 'Minimize to tray',
    }
}


class SettingsDialog(QDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.lang = settings.value('lang', 'ru')
        self.init_ui()
        self.load_settings()
        self.retranslate_ui()

    def t(self, key, *args):
        return translations[self.lang].get(key, key).format(*args)

    def init_ui(self):
        self.setWindowTitle('')
        self.setFixedSize(400, 320)
        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        hl = QHBoxLayout()
        hl.addStretch()
        flag_dir = os.path.join(APP_DIR, 'flags')
        for code in ('ru', 'en'):
            pix = QPixmap(os.path.join(flag_dir, f'{code}.png')).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            btn = QPushButton()
            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(24, 24))
            btn.setFixedSize(31, 31)
            btn.clicked.connect(lambda _, c=code: self.change_lang(c))
            hl.addWidget(btn)
        hl.addStretch()
        layout.addLayout(hl)

        cb_layout = QHBoxLayout()
        self.autostart_cb = QCheckBox()
        self.minimized_cb = QCheckBox()
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
        self.profile_cb = QComboBox()
        self.profile_cb.addItem(" ")  # default
        self.profile_cb.currentIndexChanged.connect(self.on_autostart_profile_selected)
        self.profile_enable_cb = QCheckBox()
        self.profile_enable_cb.setEnabled(False)
        profile_row.addWidget(self.profile_cb)
        profile_row.addWidget(self.profile_enable_cb)
        self.profile_enable_cb.setStyleSheet("padding-right: 4px;")
        layout.addLayout(profile_row)

        self.svc_btn = QPushButton()
        self.svc_btn.setFixedHeight(30)
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

        self.about_label = QLabel()
        self.about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.about_label.setTextFormat(Qt.TextFormat.RichText)
        self.about_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.about_label.setOpenExternalLinks(True)
        layout.addWidget(self.about_label)

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
            '<a href="https://github.com/medvedeff-true?tab=repositories" style="color:#3399ff;">Medvedeff</a>'
        )

    def change_lang(self, lang_code):
        self.lang = lang_code
        self.settings.setValue('lang', lang_code)
        self.retranslate_ui()
        parent = self.parent()
        if parent and hasattr(parent, 'change_lang'):
            parent.change_lang(lang_code)

    def on_service_mode(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'service.bat')
        if os.path.exists(script):
            subprocess.Popen([script], shell=True, close_fds=True)
        else:
            QMessageBox.warning(self, self.t('Settings'), 'service.bat не найден')

    def install_service(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'install_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'install_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)

    def install_discord_service(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'install_discord_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'install_discord_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)

    def remove_service(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'uninstall.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'remove_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)

    def check_updates(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'update_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'update_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE, close_fds=True)

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)

class MainWindow(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings
        self.lang = settings.value('lang', 'ru')
        self.autostart = settings.value('autostart', False, type=bool)
        self.minimized = settings.value('minimized', False, type=bool)
        self.last_profile = settings.value('last_profile', 'General')

        self.core_dir = os.path.join(APP_DIR, 'core')
        self.patch_bat_files()
        self.unblock_executables()
        self.presets = {}
        self.process = None

        self.init_ui()
        self.retranslate_ui()
        self.set_autostart(self.autostart)
        self.init_tray_icon()
        if self.minimized:
            self.hide()
        else:
            self.show()

        autostart_profile = settings.value('autostart_profile', ' ')
        autostart_enabled = settings.value('autostart_profile_enabled', False, type=bool)

        if self.autostart and autostart_enabled and autostart_profile in self.presets:
            self.cb.setCurrentText(autostart_profile)
            self.toggle_btn.setChecked(True)
            QTimer.singleShot(1000, lambda: self.on_toggle(True))

    def init_tray_icon(self):
        icon_path = os.path.join(APP_DIR, 'flags', 'z.ico')
        self.tray = QSystemTrayIcon(QIcon(icon_path), self)

        self.tray_menu = QMenu()
        self.action_open = QAction(self.t('Open'), self)
        self.action_open.triggered.connect(self.showNormal)
        self.tray_menu.addAction(self.action_open)
        self.tray_menu.addSeparator()
        self.action_start = QAction(self.t('Enable bypass'), self)
        self.action_start.triggered.connect(lambda: self.toggle_tray(True))
        self.tray_menu.addAction(self.action_start)
        self.action_stop = QAction(self.t('Disable bypass'), self)
        self.action_stop.triggered.connect(lambda: self.toggle_tray(False))
        self.tray_menu.addAction(self.action_stop)
        self.tray_menu.addSeparator()
        self.preset_menu = QMenu(self.t('Select profile'), self)
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
        self.preset_menu.setTitle(self.t('Select profile'))
        self.exit_action.setText(self.t('Exit'))
        self.tray_btn.setToolTip(self.t('Minimize to tray'))

    def update_tray_status(self):
        running = self.toggle_btn.isChecked()
        self.action_start.setEnabled(not running)
        self.action_stop.setEnabled(running)
        self.tray.setToolTip(self.get_tray_tooltip())
        self.update_tray_presets()

    def get_tray_tooltip(self):
        if hasattr(self, 'toggle_btn') and self.toggle_btn.isChecked():
            return self.t('On: {}', self.cb.currentText())
        return self.t('Off')

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.showNormal()
            self.activateWindow()

    def update_tray_presets(self):
        self.preset_menu.clear()
        current = self.cb.currentText()
        for name in self.presets:
            action = QAction(name, self)
            action.setCheckable(True)
            action.setChecked(name == current)
            action.triggered.connect(lambda _, n=name: self.select_preset_from_tray(n))
            self.preset_menu.addAction(action)

    def select_preset_from_tray(self, name):
        self.cb.blockSignals(True)
        self.cb.setCurrentText(name)
        self.cb.blockSignals(False)
        self.on_profile_changed(name)

    def toggle_tray(self, state: bool):
        if self.toggle_btn.isChecked() != state:
            self.toggle_btn.setChecked(state)
            self.on_toggle(state)
        self.update_tray_status()

    def tray_exit(self):
        if self.is_winws_running():
            title = self.t('Exit')
            text = (
                "Обход сейчас активен. Вы хотите завершить его и выйти?"
                if self.lang == 'ru'
                else "Bypass is currently running. Do you want to stop it and exit?"
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
            if msg.clickedButton() == btn_yes:
                os.system('taskkill /IM winws.exe /F')
                QApplication.instance().quit()
            return
        QApplication.instance().quit()

    def reload_presets(self):
        self.presets = {'General': 'general.bat', 'Discord': 'discord.bat'}
        for fn in sorted(os.listdir(self.core_dir)):
            if fn.lower().endswith('.bat') and fn not in (
                'general.bat', 'discord.bat', 'service.bat', 'cloudflare_switch.bat'
            ):
                self.presets[os.path.splitext(fn)[0]] = fn

        self.cb.blockSignals(True)
        self.cb.clear()
        self.cb.addItems(self.presets.keys())
        self.cb.setCurrentText(self.settings.value('last_profile', 'General'))
        self.cb.blockSignals(False)

        self.cb.currentTextChanged.connect(self.on_profile_changed)
        self.update_tray_presets()
        self.update_tray_status()

    def on_profile_changed(self, text):
        self.settings.setValue('last_profile', text)
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

    def patch_bat_files(self):
        skip_files = {'service.bat', 'install_service.bat', 'uninstall.bat', 'update_service.bat'}
        bin_dir = os.path.join(APP_DIR, 'core', 'bin') + '\\'
        files_dir = os.path.join(APP_DIR, 'core', 'files') + '\\'
        winws_exe = os.path.join(bin_dir, 'winws.exe')

        for fn in os.listdir(self.core_dir):
            if not fn.lower().endswith('.bat') or fn in skip_files:
                continue

            path = os.path.join(self.core_dir, fn)

            # Если файл уже пропатчен — пропускаем
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'PATCHED_BY_GUI' in content:
                    print(f'[=] Уже пропатчен: {fn}')
                    continue

            # Делаем резервную копию
            backup_path = path + '.backup'
            if not os.path.exists(backup_path):
                shutil.copy2(path, backup_path)
                print(f'[B] Создан бэкап: {backup_path}')

            # Собираем новый контент батника:
            new_lines = []
            new_lines.append('@echo off\n')
            new_lines.append('chcp 65001 > nul\n')
            new_lines.append(':: 65001 - UTF-8\n')
            new_lines.append('\n')
            new_lines.append('cd /d "%~dp0"\n')
            new_lines.append('call service.bat status_zapret\n')
            new_lines.append('call service.bat check_updates\n')
            new_lines.append('echo:\n')
            new_lines.append('\n')
            new_lines.append(f'set "BIN={bin_dir}"\n')
            new_lines.append(f'set "FILES={files_dir}"\n')
            new_lines.append('\n')
            new_lines.append('@echo PATCHED_BY_GUI\n')

            args = (
                f'"{winws_exe}" '
                '--wf-tcp=80,443 --wf-udp=443,50000-50099 '
                '--filter-tcp=80 --dpi-desync=fake,fakedsplit --dpi-desync-autottl=2 --dpi-desync-fooling=md5sig --new '
                '--filter-tcp=443 --hostlist="%FILES%list-youtube.txt" --dpi-desync=fake,multidisorder '
                '--dpi-desync-split-pos=1,midsld --dpi-desync-repeats=11 --dpi-desync-fooling=md5sig '
                '--dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com --new '
                '--filter-tcp=443 --dpi-desync=fake,multidisorder --dpi-desync-split-pos=midsld '
                '--dpi-desync-repeats=6 --dpi-desync-fooling=badseq,md5sig --new '
                '--filter-udp=443 --hostlist="%FILES%list-youtube.txt" --dpi-desync=fake '
                '--dpi-desync-repeats=11 --dpi-desync-fake-quic="%FILES%quic_initial_www_google_com.bin" --new '
                '--filter-udp=443 --dpi-desync=fake --dpi-desync-repeats=11 --new '
                '--filter-udp=50000-50099 --filter-l7=discord,stun --dpi-desync=fake\n'
            )

            new_lines.append(args)

            with open(path, 'w', encoding='utf-8') as f:
                f.writelines(new_lines)

            print(f'[+] Полностью переписан: {fn}')

    def open_instruction(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('Instruction'))

        if self.lang == 'ru':
            dialog.setFixedSize(410, 590)
        else:
            dialog.setFixedSize(410, 490)

        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        dialog.setModal(False)

        layout = QVBoxLayout(dialog)

        browser = QTextBrowser(dialog)
        browser.setHtml(
            f"<html><body style='font-family:Segoe UI; font-size:10.5pt'>{self.t('Instruction Text')}</body></html>")
        browser.setOpenExternalLinks(True)
        browser.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(browser)

        dialog.show()

    def t(self, key, *args):
        return translations[self.lang].get(key, key).format(*args)

    def change_lang(self, lang_code):
        self.lang = lang_code
        self.settings.setValue('lang', lang_code)
        self.retranslate_ui()
        self.retranslate_tray()
        self.update_tray_presets()
        self.update_tray_status()

    def init_ui(self):
        self.setFixedSize(300, 320)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self.status_lbl = QLabel()
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_lbl)

        self.toggle_btn = QPushButton()
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.setFixedSize(100, 100)

        icon_path = os.path.join(os.path.dirname(__file__), 'flags', 'toggle.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QIcon.fromTheme("media-playback-start")
        self.toggle_btn.setIcon(icon)
        self.toggle_btn.setIconSize(QSize(48, 48))

        self.toggle_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid #ffffff;
                border-radius: 50px;
                background-color: green;
                padding-left: 7px;
                padding-right: 0px;
            }
            QPushButton::icon {
                alignment: center;
            }
        """)
        self.toggle_btn.setContentsMargins(0, 0, 0, 0)

        self.toggle_btn.clicked.connect(self.on_toggle)
        hl = QHBoxLayout();
        hl.addStretch();
        hl.addWidget(self.toggle_btn);
        hl.addStretch()
        layout.addLayout(hl)

        self.tray_btn = QPushButton()
        self.tray_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'flags', 'tray.ico')))
        self.tray_btn.setIconSize(QSize(24, 24))
        self.tray_btn.setToolTip(self.t('Minimize to tray'))
        self.tray_btn.setFixedSize(28, 28)
        self.tray_btn.setStyleSheet("border: none;")

        self.tray_btn.clicked.connect(self.hide)

        tray_layout = QHBoxLayout()
        tray_layout.addStretch()
        tray_layout.addWidget(self.tray_btn)
        layout.addLayout(tray_layout)

        self.cb = QComboBox()
        self.reload_presets()
        self.cb.setCurrentText(self.last_profile)
        self.cb.currentTextChanged.connect(self.on_profile_changed)
        layout.addWidget(self.cb)

        self.settings_btn = QPushButton()
        self.settings_btn.setFixedHeight(30)
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        self.instruction_btn = QPushButton("Инструкция")
        self.instruction_btn.setFixedHeight(30)
        self.instruction_btn.clicked.connect(self.open_instruction)
        layout.addWidget(self.instruction_btn)

        self.powered_lbl = QLabel(
            '<span style="color:white;">Powered by </span>'
            '<span style="color:green;">Medvedeff</span>'
            '<span style="color:white;"> & </span>'
            '<span style="color:red;">Zapret</span>'
        )
        self.powered_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.powered_lbl)

        # Мигание
        self.blink_on = False
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.update_blink)
        self.blink_timer.start(800)

    def reload_presets(self):
        self.presets = {'General': 'general.bat', 'Discord': 'discord.bat'}
        for fn in sorted(os.listdir(self.core_dir)):
            if fn.lower().endswith('.bat') and fn not in ('general.bat', 'discord.bat', 'service.bat'):
                self.presets[os.path.splitext(fn)[0]] = fn
        self.cb.clear()
        self.cb.addItems(self.presets.keys())

    def retranslate_ui(self):
        self.setWindowTitle('Zapret GUI')
        if self.toggle_btn.isChecked():
            self.status_lbl.setText(self.t('On: {}', self.cb.currentText()))
        else:
            self.status_lbl.setText(self.t('Off'))
        self.settings_btn.setText(self.t('Settings'))
        self.instruction_btn.setText(self.t('Instruction'))

    def update_blink(self):
        color = "#ffffff" if self.blink_on else "#222222"
        bg_color = "red" if self.toggle_btn.isChecked() else "green"
        self.toggle_btn.setStyleSheet(f"""
            QPushButton {{
                border: 2px solid {color};
                border-radius: 50px;
                background-color: {bg_color};
                padding-left: 7px;
                padding-right: 0px;
            }}
        """)
        self.blink_on = not self.blink_on

    def is_winws_running(self):
        try:
            output = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq winws.exe" /NH',
                shell=True,
                text=True
            )
            return "winws.exe" in output.lower()
        except Exception:
            return False

    def on_toggle(self, checked):
        profile = self.cb.currentText()
        self.settings.setValue('last_profile', profile)
        script = os.path.join(self.core_dir, self.presets[profile])
        if not os.path.exists(script):
            QMessageBox.warning(self, "Ошибка", f"Не найден файл:\n{script}")
            self.toggle_btn.setChecked(False)
            return

        if checked:
            self.process = subprocess.Popen(
                script,
                shell=True,
                creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                close_fds=True
            )
            self.status_lbl.setText(self.t('On: {}', profile))
        else:
            os.system('taskkill /IM winws.exe /F')
            self.process = None
            self.status_lbl.setText(self.t('Off'))

        self.retranslate_ui()
        self.update_tray_status()

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        dlg.profile_cb.clear()
        dlg.profile_cb.addItem(" ")
        dlg.profile_cb.addItems([p for p in self.presets if p != " "])
        dlg.profile_cb.setCurrentText(self.settings.value('autostart_profile', ' '))
        dlg.exec()
        self.autostart = self.settings.value('autostart', False, type=bool)
        self.set_autostart(self.autostart)

    def set_autostart(self, enable: bool):
        try:
            import winreg
            key = r"Software\Microsoft\Windows\CurrentVersion\Run"
            name = "ZapretGUI"
            exe = os.path.realpath(sys.argv[0])
            reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_ALL_ACCESS)
            if enable:
                winreg.SetValueEx(reg, name, 0, winreg.REG_SZ, f'"{exe}"')
            else:
                try:
                    winreg.DeleteValue(reg, name)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(reg)
        except Exception as e:
            print("Autostart error:", e)

    def closeEvent(self, event):
        if self.is_winws_running():
            title = "Выход из программы" if self.lang == 'ru' else "Exit"
            text = (
                "Обход сейчас активен. Вы хотите завершить его и выйти?"
                if self.lang == 'ru'
                else "Bypass is currently running. Do you want to stop it and exit?"
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

            if msg.clickedButton() == btn_yes:
                os.system('taskkill /IM winws.exe /F')
                event.accept()
            else:
                event.ignore()
        else:
            event.accept()

def main():
    app = QApplication(sys.argv)
    extract_files_from_meipass()
    update_domain_files()
    settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
    win = MainWindow(settings)
    icon_path = os.path.join(APP_DIR, 'flags', 'z.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()