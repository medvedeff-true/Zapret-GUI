import sys
import os
import subprocess
import csv
import ipaddress
import base64
import math
import tempfile
from PyQt6.QtCore import (
    Qt, QSettings, QSize, QTimer, QThread, pyqtSignal,
    QElapsedTimer, QEvent, QEasingCurve, QPropertyAnimation, pyqtProperty,
    QParallelAnimationGroup, QPoint, QRectF, QUrl, QVariantAnimation
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage, QAction, QPalette, QPainter, QColor, QPen, QBrush,
    QLinearGradient, QDesktopServices, QGuiApplication, QPainterPath, QRegion
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QCheckBox, QMessageBox, QSizePolicy,
    QSystemTrayIcon, QMenu, QTextBrowser, QProgressDialog, QGraphicsDropShadowEffect,
    QListWidget, QListWidgetItem, QListView, QTabWidget, QToolButton, QFileDialog, QLineEdit,
    QAbstractItemView, QStyle, QStyledItemDelegate, QTabBar, QFrame
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
from urllib.parse import urlsplit
from telegram_proxy import TelegramProxyController

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
            encoding="utf-8",
            errors="ignore",
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


APP_VERSION = "2.1.0"
APP_DIR = os.path.join(os.path.expanduser('~'), 'ZapretGUI')
os.makedirs(APP_DIR, exist_ok=True)

USER_DIR = os.path.join(APP_DIR, "user")
os.makedirs(USER_DIR, exist_ok=True)
USER_STRATEGY_BACKUP_DIR = os.path.join(USER_DIR, "strategy-backups")

FLOWSEAL_REPO = "Flowseal/zapret-discord-youtube"
FLOWSEAL_DEFAULT_VER = "1.9.7b"
FLOWSEAL_VER_KEY = "flowseal_release"
FLOWSEAL_VERSION_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt"

FLOWSEAL_LIST_BASE_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/lists/"
FLOWSEAL_LIST_FILES = (
    "ipset-all.txt",
    "ipset-exclude.txt",
    "list-exclude.txt",
    "list-general.txt",
    "list-google.txt",
)

GAMING_LISTS_REPO = "medvedeff-true/ru-gaming-blocklist"
GAMING_LISTS_API_URL = f"https://api.github.com/repos/{GAMING_LISTS_REPO}/contents/"
GUI_REPO = "medvedeff-true/Zapret-GUI"
GUI_RELEASES_URL = f"https://github.com/{GUI_REPO}/releases"
GUI_SKIPPED_UPDATE_KEY = "gui_update/skipped_version"
GAME_MODE_KEY = "game_mode_enabled"
GAME_MODE_MAIN_BYPASS_KEY = "game_mode/main_bypass_enabled"
GAME_MODE_USER_LISTS_KEY = "game_mode/user_lists_enabled"
GAME_MODE_DISCORD_KEY = "game_mode/discord_enabled"
GAME_LIST_DOMAIN_SHA_KEY = "gaming_lists/domain_remote_sha"
GAME_LIST_DOMAIN_HASH_KEY = "gaming_lists/domain_local_sha256"
GAME_LIST_IP_SHA_KEY = "gaming_lists/ip_remote_sha"
GAME_LIST_IP_HASH_KEY = "gaming_lists/ip_local_sha256"
GAME_FILTER_FLAG_MODE = "all"
TELEGRAM_MODE_ENABLED_KEY = "telegram_mode/enabled"
TELEGRAM_MODE_PROXY_ENABLED_KEY = "telegram_mode/proxy_enabled"
TELEGRAM_MODE_PROXY_PORT_KEY = "telegram_mode/proxy_port"
TELEGRAM_MODE_LAST_ERROR_KEY = "telegram_mode/last_error"
TELEGRAM_MODE_FIRST_PROXY_HINT_SHOWN_KEY = "telegram_mode/first_proxy_hint_shown"

SETTINGS_FILE = os.path.join(APP_DIR, 'settings.ini')
VERSION_FILE = os.path.join(APP_DIR, '.app_version')
AUTOLOG_FILE = os.path.join(APP_DIR, "autotest_last.log")
AUTORESULT_FILE = os.path.join(APP_DIR, "autotest_result.json")

REMOVE_BAT = os.path.join(APP_DIR, "uninstall.bat")

NOUPDATE_INP = os.path.join(APP_DIR, "_no_update_input.txt")

USER_GENERAL_FILE = os.path.join(USER_DIR, "list-general-user.txt")
USER_EXCLUDE_FILE = os.path.join(USER_DIR, "list-exclude-user.txt")
USER_IP_ALL_FILE = os.path.join(USER_DIR, "ipset-all-user.txt")
USER_IP_EXCLUDE_FILE = os.path.join(USER_DIR, "ipset-exclude-user.txt")
USER_GAME_DOMAIN_FILE = os.path.join(USER_DIR, "medvedeff-game-list-all.txt")
USER_GAME_IP_FILE = os.path.join(USER_DIR, "medvedeff-game-ipset.txt")
USER_TELEGRAM_DOMAIN_FILE = os.path.join(USER_DIR, "telegram-domains.txt")
USER_TELEGRAM_IP_FILE = os.path.join(USER_DIR, "telegram-ipset.txt")
FLOWSEAL_SOURCE_PREFIX = "flowseal-source-"
CORE_STRATEGY_RESERVED_BAT_NAMES = {
    "service.bat",
    "cloudflare_switch.bat",
    "discord.bat",
}

RUNTIME_GENERAL_FILE = os.path.join(APP_DIR, "core", "lists", "list-general.txt")
RUNTIME_EXCLUDE_FILE = os.path.join(APP_DIR, "core", "lists", "list-exclude.txt")
RUNTIME_IP_ALL_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-all.txt")
RUNTIME_IP_EXCLUDE_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-exclude.txt")
RUNTIME_GOOGLE_FILE = os.path.join(APP_DIR, "core", "lists", "list-google.txt")
RUNTIME_DISCORD_FILE = os.path.join(APP_DIR, "core", "lists", "list-discord.txt")
RUNTIME_GENERAL_USER_FILE = os.path.join(APP_DIR, "core", "lists", "list-general-user.txt")
RUNTIME_EXCLUDE_USER_FILE = os.path.join(APP_DIR, "core", "lists", "list-exclude-user.txt")
RUNTIME_IP_ALL_USER_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-all-user.txt")
RUNTIME_IP_EXCLUDE_USER_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-exclude-user.txt")
RUNTIME_TELEGRAM_DOMAIN_FILE = os.path.join(APP_DIR, "core", "lists", "telegram-domains.txt")
RUNTIME_TELEGRAM_IP_FILE = os.path.join(APP_DIR, "core", "lists", "telegram-ipset.txt")
GAME_FILTER_FLAG_FILE = os.path.join(APP_DIR, "core", "utils", "game_filter.enabled")
USER_LIST_SEEDED_BACKUP_SUFFIX = ".seeded-backup"
USER_LIST_SEEDED_OVERLAP_RATIO = 0.60
PLACEHOLDER_ITEM_ROLE = int(Qt.ItemDataRole.UserRole) + 1

EMPTY_USER_LIST_PLACEHOLDERS = {
    USER_GENERAL_FILE: ["example.com"],
    USER_EXCLUDE_FILE: ["example.org"],
    USER_IP_ALL_FILE: ["203.0.113.10"],
    USER_IP_EXCLUDE_FILE: ["203.0.113.11"],
}

USER_LIST_FILE_MAP = {
    ("domain", "add"): USER_GENERAL_FILE,
    ("domain", "exclude"): USER_EXCLUDE_FILE,
    ("ip", "add"): USER_IP_ALL_FILE,
    ("ip", "exclude"): USER_IP_EXCLUDE_FILE,
}

GAMING_LIST_TARGETS = {
    "medvedeff-game-list-all.txt": {
        "path": USER_GAME_DOMAIN_FILE,
        "remote_sha_key": GAME_LIST_DOMAIN_SHA_KEY,
        "local_hash_key": GAME_LIST_DOMAIN_HASH_KEY,
    },
    "medvedeff-game-ipset.txt": {
        "path": USER_GAME_IP_FILE,
        "remote_sha_key": GAME_LIST_IP_SHA_KEY,
        "local_hash_key": GAME_LIST_IP_HASH_KEY,
    },
}

# Curated Telegram Web list. Keep it in sync with Telegram Web endpoint changes.
TELEGRAM_WEB_DOMAINS = (
    "web.telegram.org",
    "webk.telegram.org",
    "webz.telegram.org",
    "weba.telegram.org",
    "telegram.org",
    "t.me",
    "telegram.me",
    "telegram.dog",
    "kws1.web.telegram.org",
    "kws2.web.telegram.org",
    "kws3.web.telegram.org",
    "kws4.web.telegram.org",
    "kws5.web.telegram.org",
    "pluto.web.telegram.org",
    "venus.web.telegram.org",
    "aurora.web.telegram.org",
    "vesta.web.telegram.org",
    "flora.web.telegram.org",
    "pluto-1.web.telegram.org",
    "venus-1.web.telegram.org",
    "aurora-1.web.telegram.org",
    "vesta-1.web.telegram.org",
    "flora-1.web.telegram.org",
)

# Based on https://core.telegram.org/resources/cidr.txt. Update periodically.
TELEGRAM_IP_RANGES = (
    "91.108.56.0/22",
    "91.108.4.0/22",
    "91.108.8.0/22",
    "91.108.16.0/22",
    "91.108.12.0/22",
    "149.154.160.0/20",
    "91.105.192.0/23",
    "91.108.20.0/22",
    "185.76.151.0/24",
    "2001:b28:f23d::/48",
    "2001:b28:f23f::/48",
    "2001:67c:4e8::/48",
    "2001:b28:f23c::/48",
    "2a0a:f280::/32",
)

DNS_MALW_IPV4_SERVERS = (
    "84.21.189.133",
    "193.23.209.189",
)
DNS_MALW_IPV6_SERVERS = (
    "2a12:bec4:1460:294::2",
    "2a01:ecc0:680:120::2",
)
DNS_MALW_DOH_TEMPLATE = "https://dns.malw.link/dns-query"
DNS_MALW_LAST_ATTEMPT_KEY = "dns_malw_link/last_attempt"
DNS_MALW_LAST_SUCCESS_KEY = "dns_malw_link/last_success"
DNS_MALW_LAST_STATUS_KEY = "dns_malw_link/last_status"
DNS_MALW_LAST_ERROR_KEY = "dns_malw_link/last_error"
DNS_MALW_LAST_UPDATED_KEY = "dns_malw_link/last_updated"
DNS_MALW_LAST_DOH_KEY = "dns_malw_link/last_doh"
DNS_MALW_ENABLED_BY_APP_KEY = "dns_malw_link/enabled_by_app"
DNS_MALW_RESTORE_SNAPSHOT_KEY = "dns_malw_link/restore_snapshot"
DNS_MALW_HOSTS_URL = "https://raw.githubusercontent.com/ImMALWARE/dns.malw.link/master/hosts"
DNS_MALW_ADDITIONAL_URL = "https://raw.githubusercontent.com/AvenCores/Goida-AI-Unlocker/main/additional_hosts.py"
DNS_MALW_HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
DNS_MALW_HOSTS_BACKUP_PATH = os.path.join(APP_DIR, "dns_malw_hosts_backup.txt")
DNS_MALW_HOSTS_CACHE_PATH = os.path.join(APP_DIR, "dns_malw_hosts_cache.txt")
DNS_MALW_HOSTS_BLOCK_BEGIN = "# ZapretGUI Ai DNS BEGIN"
DNS_MALW_HOSTS_BLOCK_END = "# ZapretGUI Ai DNS END"
DNS_MALW_LEGACY_HOSTS_BLOCK_BEGIN = "### dns.malw.link: hosts file"
DNS_MALW_LEGACY_HOSTS_BLOCK_END = "### dns.malw.link: end hosts file"
DNS_MALW_LEGACY_ADDITIONAL_BLOCK_BEGIN = "# Goida-AI-Unlocker additional hosts"
DNS_MALW_ADDITIONAL_VERSION_RE = re.compile(r'version_add\s*=\s*["\\\']([^"\\\']+)["\\\']')
DNS_MALW_ADDITIONAL_HOSTS_RE = re.compile(
    r'hosts_add\s*=\s*(?:r|R)?(?P<quote>"""|\'\'\')(?P<body>.*?)(?P=quote)',
    re.S,
)
DNS_MALW_PROTECTED_HOSTS = {
    "api.github.com",
    "github.com",
    "www.github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "codeload.github.com",
}

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


def _apply_unified_qt_style(app: QApplication) -> None:
    try:
        app.setStyle("Fusion")
    except Exception:
        pass

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#171717"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c1c1c"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1f1f1f"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#202020"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f7f7f7"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2db45f"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(190, 190, 190, 180))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#989898"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#a1a1a1"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#a1a1a1"))
    try:
        app.setPalette(palette)
    except Exception:
        pass


def _available_geometry_for_widget(widget: QWidget | None = None):
    try:
        screen = widget.screen() if widget is not None and hasattr(widget, "screen") else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry()
    except Exception:
        pass
    return None


def _center_widget_on_screen(widget: QWidget, parent: QWidget | None = None) -> None:
    try:
        geom = _available_geometry_for_widget(parent if parent is not None else widget)
        if geom is None:
            return
        frame = widget.frameGeometry()
        frame.moveCenter(geom.center())
        widget.move(frame.topLeft())
    except Exception:
        pass


def _show_centered_message(
    parent: QWidget | None,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
) -> QMessageBox.StandardButton:
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStandardButtons(buttons)
    msg.adjustSize()
    _center_widget_on_screen(msg, parent)
    return msg.exec()


WINDOW_RADIUS = 12.0


def _rounded_window_path(rect: QRectF, radius: float = WINDOW_RADIUS) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    return path


def _update_rounded_window_mask(widget: QWidget, radius: float = WINDOW_RADIUS) -> None:
    try:
        if widget.width() <= 0 or widget.height() <= 0:
            return
        path = _rounded_window_path(QRectF(widget.rect()), radius)
        widget.setMask(QRegion(path.toFillPolygon().toPolygon()))
    except Exception:
        pass


def _make_window_root_layout(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return layout


def _make_window_content_layout(
    root_layout: QVBoxLayout,
    parent: QWidget,
    margins: tuple[int, int, int, int] = (12, 12, 12, 12),
    spacing: int = 8,
) -> QVBoxLayout:
    content = QWidget(parent)
    content.setObjectName("windowContent")
    content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    root_layout.addWidget(content, 1)
    return layout


def _paint_app_surface(painter: QPainter, rect: QRectF, accented: bool = False) -> None:
    path = _rounded_window_path(rect)
    bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0.00, QColor("#191b1b"))
    bg.setColorAt(0.46, QColor("#111313"))
    bg.setColorAt(1.00, QColor("#0c0e0e"))

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipPath(path)
    painter.fillPath(path, QBrush(bg))

    stripe_alpha = 15 if accented else 10
    stripe_step = 34 if accented else 42
    painter.setPen(QPen(QColor(255, 255, 255, stripe_alpha), 1.0))
    for x in range(-int(rect.height()), int(rect.width() + rect.height()), stripe_step):
        painter.drawLine(QPoint(x, int(rect.height())), QPoint(x + int(rect.height()), 0))

    painter.setPen(QPen(QColor(45, 180, 95, 22 if accented else 14), 1.0))
    for x in range(-int(rect.height()) + stripe_step // 2, int(rect.width() + rect.height()), stripe_step * 3):
        painter.drawLine(QPoint(x, int(rect.height())), QPoint(x + int(rect.height()), 0))

    edge = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
    edge.setColorAt(0.0, QColor(45, 180, 95, 0))
    edge.setColorAt(0.5, QColor(45, 180, 95, 34 if accented else 22))
    edge.setColorAt(1.0, QColor(45, 180, 95, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(edge))
    painter.drawRect(QRectF(rect.left(), rect.top(), rect.width(), 1.2))

    painter.setPen(QPen(QColor(255, 255, 255, 24 if accented else 18), 1.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()


def _app_dialog_stylesheet() -> str:
    return """
        QDialog {
            color: #f2f2f2;
            background: transparent;
        }
        QLabel {
            color: #f2f2f2;
        }
        QCheckBox {
            color: #f1f1f1;
            spacing: 7px;
        }
        QPushButton {
            min-height: 30px;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 8px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(44,50,50,235),
                stop:0.36 rgba(34,40,40,238),
                stop:0.72 rgba(24,30,29,238),
                stop:1 rgba(26,49,36,235));
            color: #f6fff8;
            font-weight: 600;
            padding: 0 10px;
        }
        QPushButton:hover {
            border-color: rgba(45,180,95,0.72);
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(54,64,61,240),
                stop:0.38 rgba(40,49,46,240),
                stop:0.74 rgba(29,39,35,240),
                stop:1 rgba(33,79,51,238));
        }
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(28,35,33,245),
                stop:1 rgba(38,96,58,242));
        }
        QPushButton:disabled {
            color: #929292;
            border-color: rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.035);
        }
        QToolButton {
            color: #f3f3f3;
        }
        QLineEdit, QTextBrowser, QListWidget {
            color: #f2f2f2;
            background: rgba(255,255,255,0.026);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 8px;
        }
    """


class CustomTitleBar(QWidget):
    def __init__(self, title: str = "", parent=None, allow_minimize: bool = True):
        super().__init__(parent)
        self._window = parent
        self._drag_pos = None
        self.setFixedHeight(30)
        self.setObjectName("customTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 0, 4, 0)
        layout.setSpacing(5)

        icon_lbl = QLabel(self)
        icon_lbl.setFixedSize(16, 16)
        icon_path = os.path.join(APP_DIR, "flags", "Z.ico")
        if not os.path.exists(icon_path):
            icon_path = os.path.join(os.path.dirname(__file__), "flags", "Z.ico")
        pm = QIcon(icon_path).pixmap(16, 16) if os.path.exists(icon_path) else QPixmap()
        icon_lbl.setPixmap(pm)
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QLabel(title, self)
        self.title_lbl.setObjectName("customTitleText")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.title_lbl, 1)

        self.min_btn = QPushButton("–", self)
        self.close_btn = QPushButton("×", self)
        for btn in (self.min_btn, self.close_btn):
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setObjectName("titleButton")

        self.close_btn.setObjectName("titleCloseButton")
        self.min_btn.clicked.connect(lambda: self.window().showMinimized())
        self.close_btn.clicked.connect(lambda: self.window().close())
        self.min_btn.setVisible(bool(allow_minimize))
        layout.addWidget(self.min_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setStyleSheet("""
            QWidget#customTitleBar {
                background: transparent;
                border-bottom: 1px solid rgba(255,255,255,0.07);
            }
            QLabel#customTitleText {
                color: rgba(245,245,245,0.96);
                font-size: 12px;
                font-weight: 650;
            }
            QPushButton#titleButton, QPushButton#titleCloseButton {
                border: none;
                border-radius: 6px;
                background: transparent;
                color: rgba(245,245,245,0.92);
                font-size: 15px;
                font-weight: 700;
                padding: 0;
                min-height: 0;
            }
            QPushButton#titleButton:hover {
                border-color: rgba(45,180,95,0.55);
                background: rgba(45,180,95,0.14);
            }
            QPushButton#titleCloseButton:hover {
                border-color: rgba(226,84,84,0.66);
                background: rgba(226,84,84,0.20);
            }
            QPushButton#titleButton:pressed, QPushButton#titleCloseButton:pressed {
                background: rgba(255,255,255,0.12);
            }
        """)

    def setTitle(self, title: str) -> None:
        self.title_lbl.setText(title or "")

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class StyledDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setStyleSheet(_app_dialog_stylesheet())
        self._title_bar = None

    def setWindowTitle(self, title: str) -> None:
        super().setWindowTitle(title)
        if getattr(self, "_title_bar", None) is not None:
            self._title_bar.setTitle(title)

    def install_title_bar(self, layout: QVBoxLayout, title: str | None = None, allow_minimize: bool = False) -> CustomTitleBar:
        self.setWindowFlags(
            (self.windowFlags() | Qt.WindowType.FramelessWindowHint)
            & ~Qt.WindowType.WindowTitleHint
        )
        if title is not None:
            self.setWindowTitle(title)
        if self._title_bar is None:
            self._title_bar = CustomTitleBar(self.windowTitle(), self, allow_minimize=allow_minimize)
            layout.insertWidget(0, self._title_bar)
        else:
            self._title_bar.setTitle(self.windowTitle())
        return self._title_bar

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_app_surface(painter, QRectF(self.rect()), accented=False)
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        _update_rounded_window_mask(self)


class TextInputDialog(StyledDialog):
    def __init__(
        self,
        title: str,
        label: str,
        ok_text: str = "OK",
        cancel_text: str = "Cancel",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(330, 150)

        root = _make_window_root_layout(self)
        self.install_title_bar(root, title, allow_minimize=False)
        layout = _make_window_content_layout(root, self, margins=(10, 8, 10, 10), spacing=7)

        self.label = QLabel(label, self)
        self.label.setWordWrap(False)
        layout.addWidget(self.label)

        self.line_edit = QLineEdit(self)
        self.line_edit.setMinimumHeight(30)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                padding: 0 10px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.13);
                background: rgba(255,255,255,0.045);
                color: #f5f5f5;
                selection-background-color: rgba(45,180,95,0.55);
            }
            QLineEdit:focus {
                border-color: rgba(45,180,95,0.72);
                background: rgba(255,255,255,0.060);
            }
        """)
        self.line_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.line_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton(cancel_text, self)
        self.ok_btn = QPushButton(ok_text, self)
        self.cancel_btn.setFixedHeight(28)
        self.ok_btn.setFixedHeight(28)
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

    def setTextValue(self, text: str) -> None:
        self.line_edit.setText(text or "")
        self.line_edit.selectAll()

    def textValue(self) -> str:
        return self.line_edit.text()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.line_edit.setFocus)

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
    try:
        with open(tmp_path, "wb") as f:
            f.write(data)
        os.replace(tmp_path, path)
        return
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass

    with open(path, "wb") as f:
        f.write(data)

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

    content = "\n".join(uniq) + ("\n" if uniq else "")
    tmp = path + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
        os.replace(tmp, path)
        return
    except Exception:
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass

    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


def _copy_if_missing(src: str, dst: str) -> None:
    try:
        if os.path.exists(src) and not os.path.exists(dst):
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            shutil.copy2(src, dst)
    except Exception:
        pass


def _bundled_root_dir() -> str:
    if hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return os.path.dirname(__file__)


def _bundled_path(*parts: str) -> str:
    return os.path.join(_bundled_root_dir(), *parts)


def _flowseal_source_path(filename: str) -> str:
    return os.path.join(USER_DIR, f"{FLOWSEAL_SOURCE_PREFIX}{filename}")


def _flowseal_base_paths(filename: str) -> tuple[str, ...]:
    return (
        _flowseal_source_path(filename),
        _bundled_path("core", "lists", filename),
        os.path.join(APP_DIR, "core", "lists", filename),
    )


def _immutable_seeded_base_paths(filename: str) -> list[str]:
    paths = []
    seen = set()
    for path in (
        _flowseal_source_path(filename),
        _bundled_path("core", "lists", filename),
    ):
        key = os.path.normcase(os.path.abspath(path))
        if key in seen:
            continue
        seen.add(key)
        paths.append(path)
    return paths


def _read_flowseal_base_lines(filename: str) -> list[str]:
    for path in _flowseal_base_paths(filename):
        if os.path.exists(path):
            lines = _read_lines_utf8(path)
            if lines or path != _flowseal_source_path(filename):
                return lines
    return []


def _load_icon_preserving_modes(path: str, fallback: QIcon | None = None) -> QIcon:
    pixmap = QPixmap(path) if os.path.exists(path) else QPixmap()
    if pixmap.isNull():
        return fallback if fallback is not None else QIcon()

    icon = QIcon()
    for mode in (
        QIcon.Mode.Normal,
        QIcon.Mode.Disabled,
        QIcon.Mode.Active,
        QIcon.Mode.Selected,
    ):
        for state in (QIcon.State.Off, QIcon.State.On):
            icon.addPixmap(pixmap, mode, state)
    return icon


def _runtime_user_list_paths() -> tuple[str, ...]:
    return (
        RUNTIME_GENERAL_USER_FILE,
        RUNTIME_EXCLUDE_USER_FILE,
        RUNTIME_IP_ALL_USER_FILE,
        RUNTIME_IP_EXCLUDE_USER_FILE,
    )


def _normalized_value_keys(lines: list[str]) -> set[str]:
    out = set()
    for line in lines:
        s = (line or "").strip()
        if not s or s.startswith("#"):
            continue
        out.add(s.casefold())
    return out


def _ensure_flowseal_source_lists() -> None:
    runtime_lists_dir = os.path.join(APP_DIR, "core", "lists")

    for filename in FLOWSEAL_LIST_FILES:
        dst = _flowseal_source_path(filename)
        if os.path.exists(dst):
            continue

        copied = False
        for src in (
            _bundled_path("core", "lists", filename),
            os.path.join(runtime_lists_dir, filename),
        ):
            if os.path.exists(src):
                try:
                    _copy_if_missing(src, dst)
                    copied = os.path.exists(dst)
                    if copied:
                        break
                except Exception:
                    copied = False

        if not copied:
            try:
                _write_lines_utf8(dst, [])
            except Exception:
                pass


def _backup_user_list_before_migration(path: str) -> None:
    backup_path = path + USER_LIST_SEEDED_BACKUP_SUFFIX
    try:
        if os.path.exists(path) and not os.path.exists(backup_path):
            shutil.copy2(path, backup_path)
    except Exception:
        pass


def _prune_seeded_user_file(user_path: str, base_paths: list[str]) -> bool:
    current_lines = _read_lines_utf8(user_path)
    current_keys = _normalized_value_keys(current_lines)
    if not current_keys:
        return False

    base_keys = set()
    for base_path in base_paths:
        base_keys.update(_normalized_value_keys(_read_lines_utf8(base_path)))

    if not base_keys:
        return False

    overlap = current_keys & base_keys
    if not overlap:
        return False

    overlap_ratio = len(overlap) / max(1, len(current_keys))
    if overlap_ratio < USER_LIST_SEEDED_OVERLAP_RATIO and len(overlap) != len(current_keys):
        return False

    filtered_lines = [
        line for line in current_lines
        if (line or "").strip().casefold() not in base_keys
    ]
    if len(filtered_lines) == len(current_lines):
        return False

    try:
        _backup_user_list_before_migration(user_path)
        _write_lines_utf8(user_path, filtered_lines)
        return True
    except Exception:
        return False


def _migrate_seeded_user_lists() -> None:
    _ensure_flowseal_source_lists()

    _prune_seeded_user_file(
        USER_GENERAL_FILE,
        _immutable_seeded_base_paths("list-general.txt")
    )
    _prune_seeded_user_file(
        USER_EXCLUDE_FILE,
        _immutable_seeded_base_paths("list-exclude.txt")
    )
    _prune_seeded_user_file(
        USER_IP_ALL_FILE,
        _immutable_seeded_base_paths("ipset-all.txt")
    )
    _prune_seeded_user_file(
        USER_IP_EXCLUDE_FILE,
        _immutable_seeded_base_paths("ipset-exclude.txt")
    )


def _ensure_user_lists_initialized() -> None:
    os.makedirs(USER_DIR, exist_ok=True)
    _ensure_flowseal_source_lists()
    _ensure_telegram_runtime_files()

    if not os.path.exists(USER_GENERAL_FILE):
        try:
            _write_lines_utf8(USER_GENERAL_FILE, [])
        except Exception:
            pass
    if not os.path.exists(USER_EXCLUDE_FILE):
        try:
            _write_lines_utf8(USER_EXCLUDE_FILE, [])
        except Exception:
            pass
    if not os.path.exists(USER_IP_ALL_FILE):
        try:
            _write_lines_utf8(USER_IP_ALL_FILE, [])
        except Exception:
            pass
    if not os.path.exists(USER_IP_EXCLUDE_FILE):
        try:
            _write_lines_utf8(USER_IP_EXCLUDE_FILE, [])
        except Exception:
            pass

    try:
        _migrate_seeded_user_lists()
    except Exception:
        pass


def _load_settings_if_needed(settings: QSettings | None = None) -> QSettings:
    return settings if settings is not None else QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)


def _safe_int_setting(qs: QSettings, key: str, default: int = 0) -> int:
    try:
        return int(qs.value(key, default) or default)
    except Exception:
        return default


def _is_telegram_mode_enabled(settings: QSettings | None = None) -> bool:
    try:
        qs = _load_settings_if_needed(settings)
        return bool(qs.value(TELEGRAM_MODE_ENABLED_KEY, False, type=bool))
    except Exception:
        return False


def _set_telegram_mode_enabled(enabled: bool, settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    qs.setValue(TELEGRAM_MODE_ENABLED_KEY, bool(enabled))
    qs.setValue(TELEGRAM_MODE_PROXY_ENABLED_KEY, bool(enabled))
    if not str(qs.value(TELEGRAM_MODE_PROXY_PORT_KEY, "") or "").strip():
        qs.setValue(TELEGRAM_MODE_PROXY_PORT_KEY, 1080)
    qs.sync()


def _get_telegram_proxy_port(settings: QSettings | None = None) -> int:
    qs = _load_settings_if_needed(settings)
    port = _safe_int_setting(qs, TELEGRAM_MODE_PROXY_PORT_KEY, 1080)
    if port <= 0 or port > 65535:
        port = 1080
    return port


def _set_telegram_last_error(error: str, settings: QSettings | None = None) -> None:
    try:
        qs = _load_settings_if_needed(settings)
        qs.setValue(TELEGRAM_MODE_LAST_ERROR_KEY, str(error or "").strip())
        qs.sync()
    except Exception:
        pass


def _ensure_telegram_runtime_files() -> None:
    try:
        _write_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE, _read_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE))
        _write_lines_utf8(RUNTIME_TELEGRAM_IP_FILE, _read_lines_utf8(RUNTIME_TELEGRAM_IP_FILE))
    except Exception:
        pass


def _write_telegram_managed_lists() -> None:
    _write_lines_utf8(USER_TELEGRAM_DOMAIN_FILE, list(TELEGRAM_WEB_DOMAINS))
    _write_lines_utf8(USER_TELEGRAM_IP_FILE, list(TELEGRAM_IP_RANGES))


def _clear_telegram_managed_lists() -> None:
    _write_lines_utf8(USER_TELEGRAM_DOMAIN_FILE, [])
    _write_lines_utf8(USER_TELEGRAM_IP_FILE, [])
    _write_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE, [])
    _write_lines_utf8(RUNTIME_TELEGRAM_IP_FILE, [])


def _sync_telegram_runtime_lists(settings: QSettings | None = None) -> None:
    try:
        if _is_telegram_mode_enabled(settings):
            if not os.path.exists(USER_TELEGRAM_DOMAIN_FILE) or not os.path.exists(USER_TELEGRAM_IP_FILE):
                _write_telegram_managed_lists()
            domains = _read_lines_utf8(USER_TELEGRAM_DOMAIN_FILE)
            ip_ranges = _read_lines_utf8(USER_TELEGRAM_IP_FILE)
        else:
            domains = []
            ip_ranges = []

        _write_lines_utf8(RUNTIME_TELEGRAM_DOMAIN_FILE, domains)
        _write_lines_utf8(RUNTIME_TELEGRAM_IP_FILE, ip_ranges)
    except Exception as e:
        _set_telegram_last_error(str(e), settings)


def _apply_telegram_mode_files(enabled: bool, settings: QSettings | None = None) -> None:
    if enabled:
        _write_telegram_managed_lists()
    else:
        _clear_telegram_managed_lists()
    _sync_telegram_runtime_lists(settings)


def _dns_malw_link_common_powershell() -> str:
    return r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Normalize-Servers([object[]]$servers) {
    return @(
        $servers |
        Where-Object { $_ } |
        ForEach-Object { $_.ToString().Trim().ToLowerInvariant() } |
        Sort-Object -Unique
    )
}

function Test-SameServers([object[]]$left, [object[]]$right) {
    $a = Normalize-Servers $left
    $b = Normalize-Servers $right
    if ($a.Count -ne $b.Count) {
        return $false
    }
    for ($i = 0; $i -lt $a.Count; $i++) {
        if ($a[$i] -ne $b[$i]) {
            return $false
        }
    }
    return $true
}

function Get-AdminState() {
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

$ipv4Servers = @(__IPV4__)
$ipv6Servers = @(__IPV6__)
$desiredServers = @($ipv4Servers + $ipv6Servers)
$dohTemplate = '__DOH__'
"""


def _build_dns_malw_link_status_script() -> str:
    script = _dns_malw_link_common_powershell() + r"""
$result = [ordered]@{
    ok = $false
    active = $false
    error = ''
    admin = Get-AdminState
    adapters = 0
    matched = 0
    method = ''
}

try {
    $getDnsClient = Get-Command Get-DnsClient -ErrorAction SilentlyContinue
    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClient -and $getDnsClientServerAddress) {
        $result.method = 'dnsclient'
        $adapters = @(
            Get-DnsClient |
            Where-Object {
                $_.InterfaceAlias -and
                $_.InterfaceOperationalStatus -eq 'Up' -and
                $_.InterfaceAlias -notmatch 'Loopback|isatap|Teredo'
            } |
            Sort-Object InterfaceIndex -Unique
        )
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @(
                Get-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ErrorAction SilentlyContinue |
                ForEach-Object { @($_.ServerAddresses) } |
                Where-Object { $_ }
            )
            if (Test-SameServers $currentServers $desiredServers) {
                $result.matched += 1
            }
        }
    } elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        $result.method = 'cim'
        $adapters = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            if (Test-SameServers @($adapter.DNSServerSearchOrder) $desiredServers) {
                $result.matched += 1
            }
        }
    } elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {
        $result.method = 'wmi'
        $adapters = @(Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            if (Test-SameServers @($adapter.DNSServerSearchOrder) $desiredServers) {
                $result.matched += 1
            }
        }
    } else {
        throw 'No DNS query backend available'
    }

    $result.active = ($result.adapters -gt 0 -and $result.matched -eq $result.adapters)
    $result.ok = $true
} catch {
    $result.error = [string]$_.Exception.Message
}

$result | ConvertTo-Json -Compress
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _build_dns_malw_link_enable_script() -> str:
    script = _dns_malw_link_common_powershell() + r"""
$result = [ordered]@{
    ok = $false
    error = ''
    admin = Get-AdminState
    adapters = 0
    applied = 0
    updated = 0
    doh = $false
    method = ''
    snapshot = @()
}

try {
    if (-not $result.admin) {
        throw 'not-admin'
    }

    $addDohCommand = Get-Command Add-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $setDohCommand = Get-Command Set-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $getDohCommand = Get-Command Get-DnsClientDohServerAddress -ErrorAction SilentlyContinue

    if ($addDohCommand -or $setDohCommand) {
        foreach ($server in $desiredServers) {
            try {
                $hasExisting = $false
                if ($getDohCommand) {
                    $existing = @(Get-DnsClientDohServerAddress -ServerAddress $server -ErrorAction SilentlyContinue)
                    $hasExisting = ($existing.Count -gt 0)
                }

                if ($hasExisting -and $setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }
                if ($addDohCommand) {
                    Add-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }
                if ($setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                }
            } catch {
                try {
                    if ($setDohCommand) {
                        Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                        $result.doh = $true
                    }
                } catch {
                }
            }
        }
    }

    $getDnsClient = Get-Command Get-DnsClient -ErrorAction SilentlyContinue
    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue
    $setDnsClientServerAddress = Get-Command Set-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClient -and $getDnsClientServerAddress -and $setDnsClientServerAddress) {
        $result.method = 'dnsclient'
        $adapters = @(
            Get-DnsClient |
            Where-Object {
                $_.InterfaceAlias -and
                $_.InterfaceOperationalStatus -eq 'Up' -and
                $_.InterfaceAlias -notmatch 'Loopback|isatap|Teredo'
            } |
            Sort-Object InterfaceIndex -Unique
        )
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @(
                Get-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ErrorAction SilentlyContinue |
                ForEach-Object { @($_.ServerAddresses) } |
                Where-Object { $_ }
            )
            $result.snapshot += [pscustomobject]@{
                interface_index = $adapter.InterfaceIndex
                alias = $adapter.InterfaceAlias
                servers = @($currentServers)
            }
            if (Test-SameServers $currentServers $desiredServers) {
                $result.applied += 1
                continue
            }

            Set-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ServerAddresses $desiredServers -ErrorAction Stop | Out-Null
            $result.updated += 1
            $result.applied += 1
        }
    } elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        $result.method = 'cim'
        $adapters = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @($adapter.DNSServerSearchOrder)
            $result.snapshot += [pscustomobject]@{
                interface_index = [int]$adapter.InterfaceIndex
                alias = [string]$adapter.Description
                servers = @($currentServers)
            }
            if (Test-SameServers $currentServers $desiredServers) {
                $result.applied += 1
                continue
            }

            $invokeResult = Invoke-CimMethod -InputObject $adapter -MethodName SetDNSServerSearchOrder -Arguments @{DNSServerSearchOrder = $desiredServers} -ErrorAction Stop
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                $result.updated += 1
                $result.applied += 1
            }
        }
    } elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {
        $result.method = 'wmi'
        $adapters = @(Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @($adapter.DNSServerSearchOrder)
            $result.snapshot += [pscustomobject]@{
                interface_index = [int]$adapter.InterfaceIndex
                alias = [string]$adapter.Description
                servers = @($currentServers)
            }
            if (Test-SameServers $currentServers $desiredServers) {
                $result.applied += 1
                continue
            }

            $invokeResult = $adapter.SetDNSServerSearchOrder($desiredServers)
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                $result.updated += 1
                $result.applied += 1
            }
        }
    } else {
        throw 'No DNS configuration backend available'
    }

    if ($result.adapters -le 0) {
        throw 'no-active-adapters'
    }
    if ($result.applied -le 0) {
        throw 'dns-apply-failed'
    }

    try {
        if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {
            Clear-DnsClientCache | Out-Null
        } else {
            & ipconfig /flushdns | Out-Null
        }
    } catch {
    }

    $result.ok = $true
} catch {
    $result.error = [string]$_.Exception.Message
}

$result | ConvertTo-Json -Compress -Depth 6
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _build_dns_malw_link_disable_script(snapshot_json: str) -> str:
    escaped_snapshot = snapshot_json.replace("'", "''")
    script = _dns_malw_link_common_powershell() + rf"""
$result = [ordered]@{{
    ok = $false
    error = ''
    admin = Get-AdminState
    adapters = 0
    applied = 0
    updated = 0
    method = ''
}}

try {{
    if (-not $result.admin) {{
        throw 'not-admin'
    }}

    $snapshotRaw = @'
{escaped_snapshot}
'@
    $snapshot = @()
    if ($snapshotRaw.Trim()) {{
        $snapshot = @((ConvertFrom-Json $snapshotRaw -ErrorAction Stop))
    }}
    if ($snapshot.Count -le 0) {{
        throw 'no-snapshot'
    }}
    $result.adapters = $snapshot.Count

    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue
    $setDnsClientServerAddress = Get-Command Set-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClientServerAddress -and $setDnsClientServerAddress) {{
        $result.method = 'dnsclient'
        foreach ($adapter in $snapshot) {{
            $index = [int]$adapter.interface_index
            $servers = @($adapter.servers)
            $currentServers = @(
                Get-DnsClientServerAddress -InterfaceIndex $index -ErrorAction SilentlyContinue |
                ForEach-Object {{ @($_.ServerAddresses) }} |
                Where-Object {{ $_ }}
            )
            if (Test-SameServers $currentServers $servers) {{
                $result.applied += 1
                continue
            }}

            if ($servers.Count -gt 0) {{
                Set-DnsClientServerAddress -InterfaceIndex $index -ServerAddresses $servers -ErrorAction Stop | Out-Null
            }} else {{
                Set-DnsClientServerAddress -InterfaceIndex $index -ResetServerAddresses -ErrorAction Stop | Out-Null
            }}
            $result.updated += 1
            $result.applied += 1
        }}
    }} elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {{
        $result.method = 'cim'
        foreach ($entry in $snapshot) {{
            $index = [int]$entry.interface_index
            $servers = @($entry.servers)
            $adapter = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop | Where-Object {{ [int]$_.InterfaceIndex -eq $index }} | Select-Object -First 1
            if (-not $adapter) {{
                continue
            }}
            $currentServers = @($adapter.DNSServerSearchOrder)
            if (Test-SameServers $currentServers $servers) {{
                $result.applied += 1
                continue
            }}
            $target = if ($servers.Count -gt 0) {{ $servers }} else {{ $null }}
            $invokeResult = Invoke-CimMethod -InputObject $adapter -MethodName SetDNSServerSearchOrder -Arguments @{{DNSServerSearchOrder = $target}} -ErrorAction Stop
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {{
                $result.updated += 1
                $result.applied += 1
            }}
        }}
    }} elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {{
        $result.method = 'wmi'
        foreach ($entry in $snapshot) {{
            $index = [int]$entry.interface_index
            $servers = @($entry.servers)
            $adapter = Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop | Where-Object {{ [int]$_.InterfaceIndex -eq $index }} | Select-Object -First 1
            if (-not $adapter) {{
                continue
            }}
            $currentServers = @($adapter.DNSServerSearchOrder)
            if (Test-SameServers $currentServers $servers) {{
                $result.applied += 1
                continue
            }}
            $target = if ($servers.Count -gt 0) {{ $servers }} else {{ $null }}
            $invokeResult = $adapter.SetDNSServerSearchOrder($target)
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {{
                $result.updated += 1
                $result.applied += 1
            }}
        }}
    }} else {{
        throw 'No DNS configuration backend available'
    }}

    if ($result.applied -le 0) {{
        throw 'dns-restore-failed'
    }}

    try {{
        if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {{
            Clear-DnsClientCache | Out-Null
        }} else {{
            & ipconfig /flushdns | Out-Null
        }}
    }} catch {{
    }}

    $result.ok = $true
}} catch {{
    $result.error = [string]$_.Exception.Message
}}

$result | ConvertTo-Json -Compress
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _run_hidden_powershell_json(script: str, timeout: int = 35) -> dict:
    result = {"ok": False, "error": "powershell-launch-failed"}
    try:
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        completed = _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand",
                encoded_script,
            ],
            timeout=timeout,
        )
        if completed is None:
            return result

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if stdout:
            for line in reversed([line.strip() for line in stdout.splitlines() if line.strip()]):
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    if "error" not in payload:
                        payload["error"] = ""
                    return payload

        if stderr:
            result["error"] = stderr.splitlines()[-1].strip()
        elif completed.returncode not in (0, None):
            result["error"] = f"powershell-exit-{completed.returncode}"
        else:
            result["error"] = "empty-powershell-result"
    except Exception as e:
        result["error"] = str(e)
    return result


def _normalize_dns_server_string(value: str) -> str:
    s = (value or "").strip().lower()
    if not s or s in {"none", "нет"}:
        return ""
    if "%" in s:
        s = s.split("%", 1)[0].strip()
    return s


def _parse_netsh_dns_servers(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current = None
    collecting = False

    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        m = re.match(r'^\s*(?:Configuration for interface|Настройка интерфейса)\s+"(.*)"\s*$', line)
        if m:
            current = m.group(1).strip()
            blocks.setdefault(current, [])
            collecting = False
            continue

        if current is None:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if (
            "Register with which suffix" in stripped
            or "Зарегистрировать с суффиксом" in stripped
        ):
            collecting = False
            continue

        if (
            "DNS Servers" in stripped
            or "DNS servers" in stripped
            or "DNS-серверы" in stripped
        ):
            collecting = True
            _, _, value_part = stripped.partition(":")
            candidate = _normalize_dns_server_string(value_part)
            if candidate:
                blocks[current].append(candidate)
            continue

        if collecting and raw_line[:1].isspace():
            candidate = _normalize_dns_server_string(stripped)
            if candidate:
                blocks[current].append(candidate)

    return {name: _merge_unique(values) for name, values in blocks.items()}


def _get_connected_interface_names() -> list[str]:
    try:
        completed = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = completed.stdout or ""
    except Exception:
        return []

    names = []
    excluded_markers = (
        "loopback",
        "bluetooth",
        "virtual",
        "hyper-v",
        "vmware",
        "vbox",
        "tap",
        "tun",
        "vpn",
        "wintun",
        "teredo",
    )
    for line in output.splitlines():
        if not line.strip():
            continue
        if (
            line.lstrip().startswith("Admin State")
            or line.lstrip().startswith("Состояние адм.")
            or set(line.strip()) == {"-"}
        ):
            continue
        m = re.match(r'^\s*\S+\s+(?:Connected|Подключен)\s+\S+\s+(.+?)\s*$', line)
        if not m:
            continue
        name = m.group(1).strip()
        name_cf = name.casefold()
        if name and not any(marker in name_cf for marker in excluded_markers):
            names.append(name)
    return names


def _parse_netsh_dns_details(text: str) -> dict[str, dict]:
    blocks: dict[str, dict] = {}
    current = None
    collecting = False

    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        m = re.match(r'^\s*(?:Configuration for interface|Настройка интерфейса)\s+"(.*)"\s*$', line)
        if m:
            current = m.group(1).strip()
            blocks[current] = {"mode": "", "servers": []}
            collecting = False
            continue

        if current is None:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if (
            "Register with which suffix" in stripped
            or "Зарегистрировать с суффиксом" in stripped
        ):
            collecting = False
            continue

        if (
            "DNS Servers" in stripped
            or "DNS servers" in stripped
            or "DNS-серверы" in stripped
        ):
            collecting = True
            low = stripped.casefold()
            if "dhcp" in low:
                blocks[current]["mode"] = "dhcp"
            elif ("static" in low) or ("статичес" in low):
                blocks[current]["mode"] = "static"
            _, _, value_part = stripped.partition(":")
            candidate = _normalize_dns_server_string(value_part)
            if candidate:
                blocks[current]["servers"].append(candidate)
            continue

        if collecting and raw_line[:1].isspace():
            candidate = _normalize_dns_server_string(stripped)
            if candidate:
                blocks[current]["servers"].append(candidate)

    for name, info in blocks.items():
        info["servers"] = _merge_unique(info.get("servers", []))
        if not info.get("mode"):
            info["mode"] = "static" if info["servers"] else "dhcp"
    return blocks


def _run_netsh_command(args: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ok = completed.returncode == 0
        msg = (completed.stderr or completed.stdout or "").strip()
        return ok, msg
    except Exception as e:
        return False, str(e)


def _get_current_dns_snapshot(interface_names: list[str] | None = None) -> list[dict]:
    names = interface_names if interface_names is not None else _get_connected_interface_names()
    ipv4_ok, ipv4_text = _run_netsh_command(["netsh", "interface", "ipv4", "show", "dnsservers"])
    ipv6_ok, ipv6_text = _run_netsh_command(["netsh", "interface", "ipv6", "show", "dnsservers"])
    ipv4_details = _parse_netsh_dns_details(ipv4_text if ipv4_ok else "")
    ipv6_details = _parse_netsh_dns_details(ipv6_text if ipv6_ok else "")
    snapshot = []
    for name in names:
        snapshot.append({
            "name": name,
            "ipv4": dict(ipv4_details.get(name, {"mode": "dhcp", "servers": []})),
            "ipv6": dict(ipv6_details.get(name, {"mode": "dhcp", "servers": []})),
        })
    return snapshot


def _apply_netsh_dns_family(interface_name: str, family: str, mode: str, servers: list[str]) -> tuple[bool, str]:
    fam = "ipv6" if family == "ipv6" else "ipv4"
    normalized = [_normalize_dns_server_string(s) for s in servers if _normalize_dns_server_string(s)]
    quoted_name = f'name="{interface_name}"' if fam == "ipv4" else interface_name

    if mode == "dhcp":
        args = ["netsh", "interface", fam, "set", "dnsservers"]
        if fam == "ipv4":
            args.extend([quoted_name, "source=dhcp", "validate=no"])
        else:
            args.extend([quoted_name, "source=dhcp", "validate=no"])
        return _run_netsh_command(args)

    if not normalized:
        return _run_netsh_command(
            ["netsh", "interface", fam, "set", "dnsservers", quoted_name, "source=dhcp", "validate=no"]
        )

    if fam == "ipv4":
        ok, msg = _run_netsh_command(
            ["netsh", "interface", "ipv4", "set", "dnsservers", quoted_name, "static", normalized[0], "primary", "validate=no"]
        )
    else:
        ok, msg = _run_netsh_command(
            ["netsh", "interface", "ipv6", "set", "dnsservers", quoted_name, "static", normalized[0], "primary", "validate=no"]
        )
    if not ok:
        return ok, msg

    for index, server in enumerate(normalized[1:], start=2):
        if fam == "ipv4":
            ok, msg = _run_netsh_command(
                ["netsh", "interface", "ipv4", "add", "dnsservers", quoted_name, server, f"index={index}", "validate=no"]
            )
        else:
            ok, msg = _run_netsh_command(
                ["netsh", "interface", "ipv6", "add", "dnsservers", quoted_name, server, f"index={index}", "validate=no"]
            )
        if not ok:
            return ok, msg
    return True, ""


def _is_dns_malw_link_enabled_by_app(settings: QSettings | None = None) -> bool:
    try:
        qs = _load_settings_if_needed(settings)
        return bool(qs.value(DNS_MALW_ENABLED_BY_APP_KEY, False, type=bool))
    except Exception:
        return False


def _set_dns_malw_link_enabled_by_app(enabled: bool, settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    qs.setValue(DNS_MALW_ENABLED_BY_APP_KEY, bool(enabled))
    qs.sync()


def _load_dns_malw_link_snapshot(settings: QSettings | None = None) -> list[dict]:
    try:
        qs = _load_settings_if_needed(settings)
        raw = str(qs.value(DNS_MALW_RESTORE_SNAPSHOT_KEY, "") or "").strip()
        if not raw:
            return []
        payload = json.loads(raw)
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _save_dns_malw_link_snapshot(snapshot: list[dict], settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    try:
        raw = json.dumps(snapshot or [], ensure_ascii=False)
    except Exception:
        raw = "[]"
    qs.setValue(DNS_MALW_RESTORE_SNAPSHOT_KEY, raw)
    qs.sync()


def _read_hosts_file(path: str = DNS_MALW_HOSTS_PATH) -> str:
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        return ""

    return _decode_hosts_bytes(raw)


def _read_hosts_file_strict(path: str = DNS_MALW_HOSTS_PATH) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    return _decode_hosts_bytes(raw)


def _decode_hosts_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "mbcs"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _write_hosts_file(content: str, path: str = DNS_MALW_HOSTS_PATH) -> None:
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    data = normalized.encode("utf-8")
    is_system_hosts = os.path.normcase(path) == os.path.normcase(DNS_MALW_HOSTS_PATH)
    attempts = 8 if is_system_hosts else 1
    last_error = None

    for attempt in range(attempts):
        try:
            with open(path, "wb") as f:
                f.write(data)
            return
        except (PermissionError, OSError) as e:
            last_error = e
            is_permission_error = isinstance(e, PermissionError) or getattr(e, "errno", None) == 13 or getattr(e, "winerror", None) == 5
            if not is_permission_error:
                raise
            if attempt >= attempts - 1:
                break
            try:
                os.chmod(path, 0o666)
            except Exception:
                pass
            time.sleep(0.28 + attempt * 0.34)

    if is_system_hosts:
        ps_error = _write_system_hosts_file_via_powershell(data, path)
        if not ps_error:
            return
        if last_error is None:
            raise PermissionError(ps_error)

    if last_error is not None:
        raise last_error


def _write_system_hosts_file_via_powershell(data: bytes, path: str = DNS_MALW_HOSTS_PATH) -> str:
    tmp_path = ""
    script_path = ""
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="hosts-write-", suffix=".tmp", dir=APP_DIR)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        script = r"""
param([string]$src, [string]$dst)
$ErrorActionPreference = 'Stop'
$bytes = [System.IO.File]::ReadAllBytes($src)
$lastError = $null

for ($i = 0; $i -lt 8; $i++) {
    try {
        if (Test-Path -LiteralPath $dst) {
            try { & attrib.exe -R -S -H $dst 2>$null | Out-Null } catch {}
        }
        [System.IO.File]::WriteAllBytes($dst, $bytes)
        exit 0
    } catch {
        $lastError = $_.Exception.Message
        Start-Sleep -Milliseconds (260 + ($i * 280))
    }
}

throw $lastError
"""
        fd_script, script_path = tempfile.mkstemp(prefix="hosts-write-", suffix=".ps1", dir=APP_DIR)
        with os.fdopen(fd_script, "w", encoding="utf-8") as f:
            f.write(script.lstrip())

        completed = _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File",
                script_path,
                tmp_path,
                path,
            ],
            timeout=12,
        )
        if completed is not None and completed.returncode == 0:
            return ""
        if completed is None:
            return "powershell-hosts-write-failed"
        return (completed.stderr or completed.stdout or f"powershell-exit-{completed.returncode}").strip()
    except Exception as e:
        return str(e)
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        if script_path:
            try:
                os.remove(script_path)
            except Exception:
                pass


def _is_hosts_permission_error_message(error: str) -> bool:
    s = (error or "").casefold()
    return (
        "permission denied" in s
        or "access is denied" in s
        or "отказано в доступе" in s
        or "errno 13" in s
        or "winerror 5" in s
        or DNS_MALW_HOSTS_PATH.casefold() in s
    )


def _hosts_contains_ai_marker(text: str) -> bool:
    hay = (text or "").casefold()
    return (
        DNS_MALW_HOSTS_BLOCK_BEGIN.casefold() in hay
        or "dns.malw.link" in hay
        or "goida ai unlocker" in hay
        or "openai.com.cdn.cloudflare.net" in hay
        or "claude.ai.cdn.cloudflare.net" in hay
    )


def _hosts_contains_dns_malw_managed_block(text: str) -> bool:
    hay = (text or "").casefold()
    return (
        DNS_MALW_HOSTS_BLOCK_BEGIN.casefold() in hay
        and DNS_MALW_HOSTS_BLOCK_END.casefold() in hay
    )


def _hosts_bundle_looks_useful(text: str) -> bool:
    hay = (text or "").casefold()
    return any(token in hay for token in ("openai", "chatgpt", "claude", "gemini", "anthropic"))


def _strip_dns_malw_hosts_block(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    pattern = re.compile(
        rf"(?:^|\n)[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_BEGIN)}[^\n]*\n.*?"
        rf"[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_END)}[^\n]*(?:\n|$)",
        re.S,
    )
    cleaned = pattern.sub("\n", normalized)
    cleaned = _strip_dns_malw_legacy_hosts_blocks(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned + ("\n" if cleaned else "")


def _strip_dns_malw_legacy_hosts_blocks(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    main_pattern = re.compile(
        rf"(?:^|\n)[ \t]*{re.escape(DNS_MALW_LEGACY_HOSTS_BLOCK_BEGIN)}[^\n]*\n.*?"
        rf"[ \t]*{re.escape(DNS_MALW_LEGACY_HOSTS_BLOCK_END)}[^\n]*(?:\n|$)",
        re.S | re.I,
    )
    cleaned = main_pattern.sub("\n", normalized)

    additional_pattern = re.compile(
        rf"(?:^|\n)[ \t]*{re.escape(DNS_MALW_LEGACY_ADDITIONAL_BLOCK_BEGIN)}[^\n]*(?:\n.*)?$",
        re.S | re.I,
    )
    return additional_pattern.sub("\n", cleaned)


def _extract_dns_malw_hosts_block_body(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    pattern = re.compile(
        rf"[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_BEGIN)}[^\n]*\n(?P<body>.*?)"
        rf"\n[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_END)}[^\n]*",
        re.S,
    )
    m = pattern.search(normalized)
    return (m.group("body") if m else "").strip()


def _hosts_line_target_hostname(line: str) -> str:
    clean = (line or "").split("#", 1)[0].strip()
    if not clean:
        return ""
    parts = clean.split()
    if len(parts) < 2:
        return ""
    return parts[1].strip().rstrip(".").casefold()


def _filter_dns_malw_hosts_bundle(text: str) -> str:
    protected = {host.casefold() for host in DNS_MALW_PROTECTED_HOSTS}
    kept = []
    for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        host = _hosts_line_target_hostname(line)
        if host and host in protected:
            continue
        kept.append(line.rstrip())
    out = "\n".join(kept).strip()
    return out + ("\n" if out else "")


def _compose_dns_malw_hosts(original_hosts: str, managed_hosts: str) -> str:
    base = _strip_dns_malw_hosts_block(original_hosts).rstrip()
    block_body = _filter_dns_malw_hosts_bundle(managed_hosts).strip()
    block = f"{DNS_MALW_HOSTS_BLOCK_BEGIN}\n{block_body}\n{DNS_MALW_HOSTS_BLOCK_END}\n"
    if base:
        return base + "\n\n" + block
    return block


def _repair_dns_malw_hosts_for_app_network(settings: QSettings | None = None) -> bool:
    if not _is_dns_malw_link_enabled_by_app(settings):
        return False
    try:
        current_hosts = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
        if not _hosts_contains_dns_malw_managed_block(current_hosts):
            return False

        block_body = _extract_dns_malw_hosts_block_body(current_hosts)
        filtered_body = _filter_dns_malw_hosts_bundle(block_body)
        if filtered_body.strip() == block_body.strip():
            return False

        base_hosts = _strip_dns_malw_hosts_block(current_hosts)
        _write_hosts_file(_compose_dns_malw_hosts(base_hosts, filtered_body), DNS_MALW_HOSTS_PATH)
        _run_hidden(["ipconfig", "/flushdns"])
        return True
    except Exception:
        return False


def _is_dns_malw_backup_usable(text: str) -> bool:
    return bool((text or "").strip()) and not _hosts_contains_ai_marker(text)


def _load_dns_malw_backup() -> str:
    if not os.path.exists(DNS_MALW_HOSTS_BACKUP_PATH):
        return ""
    return _read_hosts_file(DNS_MALW_HOSTS_BACKUP_PATH)


def _save_dns_malw_backup_if_safe(current_hosts: str, settings: QSettings | None = None) -> str:
    qs = _load_settings_if_needed(settings)
    existing = _load_dns_malw_backup()
    if _is_dns_malw_link_enabled_by_app(qs) and _is_dns_malw_backup_usable(existing):
        return existing

    cleaned = _strip_dns_malw_hosts_block(current_hosts)
    if _hosts_contains_ai_marker(cleaned) and _is_dns_malw_backup_usable(existing):
        return existing

    if (not _hosts_contains_ai_marker(cleaned)) or not existing:
        _write_hosts_file(cleaned, DNS_MALW_HOSTS_BACKUP_PATH)
        return cleaned

    return existing


def _download_ai_hosts_bundle() -> tuple[str, str]:
    headers = {"User-Agent": "ZapretGUI-AiDNS"}
    try:
        main_resp = requests.get(DNS_MALW_HOSTS_URL, headers=headers, timeout=25)
        main_resp.raise_for_status()
        main_hosts = (main_resp.text or "").replace("\r\n", "\n").replace("\r", "\n").strip()

        additional_block = ""
        additional_version = ""
        try:
            add_resp = requests.get(DNS_MALW_ADDITIONAL_URL, headers=headers, timeout=20)
            add_resp.raise_for_status()
            add_text = add_resp.text or ""
            m_ver = DNS_MALW_ADDITIONAL_VERSION_RE.search(add_text)
            m_hosts = DNS_MALW_ADDITIONAL_HOSTS_RE.search(add_text)
            if m_ver:
                additional_version = m_ver.group(1).strip()
            if m_hosts:
                additional_block = (m_hosts.group("body") or "").strip()
        except Exception:
            additional_block = ""
            additional_version = ""

        pieces = [main_hosts]
        if additional_block:
            header = "# Goida-AI-Unlocker additional hosts"
            if additional_version:
                header += f" ({additional_version})"
            pieces.append(header)
            pieces.append(additional_block)

        final_hosts = "\n\n".join(part for part in pieces if part).strip() + "\n"
        if len([line for line in final_hosts.splitlines() if line.strip() and not line.lstrip().startswith("#")]) < 3:
            raise RuntimeError("downloaded-hosts-too-small")
        if not _hosts_bundle_looks_useful(final_hosts):
            raise RuntimeError("downloaded-hosts-do-not-contain-ai-domains")
        final_hosts = _filter_dns_malw_hosts_bundle(final_hosts)
        _write_hosts_file(final_hosts, DNS_MALW_HOSTS_CACHE_PATH)
        return final_hosts, additional_version
    except Exception as e:
        cached_hosts = _read_hosts_file(DNS_MALW_HOSTS_CACHE_PATH)
        if cached_hosts.strip() and _hosts_bundle_looks_useful(cached_hosts):
            return _filter_dns_malw_hosts_bundle(cached_hosts), "cached"
        raise e


def _sync_ai_dns_if_enabled(settings: QSettings | None = None) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {"ok": False, "skipped": False, "error": ""}
    if not _is_dns_malw_link_enabled_by_app(qs):
        result["skipped"] = True
        return result

    try:
        is_admin_now = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin_now = False

    if not is_admin_now:
        result["skipped"] = True
        return result

    sync_result = _enable_dns_malw_link(qs)
    result["ok"] = bool(sync_result.get("ok"))
    result["error"] = str(sync_result.get("error", "") or "")
    return result


def _get_dns_malw_link_status() -> dict:
    result = {
        "ok": True,
        "active": False,
        "error": "",
        "admin": False,
        "adapters": 0,
        "matched": 0,
        "method": "hosts",
    }

    try:
        hosts_text = _read_hosts_file(DNS_MALW_HOSTS_PATH)
        result["active"] = _hosts_contains_ai_marker(hosts_text)
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)

    return result


def _enable_dns_malw_link(settings: QSettings | None = None) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "error": "",
        "admin": False,
        "adapters": 1,
        "applied": 0,
        "updated": 0,
        "doh": False,
        "method": "hosts",
        "snapshot": [],
    }

    try:
        result["admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        result["admin"] = False

    if not result["admin"]:
        result["error"] = "not-admin"
    else:
        try:
            try:
                current_hosts = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
            except FileNotFoundError:
                current_hosts = ""
            backup_hosts = _save_dns_malw_backup_if_safe(current_hosts, qs)
            new_hosts, additional_version = _download_ai_hosts_bundle()
            base_hosts = _strip_dns_malw_hosts_block(current_hosts)
            if _hosts_contains_ai_marker(base_hosts):
                if _is_dns_malw_backup_usable(backup_hosts):
                    base_hosts = backup_hosts
                else:
                    raise RuntimeError("no-clean-snapshot")
            final_hosts = _compose_dns_malw_hosts(base_hosts, new_hosts)
            _write_hosts_file(final_hosts, DNS_MALW_HOSTS_PATH)
            _run_hidden(["ipconfig", "/flushdns"])
            _run_hidden(["ipconfig", "/registerdns"])
            result["ok"] = True
            result["applied"] = 1
            result["updated"] = 1
            result["snapshot"] = [{
                "backup": DNS_MALW_HOSTS_BACKUP_PATH,
                "mode": "hosts-managed-block",
                "additional_version": additional_version,
            }]
        except Exception as e:
            result["error"] = str(e)

    try:
        qs.setValue(DNS_MALW_LAST_ATTEMPT_KEY, int(time.time()))
        qs.setValue(DNS_MALW_LAST_STATUS_KEY, "ok" if result.get("ok") else "error")
        qs.setValue(DNS_MALW_LAST_ERROR_KEY, str(result.get("error", "") or ""))
        qs.setValue(DNS_MALW_LAST_UPDATED_KEY, int(result.get("updated", 0) or 0))
        qs.setValue(DNS_MALW_LAST_DOH_KEY, bool(result.get("doh")))
        if result.get("ok"):
            qs.setValue(DNS_MALW_LAST_SUCCESS_KEY, int(time.time()))
            _save_dns_malw_link_snapshot(result.get("snapshot") or [], qs)
            qs.setValue(DNS_MALW_ENABLED_BY_APP_KEY, True)
        qs.sync()
    except Exception:
        pass
    return result


def _disable_dns_malw_link(settings: QSettings | None = None) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "error": "",
        "admin": False,
        "adapters": 1,
        "applied": 0,
        "updated": 0,
        "method": "hosts",
    }
    try:
        result["admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        result["admin"] = False

    if not result["admin"]:
        result["error"] = "not-admin"
    else:
        try:
            try:
                current_hosts = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
            except FileNotFoundError:
                current_hosts = ""
            backup_hosts = _load_dns_malw_backup()
            if _hosts_contains_dns_malw_managed_block(current_hosts):
                restored_hosts = _strip_dns_malw_hosts_block(current_hosts)
                if _hosts_contains_ai_marker(restored_hosts):
                    if _is_dns_malw_backup_usable(backup_hosts):
                        restored_hosts = backup_hosts
                    else:
                        raise RuntimeError("no-clean-snapshot")
            elif _is_dns_malw_backup_usable(backup_hosts):
                restored_hosts = backup_hosts
            else:
                restored_hosts = _strip_dns_malw_hosts_block(current_hosts)
                if _hosts_contains_ai_marker(restored_hosts):
                    raise RuntimeError("no-clean-snapshot")
            _write_hosts_file(restored_hosts, DNS_MALW_HOSTS_PATH)
            _run_hidden(["ipconfig", "/flushdns"])
            _run_hidden(["ipconfig", "/registerdns"])
            result["ok"] = True
            result["applied"] = 1
            result["updated"] = 1
        except Exception as e:
            result["error"] = str(e)

    try:
        qs.setValue(DNS_MALW_LAST_ATTEMPT_KEY, int(time.time()))
        qs.setValue(DNS_MALW_LAST_STATUS_KEY, "ok" if result.get("ok") else "error")
        qs.setValue(DNS_MALW_LAST_ERROR_KEY, str(result.get("error", "") or ""))
        if result.get("ok"):
            qs.setValue(DNS_MALW_ENABLED_BY_APP_KEY, False)
            qs.setValue(DNS_MALW_RESTORE_SNAPSHOT_KEY, "")
            qs.setValue(DNS_MALW_LAST_UPDATED_KEY, int(result.get("updated", 0) or 0))
        qs.sync()
    except Exception:
        pass
    return result


def _run_self_as_admin_for_dns_action(action: str) -> bool:
    try:
        action = (action or "").strip().lower()
        if action not in {"enable", "disable"}:
            return False

        if getattr(sys, "frozen", False):
            executable = sys.executable
            params = subprocess.list2cmdline([f"--dns-malw-link-action={action}"])
        else:
            executable = sys.executable
            params = subprocess.list2cmdline([os.path.abspath(sys.argv[0]), f"--dns-malw-link-action={action}"])

        res = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            0,
        )
        return int(res) > 32
    except Exception:
        return False


def _build_dns_malw_link_script() -> str:
    script = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Normalize-Servers([object[]]$servers) {
    return @(
        $servers |
        Where-Object { $_ } |
        ForEach-Object { $_.ToString().Trim().ToLowerInvariant() } |
        Sort-Object -Unique
    )
}

function Test-SameServers([object[]]$left, [object[]]$right) {
    $a = Normalize-Servers $left
    $b = Normalize-Servers $right
    if ($a.Count -ne $b.Count) {
        return $false
    }
    for ($i = 0; $i -lt $a.Count; $i++) {
        if ($a[$i] -ne $b[$i]) {
            return $false
        }
    }
    return $true
}

$result = [ordered]@{
    ok = $false
    skipped = $false
    reason = ''
    error = ''
    admin = $false
    adapters = 0
    applied = 0
    updated = 0
    doh = $false
    method = ''
}

try {
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        $result.admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        $result.admin = $false
    }

    if (-not $result.admin) {
        $result.skipped = $true
        $result.reason = 'not-admin'
        $result | ConvertTo-Json -Compress
        exit 0
    }

    $ipv4Servers = @(__IPV4__)
    $ipv6Servers = @(__IPV6__)
    $desiredServers = @($ipv4Servers + $ipv6Servers)
    $dohTemplate = '__DOH__'

    $addDohCommand = Get-Command Add-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $setDohCommand = Get-Command Set-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $getDohCommand = Get-Command Get-DnsClientDohServerAddress -ErrorAction SilentlyContinue

    if ($addDohCommand -or $setDohCommand) {
        foreach ($server in $desiredServers) {
            try {
                $hasExisting = $false
                if ($getDohCommand) {
                    $existing = @(Get-DnsClientDohServerAddress -ServerAddress $server -ErrorAction SilentlyContinue)
                    $hasExisting = ($existing.Count -gt 0)
                }

                if ($hasExisting -and $setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }

                if ($addDohCommand) {
                    Add-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }

                if ($setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                }
            } catch {
                try {
                    if ($setDohCommand) {
                        Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                        $result.doh = $true
                    }
                } catch {
                }
            }
        }
    }

    $getDnsClient = Get-Command Get-DnsClient -ErrorAction SilentlyContinue
    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue
    $setDnsClientServerAddress = Get-Command Set-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClient -and $getDnsClientServerAddress -and $setDnsClientServerAddress) {
        $result.method = 'dnsclient'
        $adapters = @(
            Get-DnsClient |
            Where-Object {
                $_.InterfaceAlias -and
                $_.InterfaceOperationalStatus -eq 'Up' -and
                $_.InterfaceAlias -notmatch 'Loopback|isatap|Teredo'
            } |
            Sort-Object InterfaceIndex -Unique
        )
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            try {
                $currentServers = @(
                    Get-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ErrorAction SilentlyContinue |
                    ForEach-Object { @($_.ServerAddresses) } |
                    Where-Object { $_ }
                )
                if (Test-SameServers $currentServers $desiredServers) {
                    $result.applied += 1
                    continue
                }

                Set-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ServerAddresses $desiredServers -ErrorAction Stop | Out-Null
                $result.updated += 1
                $result.applied += 1
            } catch {
            }
        }
    } elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        $result.method = 'cim'
        $adapters = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            try {
                $currentServers = @($adapter.DNSServerSearchOrder)
                if (Test-SameServers $currentServers $desiredServers) {
                    $result.applied += 1
                    continue
                }

                $invokeResult = Invoke-CimMethod -InputObject $adapter -MethodName SetDNSServerSearchOrder -Arguments @{DNSServerSearchOrder = $desiredServers} -ErrorAction Stop
                if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                    $result.updated += 1
                    $result.applied += 1
                }
            } catch {
            }
        }
    } elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {
        $result.method = 'wmi'
        $adapters = @(Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            try {
                $currentServers = @($adapter.DNSServerSearchOrder)
                if (Test-SameServers $currentServers $desiredServers) {
                    $result.applied += 1
                    continue
                }

                $invokeResult = $adapter.SetDNSServerSearchOrder($desiredServers)
                if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                    $result.updated += 1
                    $result.applied += 1
                }
            } catch {
            }
        }
    } else {
        throw 'No DNS configuration backend available'
    }

    if ($result.adapters -le 0) {
        $result.skipped = $true
        $result.reason = 'no-active-adapters'
        $result | ConvertTo-Json -Compress
        exit 0
    }

    if ($result.applied -le 0) {
        throw 'dns-apply-failed'
    }

    try {
        if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {
            Clear-DnsClientCache | Out-Null
        } else {
            & ipconfig /flushdns | Out-Null
        }
    } catch {
    }

    $result.ok = $true
} catch {
    $result.error = [string]$_.Exception.Message
}

$result | ConvertTo-Json -Compress
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _ensure_dns_malw_link(
    settings: QSettings | None = None,
    min_retry_seconds: int = 0,
) -> dict:
    result = {
        "ok": False,
        "skipped": False,
        "reason": "",
        "error": "",
        "admin": False,
        "adapters": 0,
        "applied": 0,
        "updated": 0,
        "doh": False,
        "method": "",
    }

    qs = _load_settings_if_needed(settings)
    now = int(time.time())
    last_attempt_to_store = now

    if not sys.platform.startswith("win"):
        result["skipped"] = True
        result["reason"] = "non-windows"
    else:
        should_run = True
        if min_retry_seconds > 0:
            last_attempt = _safe_int_setting(qs, DNS_MALW_LAST_ATTEMPT_KEY, 0)
            last_status = str(qs.value(DNS_MALW_LAST_STATUS_KEY, "") or "").strip().lower()
            if last_attempt > 0 and (now - last_attempt) < min_retry_seconds:
                result["skipped"] = True
                result["reason"] = "recent-attempt"
                last_attempt_to_store = last_attempt
                should_run = False
                if last_status == "ok":
                    result["ok"] = True
                    result["doh"] = bool(qs.value(DNS_MALW_LAST_DOH_KEY, False, type=bool))
                    result["updated"] = _safe_int_setting(qs, DNS_MALW_LAST_UPDATED_KEY, 0)
                try:
                    result["admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
                except Exception:
                    result["admin"] = False
        if should_run:
            encoded_script = base64.b64encode(
                _build_dns_malw_link_script().encode("utf-16le")
            ).decode("ascii")
            completed = _run_hidden(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-EncodedCommand",
                    encoded_script,
                ],
                timeout=35,
            )

            if completed is None:
                result["error"] = "powershell-launch-failed"
            else:
                stdout = (completed.stdout or "").strip()
                stderr = (completed.stderr or "").strip()
                payload = None
                if stdout:
                    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
                    for line in reversed(lines):
                        try:
                            parsed = json.loads(line)
                        except Exception:
                            continue
                        if isinstance(parsed, dict):
                            payload = parsed
                            break

                if isinstance(payload, dict):
                    for key in result:
                        if key in payload:
                            result[key] = payload[key]
                elif stderr:
                    result["error"] = stderr.splitlines()[-1].strip()

                if completed.returncode not in (0, None) and not result["error"]:
                    result["error"] = f"powershell-exit-{completed.returncode}"

    try:
        qs.setValue(DNS_MALW_LAST_ATTEMPT_KEY, last_attempt_to_store)
        qs.setValue(
            DNS_MALW_LAST_STATUS_KEY,
            "ok" if result["ok"] else ("skipped" if result["skipped"] else "error"),
        )
        qs.setValue(
            DNS_MALW_LAST_ERROR_KEY,
            str(result.get("error") or result.get("reason") or "").strip(),
        )
        qs.setValue(DNS_MALW_LAST_UPDATED_KEY, int(result.get("updated", 0) or 0))
        qs.setValue(DNS_MALW_LAST_DOH_KEY, bool(result.get("doh")))
        if result["ok"]:
            qs.setValue(DNS_MALW_LAST_SUCCESS_KEY, now)
        qs.sync()
    except Exception:
        pass

    return result


def _is_game_mode_enabled(settings: QSettings | None = None) -> bool:
    try:
        qs = _load_settings_if_needed(settings)
        return bool(qs.value(GAME_MODE_KEY, False, type=bool))
    except Exception:
        return False


def _set_game_mode_enabled(enabled: bool, settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    qs.setValue(GAME_MODE_KEY, bool(enabled))
    qs.sync()


def _get_game_mode_options(settings: QSettings | None = None) -> dict:
    try:
        qs = _load_settings_if_needed(settings)
        return {
            "main_bypass_enabled": bool(qs.value(GAME_MODE_MAIN_BYPASS_KEY, True, type=bool)),
            "user_lists_enabled": bool(qs.value(GAME_MODE_USER_LISTS_KEY, True, type=bool)),
            "discord_enabled": bool(qs.value(GAME_MODE_DISCORD_KEY, False, type=bool)),
        }
    except Exception:
        return {
            "main_bypass_enabled": True,
            "user_lists_enabled": True,
            "discord_enabled": False,
        }


def _set_game_mode_options(
    main_bypass_enabled: bool | None = None,
    user_lists_enabled: bool | None = None,
    discord_enabled: bool | None = None,
    settings: QSettings | None = None,
) -> None:
    qs = _load_settings_if_needed(settings)
    if main_bypass_enabled is not None:
        qs.setValue(GAME_MODE_MAIN_BYPASS_KEY, bool(main_bypass_enabled))
    if user_lists_enabled is not None:
        qs.setValue(GAME_MODE_USER_LISTS_KEY, bool(user_lists_enabled))
    if discord_enabled is not None:
        qs.setValue(GAME_MODE_DISCORD_KEY, bool(discord_enabled))
    qs.sync()


def _get_effective_game_mode_options(settings: QSettings | None = None) -> dict:
    if not _is_game_mode_enabled(settings):
        return {
            "main_bypass_enabled": True,
            "user_lists_enabled": True,
            "discord_enabled": False,
        }
    return _get_game_mode_options(settings)


def _get_game_filter_ports(settings: QSettings | None = None) -> tuple[str, str]:
    if not _is_game_mode_enabled(settings):
        return ("12", "12")

    mode = (GAME_FILTER_FLAG_MODE or "all").strip().casefold()
    if mode == "tcp":
        return ("1024-65535", "12")
    if mode == "udp":
        return ("12", "1024-65535")
    return ("1024-65535", "1024-65535")


def _apply_game_mode_state_to_core(settings: QSettings | None = None) -> None:
    enabled = _is_game_mode_enabled(settings)
    try:
        if enabled:
            os.makedirs(os.path.dirname(GAME_FILTER_FLAG_FILE), exist_ok=True)
            _atomic_write_bytes(GAME_FILTER_FLAG_FILE, (GAME_FILTER_FLAG_MODE + "\n").encode("ascii"))
        else:
            if os.path.exists(GAME_FILTER_FLAG_FILE):
                os.remove(GAME_FILTER_FLAG_FILE)
    except Exception:
        pass


def _create_lists_sync_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "*/*",
        "Cache-Control": "no-cache",
    })
    return session


def _download_sync_bytes(session: requests.Session, url: str) -> bytes:
    r = session.get(
        url,
        timeout=(2.5, 6.0),
        allow_redirects=True,
    )
    r.raise_for_status()
    return r.content


def _sync_gaming_lists(settings: QSettings | None = None, session: requests.Session | None = None) -> dict:
    result = {
        "ok": False,
        "updated": 0,
        "error": "",
        "offline": False,
        "silent_missing": False,
    }

    qs = _load_settings_if_needed(settings)
    own_session = session is None
    missing_before = sum(0 if os.path.exists(meta["path"]) else 1 for meta in GAMING_LIST_TARGETS.values())

    try:
        os.makedirs(USER_DIR, exist_ok=True)

        if session is None:
            session = _create_lists_sync_session("ZapretGUI-GamingLists")

        response = session.get(
            GAMING_LISTS_API_URL,
            timeout=(2.5, 6.0),
            allow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected gaming lists API response")

        remote_items = {
            str(item.get("name")): item
            for item in payload
            if isinstance(item, dict) and item.get("type") == "file"
        }

        for name, meta in GAMING_LIST_TARGETS.items():
            remote = remote_items.get(name)
            if not remote:
                continue

            dst = meta["path"]
            remote_sha = str(remote.get("sha") or "").strip()
            download_url = str(remote.get("download_url") or "").strip()
            stored_remote_sha = str(qs.value(meta["remote_sha_key"], "") or "").strip()
            stored_local_hash = str(qs.value(meta["local_hash_key"], "") or "").strip()
            local_data = _read_file_bytes(dst)
            local_hash = _sha256_bytes(local_data)

            needs_download = (
                not os.path.exists(dst)
                or not local_hash
                or local_hash != stored_local_hash
                or (remote_sha and remote_sha != stored_remote_sha)
            )

            if needs_download and download_url:
                remote_data = _download_sync_bytes(session, download_url)
                remote_hash = _sha256_bytes(remote_data)
                if remote_hash != local_hash:
                    _atomic_write_bytes(dst, remote_data)
                    result["updated"] += 1
                local_hash = remote_hash

            if remote_sha:
                qs.setValue(meta["remote_sha_key"], remote_sha)
            if local_hash:
                qs.setValue(meta["local_hash_key"], local_hash)

        qs.sync()
        result["ok"] = True
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["error"] = str(e)
        if missing_before > 0:
            result["silent_missing"] = True
    except Exception as e:
        result["error"] = str(e)
        if missing_before > 0:
            result["silent_missing"] = True
    finally:
        if own_session and session is not None:
            try:
                session.close()
            except Exception:
                pass

    return result


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


def _is_single_ip_address_like(s: str) -> bool:
    try:
        ipaddress.ip_address(_normalize_ip_candidate(s))
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


def _normalize_ip_candidate(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""

    s = s.split("#", 1)[0].strip().strip("\"'(){}<>")
    if not s:
        return ""

    if "://" in s:
        try:
            s = (urlsplit(s).hostname or "").strip()
        except Exception:
            s = s.split("://", 1)[1]

    s = s.split("\\", 1)[0].strip()
    if s.startswith("[") and "]" in s:
        s = s[1:s.index("]")]
    elif "/" in s:
        host, suffix = s.split("/", 1)
        if not suffix.isdigit():
            s = host

    if s.count(":") == 1 and "." in s:
        host, port = s.rsplit(":", 1)
        if port.isdigit():
            s = host

    return s.strip().strip("\"'[](){}<>")


def _is_valid_ip_or_network_like(s: str) -> bool:
    try:
        ipaddress.ip_network(_normalize_ip_candidate(s), strict=False)
        return True
    except ValueError:
        return False


def _entity_kind_for_target_file(target_file: str) -> str:
    if target_file in (USER_IP_ALL_FILE, USER_IP_EXCLUDE_FILE):
        return "ip"
    return "domain"


def _normalize_value_for_target_file(target_file: str, raw: str) -> str:
    if _entity_kind_for_target_file(target_file) == "ip":
        return _normalize_ip_candidate(raw)
    return _normalize_domain_candidate(raw)


def _is_valid_value_for_target_file(target_file: str, value: str) -> bool:
    if _entity_kind_for_target_file(target_file) == "ip":
        return _is_valid_ip_or_network_like(value)
    return _is_valid_domain_like(value)


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
        _ensure_flowseal_source_lists()
        _ensure_user_lists_initialized()
        game_mode_enabled = _is_game_mode_enabled(settings)
        effective_options = _get_effective_game_mode_options(settings)
        main_bypass_enabled = bool(effective_options["main_bypass_enabled"])
        user_lists_enabled = bool(effective_options["user_lists_enabled"])
        discord_enabled = bool(effective_options["discord_enabled"])

        core_general = _read_flowseal_base_lines("list-general.txt") if main_bypass_enabled else []
        core_exclude = _read_flowseal_base_lines("list-exclude.txt") if main_bypass_enabled else []
        core_google = _read_flowseal_base_lines("list-google.txt") if main_bypass_enabled else []
        core_ip_all = _read_flowseal_base_lines("ipset-all.txt") if main_bypass_enabled else []
        core_ip_exclude = _read_flowseal_base_lines("ipset-exclude.txt") if main_bypass_enabled else []

        user_general = _read_lines_utf8(USER_GENERAL_FILE) if user_lists_enabled else []
        user_exclude = _read_lines_utf8(USER_EXCLUDE_FILE) if user_lists_enabled else []
        user_ip_all = _read_lines_utf8(USER_IP_ALL_FILE) if user_lists_enabled else []
        user_ip_exclude = _read_lines_utf8(USER_IP_EXCLUDE_FILE) if user_lists_enabled else []
        user_game_domains = _read_lines_utf8(USER_GAME_DOMAIN_FILE) if game_mode_enabled else []
        user_game_ip = _read_lines_utf8(USER_GAME_IP_FILE) if game_mode_enabled else []
        discord_domains = _read_lines_utf8(RUNTIME_DISCORD_FILE) if (game_mode_enabled and discord_enabled) else []

        merged_general = _merge_unique(core_general, user_general, user_game_domains, discord_domains)
        merged_exclude = _merge_unique(core_exclude, user_exclude)
        merged_google = _merge_unique(core_google)
        merged_ip_all = _merge_unique(core_ip_all, user_ip_all, user_game_ip)
        merged_ip_exclude = _merge_unique(core_ip_exclude, user_ip_exclude)

        _write_lines_utf8(RUNTIME_GENERAL_FILE, merged_general)
        _write_lines_utf8(RUNTIME_EXCLUDE_FILE, merged_exclude)
        _write_lines_utf8(RUNTIME_GOOGLE_FILE, merged_google)
        _write_lines_utf8(RUNTIME_IP_ALL_FILE, merged_ip_all)
        _write_lines_utf8(RUNTIME_IP_EXCLUDE_FILE, merged_ip_exclude)
        for runtime_user_path in _runtime_user_list_paths():
            _write_lines_utf8(runtime_user_path, [])
        _apply_game_mode_state_to_core(settings)
        _sync_telegram_runtime_lists(settings)
    except Exception:
        pass


def _sync_flowseal_lists(settings: QSettings | None = None) -> dict:
    result = {
        "ok": False,
        "offline": False,
        "flowseal_updated": 0,
        "gaming_updated": 0,
        "gaming_error": "",
        "gaming_offline": False,
        "gaming_silent_missing": False,
        "error": "",
    }
    session = None
    try:
        os.makedirs(USER_DIR, exist_ok=True)
        _ensure_flowseal_source_lists()
        _repair_dns_malw_hosts_for_app_network(settings)

        session = _create_lists_sync_session("ZapretGUI-ListsSync")

        flowseal_updates = []
        for fn in FLOWSEAL_LIST_FILES:
            url = FLOWSEAL_LIST_BASE_URL + fn
            remote_data = _download_sync_bytes(session, url)
            dst = _flowseal_source_path(fn)
            local_data = _read_file_bytes(dst)
            if _sha256_bytes(local_data) != _sha256_bytes(remote_data):
                flowseal_updates.append((dst, remote_data))

        for dst, data in flowseal_updates:
            _atomic_write_bytes(dst, data)

        gaming_result = _sync_gaming_lists(settings, session=session)
        _ensure_user_lists_initialized()
        _rebuild_runtime_lists(settings)

        result["ok"] = True
        result["flowseal_updated"] = len(flowseal_updates)
        result["gaming_updated"] = gaming_result.get("updated", 0)
        result["gaming_error"] = gaming_result.get("error", "")
        result["gaming_offline"] = bool(gaming_result.get("offline"))
        result["gaming_silent_missing"] = bool(gaming_result.get("silent_missing"))
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
    return result


def _format_lists_status_text(result: dict, lang: str = "ru") -> str:
    flowseal_updated = int(result.get("flowseal_updated", 0) or 0)
    gaming_updated = int(result.get("gaming_updated", 0) or 0)
    gaming_error = str(result.get("gaming_error", "") or "").strip()
    gaming_silent_missing = bool(result.get("gaming_silent_missing"))

    if lang == "ru":
        parts = []
        if flowseal_updated > 0:
            parts.append(f"Основные списки обновлены: {flowseal_updated}")
        else:
            parts.append("Основные списки актуальны.")

        if gaming_updated > 0:
            parts.append(f"Игровые списки обновлены: {gaming_updated}")
        elif gaming_error and not gaming_silent_missing:
            parts.append("Игровые списки не удалось обновить, используются локальные файлы.")

        return "\n".join(parts)

    parts = []
    if flowseal_updated > 0:
        parts.append(f"Main lists updated: {flowseal_updated}")
    else:
        parts.append("Main lists are up to date.")

    if gaming_updated > 0:
        parts.append(f"Gaming lists updated: {gaming_updated}")
    elif gaming_error and not gaming_silent_missing:
        parts.append("Gaming lists could not be updated; local files are kept.")

    return "\n".join(parts)


def _read_text_full(path: str) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return ""

    for enc in ("utf-8", "cp1251", "utf-16"):
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


def _extract_profile_launch_parts(script_path: str) -> tuple[str, list[str]]:
    raw_text = _read_text_full(script_path)
    if not raw_text:
        raise RuntimeError("Profile script is empty")

    lines = raw_text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        if "%BIN%winws.exe" in line:
            start_index = idx
            break

    if start_index is None:
        raise RuntimeError("winws launch command not found")

    collected = []
    for idx in range(start_index, len(lines)):
        line = lines[idx].strip()
        if not line:
            continue
        collected.append(line)
        if not line.rstrip().endswith("^"):
            break

    if not collected:
        raise RuntimeError("winws launch command is empty")

    marker = '"%BIN%winws.exe"'
    if marker not in collected[0]:
        raise RuntimeError("winws marker not found")

    preamble = collected[0].split(marker, 1)[1].strip()
    if preamble.endswith("^"):
        preamble = preamble[:-1].rstrip()

    segments = []
    for raw_line in collected[1:]:
        segment = raw_line.rstrip()
        if segment.endswith("^"):
            segment = segment[:-1].rstrip()
        if segment:
            segments.append(segment)

    return preamble, segments


def _expand_profile_placeholders(
    text: str,
    core_dir: str,
    game_filter_tcp: str,
    game_filter_udp: str,
) -> str:
    bin_dir = os.path.join(core_dir, "bin") + os.sep
    lists_dir = os.path.join(core_dir, "lists") + os.sep
    game_filter_any = "1024-65535" if (game_filter_tcp != "12" or game_filter_udp != "12") else "12"
    return (
        text.replace("%BIN%", bin_dir)
        .replace("%LISTS%", lists_dir)
        .replace("%GameFilterTCP%", game_filter_tcp)
        .replace("%GameFilterUDP%", game_filter_udp)
        .replace("%GameFilter%", game_filter_any)
        .replace("^!", "!")
        .strip()
    )


def _build_game_mode_winws_command(
    script_path: str,
    core_dir: str,
    settings: QSettings | None = None,
) -> str:
    preamble, segments = _extract_profile_launch_parts(script_path)
    game_filter_tcp, game_filter_udp = _get_game_filter_ports(settings)
    effective_options = _get_effective_game_mode_options(settings)
    main_bypass_enabled = bool(effective_options["main_bypass_enabled"])
    discord_enabled = bool(effective_options["discord_enabled"])
    include_discord_segments = main_bypass_enabled or discord_enabled

    winws_path = os.path.join(core_dir, "bin", "winws.exe")
    expanded_segments = []
    for segment in segments:
        lower = segment.casefold()
        if "list-google.txt" in lower and not main_bypass_enabled:
            continue
        if "discord" in lower and not include_discord_segments:
            continue
        expanded_segments.append(
            _expand_profile_placeholders(segment, core_dir, game_filter_tcp, game_filter_udp)
        )

    expanded_preamble = _expand_profile_placeholders(
        preamble,
        core_dir,
        game_filter_tcp,
        game_filter_udp,
    )
    command_parts = [f'"{winws_path}"']
    if expanded_preamble:
        command_parts.append(expanded_preamble)
    command_parts.extend(seg for seg in expanded_segments if seg)
    return " ".join(command_parts).strip()


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


def _is_winws_running_silent() -> bool:
    try:
        out = subprocess.check_output(
            'tasklist /FI "IMAGENAME eq winws.exe" /NH',
            shell=True,
            text=True,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return "winws.exe" in out.lower()
    except Exception:
        return False


_PENDING_STRATEGY_RESTORE: dict | None = None


def _is_core_strategy_bat_name(name: str) -> bool:
    low = os.path.basename(name or "").lower()
    if not low.endswith(".bat"):
        return False
    if low.startswith("__noupdate__"):
        return False
    return low not in CORE_STRATEGY_RESERVED_BAT_NAMES


def _strategy_bat_names_from_dir(core_dir: str) -> set[str]:
    names: set[str] = set()
    try:
        for name in os.listdir(core_dir):
            if _is_core_strategy_bat_name(name):
                names.add(name.lower())
    except Exception:
        pass
    return names


def _read_core_strategy_files(core_dir: str) -> dict[str, dict]:
    files: dict[str, dict] = {}
    try:
        for name in os.listdir(core_dir):
            if not _is_core_strategy_bat_name(name):
                continue
            path = os.path.join(core_dir, name)
            if not os.path.isfile(path):
                continue
            try:
                with open(path, "rb") as f:
                    files[name.lower()] = {"name": name, "data": f.read()}
            except Exception:
                pass
    except Exception:
        pass
    return files


def _safe_strategy_backup_folder(reason: str) -> str:
    safe_reason = re.sub(r"[^A-Za-z0-9_.-]+", "_", reason or "update").strip("_") or "update"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    base = os.path.join(USER_STRATEGY_BACKUP_DIR, f"{safe_reason}-{stamp}")
    path = base
    n = 2
    while os.path.exists(path):
        path = f"{base}-{n}"
        n += 1
    return path


def _backup_core_strategy_files(strategy_files: dict[str, dict], reason: str) -> str:
    if not strategy_files:
        return ""

    backup_dir = _safe_strategy_backup_folder(reason)
    try:
        os.makedirs(backup_dir, exist_ok=True)
        for item in strategy_files.values():
            name = os.path.basename(str(item.get("name") or ""))
            data = item.get("data")
            if not name or not isinstance(data, (bytes, bytearray)):
                continue
            with open(os.path.join(backup_dir, name), "wb") as f:
                f.write(bytes(data))
        return backup_dir
    except Exception:
        return ""


def _unique_strategy_restore_path(core_dir: str, name: str) -> str:
    stem, ext = os.path.splitext(os.path.basename(name))
    ext = ext or ".bat"
    candidate = os.path.join(core_dir, stem + ext)
    if not os.path.exists(candidate):
        return candidate

    n = 2
    while True:
        candidate = os.path.join(core_dir, f"{stem} (user {n}){ext}")
        if not os.path.exists(candidate):
            return candidate
        n += 1


def _restore_custom_strategy_files(
    core_dir: str,
    strategy_files: dict[str, dict],
    replacement_strategy_names: set[str],
) -> int:
    if not strategy_files:
        return 0

    os.makedirs(core_dir, exist_ok=True)
    restored = 0
    replacement_strategy_names = {str(x).lower() for x in (replacement_strategy_names or set())}

    for low, item in strategy_files.items():
        if low in replacement_strategy_names:
            continue
        name = os.path.basename(str(item.get("name") or ""))
        data = item.get("data")
        if not name or not isinstance(data, (bytes, bytearray)):
            continue
        try:
            dst = _unique_strategy_restore_path(core_dir, name)
            with open(dst, "wb") as f:
                f.write(bytes(data))
            restored += 1
        except Exception:
            pass

    return restored


def wipe_app_dir_if_new_version():
    if not hasattr(sys, "_MEIPASS"):
        return

    global _PENDING_STRATEGY_RESTORE

    prev = _read_text(VERSION_FILE) if os.path.exists(VERSION_FILE) else ""
    if prev == APP_VERSION:
        return

    _force_stop_blockers()

    try:
        source_core_dir = os.path.join(sys._MEIPASS, "core")
        current_strategy_files = _read_core_strategy_files(os.path.join(APP_DIR, "core"))
        replacement_strategy_names = _strategy_bat_names_from_dir(source_core_dir)
        backup_dir = _backup_core_strategy_files(current_strategy_files, f"gui-{prev or 'unknown'}-to-{APP_VERSION}")
        _PENDING_STRATEGY_RESTORE = {
            "files": current_strategy_files,
            "replacement_names": replacement_strategy_names,
            "backup_dir": backup_dir,
        }

        preserved_names = {
            "user",
            os.path.basename(SETTINGS_FILE).lower(),
            os.path.basename(AUTOLOG_FILE).lower(),
            os.path.basename(AUTORESULT_FILE).lower(),
        }
        if os.path.isdir(APP_DIR):
            for name in os.listdir(APP_DIR):
                if name.lower() in preserved_names:
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


def restore_pending_user_strategies_after_extract() -> None:
    global _PENDING_STRATEGY_RESTORE

    pending = _PENDING_STRATEGY_RESTORE
    _PENDING_STRATEGY_RESTORE = None
    if not pending:
        return

    try:
        restored = _restore_custom_strategy_files(
            os.path.join(APP_DIR, "core"),
            pending.get("files") or {},
            pending.get("replacement_names") or set(),
        )
        if restored:
            print(f"Restored custom strategy bat files: {restored}")
    except Exception as e:
        print("Strategy restore error:", e)


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

        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}

        _repair_dns_malw_hosts_for_app_network(settings)
        data = _fetch_latest_flowseal_release_payload(headers, timeout=20)

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
            _sync_ai_dns_if_enabled(settings)
            if lists_result.get("offline"):
                QMessageBox.warning(
                    None,
                    "Обновление",
                    f"У вас уже актуальная версия: {current_ver}\nНе удалось проверить списки, проверьте интернет-соединение."
                )
            else:
                QMessageBox.information(
                    None,
                    "Обновление",
                    f"У вас уже актуальная версия: {current_ver}\n{_format_lists_status_text(lists_result, 'ru')}"
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
        replaced = _replace_core_from_archive(z, core_target)

        settings.setValue(FLOWSEAL_VER_KEY, latest_ver)
        settings.sync()

        _apply_game_mode_state_to_core(settings)
        lists_result = _sync_flowseal_lists(settings)
        _sync_ai_dns_if_enabled(settings)
        list_status = _format_lists_status_text(lists_result, "ru")
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


def _detect_runtime_core_version(settings: QSettings | None = None) -> str:
    qs = _load_settings_if_needed(settings)

    try:
        current_ver = str(qs.value(FLOWSEAL_VER_KEY, "") or "").strip()
    except Exception:
        current_ver = ""
    if current_ver:
        return current_ver

    try:
        svc = os.path.join(APP_DIR, "core", "service.bat")
        if os.path.exists(svc):
            raw = _read_text(svc)
            m = re.search(r'(?im)^\s*set\s+"LOCAL_VERSION\s*=\s*([^"]+)"\s*$', raw)
            current_ver = (m.group(1).strip() if m else "")
    except Exception:
        current_ver = ""

    if not current_ver:
        current_ver = FLOWSEAL_DEFAULT_VER

    try:
        qs.setValue(FLOWSEAL_VER_KEY, current_ver)
        qs.sync()
    except Exception:
        pass

    return current_ver


def _find_flowseal_download_url(release_payload: dict) -> str:
    assets = release_payload.get("assets") or []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = (asset.get("name") or "").lower()
        if name.endswith(".zip"):
            return str(asset.get("browser_download_url") or "").strip()
    return str(release_payload.get("zipball_url") or "").strip()


def _flowseal_archive_url(version: str) -> str:
    tag = (version or "").strip()
    if not tag:
        return ""
    return f"https://github.com/{FLOWSEAL_REPO}/archive/refs/tags/{tag}.zip"


def _fetch_latest_flowseal_release_payload(headers: dict, timeout: float = 20) -> dict:
    api_url = f"https://api.github.com/repos/{FLOWSEAL_REPO}/releases/latest"
    try:
        response = requests.get(api_url, headers=headers, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            return payload
    except requests.exceptions.RequestException:
        pass

    version_response = requests.get(
        FLOWSEAL_VERSION_URL,
        headers={"User-Agent": headers.get("User-Agent", "ZapretGUI-Updater"), "Cache-Control": "no-cache"},
        timeout=min(float(timeout or 20), 12),
    )
    version_response.raise_for_status()
    latest_ver = (version_response.text or "").strip()
    if not latest_ver:
        raise RuntimeError("latest-version-missing")
    return {
        "tag_name": latest_ver,
        "assets": [],
        "zipball_url": _flowseal_archive_url(latest_ver),
        "zapretgui_fallback": "raw-version",
    }


def _fetch_latest_gui_release_payload(headers: dict, timeout: float = 20) -> dict:
    api_url = f"https://api.github.com/repos/{GUI_REPO}/releases/latest"
    response = requests.get(api_url, headers=headers, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("latest-gui-release-missing")
    return payload


def _find_gui_download_url(release_payload: dict) -> str:
    assets = release_payload.get("assets") or []
    preferred = []
    fallback = []
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        lower = name.lower()
        url = str(asset.get("browser_download_url") or "").strip()
        if not url or not lower.endswith(".zip"):
            continue
        if "zapret" in lower and "gui" in lower:
            preferred.append(url)
        else:
            fallback.append(url)
    if preferred:
        return preferred[0]
    if fallback:
        return fallback[0]
    return ""


def _normalize_release_version(tag: str) -> str:
    version = (tag or "").strip()
    if version.startswith(("v", "V")):
        version = version[1:].strip()
    return version


def _check_gui_update_available(
    settings: QSettings | None = None,
    respect_skipped: bool = False,
    timeout: float = 20,
) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "current_ver": APP_VERSION,
        "latest_ver": "",
        "download_url": "",
        "release_url": GUI_RELEASES_URL,
        "skipped": False,
    }

    try:
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        _repair_dns_malw_hosts_for_app_network(qs)
        payload = _fetch_latest_gui_release_payload(headers, timeout=timeout)

        latest_ver = _normalize_release_version(str(payload.get("tag_name") or ""))
        if not latest_ver:
            result["status"] = "error"
            result["error"] = "latest-gui-version-missing"
            return result

        result["latest_ver"] = latest_ver

        try:
            is_newer = _version_key(latest_ver) > _version_key(APP_VERSION)
        except Exception:
            is_newer = latest_ver != APP_VERSION

        if not is_newer:
            result["ok"] = True
            result["status"] = "up-to-date"
            return result

        skipped_ver = ""
        if respect_skipped:
            try:
                skipped_ver = str(qs.value(GUI_SKIPPED_UPDATE_KEY, "") or "").strip()
            except Exception:
                skipped_ver = ""
            if skipped_ver and skipped_ver == latest_ver:
                result["ok"] = True
                result["status"] = "skipped"
                result["skipped"] = True
                return result

        download_url = _find_gui_download_url(payload)
        if not download_url:
            result["status"] = "error"
            result["error"] = "gui-download-url-missing"
            return result

        result["ok"] = True
        result["status"] = "update-available"
        result["download_url"] = download_url
        return result

    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


def _check_all_updates_async(
    settings: QSettings | None = None,
    should_cancel=None,
    phase_callback=None,
) -> dict:
    def _phase(name: str) -> None:
        try:
            if phase_callback:
                phase_callback(name)
        except Exception:
            pass

    qs = _load_settings_if_needed(settings)
    _phase("gui-version")
    gui_result = _check_gui_update_available(qs, respect_skipped=False, timeout=20)
    if gui_result.get("ok") and gui_result.get("status") == "update-available":
        return {
            "ok": True,
            "status": "gui-update-available",
            "current_ver": str(gui_result.get("current_ver") or APP_VERSION),
            "latest_ver": str(gui_result.get("latest_ver") or ""),
            "download_url": str(gui_result.get("download_url") or ""),
            "release_url": str(gui_result.get("release_url") or GUI_RELEASES_URL),
            "gui_result": gui_result,
        }

    core_result = _check_flowseal_update_async(
        qs,
        should_cancel=should_cancel,
        phase_callback=phase_callback,
    )
    core_result["gui_checked"] = bool(gui_result.get("ok"))
    core_result["gui_current_ver"] = APP_VERSION
    core_result["gui_latest_ver"] = str(gui_result.get("latest_ver") or APP_VERSION)
    core_result["gui_error"] = str(gui_result.get("error") or "")
    core_result["gui_offline"] = bool(gui_result.get("offline"))
    return core_result


def _current_gui_executable_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.realpath(sys.executable)
    return os.path.realpath(sys.argv[0])


def _download_gui_update_archive(download_url: str, latest_ver: str) -> str:
    update_dir = os.path.join(APP_DIR, "updates")
    os.makedirs(update_dir, exist_ok=True)

    safe_ver = re.sub(r"[^A-Za-z0-9_.-]+", "_", latest_ver or "latest")
    fd, part_path = tempfile.mkstemp(prefix=f"ZapretGUI-{safe_ver}-", suffix=".zip.part", dir=update_dir)
    os.close(fd)
    final_path = part_path[:-5]

    headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/octet-stream"}
    try:
        with requests.get(download_url, headers=headers, timeout=90, stream=True) as response:
            response.raise_for_status()
            with open(part_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
        if os.path.getsize(part_path) < 1024:
            raise RuntimeError("downloaded-gui-archive-too-small")
        if os.path.exists(final_path):
            os.remove(final_path)
        os.replace(part_path, final_path)
        return final_path
    except Exception:
        try:
            if os.path.exists(part_path):
                os.remove(part_path)
        except Exception:
            pass
        raise


def _write_gui_update_script() -> str:
    script_dir = os.path.join(APP_DIR, "updates")
    os.makedirs(script_dir, exist_ok=True)
    script_path = os.path.join(script_dir, "apply_gui_update.ps1")
    script = r'''
param(
    [Parameter(Mandatory=$true)][string]$ArchivePath,
    [Parameter(Mandatory=$true)][string]$InstallDir,
    [Parameter(Mandatory=$true)][string]$OldExePath,
    [Parameter(Mandatory=$true)][int]$CurrentPid,
    [string]$NewVersion = ""
)

$ErrorActionPreference = "Stop"
$LogPath = Join-Path $InstallDir "ZapretGUI-update.log"

function Write-UpdateLog([string]$Message) {
    try {
        $stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
        Add-Content -LiteralPath $LogPath -Value "[$stamp] $Message" -Encoding UTF8
    } catch {}
}

function Copy-TreeOverwrite([string]$Source, [string]$Destination, [bool]$ProtectRoot = $false) {
    if (!(Test-Path -LiteralPath $Destination)) {
        New-Item -ItemType Directory -Path $Destination -Force | Out-Null
    }

    $protectedRootNames = @(
        "user",
        "core",
        "updates",
        "settings.ini",
        ".app_version",
        "autotest_last.log",
        "autotest_result.json",
        "dns_malw_hosts_backup.txt",
        "dns_malw_hosts_cache.txt",
        "_no_update_input.txt",
        "ZapretGUI-update.log"
    )

    Get-ChildItem -LiteralPath $Source -Force | ForEach-Object {
        if ($ProtectRoot -and ($protectedRootNames -contains $_.Name)) {
            Write-UpdateLog ("Protected app-data item kept: " + $_.Name)
        } else {
            $dst = Join-Path $Destination $_.Name
            if ($_.PSIsContainer) {
                Copy-TreeOverwrite -Source $_.FullName -Destination $dst -ProtectRoot $false
            } else {
                Copy-Item -LiteralPath $_.FullName -Destination $dst -Force
            }
        }
    }
}

function Update-ZapretShortcuts([string]$OldExe, [string]$NewExe, [string]$WorkDir) {
    try {
        $shell = New-Object -ComObject WScript.Shell
        $shortcutRoots = @(
            [Environment]::GetFolderPath("Desktop"),
            [Environment]::GetFolderPath("CommonDesktopDirectory"),
            [Environment]::GetFolderPath("Programs"),
            [Environment]::GetFolderPath("Startup")
        ) | Where-Object { $_ -and (Test-Path -LiteralPath $_) } | Select-Object -Unique

        foreach ($root in $shortcutRoots) {
            Get-ChildItem -LiteralPath $root -Filter "*.lnk" -Recurse -ErrorAction SilentlyContinue | ForEach-Object {
                try {
                    $lnk = $shell.CreateShortcut($_.FullName)
                    $target = [string]$lnk.TargetPath
                    $name = [string]$_.Name
                    $targetName = [IO.Path]::GetFileName($target)
                    $shouldUpdate = $false
                    if ($target -and ([string]::Compare($target, $OldExe, $true) -eq 0)) { $shouldUpdate = $true }
                    if ($name -match "Zapret.?GUI|Zapret GUI") { $shouldUpdate = $true }
                    if ($targetName -match "Zapret.?GUI|Zapret GUI") { $shouldUpdate = $true }
                    if ($shouldUpdate) {
                        $lnk.TargetPath = $NewExe
                        $lnk.WorkingDirectory = $WorkDir
                        $lnk.IconLocation = $NewExe
                        $lnk.Save()
                    }
                } catch {}
            }
        }

        $desktop = [Environment]::GetFolderPath("Desktop")
        if ($desktop -and (Test-Path -LiteralPath $desktop)) {
            $mainShortcut = Join-Path $desktop "Zapret GUI.lnk"
            $lnk = $shell.CreateShortcut($mainShortcut)
            $lnk.TargetPath = $NewExe
            $lnk.WorkingDirectory = $WorkDir
            $lnk.IconLocation = $NewExe
            $lnk.Save()
        }
    } catch {
        Write-UpdateLog ("Shortcut update failed: " + $_.Exception.Message)
    }
}

try {
    Write-UpdateLog "GUI update started"
    try { Wait-Process -Id $CurrentPid -Timeout 45 -ErrorAction SilentlyContinue } catch {}
    Start-Sleep -Milliseconds 800

    if (!(Test-Path -LiteralPath $ArchivePath)) { throw "Archive not found: $ArchivePath" }
    if (!(Test-Path -LiteralPath $InstallDir)) { New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null }

    $tempRoot = Join-Path ([IO.Path]::GetTempPath()) ("ZapretGUI-update-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Path $tempRoot -Force | Out-Null

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    [System.IO.Compression.ZipFile]::ExtractToDirectory($ArchivePath, $tempRoot)

    $exeCandidates = Get-ChildItem -LiteralPath $tempRoot -Recurse -File -Filter "*.exe" | Sort-Object `
        @{ Expression = { if ($_.Name -match "Zapret.?GUI|Zapret GUI") { 0 } else { 1 } } }, FullName
    if (!$exeCandidates -or $exeCandidates.Count -lt 1) { throw "No exe file found in archive" }

    $sourceExe = $exeCandidates[0].FullName
    $sourceRoot = Split-Path -Parent $sourceExe
    $appDataDir = Join-Path $env:USERPROFILE "ZapretGUI"
    $protectAppData = ([string]::Compare(
        ([IO.Path]::GetFullPath($InstallDir)).TrimEnd("\"),
        ([IO.Path]::GetFullPath($appDataDir)).TrimEnd("\"),
        $true
    ) -eq 0)
    Copy-TreeOverwrite -Source $sourceRoot -Destination $InstallDir -ProtectRoot $protectAppData

    $relativeExe = $sourceExe.Substring($sourceRoot.Length).TrimStart("\", "/")
    $newExe = Join-Path $InstallDir $relativeExe
    if (!(Test-Path -LiteralPath $newExe)) {
        $newExe = Join-Path $InstallDir (Split-Path -Leaf $sourceExe)
    }
    if (!(Test-Path -LiteralPath $newExe)) { throw "Updated exe not found after copy" }

    Update-ZapretShortcuts -OldExe $OldExePath -NewExe $newExe -WorkDir $InstallDir

    try {
        schtasks /Query /TN "ZapretGUI" | Out-Null
        if ($LASTEXITCODE -eq 0) {
            schtasks /Create /TN "ZapretGUI" /SC ONLOGON /RL HIGHEST /F /TR "`"$newExe`"" | Out-Null
        }
    } catch {
        Write-UpdateLog ("Autostart task update failed: " + $_.Exception.Message)
    }

    try { Remove-Item -LiteralPath $ArchivePath -Force -ErrorAction SilentlyContinue } catch {}
    try { Remove-Item -LiteralPath $tempRoot -Recurse -Force -ErrorAction SilentlyContinue } catch {}

    Write-UpdateLog "Starting updated GUI: $newExe"
    Start-Process -FilePath $newExe -WorkingDirectory $InstallDir
} catch {
    Write-UpdateLog ("GUI update failed: " + $_.Exception.Message)
    try {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "Zapret GUI update failed. Details are in:`n$LogPath",
            "Zapret GUI updater"
        ) | Out-Null
    } catch {}
}
'''
    with open(script_path, "w", encoding="utf-8") as f:
        f.write(script.lstrip())
    return script_path


def _schedule_gui_update_restart(latest_ver: str, download_url: str) -> dict:
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "latest_ver": latest_ver,
        "download_url": download_url,
    }

    try:
        current_exe = _current_gui_executable_path()
        if not current_exe.lower().endswith(".exe"):
            result["status"] = "unsupported"
            result["error"] = "gui-self-update-requires-exe"
            return result

        archive_path = _download_gui_update_archive(download_url, latest_ver)
        with zipfile.ZipFile(archive_path, "r") as archive:
            bad_member = archive.testzip()
            if bad_member:
                raise zipfile.BadZipFile(f"bad member: {bad_member}")
        script_path = _write_gui_update_script()
        install_dir = os.path.dirname(current_exe)

        args = [
            "powershell.exe",
            "-NoProfile",
            "-ExecutionPolicy", "Bypass",
            "-File", script_path,
            "-ArchivePath", archive_path,
            "-InstallDir", install_dir,
            "-OldExePath", current_exe,
            "-CurrentPid", str(os.getpid()),
            "-NewVersion", latest_ver,
        ]
        subprocess.Popen(
            args,
            cwd=install_dir,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            close_fds=True,
        )

        result["ok"] = True
        result["status"] = "gui-restart-scheduled"
        result["archive_path"] = archive_path
        result["script_path"] = script_path
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except zipfile.BadZipFile:
        result["status"] = "bad-zip"
        result["error"] = "bad-zip"
    except PermissionError as e:
        result["status"] = "permission"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


def _replace_core_from_archive(archive: zipfile.ZipFile, core_target: str) -> int:
    driver_names = {"windivert64.sys", "windivert32.sys"}
    driver_backups: dict[str, bytes] = {}

    names = [name for name in archive.namelist() if name and not name.startswith("__MACOSX/")]
    top_levels = set()
    for name in names:
        segment = name.split("/", 1)[0]
        if segment:
            top_levels.add(segment)

    root_prefix = ""
    if len(top_levels) == 1:
        root_prefix = next(iter(top_levels)) + "/"

    current_strategy_files = _read_core_strategy_files(core_target)
    _backup_core_strategy_files(current_strategy_files, "core-update")
    replacement_strategy_names: set[str] = set()
    for member in names:
        if member.endswith("/"):
            continue
        if root_prefix and not member.startswith(root_prefix):
            continue
        rel = member[len(root_prefix):] if root_prefix else member
        if not rel or "/" in rel or "\\" in rel:
            continue
        if _is_core_strategy_bat_name(rel):
            replacement_strategy_names.add(os.path.basename(rel).lower())

    bin_dir = os.path.join(core_target, "bin")
    for driver in driver_names:
        path = os.path.join(bin_dir, driver)
        try:
            with open(path, "rb") as f:
                driver_backups[driver] = f.read()
        except Exception:
            pass

    os.makedirs(core_target, exist_ok=True)
    for name in os.listdir(core_target):
        path = os.path.join(core_target, name)
        if os.path.isdir(path):
            shutil.rmtree(path, ignore_errors=False)
        else:
            os.remove(path)

    replaced = 0
    extracted_drivers: set[str] = set()
    core_root = os.path.abspath(core_target)
    core_prefix = core_root + os.sep

    for member in names:
        if member.endswith("/"):
            continue
        if root_prefix and not member.startswith(root_prefix):
            continue

        rel = member[len(root_prefix):] if root_prefix else member
        if not rel:
            continue

        dst_path = os.path.abspath(os.path.join(core_target, rel))
        if dst_path != core_root and not dst_path.startswith(core_prefix):
            continue

        os.makedirs(os.path.dirname(dst_path), exist_ok=True)

        with archive.open(member) as src, open(dst_path, "wb") as dst:
            dst.write(src.read())

        if os.path.basename(dst_path).lower() in driver_names:
            extracted_drivers.add(os.path.basename(dst_path).lower())
        replaced += 1

    for driver, data in driver_backups.items():
        if driver in extracted_drivers:
            continue
        path = os.path.join(bin_dir, driver)
        try:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "wb") as f:
                f.write(data)
            replaced += 1
        except Exception:
            pass

    replaced += _restore_custom_strategy_files(core_target, current_strategy_files, replacement_strategy_names)

    return replaced


def _check_flowseal_update_async(
    settings: QSettings | None = None,
    should_cancel=None,
    phase_callback=None,
) -> dict:
    def _cancelled() -> bool:
        try:
            return bool(should_cancel and should_cancel())
        except Exception:
            return False

    def _phase(name: str) -> None:
        try:
            if phase_callback:
                phase_callback(name)
        except Exception:
            pass

    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "current_ver": "",
        "latest_ver": "",
        "download_url": "",
        "lists_result": {},
        "ai_dns_error": "",
    }

    _phase("version")

    if _is_winws_running_silent():
        result["status"] = "winws-running"
        result["error"] = "winws-running"
        return result

    try:
        if _cancelled():
            result["status"] = "cancelled"
            result["error"] = "cancelled"
            return result

        current_ver = _detect_runtime_core_version(qs)
        result["current_ver"] = current_ver

        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        _repair_dns_malw_hosts_for_app_network(qs)
        payload = _fetch_latest_flowseal_release_payload(headers, timeout=20)

        if _cancelled():
            result["status"] = "cancelled"
            result["error"] = "cancelled"
            return result

        tag = (payload.get("tag_name") or "").strip()
        latest_ver = tag[1:] if tag.startswith("v") else tag
        latest_ver = (latest_ver or "").strip()
        if not latest_ver:
            result["status"] = "error"
            result["error"] = "latest-version-missing"
            return result

        result["latest_ver"] = latest_ver

        try:
            is_newer = _version_key(latest_ver) > _version_key(current_ver)
        except Exception:
            is_newer = latest_ver != current_ver

        if is_newer:
            download_url = _find_flowseal_download_url(payload)
            if not download_url:
                result["status"] = "error"
                result["error"] = "download-url-missing"
                return result

            result["ok"] = True
            result["status"] = "update-available"
            result["download_url"] = download_url
            return result

        if _cancelled():
            result["status"] = "cancelled"
            result["error"] = "cancelled"
            return result

        _phase("lists")
        lists_result = _sync_flowseal_lists(qs)
        ai_result = _sync_ai_dns_if_enabled(qs)
        result["ok"] = True
        result["status"] = "up-to-date"
        result["lists_result"] = lists_result
        result["ai_dns_error"] = str(ai_result.get("error") or "")
        return result

    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)
    return result


def _apply_flowseal_update_async(latest_ver: str, download_url: str, settings: QSettings | None = None) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "status": "",
        "error": "",
        "offline": False,
        "latest_ver": latest_ver,
        "replaced": 0,
        "core_target": os.path.join(APP_DIR, "core"),
        "lists_result": {},
        "ai_dns_error": "",
    }

    if _is_winws_running_silent():
        result["status"] = "winws-running"
        result["error"] = "winws-running"
        return result

    try:
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        response = requests.get(download_url, headers=headers, timeout=60)
        response.raise_for_status()
        archive = zipfile.ZipFile(io.BytesIO(response.content))

        core_target = os.path.join(APP_DIR, "core")
        os.makedirs(core_target, exist_ok=True)
        os.makedirs(USER_DIR, exist_ok=True)
        replaced = _replace_core_from_archive(archive, core_target)

        qs.setValue(FLOWSEAL_VER_KEY, latest_ver)
        qs.sync()

        _apply_game_mode_state_to_core(qs)
        lists_result = _sync_flowseal_lists(qs)
        ai_result = _sync_ai_dns_if_enabled(qs)

        result["ok"] = True
        result["status"] = "updated"
        result["replaced"] = replaced
        result["lists_result"] = lists_result
        result["ai_dns_error"] = str(ai_result.get("error") or "")
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["status"] = "offline"
        result["error"] = str(e)
    except zipfile.BadZipFile:
        result["status"] = "bad-zip"
        result["error"] = "bad-zip"
    except PermissionError as e:
        result["status"] = "permission"
        result["error"] = str(e)
    except Exception as e:
        result["status"] = "error"
        result["error"] = str(e)

    return result


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
        headers = {"User-Agent": "ZapretGUI-Updater", "Accept": "application/vnd.github+json"}
        data = _fetch_latest_flowseal_release_payload(headers, timeout=12)
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
        'Enable': 'Включить',
        'Disable': 'Выключить',
        'Telegram Mode': 'Telegram Mode',
        'Add Domain': 'Добавить домен',
        'Exclude Domain': 'Исключить домен',
        'Add IP': 'Добавить IP',
        'Exclude IP': 'Исключить IP',
        'Game Mode': 'Игровой режим',
        'Game Mode Settings': 'Настройки игрового режима',
        'Game Mode Placeholder': 'Настройки игрового режима появятся позже.',
        'Instruction Text': """
        <b>1.</b> Выберите из выпадающего списка <b>профиль настроек</b>, затем нажмите на <span style="display:inline-block; padding:2px 8px; border-radius:8px; background:#d94b4b; color:white;"><b>большую красную кнопку</b></span>, чтобы запустить обход блокировок. Если выбранный профиль не сработал, переходите к следующему.<br><br>
        <b>2.</b> Проверить, работает ли текущий профиль можно, например на: <a href="https://www.youtube.com">@YouTube</a> или <a href="https://discord.com/">@Discord</a><br><br>
        <b>3.</b> В настройках можно включить <b>Автозапуск</b> вместе с Windows и выбрать профиль для автозапуска. А также проверить обновления списков и приложения.<br><br>
        <b>4.</b> Игровой режим <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>G</b></span> активирует Game Filters, чтобы обходить блокировки игровых сервисов. Его можно настроить по <b>шестерёнке</b> рядом с ним.<br><br>
        <b>5.</b> Для автоподбора профилей можно воспользоваться кнопкой <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>A</b></span>. Это может занять несколько минут.<br><br>
        <b>6.</b> Кнопка <span style="display:inline-block; min-width:22px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>Ai</b></span> открывает для доступ к недоступным нейросетям БЕЗ VPN.<br><br>
        <b>7.</b> Инструкцию по использованию Менеджера сайтов можно открыть по кнопке <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>i</b></span> внутри окна, либо по этой кнопке:
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
        'Enable': 'Enable',
        'Disable': 'Disable',
        'Telegram Mode': 'Telegram Mode',
        'Add Domain': 'Add domain',
        'Exclude Domain': 'Exclude domain',
        'Add IP': 'Add IP',
        'Exclude IP': 'Exclude IP',
        'Game Mode': 'Game mode',
        'Game Mode Settings': 'Game mode settings',
        'Game Mode Placeholder': 'Game mode settings will be added later.',
        'Instruction Text': """
        <b>1.</b> Select a <b>profile</b> from the dropdown list, then click the <span style="display:inline-block; padding:2px 8px; border-radius:8px; background:#d94b4b; color:white;"><b>big red button</b></span> to start the bypass. <i>By default, profile <b>General</b> is used.</i><br><br>
        <b>2.</b> If the selected profile does not work, stop bypass with the <span style="display:inline-block; padding:2px 8px; border-radius:8px; background:#2db45f; color:white;"><b>green button</b></span> and choose another profile.<br><br>
        <b>3.</b> In settings you can enable <b>Autostart</b> with Windows and choose a profile for autostart.<br><br>
        <b>4.</b> To check if bypass works — try opening websites that were blocked for you, or test on: <a href="https://www.youtube.com">@YouTube</a> or <a href="https://discord.com/">@Discord</a><br><br>
        <b>5.</b> Game mode <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>G</b></span> enables Game Filters for blocked game services. Use the gear button next to it for settings.<br><br>
        <b>6.</b> Button <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>A</b></span> runs the old quick test of ready-made Flowseal profiles. It usually takes a few minutes.<br><br>
        <b>7.</b> Button <span style="display:inline-block; min-width:22px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>Ai</b></span> enables Ai DNS for restricted neural-network services.<br><br>
        <b>8.</b> You can open the Site Manager guide from the <span style="display:inline-block; min-width:18px; padding:2px 7px; border-radius:999px; background:#2db45f; color:white;"><b>i</b></span> button inside that window, or by pressing this button:
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

_DETACHED_UPDATE_WORKERS = []


def _show_gui_update_question(parent, lang: str, result: dict, allow_skip: bool = False) -> tuple[bool, bool]:
    latest_ver = str(result.get("latest_ver") or "")
    current_ver = str(result.get("current_ver") or APP_VERSION)
    release_url = str(result.get("release_url") or GUI_RELEASES_URL)

    msg = QMessageBox(parent)
    msg.setWindowTitle("Обновление GUI" if lang == "ru" else "GUI update")
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setText(
        (
            f"Доступна новая версия GUI: {latest_ver}\n"
            f"Текущая версия GUI: {current_ver}\n\n"
            "Будет скачан zip-архив релиза, текущая версия закроется, "
            "файлы будут распакованы поверх запущенной версии, ярлык будет обновлён, "
            "после чего запустится новая версия.\n\n"
            "Обновить сейчас?"
        )
        if lang == "ru" else
        (
            f"New GUI version available: {latest_ver}\n"
            f"Current GUI version: {current_ver}\n\n"
            "The release zip will be downloaded, the current app will close, "
            "files will be unpacked over the running version, shortcuts will be updated, "
            "and the new version will be started.\n\n"
            "Update now?"
        )
    )
    msg.setInformativeText(release_url)
    skip_cb = None
    if allow_skip:
        skip_cb = QCheckBox("Пропустить это обновление" if lang == "ru" else "Skip this update")
        msg.setCheckBox(skip_cb)

    btn_yes = msg.addButton("Да" if lang == "ru" else "Yes", QMessageBox.ButtonRole.YesRole)
    msg.addButton("Нет" if lang == "ru" else "No", QMessageBox.ButtonRole.NoRole)
    msg.exec()

    update_now = msg.clickedButton() == btn_yes
    skip = bool(skip_cb and skip_cb.isChecked() and not update_now)
    return update_now, skip


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

    def _start_update_worker(self, mode: str, latest_ver: str = "", download_url: str = "") -> None:
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
        worker = ReleaseUpdateWorker(mode, latest_ver, download_url, self)
        self._update_worker = worker
        worker.finished_update.connect(self._on_update_worker_finished)
        worker.start()

    def _format_update_result_text(self, result: dict) -> str:
        status = str(result.get("status") or "")
        current_ver = str(result.get("current_ver") or "")
        latest_ver = str(result.get("latest_ver") or "")
        lists_result = result.get("lists_result") or {}

        if self.lang == "ru":
            if status == "up-to-date":
                if result.get("gui_checked"):
                    gui_ver = str(result.get("gui_current_ver") or APP_VERSION)
                    head = f"GUI: актуальная версия {gui_ver}\nCore: актуальная версия {current_ver}"
                else:
                    head = f"У вас уже актуальная версия: {current_ver}"
                body = _format_lists_status_text(lists_result, "ru") if lists_result else ""
                return f"{head}\n{body}".strip()
            if status == "updated":
                head = f"Core обновлён до: {latest_ver}"
                body = _format_lists_status_text(lists_result, "ru") if lists_result else ""
                return f"{head}\n{body}".strip()
            if status == "gui-restart-scheduled":
                return "GUI обновляется. Приложение сейчас перезапустится."
            if status == "unsupported":
                return "Автообновление GUI доступно только для exe-версии приложения."
            if status == "winws-running":
                return "Сначала выключите обход, затем повторите проверку."
            if status == "offline":
                return "Не удалось проверить обновления: проверьте интернет-соединение."
            if status == "bad-zip":
                return "Скачанный архив повреждён или не является zip."
            if status == "permission":
                return "Не удалось записать файлы core. Остановите обход и повторите."
            return "Не удалось завершить проверку обновлений."

        if status == "up-to-date":
            if result.get("gui_checked"):
                gui_ver = str(result.get("gui_current_ver") or APP_VERSION)
                head = f"GUI: latest version {gui_ver}\nCore: latest version {current_ver}"
            else:
                head = f"You already have the latest version: {current_ver}"
            body = _format_lists_status_text(lists_result, "en") if lists_result else ""
            return f"{head}\n{body}".strip()
        if status == "updated":
            head = f"Core updated to: {latest_ver}"
            body = _format_lists_status_text(lists_result, "en") if lists_result else ""
            return f"{head}\n{body}".strip()
        if status == "gui-restart-scheduled":
            return "The GUI is updating. The app will restart now."
        if status == "unsupported":
            return "GUI auto-update is available only for the exe build."
        if status == "winws-running":
            return "Stop the bypass first, then check again."
        if status == "offline":
            return "Could not check updates: check your internet connection."
        if status == "bad-zip":
            return "The downloaded archive is damaged or is not a zip file."
        if status == "permission":
            return "Could not write core files. Stop the bypass and try again."
        return "Could not finish the update check."

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

        if result.get("status") == "cancelled":
            self._set_update_busy(False, "")
            if self._update_close_after_finish:
                self.close()
            return

        if mode == "apply-gui":
            self._finish_update_ui(result)
            if result.get("ok") and result.get("status") == "gui-restart-scheduled":
                parent = self.parent()
                if parent and hasattr(parent, "_shutdown_and_quit"):
                    QTimer.singleShot(250, parent._shutdown_and_quit)
                else:
                    QTimer.singleShot(250, QApplication.instance().quit)
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

    def run(self):
        try:
            settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
            result = _sync_flowseal_lists(settings)
            ai_result = _sync_ai_dns_if_enabled(settings)
            result["ai_dns_error"] = str(ai_result.get("error") or "")
            result["gui_update"] = _check_gui_update_available(settings, respect_skipped=True, timeout=10)
        except Exception as e:
            result = {
                "ok": False,
                "offline": False,
                "flowseal_updated": 0,
                "gaming_updated": 0,
                "gaming_error": "",
                "gaming_offline": False,
                "gaming_silent_missing": False,
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


class ReleaseUpdateWorker(QThread):
    finished_update = pyqtSignal(str, dict)

    def __init__(self, mode: str, latest_ver: str = "", download_url: str = "", parent=None):
        super().__init__(parent)
        self.mode = (mode or "check").strip().lower()
        self.latest_ver = latest_ver
        self.download_url = download_url
        self.phase = "version" if self.mode in {"check", "check-core"} else "apply"

    def run(self):
        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
        if self.mode == "apply":
            self.phase = "apply"
            result = _apply_flowseal_update_async(self.latest_ver, self.download_url, settings)
        elif self.mode == "apply-gui":
            self.phase = "apply-gui"
            result = _schedule_gui_update_restart(self.latest_ver, self.download_url)
        elif self.mode == "check-core":
            result = _check_flowseal_update_async(
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
            "error": "",
        }
        try:
            if self.action == "enable":
                _set_telegram_mode_enabled(True, settings)
                _set_telegram_last_error("", settings)
                _apply_telegram_mode_files(True, settings)
                if self.proxy_controller is None:
                    raise RuntimeError("Telegram proxy controller is not available")
                self.proxy_controller.start(result["proxy_port"])
                result["enabled"] = True
                result["proxy_running"] = self.proxy_controller.is_running()
                result["ok"] = True
            elif self.action == "disable":
                _set_telegram_mode_enabled(False, settings)
                if self.proxy_controller is not None:
                    self.proxy_controller.stop()
                _apply_telegram_mode_files(False, settings)
                _set_telegram_last_error("", settings)
                result["enabled"] = False
                result["proxy_running"] = False
                result["ok"] = True
            elif self.action == "restore":
                if _is_telegram_mode_enabled(settings):
                    _apply_telegram_mode_files(True, settings)
                    if self.proxy_controller is None:
                        raise RuntimeError("Telegram proxy controller is not available")
                    self.proxy_controller.start(result["proxy_port"])
                    result["enabled"] = True
                    result["proxy_running"] = self.proxy_controller.is_running()
                else:
                    _apply_telegram_mode_files(False, settings)
                    result["enabled"] = False
                    result["proxy_running"] = False
                _set_telegram_last_error("", settings)
                result["ok"] = True
            else:
                raise RuntimeError("Unknown Telegram Mode action")
        except Exception as e:
            result["error"] = str(e)
            result["enabled"] = _is_telegram_mode_enabled(settings)
            try:
                result["proxy_running"] = bool(
                    self.proxy_controller is not None and self.proxy_controller.is_running()
                )
            except Exception:
                result["proxy_running"] = False
            _set_telegram_last_error(result["error"], settings)

        self.finished_telegram.emit(self.action, result)

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


class AutoProgressDialog(StyledDialog):
    canceled = pyqtSignal()

    def __init__(self, title: str, left_text: str, cancel_text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(330, 270)

        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        flags = self.windowFlags()
        flags &= ~Qt.WindowType.WindowMaximizeButtonHint
        self.setWindowFlags(flags)

        root = _make_window_root_layout(self)
        title_bar = self.install_title_bar(root, title)
        v = _make_window_content_layout(root, self, margins=(12, 10, 12, 12), spacing=10)
        try:
            title_bar.close_btn.clicked.disconnect()
        except Exception:
            pass
        title_bar.close_btn.clicked.connect(self._on_cancel)

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

    def hitButton(self, pos):
        return self.rect().contains(pos)

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


class ModernCheckBox(QCheckBox):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QCheckBox { background: transparent; spacing: 0; }")

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(24 + fm.horizontalAdvance(self.text()) + 10, max(24, fm.height() + 8))

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        box_size = 18
        box = QRectF(1, (self.height() - box_size) / 2.0, box_size, box_size)
        checked = self.isChecked()
        hover = self.underMouse()
        enabled = self.isEnabled()

        if checked:
            fill = QLinearGradient(box.topLeft(), box.bottomRight())
            fill.setColorAt(0.0, QColor("#39d879" if enabled else "#5c8f6d"))
            fill.setColorAt(1.0, QColor("#238c4b" if enabled else "#476352"))
            border = QColor(91, 232, 143, 230 if enabled else 120)
        else:
            fill = QLinearGradient(box.topLeft(), box.bottomRight())
            fill.setColorAt(0.0, QColor(255, 255, 255, 22 if enabled else 10))
            fill.setColorAt(1.0, QColor(255, 255, 255, 8 if enabled else 4))
            border = QColor(255, 255, 255, 74 if enabled else 32)

        if hover and enabled and not checked:
            border = QColor(45, 180, 95, 150)

        p.setPen(QPen(border, 1.2))
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(box, 5, 5)

        if checked:
            pen = QPen(QColor(255, 255, 255, 242 if enabled else 150), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(QPoint(int(box.left() + 4), int(box.center().y() + 1)), QPoint(int(box.left() + 8), int(box.bottom() - 5)))
            p.drawLine(QPoint(int(box.left() + 8), int(box.bottom() - 5)), QPoint(int(box.right() - 4), int(box.top() + 5)))

        text_rect = QRectF(box.right() + 8, 0, max(0, self.width() - box.right() - 8), self.height())
        p.setPen(QColor(242, 242, 242, 245 if enabled else 120))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        p.end()


class StableComboPopupView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUniformItemSizes(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        self.viewport().setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMouseTracking(True)
        self.verticalScrollBar().valueChanged.connect(lambda _=0: self.viewport().update())

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor("#171717"))
        pal.setColor(QPalette.ColorRole.Window, QColor("#171717"))
        self.setPalette(pal)
        self.viewport().setPalette(pal)

        self.setStyleSheet("""
            QListView {
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: #171717;
                color: #f3f3f3;
                padding: 4px;
                outline: none;
                selection-background-color: rgba(45,180,95,0.34);
                selection-color: #ffffff;
            }
            QListView::item {
                min-height: 26px;
                padding: 5px 8px;
                border-radius: 6px;
                background: transparent;
            }
            QListView::item:hover {
                background: rgba(255,255,255,0.075);
            }
            QListView::item:selected {
                background: rgba(45,180,95,0.34);
            }
        """)

    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), QColor("#171717"))
        painter.end()
        super().paintEvent(event)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self.viewport().update()


class StableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stableComboBox")
        self._hovered = False
        self._popup_open = False
        self._arrow_progress = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self._arrow_anim = QPropertyAnimation(self, b"arrowProgress", self)
        self._arrow_anim.setDuration(150)
        self._arrow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setMinimumHeight(31)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        popup_view = StableComboPopupView(self)
        self.setView(popup_view)
        self.setMaxVisibleItems(10)

    def getArrowProgress(self) -> float:
        return float(self._arrow_progress)

    def setArrowProgress(self, value: float) -> None:
        self._arrow_progress = max(0.0, min(1.0, float(value)))
        self.update()

    arrowProgress = pyqtProperty(float, fget=getArrowProgress, fset=setArrowProgress)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(max(hint.width(), 120), max(hint.height(), 31))

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(max(hint.width(), 96), 31)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def _animate_arrow(self, target: float) -> None:
        try:
            self._arrow_anim.stop()
            self._arrow_anim.setStartValue(self._arrow_progress)
            self._arrow_anim.setEndValue(float(target))
            self._arrow_anim.start()
        except Exception:
            self.setArrowProgress(target)

    def showPopup(self) -> None:
        try:
            view = self.view()
            if view is not None:
                popup_width = max(self.width(), self.sizeHint().width())
                view.setMinimumWidth(popup_width)
                view.setMaximumWidth(max(popup_width + 2, popup_width))
        except Exception:
            pass
        self._popup_open = True
        self._animate_arrow(1.0)
        super().showPopup()
        self._fit_popup_window()
        self._shape_popup_window()
        QTimer.singleShot(0, lambda: (self._fit_popup_window(), self._shape_popup_window()))

    def _fit_popup_window(self) -> None:
        try:
            view = self.view()
            popup = view.window()
            visible_rows = max(1, min(int(self.maxVisibleItems()), int(self.count())))
            row_h = view.sizeHintForRow(0)
            if row_h <= 0:
                row_h = 30
            target_h = visible_rows * row_h + 10
            popup.resize(max(popup.width(), self.width()), target_h)
            view.resize(popup.size())
        except Exception:
            pass

    def _shape_popup_window(self) -> None:
        try:
            popup = self.view().window()
            popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            popup.setAutoFillBackground(True)
            popup.setStyleSheet("background: #171717;")
            _update_rounded_window_mask(popup, 8.0)
        except Exception:
            pass

    def hidePopup(self) -> None:
        super().hidePopup()
        self._popup_open = False
        self._animate_arrow(0.0)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        enabled = self.isEnabled()
        active = self._popup_open or self.hasFocus()
        bg_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if active:
            bg_grad.setColorAt(0.00, QColor("#313a35"))
            bg_grad.setColorAt(0.34, QColor("#29312d"))
            bg_grad.setColorAt(0.72, QColor("#1f2523"))
            bg_grad.setColorAt(1.00, QColor(29, 74, 48, 190))
        else:
            bg_grad.setColorAt(0.00, QColor("#252b2b" if self._hovered else "#202424"))
            bg_grad.setColorAt(0.38, QColor("#1d2222"))
            bg_grad.setColorAt(0.74, QColor("#171a1b"))
            bg_grad.setColorAt(1.00, QColor(27, 54, 39, 180 if self._hovered else 150))
        border = QColor("#2db45f" if active else ("#617069" if self._hovered else "#3b4642"))
        text_color = QColor("#f4f4f4" if enabled else "#8f8f8f")

        p.setPen(QPen(border, 1.0))
        p.setBrush(QBrush(bg_grad))
        p.drawRoundedRect(rect, 8, 8)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 18 if not active else 26))
        p.drawRoundedRect(rect.adjusted(3, 3, -3, -rect.height() * 0.54), 6, 6)

        text_rect = rect.adjusted(11, 0, -34, 0)
        metrics = self.fontMetrics()
        text = metrics.elidedText(self.currentText(), Qt.TextElideMode.ElideRight, max(12, int(text_rect.width())))
        p.setPen(text_color)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        arrow_center = rect.center()
        arrow_center.setX(rect.right() - 17)
        p.save()
        p.translate(arrow_center)
        p.rotate(180.0 * self._arrow_progress)
        arrow_pen = QPen(QColor("#ededed" if enabled else "#8f8f8f"), 1.8)
        arrow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        arrow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(arrow_pen)
        p.drawLine(-5, -2, 0, 3)
        p.drawLine(0, 3, 5, -2)
        p.restore()

        p.end()


class AnimatedActionButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._hover_progress = 0.0
        self._hover_anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0; }")

    def getHoverProgress(self) -> float:
        return float(self._hover_progress)

    def setHoverProgress(self, value: float) -> None:
        self._hover_progress = max(0.0, min(1.0, float(value)))
        self.update()

    hoverProgress = pyqtProperty(float, fget=getHoverProgress, fset=setHoverProgress)

    def _animate_hover(self, target: float) -> None:
        try:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_progress)
            self._hover_anim.setEndValue(float(target))
            self._hover_anim.start()
        except Exception:
            self.setHoverProgress(target)

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        hover = self._hover_progress
        down = 1.0 if self.isDown() else 0.0
        radius = 9.0

        base_top = QColor(39, 44, 46, 236)
        base_bottom = QColor(20, 23, 24, 242)
        if hover > 0:
            base_top = QColor(
                int(base_top.red() + 18 * hover),
                int(base_top.green() + 26 * hover),
                int(base_top.blue() + 20 * hover),
                base_top.alpha(),
            )
            base_bottom = QColor(
                int(base_bottom.red() + 8 * hover),
                int(base_bottom.green() + 18 * hover),
                int(base_bottom.blue() + 12 * hover),
                base_bottom.alpha(),
            )

        if down:
            rect.translate(0, 1.0)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.00, base_top)
        grad.setColorAt(0.34, QColor(
            int(base_top.red() * 0.62 + 24 * 0.38),
            int(base_top.green() * 0.62 + 28 * 0.38),
            int(base_top.blue() * 0.62 + 28 * 0.38),
            240,
        ))
        grad.setColorAt(0.72, QColor(24, 28, 28, 240))
        grad.setColorAt(1.00, QColor(29, 72, 48, int(118 + 54 * hover)))
        bg = QBrush(grad)

        border = QColor(255, 255, 255, int(34 + 38 * hover))
        if hover > 0:
            border = QColor(45, 180, 95, int(85 + 80 * hover))

        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, radius, radius)

        shine = QColor(255, 255, 255, int(18 + 30 * hover))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shine)
        p.drawRoundedRect(rect.adjusted(3, 3, -3, -rect.height() * 0.52), radius - 2, radius - 2)

        if hover > 0:
            sweep = QRectF(rect)
            sweep_w = rect.width() * 0.32
            sweep_x = rect.left() - sweep_w + (rect.width() + sweep_w * 2) * hover
            sweep = QRectF(sweep_x, rect.top(), sweep_w, rect.height())
            p.setBrush(QColor(113, 255, 172, int(18 * hover)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(sweep, radius, radius)

        text_color = QColor("#f5fff8" if self.isEnabled() else "#8f8f8f")
        p.setPen(text_color)
        font = p.font()
        font.setPixelSize(12)
        font.setWeight(650)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class SegmentedControl(QWidget):
    currentChanged = pyqtSignal(int)
    tabBarClicked = pyqtSignal(int)

    def __init__(self, parent=None, attention_enabled: bool = False):
        super().__init__(parent)
        self._buttons = []
        self._current_index = 0
        self._attention_alpha = 0
        self._mode_activated = True
        self._attention_enabled = bool(attention_enabled)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 2, 0, 4)
        self._layout.setSpacing(5)
        self.setFixedHeight(38)

    def addTab(self, _widget: QWidget, text: str) -> int:
        index = len(self._buttons)
        btn = QPushButton(text, self)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedHeight(32)
        btn.clicked.connect(lambda _checked=False, i=index: self._button_clicked(i))
        self._layout.addWidget(btn, 1)
        self._buttons.append(btn)
        if index == self._current_index:
            btn.setChecked(True)
        self._sync_button_styles()
        return index

    def _button_clicked(self, index: int) -> None:
        if not self.signalsBlocked():
            self.tabBarClicked.emit(index)
        self.setCurrentIndex(index)

    def currentIndex(self) -> int:
        return self._current_index

    def setCurrentIndex(self, index: int) -> None:
        index = int(index)
        if index >= len(self._buttons):
            index = -1
        if index == self._current_index:
            self._sync_button_styles()
            return
        self._current_index = index
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == index)
            btn.blockSignals(False)
        self._sync_button_styles()
        if not self.signalsBlocked():
            self.currentChanged.emit(index)

    def set_attention_state(self, alpha: int) -> None:
        self._attention_alpha = max(0, min(255, int(alpha)))
        self._sync_button_styles()

    def clear_attention(self) -> None:
        self._attention_alpha = 0
        self._sync_button_styles()

    def set_mode_activated(self, activated: bool) -> None:
        self._mode_activated = bool(activated)
        self._sync_button_styles()

    def _sync_button_styles(self) -> None:
        for i, btn in enumerate(self._buttons):
            selected = i == self._current_index and self._mode_activated
            alpha = self._attention_alpha if (self._attention_enabled and not self._mode_activated) else 0
            border = f"rgba(45,180,95,{max(70, alpha)})" if alpha > 0 else "rgba(255,255,255,38)"
            bg = "rgba(45,180,95,210)" if selected else "rgba(255,255,255,10)"
            color = "#ffffff" if selected else "#e9e9e9"
            hover_bg = "rgba(45,180,95,54)" if not selected else "rgba(45,180,95,230)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid {border};
                    border-radius: 9px;
                    background: {bg};
                    color: {color};
                    font-size: 12px;
                    font-weight: 650;
                    padding: 0 10px;
                }}
                QPushButton:hover {{
                    background: {hover_bg};
                    border-color: rgba(45,180,95,165);
                }}
                QPushButton:pressed {{
                    background: rgba(45,180,95,185);
                }}
            """)


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

class SmallCircleButton(QPushButton):
    def __init__(self, text: str = "", icon_kind: str = "text", parent=None):
        super().__init__(text, parent)
        self._visual_active = True
        self._icon_kind = icon_kind or "text"
        self._display_text = text or ""
        self._pixmap = None
        self._pixmap_cache = {}
        self._pixmap_scale = 1.0
        self._pixmap_offset = QPoint(0, 0)
        self._busy = False
        self._busy_phase = 0.0
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(28)
        self._busy_timer.timeout.connect(self._advance_busy_indicator)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0; }"
        )

    def setVisualActive(self, active: bool) -> None:
        active = bool(active)
        if self._visual_active != active:
            self._visual_active = active
            self.update()

    def setIconKind(self, icon_kind: str) -> None:
        icon_kind = icon_kind or "text"
        if self._icon_kind != icon_kind:
            self._icon_kind = icon_kind
            self.update()

    def setPixmapPath(self, path: str) -> None:
        pm = QPixmap()
        if path and os.path.exists(path):
            image = QImage(path)
            if not image.isNull():
                image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                pm = QPixmap.fromImage(image)
        if not pm.isNull():
            pm = self._trim_transparent_pixmap(pm)
        self._pixmap = pm if not pm.isNull() else None
        self._pixmap_cache = {}
        self.update()

    def setPixmapTuning(self, scale: float = 1.0, offset_x: int = 0, offset_y: int = 0) -> None:
        self._pixmap_scale = max(0.2, min(1.4, float(scale)))
        self._pixmap_offset = QPoint(int(offset_x), int(offset_y))
        self._pixmap_cache = {}
        self.update()

    def _trim_transparent_pixmap(self, pixmap: QPixmap) -> QPixmap:
        try:
            image = pixmap.toImage()
            if not image.hasAlphaChannel():
                return pixmap
            left = image.width()
            top = image.height()
            right = -1
            bottom = -1
            for y in range(image.height()):
                for x in range(image.width()):
                    if image.pixelColor(x, y).alpha() > 8:
                        left = min(left, x)
                        top = min(top, y)
                        right = max(right, x)
                        bottom = max(bottom, y)
            if right < left or bottom < top:
                return pixmap
            if left <= 1 and top <= 1 and right >= image.width() - 2 and bottom >= image.height() - 2:
                return pixmap
            image = image.copy(left, top, right - left + 1, bottom - top + 1)
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            return QPixmap.fromImage(image)
        except Exception:
            return pixmap

    def _scaled_pixmap_for_target(self, width: float, height: float) -> QPixmap:
        if self._pixmap is None or self._pixmap.isNull():
            return QPixmap()

        sample_scale = 2.0
        target_size = QSize(
            max(1, int(round(width * sample_scale))),
            max(1, int(round(height * sample_scale))),
        )
        key = (target_size.width(), target_size.height())
        cached = self._pixmap_cache.get(key)
        if cached is not None and not cached.isNull():
            return cached

        pm = self._pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._pixmap_cache[key] = pm
        return pm

    def setBusy(self, busy: bool) -> None:
        busy = bool(busy)
        if self._busy == busy:
            return
        self._busy = busy
        if busy:
            self._busy_timer.start()
        else:
            self._busy_timer.stop()
            self._busy_phase = 0.0
        self.update()

    def _advance_busy_indicator(self) -> None:
        self._busy_phase = (self._busy_phase + 7.0) % 360.0
        self.update()

    def setText(self, text: str) -> None:
        self._display_text = text or ""
        super().setText(text)
        self.update()

    def _alpha(self, color: QColor, factor: float) -> QColor:
        c = QColor(color)
        c.setAlpha(max(0, min(255, int(c.alpha() * factor))))
        return c

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        if self._visual_active:
            border = QColor(45, 180, 95, 238)
            fill = QColor(45, 180, 95, 54)
            symbol = QColor(138, 240, 176, 255)
        else:
            border = QColor(120, 120, 120, 232)
            fill = QColor(110, 110, 110, 34)
            symbol = QColor(222, 222, 222, 245)

        if self.isChecked() and self._visual_active:
            fill = QColor(45, 180, 95, 76)
            symbol = QColor(167, 255, 198, 255)

        if self.underMouse():
            fill.setAlpha(min(255, fill.alpha() + 18))

        if self.isDown():
            fill.setAlpha(min(255, fill.alpha() + 28))

        if not self.isEnabled():
            border = self._alpha(border, 0.84)
            fill = self._alpha(fill, 0.90)
            symbol = self._alpha(symbol, 0.88)

        return border, fill, symbol

    def _draw_text_symbol(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        text = self._display_text or self.text() or ""
        if not text:
            return

        painter.setPen(color)
        font = painter.font()
        font.setBold(True)

        size_ratio = 0.46 if len(text) == 1 else 0.38
        if text == "A":
            size_ratio = 0.58
        elif text == "Ai":
            size_ratio = 0.49
        font.setPixelSize(max(9, int(min(rect.width(), rect.height()) * size_ratio)))
        painter.setFont(font)

        text_rect = QRectF(rect)
        if text.lower() == "i":
            text_rect.translate(0, -0.6)
        elif len(text) > 1:
            text_rect.translate(0, -0.2)

        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_gear_symbol(self, painter: QPainter, rect: QRectF, color: QColor, hole_color: QColor) -> None:
        cx = rect.center().x()
        cy = rect.center().y()
        scale = min(rect.width(), rect.height()) / 28.0

        pen = QPen(color, max(1.5, 1.6 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        inner_r = 4.0 * scale
        outer_r = 6.2 * scale
        for i in range(8):
            angle = (math.pi / 4.0) * i
            x1 = cx + math.cos(angle) * inner_r
            y1 = cy + math.sin(angle) * inner_r
            x2 = cx + math.cos(angle) * outer_r
            y2 = cy + math.sin(angle) * outer_r
            painter.drawLine(int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))

        gear_rect = QRectF(cx - 3.8 * scale, cy - 3.8 * scale, 7.6 * scale, 7.6 * scale)
        painter.drawEllipse(gear_rect)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(hole_color)
        hole_rect = QRectF(cx - 1.8 * scale, cy - 1.8 * scale, 3.6 * scale, 3.6 * scale)
        painter.drawEllipse(hole_rect)

    def _draw_gamepad_symbol(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        cx = rect.center().x()
        cy = rect.center().y()
        scale = min(rect.width(), rect.height()) / 28.0

        pen = QPen(color, max(1.45, 1.55 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        body = QRectF(cx - 7.0 * scale, cy - 4.2 * scale, 14.0 * scale, 8.4 * scale)
        painter.drawRoundedRect(body, 3.6 * scale, 3.6 * scale)

        painter.drawLine(
            int(round(cx - 5.0 * scale)),
            int(round(cy)),
            int(round(cx - 2.2 * scale)),
            int(round(cy)),
        )
        painter.drawLine(
            int(round(cx - 3.6 * scale)),
            int(round(cy - 1.4 * scale)),
            int(round(cx - 3.6 * scale)),
            int(round(cy + 1.4 * scale)),
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        button_r = 1.2 * scale
        painter.drawEllipse(QRectF(cx + 2.1 * scale - button_r, cy - 1.3 * scale - button_r, button_r * 2, button_r * 2))
        painter.drawEllipse(QRectF(cx + 4.8 * scale - button_r, cy + 0.7 * scale - button_r, button_r * 2, button_r * 2))

    def _draw_pixmap_symbol(self, painter: QPainter, rect: QRectF) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        pad = max(1.5, min(rect.width(), rect.height()) * 0.09)
        box = QRectF(rect).adjusted(pad, pad, -pad, -pad)
        pm_size = self._pixmap.size()
        if pm_size.width() <= 0 or pm_size.height() <= 0:
            return
        scale = min(box.width() / pm_size.width(), box.height() / pm_size.height()) * float(self._pixmap_scale)
        target_w = max(1.0, round(pm_size.width() * scale))
        target_h = max(1.0, round(pm_size.height() * scale))
        target = QRectF(
            round(box.center().x() - target_w / 2.0 + self._pixmap_offset.x()),
            round(box.center().y() - target_h / 2.0 + self._pixmap_offset.y()),
            target_w,
            target_h,
        )
        scaled = self._scaled_pixmap_for_target(target_w, target_h)
        if scaled.isNull():
            return
        painter.save()
        painter.setOpacity(1.0 if self._visual_active else 0.56)
        painter.drawPixmap(target, scaled, QRectF(scaled.rect()))
        painter.restore()

    def _draw_busy_indicator(self, painter: QPainter, rect: QRectF) -> None:
        arc_rect = QRectF(rect).adjusted(1.6, 1.6, -1.6, -1.6)
        start_angle = int((90.0 - self._busy_phase) * 16)

        tail = QColor(78, 231, 137, 118)
        if self._visual_active:
            tail = QColor(153, 255, 190, 118)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(tail, 2.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(arc_rect, start_angle, -86 * 16)

    def paintEvent(self, event):
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(1.25, 1.25, -1.25, -1.25)
        border, fill, symbol = self._colors()

        painter.setPen(QPen(border, 1.15))
        painter.setBrush(fill)
        painter.drawEllipse(rect)

        highlight = QRectF(
            rect.left() + 3,
            rect.top() + 3,
            max(0.0, rect.width() - 6),
            max(0.0, rect.height() * 0.42),
        )
        if highlight.width() > 0 and highlight.height() > 0:
            gloss = QColor(255, 255, 255, 22 if self._visual_active else 14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gloss)
            painter.drawEllipse(highlight)

        hole_color = QColor("#151515")
        hole_color.setAlpha(230)

        if self._icon_kind == "gear":
            self._draw_gear_symbol(painter, rect, symbol, hole_color)
        elif self._icon_kind == "gamepad":
            self._draw_gamepad_symbol(painter, rect, symbol)
        elif self._icon_kind == "pixmap":
            self._draw_pixmap_symbol(painter, rect)
        else:
            self._draw_text_symbol(painter, rect, symbol)

        if self._busy:
            self._draw_busy_indicator(painter, rect)

        painter.end()

class SiteManagerTutorButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Обучение по менеджеру сайтов")
        self.setFixedSize(30, 30)
        self.setAutoRaise(True)
        self.setStyleSheet("QToolButton { border: none; background: transparent; }")

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

        badge_rect = QRectF(rect).adjusted(5, 5, -5, -5)
        badge_color = QColor("#279f55" if self.isDown() else "#2db45f")
        painter.setPen(QPen(QColor(255, 255, 255, 52), 1.0))
        painter.setBrush(badge_color)
        painter.drawEllipse(badge_rect)

        highlight = QRectF(badge_rect).adjusted(3, 2, -3, -10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 36))
        painter.drawEllipse(highlight)

        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(13.5)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 238))
        painter.drawText(badge_rect.toRect(), Qt.AlignmentFlag.AlignCenter, "i")
        painter.end()

class SiteManagerTutorialDialog(StyledDialog):
    def __init__(self, parent=None, lang="ru"):
        super().__init__(parent)
        self.lang = lang

        self.setWindowTitle("Обучение: Менеджер сайтов" if lang == "ru" else "Guide: Site manager")
        self.setFixedSize(430, 530)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.setStyleSheet(_app_dialog_stylesheet() + """
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
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(54,64,61,240),
                    stop:0.52 rgba(28,35,33,240),
                    stop:1 rgba(33,79,51,238));
                color: #f6fff8;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: rgba(45,180,95,0.72);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(62,74,70,242),
                    stop:0.52 rgba(34,44,40,242),
                    stop:1 rgba(42,104,63,240));
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(28,35,33,245),
                    stop:1 rgba(38,96,58,242));
            }
        """)

        frame = _make_window_root_layout(self)
        self.install_title_bar(frame, self.windowTitle())
        root = _make_window_content_layout(frame, self, margins=(14, 12, 14, 14), spacing=10)

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

        self.dont_show_cb = ModernCheckBox(
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
                    Здесь можно быстро добавлять в обход и домены, и IP, либо исключать их из обработки.
                </div>
                <div style="margin-bottom:10px;">
                    <b>1. Верхний переключатель</b><br>
                    <span style="color:#bfbfbf;">Домены</span> — работа со списками доменов и сайтов.<br>
                    <span style="color:#bfbfbf;">IP</span> — работа со списками IP-адресов и подсетей.
                </div>
                <div style="margin-bottom:10px;">
                    <b>2. Переключатель ниже</b><br>
                    <span style="color:#bfbfbf;">Добавление</span> — запись попадёт в пользовательский список обхода текущего режима.<br>
                    <span style="color:#bfbfbf;">Исключения</span> — запись попадёт в список исключений текущего режима.
                </div>
                <div style="margin-bottom:10px;">
                    <b>3. Кнопки сверху</b><br>
                    Открыть папку — открывает каталог с пользовательскими списками.<br>
                    Добавить список — импортирует текущий тип данных в список добавления.<br>
                    Исключить список — импортирует текущий тип данных в список исключений.
                </div>
                <div style="margin-bottom:10px;">
                    <b>4. Кнопки рядом с вкладками</b><br>
                    Кнопка с плюсом добавляет один домен или IP вручную в текущий режим.<br>
                    Поле поиска ниже фильтрует уже загруженный список.
                </div>
                <div style="margin-bottom:10px;">
                    <b>5. Работа со списком</b><br>
                    Нажатие по строке отмечает запись галочкой.<br>
                    Корзина удаляет отмеченные записи.<br>
                    Стрелка справа открывает домен или одиночный IP в браузере по умолчанию.
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px;">
                    <b>Подсказка</b><br>
                    Если у вас сайт — используйте режим <b>Домены</b>. Если у вас IP или подсеть — переключитесь на <b>IP</b>.
                </div>
                </body></html>
            """
        return """
            <html><body style="font-family:Segoe UI; font-size:10.5pt; color:#efefef;">
            <div style="background:rgba(45,180,95,0.10); border:1px solid rgba(45,180,95,0.28); border-radius:12px; padding:12px; margin-bottom:10px;">
                <b>What this window does</b><br>
                Use it to add both domains and IPs to the bypass lists or exclude them from processing.
            </div>
            <div style="margin-bottom:10px;">
                <b>1. Top switch</b><br>
                <span style="color:#bfbfbf;">Domains</span> works with domain and site lists.<br>
                <span style="color:#bfbfbf;">IP</span> works with IP address and subnet lists.
            </div>
            <div style="margin-bottom:10px;">
                <b>2. Switch below</b><br>
                <span style="color:#bfbfbf;">Additions</span> sends the current value type into the user bypass list.<br>
                <span style="color:#bfbfbf;">Excludes</span> sends the current value type into the exclude list.
            </div>
            <div style="margin-bottom:10px;">
                <b>3. Top buttons</b><br>
                Open folder opens the folder with user lists.<br>
                Add list imports the current value type into additions.<br>
                Exclude list imports the current value type into excludes.
            </div>
            <div style="margin-bottom:10px;">
                <b>4. Buttons near tabs</b><br>
                The plus button adds a single domain or IP into the current mode.<br>
                The search field below filters the currently loaded list.
            </div>
            <div style="margin-bottom:10px;">
                <b>5. Working with the list</b><br>
                Clicking a row toggles its checkmark.<br>
                The trash button removes checked items.<br>
                The arrow on the right opens a domain or a single IP in the default browser.
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px;">
                <b>Tip</b><br>
                Use <b>Domains</b> for websites and <b>IP</b> for direct addresses or subnets.
            </div>
            </body></html>
        """

class SiteManagerDialog(StyledDialog):
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
        self.lazy_loaded = {path: False for path in USER_LIST_FILE_MAP.values()}
        self._mode_activated = False
        self._add_button_acknowledged = False
        self._tutorial_dialog = None

        base_w = parent.width() if parent else 300
        self.setWindowTitle("Менеджер сайтов и ip" if self.lang == "ru" else "Site manager")
        self.setMinimumSize(base_w, 410)
        self.resize(base_w, 450)
        self.setFixedWidth(base_w)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        frame = _make_window_root_layout(self)
        self.install_title_bar(frame, self.windowTitle())
        root = _make_window_content_layout(frame, self, margins=(10, 10, 10, 10), spacing=8)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        tool_btn_style = """
            QToolButton {
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(44,50,50,235),
                    stop:0.36 rgba(34,40,40,238),
                    stop:0.72 rgba(24,30,29,238),
                    stop:1 rgba(26,49,36,235));
                padding: 3px 6px;
                text-align: center;
                font-size: 12px;
            }
            QToolButton:hover {
                border-color: rgba(45,180,95,0.72);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(54,64,61,240),
                    stop:0.38 rgba(40,49,46,240),
                    stop:0.74 rgba(29,39,35,240),
                    stop:1 rgba(33,79,51,238));
            }
            QToolButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(28,35,33,245),
                    stop:1 rgba(38,96,58,242));
            }
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
        self.import_add_btn.setIconSize(QSize(24, 24))
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
        self.import_exclude_btn.setIconSize(QSize(24, 24))
        self.import_exclude_btn.setFixedHeight(68)
        self.import_exclude_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.import_exclude_btn.setStyleSheet(tool_btn_style)
        self.import_exclude_btn.clicked.connect(self.import_exclude_file)

        top_row.addWidget(self.open_folder_btn, 1)
        top_row.addWidget(self.import_add_btn, 1)
        top_row.addWidget(self.import_exclude_btn, 1)
        root.addLayout(top_row)

        self.value_tabs = SegmentedControl(self)
        self.value_tabs.addTab(QWidget(), "Домены" if self.lang == "ru" else "Domains")
        self.value_tabs.addTab(QWidget(), "IP")
        self.value_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(self.value_tabs)

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)

        self.tabs = SegmentedControl(self, attention_enabled=True)
        self.tabs.addTab(QWidget(), "Добавление" if self.lang == "ru" else "Additions")
        self.tabs.addTab(QWidget(), "Исключения" if self.lang == "ru" else "Excludes")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.add_btn = QToolButton()
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setAutoRaise(False)
        self.add_btn.setFixedSize(34, 34)
        self.add_btn.setToolTip("Добавить сайт" if self.lang == "ru" else "Add site")
        self.add_btn.setIcon(self._build_circle_action_icon("#2db45f", True, 22))
        self.add_btn.setIconSize(QSize(22, 22))
        self.add_btn.clicked.connect(self.add_site)
        self._init_add_button_attention()
        self._apply_add_button_style()

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
        search_row.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)
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

        self.value_tabs.currentChanged.connect(self.on_mode_changed)
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
            QListWidget::item:selected { background: rgba(45,180,95,0.16); }
            QListWidget::item:hover { background: rgba(120,120,120,0.08); }
        """)
        self.sites_list.itemChanged.connect(self.update_delete_buttons)
        self.sites_list.viewport().installEventFilter(self)
        list_wrap_layout.addWidget(self.sites_list)

        root.addWidget(list_wrap, 1)
        self._refresh_mode_controls()
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
                    if bool(item.data(PLACEHOLDER_ITEM_ROLE)):
                        return True
                    item_rect = self.sites_list.visualItemRect(item)
                    if self._visit_icon_rect(item_rect).contains(event.position()):
                        self.open_site_in_browser(item)
                        return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.update_delete_buttons)

    def _build_folder_action_icon(self, badge_color: str, positive: bool, size: int = 24) -> QIcon:
        logical_size = max(18, int(size))
        dpr = 1.0
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            pass

        pm = QPixmap(int(round(logical_size * dpr)), int(round(logical_size * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = logical_size / 24.0
        tab_rect = QRectF(4.0 * scale, 5.0 * scale, 7.5 * scale, 4.2 * scale)
        back_rect = QRectF(2.8 * scale, 7.5 * scale, 17.6 * scale, 11.2 * scale)
        front_rect = QRectF(2.4 * scale, 8.8 * scale, 18.4 * scale, 10.2 * scale)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c9962c"))
        painter.drawRoundedRect(tab_rect, 1.6 * scale, 1.6 * scale)
        painter.setBrush(QColor("#e5b64a"))
        painter.drawRoundedRect(back_rect, 2.2 * scale, 2.2 * scale)
        painter.setBrush(QColor("#f1cf6a"))
        painter.drawRoundedRect(front_rect, 2.3 * scale, 2.3 * scale)

        gloss = QColor(255, 255, 255, 55)
        painter.setBrush(gloss)
        painter.drawRoundedRect(
            QRectF(front_rect.left() + 1.8 * scale, front_rect.top() + 1.5 * scale, front_rect.width() - 5.4 * scale, 2.0 * scale),
            1.0 * scale,
            1.0 * scale,
        )

        badge_size = 9.8 * scale
        circle_rect = QRectF(
            logical_size - badge_size - 1.6 * scale,
            logical_size - badge_size - 1.6 * scale,
            badge_size,
            badge_size,
        )
        painter.setBrush(QColor(20, 20, 20, 190))
        painter.drawEllipse(circle_rect.adjusted(-0.8 * scale, -0.8 * scale, 0.8 * scale, 0.8 * scale))
        painter.setBrush(QColor(badge_color))
        painter.drawEllipse(circle_rect)

        line_pen = QPen(QColor("white"), max(1.6, 2.0 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(line_pen)

        cx = circle_rect.center().x()
        cy = circle_rect.center().y()
        arm = 2.6 * scale
        painter.drawLine(QPoint(int(round(cx - arm)), int(round(cy))), QPoint(int(round(cx + arm)), int(round(cy))))
        if positive:
            painter.drawLine(QPoint(int(round(cx)), int(round(cy - arm))), QPoint(int(round(cx)), int(round(cy + arm))))

        painter.end()
        return QIcon(pm)

    def _build_web_action_icon(self, badge_color: str, positive: bool, size: int = 22) -> QIcon:
        logical_size = max(18, int(size))
        dpr = 1.0
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            pass

        pm = QPixmap(int(round(logical_size * dpr)), int(round(logical_size * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = logical_size / 22.0
        globe_rect = QRectF(2.2 * scale, 2.2 * scale, 15.8 * scale, 15.8 * scale)
        globe = QColor("#74d6ff")
        globe_dark = QColor("#3aa8d8")
        line = QColor("#e9fbff")

        painter.setPen(QPen(globe_dark, max(1.15, 1.35 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor(116, 214, 255, 42))
        painter.drawEllipse(globe_rect)

        painter.setPen(QPen(line, max(0.85, 1.05 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = globe_rect.center().x()
        cy = globe_rect.center().y()
        painter.drawLine(QPoint(int(round(globe_rect.left() + 1.9 * scale)), int(round(cy))), QPoint(int(round(globe_rect.right() - 1.9 * scale)), int(round(cy))))
        painter.drawArc(globe_rect.adjusted(4.6 * scale, 0.7 * scale, -4.6 * scale, -0.7 * scale), 90 * 16, 180 * 16)
        painter.drawArc(globe_rect.adjusted(4.6 * scale, 0.7 * scale, -4.6 * scale, -0.7 * scale), -90 * 16, 180 * 16)
        painter.drawArc(globe_rect.adjusted(1.0 * scale, 4.8 * scale, -1.0 * scale, -4.8 * scale), 0, 180 * 16)
        painter.drawArc(globe_rect.adjusted(1.0 * scale, 4.8 * scale, -1.0 * scale, -4.8 * scale), 180 * 16, 180 * 16)

        painter.setPen(Qt.PenStyle.NoPen)
        badge_size = 8.8 * scale
        badge_rect = QRectF(
            logical_size - badge_size - 1.0 * scale,
            logical_size - badge_size - 1.0 * scale,
            badge_size,
            badge_size,
        )
        painter.setBrush(QColor(20, 20, 20, 185))
        painter.drawEllipse(badge_rect.adjusted(-0.75 * scale, -0.75 * scale, 0.75 * scale, 0.75 * scale))
        painter.setBrush(QColor(badge_color))
        painter.drawEllipse(badge_rect)

        symbol_pen = QPen(QColor("white"), max(1.55, 1.85 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(symbol_pen)
        bx = badge_rect.center().x()
        by = badge_rect.center().y()
        arm = 2.35 * scale
        painter.drawLine(QPoint(int(round(bx - arm)), int(round(by))), QPoint(int(round(bx + arm)), int(round(by))))
        if positive:
            painter.drawLine(QPoint(int(round(bx)), int(round(by - arm))), QPoint(int(round(bx)), int(round(by + arm))))

        painter.end()
        return QIcon(pm)

    def _build_circle_action_icon(self, circle_color: str, positive: bool, size: int = 22) -> QIcon:
        logical_size = max(18, int(size))
        dpr = 1.0
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            pass

        pm = QPixmap(int(round(logical_size * dpr)), int(round(logical_size * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = logical_size / 22.0
        shadow_rect = QRectF(2.4 * scale, 2.4 * scale, 17.2 * scale, 17.2 * scale)
        circle_rect = QRectF(2.8 * scale, 2.0 * scale, 16.8 * scale, 16.8 * scale)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 95))
        painter.drawEllipse(shadow_rect)

        painter.setBrush(QColor(circle_color))
        painter.drawEllipse(circle_rect)

        painter.setBrush(QColor(255, 255, 255, 34))
        painter.drawEllipse(circle_rect.adjusted(3.0 * scale, 2.0 * scale, -6.2 * scale, -8.8 * scale))

        symbol_pen = QPen(QColor("white"), max(2.0, 2.35 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(symbol_pen)

        cx = circle_rect.center().x()
        cy = circle_rect.center().y()
        arm = 4.2 * scale
        painter.drawLine(QPoint(int(round(cx - arm)), int(round(cy))), QPoint(int(round(cx + arm)), int(round(cy))))
        if positive:
            painter.drawLine(QPoint(int(round(cx)), int(round(cy - arm))), QPoint(int(round(cx)), int(round(cy + arm))))

        painter.end()
        return QIcon(pm)

    def _current_value_kind(self) -> str:
        return "ip" if self.value_tabs.currentIndex() == 1 else "domain"

    def _current_action_kind(self) -> str | None:
        index = self.tabs.currentIndex()
        if index < 0:
            return None
        return "add" if index == 0 else "exclude"

    def _placeholder_lines_for_current_file(self) -> list[str]:
        if not self.current_file:
            return []
        return list(EMPTY_USER_LIST_PLACEHOLDERS.get(self.current_file, []))

    def _add_button_attention_color(self) -> tuple[int, int, int]:
        action = self._current_action_kind() or "add"
        return (212, 96, 96) if action == "exclude" else (45, 180, 95)

    def _apply_add_button_style(self, attention_alpha: int = 0) -> None:
        if not hasattr(self, "add_btn"):
            return

        r, g, b = self._add_button_attention_color()
        hover_alpha = 10 if attention_alpha <= 0 else max(18, min(110, attention_alpha // 2))
        press_alpha = 20 if attention_alpha <= 0 else max(28, min(150, int(attention_alpha * 0.7)))
        border_alpha = 60 if attention_alpha <= 0 else max(75, min(210, attention_alpha))

        self.add_btn.setStyleSheet(f"""
            QToolButton {{
                border: 1px solid rgba({r},{g},{b},{border_alpha});
                border-radius: 8px;
                background: rgba({r},{g},{b},10);
                color: rgb({r},{g},{b});
            }}
            QToolButton:hover {{ background: rgba({r},{g},{b},{hover_alpha}); }}
            QToolButton:pressed {{ background: rgba({r},{g},{b},{press_alpha}); }}
        """)

    def _init_add_button_attention(self) -> None:
        self._add_btn_attention_anim = QVariantAnimation(self)
        self._add_btn_attention_anim.setDuration(900)
        self._add_btn_attention_anim.setStartValue(30)
        self._add_btn_attention_anim.setKeyValueAt(0.5, 210)
        self._add_btn_attention_anim.setEndValue(30)
        self._add_btn_attention_anim.setLoopCount(-1)
        self._add_btn_attention_anim.valueChanged.connect(
            lambda value: self._apply_add_button_style(int(value))
            if (not self._add_button_acknowledged and self._mode_activated)
            else None
        )

    def _start_add_button_attention(self) -> None:
        if self._add_button_acknowledged:
            self._apply_add_button_style()
            return
        if hasattr(self, "_add_btn_attention_anim"):
            if self._add_btn_attention_anim.state() == QPropertyAnimation.State.Running:
                return
            self._add_btn_attention_anim.start()
            self._apply_add_button_style(int(self._add_btn_attention_anim.startValue()))

    def _stop_add_button_attention(self) -> None:
        self._add_button_acknowledged = True
        if hasattr(self, "_add_btn_attention_anim"):
            self._add_btn_attention_anim.stop()
        self._apply_add_button_style()

    def _refresh_mode_controls(self) -> None:
        is_ip = self._current_value_kind() == "ip"
        action = self._current_action_kind() or "add"

        if self.lang == "ru":
            add_btn_tip = "Добавить IP" if is_ip else "Добавить сайт"
            if action == "exclude":
                add_btn_tip = "Исключить IP" if is_ip else "Исключить сайт"

            self.import_add_btn.setToolTip(
                "Добавить IP в user/ipset-all-user.txt"
                if is_ip else
                "Добавить домены в user/list-general-user.txt"
            )
            self.import_exclude_btn.setToolTip(
                "Добавить IP в user/ipset-exclude-user.txt"
                if is_ip else
                "Добавить домены в user/list-exclude-user.txt"
            )
        else:
            add_btn_tip = "Add IP" if is_ip else "Add site"
            if action == "exclude":
                add_btn_tip = "Exclude IP" if is_ip else "Exclude site"

            self.import_add_btn.setToolTip(
                "Add IPs to user/ipset-all-user.txt"
                if is_ip else
                "Add domains to user/list-general-user.txt"
            )
            self.import_exclude_btn.setToolTip(
                "Add IPs to user/ipset-exclude-user.txt"
                if is_ip else
                "Add domains to user/list-exclude-user.txt"
            )

        self.add_btn.setToolTip(add_btn_tip)
        self.add_btn.setIcon(self._build_circle_action_icon("#d46060" if action == "exclude" else "#2db45f", action != "exclude", 22))
        self._apply_add_button_style()

    def _selected_file_path(self) -> str:
        action = self._current_action_kind()
        if action is None:
            return None
        return USER_LIST_FILE_MAP.get((self._current_value_kind(), action))

    def _update_list_info(self) -> None:
        selected_path = self._selected_file_path()
        is_ip = self._current_value_kind() == "ip"
        if selected_path is None:
            self.list_info_lbl.setText(
                "Выберите режим Добавление или Исключения, чтобы показать список."
                if self.lang == "ru" else
                "Choose Additions or Excludes to show the list."
            )
        elif selected_path in (USER_GENERAL_FILE, USER_IP_ALL_FILE):
            self.list_info_lbl.setText(
                "Добавляется к основному списку обхода доменов."
                if self.lang == "ru" and not is_ip else
                "Добавляется к основному IP-списку core."
                if self.lang == "ru" else
                "Appended to the main bypass list."
                if not is_ip else
                "Merged into the main core IP list."
            )
        else:
            self.list_info_lbl.setText(
                "Добавляется к списку исключений доменов."
                if self.lang == "ru" and not is_ip else
                "Добавляется к списку исключений IP."
                if self.lang == "ru" else
                "Appended to the exclude list."
                if not is_ip else
                "Appended to the IP exclude list."
            )

    def on_mode_changed(self, _=0):
        self._refresh_mode_controls()
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
            self._activate_mode_selection()

        self.current_file = self._selected_file_path()
        self.reload_current_file()
        if self.current_file:
            self.lazy_loaded[self.current_file] = True

    def reload_current_file(self):
        self.current_file = self._selected_file_path()
        self.sites_list.clear()
        self._refresh_mode_controls()
        self._update_list_info()
        if not self.current_file:
            self.update_delete_buttons()
            return

        lines = _read_lines_utf8(self.current_file)
        placeholder_mode = False
        if not lines:
            lines = self._placeholder_lines_for_current_file()
            placeholder_mode = bool(lines)

        for site in lines:
            item = QListWidgetItem(site)
            item.setData(Qt.ItemDataRole.UserRole, site)
            item.setData(PLACEHOLDER_ITEM_ROLE, placeholder_mode)
            if placeholder_mode:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor(170, 170, 170))
                item.setToolTip("Пример записи" if self.lang == "ru" else "Example entry")
            else:
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
        self.import_values_from_file(USER_LIST_FILE_MAP[(self._current_value_kind(), "add")])

    def import_exclude_file(self) -> None:
        self.import_values_from_file(USER_LIST_FILE_MAP[(self._current_value_kind(), "exclude")])

    def import_values_from_file(self, target_file: str) -> None:
        is_ip = _entity_kind_for_target_file(target_file) == "ip"
        title = (
            "Импорт IP" if is_ip and self.lang == "ru" else
            "Импорт доменов" if self.lang == "ru" else
            "Import IPs" if is_ip else
            "Import domains"
        )
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

        imported_values = []
        for value in candidates:
            normalized = _normalize_value_for_target_file(target_file, value)
            if not _is_valid_value_for_target_file(target_file, normalized):
                continue
            imported_values.append(normalized)

        if not imported_values:
            QMessageBox.warning(
                self,
                "Ошибка" if self.lang == "ru" else "Error",
                "В файле не найдено валидных IP или подсетей."
                if is_ip and self.lang == "ru" else
                "В файле не найдено валидных доменов."
                if self.lang == "ru" else
                "No valid IPs or subnets were found in the file."
                if is_ip else
                "No valid domains were found in the file."
            )
            return

        existing = _read_lines_utf8(target_file)
        before = {x.strip().casefold() for x in existing if x.strip()}
        merged = _merge_unique(existing, imported_values)
        after = {x.strip().casefold() for x in merged if x.strip()}
        added_count = len(after - before)
        _write_lines_utf8(target_file, merged)

        self.lazy_loaded[target_file] = True
        if target_file == self._selected_file_path():
            self.reload_current_file()
        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        QMessageBox.information(
            self,
            "Импорт завершён" if self.lang == "ru" else "Import completed",
            (
                f"Добавлено IP: {added_count}"
                if is_ip and self.lang == "ru" else
                f"Добавлено доменов: {added_count}"
                if self.lang == "ru" else
                f"IPs added: {added_count}"
                if is_ip else
                f"Domains added: {added_count}"
            )
        )

    def add_site(self):
        self._stop_add_button_attention()
        if self.tabs.currentIndex() < 0:
            self.tabs.setCurrentIndex(0)
        is_ip = self._current_value_kind() == "ip"
        action = self._current_action_kind() or "add"
        title = (
            "Добавить IP" if is_ip and action == "add" and self.lang == "ru" else
            "Исключить IP" if is_ip and self.lang == "ru" else
            "Добавить сайт" if action == "add" and self.lang == "ru" else
            "Исключить сайт" if self.lang == "ru" else
            "Add IP" if is_ip and action == "add" else
            "Exclude IP" if is_ip else
            "Add site" if action == "add" else
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
        _center_widget_on_screen(dlg, self)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        value = _normalize_value_for_target_file(self.current_file, dlg.textValue())

        if not _is_valid_value_for_target_file(self.current_file, value):
            QMessageBox.warning(
                self,
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

        lines = _read_lines_utf8(self.current_file)
        lines = _merge_unique(lines, [value])
        _write_lines_utf8(self.current_file, lines)
        self.lazy_loaded[self.current_file] = True

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
        if bool(item.data(PLACEHOLDER_ITEM_ROLE)):
            return
        site = str(item.data(Qt.ItemDataRole.UserRole) or item.text()).strip()
        if not site:
            return
        if _is_valid_ip_or_network_like(site):
            if not _is_single_ip_address_like(site):
                return
            host = _normalize_ip_candidate(site)
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            url = site if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", site) else f"http://{host}"
        else:
            url = site if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", site) else f"https://{site}"
        QDesktopServices.openUrl(QUrl(url))

    def _on_tab_clicked(self, index: int) -> None:
        if index < 0:
            return
        if not self._mode_activated and self.tabs.currentIndex() == index:
            self._activate_mode_selection()
            self.current_file = self._selected_file_path()
            self.reload_current_file()
            if self.current_file:
                self.lazy_loaded[self.current_file] = True
            return
        self.tabs.setCurrentIndex(index)

    def _activate_mode_selection(self) -> None:
        if self._mode_activated:
            return
        self._mode_activated = True
        self._stop_tab_attention()
        self._sync_tabbar_mode_state()
        self._start_add_button_attention()

    def _init_tab_attention(self) -> None:
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(-1)
        self.tabs.blockSignals(False)
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
        if hasattr(self.tabs, "set_attention_state"):
            self.tabs.set_attention_state(int(value))

    def _stop_tab_attention(self) -> None:
        if hasattr(self, "_tab_attention_anim") and self._tab_attention_anim is not None:
            self._tab_attention_anim.stop()
        if hasattr(self.tabs, "clear_attention"):
            self.tabs.clear_attention()

    def _sync_tabbar_mode_state(self) -> None:
        if hasattr(self.tabs, "set_mode_activated"):
            self.tabs.set_mode_activated(self._mode_activated)

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
            if (not bool(item.data(PLACEHOLDER_ITEM_ROLE)))
            and item.checkState() == Qt.CheckState.Checked
        ]

    def _selected_items(self):
        return []

    def _marked_items(self):
        ordered = []
        seen = set()
        for item in self._checked_items():
            key = id(item)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(item)
        return ordered

    def delete_selected_multiple(self):
        items = self._marked_items()
        if not items:
            return
        if not self._confirm_delete(len(items)):
            return

        selected = {str((it.data(Qt.ItemDataRole.UserRole) or it.text())).strip().casefold() for it in items}
        lines = [x for x in _read_lines_utf8(self.current_file) if x.strip().casefold() not in selected]
        _write_lines_utf8(self.current_file, lines)
        self.lazy_loaded[self.current_file] = True

        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        self.reload_current_file()

    def update_delete_buttons(self):
        if self._marked_items():
            self.delete_btn.show()
        else:
            self.delete_btn.hide()


class GameModeSettingsDialog(StyledDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        lang = getattr(parent, "lang", "ru") if parent else "ru"
        self.parent_window = parent
        self.lang = lang
        options = _get_game_mode_options(getattr(parent, "settings", None))
        base_w = parent.width() if parent else 300

        self.setWindowTitle("Настройки игрового режима" if lang == "ru" else "Game mode settings")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setStyleSheet(_app_dialog_stylesheet() + """
            QLabel {
                color: #f1f1f1;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 14px;
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(54,64,61,240),
                    stop:0.52 rgba(28,35,33,240),
                    stop:1 rgba(33,79,51,238));
                color: #f6fff8;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: rgba(45,180,95,0.72);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(62,74,70,242),
                    stop:0.52 rgba(34,44,40,242),
                    stop:1 rgba(42,104,63,240));
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(28,35,33,245),
                    stop:1 rgba(38,96,58,242));
            }
        """)

        frame = _make_window_root_layout(self)
        self.install_title_bar(frame, self.windowTitle())
        layout = _make_window_content_layout(frame, self, margins=(14, 12, 14, 14), spacing=10)

        caption = QLabel(
            "Настройте, что добавлять к игровому режиму."
            if lang == "ru" else
            "Choose what should be added to game mode."
        )
        caption.setWordWrap(True)
        layout.addWidget(caption)

        self.main_bypass_switch = ToggleSwitch(self)
        self.main_bypass_switch.setChecked(bool(options["main_bypass_enabled"]))
        layout.addLayout(
            self._build_switch_row(
                "Основной обход" if lang == "ru" else "Main bypass",
                self.main_bypass_switch,
            )
        )

        self.user_lists_switch = ToggleSwitch(self)
        self.user_lists_switch.setChecked(bool(options["user_lists_enabled"]))
        layout.addLayout(
            self._build_switch_row(
                "Пользовательские домены и ip"
                if lang == "ru" else
                "User domains and IP",
                self.user_lists_switch,
            )
        )

        self.discord_switch = ToggleSwitch(self)
        self.discord_switch.setChecked(bool(options["discord_enabled"]))
        layout.addLayout(
            self._build_switch_row(
                "Discord отдельно" if lang == "ru" else "Discord separately",
                self.discord_switch,
            )
        )

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(10)

        self.help_hint_lbl = QLabel(
            "Зачем это нужно?"
            if lang == "ru" else
            "Why is this needed?"
        )
        self.help_hint_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_hint_lbl.setMouseTracking(True)
        self.help_hint_lbl.setStyleSheet("""
            QLabel {
                color: #8ee6ad;
                font-weight: 600;
                padding: 4px 0;
                text-decoration: underline;
            }
            QLabel:hover { color: #b7f6c9; }
        """)
        self.help_hint_lbl.installEventFilter(self)
        bottom_row.addWidget(self.help_hint_lbl, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bottom_row.addStretch()

        close_btn = QPushButton("Закрыть" if lang == "ru" else "Close")
        close_btn.clicked.connect(self.close)
        bottom_row.addWidget(close_btn)

        layout.addStretch()
        layout.addLayout(bottom_row)

        self._help_popup_anim = None
        self._build_help_popup()

        self.main_bypass_switch.toggled.connect(self.apply_changes)
        self.user_lists_switch.toggled.connect(self.apply_changes)
        self.discord_switch.toggled.connect(self.apply_changes)

        self.setFixedWidth(base_w)
        self.adjustSize()
        self.setFixedSize(base_w, self.sizeHint().height())

    def _help_popup_text(self) -> str:
        if self.lang == "ru":
            return (
                "Данные настройки призваны уменьшить влияние на сеть, пока вы играете. "
                "Если вам не нужен обычный обход (YouTube, Twitch и т.д.) во время игры, "
                "а нужны только Game Filters, то лишнее можно отключить, чтобы не влиять на пинг "
                "и не мониторить все сетевые пакеты. Вы также можете отдельно включить только "
                "Discord обход в дополнение к игровому режиму, чтобы общаться во время игры. "
                "Либо другие ваши пользовательские домены/ip."
            )
        return (
            "These settings reduce network impact while you play. If you do not need the regular "
            "bypass for YouTube, Twitch, and similar sites during a game, and only need Game Filters, "
            "you can disable it to avoid affecting ping or monitoring all network packets. You can also "
            "enable only Discord bypass in addition to game mode so you can talk while playing, or keep "
            "your own custom domains/IP enabled."
        )

    def _build_help_popup(self) -> None:
        popup_flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        try:
            popup_flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        except AttributeError:
            pass

        popup = QFrame(self, popup_flags)
        popup.setObjectName("gameModeHelpPopup")
        popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        popup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        popup.setStyleSheet("""
            QFrame#gameModeHelpPopup {
                background: #242424;
                border: 1px solid rgba(142, 230, 173, 0.58);
                border-radius: 10px;
            }
            QFrame#gameModeHelpPopup QLabel {
                color: #f3f3f3;
            }
        """)

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(14, 12, 14, 12)
        popup_layout.setSpacing(0)

        text_lbl = QLabel(self._help_popup_text(), popup)
        font = text_lbl.font()
        font.setPixelSize(12)
        text_lbl.setFont(font)
        text_lbl.setWordWrap(True)
        text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        popup_layout.addWidget(text_lbl)

        popup.hide()
        self.help_popup = popup
        self.help_popup_text_lbl = text_lbl
        self._help_popup_target_visible = False

    def _stop_help_popup_anim(self) -> None:
        if self._help_popup_anim is None:
            return
        anim = self._help_popup_anim
        self._help_popup_anim = None
        anim.stop()
        anim.deleteLater()

    def _finish_help_popup_anim(self) -> None:
        anim = self._help_popup_anim
        self._help_popup_anim = None
        if anim is not None:
            anim.deleteLater()

        if self._help_popup_target_visible:
            self.help_popup.setWindowOpacity(1.0)
        else:
            self.help_popup.hide()
            self.help_popup.setWindowOpacity(0.0)

    def _help_popup_screen_geometry(self):
        screen = QGuiApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def _help_popup_positions(self) -> tuple[QPoint, QPoint]:
        screen_rect = self._help_popup_screen_geometry()
        popup_w = max(320, self.width() + 100)
        if screen_rect is not None:
            popup_w = min(popup_w, max(260, screen_rect.width() - 32))

        margins = self.help_popup.layout().contentsMargins()
        inner_w = max(220, int(popup_w) - margins.left() - margins.right())
        self.help_popup_text_lbl.setFixedWidth(inner_w)
        text_h = self.help_popup_text_lbl.heightForWidth(inner_w)
        if text_h <= 0:
            text_h = self.help_popup_text_lbl.sizeHint().height()
        popup_h = int(text_h + margins.top() + margins.bottom())
        self.help_popup.setMinimumSize(0, 0)
        self.help_popup.setMaximumSize(16777215, 16777215)
        self.help_popup.setFixedSize(int(popup_w), max(80, popup_h))

        label_pos = self.help_hint_lbl.mapToGlobal(QPoint(0, 0))
        target_x = label_pos.x()
        target_y = label_pos.y() + self.help_hint_lbl.height() + 8

        if screen_rect is not None:
            if target_x + popup_w > screen_rect.right() - 8:
                target_x = screen_rect.right() - int(popup_w) - 8
            target_x = max(screen_rect.left() + 8, target_x)

            if target_y + popup_h > screen_rect.bottom() - 8:
                target_y = label_pos.y() - popup_h - 8
            target_y = max(screen_rect.top() + 8, target_y)

        target = QPoint(int(target_x), int(target_y))
        start = QPoint(target.x(), target.y() + 10)
        return start, target

    def _show_help_popup(self) -> None:
        if not hasattr(self, "help_popup"):
            return

        start_pos, target_pos = self._help_popup_positions()

        if self._help_popup_target_visible and self.help_popup.isVisible():
            self._stop_help_popup_anim()
            self.help_popup.move(target_pos)
            self.help_popup.setWindowOpacity(1.0)
            return

        self._help_popup_target_visible = True
        visible = self.help_popup.isVisible()
        current_opacity = float(self.help_popup.windowOpacity()) if visible else 0.0

        self._stop_help_popup_anim()

        if visible:
            start_pos = self.help_popup.pos()
        else:
            self.help_popup.move(start_pos)
            self.help_popup.setWindowOpacity(0.0)

        self.help_popup.show()
        self.help_popup.raise_()

        pos_anim = QPropertyAnimation(self.help_popup, b"pos", self)
        pos_anim.setDuration(180)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(target_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(self.help_popup, b"windowOpacity", self)
        op_anim.setDuration(160)
        op_anim.setStartValue(current_opacity)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(self)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)
        grp.finished.connect(self._finish_help_popup_anim)
        self._help_popup_anim = grp
        grp.start()

    def _hide_help_popup(self, immediate: bool = False) -> None:
        if not hasattr(self, "help_popup"):
            return

        if not self._help_popup_target_visible and not self.help_popup.isVisible():
            return

        self._help_popup_target_visible = False
        self._stop_help_popup_anim()

        if immediate or not self.help_popup.isVisible():
            self.help_popup.hide()
            self.help_popup.setWindowOpacity(0.0)
            return

        start_pos = self.help_popup.pos()
        end_pos = QPoint(start_pos.x(), start_pos.y() + 10)

        pos_anim = QPropertyAnimation(self.help_popup, b"pos", self)
        pos_anim.setDuration(150)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        op_anim = QPropertyAnimation(self.help_popup, b"windowOpacity", self)
        op_anim.setDuration(150)
        op_anim.setStartValue(float(self.help_popup.windowOpacity()))
        op_anim.setEndValue(0.0)
        op_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        grp = QParallelAnimationGroup(self)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)
        grp.finished.connect(self._finish_help_popup_anim)
        self._help_popup_anim = grp
        grp.start()

    def eventFilter(self, obj, event):
        if obj is getattr(self, "help_hint_lbl", None):
            if event.type() == QEvent.Type.Enter:
                self._show_help_popup()
            elif event.type() == QEvent.Type.Leave:
                self._hide_help_popup()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self._hide_help_popup(immediate=True)
        super().closeEvent(event)

    def _build_switch_row(self, text: str, switch: ToggleSwitch) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(10)

        label = ClickableLabel(text)
        label.setWordWrap(True)
        label.clicked.connect(switch.toggle)
        row.addWidget(label, 1)
        row.addWidget(switch, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return row

    def apply_changes(self) -> None:
        if self.parent_window and hasattr(self.parent_window, "apply_game_mode_preferences"):
            self.parent_window.apply_game_mode_preferences(
                main_bypass_enabled=self.main_bypass_switch.isChecked(),
                user_lists_enabled=self.user_lists_switch.isChecked(),
                discord_enabled=self.discord_switch.isChecked(),
                restart_if_running=True,
            )

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
        self._gui_update_busy = False
        self._gui_update_worker = None
        self._pending_autostart = False
        self._pending_autostart_profile = " "
        self._site_manager_dlg = None
        self._instruction_dialog = None
        self._settings_dlg = None
        self._settings_guard_installed = False
        self._settings_guard_last_sound = 0.0
        self._game_settings_dlg = None
        self._telegram_help_msg = None
        self.game_mode_enabled = _is_game_mode_enabled(self.settings)
        self.telegram_mode_enabled = _is_telegram_mode_enabled(self.settings)
        self._telegram_mode_busy = False
        self._telegram_mode_worker = None
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
        self.show()
        self.setWindowState((self.windowState() & ~Qt.WindowState.WindowMinimized) | Qt.WindowState.WindowActive)
        self.raise_()
        self.activateWindow()

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

    def _play_settings_guard_sound(self) -> None:
        now = time.monotonic()
        if now - float(getattr(self, "_settings_guard_last_sound", 0.0)) < 0.65:
            return
        self._settings_guard_last_sound = now
        if sys.platform.startswith("win"):
            try:
                import winsound
                winsound.MessageBeep(0x00000040)  # MB_ICONASTERISK
                return
            except Exception:
                pass
        try:
            QApplication.beep()
        except Exception:
            pass

    def _nudge_settings_dialog(self) -> None:
        dlg = getattr(self, "_settings_dlg", None)
        if dlg is None or not dlg.isVisible():
            return
        self._play_settings_guard_sound()
        try:
            dlg.raise_()
            dlg.activateWindow()
        except Exception:
            pass

    def eventFilter(self, obj, event):
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

        self.action_start.setEnabled((not running) and (not pending_start))
        self.action_stop.setEnabled(running and (not pending_start))

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

    def _startup_blockers_active(self) -> bool:
        return bool(
            getattr(self, "_lists_check_in_progress", False)
            or getattr(self, "_gui_update_busy", False)
            or getattr(self, "_dns_malw_link_busy", False)
            or getattr(self, "_telegram_mode_busy", False)
        )

    def _set_pending_start_ui(self, active: bool) -> None:
        try:
            self.toggle_btn.blockSignals(True)
            self.toggle_btn.setChecked(False)
            self.toggle_btn.blockSignals(False)
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
        self.update_tray_status()

    def _queue_toggle_start(self, profile: str) -> None:
        self._pending_toggle_state = True
        self._pending_toggle_profile = profile
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
        self._set_pending_start_ui(False)

        if profile in self.presets:
            self.cb.setCurrentText(profile)

        self.toggle_btn.blockSignals(True)
        self.toggle_btn.setChecked(True)
        self.toggle_btn.blockSignals(False)
        QTimer.singleShot(0, lambda: self.on_toggle(True))

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

        if result.get("offline") and getattr(self, "_pending_toggle_state", None) is not True:
            self._show_lists_sync_network_notice()
        elif result.get("error"):
            print("Lists sync error:", result.get("error", ""))
        elif result.get("ai_dns_error"):
            print("Ai DNS sync error:", result.get("ai_dns_error", ""))

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
            self._start_gui_update_worker(latest_ver, str(gui_result.get("download_url") or ""))
            return True

        return False

    def _start_gui_update_worker(self, latest_ver: str, download_url: str) -> None:
        if getattr(self, "_gui_update_busy", False):
            return

        self._gui_update_busy = True
        try:
            self.status_lbl.setText(
                "Скачивание обновления GUI..." if self.lang == "ru" else "Downloading GUI update..."
            )
        except Exception:
            pass

        worker = ReleaseUpdateWorker("apply-gui", latest_ver, download_url, self)
        self._gui_update_worker = worker
        worker.finished_update.connect(self._on_gui_update_worker_finished)
        worker.start()

    def _on_gui_update_worker_finished(self, mode: str, result: dict) -> None:
        del mode
        self._gui_update_busy = False
        self._gui_update_worker = None

        if result.get("ok") and result.get("status") == "gui-restart-scheduled":
            self.status_lbl.setText(
                "GUI обновляется, перезапуск..." if self.lang == "ru" else "GUI is updating, restarting..."
            )
            QTimer.singleShot(250, self._shutdown_and_quit)
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

        if getattr(self, "_lists_check_in_progress", False):
            QMessageBox.information(
                self,
                title,
                "Дождитесь завершения проверки списков, затем запустите автоподбор."
                if self.lang == "ru" else
                "Wait for the list check to finish, then start auto selection."
            )
            return

        text = "Вы хотите выполнить автоматический подбор профиля?" if self.lang == "ru" else "Do you want to auto-select the best profile?"

        msg = QMessageBox(self)
        msg.setWindowTitle(title)
        msg.setIcon(QMessageBox.Icon.Question)
        msg.setText(text)
        btn_yes = msg.addButton("Да" if self.lang == "ru" else "Yes", QMessageBox.ButtonRole.YesRole)
        msg.addButton("Нет" if self.lang == "ru" else "No", QMessageBox.ButtonRole.NoRole)
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
                "Закройте программу и запустите EXE через ПКМ -> Запуск от имени администратора."
                if self.lang == "ru" else
                "Auto selection requires running the app as Administrator.\n"
                "Close the app and run the EXE: Right click -> Run as Administrator."
            )
            return

        self._auto_cancelled = False

        try:
            if hasattr(self, "_eta_timer") and self._eta_timer:
                self._eta_timer.stop()
        except Exception:
            pass

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
            self.telegram_proxy.stop()
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

        self.auto_btn = SmallCircleButton("A", "text", self)
        self.auto_btn.setFixedSize(28, 28)
        self.auto_btn.setToolTip("Автоматический подбор профиля" if self.lang == "ru" else "Automatic profile selection")
        self.auto_btn.clicked.connect(self.on_auto_pick_profile)

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

        self.auto_info_btn = SmallCircleButton("i", "text")
        self.auto_info_btn.setToolTip("Результаты последнего автоподбора")
        self.auto_info_btn.setFixedSize(24, 24)
        self.auto_info_btn.clicked.connect(self.show_autotest_info)
        self.auto_info_btn.hide()

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
        left_row = QHBoxLayout()
        left_row.setSpacing(4)
        left_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        left_row.addWidget(self.auto_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        left_row.addWidget(self.auto_info_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        left_row.setContentsMargins(0, 0, 0, 0)

        top_row.addLayout(left_row)
        top_row.addStretch()
        game_row = QHBoxLayout()
        game_row.setSpacing(4)
        game_row.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        game_row.addWidget(self.game_settings_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        game_row.addWidget(self.game_mode_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        top_row.addLayout(game_row)

        toggle_widget = QWidget(self)
        toggle_widget.setFixedHeight(114)
        hl = QHBoxLayout(toggle_widget)
        hl.setContentsMargins(0, 0, 0, 0)
        hl.addStretch()
        hl.addWidget(self.toggle_btn)
        hl.addStretch()
        layout.addWidget(toggle_widget)
        layout.addWidget(top_widget)

        self.cb = StableComboBox()
        self.cb.setObjectName("profileCombo")
        self.cb.setFixedHeight(31)
        self.reload_presets()
        self.cb.setCurrentText(self.last_profile)
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
        self._position_ai_mode_button()
        self._position_telegram_mode_button()
        self._update_small_circle_buttons_ui()
        self._update_ai_mode_ui()
        self._update_telegram_mode_ui()
        self._update_game_mode_ui()

    def _position_overlay_mode_buttons(self) -> None:
        self._position_ai_mode_button()
        self._position_telegram_mode_button()

    def _position_ai_mode_button(self) -> None:
        if not hasattr(self, "ai_mode_btn"):
            return
        x = 12
        y = 40
        if hasattr(self, "status_lbl"):
            try:
                y = max(8, int(self.status_lbl.y() + (self.status_lbl.height() - self.ai_mode_btn.height()) / 2))
            except Exception:
                y = 40
        if hasattr(self, "title_bar"):
            y = max(y, int(self.title_bar.height() + 6))
        self.ai_mode_btn.move(x, y)
        self.ai_mode_btn.raise_()

    def _position_telegram_mode_button(self) -> None:
        if not hasattr(self, "telegram_mode_btn"):
            return
        x = max(8, self.width() - self.telegram_mode_btn.width() - 12)
        y = 38
        if hasattr(self, "status_lbl"):
            try:
                y = max(8, int(self.status_lbl.y() + (self.status_lbl.height() - self.telegram_mode_btn.height()) / 2))
            except Exception:
                y = 38
        if hasattr(self, "title_bar"):
            y = max(y, int(self.title_bar.height() + 4))
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
            self.auto_btn.setToolTip("Автоматический подбор профиля" if self.lang == "ru" else "Automatic profile selection")

        if hasattr(self, "auto_info_btn"):
            self._apply_small_circle_button_state(self.auto_info_btn, True, "i", "text")

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
        self._position_ai_mode_button()
        self._position_telegram_mode_button()

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
            text = f"{text}\n\n{error}"
        _show_centered_message(self, QMessageBox.Icon.Warning, "Ai DNS", text)
        self._resume_pending_toggle_if_ready()

    def _start_dns_malw_link_poll(self, expected_active: bool) -> None:
        if self._dns_malw_link_poll_timer is None:
            self._dns_malw_link_poll_timer = QTimer(self)
            self._dns_malw_link_poll_timer.setInterval(900)
            self._dns_malw_link_poll_timer.timeout.connect(self._poll_dns_malw_link_status)
        self._dns_malw_link_expected_active = bool(expected_active)
        self._dns_malw_link_poll_attempts = 30
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
                "Telegram Mode включён: Telegram Web + Desktop proxy"
                if self.lang == "ru" else
                "Telegram Mode enabled: Telegram Web + Desktop proxy"
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
        self._set_telegram_mode_busy(False)

        error = str(result.get("error") or "").strip()
        if error:
            title = "Telegram Mode"
            text = (
                f"Не удалось применить Telegram Mode:\n{error}"
                if self.lang == "ru" else
                f"Failed to apply Telegram Mode:\n{error}"
            )
            _show_centered_message(self, QMessageBox.Icon.Warning, title, text)

        if result.get("ok") and action == "enable":
            self._show_telegram_proxy_hint_if_needed(int(result.get("proxy_port") or _get_telegram_proxy_port(self.settings)))

        if action in {"enable", "disable"} and hasattr(self, "toggle_btn") and self.toggle_btn.isChecked():
            self._schedule_game_mode_restart_after_change(
                "Применение Telegram Mode..."
                if self.lang == "ru" else
                "Applying Telegram Mode..."
            )

        self._update_telegram_mode_ui()
        self._resume_pending_toggle_if_ready()

    def _show_telegram_proxy_hint_if_needed(self, port: int) -> None:
        first_hint_was_shown = bool(
            self.settings.value(TELEGRAM_MODE_FIRST_PROXY_HINT_SHOWN_KEY, False, type=bool)
        )

        opened = False
        try:
            opened = QDesktopServices.openUrl(QUrl(f"tg://socks?server=127.0.0.1&port={int(port)}"))
        except Exception:
            opened = False

        if (not first_hint_was_shown) or (not opened):
            self.settings.setValue(TELEGRAM_MODE_FIRST_PROXY_HINT_SHOWN_KEY, True)
            self.settings.sync()
            _show_centered_message(
                self,
                QMessageBox.Icon.NoIcon,
                "Telegram Mode",
                (
                    "Если Telegram Desktop не предложил добавить proxy автоматически:\n"
                    f"Настройки -> Продвинутые -> Тип соединения -> SOCKS5\n"
                    f"IP: 127.0.0.1    Port: {int(port)}"
                    if self.lang == "ru" else
                    "If Telegram Desktop did not offer to add the proxy automatically:\n"
                    f"Settings -> Advanced -> Connection type -> SOCKS5\n"
                    f"IP: 127.0.0.1    Port: {int(port)}"
                ),
            )

    def show_telegram_mode_help(self) -> None:
        port = _get_telegram_proxy_port(self.settings)
        if _is_telegram_mode_enabled(self.settings):
            try:
                QDesktopServices.openUrl(QUrl(f"tg://socks?server=127.0.0.1&port={int(port)}"))
            except Exception:
                pass

        try:
            if self._telegram_help_msg is not None and self._telegram_help_msg.isVisible():
                self._telegram_help_msg.close()
        except Exception:
            pass

        text = (
            "Сначала включите Telegram Mode, затем, если у вас не появилось автоматическое "
            "добавление SOCKS5, нажмите снова на \"вопросик\".\n\n"
            "Если по какой-то причине у вас не работает автоматическое добавление протокола, "
            "выполните инструкцию вручную:\n\n"
            "Telegram Desktop:\n"
            "Настройки -> Продвинутые -> Тип соединения -> Использовать свой proxy\n"
            f"SOCKS5: 127.0.0.1:{int(port)}"
            if self.lang == "ru" else
            "First enable Telegram Mode. If SOCKS5 is not added automatically, click the "
            "\"question mark\" again.\n\n"
            "If automatic protocol setup does not work for some reason, follow this manual "
            "instruction:\n\n"
            "Telegram Desktop:\n"
            "Settings -> Advanced -> Connection type -> Use custom proxy\n"
            f"SOCKS5: 127.0.0.1:{int(port)}"
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
            try:
                self.telegram_proxy.start(port)
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
        script_name = self.presets.get(profile)
        if not script_name:
            self.retranslate_ui()
            return

        script = os.path.join(self.core_dir, script_name)
        if not os.path.exists(script):
            _show_centered_message(
                self,
                QMessageBox.Icon.Warning,
                "Ошибка" if self.lang == "ru" else "Error",
                f"Не найден файл:\n{script}" if self.lang == "ru" else f"File not found:\n{script}",
            )
            self.retranslate_ui()
            return

        try:
            self.process = self._launch_profile_process(script)
            self.status_lbl.setText(self.t("On: {}", profile))
        except Exception as e:
            _show_centered_message(
                self,
                QMessageBox.Icon.Warning,
                "Ошибка" if self.lang == "ru" else "Error",
                str(e),
            )
            self.toggle_btn.blockSignals(True)
            self.toggle_btn.setChecked(False)
            self.toggle_btn.blockSignals(False)
            self.process = None
            self.status_lbl.setText(self.t("Off"))
        self.update_tray_status()

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

    def _launch_profile_process(self, script: str):
        env = os.environ.copy()
        env["ZAPRETGUI_NOUPDATE"] = "1"
        env["NO_UPDATE_CHECK"] = "1"

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

        if self.game_mode_enabled:
            try:
                commandline = _build_game_mode_winws_command(script, self.core_dir, self.settings)
                if not commandline:
                    raise RuntimeError("Empty winws command line")
                return subprocess.Popen(
                    commandline,
                    cwd=os.path.join(self.core_dir, "bin"),
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    startupinfo=si,
                    creationflags=flags,
                    close_fds=True,
                )
            except Exception as e:
                print("Game mode launcher fallback:", e)

        inp_path = _ensure_no_update_input()
        fin = None
        try:
            try:
                fin = open(inp_path, "r", encoding="ascii")
            except Exception:
                fin = None

            return subprocess.Popen(
                ["cmd.exe", "/d", "/c", script],
                cwd=self.core_dir,
                stdin=fin if fin else subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                env=env,
                startupinfo=si,
                creationflags=flags,
                close_fds=True,
            )
        finally:
            try:
                if fin:
                    fin.close()
            except Exception:
                pass

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
        dlg.move(self._bottom_dialog_start_pos(dlg))
        dlg.show()
        self._animate_bottom_dialog_open(dlg, gap=8)
        dlg.raise_()
        dlg.activateWindow()

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
        if (not checked) and getattr(self, "_pending_toggle_state", None) is True:
            self._pending_toggle_state = None
            self._pending_toggle_profile = " "
            self._set_pending_start_ui(False)
            return

        profile = self.cb.currentText()

        if checked and self._startup_blockers_active():
            self._queue_toggle_start(profile)
            return

        self.settings.setValue("last_profile", profile)

        script = os.path.join(self.core_dir, self.presets[profile])
        if not os.path.exists(script):
            _show_centered_message(self, QMessageBox.Icon.Warning, "Ошибка", f"Не найден файл:\n{script}")
            self.toggle_btn.setChecked(False)
            self.update_tray_status()
            return

        if checked:
            _ensure_user_lists_initialized()
            _apply_game_mode_state_to_core(self.settings)
            self._ensure_telegram_mode_ready_for_bypass()
            _rebuild_runtime_lists(self.settings)
            _force_stop_blockers()
            try:
                self.process = self._launch_profile_process(script)
                self.status_lbl.setText(self.t("On: {}", profile))
            except Exception as e:
                _show_centered_message(
                    self,
                    QMessageBox.Icon.Warning,
                    "Ошибка" if self.lang == "ru" else "Error",
                    str(e)
                )
                self.toggle_btn.setChecked(False)
                self.process = None
                self.status_lbl.setText(self.t("Off"))
                self.update_tray_status()
                return

        else:
            _run_hidden(["taskkill", "/IM", "winws.exe", "/F"])

            if self.process and self.process.poll() is None:
                _run_hidden(["taskkill", "/PID", str(self.process.pid), "/T", "/F"])

            self.process = None
            self.status_lbl.setText(self.t("Off"))

        self.retranslate_ui()
        self.update_tray_status()

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
            self.set_autostart(self.autostart)
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


def _same_file_path(left: str, right: str) -> bool:
    try:
        return os.path.normcase(os.path.realpath(left)) == os.path.normcase(os.path.realpath(right))
    except Exception:
        return os.path.normcase(str(left or "")) == os.path.normcase(str(right or ""))


def _find_existing_app_processes() -> list[dict]:
    try:
        import psutil
    except Exception:
        return []

    rows = []
    current_pid = os.getpid()
    current_exe = sys.executable if getattr(sys, "frozen", False) else os.path.abspath(sys.argv[0])
    current_script = os.path.abspath(sys.argv[0])
    frozen_name = "ZapretGUI.exe".casefold()

    for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
        try:
            if int(proc.info.get("pid") or 0) == current_pid:
                continue
            name = str(proc.info.get("name") or "")
            exe = str(proc.info.get("exe") or "")
            cmdline = [str(x) for x in (proc.info.get("cmdline") or [])]
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

        matched = False
        if exe and _same_file_path(exe, current_exe):
            matched = True
        elif name.casefold() == frozen_name and os.path.basename(exe or name).casefold() == frozen_name:
            matched = True
        elif not getattr(sys, "frozen", False):
            for part in cmdline:
                if part and _same_file_path(part, current_script):
                    matched = True
                    break

        if matched:
            rows.append({"pid": int(proc.info.get("pid") or 0), "name": name or os.path.basename(exe), "exe": exe})
    return rows


def _terminate_existing_app_processes(processes: list[dict], timeout: float = 4.0) -> tuple[bool, str]:
    try:
        import psutil
    except Exception as e:
        return False, str(e)

    targets = []
    for row in processes:
        try:
            pid = int(row.get("pid") or 0)
            if pid and pid != os.getpid():
                targets.append(psutil.Process(pid))
        except Exception:
            pass

    if not targets:
        return True, ""

    errors = []
    for proc in targets:
        try:
            proc.terminate()
        except Exception as e:
            errors.append(str(e))

    try:
        gone, alive = psutil.wait_procs(targets, timeout=timeout)
    except Exception:
        alive = targets

    for proc in alive:
        try:
            proc.kill()
        except Exception as e:
            errors.append(str(e))

    try:
        _, alive = psutil.wait_procs(alive, timeout=2.0)
    except Exception:
        pass

    still_alive = []
    for proc in targets:
        try:
            if proc.is_running():
                still_alive.append(str(proc.pid))
        except Exception:
            pass

    if still_alive:
        return False, "; ".join(errors) or ("still running: " + ", ".join(still_alive))
    return True, ""


SINGLE_INSTANCE_MUTEX_NAME = "Local\\ZapretGUI_SingleInstance"


def _try_acquire_single_instance_lock() -> tuple[bool, int | None, str]:
    if not sys.platform.startswith("win"):
        return True, None, ""

    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        kernel32.CreateMutexW.restype = ctypes.c_void_p
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool

        ctypes.set_last_error(0)
        handle = kernel32.CreateMutexW(None, False, SINGLE_INSTANCE_MUTEX_NAME)
        err = ctypes.get_last_error()
        if not handle:
            return True, None, f"CreateMutexW failed: {err}"
        if err == 183:  # ERROR_ALREADY_EXISTS
            try:
                kernel32.CloseHandle(handle)
            except Exception:
                pass
            return False, None, "already-running"
        return True, int(handle), ""
    except Exception as e:
        return True, None, str(e)


def _release_single_instance_lock(handle: int | None) -> None:
    if not handle or not sys.platform.startswith("win"):
        return
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.CloseHandle.argtypes = [ctypes.c_void_p]
        kernel32.CloseHandle.restype = ctypes.c_bool
        kernel32.CloseHandle(ctypes.c_void_p(int(handle)))
    except Exception:
        pass


def _keep_single_instance_lock(app: QApplication, handle: int | None) -> None:
    if not handle:
        return
    try:
        app._zapret_single_instance_mutex = handle
        app.aboutToQuit.connect(lambda h=handle: _release_single_instance_lock(h))
    except Exception:
        pass


def _handle_existing_instance_before_start(app: QApplication) -> bool:
    acquired, handle, _error = _try_acquire_single_instance_lock()
    if acquired:
        _keep_single_instance_lock(app, handle)
        return True

    lang = "ru"
    try:
        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
        lang = str(settings.value("lang", "ru") or "ru")
    except Exception:
        pass

    msg = QMessageBox()
    msg.setWindowTitle("ZapretGUI")
    msg.setIcon(QMessageBox.Icon.Warning)
    msg.setText(
        "ZapretGUI уже запущен.\n\nПерезапустить существующий экземпляр?"
        if lang == "ru" else
        "ZapretGUI is already running.\n\nRestart the existing instance?"
    )
    restart_btn = msg.addButton("Перезапустить" if lang == "ru" else "Restart", QMessageBox.ButtonRole.AcceptRole)
    cancel_btn = msg.addButton("Отмена" if lang == "ru" else "Cancel", QMessageBox.ButtonRole.RejectRole)
    msg.setDefaultButton(cancel_btn)
    msg.adjustSize()
    _center_widget_on_screen(msg, None)
    msg.exec()

    if msg.clickedButton() != restart_btn:
        return False

    try:
        _force_stop_blockers()
    except Exception:
        pass

    existing = _find_existing_app_processes()
    ok, error = _terminate_existing_app_processes(existing)
    if ok:
        for _ in range(30):
            acquired, handle, _error = _try_acquire_single_instance_lock()
            if acquired:
                _keep_single_instance_lock(app, handle)
                return True
            time.sleep(0.15)
        error = _error or "single-instance lock is still held"

    _show_centered_message(
        None,
        QMessageBox.Icon.Warning,
        "ZapretGUI",
        (
            "Не удалось остановить уже запущенный экземпляр.\n"
            "Закройте его вручную или запустите перезапуск от имени администратора.\n\n"
            f"{error}"
        )
        if lang == "ru" else
        (
            "Could not stop the already running instance.\n"
            "Close it manually or restart with administrator rights.\n\n"
            f"{error}"
        ),
    )
    return False


def main():
    dns_cli_action = None
    for arg in sys.argv[1:]:
        if arg.startswith("--dns-malw-link-action="):
            dns_cli_action = arg.split("=", 1)[1].strip().lower()
            break

    if dns_cli_action in {"enable", "disable"}:
        settings = QSettings(SETTINGS_FILE, QSettings.Format.IniFormat)
        if dns_cli_action == "enable":
            _enable_dns_malw_link(settings)
        else:
            _disable_dns_malw_link(settings)
        return

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
    _apply_unified_qt_style(app)
    if not _handle_existing_instance_before_start(app):
        return
    wipe_app_dir_if_new_version()
    extract_files_from_meipass()
    restore_pending_user_strategies_after_extract()
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
