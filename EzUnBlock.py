import sys
import os
import subprocess
import csv
import ipaddress
from PyQt6.QtCore import (
    Qt, QSettings, QSize, QTimer, QThread, pyqtSignal,
    QElapsedTimer, QEvent, QEasingCurve, QPropertyAnimation, pyqtProperty,
    QParallelAnimationGroup, QPoint, QRectF, QUrl, QVariantAnimation
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QAction, QPalette, QPainter, QColor, QPen, QBrush,
    QConicalGradient, QDesktopServices, QGuiApplication
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QCheckBox, QMessageBox, QSizePolicy,
    QSystemTrayIcon, QMenu, QTextBrowser, QProgressDialog, QProgressBar, QGraphicsDropShadowEffect,
    QListWidget, QListWidgetItem, QInputDialog, QTabWidget, QToolButton, QFileDialog, QLineEdit,
    QAbstractItemView, QStyle, QStyledItemDelegate, QTabBar
)
import shutil
import requests
import zipfile
import io
import re
import socket
import time
import ctypes
import json
import hashlib

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


APP_VERSION = "1.8.0"
APP_DIR = os.path.join(os.path.expanduser('~'), 'ZapretGUI')
os.makedirs(APP_DIR, exist_ok=True)

USER_DIR = os.path.join(APP_DIR, "user")
os.makedirs(USER_DIR, exist_ok=True)

FLOWSEAL_REPO = "Flowseal/zapret-discord-youtube"
FLOWSEAL_DEFAULT_VER = "1.9.7b"
FLOWSEAL_VER_KEY = "flowseal_release"

FLOWSEAL_LIST_BASE_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/lists/"
FLOWSEAL_LIST_FILES = (
    "ipset-all.txt",
    "ipset-exclude.txt",
    "list-exclude.txt",
    "list-general.txt",
    "list-google.txt",
)

SETTINGS_FILE = os.path.join(APP_DIR, 'settings.ini')
VERSION_FILE = os.path.join(APP_DIR, '.app_version')
AUTOLOG_FILE = os.path.join(APP_DIR, "autotest_last.log")
AUTORESULT_FILE = os.path.join(APP_DIR, "autotest_result.json")

REMOVE_BAT = os.path.join(APP_DIR, "uninstall.bat")

NOUPDATE_INP = os.path.join(APP_DIR, "_no_update_input.txt")

USER_GENERAL_FILE = os.path.join(USER_DIR, "list-general-user.txt")
USER_EXCLUDE_FILE = os.path.join(USER_DIR, "list-exclude-user.txt")

RUNTIME_GENERAL_FILE = os.path.join(APP_DIR, "core", "lists", "list-general.txt")
RUNTIME_EXCLUDE_FILE = os.path.join(APP_DIR, "core", "lists", "list-exclude.txt")

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

def _save_autotest_result(best: str | None, good: list[str], bad: list[str]) -> None:
    try:
        data = {
            "best": best or "",
            "good": list(good or []),
            "bad": list(bad or []),
            "updated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(AUTORESULT_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_autotest_result() -> dict:
    try:
        with open(AUTORESULT_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {}

def _sha256_bytes(data: bytes) -> str:
    try:
        return hashlib.sha256(data).hexdigest()
    except Exception:
        return ""


def _read_file_bytes(path: str) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read()
    except Exception:
        return b""


def _atomic_write_bytes(path: str, data: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp_path = path + ".tmp"
    with open(tmp_path, "wb") as f:
        f.write(data)
    os.replace(tmp_path, path)

def _read_lines_utf8(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return [ln.strip() for ln in f.read().splitlines()]
    except Exception:
        return []


def _write_lines_utf8(path: str, lines: list[str]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    uniq = []
    seen = set()
    for x in lines:
        s = (x or "").strip()
        if not s or s.startswith("#"):
            continue
        k = s.casefold()
        if k in seen:
            continue
        seen.add(k)
        uniq.append(s)

    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        if uniq:
            f.write("\n".join(uniq) + "\n")
        else:
            f.write("")
    os.replace(tmp, path)


def _copy_if_missing(src: str, dst: str) -> None:
    try:
        if os.path.exists(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    except Exception:
        pass


def _ensure_user_lists_initialized() -> None:
    os.makedirs(USER_DIR, exist_ok=True)
    _copy_if_missing(os.path.join(APP_DIR, "core", "lists", "list-general.txt"), USER_GENERAL_FILE)
    _copy_if_missing(os.path.join(APP_DIR, "core", "lists", "list-exclude.txt"), USER_EXCLUDE_FILE)

    if not os.path.exists(USER_GENERAL_FILE):
        _write_lines_utf8(USER_GENERAL_FILE, [])
    if not os.path.exists(USER_EXCLUDE_FILE):
        _write_lines_utf8(USER_EXCLUDE_FILE, [])


def _is_valid_domain_like(s: str) -> bool:
    s = _normalize_domain_candidate(s)
    if not s:
        return False
    if _is_ip_address_like(s):
        return False
    if "." not in s or s.endswith("."):
        return False
    if " " in s or "\t" in s:
        return False
    if not re.fullmatch(r"[a-z0-9._-]+", s):
        return False
    parts = s.split(".")
    if any(not part for part in parts):
        return False
    return not any(part.startswith("-") or part.endswith("-") for part in parts)


def _is_ip_address_like(s: str) -> bool:
    try:
        ipaddress.ip_address((s or "").strip())
        return True
    except ValueError:
        return False


def _normalize_domain_candidate(raw: str) -> str:
    s = (raw or "").strip().lower()
    if not s:
        return ""

    s = s.split("#", 1)[0].strip().strip("\"'[](){}<>")
    if not s:
        return ""

    if "://" in s:
        s = s.split("://", 1)[1]

    s = s.split("/", 1)[0].split("\\", 1)[0].strip()
    if ":" in s:
        host, port = s.rsplit(":", 1)
        if port.isdigit():
            s = host

    return s.lstrip(".").strip().strip("\"'[](){}<>")


def _extract_string_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_extract_string_values(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_extract_string_values(item))
        return out
    return []


def _extract_domain_candidates_from_text(raw_text: str) -> list[str]:
    out = []
    for line in (raw_text or "").splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if not cleaned:
            continue
        out.extend(part for part in re.split(r"[;,]", cleaned) if part.strip())
    return out


def _extract_domain_candidates_from_file(source_path: str, raw_text: str) -> list[str]:
    ext = os.path.splitext(source_path)[1].lower()

    if ext == ".json":
        try:
            return _extract_string_values(json.loads(raw_text))
        except Exception:
            return _extract_domain_candidates_from_text(raw_text)

    if ext == ".csv":
        out = []
        try:
            for row in csv.reader(io.StringIO(raw_text)):
                for cell in row:
                    out.extend(part for part in re.split(r"[;,]", cell) if part.strip())
            return out
        except Exception:
            return _extract_domain_candidates_from_text(raw_text)

    return _extract_domain_candidates_from_text(raw_text)


def _merge_unique(*lists: list[str]) -> list[str]:
    out = []
    seen = set()
    for arr in lists:
        for x in arr:
            s = (x or "").strip()
            if not s:
                continue
            k = s.casefold()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
    return out


def _rebuild_runtime_lists(settings: QSettings | None = None) -> None:
    try:
        _ensure_user_lists_initialized()

        core_general = _read_lines_utf8(os.path.join(APP_DIR, "core", "lists", "list-general.txt"))
        core_exclude = _read_lines_utf8(os.path.join(APP_DIR, "core", "lists", "list-exclude.txt"))

        user_general = _read_lines_utf8(USER_GENERAL_FILE)
        user_exclude = _read_lines_utf8(USER_EXCLUDE_FILE)

        merged_general = _merge_unique(core_general, user_general)
        merged_exclude = _merge_unique(core_exclude, user_exclude)

        _write_lines_utf8(RUNTIME_GENERAL_FILE, merged_general)
        _write_lines_utf8(RUNTIME_EXCLUDE_FILE, merged_exclude)
    except Exception:
        pass


def _sync_flowseal_lists(settings: QSettings | None = None) -> dict:
    result = {
        "ok": False,
        "offline": False,
        "flowseal_updated": 0,
        "error": "",
    }
    try:
        lists_dir = os.path.join(APP_DIR, "core", "lists")
        os.makedirs(lists_dir, exist_ok=True)
        os.makedirs(USER_DIR, exist_ok=True)

        session = requests.Session()
        session.headers.update({
            "User-Agent": "ZapretGUI-ListsSync",
            "Accept": "*/*",
            "Cache-Control": "no-cache",
        })

        flowseal_updates = []
        for fn in FLOWSEAL_LIST_FILES:
            url = FLOWSEAL_LIST_BASE_URL + fn
            r = session.get(url, timeout=(2.5, 6.0), allow_redirects=True)
            r.raise_for_status()
            remote_data = r.content
            dst = os.path.join(lists_dir, fn)
            local_data = _read_file_bytes(dst)
            if _sha256_bytes(local_data) != _sha256_bytes(remote_data):
                flowseal_updates.append((dst, remote_data))

        for dst, data in flowseal_updates:
            _atomic_write_bytes(dst, data)

        _ensure_user_lists_initialized()
        _rebuild_runtime_lists(settings)

        result["ok"] = True
        result["flowseal_updated"] = len(flowseal_updates)
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)
    return result


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
                if name.lower() == "user":
                    continue

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
        os.makedirs(USER_DIR, exist_ok=True)

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

        def _detect_local_core_version() -> str:
            try:
                svc = os.path.join(APP_DIR, "core", "service.bat")
                if not os.path.exists(svc):
                    return ""
                raw = _read_text(svc)
                m = re.search(r'(?im)^\s*set\s+"LOCAL_VERSION\s*=\s*([^"]+)"\s*$', raw)
                return (m.group(1).strip() if m else "")
            except Exception:
                return ""

        current_ver = str(settings.value(FLOWSEAL_VER_KEY, "")).strip()
        if not current_ver:
            current_ver = _detect_local_core_version().strip()
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

        try:
            is_newer = _version_key(latest_ver) > _version_key(current_ver)
        except Exception:
            is_newer = (latest_ver != current_ver)

        if not is_newer:
            lists_result = _sync_flowseal_lists(settings)
            if lists_result.get("offline"):
                QMessageBox.warning(
                    None,
                    "Обновление",
                    f"У вас уже актуальная версия: {current_ver}\nНе удалось проверить списки, проверьте интернет-соединение."
                )
            elif lists_result.get("flowseal_updated", 0) > 0:
                QMessageBox.information(
                    None,
                    "Обновление",
                    f"У вас уже актуальная версия: {current_ver}\nСписки обновлены: {lists_result.get('flowseal_updated', 0)}"
                )
            else:
                QMessageBox.information(
                    None,
                    "Обновление",
                    f"У вас уже актуальная версия: {current_ver}\nСписки актуальны."
                )
            return

        msg = QMessageBox()
        msg.setWindowTitle("Обновление")
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(
            f"Доступен новый релиз: {latest_ver}\n"
            f"Текущая версия: {current_ver}\n\n"
            "Будет обновлена папка core, при этом пользовательская папка user сохранится.\n"
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

        zr = requests.get(download_url, headers=headers, timeout=60)
        zr.raise_for_status()
        z = zipfile.ZipFile(io.BytesIO(zr.content))

        core_target = os.path.join(APP_DIR, "core")
        os.makedirs(core_target, exist_ok=True)
        os.makedirs(USER_DIR, exist_ok=True)

        for name in os.listdir(core_target):
            p = os.path.join(core_target, name)
            if os.path.isdir(p):
                shutil.rmtree(p, ignore_errors=False)
            else:
                os.remove(p)

        names = [n for n in z.namelist() if n and not n.startswith("__MACOSX/")]

        top_levels = set()
        for n in names:
            seg = n.split("/", 1)[0]
            if seg:
                top_levels.add(seg)

        root_prefix = ""
        if len(top_levels) == 1:
            root_prefix = next(iter(top_levels)) + "/"

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

        settings.setValue(FLOWSEAL_VER_KEY, latest_ver)
        settings.sync()

        lists_result = _sync_flowseal_lists(settings)
        list_status = "Списки актуальны." if lists_result.get("flowseal_updated", 0) == 0 else f"Списки обновлены: {lists_result.get('flowseal_updated', 0)}"
        if lists_result.get("offline"):
            list_status = "Обновлено, но список не удалось проверить/обновить: проверьте интернет-соединение."
        elif lists_result.get("error"):
            list_status = "Обновлено, но произошла ошибка при проверке списков."

        QMessageBox.information(
            None,
            "Обновление завершено",
            f"Обновлено до: {latest_ver}\n"
            f"Файлов распаковано: {replaced}\n\n"
            f"{list_status}\n"
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

def _version_key(v: str):
    s = (v or "").strip()
    if s.startswith(("v", "V")):
        s = s[1:].strip()

    m = re.match(r"^\s*(\d+(?:\.\d+){0,3})(.*)\s*$", s)
    if not m:
        return ((0, 0, 0, 0), 0, ("",))

    num_part = m.group(1).strip()
    suffix = (m.group(2) or "").strip()

    nums = []
    for p in num_part.split("."):
        try:
            nums.append(int(p))
        except Exception:
            nums.append(0)
    while len(nums) < 4:
        nums.append(0)
    nums = tuple(nums[:4])

    suffix = re.sub(r"^[\s\-\._]+", "", suffix)

    has_suffix = 1 if suffix else 0

    if not suffix:
        suffix_key = ("",)
    else:
        toks = []
        for t in re.findall(r"[A-Za-z]+|\d+|[^A-Za-z\d]+", suffix):
            if t.isdigit():
                toks.append((1, int(t)))
            else:
                toks.append((0, t.casefold()))
        suffix_key = tuple(toks)

    return (nums, has_suffix, suffix_key)

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

        def _detect_local_core_version() -> str:
            try:
                svc = os.path.join(core_dir, "service.bat")
                if not os.path.exists(svc):
                    return ""
                raw = _read_text(svc)
                m = re.search(r'(?im)^\s*set\s+"LOCAL_VERSION\s*=\s*([^"]+)"\s*$', raw)
                return (m.group(1).strip() if m else "")
            except Exception:
                return ""

        current = _detect_local_core_version().strip()
        if not current:
            current = str(settings.value(FLOWSEAL_VER_KEY, FLOWSEAL_DEFAULT_VER)).strip() or FLOWSEAL_DEFAULT_VER

        try:
            outdated = _version_key(latest) > _version_key(current)
        except Exception:
            outdated = (latest != current)

        try:
            settings.setValue(FLOWSEAL_VER_KEY, current)
            settings.sync()
        except Exception:
            pass

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
        'Sites': 'Сайты',
        'Add': 'Добавить',
        'Exclude': 'Исключить',
        'Instruction Text': """
        <b>1.</b> Выберите из выпадающего списка <b>профиль настроек</b>, затем нажмите на <span style="color:red;"><b>большую красную кнопку</b></span>, чтобы запустить обход блокировок.<br><br>
        <b>2.</b> Если выбранный профиль не сработал — <span style="color:green;"><b>нажмите на зелёную кнопку</b></span> для отключения и выберите другой профиль.<br><br>
        <b>3.</b> В настройках можно включить <b>Автозапуск</b> вместе с Windows и выбрать профиль для автозапуска.<br><br>
        <b>4.</b> Чтобы проверить, работает ли обход — попробуйте открыть сайты, которые у вас не открывались, или сделайте проверку на сайте: <a href="https://www.youtube.com">@YouTube</a> или <a href="https://discord.com/">@Discord</a><br><br>
        <b>5.</b> Для автоматического подбора профиля можно воспользоваться кнопкой - <span style="color:green;"><b>зелёный кружок с буквой "А" внутри.</b></span> Процесс подбора обычно занимает несколько минут.<br><br>
        <b>6.</b> Инструкцию по использованию Менеджера сайтов можно открыть по кнопке "i" внутри окна, либо по этой кнопке -
        <a href="app://site-manager-tutorial" style="display:inline-block; padding:3px 10px; border-radius:8px; background:#2db45f; color:white; text-decoration:none;"><b>Нажми сюда</b></a>
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
        'Sites': 'Sites',
        'Add': 'Add',
        'Exclude': 'Exclude',
        'Instruction Text': """
        <b>1.</b> Select a <b>profile</b> from the dropdown list, then click the <span style="color:red;"><b>big red button</b></span> to start the bypass. <i>(By default, profile <b>General</b> is used).</i><br><br>
        <b>2.</b> If the selected profile doesn’t work — <span style="color:green;"><b>click the green button</b></span> to stop and choose another profile.<br><br>
        <b>3.</b> In settings you can enable <b>Autostart</b> with Windows and choose a profile for autostart.<br><br>
        <b>4.</b> To check if bypass works — try opening websites that were blocked for you, or test on: <a href="https://www.youtube.com">@YouTube</a> or <a href="https://discord.com/">@Discord</a><br><br>
        <b>5.</b> To automatically select a profile, you can use the button - <span style="color:green;"><b>green circle with the letter “A” inside.</b></span> The selection process usually takes a few minutes.<br><br>
        <b>6.</b> You can open the Site Manager guide from the "i" button inside that window, or by pressing this button -
        <a href="app://site-manager-tutorial" style="display:inline-block; padding:3px 10px; border-radius:8px; background:#2db45f; color:white; text-decoration:none;"><b>Click here</b></a>
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
                subprocess.run(
                    ["sc", "stop", svc],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL
                )
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
        env["NO_UPDATE_CHECK"] = "1"

        proc = None
        try:
            with open(AUTOLOG_FILE, "a", encoding="utf-8") as log, open(inp_path, "r", encoding="ascii") as fin:
                proc = subprocess.Popen(
                    ["cmd.exe", "/d", "/c", bat],
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
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
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
            env["NO_UPDATE_CHECK"] = "1"

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
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        except Exception:
            pass

class ListsUpdateWorker(QThread):
    finished_sync = pyqtSignal(dict)

    def __init__(self, core_lists_dir: str, user_lists_dir: str, parent=None):
        super().__init__(parent)
        self.core_lists_dir = core_lists_dir
        self.user_lists_dir = user_lists_dir

    def _download_bytes(self, session: requests.Session, url: str) -> bytes:
        r = session.get(
            url,
            timeout=(2.5, 6.0),
            allow_redirects=True,
        )
        r.raise_for_status()
        return r.content

    def run(self):
        result = {
            "ok": False,
            "offline": False,
            "flowseal_updated": 0,
            "error": "",
        }

        try:
            os.makedirs(self.core_lists_dir, exist_ok=True)
            os.makedirs(self.user_lists_dir, exist_ok=True)

            session = requests.Session()
            session.headers.update({
                "User-Agent": "ZapretGUI-ListsSync",
                "Accept": "*/*",
                "Cache-Control": "no-cache",
            })

            remote_flowseal = {}
            for fn in FLOWSEAL_LIST_FILES:
                url = FLOWSEAL_LIST_BASE_URL + fn
                remote_flowseal[fn] = self._download_bytes(session, url)

            flowseal_updates = []
            for fn, remote_data in remote_flowseal.items():
                dst = os.path.join(self.core_lists_dir, fn)
                local_data = _read_file_bytes(dst)
                if _sha256_bytes(local_data) != _sha256_bytes(remote_data):
                    flowseal_updates.append((dst, remote_data))

            for dst, data in flowseal_updates:
                _atomic_write_bytes(dst, data)

            _ensure_user_lists_initialized()

            result["ok"] = True
            result["flowseal_updated"] = len(flowseal_updates)

        except requests.exceptions.RequestException as e:
            result["offline"] = True
            result["error"] = str(e)
        except Exception as e:
            result["error"] = str(e)

        self.finished_sync.emit(result)

class AutoTestSpinner(QWidget):
    def __init__(self, icon: QIcon | None = None, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)

        self._icon = icon if (icon is not None and (not icon.isNull())) else QIcon()
        self._icon_pm = None
        self._rebuild_icon_pix()

        self._progress = 0.0   # 0..1
        self._pulse = 0.0      # 0..1
        self._angle = 0.0
        self._scale = 1.0      # 0.9..1.05

        self._anim_progress = QPropertyAnimation(self, b"progress", self)
        self._anim_progress.setDuration(220)
        self._anim_progress.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_pulse = QPropertyAnimation(self, b"pulse", self)
        self._anim_pulse.setDuration(1200)
        self._anim_pulse.setStartValue(0.0)
        self._anim_pulse.setEndValue(1.0)
        self._anim_pulse.setLoopCount(-1)
        self._anim_pulse.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._anim_angle = QPropertyAnimation(self, b"iconAngle", self)
        self._anim_angle.setDuration(1600)
        self._anim_angle.setStartValue(0.0)
        self._anim_angle.setEndValue(360.0)
        self._anim_angle.setLoopCount(-1)
        self._anim_angle.setEasingCurve(QEasingCurve.Type.Linear)

        self._anim_scale = QPropertyAnimation(self, b"iconScale", self)
        self._anim_scale.setDuration(1150)  
        self._anim_scale.setKeyValueAt(0.00, 1.08)  
        self._anim_scale.setKeyValueAt(0.50, 0.82)  #
        self._anim_scale.setKeyValueAt(1.00, 1.08)
        self._anim_scale.setLoopCount(-1)
        self._anim_scale.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._running = False

    def setIcon(self, icon: QIcon):
        self._icon = icon if (icon is not None and (not icon.isNull())) else QIcon()
        self._rebuild_icon_pix()
        self.update()

    def _rebuild_icon_pix(self):
        try:
            if self._icon is None or self._icon.isNull():
                self._icon_pm = None
                return
            pm = self._icon.pixmap(512, 512)
            self._icon_pm = pm if (pm is not None and not pm.isNull()) else None
        except Exception:
            self._icon_pm = None

    def start(self):
        if self._running:
            return
        self._running = True
        self._anim_angle.start()
        self._anim_scale.start()

    def stop(self):
        self._running = False
        for a in (self._anim_pulse, self._anim_angle, self._anim_scale, self._anim_progress):
            try:
                a.stop()
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

    def animate_to_progress(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        self._anim_progress.stop()
        self._anim_progress.setStartValue(self._progress)
        self._anim_progress.setEndValue(v)
        self._anim_progress.start()

    def getPulse(self) -> float:
        return float(self._pulse)

    def setPulse(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        if abs(self._pulse - v) > 1e-4:
            self._pulse = v
            self.update()

    pulse = pyqtProperty(float, fget=getPulse, fset=setPulse)

    def getIconAngle(self) -> float:
        return float(self._angle)

    def setIconAngle(self, v: float):
        v = float(v)
        if abs(self._angle - v) > 1e-3:
            self._angle = v
            self.update()

    iconAngle = pyqtProperty(float, fget=getIconAngle, fset=setIconAngle)

    def getIconScale(self) -> float:
        return float(self._scale)

    def setIconScale(self, v: float):
        v = max(0.70, min(1.20, float(v)))
        if abs(self._scale - v) > 1e-3:
            self._scale = v
            self.update()

    iconScale = pyqtProperty(float, fget=getIconScale, fset=setIconScale)

    def sizeHint(self):
        return QSize(130, 130)

    def paintEvent(self, event):
        w = self.width()
        h = self.height()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        p.setPen(Qt.PenStyle.NoPen)
        side = min(w, h)
        cx = w / 2.0
        cy = h / 2.0

        pad = max(6, side // 14)

        ring_w = max(6, int(side * 0.08))
        ring_gap = 3
        ring_total = ring_w + ring_gap

        full = self.rect().adjusted(pad, pad, -pad, -pad)
        ring_rect = full

        outer = self.rect().adjusted(pad + ring_total, pad + ring_total, -(pad + ring_total), -(pad + ring_total))

        off_col = QColor(220, 50, 50)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(off_col)
        p.drawEllipse(outer)

        inner_pad = max(10, min(outer.width(), outer.height()) // 11)
        inner = outer.adjusted(inner_pad, inner_pad, -inner_pad, -inner_pad)

        shade = QColor(0, 0, 0, 92)
        highlight = QColor(255, 255, 255, 14)

        p.setBrush(shade)
        p.drawEllipse(inner)

        # лёгкий блик сверху
        p.setBrush(highlight)
        hl = inner.adjusted(-2, -2, -2, -2)
        hl.setHeight(max(6, hl.height() // 2))
        p.drawEllipse(hl)

        ring_margin = max(2, side // 30)
        ring_rect = outer.adjusted(ring_margin, ring_margin, -ring_margin, -ring_margin)

        if ring_rect.width() > 8 and ring_rect.height() > 8:
            start_deg = -90.0
            span_deg = 360.0 * float(self._progress)
            ring_w = max(6, int(side * 0.08))

            green = QColor("#2db45f")

            pulse_wave2 = 1.0 - abs(self._pulse * 2.0 - 1.0)
            glow = QColor(green)
            glow.setAlpha(int(10 + 36 * pulse_wave2))
            pen_glow = QPen(glow, ring_w + 5, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
            p.setPen(pen_glow)
            p.drawArc(ring_rect, int(start_deg * 16), int(-span_deg * 16))

            base = QColor(green)
            base.setAlpha(235)
            pen_base = QPen(base, ring_w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap)
            p.setPen(pen_base)
            p.drawArc(ring_rect, int(start_deg * 16), int(-span_deg * 16))
        pm = self._icon_pm
        if pm is not None and (not pm.isNull()):
            target = int(side * 0.36)

            dpr = float(pm.devicePixelRatio()) if hasattr(pm, "devicePixelRatio") else 1.0
            logical_w = pm.width() / max(1.0, dpr)
            logical_h = pm.height() / max(1.0, dpr)

            scale_to_target = target / max(1.0, float(min(logical_w, logical_h)))

            p.save()
            p.translate(cx, cy)
            p.rotate(self._angle)
            s = scale_to_target * float(self._scale)
            p.scale(s, s)
            p.translate(-pm.width() / 2.0, -pm.height() / 2.0)
            p.drawPixmap(0, 0, pm)
            p.restore()

        p.end()


class AutoProgressDialog(QDialog):
    canceled = pyqtSignal()

    def __init__(self, title: str, left_text: str, cancel_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(330, 240)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowMaximizeButtonHint
        self.setWindowFlags(flags)

        v = QVBoxLayout(self)
        v.setContentsMargins(12, 12, 12, 12)
        v.setSpacing(10)

        row = QHBoxLayout()
        self.lbl_left = QLabel(left_text)
        self.lbl_right = QLabel("")  # ETA
        self.lbl_right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_right.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,235);
                font-weight: 600;
            }
        """)
        shadow_eta = QGraphicsDropShadowEffect(self.lbl_right)
        shadow_eta.setBlurRadius(10)
        shadow_eta.setOffset(0, 2)
        shadow_eta.setColor(QColor(0, 0, 0, 180))
        self.lbl_right.setGraphicsEffect(shadow_eta)

        row.addWidget(self.lbl_left, 1)
        row.addWidget(self.lbl_right, 0)
        v.addLayout(row)

        icon_path = os.path.join(APP_DIR, "flags", "toggle-on.ico")
        ico = QIcon(icon_path) if os.path.exists(icon_path) else QIcon.fromTheme("applications-system")

        self.spinner = AutoTestSpinner(icon=ico, parent=self)
        self.spinner.setFixedSize(140, 140)
        self.spinner.start()

        spin_row = QHBoxLayout()
        spin_row.addStretch()
        spin_row.addWidget(self.spinner)
        spin_row.addStretch()
        v.addLayout(spin_row)

        self.lbl_profile = QLabel("")
        self.lbl_profile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_profile.setStyleSheet("""
            QLabel {
                color: rgba(255,255,255,235);
                font-weight: 600;
            }
        """)
        # тень
        shadow = QGraphicsDropShadowEffect(self.lbl_profile)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.lbl_profile.setGraphicsEffect(shadow)

        v.addWidget(self.lbl_profile)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton(cancel_text)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_cancel)
        v.addLayout(btn_row)

    def closeEvent(self, e):
        try:
            if hasattr(self, "spinner") and self.spinner:
                self.spinner.stop()
        except Exception:
            pass
        super().closeEvent(e)

    def set_progress(self, cur: int, total: int):
        total = max(1, int(total))
        cur = max(0, min(int(cur), total))
        frac = float(cur) / float(total)
        try:
            self.spinner.animate_to_progress(frac)
        except Exception:
            try:
                self.spinner.progress = frac
            except Exception:
                pass

    def set_current_profile(self, name: str):
        # красивее читается с префиксом
        if name:
            self.lbl_profile.setText(f"Профиль: {name}")
        else:
            self.lbl_profile.setText("")

    def _on_cancel(self):
        self.canceled.emit()
        self.close()

    def set_eta_text(self, s: str):
        self.lbl_right.setText(s or "")

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
            pm = ic.pixmap(512, 512)
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

            dpr = float(pm.devicePixelRatio()) if hasattr(pm, "devicePixelRatio") else 1.0
            logical_w = pm.width() / max(1.0, dpr)
            logical_h = pm.height() / max(1.0, dpr)

            scale_to_target = target / max(1.0, float(min(logical_w, logical_h)))

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

class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)

    def sizeHint(self):
        return QSize(44, 24)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = self.rect().adjusted(1, 1, -1, -1)
        radius = r.height() / 2

        if self.isChecked():
            bg = QColor("#2db45f")
            knob_x = r.right() - r.height() + 1
        else:
            bg = QColor(110, 110, 110)
            knob_x = r.left()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, radius, radius)

        knob_rect = QRectF(knob_x, r.top(), r.height(), r.height()).adjusted(2, 2, -2, -2)
        p.setBrush(QColor("white"))
        p.drawEllipse(knob_rect)

        p.end()

class SiteManagerTutorButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Обучение по менеджеру сайтов")
        self.setFixedSize(30, 30)
        self.setAutoRaise(True)
        self.setStyleSheet("QToolButton { border: none; background: transparent; }")

        icon_path = os.path.join(os.path.dirname(__file__), "flags", "info.ico")
        self._icon = QIcon(icon_path) if os.path.exists(icon_path) else self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self._icon_size = 20

        self._pulse = 0.0
        self._pulse_anim = QPropertyAnimation(self, b"pulse", self)
        self._pulse_anim.setDuration(1150)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

    def start_pulse(self) -> None:
        if self._pulse_anim.state() != QPropertyAnimation.State.Running:
            self._pulse_anim.start()

    def stop_pulse(self) -> None:
        self._pulse_anim.stop()
        self._pulse = 0.0
        self.update()

    def getPulse(self) -> float:
        return float(self._pulse)

    def setPulse(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        if abs(self._pulse - value) > 1e-4:
            self._pulse = value
            self.update()

    pulse = pyqtProperty(float, fget=getPulse, fset=setPulse)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        pulse_wave = 1.0 - abs(self._pulse * 2.0 - 1.0)

        bg = QColor(255, 255, 255, 22 if not self.isDown() else 36)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawEllipse(rect)

        if self._pulse_anim.state() == QPropertyAnimation.State.Running:
            glow_rect = QRectF(rect).adjusted(1.5, 1.5, -1.5, -1.5)
            glow = QColor("#2db45f")
            glow.setAlpha(int(26 + 78 * pulse_wave))
            painter.setBrush(glow)
            painter.drawEllipse(glow_rect)

            border = QColor("#66d58c")
            border.setAlpha(int(95 + 120 * pulse_wave))
            painter.setPen(QPen(border, 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(glow_rect.adjusted(0.5, 0.5, -0.5, -0.5))

            inner_glow = QColor(255, 255, 255, int(18 + 34 * pulse_wave))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(inner_glow)
            painter.drawEllipse(QRectF(rect).adjusted(6, 6, -6, -6))

        icon_pm = self._icon.pixmap(self._icon_size, self._icon_size)
        icon_rect = QRectF(
            rect.center().x() - self._icon_size / 2,
            rect.center().y() - self._icon_size / 2,
            self._icon_size,
            self._icon_size,
        )
        painter.drawPixmap(icon_rect.toRect(), icon_pm)
        painter.end()

class SiteManagerTutorialDialog(QDialog):
    def __init__(self, parent=None, lang="ru"):
        super().__init__(parent)
        self.lang = lang

        self.setWindowTitle("Обучение: Менеджер сайтов" if lang == "ru" else "Guide: Site manager")
        self.setFixedSize(430, 500)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.setStyleSheet("""
            QDialog {
                background: #171717;
            }
            QLabel#Title {
                color: white;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#Subtitle {
                color: rgba(220,220,220,0.92);
                font-size: 12px;
            }
            QTextBrowser {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                background: rgba(255,255,255,0.03);
                padding: 6px;
            }
            QCheckBox {
                color: white;
                spacing: 8px;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 14px;
                border-radius: 8px;
                background: #2db45f;
                color: white;
                font-weight: 600;
            }
            QPushButton:hover { background: #36c96b; }
            QPushButton:pressed { background: #25934d; }
        """)

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 14)
        root.setSpacing(10)

        title = QLabel("Как пользоваться Менеджером сайтов" if lang == "ru" else "How to use Site Manager")
        title.setObjectName("Title")
        root.addWidget(title)

        subtitle = QLabel(
            "Короткое обучение по вкладкам, кнопкам и спискам."
            if lang == "ru" else
            "A quick walkthrough of tabs, buttons, and list actions."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(False)
        browser.setHtml(self._build_html())
        root.addWidget(browser, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self.dont_show_cb = QCheckBox(
            "Больше не показывать"
            if lang == "ru" else
            "Don't show again"
        )
        self.dont_show_cb.setChecked(True)
        bottom.addWidget(self.dont_show_cb, 1)

        close_btn = QPushButton("Понятно" if lang == "ru" else "Got it")
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn, 0)
        root.addLayout(bottom)

    def _build_html(self) -> str:
        if self.lang == "ru":
            return """
                <html><body style="font-family:Segoe UI; font-size:10.5pt; color:#efefef;">
                <div style="background:rgba(45,180,95,0.10); border:1px solid rgba(45,180,95,0.28); border-radius:12px; padding:12px; margin-bottom:10px;">
                    <b>Что делает это окно</b><br>
                    Здесь можно быстро добавлять сайты в список обхода или, наоборот, исключать их из обработки.
                </div>
                <div style="margin-bottom:10px;">
                    <b>1. Вкладки сверху</b><br>
                    <span style="color:#bfbfbf;">Добавление</span> — домены будут добавлены в пользовательский список обхода.<br>
                    <span style="color:#bfbfbf;">Исключения</span> — домены будут исключены из обработки.
                </div>
                <div style="margin-bottom:10px;">
                    <b>2. Кнопки сверху</b><br>
                    Открыть папку — открывает каталог с пользовательскими списками.<br>
                    Добавить список — импортирует домены в список добавления.<br>
                    Исключить список — импортирует домены в список исключений.
                </div>
                <div style="margin-bottom:10px;">
                    <b>3. Кнопки рядом с вкладками</b><br>
                    Кнопка с плюсом добавляет один сайт вручную в текущую вкладку.<br>
                    Поле поиска ниже фильтрует уже загруженный список.
                </div>
                <div style="margin-bottom:10px;">
                    <b>4. Работа со списком</b><br>
                    Нажатие по строке отмечает домен галочкой.<br>
                    Корзина удаляет отмеченные записи.<br>
                    Стрелка справа от домена открывает сайт в браузере по умолчанию.
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px;">
                    <b>Подсказка</b><br>
                    Если сомневаетесь, добавляйте сайт через вкладку <b>Добавление</b>. Исключения нужны, когда сайт нужно убрать из обработки.
                </div>
                </body></html>
            """
        return """
            <html><body style="font-family:Segoe UI; font-size:10.5pt; color:#efefef;">
            <div style="background:rgba(45,180,95,0.10); border:1px solid rgba(45,180,95,0.28); border-radius:12px; padding:12px; margin-bottom:10px;">
                <b>What this window does</b><br>
                Use it to add domains to the bypass list or exclude them from processing.
            </div>
            <div style="margin-bottom:10px;">
                <b>1. Top tabs</b><br>
                <span style="color:#bfbfbf;">Additions</span> adds domains to the user bypass list.<br>
                <span style="color:#bfbfbf;">Excludes</span> keeps domains out of processing.
            </div>
            <div style="margin-bottom:10px;">
                <b>2. Top buttons</b><br>
                Open folder opens the folder with user lists.<br>
                Add list imports domains into additions.<br>
                Exclude list imports domains into excludes.
            </div>
            <div style="margin-bottom:10px;">
                <b>3. Buttons near tabs</b><br>
                The plus button adds a single site into the current tab.<br>
                The search field below filters the currently loaded list.
            </div>
            <div style="margin-bottom:10px;">
                <b>4. Working with the list</b><br>
                Clicking a row toggles its checkmark.<br>
                The trash button removes checked items.<br>
                The arrow on the right opens a site in the default browser.
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px;">
                <b>Tip</b><br>
                If you are unsure, start with <b>Additions</b>. Use <b>Excludes</b> only when you want a site removed from processing.
            </div>
            </body></html>
        """

class SiteManagerDialog(QDialog):
    TUTORIAL_SEEN_KEY = "site_manager_tutorial_seen"
    TUTORIAL_HIDE_KEY = "site_manager_tutorial_hide_button"

    class AttentionTabBar(QTabBar):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._attention_alpha = 0

        def set_attention_state(self, alpha: int) -> None:
            self._attention_alpha = max(0, min(255, alpha))
            self.update()

        def clear_attention(self) -> None:
            self._attention_alpha = 0
            self.update()

        def paintEvent(self, event):
            super().paintEvent(event)
            if self._attention_alpha <= 0:
                return

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            outline = QColor("#2db45f")
            outline.setAlpha(self._attention_alpha)
            pen = QPen(outline, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for index in range(self.count()):
                rect = self.tabRect(index).adjusted(2, 2, -2, -2)
                if rect.isValid():
                    painter.drawRoundedRect(QRectF(rect.adjusted(0, 0, -1, -1)), 8, 8)

            painter.end()

    class SiteListDelegate(QStyledItemDelegate):
        def __init__(self, dialog):
            super().__init__(dialog)
            self.dialog = dialog

        def paint(self, painter, option, index):
            super().paint(painter, option, index)

            item_rect = QRectF(option.rect)
            icon_rect = self.dialog._visit_icon_rect(option.rect)
            color = QColor("#2db45f") if not index.data(Qt.ItemDataRole.CheckStateRole) else QColor("#43c879")

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            arrow_start = QPoint(
                int(icon_rect.left() + 5),
                int(icon_rect.bottom() - 5),
            )
            arrow_end = QPoint(
                int(icon_rect.right() - 5),
                int(icon_rect.top() + 5),
            )
            painter.drawLine(arrow_start, arrow_end)
            painter.drawLine(
                arrow_end,
                QPoint(int(icon_rect.right() - 10), int(icon_rect.top() + 5)),
            )
            painter.drawLine(
                arrow_end,
                QPoint(int(icon_rect.right() - 5), int(icon_rect.top() + 10)),
            )

            underline_y = int(item_rect.bottom() - 8)
            painter.setPen(QPen(color, 1))
            painter.drawLine(
                QPoint(int(icon_rect.left() + 4), underline_y),
                QPoint(int(icon_rect.right() - 4), underline_y),
            )
            painter.restore()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.lang = getattr(parent, "lang", "ru") if parent else "ru"
        self.current_file = None
        self.lazy_loaded = [False, False]
        self._mode_activated = False
        self._tutorial_dialog = None

        base_w = parent.width() if parent else 300
        self.setWindowTitle("Менеджер сайтов" if self.lang == "ru" else "Site manager")
        self.setMinimumSize(base_w, 380)
        self.resize(base_w, 420)
        self.setFixedWidth(base_w)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(8)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        tool_btn_style = """
            QToolButton {
                border: 1px solid rgba(120,120,120,90);
                border-radius: 8px;
                background: transparent;
                padding: 6px 8px 5px 8px;
                text-align: center;
                font-size: 12px;
            }
            QToolButton:hover { background: rgba(120,120,120,0.12); }
            QToolButton:pressed { background: rgba(120,120,120,0.20); }
        """

        self.open_folder_btn = QToolButton()
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.setToolTip(USER_DIR)
        self.open_folder_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.open_folder_btn.setText("Открыть\nпапку" if self.lang == "ru" else "Open\nfolder")
        self.open_folder_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.open_folder_btn.setIconSize(QSize(18, 18))
        self.open_folder_btn.setFixedHeight(68)
        self.open_folder_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.open_folder_btn.setStyleSheet(tool_btn_style)
        self.open_folder_btn.clicked.connect(self.open_user_folder)

        self.import_add_btn = QToolButton()
        self.import_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_add_btn.setToolTip(
            "Добавить домены в user/list-general-user.txt"
            if self.lang == "ru" else
            "Add domains to user/list-general-user.txt"
        )
        self.import_add_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.import_add_btn.setText("Добавить\nсписок" if self.lang == "ru" else "Add\nlist")
        self.import_add_btn.setIcon(self._build_folder_action_icon("#2db45f", True))
        self.import_add_btn.setIconSize(QSize(18, 18))
        self.import_add_btn.setFixedHeight(68)
        self.import_add_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.import_add_btn.setStyleSheet(tool_btn_style)
        self.import_add_btn.clicked.connect(self.import_add_file)

        self.import_exclude_btn = QToolButton()
        self.import_exclude_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_exclude_btn.setToolTip(
            "Добавить домены в user/list-exclude-user.txt"
            if self.lang == "ru" else
            "Add domains to user/list-exclude-user.txt"
        )
        self.import_exclude_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.import_exclude_btn.setText("Исключить\nсписок" if self.lang == "ru" else "Exclude\nlist")
        self.import_exclude_btn.setIcon(self._build_folder_action_icon("#d46060", False))
        self.import_exclude_btn.setIconSize(QSize(18, 18))
        self.import_exclude_btn.setFixedHeight(68)
        self.import_exclude_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.import_exclude_btn.setStyleSheet(tool_btn_style)
        self.import_exclude_btn.clicked.connect(self.import_exclude_file)

        top_row.addWidget(self.open_folder_btn, 1)
        top_row.addWidget(self.import_add_btn, 1)
        top_row.addWidget(self.import_exclude_btn, 1)
        root.addLayout(top_row)

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)

        self.tabs = QTabWidget()
        self.tabs.setTabBar(self.AttentionTabBar(self.tabs))
        self.tabs.setDocumentMode(True)
        self.tabs.setTabPosition(QTabWidget.TabPosition.North)
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setUsesScrollButtons(False)
        self.tabs.setElideMode(Qt.TextElideMode.ElideRight)
        self.tabs.setStyleSheet("""
            QTabWidget::pane {
                border: none;
                background: transparent;
                margin: 0;
                padding: 0;
            }
            QTabBar::tab {
                padding: 6px 10px;
                margin: 0 2px;
                border-radius: 8px;
                background: transparent;
                border: 1px solid rgba(120,120,120,70);
                min-width: 78px;
                max-width: 96px;
            }
            QTabBar[modeActivated="true"]::tab:selected {
                background: #2db45f;
                border: 1px solid #2db45f;
                color: white;
            }
            QTabBar::tab:hover {
                background: rgba(45,180,95,0.12);
            }
        """)
        self.tabs.addTab(QWidget(), "Добавление" if self.lang == "ru" else "Additions")
        self.tabs.addTab(QWidget(), "Исключения" if self.lang == "ru" else "Excludes")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.tabs.setFixedHeight(self.tabs.tabBar().sizeHint().height() + 4)

        self.add_btn = QToolButton()
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setAutoRaise(True)
        self.add_btn.setFixedSize(34, 30)
        self.add_btn.setToolTip("Добавить сайт" if self.lang == "ru" else "Add site")
        self.add_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileDialogNewFolder))
        self.add_btn.setIconSize(QSize(16, 16))
        self.add_btn.setStyleSheet("""
            QToolButton {
                border: none;
                border-radius: 6px;
                background: transparent;
                color: #2db45f;
            }
            QToolButton:hover { background: rgba(45,180,95,0.10); }
            QToolButton:pressed { background: rgba(45,180,95,0.20); }
        """)
        self.add_btn.clicked.connect(self.add_site)

        tabs_row.addWidget(self.tabs, 1)
        tabs_row.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(tabs_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск..." if self.lang == "ru" else "Search...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(28)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid rgba(120,120,120,70);
                border-radius: 8px;
                padding: 6px 10px;
                background: rgba(255,255,255,0.02);
            }
            QLineEdit:focus {
                border: 1px solid rgba(45,180,95,0.70);
            }
        """)
        self.search_input.textChanged.connect(self.filter_list)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(6)
        search_row.addWidget(self.search_input, 1)

        self.delete_btn = QToolButton()
        self.delete_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setFixedSize(34, 34)
        self.delete_btn.setToolTip("Удалить отмеченные" if self.lang == "ru" else "Delete checked")
        self.delete_btn.setStyleSheet("""
            QToolButton {
                border: 1px solid rgba(200,60,60,0.45);
                border-radius: 8px;
                background: rgba(200,60,60,0.08);
            }
            QToolButton:hover { background: rgba(200,60,60,0.18); }
            QToolButton:pressed { background: rgba(200,60,60,0.28); }
        """)
        self.delete_btn.clicked.connect(self.delete_selected_multiple)
        self.delete_btn.hide()
        search_row.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(search_row)

        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(6)

        self.list_info_lbl = QLabel()
        self.list_info_lbl.setWordWrap(True)
        self.list_info_lbl.setStyleSheet("color: rgba(180,180,180,0.95);")
        info_row.addWidget(self.list_info_lbl, 1)

        self.tutorial_btn = SiteManagerTutorButton(self)
        self.tutorial_btn.setToolTip(
            "Обучение по менеджеру сайтов"
            if self.lang == "ru" else
            "Site manager guide"
        )
        self.tutorial_btn.clicked.connect(self.open_tutorial)
        info_row.addWidget(self.tutorial_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        root.addLayout(info_row)

        self.tabs.currentChanged.connect(self.on_mode_changed)
        self.tabs.tabBarClicked.connect(self._on_tab_clicked)

        list_wrap = QWidget(self)
        list_wrap_layout = QVBoxLayout(list_wrap)
        list_wrap_layout.setContentsMargins(0, 0, 0, 0)
        list_wrap_layout.setSpacing(0)

        self.sites_list = QListWidget()
        self.sites_list.setItemDelegate(self.SiteListDelegate(self))
        self.sites_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.sites_list.setMouseTracking(True)
        self.sites_list.viewport().setMouseTracking(True)
        self.sites_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sites_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.sites_list.setStyleSheet("""
            QListWidget {
                border: 1px solid rgba(120,120,120,70);
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 30px 6px 8px;
                border-radius: 6px;
            }
            QListWidget::item:selected { background: transparent; }
            QListWidget::item:hover { background: rgba(120,120,120,0.08); }
        """)
        self.sites_list.itemChanged.connect(self.update_delete_buttons)
        self.sites_list.viewport().installEventFilter(self)
        list_wrap_layout.addWidget(self.sites_list)

        root.addWidget(list_wrap, 1)
        self._update_list_info()
        self.update_delete_buttons()
        self._init_tab_attention()
        self._apply_tutorial_button_state()

    def eventFilter(self, obj, event):
        if obj is self.sites_list.viewport():
            if event.type() == QEvent.Type.MouseMove:
                item = self.sites_list.itemAt(event.pos())
                cursor = Qt.CursorShape.ArrowCursor
                if item is not None:
                    item_rect = self.sites_list.visualItemRect(item)
                    if self._visit_icon_rect(item_rect).contains(event.position()):
                        cursor = Qt.CursorShape.PointingHandCursor
                self.sites_list.viewport().setCursor(cursor)
            if event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.Paint,
            ):
                QTimer.singleShot(0, self.update_delete_buttons)
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                item = self.sites_list.itemAt(event.pos())
                if item is not None:
                    item_rect = self.sites_list.visualItemRect(item)
                    if self._visit_icon_rect(item_rect).contains(event.position()):
                        self.open_site_in_browser(item)
                        return True
                    item.setCheckState(
                        Qt.CheckState.Unchecked
                        if item.checkState() == Qt.CheckState.Checked else
                        Qt.CheckState.Checked
                    )
                    return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.update_delete_buttons)

    def _build_folder_action_icon(self, badge_color: str, positive: bool) -> QIcon:
        base_icon = self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        base_pm = base_icon.pixmap(18, 18)
        if base_pm.isNull():
            base_pm = QPixmap(18, 18)
            base_pm.fill(Qt.GlobalColor.transparent)

        pm = QPixmap(base_pm)
        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        circle_rect = QRectF(pm.width() - 9.5, pm.height() - 9.5, 8.0, 8.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(badge_color))
        painter.drawEllipse(circle_rect)

        line_pen = QPen(QColor("white"))
        line_pen.setWidth(2)
        line_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(line_pen)

        cx = circle_rect.center().x()
        cy = circle_rect.center().y()
        painter.drawLine(QPoint(int(cx - 2), int(cy)), QPoint(int(cx + 2), int(cy)))
        if positive:
            painter.drawLine(QPoint(int(cx), int(cy - 2)), QPoint(int(cx), int(cy + 2)))

        painter.end()
        return QIcon(pm)

    def _selected_file_path(self) -> str:
        index = self.tabs.currentIndex()
        if index == 0:
            return USER_GENERAL_FILE
        if index == 1:
            return USER_EXCLUDE_FILE
        return None

    def _update_list_info(self) -> None:
        selected_path = self._selected_file_path()
        if selected_path is None:
            self.list_info_lbl.setText(
                "Выберите вкладку выше, чтобы показать список."
                if self.lang == "ru" else
                "Choose a tab above to show the list."
            )
        elif selected_path == USER_GENERAL_FILE:
            self.list_info_lbl.setText(
                "Добавляется к основному списку обхода."
                if self.lang == "ru" else
                "Appended to the main bypass list."
            )
        else:
            self.list_info_lbl.setText(
                "Добавляется к списку исключений."
                if self.lang == "ru" else
                "Appended to the exclude list."
            )

    def on_mode_changed(self, _=0):
        if not hasattr(self, "sites_list"):
            return
        index = self.tabs.currentIndex()
        if index < 0:
            self.current_file = None
            self.sites_list.clear()
            self._update_list_info()
            self.update_delete_buttons()
            return

        if not self._mode_activated:
            self._mode_activated = True
            self._stop_tab_attention()
            self._sync_tabbar_mode_state()

        self.current_file = self._selected_file_path()
        self.reload_current_file()
        if 0 <= index < len(self.lazy_loaded):
            self.lazy_loaded[index] = True

    def reload_current_file(self):
        self.current_file = self._selected_file_path()
        self.sites_list.clear()
        self._update_list_info()
        if not self.current_file:
            self.update_delete_buttons()
            return

        for site in _read_lines_utf8(self.current_file):
            item = QListWidgetItem(site)
            item.setData(Qt.ItemDataRole.UserRole, site)
            item.setFlags(
                item.flags() |
                Qt.ItemFlag.ItemIsUserCheckable |
                Qt.ItemFlag.ItemIsEnabled
            )
            item.setCheckState(Qt.CheckState.Unchecked)
            self.sites_list.addItem(item)

        self.filter_list(self.search_input.text())
        self.update_delete_buttons()

    def open_user_folder(self):
        try:
            os.startfile(USER_DIR)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка" if self.lang == "ru" else "Error", str(e))

    def import_add_file(self) -> None:
        self.import_domains_from_file(USER_GENERAL_FILE)

    def import_exclude_file(self) -> None:
        self.import_domains_from_file(USER_EXCLUDE_FILE)

    def import_domains_from_file(self, target_file: str) -> None:
        title = "Импорт доменов" if self.lang == "ru" else "Import domains"
        file_filter = (
            "Поддерживаемые файлы (*.txt *.lst *.list *.json *.csv);;"
            "Текстовые файлы (*.txt *.lst *.list);;"
            "JSON (*.json);;"
            "CSV (*.csv)"
            if self.lang == "ru" else
            "Supported files (*.txt *.lst *.list *.json *.csv);;"
            "Text files (*.txt *.lst *.list);;"
            "JSON (*.json);;"
            "CSV (*.csv)"
        )
        source_path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if not source_path:
            return

        raw_text = _read_text(source_path)
        candidates = _extract_domain_candidates_from_file(source_path, raw_text)

        imported_domains = []
        for value in candidates:
            site = _normalize_domain_candidate(value)
            if not _is_valid_domain_like(site):
                continue
            imported_domains.append(site)

        if not imported_domains:
            QMessageBox.warning(
                self,
                "Ошибка" if self.lang == "ru" else "Error",
                "В файле не найдено валидных доменов."
                if self.lang == "ru" else
                "No valid domains were found in the file."
            )
            return

        existing = _read_lines_utf8(target_file)
        before = {x.strip().casefold() for x in existing if x.strip()}
        merged = _merge_unique(existing, imported_domains)
        after = {x.strip().casefold() for x in merged if x.strip()}
        added_count = len(after - before)
        _write_lines_utf8(target_file, merged)

        target_index = 0 if target_file == USER_GENERAL_FILE else 1
        self.lazy_loaded[target_index] = True
        if target_file == self._selected_file_path():
            self.reload_current_file()
        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        QMessageBox.information(
            self,
            "Импорт завершён" if self.lang == "ru" else "Import completed",
            (
                f"Добавлено доменов: {added_count}"
                if self.lang == "ru" else
                f"Domains added: {added_count}"
            )
        )

    def add_site(self):
        if self.tabs.currentIndex() < 0:
            self.tabs.setCurrentIndex(0)
        title = "Добавить сайт" if self.lang == "ru" else "Add site"
        label = "Введите домен или сайт:" if self.lang == "ru" else "Enter domain or site:"

        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue("")
        dlg.setOkButtonText("OK")
        dlg.setCancelButtonText("Отмена" if self.lang == "ru" else "Cancel")
        dlg.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        site = _normalize_domain_candidate(dlg.textValue())

        if not _is_valid_domain_like(site):
            QMessageBox.warning(
                self,
                "Ошибка" if self.lang == "ru" else "Error",
                "Некорректный домен." if self.lang == "ru" else "Invalid domain."
            )
            return

        lines = _read_lines_utf8(self.current_file)
        lines = _merge_unique(lines, [site])
        _write_lines_utf8(self.current_file, lines)
        self.lazy_loaded[self.tabs.currentIndex()] = True

        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        self.reload_current_file()

    def _confirm_delete(self, count: int) -> bool:
        title = "Удаление" if self.lang == "ru" else "Delete"
        text = (
            f"Удалить выбранные записи ({count})?"
            if count > 1 and self.lang == "ru" else
            "Удалить выбранную запись?"
            if self.lang == "ru" else
            f"Delete selected entries ({count})?"
            if count > 1 else
            "Delete selected entry?"
        )
        return QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

    def filter_list(self, text):
        text = (text or "").strip().lower()
        for row in range(self.sites_list.count()):
            item = self.sites_list.item(row)
            item.setHidden(text not in item.text().lower())

    def _visit_icon_rect(self, item_rect) -> QRectF:
        size = 18
        margin_right = 8
        x = item_rect.right() - size - margin_right
        y = item_rect.center().y() - size / 2
        return QRectF(x, y, size, size)

    def open_site_in_browser(self, item: QListWidgetItem) -> None:
        site = str(item.data(Qt.ItemDataRole.UserRole) or item.text()).strip()
        if not site:
            return
        url = site if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", site) else f"https://{site}"
        QDesktopServices.openUrl(QUrl(url))

    def _on_tab_clicked(self, index: int) -> None:
        if not self._mode_activated and self.tabs.currentIndex() == index:
            self._mode_activated = True
            self._stop_tab_attention()
            self._sync_tabbar_mode_state()
            self.current_file = USER_GENERAL_FILE if index == 0 else USER_EXCLUDE_FILE
            self.reload_current_file()
            if 0 <= index < len(self.lazy_loaded):
                self.lazy_loaded[index] = True
            return
        self.tabs.setCurrentIndex(index)

    def _init_tab_attention(self) -> None:
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(-1)
        self.tabs.blockSignals(False)
        self.tabs.tabBar().setCurrentIndex(-1)
        if hasattr(self, "sites_list"):
            self.sites_list.clear()
        self._update_list_info()
        self._sync_tabbar_mode_state()
        self._tab_attention_anim = QVariantAnimation(self)
        self._tab_attention_anim.setDuration(900)
        self._tab_attention_anim.setStartValue(30)
        self._tab_attention_anim.setKeyValueAt(0.5, 220)
        self._tab_attention_anim.setEndValue(30)
        self._tab_attention_anim.setLoopCount(-1)
        self._tab_attention_anim.valueChanged.connect(self._update_tab_attention)
        self._tab_attention_anim.start()
        self._update_tab_attention(self._tab_attention_anim.startValue())

    def _update_tab_attention(self, value) -> None:
        if self._mode_activated:
            return
        tab_bar = self.tabs.tabBar()
        if hasattr(tab_bar, "set_attention_state"):
            tab_bar.set_attention_state(int(value))

    def _stop_tab_attention(self) -> None:
        if hasattr(self, "_tab_attention_anim") and self._tab_attention_anim is not None:
            self._tab_attention_anim.stop()
        tab_bar = self.tabs.tabBar()
        if hasattr(tab_bar, "clear_attention"):
            tab_bar.clear_attention()

    def _sync_tabbar_mode_state(self) -> None:
        tab_bar = self.tabs.tabBar()
        tab_bar.setProperty("modeActivated", self._mode_activated)
        tab_bar.style().unpolish(tab_bar)
        tab_bar.style().polish(tab_bar)
        tab_bar.update()

    def _is_tutorial_hidden(self) -> bool:
        return bool(self.settings.value(self.TUTORIAL_HIDE_KEY, False, type=bool)) if self.settings else False

    def _is_tutorial_seen(self) -> bool:
        return bool(self.settings.value(self.TUTORIAL_SEEN_KEY, False, type=bool)) if self.settings else False

    def _apply_tutorial_button_state(self) -> None:
        if not hasattr(self, "tutorial_btn"):
            return
        if self._is_tutorial_hidden():
            self.tutorial_btn.hide()
            self.tutorial_btn.stop_pulse()
            return

        self.tutorial_btn.show()
        if self._is_tutorial_seen():
            self.tutorial_btn.stop_pulse()
        else:
            self.tutorial_btn.start_pulse()

    def _tutorial_start_pos(self, dialog: QDialog, gap: int = 8) -> QPoint:
        geom = self.frameGeometry()
        x = geom.left() - dialog.width() - 26
        y = geom.top()
        return QPoint(int(x), int(y))

    def _tutorial_target_pos(self, dialog: QDialog, gap: int = 8) -> QPoint:
        geom = self.frameGeometry()
        x = geom.left() - gap - dialog.width()
        y = geom.top()
        return QPoint(int(x), int(y))

    def open_tutorial(self) -> None:
        if self._tutorial_dialog is not None and self._tutorial_dialog.isVisible():
            self._tutorial_dialog.raise_()
            self._tutorial_dialog.activateWindow()
            return

        dialog = SiteManagerTutorialDialog(self, self.lang)
        self._tutorial_dialog = dialog

        def _after_close(_=0):
            dont_show = True
            try:
                dont_show = bool(dialog.dont_show_cb.isChecked())
            except Exception:
                pass

            if self.settings:
                self.settings.setValue(self.TUTORIAL_SEEN_KEY, True)
                self.settings.setValue(self.TUTORIAL_HIDE_KEY, dont_show)

            self._tutorial_dialog = None
            self._apply_tutorial_button_state()

        dialog.finished.connect(_after_close)
        dialog.show()

        start_pos = self._tutorial_start_pos(dialog)
        end_pos = self._tutorial_target_pos(dialog)
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
        dialog._open_anim_grp = grp
        dialog._open_anim_pos = pos_anim
        dialog._open_anim_op = op_anim
        grp.start()

    def _checked_items(self):
        return [
            item for item in self.sites_list.findItems("", Qt.MatchFlag.MatchContains)
            if item.checkState() == Qt.CheckState.Checked
        ]

    def delete_selected_multiple(self):
        items = self._checked_items()
        if not items:
            return
        if not self._confirm_delete(len(items)):
            return

        selected = {str((it.data(Qt.ItemDataRole.UserRole) or it.text())).strip().casefold() for it in items}
        lines = [x for x in _read_lines_utf8(self.current_file) if x.strip().casefold() not in selected]
        _write_lines_utf8(self.current_file, lines)
        self.lazy_loaded[self.tabs.currentIndex()] = True

        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        self.reload_current_file()

    def update_delete_buttons(self):
        if self._checked_items():
            self.delete_btn.show()
        else:
            self.delete_btn.hide()

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
        self.core_lists_dir = os.path.join(self.core_dir, "lists")
        self.user_lists_dir = USER_DIR

        self.presets = {}
        self.process = None
        self._auto_cancelled = False
        self._auto_done = 0
        self._auto_total = 0
        self._eta_ms_per_profile = None
        self._eta_last_done = 0
        self._eta_last_elapsed_ms = 0

        self._lists_check_in_progress = False
        self._lists_worker = None
        self._pending_autostart = False
        self._pending_autostart_profile = " "
        self._site_manager_dlg = None
        self._instruction_dialog = None

        self.tray = None
        self.tray_menu = None
        self.action_open = None
        self.action_start = None
        self.action_stop = None
        self.sites_menu = None
        self.action_sites_open = None
        self.action_sites_add = None
        self.action_sites_exclude = None
        self.preset_menu = None
        self.exit_action = None

        _ensure_user_lists_initialized()
        _rebuild_runtime_lists(self.settings)

        self.init_ui()
        self.retranslate_ui()

        if hasattr(self, "_update_autotest_info_button"):
            try:
                self._update_autotest_info_button()
            except Exception:
                pass

        self.set_autostart(self.autostart)
        self.init_tray_icon()

        if self.minimized:
            self.hide()
        else:
            self.show()

        autostart_profile = settings.value('autostart_profile', ' ')
        autostart_enabled = settings.value('autostart_profile_enabled', False, type=bool)

        if self.autostart and autostart_enabled and autostart_profile in self.presets:
            self._pending_autostart = True
            self._pending_autostart_profile = autostart_profile

        QTimer.singleShot(0, self.start_lists_sync)

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
        self.sites_menu = QMenu(self.t('Sites'), self)
        self.action_sites_open = QAction(self.t('Open'), self)
        self.action_sites_open.triggered.connect(self.open_site_manager_from_tray)
        self.sites_menu.addAction(self.action_sites_open)
        self.action_sites_add = QAction(self.t('Add'), self)
        self.action_sites_add.triggered.connect(lambda: self.open_site_domain_input_from_tray(USER_GENERAL_FILE))
        self.sites_menu.addAction(self.action_sites_add)
        self.action_sites_exclude = QAction(self.t('Exclude'), self)
        self.action_sites_exclude.triggered.connect(lambda: self.open_site_domain_input_from_tray(USER_EXCLUDE_FILE))
        self.sites_menu.addAction(self.action_sites_exclude)
        self.tray_menu.addMenu(self.sites_menu)

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
        self.sites_menu.setTitle(self.t('Sites'))
        self.action_sites_open.setText(self.t('Open'))
        self.action_sites_add.setText(self.t('Add'))
        self.action_sites_exclude.setText(self.t('Exclude'))
        self.preset_menu.setTitle(self.t('Select profile'))
        self.exit_action.setText(self.t('Exit'))
        self.tray_btn.setToolTip(self.t('Minimize to tray'))

    def update_tray_status(self):
        if self.tray is None or self.action_start is None or self.action_stop is None:
            return

        running = self.toggle_btn.isChecked()
        busy = bool(getattr(self, "_lists_check_in_progress", False))

        self.action_start.setEnabled((not running) and (not busy))
        self.action_stop.setEnabled(running)

        try:
            self.tray.setIcon(QIcon(self._tray_icon_path(running)))
        except Exception:
            pass
        self.tray.setToolTip(self.get_tray_tooltip())

        self.update_tray_presets()

    def _set_lists_sync_ui_busy(self, busy: bool):
        self._lists_check_in_progress = bool(busy)

        try:
            self.toggle_btn.setEnabled(not busy)
        except Exception:
            pass

        try:
            self.auto_btn.setEnabled(not busy)
        except Exception:
            pass

        try:
            self.cb.setEnabled(not busy)
        except Exception:
            pass

        if busy:
            self.status_lbl.setText(
                "Проверка списков..." if self.lang == "ru" else "Checking lists..."
            )
        else:
            self.retranslate_ui()

        self.update_tray_status()

    def _show_lists_sync_network_notice(self):
        title = "Обновление списков" if self.lang == "ru" else "Lists update"
        text = (
            "Ваш интернет нестабилен, проверьте соединение.\n"
            "Обновление списков отменено до следующего запуска."
            if self.lang == "ru" else
            "Your internet connection looks unstable.\n"
            "List update was canceled until the next launch."
        )

        if self.isHidden() and self.tray is not None:
            try:
                self.tray.showMessage(
                    title,
                    text,
                    QSystemTrayIcon.MessageIcon.Warning,
                    5000
                )
                return
            except Exception:
                pass

        QMessageBox.warning(self, title, text)

    def _run_pending_autostart_if_needed(self):
        if not self._pending_autostart:
            return

        profile = self._pending_autostart_profile
        self._pending_autostart = False
        self._pending_autostart_profile = " "

        if profile in self.presets:
            self.cb.setCurrentText(profile)
            self.toggle_btn.setChecked(True)
            QTimer.singleShot(300, lambda: self.on_toggle(True))

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

        if result.get("offline"):
            self._show_lists_sync_network_notice()
        elif result.get("error"):
            print("Lists sync error:", result.get("error", ""))

        self._run_pending_autostart_if_needed()

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
            subprocess.run(
                ["taskkill", "/IM", "winws.exe", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
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

        dialog = QDialog(self)
        dialog.setWindowTitle(self.t('Instruction'))

        if self.lang == 'ru':
            dialog.setFixedSize(430, 470)
        else:
            dialog.setFixedSize(430, 390)

        dialog.setWindowFlags(dialog.windowFlags() & ~Qt.WindowType.WindowMaximizeButtonHint)
        dialog.setModal(False)

        layout = QVBoxLayout(dialog)

        lists_dir = USER_DIR
        lists_url = lists_dir.replace("\\", "/")
        instruction_html = self.t('Instruction Text', lists_url, lists_dir)

        browser = QTextBrowser(dialog)
        browser.setHtml(
            f"<html><body style='font-family:Segoe UI; font-size:10.5pt'>{instruction_html}</body></html>"
        )
        browser.setOpenExternalLinks(False)
        browser.anchorClicked.connect(self._handle_instruction_link)
        browser.setStyleSheet("border: none; background: transparent;")
        layout.addWidget(browser)

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
        self.setFixedSize(300, 360)
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

        self.auto_info_btn = QToolButton()
        self.auto_info_btn.setFixedSize(36, 36)
        self.auto_info_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.auto_info_btn.setToolTip("Результаты последнего автоподбора")
        info_icon_path = os.path.join(os.path.dirname(__file__), 'flags', 'info.ico')
        info_icon = QIcon(info_icon_path) if os.path.exists(info_icon_path) else self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxInformation)
        self.auto_info_btn.setIcon(info_icon)
        self.auto_info_btn.setIconSize(QSize(21, 21))
        self.auto_info_btn.setAutoRaise(True)
        self.auto_info_btn.setFixedSize(24, 24)
        self.auto_info_btn.setStyleSheet("""
            QToolButton {
                border: none;
                background: transparent;
                padding: 0px;
                margin: 0px;
            }
            QToolButton:hover { background: transparent; }
            QToolButton:pressed { background: transparent; }
        """)
        self.auto_info_btn.clicked.connect(self.show_autotest_info)
        self.auto_info_btn.hide()

        self.tray_btn = QPushButton()
        self.tray_btn.setIcon(QIcon(os.path.join(os.path.dirname(__file__), 'flags', 'tray.ico')))
        self.tray_btn.setIconSize(QSize(24, 24))
        self.tray_btn.setToolTip(self.t('Minimize to tray'))
        self.tray_btn.setFixedSize(28, 28)
        self.tray_btn.setStyleSheet("border: none;")
        self.tray_btn.clicked.connect(self.hide)

        top_row = QHBoxLayout()
        left_row = QHBoxLayout()
        left_row.setSpacing(4)
        left_row.setAlignment(Qt.AlignmentFlag.AlignBottom)
        left_row.addWidget(self.auto_btn, 0, Qt.AlignmentFlag.AlignBottom)
        left_row.addWidget(self.auto_info_btn, 0, Qt.AlignmentFlag.AlignBottom)
        left_row.setContentsMargins(0, 0, 0, 0)

        top_row.addLayout(left_row)
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

        self.site_manager_btn = QPushButton("Менеджер сайтов" if self.lang == "ru" else "Site manager")
        self.site_manager_btn.setFixedHeight(30)
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
        layout.addWidget(self.powered_lbl)

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
        self.site_manager_btn.setText("Менеджер сайтов" if self.lang == "ru" else "Site manager")

    def update_blink(self):
        return

    def _update_autotest_info_button(self):
        data = _load_autotest_result()
        has_data = bool(data.get("best") or data.get("good") or data.get("bad"))
        if hasattr(self, "auto_info_btn"):
            self.auto_info_btn.setVisible(has_data)

    def show_autotest_info(self):
        data = _load_autotest_result()
        if not data:
            return

        best = data.get("best", "")
        good = data.get("good", []) or []
        bad = data.get("bad", []) or []
        updated_at = data.get("updated_at", "")

        if self.lang == "ru":
            best_line = f"<b>Самый лучший для Вас профиль:</b> {best}" if best else "<b>Самый лучший для Вас профиль:</b> не найден"
            good_line = "<b>Профили, которые также будут работать:</b><br>" + ("<br>".join(good) if good else "—")
            bad_line = "<b>Профили, которые у Вас не сработают:</b><br>" + ("<br>".join(bad) if bad else "—")
            updated_line = f"<br><br><span style='color:gray;'>Обновлено: {updated_at}</span>" if updated_at else ""
            title = "Результаты автоподбора"
        else:
            best_line = f"<b>Best profile for you:</b> {best}" if best else "<b>Best profile for you:</b> not found"
            good_line = "<b>Profiles that should work:</b><br>" + ("<br>".join(good) if good else "—")
            bad_line = "<b>Profiles that won't work:</b><br>" + ("<br>".join(bad) if bad else "—")
            updated_line = f"<br><br><span style='color:gray;'>Updated: {updated_at}</span>" if updated_at else ""
            title = "Auto selection results"

        html = (
            "<div style='font-family:Segoe UI; font-size:10.5pt'>"
            f"{best_line}<br><br>{good_line}<br><br>{bad_line}{updated_line}"
            "</div>"
        )

        dlg = QMessageBox(self)
        dlg.setWindowTitle(title)
        dlg.setIcon(QMessageBox.Icon.NoIcon)
        dlg.setTextFormat(Qt.TextFormat.RichText)
        dlg.setText(html)
        dlg.exec()

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
        if checked and getattr(self, "_lists_check_in_progress", False):
            self.toggle_btn.setChecked(False)
            self.update_tray_status()
            return

        profile = self.cb.currentText()
        self.settings.setValue("last_profile", profile)

        script = os.path.join(self.core_dir, self.presets[profile])
        if not os.path.exists(script):
            QMessageBox.warning(self, "Ошибка", f"Не найден файл:\n{script}")
            self.toggle_btn.setChecked(False)
            self.update_tray_status()
            return

        if checked:
            _ensure_user_lists_initialized()
            _rebuild_runtime_lists(self.settings)
            _force_stop_blockers()

            inp_path = _ensure_no_update_input()

            env = os.environ.copy()
            env["ZAPRETGUI_NOUPDATE"] = "1"
            env["NO_UPDATE_CHECK"] = "1"

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
                    si.wShowWindow = 0
            except Exception:
                si = None

            flags = (
                    getattr(subprocess, "CREATE_NO_WINDOW", 0)
                    | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
            )

            try:
                self.process = subprocess.Popen(
                    ["cmd.exe", "/d", "/c", script],
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

        dlg.setWindowModality(Qt.WindowModality.ApplicationModal)

        self._settings_dlg = dlg

        start_pos = self._side_dialog_start_pos(dlg, side="right")
        dlg.move(start_pos)
        try:
            dlg.setWindowOpacity(0.0)
        except Exception:
            pass

        def _after_close(_=0):
            self.autostart = self.settings.value('autostart', False, type=bool)
            self.set_autostart(self.autostart)
            try:
                self._settings_dlg = None
            except Exception:
                pass

        dlg.finished.connect(_after_close)

        dlg.open()
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
        title = (
            "Добавить сайт" if target_file == USER_GENERAL_FILE and self.lang == "ru" else
            "Исключить сайт" if self.lang == "ru" else
            "Add site" if target_file == USER_GENERAL_FILE else
            "Exclude site"
        )
        label = (
            "Введите домен или сайт:" if self.lang == "ru" else
            "Enter domain or site:"
        )

        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(label)
        dlg.setTextValue("")
        dlg.setOkButtonText("OK")
        dlg.setCancelButtonText("Отмена" if self.lang == "ru" else "Cancel")
        dlg.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )
        dlg.setModal(True)
        dlg.show()
        self._center_dialog_on_screen(dlg)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        site = _normalize_domain_candidate(dlg.textValue())
        if not _is_valid_domain_like(site):
            QMessageBox.warning(
                self,
                "Ошибка" if self.lang == "ru" else "Error",
                "Некорректный домен." if self.lang == "ru" else "Invalid domain."
            )
            return

        lines = _read_lines_utf8(target_file)
        lines = _merge_unique(lines, [site])
        _write_lines_utf8(target_file, lines)
        _rebuild_runtime_lists(self.settings)

        if self._site_manager_dlg is not None and self._site_manager_dlg.isVisible():
            target_index = 0 if target_file == USER_GENERAL_FILE else 1
            self._site_manager_dlg.lazy_loaded[target_index] = True
            if self._site_manager_dlg.tabs.currentIndex() == target_index:
                self._site_manager_dlg.reload_current_file()

    def set_autostart(self, enable: bool):
        task_name = "ZapretGUI"
        exe = os.path.realpath(sys.argv[0])

        try:
            if enable:
                subprocess.run(
                    [
                        "schtasks", "/Create",
                        "/TN", task_name,
                        "/SC", "ONLOGON",
                        "/RL", "HIGHEST",
                        "/F",
                        "/TR", f'"{exe}"'
                    ],
                    check=True,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
            else:
                subprocess.run(
                    ["schtasks", "/Delete", "/TN", task_name, "/F"],
                    check=False,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)
                )
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
    if sys.platform.startswith("win"):
        try:
            DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
            ctypes.windll.user32.SetProcessDpiAwarenessContext(
                ctypes.c_void_p(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)
            )
        except Exception:
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except Exception:
                pass

    try:
        # Не даём Qt криво округлять scale factor на 125/150/175/200%
        QApplication.setHighDpiScaleFactorRoundingPolicy(
            Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
        )
    except Exception:
        pass

    try:
        QApplication.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    app = QApplication(sys.argv)
    wipe_app_dir_if_new_version()
    extract_files_from_meipass()
    unblock_core_tree(os.path.join(APP_DIR, "core"))
    create_delete_bat()
    settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
    _patch_profiles_if_core_outdated(os.path.join(APP_DIR, "core"), settings)
    _patch_profiles_hide_windows(os.path.join(APP_DIR, "core"))
    _ensure_user_lists_initialized()
    _rebuild_runtime_lists(settings)
    win = MainWindow(settings)
    icon_path = os.path.join(APP_DIR, 'flags', 'z.ico')
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    exit_code = app.exec()
    sys.exit(exit_code)

if __name__ == '__main__':
    main()
