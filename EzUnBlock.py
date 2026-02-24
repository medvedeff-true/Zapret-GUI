import sys
import os
import subprocess
from PyQt6.QtCore import (
    Qt, QSettings, QSize, QTimer, QThread, pyqtSignal,
    QElapsedTimer, QEvent, QEasingCurve, QPropertyAnimation, pyqtProperty,
    QParallelAnimationGroup
)
from PyQt6.QtGui import QIcon, QPixmap, QAction, QPalette, QPainter, QColor, QPen
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QCheckBox, QMessageBox, QSizePolicy,
    QSystemTrayIcon, QMenu, QTextBrowser, QProgressDialog, QProgressBar
)
import shutil
import requests
import zipfile
import io
import re
import socket
import time
import ctypes

def _run_hidden(args, cwd=None, timeout=None):
    try:
        si = subprocess.STARTUPINFO()
        si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        si.wShowWindow = 0  # SW_HIDE

        return subprocess.run(
            args,
            cwd=cwd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            startupinfo=si,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except Exception:
        return None

def extract_files_from_meipass():
    if not hasattr(sys, "_MEIPASS"):
        base_src = os.path.dirname(__file__)
    else:
        base_src = sys._MEIPASS

    for folder in ("flags", "core"):
        _safe_copy_tree(
            os.path.join(base_src, folder),
            os.path.join(APP_DIR, folder),
            overwrite=False
        )

    try:
        src_uninstall = os.path.join(base_src, "core", "fast", "uninstall.bat")
        if os.path.exists(src_uninstall) and (not os.path.exists(REMOVE_BAT)):
            _safe_copy_file(src_uninstall, REMOVE_BAT, overwrite=False)
    except Exception:
        pass

def unblock_core_tree(core_dir: str) -> None:
    if not os.path.isdir(core_dir):
        return
    try:
        _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-Command",
                (
                    f"Get-ChildItem -LiteralPath '{core_dir}' -Recurse -File "
                    "| Unblock-File -ErrorAction SilentlyContinue"
                )
            ]
        )
    except Exception:
        pass

def _safe_copy_file(src: str, dst: str, overwrite: bool = False) -> bool:
    os.makedirs(os.path.dirname(dst), exist_ok=True)

    if (not overwrite) and os.path.exists(dst):
        return False

    try:
        shutil.copy2(src, dst)
        return True
    except PermissionError:
        return False
    except OSError:
        return False


def _safe_copy_tree(src_root: str, dst_root: str, overwrite: bool = False) -> None:
    if not os.path.isdir(src_root):
        return

    for root, _, files in os.walk(src_root):
        rel = os.path.relpath(root, src_root)
        target_dir = dst_root if rel == "." else os.path.join(dst_root, rel)
        os.makedirs(target_dir, exist_ok=True)

        for f in files:
            s = os.path.join(root, f)
            d = os.path.join(target_dir, f)
            _safe_copy_file(s, d, overwrite=overwrite)


APP_VERSION = "1.7.1"
APP_DIR = os.path.join(os.path.expanduser('~'), 'ZapretGUI')
os.makedirs(APP_DIR, exist_ok=True)
FLOWSEAL_REPO = "Flowseal/zapret-discord-youtube"
FLOWSEAL_DEFAULT_VER = "1.9.7"
FLOWSEAL_VER_KEY = "flowseal_release"

SETTINGS_FILE = os.path.join(APP_DIR, 'settings.ini')
VERSION_FILE = os.path.join(APP_DIR, '.app_version')
AUTOLOG_FILE = os.path.join(APP_DIR, "autotest_last.log")

REMOVE_BAT = os.path.join(APP_DIR, "uninstall.bat")

NOUPDATE_INP = os.path.join(APP_DIR, "_no_update_input.txt")

def _ensure_no_update_input(lines: int = 12) -> str:
    try:
        if not os.path.exists(NOUPDATE_INP):
            with open(NOUPDATE_INP, "w", encoding="ascii", newline="\n") as f:
                for _ in range(lines):
                    f.write("n\n")
    except Exception:
        pass
    return NOUPDATE_INP

def _patch_bat_inplace_remove_updates(bat_path: str) -> bool:
    try:
        if not os.path.exists(bat_path):
            return False

        with open(bat_path, "rb") as f:
            raw = f.read()

        enc = "utf-8"
        bom = b""
        if raw.startswith(b"\xff\xfe"):
            enc = "utf-16le"; bom = b"\xff\xfe"
        elif raw.startswith(b"\xfe\xff"):
            enc = "utf-16be"; bom = b"\xfe\xff"
        elif raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8"; bom = b"\xef\xbb\xbf"
        else:
            try:
                raw.decode("utf-8")
                enc = "utf-8"
            except Exception:
                enc = "cp1251"

        text = raw[len(bom):].decode(enc, errors="replace")
        lines = text.splitlines()

        new_lines = []
        changed = False

        for ln in lines:
            s = ln.strip().lower()
            if "service.bat" in s and "check_updates" in s:
                if s.startswith("call ") or s.startswith("service.bat") or '"service.bat"' in s or "%~dp0" in s:
                    changed = True
                    continue
            new_lines.append(ln)

        stripped = []
        i = 0
        while i < len(new_lines):
            s = new_lines[i].strip().lower()
            if s.startswith("net session") and "||" in s and "(" in s:
                j = i + 1
                found_runas = False
                while j < len(new_lines) and j < i + 12:
                    sj = new_lines[j].strip().lower()
                    if "-verb runas" in sj or "start-process" in sj:
                        found_runas = True
                    if sj == ")":
                        break
                    j += 1
                if found_runas and j < len(new_lines) and new_lines[j].strip() == ")":
                    changed = True
                    i = j + 1
                    continue
            stripped.append(new_lines[i])
            i += 1

        if not stripped:
            return False

        out_text = "\r\n".join(stripped) + "\r\n"
        out_raw = bom + out_text.encode(enc, errors="replace")

        if out_raw == raw:
            return False

        with open(bat_path, "wb") as f:
            f.write(out_raw)

        return changed
    except Exception:
        return False

def _patch_bat_inplace_hide_windows(bat_path: str) -> bool:
    try:
        if not os.path.exists(bat_path):
            return False

        with open(bat_path, "rb") as f:
            raw = f.read()

        enc = "utf-8"
        bom = b""
        if raw.startswith(b"\xff\xfe"):
            enc = "utf-16le"; bom = b"\xff\xfe"
        elif raw.startswith(b"\xfe\xff"):
            enc = "utf-16be"; bom = b"\xfe\xff"
        elif raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8"; bom = b"\xef\xbb\xbf"
        else:
            try:
                raw.decode("utf-8")
                enc = "utf-8"
            except Exception:
                enc = "cp1251"

        text = raw[len(bom):].decode(enc, errors="replace")
        lines = text.splitlines()

        changed = False
        out_lines = []

        for ln in lines:
            if re.match(r"(?i)^\s*start\b", ln):
                low = ln.lower()
                if re.search(r"(?i)(\s)/b(\s|$)", ln) is None:
                    new_ln = re.sub(r"(?i)(\s)/min(\s|$)", r"\1/b\2", ln, count=1)
                    if new_ln != ln:
                        ln = new_ln
                        changed = True

            out_lines.append(ln)

        if not changed:
            return False

        out_text = "\r\n".join(out_lines) + "\r\n"
        out_raw = bom + out_text.encode(enc, errors="replace")

        if out_raw == raw:
            return False

        with open(bat_path, "wb") as f:
            f.write(out_raw)

        return True
    except Exception:
        return False

def _patch_profiles_hide_windows(core_dir: str) -> None:
    try:
        if not os.path.isdir(core_dir):
            return
        for fn in os.listdir(core_dir):
            low = fn.lower()
            if not low.endswith(".bat"):
                continue
            if low.startswith("__noupdate__"):
                continue
            if low in ("service.bat", "cloudflare_switch.bat"):
                continue
            _patch_bat_inplace_hide_windows(os.path.join(core_dir, fn))
    except Exception:
        pass


def _read_text(path: str) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return ""
    except Exception:
        return ""

    for enc in ("utf-8", "cp1251", "utf-16"):
        try:
            return data.decode(enc).strip()
        except Exception:
            pass
    return data.decode("utf-8", errors="replace").strip()

def _theme_text_color_hex(w: QWidget) -> str:
    c = w.palette().color(QPalette.ColorRole.Text)
    return c.name()

def _force_stop_blockers():
    try:
        _run_hidden(["taskkill", "/IM", "winws.exe", "/F"])
    except Exception:
        pass

    for svc in ("zapret", "zapret_discord", "WinDivert", "WinDivert14"):
        try:
            _run_hidden(["sc", "stop", svc])
        except Exception:
            pass

    try:
        time.sleep(0.6)
    except Exception:
        pass

def wipe_app_dir_if_new_version():
    if not hasattr(sys, "_MEIPASS"):
        return

    prev = _read_text(VERSION_FILE) if os.path.exists(VERSION_FILE) else ""
    if prev == APP_VERSION:
        return

    _force_stop_blockers()

    try:
        if os.path.isdir(APP_DIR):
            for name in os.listdir(APP_DIR):
                p = os.path.join(APP_DIR, name)

                try:
                    if os.path.isdir(p):
                        shutil.rmtree(p, ignore_errors=False)
                    else:
                        os.remove(p)
                except PermissionError:
                    _force_stop_blockers()
                    try:
                        if os.path.isdir(p):
                            shutil.rmtree(p, ignore_errors=False)
                        else:
                            os.remove(p)
                    except PermissionError:
                        pass
                except FileNotFoundError:
                    pass

        os.makedirs(APP_DIR, exist_ok=True)
        with open(VERSION_FILE, "w", encoding="utf-8") as f:
            f.write(APP_VERSION)

    except Exception as e:
        try:
            QMessageBox.warning(
                None,
                "Предупреждение",
                "Не удалось полностью очистить папку ZapretGUI, но приложение продолжит запуск.\n"
                "Если будут проблемы — закройте обход/winws.exe и запустите приложение от администратора.\n\n"
                f"Детали: {e}"
            )
        except Exception:
            pass

def update_domain_files():
    try:
        import psutil

        def is_winws_running() -> bool:
            try:
                out = subprocess.check_output(
                    'tasklist /FI "IMAGENAME eq winws.exe" /NH',
                    shell=True,
                    text=True
                )
                return "winws.exe" in out.lower()
            except Exception:
                return False

        if is_winws_running():
            QMessageBox.warning(
                None,
                "Обновление",
                "Сейчас запущен обход (winws.exe).\n\n"
                "Перед обновлением нажмите красную кнопку (выключить обход), "
                "закройте/остановите winws.exe и повторите."
            )
            return

        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)

        current_ver = str(settings.value(FLOWSEAL_VER_KEY, "")).strip()
        if not current_ver:
            current_ver = FLOWSEAL_DEFAULT_VER
            settings.setValue(FLOWSEAL_VER_KEY, current_ver)
            settings.sync()

        api_url = f"https://api.github.com/repos/{FLOWSEAL_REPO}/releases/latest"
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}

        r = requests.get(api_url, headers=headers, timeout=20)
        r.raise_for_status()
        data = r.json()

        tag = (data.get("tag_name") or "").strip()
        latest_ver = tag[1:] if tag.startswith("v") else tag
        if not latest_ver:
            QMessageBox.warning(None, "Обновление", "Не удалось определить версию последнего релиза.")
            return

        # Сравнение версий
        def semver_tuple(v: str):
            parts = v.strip().split(".")
            nums = []
            for p in parts:
                q = "".join(ch for ch in p if ch.isdigit())
                nums.append(int(q) if q else 0)
            while len(nums) < 3:
                nums.append(0)
            return tuple(nums[:3])

        try:
            is_newer = semver_tuple(latest_ver) > semver_tuple(current_ver)
        except Exception:
            is_newer = (latest_ver != current_ver)

        if not is_newer:
            QMessageBox.information(None, "Обновление", f"У вас уже актуальная версия: {current_ver}")
            return

        msg = QMessageBox()
        msg.setWindowTitle("Обновление")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(
            f"Доступен новый релиз: {latest_ver}\n"
            f"Текущая версия: {current_ver}\n\n"
            "Будет полностью очищена папка core и распакованы новые файлы.\n"
            "Продолжить?"
        )
        btn_yes = msg.addButton("Да", QMessageBox.ButtonRole.YesRole)
        btn_no = msg.addButton("Нет", QMessageBox.ButtonRole.NoRole)
        msg.exec()
        if msg.clickedButton() != btn_yes:
            return

        download_url = None
        assets = data.get("assets") or []
        for a in assets:
            name = (a.get("name") or "").lower()
            if name.endswith(".zip"):
                download_url = a.get("browser_download_url")
                break
        if not download_url:
            download_url = data.get("zipball_url")

        if not download_url:
            QMessageBox.warning(None, "Обновление", "Не найден файл для скачивания в релизе.")
            return

        #Скачиваем архив
        zr = requests.get(download_url, headers=headers, timeout=60)
        zr.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(zr.content))

        core_target = os.path.join(APP_DIR, "core")
        os.makedirs(core_target, exist_ok=True)

        for name in os.listdir(core_target):
            p = os.path.join(core_target, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=False)
            else:
                os.remove(p)

        #Определяем корневой префикс
        names = [n for n in z.namelist() if n and not n.startswith("__MACOSX/")]

        top_levels = set()
        for n in names:
            seg = n.split("/", 1)[0]
            if seg:
                top_levels.add(seg)

        root_prefix = ""
        if len(top_levels) == 1:
            root_prefix = next(iter(top_levels)) + "/"

        #Распаковка в core
        replaced = 0
        for member in names:
            if member.endswith("/"):
                continue
            if root_prefix and not member.startswith(root_prefix):
                continue

            rel = member[len(root_prefix):] if root_prefix else member
            if not rel:
                continue

            dst_path = os.path.join(core_target, rel)
            os.makedirs(os.path.dirname(dst_path), exist_ok=True)

            base = os.path.basename(dst_path).lower()
            if base in {"windivert64.sys", "windivert32.sys"}:
                continue

            with z.open(member) as src, open(dst_path, "wb") as dst:
                dst.write(src.read())
                replaced += 1

        #Запоминаем версию
        settings.setValue(FLOWSEAL_VER_KEY, latest_ver)
        settings.sync()

        QMessageBox.information(
            None,
            "Обновление завершено",
            f"Обновлено до: {latest_ver}\n"
            f"Файлов распаковано: {replaced}\n\n"
            f"Путь: {core_target}"
        )

    except requests.exceptions.ConnectionError:
        QMessageBox.warning(None, "Ошибка обновления", "Отсутствует подключение к интернету.")
    except requests.HTTPError as e:
        QMessageBox.critical(None, "Ошибка обновления", f"HTTP ошибка:\n{e}")
    except PermissionError as e:
        QMessageBox.critical(
            None,
            "Ошибка обновления",
            "Не удалось очистить/записать файлы в папку core.\n"
            "НАЖМИТЕ НА КНОПКУ Сбросить соединения winws.\n\n"
            f"Детали: {e}"
        )
    except zipfile.BadZipFile:
        QMessageBox.critical(None, "Ошибка обновления", "Скачанный архив повреждён или не является zip.")
    except Exception as e:
        QMessageBox.critical(None, "Ошибка обновления", f"Произошла ошибка:\n{e}")

def _semver_tuple(v: str):
    parts = v.strip().split(".")
    nums = []
    for p in parts:
        q = "".join(ch for ch in p if ch.isdigit())
        nums.append(int(q) if q else 0)
    while len(nums) < 3:
        nums.append(0)
    return tuple(nums[:3])

def _get_latest_flowseal_release_silent() -> str:
    try:
        api_url = f"https://api.github.com/repos/{FLOWSEAL_REPO}/releases/latest"
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        r = requests.get(api_url, headers=headers, timeout=12)
        r.raise_for_status()
        data = r.json()
        tag = (data.get("tag_name") or "").strip()
        latest_ver = tag[1:] if tag.startswith("v") else tag
        return (latest_ver or "").strip()
    except Exception:
        return ""

def _cleanup_noupdate_files(core_dir: str) -> None:
    try:
        if not os.path.isdir(core_dir):
            return
        for fn in os.listdir(core_dir):
            if fn.lower().startswith("__noupdate__") and fn.lower().endswith(".bat"):
                try:
                    os.remove(os.path.join(core_dir, fn))
                except Exception:
                    pass
    except Exception:
        pass

def _patch_profiles_if_core_outdated(core_dir: str, settings: QSettings) -> None:
    try:
        if not os.path.isdir(core_dir):
            return

        latest = _get_latest_flowseal_release_silent()
        if not latest:
            return

        has_ver = settings.contains(FLOWSEAL_VER_KEY)
        current = str(settings.value(FLOWSEAL_VER_KEY)) if has_ver else FLOWSEAL_DEFAULT_VER

        try:
            outdated = _semver_tuple(latest) > _semver_tuple(current)
        except Exception:
            outdated = (latest != current)

        if not outdated:
            _cleanup_noupdate_files(core_dir)
            return

        _cleanup_noupdate_files(core_dir)

        for fn in os.listdir(core_dir):
            if not fn.lower().endswith(".bat"):
                continue
            low = fn.lower()
            if low in ("service.bat", "cloudflare_switch.bat"):
                continue
            _patch_bat_inplace_remove_updates(os.path.join(core_dir, fn))

    except Exception:
        pass

def create_delete_bat():
    delete_bat_path = os.path.join(APP_DIR, "Delete.bat")
    if os.path.exists(delete_bat_path):
        return

    content = r'''@echo off
setlocal EnableDelayedExpansion
chcp 65001 > nul

net session >nul 2>&1 || (
  powershell -Command "Start-Process '%~f0' -Verb RunAs"
  exit /b
)

tasklist /FI "IMAGENAME eq winws.exe" | find /I "winws.exe" > nul
if !errorlevel!==0 exit /b

sc stop zapret >nul 2>&1
sc delete zapret >nul 2>&1
sc stop zapret_discord >nul 2>&1
sc delete zapret_discord >nul 2>&1
net stop "WinDivert" >nul 2>&1 & sc delete "WinDivert" >nul 2>&1
net stop "WinDivert14" >nul 2>&1 & sc delete "WinDivert14" >nul 2>&1

ping 127.0.0.1 -n 3 >nul
set SCRIPT_PATH="%~f0"
set FOLDER_PATH=%~dp0
cd /d "%TEMP%"
echo @echo off > zapret_clean.bat
echo rmdir /s /q "%FOLDER_PATH%" >> zapret_clean.bat
echo del /f /q "%SCRIPT_PATH%" >> zapret_clean.bat
echo del /f /q zapret_clean.bat >> zapret_clean.bat
echo exit >> zapret_clean.bat
start /b cmd /c zapret_clean.bat
exit /b
'''
    with open(delete_bat_path, 'w', encoding='utf-8') as f:
        f.write(content)


translations = {
    'ru': {
        'Settings': 'Настройки',
        'Autostart program': 'Автозапуск программы',
        'Start minimized': 'Запускать свернутым',
        'Autostart profile': 'Профиль для автозагрузки',
        'Service mode': 'Сервисный режим',
        'Install Service': 'Установить сервис',
        'Remove Services': 'Сбросить соединения winws',
        'Check Updates': 'Проверить обновления',
        'About:': 'Подробнее:',
        'Off': 'Выключен',
        'On: {}': 'Включён: {}',
        'Instruction': 'Инструкция',
        'Instruction Text': """
        <b>1.</b> Выберите из выпадающего списка <b>профиль настроек</b>, затем нажмите на <span style="color:red;"><b>большую красную кнопку</b></span>, чтобы запустить обход блокировок. <i>(По умолчанию используется профиль <b>General</b>).</i><br><br>
        <b>2.</b> Если выбранный профиль не сработал — <span style="color:green;"><b>нажмите на зелёную кнопку</b></span> для отключения и выберите другой профиль.<br><br>
        <b>3.</b> В настройках можно включить <b>Автозапуск</b> вместе с Windows и выбрать профиль для автозапуска.<br><br>
        <b>4.</b> Чтобы проверить, работает ли обход — попробуйте открыть сайты, которые у вас не открывались, или сделайте проверку на сайте: <a href="https://www.youtube.com">@YouTube</a> или <a href="https://discord.com/">@Discord</a><br><br>
        <b>5.</b> Для автоматического подбора профиля можно воспользоваться кнопкой - <span style="color:green;"><b>зелёный кружок с буквой "А" внутри.</b></span> Процесс подбора обычно занимает несколько минут.
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
        'Check Updates': 'Check Updates',
        'About:': 'About:',
        'Off': 'Off',
        'On: {}': 'On: {}',
        'Instruction': 'Instruction',
        'Instruction Text': """
        <b>1.</b> Select a <b>profile</b> from the dropdown list, then click the <span style="color:red;"><b>big red button</b></span> to start the bypass. <i>(By default, profile <b>General</b> is used).</i><br><br>
        <b>2.</b> If the selected profile doesn’t work — <span style="color:green;"><b>click the green button</b></span> to stop and choose another profile.<br><br>
        <b>3.</b> In settings you can enable <b>Autostart</b> with Windows and choose a profile for autostart.<br><br>
        <b>4.</b> To check if bypass works — try opening websites that were blocked for you, or test on: <a href="https://www.youtube.com">@YouTube</a> or <a href="https://discord.com/">@Discord</a><br><br>
        <b>5.</b> To automatically select a profile, you can use the button - <span style="color:green;"><b>green circle with the letter “A” inside.</b></span> The selection process usually takes a few minutes.
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
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)

            btn.setIcon(QIcon(pix))
            btn.setIconSize(QSize(24, 24))

            btn.setFixedSize(32, 32)

            btn.setStyleSheet("""
            QPushButton {
                padding: 0px;
                margin: 0px;
                border: 1px solid rgba(0,0,0,40);
                border-radius: 6px;
                background: transparent;
            }
            QPushButton:hover {
                background: rgba(0,0,0,15);
            }
            """)

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
        self.profile_cb.addItem(" ")
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

    def check_updates(self):
        update_domain_files()

    def closeEvent(self, event):
        self.save_settings()
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
            self._kill_winws()
            self.finished_err.emit(str(e))

    def _test_profile_fast(self, profile_name: str, timeout_per_profile: float = 10.0) -> bool:
        self._kill_winws()
        for svc in ("zapret", "zapret_discord", "WinDivert", "WinDivert14"):
            try:
                subprocess.run(["sc", "stop", svc], capture_output=True, text=True)
            except Exception:
                pass
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

        inp_path = _ensure_no_update_input()

        env = os.environ.copy()
        env["ZAPRETGUI_AUTOTEST"] = "1"
        env["ZAPRETGUI_NOUPDATE"] = "1"

        proc = None
        try:
            with open(AUTOLOG_FILE, "a", encoding="utf-8") as log, open(inp_path, "r", encoding="ascii") as fin:
                proc = subprocess.Popen(
                    ["cmd.exe", "/d", "/k", bat],
                    cwd=self.core_dir,
                    stdin=fin,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    close_fds=True
                )

            start_deadline = time.time() + 12.0
            while time.time() < start_deadline:
                if self._stop:
                    return False
                if self._is_winws_running():
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
            if proc and proc.poll() is None:
                try:
                    subprocess.run(
                        ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                        capture_output=True,
                        text=True
                    )
                except Exception:
                    pass

    def _is_winws_running(self) -> bool:
        try:
            out = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq winws.exe" /NH',
                shell=True,
                text=True
            )
            return "winws.exe" in out.lower()
        except Exception:
            return False

    def _alog(self, line: str) -> None:
        try:
            with open(AUTOLOG_FILE, "a", encoding="utf-8") as f:
                f.write(line.rstrip("\n") + "\n")
        except Exception:
            pass

    def _diag_winws_start_failure(self, bat: str) -> None:
        self._alog("DIAG: winws.exe not detected after start, collecting diagnostics...")

        try:
            bin_dir = os.path.join(self.core_dir, "bin")
            self._alog(f"DIAG: bin_dir={bin_dir} exists={os.path.isdir(bin_dir)}")
            if os.path.isdir(bin_dir):
                try:
                    names = sorted(os.listdir(bin_dir))
                    self._alog("DIAG: bin_dir files: " + ", ".join(names[:80]) + (" ..." if len(names) > 80 else ""))
                except Exception as e:
                    self._alog(f"DIAG: listdir(bin_dir) failed: {repr(e)}")
        except Exception:
            pass

        try:
            out = subprocess.check_output(
                'tasklist /FI "IMAGENAME eq winws.exe" /NH',
                shell=True,
                text=True
            )
            self._alog("DIAG: tasklist winws.exe => " + out.strip().replace("\n", " | "))
        except Exception as e:
            self._alog(f"DIAG: tasklist failed: {repr(e)}")

        try:
            self._alog("DIAG: re-running BAT with capture to get error output...")

            inp_path = _ensure_no_update_input()
            env = os.environ.copy()
            env["ZAPRETGUI_AUTOTEST"] = "1"
            env["ZAPRETGUI_NOUPDATE"] = "1"

            with open(inp_path, "r", encoding="ascii") as fin:
                r = subprocess.run(
                    ["cmd.exe", "/d", "/c", bat],
                    cwd=self.core_dir,
                    stdin=fin,
                    capture_output=True,
                    text=True,
                    env=env,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    timeout=12
                )

            self._alog(f"DIAG: BAT returncode={r.returncode}")
            if r.stdout:
                self._alog("DIAG: BAT stdout (tail):")
                for line in r.stdout.splitlines()[-80:]:
                    self._alog("  " + line)
            if r.stderr:
                self._alog("DIAG: BAT stderr (tail):")
                for line in r.stderr.splitlines()[-80:]:
                    self._alog("  " + line)

        except subprocess.TimeoutExpired:
            self._alog("DIAG: BAT capture run timed out (12s)")
        except Exception as e:
            self._alog(f"DIAG: BAT capture run failed: {repr(e)}")

        self._alog("DIAG: end")

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
        try:
            subprocess.run(
                ["taskkill", "/IM", "winws.exe", "/F"],
                capture_output=True,
                text=True
            )
        except Exception:
            pass

class AutoProgressDialog(QDialog):
    canceled = pyqtSignal()

    def __init__(self, title: str, left_text: str, cancel_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(330, 120)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(8)

        row = QHBoxLayout()
        self.lbl_left = QLabel(left_text)
        self.lbl_right = QLabel("")
        self.lbl_right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        row.addWidget(self.lbl_left, 1)
        row.addWidget(self.lbl_right, 0)
        v.addLayout(row)

        self.bar = QProgressBar()
        self.bar.setRange(0, 100)
        self.bar.setValue(0)
        v.addWidget(self.bar)

        self.lbl_profile = QLabel("")
        self.lbl_profile.setStyleSheet("color: rgba(0,0,0,140);")
        v.addWidget(self.lbl_profile)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton(cancel_text)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_cancel)
        v.addLayout(btn_row)

    def set_progress(self, cur: int, total: int):
        self.bar.setRange(0, max(1, total))
        self.bar.setValue(cur)

    def set_current_profile(self, name: str):
        self.lbl_profile.setText(name)

    def _on_cancel(self):
        self.canceled.emit()
        self.close()

    def set_eta_text(self, s: str):
        self.lbl_right.setText(s)

class AnimatedPowerToggleButton(QPushButton):

    def __init__(self, icon_off: QIcon | None = None, icon_on: QIcon | None = None, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setContentsMargins(0, 0, 0, 0)

        self._max_pulse_px = 10
        self._border_w = 2
        self._base_pad = self._max_pulse_px + self._border_w + 2  # чтобы свечение не резалось

        self._progress = 1.0 if self.isChecked() else 0.0
        self._pulse = 0.0

        self._icon_off_pix = None
        self._icon_on_pix = None

        def _icon_to_pix(ic: QIcon | None) -> QPixmap | None:
            if ic is None or ic.isNull():
                return None
            pm = ic.pixmap(128, 128)  # побольше, чтобы меньше артефактов при вращении
            return pm if (pm is not None and not pm.isNull()) else None

        self._icon_off_pix = _icon_to_pix(icon_off)
        self._icon_on_pix = _icon_to_pix(icon_on)

        # текущая иконка
        self._cur_icon_pix = self._icon_on_pix if self.isChecked() else self._icon_off_pix

        self._anim_progress = QPropertyAnimation(self, b"progress", self)
        self._anim_progress.setDuration(220)
        self._anim_progress.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_pulse = QPropertyAnimation(self, b"pulse", self)
        self._anim_pulse.setDuration(1200)
        self._anim_pulse.setStartValue(0.0)
        self._anim_pulse.setEndValue(1.0)
        self._anim_pulse.setLoopCount(-1)
        self._anim_pulse.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._icon_angle = 0.0
        self._icon_scale = 1.0

        self._anim_icon_angle = QPropertyAnimation(self, b"iconAngle", self)
        self._anim_icon_angle.setDuration(420)
        self._anim_icon_angle.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._anim_icon_scale = QPropertyAnimation(self, b"iconScale", self)
        self._anim_icon_scale.setDuration(420)
        self._anim_icon_scale.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_icon_group = QParallelAnimationGroup(self)
        self._anim_icon_group.addAnimation(self._anim_icon_angle)
        self._anim_icon_group.addAnimation(self._anim_icon_scale)

        self._pending_icon = None
        self._swapped_during_scale = False
        self._anim_icon_scale.valueChanged.connect(self._maybe_swap_icon_on_scale)

        self._anim_icon_group.finished.connect(self._reset_icon_transform)

        self._blink_on = False
        self._blink_color = QColor("#2db45f")
        self._idle_border = QColor(45, 180, 95, 90)

        self.toggled.connect(self._on_toggled)

        if self._anim_pulse.state() != QPropertyAnimation.State.Running:
            self._anim_pulse.start()

        self._on_toggled(self.isChecked())

    def setBlinkOn(self, on: bool):
        self._blink_on = bool(on)
        self.update()

    def setBorderColorHex(self, hex_color: str):
        try:
            c = QColor(hex_color)
            if c.isValid():
                self._blink_color = c
        except Exception:
            pass
        self.update()

    def getProgress(self) -> float:
        return float(self._progress)

    def setProgress(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        if abs(self._progress - v) > 1e-4:
            self._progress = v
            self.update()

    progress = pyqtProperty(float, fget=getProgress, fset=setProgress)

    def getPulse(self) -> float:
        return float(self._pulse)

    def setPulse(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        if abs(self._pulse - v) > 1e-4:
            self._pulse = v
            self.update()

    pulse = pyqtProperty(float, fget=getPulse, fset=setPulse)

    def getIconAngle(self) -> float:
        return float(self._icon_angle)

    def setIconAngle(self, v: float):
        v = float(v)
        if abs(self._icon_angle - v) > 1e-3:
            self._icon_angle = v
            self.update()

    iconAngle = pyqtProperty(float, fget=getIconAngle, fset=setIconAngle)

    def getIconScale(self) -> float:
        return float(self._icon_scale)

    def setIconScale(self, v: float):
        v = max(0.60, min(1.20, float(v)))
        if abs(self._icon_scale - v) > 1e-3:
            self._icon_scale = v
            self.update()

    iconScale = pyqtProperty(float, fget=getIconScale, fset=setIconScale)

    @staticmethod
    def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, float(t)))
        r = int(c1.red()   + (c2.red()   - c1.red())   * t)
        g = int(c1.green() + (c2.green() - c1.green()) * t)
        b = int(c1.blue()  + (c2.blue()  - c1.blue())  * t)
        a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * t)
        return QColor(r, g, b, a)

    def _reset_icon_transform(self):
        self._icon_angle = 0.0
        self._icon_scale = 1.0
        self._pending_icon = None
        self._swapped_during_scale = False
        self.update()

    def _maybe_swap_icon_on_scale(self, v):
        if self._pending_icon is None or self._swapped_during_scale:
            return
        try:
            vv = float(v)
        except Exception:
            return
        if vv < 0.94:
            self._cur_icon_pix = self._pending_icon
            self._swapped_during_scale = True
            self.update()

    def _start_icon_anim(self, direction: int, pending_icon: QPixmap | None):
        self._anim_icon_group.stop()
        self._pending_icon = pending_icon
        self._swapped_during_scale = False

        self._anim_icon_angle.setStartValue(0.0)
        self._anim_icon_angle.setEndValue(360.0 * float(direction))

        self._anim_icon_scale.setKeyValueAt(0.00, 1.00)
        self._anim_icon_scale.setKeyValueAt(0.78, 1.00)
        self._anim_icon_scale.setKeyValueAt(0.90, 0.86)
        self._anim_icon_scale.setKeyValueAt(1.00, 1.00)

        self._anim_icon_group.start()

    def _on_toggled(self, checked: bool):
        self._anim_progress.stop()
        self._anim_progress.setStartValue(self._progress)
        self._anim_progress.setEndValue(1.0 if checked else 0.0)
        self._anim_progress.start()

        if checked:
            self._start_icon_anim(direction=+1, pending_icon=self._icon_on_pix)
        else:
            self._start_icon_anim(direction=-1, pending_icon=self._icon_off_pix)

        self.update()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        outer = self.rect().adjusted(self._base_pad, self._base_pad, -self._base_pad, -self._base_pad)

        off_col = QColor(220, 50, 50)
        on_col = QColor(45, 180, 95)

        t = self._progress
        base_col = self._lerp_color(off_col, on_col, t)
        if self.isDown():
            base_col = base_col.darker(116)

        state_ring_col = on_col if self.isChecked() else off_col

        pulse_wave = 1.0 - abs(self._pulse * 2.0 - 1.0)  # 0..1..0
        grow = int(self._max_pulse_px * (0.35 + 0.65 * pulse_wave))
        alpha = int(18 + 90 * pulse_wave)

        ring = QColor(state_ring_col)
        ring.setAlpha(alpha)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ring)
        p.drawEllipse(outer.adjusted(-grow, -grow, grow, grow))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base_col)
        p.drawEllipse(outer)

        inner_pad = max(10, min(w, h) // 11)
        inner = outer.adjusted(inner_pad, inner_pad, -inner_pad, -inner_pad)

        shade = QColor(0, 0, 0, int(52 + 40 * (1.0 - t)))
        if self.isDown():
            shade.setAlpha(min(95, shade.alpha() + 20))

        p.setBrush(shade)
        p.drawEllipse(inner)

        highlight = QColor(255, 255, 255, int(14 + 18 * t))
        p.setBrush(highlight)
        hl = inner.adjusted(-2, -2, -2, -2)
        hl.setHeight(max(6, hl.height() // 2))
        p.drawEllipse(hl)

        pm = self._cur_icon_pix
        if pm is not None and not pm.isNull():
            target = int(min(w, h) * 0.40)
            scale_to_target = target / max(1.0, float(min(pm.width(), pm.height())))

            cx = w / 2.0
            cy = h / 2.0

            p.save()
            p.translate(cx, cy)

            p.rotate(self._icon_angle)
            s = scale_to_target * self._icon_scale
            p.scale(s, s)

            p.translate(-pm.width() / 2.0, -pm.height() / 2.0)
            p.drawPixmap(0, 0, pm)
            p.restore()

        p.end()

class MainWindow(QWidget):
    def __init__(self, settings):
        super().__init__()
        self._exiting = False
        self._in_init = True
        self.settings = settings
        self.lang = settings.value('lang', 'ru')
        self.autostart = settings.value('autostart', False, type=bool)
        self.minimized = settings.value('minimized', False, type=bool)
        self.last_profile = settings.value('last_profile', 'General')

        self.core_dir = os.path.join(APP_DIR, 'core')
        #self.unblock_executables()
        self.presets = {}
        self.process = None
        self._auto_cancelled = False
        self._auto_done = 0
        self._auto_total = 0
        self._eta_ms_per_profile = None
        self._eta_last_done = 0
        self._eta_last_elapsed_ms = 0

        self.tray = None
        self.tray_menu = None
        self.action_open = None
        self.action_start = None
        self.action_stop = None
        self.preset_menu = None
        self.exit_action = None

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
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

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
        if self.tray is None or self.action_start is None or self.action_stop is None:
            return

        running = self.toggle_btn.isChecked()

        self.action_start.setEnabled(not running)
        self.action_stop.setEnabled(running)

        try:
            self.tray.setIcon(QIcon(self._tray_icon_path(running)))
        except Exception:
            pass
        self.tray.setToolTip(self.get_tray_tooltip())

        self.update_tray_presets()

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

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.windowState() & Qt.WindowState.WindowMinimized:
                QTimer.singleShot(0, self.hide)
                event.accept()
                return
        super().changeEvent(event)

    def update_tray_presets(self):
        if self.preset_menu is None:
            return
        if not hasattr(self, "cb"):
            return

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

    def on_auto_pick_profile(self):
        title = "Автоподбор профиля" if self.lang == "ru" else "Auto profile selection"
        text = "Вы хотите выполнить автоматический подбор профиля?" if self.lang == "ru" else "Do you want to auto-select the best profile?"

        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(text)
        btn_yes = msg.addButton("Да" if self.lang == "ru" else "Yes", QMessageBox.ButtonRole.YesRole)
        btn_no = msg.addButton("Нет" if self.lang == "ru" else "No", QMessageBox.ButtonRole.NoRole)
        msg.exec()

        if msg.clickedButton() != btn_yes:
            return

        if self.is_winws_running():
            QMessageBox.warning(
                self,
                title,
                "Сначала выключите обход (красная кнопка), затем запустите автоподбор."
                if self.lang == "ru" else
                "Please stop the bypass first (red button), then run auto selection."
            )
            return

        if not self.is_admin():
            QMessageBox.warning(
                self,
                title,
                "Автоподбор требует запуск приложения от администратора.\n"
                "Закройте программу и запустите EXE через ПКМ → Запуск от имени администратора."
                if self.lang == "ru" else
                "Auto selection requires running the app as Administrator.\n"
                "Close the app and run the EXE: Right click → Run as Administrator."
            )
            return

        self._auto_cancelled = False

        try:
            if hasattr(self, "_eta_timer") and self._eta_timer:
                self._eta_timer.stop()
        except Exception:
            pass

        title = "Автоподбор профиля" if self.lang == "ru" else "Auto profile selection"

        self._auto_progress = AutoProgressDialog(
            title=title,
            left_text="Тестируем профили..." if self.lang == "ru" else "Testing profiles...",
            cancel_text="Отмена" if self.lang == "ru" else "Cancel",
            parent=self
        )
        self._auto_progress.canceled.connect(self._on_auto_test_cancel)

        self._eta_timer = QTimer(self)
        self._eta_timer.setInterval(200)

        self._elapsed = QElapsedTimer()
        self._elapsed.start()

        def fmt_ms(ms: int) -> str:
            if ms < 0:
                ms = 0
            s = ms // 1000
            m = s // 60
            s = s % 60
            return f"{m:02d}:{s:02d}"

        def update_eta_tick():
            dlg = getattr(self, "_auto_progress", None)
            if dlg is None or (not dlg.isVisible()):
                return

            total = int(getattr(self, "_auto_total", 0))
            done = int(getattr(self, "_auto_done", 0))

            # если тест уже закончился - не трогаем
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
        self._auto_total = len(self.presets)
        self._eta_ms_per_profile = None
        self._eta_last_done = 0
        self._eta_last_elapsed_ms = 0
        self._auto_worker = AutoTestWorker(self.core_dir, self.presets, parent=self)
        self._auto_worker.finished_ok.connect(self._on_auto_test_done)
        self._auto_worker.finished_err.connect(self._on_auto_test_err)
        self._auto_worker.progress.connect(self._on_auto_test_progress)

        self._auto_progress.show()
        self._auto_worker.start()

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

        try:
            subprocess.run(["taskkill", "/IM", "winws.exe", "/F"], capture_output=True, text=True)
        except Exception:
            pass
        if w is not None:
            try:
                w.finished_ok.disconnect(self._on_auto_test_done)
            except Exception:
                pass
            try:
                w.finished_err.disconnect(self._on_auto_test_err)
            except Exception:
                pass
        try:
            if hasattr(self, "_eta_timer") and self._eta_timer:
                self._eta_timer.stop()
        except Exception:
            pass

        try:
            if hasattr(self, "_auto_progress") and self._auto_progress:
                self._auto_progress.close()
        except Exception:
            pass

    def _on_auto_test_err(self, err: str):
        if getattr(self, "_auto_cancelled", False):
            return
        try:
            if hasattr(self, "_eta_timer") and self._eta_timer:
                self._eta_timer.stop()
        except Exception:
            pass

        try:
            self._auto_progress.close()
        except Exception:
            pass

        QMessageBox.critical(
            self,
            "Автоподбор профиля" if self.lang == "ru" else "Auto selection",
            (
                f"Ошибка при выполнении тестов:\n{err}\n\n"
                f"Лог автотеста: {AUTOLOG_FILE}"
                if self.lang == "ru"
                else
                f"Auto test error:\n{err}\n\nLog file: {AUTOLOG_FILE}"
            )
        )

    def _on_auto_test_done(self, result: dict):
        if getattr(self, "_auto_cancelled", False):
            return
        try:
            if hasattr(self, "_eta_timer") and self._eta_timer:
                self._eta_timer.stop()
        except Exception:
            pass

        elapsed_ms = int(self._elapsed.elapsed()) if hasattr(self, "_elapsed") else 0

        total = max(1, len(self.presets))
        ms_per_profile = max(300, elapsed_ms // total)

        prev = int(self.settings.value("auto_test_avg_ms_per_profile", 0))
        new_avg = ms_per_profile if prev <= 0 else int(prev * 0.7 + ms_per_profile * 0.3)

        self.settings.setValue("auto_test_avg_ms_per_profile", new_avg)
        self.settings.sync()

        try:
            self._auto_progress.set_progress(self._auto_total, self._auto_total)
        except Exception:
            pass

        try:
            self._auto_progress.close()
        except Exception:
            pass

        good = result.get("good", [])
        bad = result.get("bad", [])
        raw = result.get("raw", "")
        extra_err = result.get("error", "")

        best = good[0] if good else None

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

        dlg = QMessageBox(self)
        dlg.setWindowTitle("Результаты автоподбора" if self.lang == "ru" else "Auto selection results")
        dlg.setIcon(QMessageBox.Icon.Information)
        dlg.setTextFormat(Qt.TextFormat.RichText)
        dlg.setText(html)
        dlg.exec()

        if best and best in self.presets:
            self.cb.setCurrentText(best)
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

        try:
            _force_stop_blockers()
        except Exception:
            pass

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

    def reload_presets(self):
        alt_re = re.compile(r"\(\s*([A-Za-z\-]*ALT)\s*(\d*)\s*\)\s*$", re.IGNORECASE)

        def sort_key(name: str):
            s = name.strip()

            m = alt_re.search(s)
            if m:
                alt_tag = (m.group(1) or "").casefold()
                num_str = (m.group(2) or "").strip()

                alt_num = int(num_str) if num_str.isdigit() else 1

                base = s[:m.start()].rstrip()

                parts = re.split(r"(\d+)", base)
                base_key = []
                for p in parts:
                    if p.isdigit():
                        base_key.append(int(p))
                    else:
                        base_key.append(p.casefold())

                return (base_key, 0, alt_tag, alt_num)

            parts = re.split(r"(\d+)", s)
            out = []
            for p in parts:
                if p.isdigit():
                    out.append(int(p))
                else:
                    out.append(p.casefold())
            return (out, 1, "", 0)

        self.presets = {"General": "general.bat"}

        items = []
        try:
            for fn in os.listdir(self.core_dir):
                low = fn.lower()
                if not low.endswith(".bat"):
                    continue
                if low.startswith("__noupdate__"):
                    continue
                if low in ("general.bat", "discord.bat", "service.bat", "cloudflare_switch.bat"):
                    continue
                name = os.path.splitext(fn)[0]
                items.append((name, fn))
        except FileNotFoundError:
            items = []

        for name, fn in sorted(items, key=lambda x: sort_key(x[0])):
            self.presets[name] = fn

        self.cb.blockSignals(True)
        self.cb.clear()
        self.cb.addItems(self.presets.keys())
        self.cb.setCurrentText(self.settings.value("last_profile", "General"))
        self.cb.blockSignals(False)

        try:
            self.cb.currentTextChanged.disconnect(self.on_profile_changed)
        except Exception:
            pass
        self.cb.currentTextChanged.connect(self.on_profile_changed)

        if getattr(self, "preset_menu", None) is not None:
            self.update_tray_presets()
        if getattr(self, "action_start", None) is not None:
            self.update_tray_status()

    def on_profile_changed(self, text):
        self.settings.setValue("last_profile", text)

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

    def open_instruction(self):
        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('Instruction'))

        if self.lang == 'ru':
            dialog.setFixedSize(410, 420)
        else:
            dialog.setFixedSize(410, 350)

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
        self.setWindowFlags(
            Qt.WindowType.Window
            | Qt.WindowType.CustomizeWindowHint
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowSystemMenuHint
            | Qt.WindowType.WindowMinimizeButtonHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        layout.setContentsMargins(12, 12, 12, 12)

        self.status_lbl = QLabel()
        self.status_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_lbl)

        icon_off_path = os.path.join(os.path.dirname(__file__), 'flags', 'toggle-off.ico')
        icon_on_path = os.path.join(os.path.dirname(__file__), 'flags', 'toggle-on.ico')

        icon_off = QIcon(icon_off_path) if os.path.exists(icon_off_path) else QIcon()
        icon_on = QIcon(icon_on_path) if os.path.exists(icon_on_path) else QIcon()

        # если новых иконок нет - используем старую toggle.ico или тему
        legacy_path = os.path.join(os.path.dirname(__file__), 'flags', 'toggle.ico')
        if icon_off.isNull() or icon_on.isNull():
            legacy = QIcon(legacy_path) if os.path.exists(legacy_path) else QIcon.fromTheme("media-playback-start")
            if icon_off.isNull():
                icon_off = legacy
            if icon_on.isNull():
                icon_on = legacy

        self.toggle_btn = AnimatedPowerToggleButton(icon_off=icon_off, icon_on=icon_on, parent=self)
        self.toggle_btn.setFixedSize(110, 110)

        self.toggle_btn.clicked.connect(self.on_toggle)

        hl = QHBoxLayout()
        hl.addStretch()
        hl.addWidget(self.toggle_btn)
        hl.addStretch()
        layout.addLayout(hl)

        self.auto_btn = QPushButton("A")
        self.auto_btn.setFixedSize(28, 28)
        self.auto_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_btn.setToolTip("Автоматический подбор профиля")
        self.auto_btn.setStyleSheet("""
            QPushButton {
                border: 2px solid green;
                color: green;
                border-radius: 14px;
                background: transparent;
                font-weight: 800;
            }
            QPushButton:hover { background: rgba(0,128,0,0.10); }
            QPushButton:pressed { background: rgba(0,128,0,0.20); }
        """)
        self.auto_btn.clicked.connect(self.on_auto_pick_profile)

        self.tray_btn = QPushButton()
        self.tray_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'flags', 'tray.ico')))
        self.tray_btn.setIconSize(QSize(24, 24))
        self.tray_btn.setToolTip(self.t('Minimize to tray'))
        self.tray_btn.setFixedSize(28, 28)
        self.tray_btn.setStyleSheet("border: none;")
        self.tray_btn.clicked.connect(self.hide)

        top_row = QHBoxLayout()
        top_row.addWidget(self.auto_btn)
        top_row.addStretch()
        top_row.addWidget(self.tray_btn)
        layout.addLayout(top_row)

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
            'Powered by '
            '<span style="color:#2ecc71;">Medvedeff</span>'
            ' & '
            '<span style="color:#e74c3c;">Zapret</span>'
            ' & '
            '<span style="color:#2ecc71;">Flowseal</span>'
        )

        self.powered_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.powered_lbl)

        # Мигание
        self.blink_on = False
        self.blink_timer = QTimer(self)
        self.blink_timer.timeout.connect(self.update_blink)
        self.blink_timer.start(800)

    def retranslate_ui(self):
        self.setWindowTitle('Zapret GUI')
        if self.toggle_btn.isChecked():
            self.status_lbl.setText(self.t('On: {}', self.cb.currentText()))
        else:
            self.status_lbl.setText(self.t('Off'))
        self.settings_btn.setText(self.t('Settings'))
        self.instruction_btn.setText(self.t('Instruction'))

    def update_blink(self):
        return

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
        self.settings.setValue("last_profile", profile)

        script = os.path.join(self.core_dir, self.presets[profile])
        if not os.path.exists(script):
            QMessageBox.warning(self, "Ошибка", f"Не найден файл:\n{script}")
            self.toggle_btn.setChecked(False)
            self.update_tray_status()
            return

        if checked:
            _force_stop_blockers()

            inp_path = _ensure_no_update_input()

            env = os.environ.copy()
            env["ZAPRETGUI_NOUPDATE"] = "1"

            fin = None
            try:
                fin = open(inp_path, "r", encoding="ascii")
            except Exception:
                fin = None

            si = None
            try:
                if hasattr(subprocess, "STARTUPINFO"):
                    si = subprocess.STARTUPINFO()
                    si.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                    si.wShowWindow = 0  # SW_HIDE
            except Exception:
                si = None

            flags = (
                    getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )

            try:
                self.process = subprocess.Popen(
                    ["cmd.exe", "/d", "/k", script],
                    cwd=self.core_dir,
                    stdin=fin if fin else subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    startupinfo=si,
                    creationflags=flags,
                    close_fds=True
                )
                self.status_lbl.setText(self.t("On: {}", profile))
            finally:
                try:
                    if fin:
                        fin.close()
                except Exception:
                    pass

        else:
            _run_hidden(["taskkill", "/IM", "winws.exe", "/F"])

            if self.process and self.process.poll() is None:
                _run_hidden(["taskkill", "/PID", str(self.process.pid), "/T", "/F"])

            self.process = None
            self.status_lbl.setText(self.t("Off"))

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

    def changeEvent(self, event):
        if event.type() == QEvent.Type.WindowStateChange:
            if self.isMinimized():
                QTimer.singleShot(0, self.hide)
                event.accept()
                return
        super().changeEvent(event)

    def closeEvent(self, event):
        if getattr(self, "_exiting", False):
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
                event.ignore()
                return

        self._shutdown_and_quit()
        event.accept()

def main():
    app = QApplication(sys.argv)
    wipe_app_dir_if_new_version()
    extract_files_from_meipass()
    unblock_core_tree(os.path.join(APP_DIR, "core"))
    create_delete_bat()
    settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
    _patch_profiles_if_core_outdated(os.path.join(APP_DIR, "core"), settings)
    _patch_profiles_hide_windows(os.path.join(APP_DIR, "core"))
    win = MainWindow(settings)
    icon_path = os.path.join(APP_DIR, 'flags', 'z.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()