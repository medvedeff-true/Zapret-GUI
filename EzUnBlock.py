#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
from PyQt6.QtCore import Qt, QSettings, QSize, QTimer
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QCheckBox, QMessageBox, QSizePolicy
)
from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser

APP_DIR = os.path.join(os.path.expanduser('~'), 'Zapret Gui')
os.makedirs(APP_DIR, exist_ok=True)
SETTINGS_FILE = os.path.join(APP_DIR, 'settings.ini')

translations = {
    'ru': {
        'Settings': 'Настройки',
        'Autostart program': 'Автозапуск программы',
        'Start minimized': 'Запускать свернутым',
        'Service mode': 'Сервисный режим',
        'Install Service': 'Установить сервис',
        'Remove Services': 'Удалить сервисы',
        'Check Updates': 'Проверить обновления',
        'About:': 'Подробнее:',
        'Off': 'Выключен',
        'On: {}': 'Включён: {}',
        'Instruction': 'Инструкция',
        'Instruction Text': """
        <b>1.</b> Выберите из выпадающего списка профиль настроек, затем нажмите на <span style="color:green;"><b>большую зелёную кнопку</b></span>, после чего обход блокировок будет запущен. <i>(По умолчанию используется профиль General).</i><br><br>
        <b>2.</b> Если выбранный профиль не сработал — выключите обход, нажав на <span style="color:red;"><b>красную кнопку</b></span>, выберите другой профиль и снова включите. Повторяйте, пока не найдёте рабочий.<br><br>
        <b>3.</b> В разделе <b>«Настройки»</b> можно установить службу General или Discord. Это означает, что вместо обычного окна запустится служба Windows, работающая в фоне. 
        Но работа служб <i>зависит от провайдера</i>. Если сайты не открываются — удалите службу кнопкой «Удалить сервисы».<br><br>
        <span style="color:#cc0000;"><b>4. ПРИМЕЧАНИЕ:</b> Для обхода блокировки Discord <u>используйте только</u> профиль или службу Discord. Остальные профили не помогут.</span>
        """,
    },
    'en': {
        'Settings': 'Settings',
        'Autostart program': 'Autostart program',
        'Start minimized': 'Start minimized',
        'Service mode': 'Service mode',
        'Install Service': 'Install Service',
        'Remove Service': 'Remove Services',
        'Check Updates': 'Check Updates',
        'About:': 'About:',
        'Off': 'Off',
        'On: {}': 'On: {}',
        'Instruction': 'Instruction',
        'Instruction Text': """
        <b>1.</b> Select a profile from the dropdown list, then click the <span style="color:green;"><b>large green button</b></span> to start bypassing blocks. <i>(Default profile is General).</i><br><br>
        <b>2.</b> If the selected profile doesn't work, turn it off with the <span style="color:red;"><b>red button</b></span>, select another one and try again. Repeat until one works.<br><br>
        <b>3.</b> In the <b>“Settings”</b> tab you can install either the General or Discord service. This launches a Windows service in the background instead of the console. 
        But service functionality <i>depends on your provider</i>. If it doesn’t help — uninstall the service using the appropriate button.<br><br>
        <span style="color:#cc0000;"><b>4. NOTE:</b> To unblock Discord, <u>only use</u> the Discord profile or service. Other profiles won't work.</span>
        """

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

        # Языковые кнопки
        hl = QHBoxLayout();
        hl.addStretch()
        flag_dir = os.path.join(os.path.dirname(__file__), 'flags')
        for code in ('ru', 'en'):
            pix = QPixmap(os.path.join(flag_dir, f'{code}.png')).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            btn = QPushButton()
            btn.setIcon(QIcon(pix));
            btn.setIconSize(QSize(24, 24))
            btn.setFixedSize(31, 31)
            btn.clicked.connect(lambda _, c=code: self.change_lang(c))
            hl.addWidget(btn)
        hl.addStretch()
        layout.addLayout(hl)

        # Чекбоксы
        cb_layout = QHBoxLayout()
        self.autostart_cb = QCheckBox()
        self.minimized_cb = QCheckBox()
        cb_layout.addWidget(self.autostart_cb)
        cb_layout.addWidget(self.minimized_cb)
        cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(cb_layout)

        # Кнопка сервисного режима
        self.svc_btn = QPushButton()
        self.svc_btn.setFixedHeight(30)
        self.svc_btn.clicked.connect(self.on_service_mode)
        layout.addWidget(self.svc_btn)

        # Кнопки установки/удаления
        btn_layout = QHBoxLayout()

        # Кнопка General
        self.install_general_btn = QPushButton("Установить сервис\nGeneral")
        self.install_general_btn.setFixedHeight(50)
        self.install_general_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid green;
                border-radius: 4px;
            }
        """)
        self.install_general_btn.clicked.connect(self.install_service)
        btn_layout.addWidget(self.install_general_btn)

        # Кнопка удалить
        self.remove_btn = QPushButton("Удалить сервисы")
        self.remove_btn.setFixedHeight(50)
        self.remove_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid red;
                border-radius: 4px;
            }
        """)
        self.remove_btn.clicked.connect(self.remove_service)
        btn_layout.addWidget(self.remove_btn)

        # Кнопка Discord
        self.install_discord_btn = QPushButton("Установить сервис\nDiscord")
        self.install_discord_btn.setFixedHeight(50)
        self.install_discord_btn.setStyleSheet("""
            QPushButton {
                border: 1px solid green;
                border-radius: 4px;
            }
        """)
        self.install_discord_btn.clicked.connect(self.install_discord_service)
        btn_layout.addWidget(self.install_discord_btn)

        layout.addLayout(btn_layout)

        # Кнопка обновления
        self.update_btn = QPushButton()
        self.update_btn.setFixedHeight(30)
        self.update_btn.clicked.connect(self.check_updates)
        layout.addWidget(self.update_btn)

        # Подпись
        self.about_label = QLabel()
        self.about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.about_label.setTextFormat(Qt.TextFormat.RichText)
        self.about_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.about_label.setOpenExternalLinks(True)
        layout.addWidget(self.about_label)

    def load_settings(self):
        self.autostart_cb.setChecked(self.settings.value('autostart', False, type=bool))
        self.minimized_cb.setChecked(self.settings.value('minimized', False, type=bool))

    def save_settings(self):
        self.settings.setValue('autostart', self.autostart_cb.isChecked())
        self.settings.setValue('minimized', self.minimized_cb.isChecked())

    def retranslate_ui(self):
        self.setWindowTitle(self.t('Settings'))
        self.autostart_cb.setText(self.t('Autostart program'))
        self.minimized_cb.setText(self.t('Start minimized'))
        self.svc_btn.setText(self.t('Service mode'))
        self.install_general_btn.setText(self.t('Install Service') + "\nGeneral")
        self.install_discord_btn.setText(self.t('Install Service') + "\nDiscord")
        self.remove_btn.setText(self.t('Remove Services'))
        self.update_btn.setText(self.t('Check Updates'))
        self.about_label.setText(
            f'{self.t("About:")} '
            '<a href="https://zapret.org/" style="color:#3399ff;">Zapret</a> & '
            '<a href="https://github.com/medvedeff-true?tab=repositories" style="color:#3399ff;">Medvedeff</a>'
        )

    def change_lang(self, lang_code):
        if lang_code == self.lang:
            return
        self.lang = lang_code
        self.settings.setValue('lang', lang_code)
        self.retranslate_ui()
        parent = self.parent()
        if parent and hasattr(parent, 'change_lang'):
            parent.change_lang(lang_code)

    def on_service_mode(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'service.bat')
        if os.path.exists(script):
            subprocess.Popen([script], shell=True)
        else:
            QMessageBox.warning(self, self.t('Settings'), 'service.bat не найден')

    def install_service(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'install_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'install_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def install_discord_service(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'install_discord_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'install_discord_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def remove_service(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'uninstall.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'remove_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE)

    def check_updates(self):
        script = os.path.join(os.path.dirname(__file__), 'core', 'fast', 'update_service.bat')
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'), 'update_service.bat не найден')
            return
        subprocess.Popen(['cmd.exe', '/c', script], creationflags=subprocess.CREATE_NEW_CONSOLE)

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

        self.core_dir = os.path.join(os.path.dirname(__file__), 'core')
        self.presets = {}
        self.process = None

        self.init_ui()
        self.retranslate_ui()
        self.set_autostart(self.autostart)
        if self.minimized:
            self.showMinimized()
        else:
            self.show()

    from PyQt6.QtWidgets import QDialog, QVBoxLayout, QTextBrowser

    def open_instruction(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('Instruction'))
        dialog.setFixedSize(400, 410)
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

        # Кастомная иконка
        icon_path = os.path.join(os.path.dirname(__file__), 'flags', 'toggle.ico')
        if os.path.exists(icon_path):
            icon = QIcon(icon_path)
        else:
            icon = QIcon.fromTheme("media-playback-start")
        self.toggle_btn.setIcon(icon)
        self.toggle_btn.setIconSize(QSize(48, 48))

        # Стиль кнопки (центр + круглая + без смещений)
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

        self.cb = QComboBox()
        self.reload_presets()
        self.cb.setCurrentText(self.last_profile)
        self.cb.currentTextChanged.connect(lambda t: self.settings.setValue('last_profile', t))
        layout.addWidget(self.cb)

        self.settings_btn = QPushButton()
        self.settings_btn.setFixedHeight(30)
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        # Кнопка "Инструкция"
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

    def on_toggle(self, checked):
        profile = self.cb.currentText()
        self.settings.setValue('last_profile', profile)
        script = os.path.join(self.core_dir, self.presets[profile])
        if not os.path.exists(script):
            QMessageBox.warning(self, "Ошибка", f"Не найден файл:\n{script}")
            self.toggle_btn.setChecked(False)
            return

        if checked:
            self.process = subprocess.Popen(["cmd.exe", "/c", script], creationflags=subprocess.CREATE_NEW_CONSOLE)
            self.status_lbl.setText(self.t('On: {}', profile))
        else:
            os.system(f'taskkill /FI "WINDOWTITLE eq zapret: {profile}" /T /F')
            self.status_lbl.setText(self.t('Off'))

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
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


def main():
    app = QApplication(sys.argv)
    settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
    win = MainWindow(settings)
    icon_path = os.path.join(os.path.dirname(__file__), 'flags', 'z.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
