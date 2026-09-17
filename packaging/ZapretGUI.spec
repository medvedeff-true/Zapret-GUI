# -*- mode: python ; coding: utf-8 -*-
"""Optional PyInstaller spec for the repository's src/resources layout.

The preferred release command is ``python tools/build_release.py``.  It keeps
its generated spec below ``build/``; this tracked file is useful for IDE and
manual PyInstaller invocations.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
RESOURCES_DIR = ROOT / "resources"

_datas = [
    (str(RESOURCES_DIR / "flags"), "flags"),
    (str(RESOURCES_DIR / "core"), "core"),
    (str(RESOURCES_DIR / "adaptive-runtime"), "adaptive-runtime"),
    (str(SRC_DIR / "zapret_gui" / "app_modules"), "app_modules"),
    (str(RESOURCES_DIR / "background_service" / "ZapretGUI.Service.exe"), "background_service"),
]
_datas += collect_data_files("certifi")

_hiddenimports = [
    "PyQt6.sip",
    "psutil",
    "requests",
    "cryptography",
    "zapret_gui.telegram_proxy",
    "bypass_service",
    "adaptive_strategy",
    "tg_ws_proxy_vendor.proxy.tg_ws_proxy",
    "tg_ws_proxy_vendor.proxy.bridge",
    "tg_ws_proxy_vendor.proxy.config",
    "tg_ws_proxy_vendor.proxy.stats",
    "tg_ws_proxy_vendor.proxy.balancer",
    "tg_ws_proxy_vendor.proxy.utils",
    "tg_ws_proxy_vendor.proxy.raw_websocket",
    "tg_ws_proxy_vendor.proxy.fake_tls",
    "urllib3",
    "idna",
    "charset_normalizer",
    "certifi",
]
_hiddenimports += collect_submodules("tg_ws_proxy_vendor")
_hiddenimports += collect_submodules("adaptive_strategy")


a = Analysis(
    [str(SRC_DIR / "zapret_gui" / "app.py")],
    pathex=[str(SRC_DIR)],
    binaries=[],
    datas=_datas,
    hiddenimports=_hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ZapretGUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    version=str(ROOT / "version.txt"),
    icon=[str(RESOURCES_DIR / "flags" / "Z.ico")],
)
