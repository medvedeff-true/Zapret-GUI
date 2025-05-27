#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import os
import subprocess
import re
import urllib.request
import zipfile
import tempfile

from PyQt6.QtCore import Qt, QSettings, QUrl, QSize
from PyQt6.QtGui import QDesktopServices, QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QCheckBox, QMessageBox
)
from PyQt6.QtCore import QSize, QTimer
from PyQt6.QtGui import QIcon

# ————————————————————————————————————————————————
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
        'Remove Service': 'Удалить сервис',
        'Check Updates': 'Проверить обновления',
        'About:': 'Подробнее:',
        'Off': 'Выключен',
        'On: {}': 'Включён: {}',
    },
    'en': {
        'Settings': 'Settings',
        'Autostart program': 'Autostart program',
        'Start minimized': 'Start minimized',
        'Service mode': 'Service mode',
        'Install Service': 'Install Service',
        'Remove Service': 'Remove Service',
        'Check Updates': 'Check Updates',
        'About:': 'About:',
        'Off': 'Off',
        'On: {}': 'On: {}',
    }
}
# ————————————————————————————————————————————————


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

        # — Языковые кнопки —
        hl = QHBoxLayout(); hl.addStretch()
        flag_dir = os.path.join(os.path.dirname(__file__), 'flags')
        for code in ('ru', 'en'):
            pix = QPixmap(os.path.join(flag_dir, f'{code}.png')).scaled(
                24, 24, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
            )
            btn = QPushButton()
            btn.setIcon(QIcon(pix)); btn.setIconSize(QSize(24, 24))
            btn.setFixedSize(36, 36)
            btn.clicked.connect(lambda _, c=code: self.change_lang(c))
            hl.addWidget(btn)
        hl.addStretch()
        layout.addLayout(hl)

        # — Чекбоксы автозапуска и сворачивания —
        cb_layout = QHBoxLayout()
        self.autostart_cb = QCheckBox()
        self.minimized_cb = QCheckBox()
        cb_layout.addWidget(self.autostart_cb)
        cb_layout.addWidget(self.minimized_cb)
        cb_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addLayout(cb_layout)

        # — Сервисный режим —
        self.svc_btn = QPushButton()
        self.svc_btn.setFixedHeight(30)
        self.svc_btn.clicked.connect(self.on_service_mode)
        layout.addWidget(self.svc_btn)

        # — Новые кнопки: Установить/Удалить/Обновить —
        btn_layout = QHBoxLayout()
        self.install_btn = QPushButton()
        self.install_btn.setStyleSheet(
            "QPushButton {"
            "  border: 1px solid green;"
            "  border-radius: 4px;"
            "  padding: 2px 6px;"
            "}"
        )
        self.remove_btn = QPushButton()
        self.update_btn = QPushButton()
        for btn in (self.install_btn, self.remove_btn, self.update_btn):
            btn.setFixedHeight(28)
            btn_layout.addWidget(btn)
        self.install_btn.clicked.connect(self.install_service)
        self.remove_btn.clicked.connect(self.remove_service)
        self.update_btn.clicked.connect(self.check_updates)
        layout.addLayout(btn_layout)

        # — «Подробнее: …» —
        self.about_label = QLabel()
        self.about_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.about_label.setTextFormat(Qt.TextFormat.RichText)
        self.about_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextBrowserInteraction)
        self.about_label.setOpenExternalLinks(True)
        layout.addStretch()
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
        self.install_btn.setText(self.t('Install Service'))
        self.remove_btn.setText(self.t('Remove Service'))
        self.update_btn.setText(self.t('Check Updates'))
        self.about_label.setText(
            f'{self.t("About:")} '
            '<a href="https://zapret.org/">Zapret</a> & '
            '<a href="https://github.com/medvedeff-true?tab=repositories">Medvedeff</a>'
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
        script = os.path.join(
            os.path.dirname(__file__),
            'core', 'fast', 'install_service.bat'
        )
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'),
                                'install_service.bat не найден')
            return
        subprocess.Popen(
            ['cmd.exe', '/c', script],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

    def remove_service(self):
        script = os.path.join(
            os.path.dirname(__file__),
            'core', 'fast', 'uninstall.bat'
        )
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'),
                                'remove_service.bat не найден')
            return
        subprocess.Popen(
            ['cmd.exe', '/c', script],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

    def check_updates(self):
        script = os.path.join(
            os.path.dirname(__file__),
            'core', 'fast', 'update_service.bat'
        )
        if not os.path.exists(script):
            QMessageBox.warning(self, self.t('Settings'),
                                'update_service.bat не найден')
            return
        subprocess.Popen(
            ['cmd.exe', '/c', script],
            creationflags=subprocess.CREATE_NEW_CONSOLE
        )

    def closeEvent(self, event):
        self.save_settings()
        super().closeEvent(event)


class MainWindow(QWidget):
    def __init__(self, settings):
        super().__init__()
        self.settings = settings

        # загружаем настройки
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

    def t(self, key, *args):
        return translations[self.lang].get(key, key).format(*args)

    def change_lang(self, lang_code):
        self.lang = lang_code
        self.settings.setValue('lang', lang_code)
        self.retranslate_ui()

    def init_ui(self):
        self.setFixedSize(300, 300)
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        # статус
        self.status_lbl = QLabel()
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_lbl)

        # кнопка запуска .bat
        self.toggle_btn = QPushButton(); self.toggle_btn.setFixedSize(60,60)
        self.toggle_btn.setCheckable(True)
        self.toggle_btn.clicked.connect(self.on_toggle)
        hl = QHBoxLayout(); hl.addStretch(); hl.addWidget(self.toggle_btn); hl.addStretch()
        layout.addLayout(hl)

        # выбор пресета
        self.cb = QComboBox()
        self.reload_presets()
        self.cb.setCurrentText(self.last_profile)
        self.cb.currentTextChanged.connect(lambda t: self.settings.setValue('last_profile', t))
        layout.addWidget(self.cb)

        # кнопка настроек
        self.settings_btn = QPushButton(); self.settings_btn.setFixedHeight(30)
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        # powered by
        self.powered_lbl = QLabel(
            '<span style="color:white;">Powered by </span>'
            '<span style="color:green;">Medvedeff</span>'
            '<span style="color:white;"> & </span>'
            '<span style="color:red;">Zapret</span>'
        )
        self.powered_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.powered_lbl)
        # --- Настройка кнопки запуска по умолчанию ---
        self.toggle_btn.setFixedSize(80, 80)
        self.toggle_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        self.toggle_btn.setIconSize(QSize(40, 40))
        self.blink_on = False

        def blink_init():
            color = "#ffffff" if self.blink_on else "#222222"
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    border: 2px solid {color};
                    border-radius: 40px;
                    background-color: green;
                }}
            """)
            self.blink_on = not self.blink_on

        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(blink_init)
        self.blink_timer.start(800)

    def reload_presets(self):
        self.presets = {'General':'general.bat','Discord':'discord.bat'}
        for fn in sorted(os.listdir(self.core_dir)):
            if fn.lower().endswith('.bat') and fn not in ('general.bat','discord.bat','service.bat'):
                self.presets[os.path.splitext(fn)[0]] = fn
        self.cb.clear()
        self.cb.addItems(self.presets.keys())

    def retranslate_ui(self):
        self.setWindowTitle('Zapret GUI')
        if self.toggle_btn.isChecked():
            self.status_lbl.setText(self.t('On: {}', self.cb.currentText()))
            self.toggle_btn.setStyleSheet("border-radius:30px; background-color:red;")
        else:
            self.status_lbl.setText(self.t('Off'))
            self.toggle_btn.setStyleSheet("border-radius:30px; background-color:green;")
        self.settings_btn.setText(self.t('Settings'))

    def on_toggle(self, checked):
        profile = self.cb.currentText()
        self.settings.setValue('last_profile', profile)
        script = os.path.join(self.core_dir, self.presets[profile])

        if not os.path.exists(script):
            QMessageBox.warning(self, "Ошибка", f"Не найден файл:\n{script}")
            self.toggle_btn.setChecked(False)
            return

        # Функция мигания
        def blink():
            color = "#ffffff" if self.blink_on else "#222222"
            bg_color = "red" if self.toggle_btn.isChecked() else "green"
            self.toggle_btn.setStyleSheet(f"""
                QPushButton {{
                    border: 2px solid {color};
                    border-radius: 40px;
                    background-color: {bg_color};
                }}
            """)
            self.blink_on = not self.blink_on

        if checked:
            # Запуск батника
            self.process = subprocess.Popen(
                ["cmd.exe", "/c", script],
                creationflags=subprocess.CREATE_NEW_CONSOLE
            )
            self.status_lbl.setText(self.t('On: {}', profile))
        else:
            # Завершение процесса (по названию окна)
            os.system(f'taskkill /FI "WINDOWTITLE eq zapret: {profile}" /T /F')
            self.status_lbl.setText(self.t('Off'))

        # Всегда устанавливаем нужные параметры кнопки
        self.toggle_btn.setFixedSize(80, 80)
        self.toggle_btn.setIcon(QIcon.fromTheme("media-playback-start"))
        self.toggle_btn.setIconSize(QSize(40, 40))
        self.blink_on = False

        # Перезапускаем мигание
        if hasattr(self, 'blink_timer') and self.blink_timer.isActive():
            self.blink_timer.stop()

        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(blink)
        self.blink_timer.start(800)

    def open_settings(self):
        dlg = SettingsDialog(self, self.settings)
        dlg.exec()
        # после — только автозапуск
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
                try: winreg.DeleteValue(reg, name)
                except FileNotFoundError: pass
            winreg.CloseKey(reg)
        except Exception as e:
            print("Autostart error:", e)


def main():
    app = QApplication(sys.argv)
    settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
    win = MainWindow(settings)
    sys.exit(app.exec())

if __name__ == '__main__':
    main()
