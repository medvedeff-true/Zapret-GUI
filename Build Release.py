import os
import sys
import shutil
import subprocess
import importlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SCRIPT_NAME = "EzUnBlock.py"
BASE_NAME = "ZapretGUI"

SCRIPT_PATH = ROOT / SCRIPT_NAME
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
    "psutil": "psutil",
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
    product_version = read_version_resource_string("ProductVersion")
    file_tuple = read_version_resource_tuple("filevers")
    product_tuple = read_version_resource_tuple("prodvers")

    mismatches = []
    if file_version != app_version:
        mismatches.append(f"FileVersion={file_version}, expected {app_version}")
    if product_version != app_version:
        mismatches.append(f"ProductVersion={product_version}, expected {app_version}")
    if file_tuple != expected_tuple:
        mismatches.append(f"filevers={file_tuple}, expected {expected_tuple}")
    if product_tuple != expected_tuple:
        mismatches.append(f"prodvers={product_tuple}, expected {expected_tuple}")

    if mismatches:
        raise RuntimeError("Version mismatch:\n- " + "\n- ".join(mismatches))


def validate_resources() -> None:
    required_paths = [
        (SCRIPT_PATH, "main script"),
        (VERSION_FILE, "version resource"),
        (FLAGS_DIR, "flags folder"),
        (CORE_DIR, "core folder"),
        (ICON_PATH, "application icon"),
        (FLAGS_DIR / "toggle-off.ico", "toggle-off icon"),
        (FLAGS_DIR / "toggle-on.ico", "toggle-on icon"),
        (FLAGS_DIR / "tray-off.ico", "tray-off icon"),
        (FLAGS_DIR / "tray-on.ico", "tray-on icon"),
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


def run_preflight() -> None:
    validate_resources()
    validate_versions()
    print(f"Preflight OK: {BASE_NAME} {read_app_version()}")


run_preflight()

if any(arg.lower() in {"--preflight", "--check", "--no-build"} for arg in sys.argv[1:]):
    sys.exit(0)


def running_release_processes() -> list[str]:
    rows = []
    target_name = f"{BASE_NAME}.exe".casefold()
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
    "--hidden-import=PyQt6.sip",
    "--hidden-import=psutil",
    "--hidden-import=requests",
    "--hidden-import=urllib3",
    "--hidden-import=idna",
    "--hidden-import=charset_normalizer",
    "--hidden-import=certifi",
    str(SCRIPT_PATH),
]

print("Building exe...")
subprocess.run(cmd, check=True, cwd=str(ROOT))
print("Build completed!")

src_exe = DIST_DIR / f"{BASE_NAME}.exe"
assert src_exe.exists(), f"Build result not found: {src_exe}"

print(f"\nReady: {src_exe}")
