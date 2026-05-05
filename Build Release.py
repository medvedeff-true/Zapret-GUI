import os
import sys
import shutil
import subprocess
import importlib
import re
import hashlib
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT_NAME = "EzUnBlock.py"
BASE_NAME = "ZapretGUI"
EXE_NAME = f"{BASE_NAME}.exe"
RELEASE_ZIP_TEMPLATE = f"{BASE_NAME}-{{version}}.zip"

SCRIPT_PATH = ROOT / SCRIPT_NAME
TELEGRAM_PROXY_PATH = ROOT / "telegram_proxy.py"
TG_WS_PROXY_VENDOR_DIR = ROOT / "tg_ws_proxy_vendor"
ICON_PATH = ROOT / "flags" / "Z.ico"
VERSION_FILE = ROOT / "version.txt"
FLAGS_DIR = ROOT / "flags"
CORE_DIR = ROOT / "core"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"

SPEC_FILES = (
    ROOT / f"{BASE_NAME}.spec",
    ROOT / f"{Path(SCRIPT_NAME).stem}.spec",
)

required_modules = {
    "PyInstaller": "pyinstaller",
    "PyQt6": "PyQt6",
    "requests": "requests",
    "certifi": "certifi",
    "charset_normalizer": "charset-normalizer",
    "idna": "idna",
    "urllib3": "urllib3",
    "psutil": "psutil",
    "cryptography": "cryptography",
}

missing_modules = []
for module_name, package_name in required_modules.items():
    try:
        importlib.import_module(module_name)
    except Exception:
        missing_modules.append(package_name)

if missing_modules:
    missing_str = ", ".join(missing_modules)
    raise FileNotFoundError(
        f"Missing build dependencies: {missing_str}\n"
        f"Install with: {sys.executable} -m pip install {' '.join(missing_modules)}"
    )

import psutil


def require_path(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")


def read_app_version() -> str:
    text = SCRIPT_PATH.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.MULTILINE)
    if not match:
        raise RuntimeError("APP_VERSION not found in EzUnBlock.py")
    return match.group(1).strip()


def version_tuple(version: str) -> tuple[int, int, int, int]:
    parts = [int(part) for part in re.findall(r"\d+", version)[:4]]
    return tuple((parts + [0, 0, 0, 0])[:4])


def read_version_resource_string(name: str) -> str:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(
        rf"StringStruct\(\s*['\"]{re.escape(name)}['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        text,
    )
    if not match:
        raise RuntimeError(f"{name} not found in version.txt")
    return match.group(1).strip()


def read_version_resource_tuple(name: str) -> tuple[int, int, int, int]:
    text = VERSION_FILE.read_text(encoding="utf-8")
    match = re.search(rf"{re.escape(name)}\s*=\s*\(([^)]*)\)", text)
    if not match:
        raise RuntimeError(f"{name} tuple not found in version.txt")
    values = [int(part.strip()) for part in match.group(1).split(",") if part.strip()]
    return tuple((values + [0, 0, 0, 0])[:4])


def validate_versions() -> None:
    app_version = read_app_version()
    expected_tuple = version_tuple(app_version)

    file_version = read_version_resource_string("FileVersion")
    original_filename = read_version_resource_string("OriginalFilename")
    product_version = read_version_resource_string("ProductVersion")
    file_tuple = read_version_resource_tuple("filevers")
    product_tuple = read_version_resource_tuple("prodvers")

    mismatches = []
    if file_version != app_version:
        mismatches.append(f"FileVersion={file_version}, expected {app_version}")
    if product_version != app_version:
        mismatches.append(f"ProductVersion={product_version}, expected {app_version}")
    if original_filename != EXE_NAME:
        mismatches.append(f"OriginalFilename={original_filename}, expected {EXE_NAME}")
    if file_tuple != expected_tuple:
        mismatches.append(f"filevers={file_tuple}, expected {expected_tuple}")
    if product_tuple != expected_tuple:
        mismatches.append(f"prodvers={product_tuple}, expected {expected_tuple}")

    if mismatches:
        raise RuntimeError("Version mismatch:\n- " + "\n- ".join(mismatches))


def validate_resources() -> None:
    required_paths = [
        (SCRIPT_PATH, "main script"),
        (TELEGRAM_PROXY_PATH, "Telegram proxy module"),
        (TG_WS_PROXY_VENDOR_DIR, "vendored TG WS proxy package"),
        (TG_WS_PROXY_VENDOR_DIR / "__init__.py", "vendored TG WS proxy package init"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "__init__.py", "vendored TG WS proxy module init"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "tg_ws_proxy.py", "vendored TG WS proxy runtime"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "bridge.py", "vendored TG WS proxy bridge"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "config.py", "vendored TG WS proxy config"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "stats.py", "vendored TG WS proxy stats"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "balancer.py", "vendored TG WS proxy balancer"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "utils.py", "vendored TG WS proxy utils"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "raw_websocket.py", "vendored TG WS proxy websocket"),
        (TG_WS_PROXY_VENDOR_DIR / "proxy" / "fake_tls.py", "vendored TG WS proxy fake TLS"),
        (VERSION_FILE, "version resource"),
        (FLAGS_DIR, "flags folder"),
        (CORE_DIR, "core folder"),
        (ICON_PATH, "application icon"),
        (FLAGS_DIR / "settings.png", "settings icon"),
        (FLAGS_DIR / "info.ico", "info icon"),
        (FLAGS_DIR / "toggle-off.ico", "toggle-off icon"),
        (FLAGS_DIR / "toggle-on.ico", "toggle-on icon"),
        (FLAGS_DIR / "toggle.ico", "legacy toggle icon"),
        (FLAGS_DIR / "tray-off.ico", "tray-off icon"),
        (FLAGS_DIR / "tray-on.ico", "tray-on icon"),
        (FLAGS_DIR / "tray.ico", "legacy tray icon"),
        (FLAGS_DIR / "tg.png", "Telegram mode icon"),
        (FLAGS_DIR / "joy.png", "game mode icon"),
        (FLAGS_DIR / "z-green.png", "green logo image"),
        (FLAGS_DIR / "z-red.png", "red logo image"),
        (FLAGS_DIR / "ru.png", "Russian flag icon"),
        (FLAGS_DIR / "en.png", "English flag icon"),
        (CORE_DIR / "service.bat", "core service script"),
        (CORE_DIR / "fast" / "Uninstall.bat", "core uninstall script"),
        (CORE_DIR / "bin" / "winws.exe", "winws binary"),
        (CORE_DIR / "bin" / "WinDivert.dll", "WinDivert DLL"),
        (CORE_DIR / "bin" / "WinDivert64.sys", "WinDivert driver"),
        (CORE_DIR / "lists" / "list-general.txt", "general domain list"),
        (CORE_DIR / "lists" / "list-exclude.txt", "exclude domain list"),
        (CORE_DIR / "lists" / "list-google.txt", "Google domain list"),
        (CORE_DIR / "lists" / "list-discord.txt", "Discord domain list"),
        (CORE_DIR / "lists" / "ipset-all.txt", "main IP list"),
        (CORE_DIR / "lists" / "ipset-exclude.txt", "exclude IP list"),
        (CORE_DIR / "lists" / "telegram-domains.txt", "Telegram domain runtime list"),
        (CORE_DIR / "lists" / "telegram-ipset.txt", "Telegram IP runtime list"),
        (CORE_DIR / "utils" / "targets.txt", "auto-test targets"),
        (CORE_DIR / "utils" / "check_updates.enabled", "core update flag"),
    ]

    for path, description in required_paths:
        require_path(path, description)

    optional_release_files = [
        CORE_DIR / "user" / "medvedeff-game-list-all.txt",
        CORE_DIR / "user" / "medvedeff-game-ipset.txt",
    ]
    missing_optional = [path for path in optional_release_files if not path.exists()]
    if missing_optional:
        print("Warning: optional bundled gaming list seeds are missing:")
        for path in missing_optional:
            print(f"  - {path}")

    referenced_optional_scripts = [
        CORE_DIR / "fast" / "install_service.bat",
        CORE_DIR / "fast" / "install_discord_service.bat",
    ]
    missing_referenced = [path for path in referenced_optional_scripts if not path.exists()]
    if missing_referenced:
        print("Warning: settings UI references optional service installer scripts that are missing:")
        for path in missing_referenced:
            print(f"  - {path}")


def run_preflight() -> None:
    validate_resources()
    validate_versions()
    print(f"Preflight OK: {BASE_NAME} {read_app_version()}", flush=True)


run_preflight()

if any(arg.lower() in {"--preflight", "--check", "--no-build"} for arg in sys.argv[1:]):
    sys.exit(0)


def running_release_processes() -> list[str]:
    rows = []
    target_name = EXE_NAME.casefold()
    for proc in psutil.process_iter(["pid", "name", "exe"]):
        try:
            name = str(proc.info.get("name") or "")
            exe = str(proc.info.get("exe") or "")
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

        if name.casefold() == target_name or Path(exe).name.casefold() == target_name:
            suffix = f" ({exe})" if exe else ""
            rows.append(f"PID {proc.info.get('pid')}: {name or target_name}{suffix}")
    return rows


def remove_tree(path: Path) -> None:
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
    except PermissionError as e:
        running = running_release_processes()
        details = "\n".join(f"  - {row}" for row in running)
        if details:
            details = "\nRunning ZapretGUI processes:\n" + details
        raise SystemExit(
            f"Cannot clean {path}: access denied.\n"
            f"Close the running {BASE_NAME}.exe window/tray process and run the build again."
            f"{details}"
        ) from None


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def write_release_zip(exe_path: Path, version: str) -> Path:
    zip_path = DIST_DIR / RELEASE_ZIP_TEMPLATE.format(version=version)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        z.write(exe_path, arcname=EXE_NAME)

    if not zip_path.exists() or zip_path.stat().st_size <= 1024:
        raise RuntimeError(f"Release zip was not created correctly: {zip_path}")

    with zipfile.ZipFile(zip_path, "r") as z:
        names = z.namelist()
        bad = z.testzip()
    if bad:
        raise RuntimeError(f"Release zip is damaged, first bad file: {bad}")
    if EXE_NAME not in names:
        raise RuntimeError(f"Release zip must contain {EXE_NAME} at archive root")

    sha_path = zip_path.with_suffix(zip_path.suffix + ".sha256")
    sha_path.write_text(f"{file_sha256(zip_path)}  {zip_path.name}\n", encoding="ascii")
    return zip_path


# Clean previous build
for folder in (BUILD_DIR, DIST_DIR):
    remove_tree(folder)

for spec_file in SPEC_FILES:
    if spec_file.exists():
        spec_file.unlink()

sep = os.pathsep


def add_data(source: Path, target: str) -> str:
    return f"--add-data={source}{sep}{target}"


cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    "--clean",
    "--noconfirm",
    f"--icon={ICON_PATH}",
    f"--name={BASE_NAME}",
    f"--distpath={DIST_DIR}",
    f"--workpath={BUILD_DIR}",
    f"--specpath={ROOT}",
    add_data(FLAGS_DIR, "flags"),
    add_data(CORE_DIR, "core"),
    "--version-file", str(VERSION_FILE),
    "--collect-data=certifi",
    "--collect-submodules=tg_ws_proxy_vendor",
    "--hidden-import=PyQt6.sip",
    "--hidden-import=psutil",
    "--hidden-import=requests",
    "--hidden-import=cryptography",
    "--hidden-import=telegram_proxy",
    "--hidden-import=tg_ws_proxy_vendor.proxy.tg_ws_proxy",
    "--hidden-import=tg_ws_proxy_vendor.proxy.bridge",
    "--hidden-import=tg_ws_proxy_vendor.proxy.config",
    "--hidden-import=tg_ws_proxy_vendor.proxy.stats",
    "--hidden-import=tg_ws_proxy_vendor.proxy.balancer",
    "--hidden-import=tg_ws_proxy_vendor.proxy.utils",
    "--hidden-import=tg_ws_proxy_vendor.proxy.raw_websocket",
    "--hidden-import=tg_ws_proxy_vendor.proxy.fake_tls",
    "--hidden-import=urllib3",
    "--hidden-import=idna",
    "--hidden-import=charset_normalizer",
    "--hidden-import=certifi",
    str(SCRIPT_PATH),
]

print("Building exe...", flush=True)
subprocess.run(cmd, check=True, cwd=str(ROOT))
print("Build completed!", flush=True)

src_exe = DIST_DIR / EXE_NAME
assert src_exe.exists(), f"Build result not found: {src_exe}"

app_version = read_app_version()
release_zip = write_release_zip(src_exe, app_version)

print(f"\nReady exe: {src_exe}", flush=True)
print(f"Ready release zip: {release_zip}", flush=True)
print(f"Release zip SHA256: {file_sha256(release_zip)}", flush=True)
