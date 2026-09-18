import sys
import os
from zapret_gui.startup_diagnostics import initialize as _initialize_startup_diagnostics, logger as _startup_log

if __name__ == "__main__" or getattr(sys, "frozen", False):
    _initialize_startup_diagnostics()

import subprocess
import csv
import ipaddress
import base64
import math
import tempfile
import threading
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import (
    Qt, QSettings, QSize, QTimer, QThread, pyqtSignal,
    QElapsedTimer, QEvent, QEasingCurve, QPropertyAnimation, pyqtProperty,
    QParallelAnimationGroup, QPoint, QPointF, QRectF, QUrl, QVariantAnimation
)
from PyQt6.QtGui import (
    QIcon, QPixmap, QImage, QAction, QPalette, QPainter, QColor, QPen, QBrush,
    QLinearGradient, QDesktopServices, QGuiApplication, QPainterPath, QRegion
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QComboBox, QDialog, QCheckBox, QMessageBox, QSizePolicy,
    QSystemTrayIcon, QMenu, QTextBrowser, QProgressDialog, QGraphicsDropShadowEffect,
    QGraphicsOpacityEffect, QStackedWidget,
    QListWidget, QListWidgetItem, QListView, QTabWidget, QToolButton, QFileDialog, QLineEdit,
    QAbstractItemView, QStyle, QStyledItemDelegate, QTabBar, QFrame, QProgressBar
)
import shutil
import requests
import zipfile
import io
import re
import socket
import time
import ctypes
from ctypes import wintypes
import json
import hashlib
from urllib.parse import quote, urlsplit
from zapret_gui.telegram_proxy import TelegramProxyController
from bypass_service import controller as _bypass_service
from adaptive_strategy import (
    RuntimePaths as AdaptiveRuntimePaths,
    SearchEngine as AdaptiveSearchEngine,
    ZapretGuiBatGenerator,
    parse_targets as parse_adaptive_targets,
    select_profile_builder_targets as select_adaptive_profile_targets,
    validate_strategy_name,
)
from adaptive_strategy.engine import SearchCancelled as AdaptiveSearchCancelled
from adaptive_strategy.generator import profile_requires_telegram_hosts
from adaptive_strategy.resources import ensure_adaptive_runtime


if __name__ == "__main__" and "--startup-self-test" in sys.argv:
    # An explicit packaging probe: load Qt and the real onefile imports without
    # touching Run, services, hosts, runtime migration or the user's settings.
    destination = sys.argv[sys.argv.index("--startup-self-test") + 1]
    probe = QApplication(sys.argv)
    QTimer.singleShot(50, probe.quit)
    result = probe.exec()
    Path(destination).write_text(json.dumps({
        "exit_code": result,
        "frozen": bool(getattr(sys, "frozen", False)),
        "executable": sys.executable,
        "cwd": os.getcwd(),
        "argv": sys.argv,
        "tray_available": QSystemTrayIcon.isSystemTrayAvailable(),
    }, ensure_ascii=False), encoding="utf-8")
    raise SystemExit(result)


# The executable entry point and backwards-compatible public module.
#
# Feature code is separated into app_modules/*.py.  Fragments are executed in
# this module's global namespace so legacy functions, Qt classes, integrations,
# and tests that patch ``EzUnBlock.<name>`` retain their exact lookup behavior.
# PyInstaller bundles app_modules as data, including in --onefile builds.
_SOURCE_FRAGMENT_NAMES = (
    'runtime_setup.py',
    'app_config.py',
    'ui_base.py',
    'runtime_data.py',
    'dns_service.py',
    'list_management.py',
    'updates.py',
    'dialogs_and_workers.py',
    'adaptive_ui.py',
    'ui_controls.py',
    'site_manager.py',
    'main_window.py',
    'application_lifecycle.py',
)


def _source_fragments_root() -> Path:
    """Return the source-fragment directory in development and frozen builds."""
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        fragment_root = Path(meipass) / "app_modules"
        if fragment_root.is_dir():
            return fragment_root
    return Path(__file__).resolve().parent / "app_modules"


def _execute_source_fragment(path: Path) -> None:
    """Compile a fragment with its own filename but retain this module's globals."""
    import types

    source = path.read_text(encoding="utf-8")
    fragment_module_name = f"{__name__}.__source_fragments__.{path.stem}"
    fragment_module = types.ModuleType(fragment_module_name)
    fragment_module.__file__ = str(path)
    sys.modules[fragment_module_name] = fragment_module

    existing_class_ids = {
        id(value)
        for value in globals().values()
        if isinstance(value, type)
    }
    exec(compile(source, str(path), "exec"), globals(), globals())

    # Keep source introspection accurate after executing the fragment in this
    # compatibility module's namespace. Function global lookups still resolve
    # through EzUnBlock exactly as they did before the split.
    for value in globals().values():
        if isinstance(value, type) and id(value) not in existing_class_ids:
            value.__module__ = fragment_module_name
            # Python 3.13 stores the definition line separately from
            # ``co_firstlineno``; update it for classes created by ``exec``.
            # This keeps inspect.getsource() and IDE navigation correct.
            if not hasattr(value, "__firstlineno__"):
                try:
                    value.__firstlineno__ = next(
                        index
                        for index, line in enumerate(source.splitlines(), 1)
                        if line.lstrip().startswith(f"class {value.__name__}")
                    )
                except StopIteration:
                    pass


_source_fragment_root = _source_fragments_root()
for _source_fragment_name in _SOURCE_FRAGMENT_NAMES:
    _execute_source_fragment(_source_fragment_root / _source_fragment_name)

# Keep the fragment list as a small introspection aid for support tools. The
# loader helpers are private implementation details and are removed.
del _source_fragment_name
del _source_fragment_root
del _execute_source_fragment
del _source_fragments_root


if __name__ == '__main__':
    main()
