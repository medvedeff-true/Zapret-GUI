import os
import sys
import shutil
import subprocess
import importlib
import json
import re
import base64
import hashlib
import zipfile
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT / "src"
RESOURCES_DIR = ROOT / "resources"
TOOLS_DIR = ROOT / "tools"
PACKAGING_DIR = ROOT / "packaging"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
SCRIPT_NAME = "src/zapret_gui/app.py"
BASE_NAME = "ZapretGUI"
EXE_NAME = f"{BASE_NAME}.exe"
RELEASE_ZIP_TEMPLATE = f"{BASE_NAME}-{{version}}.zip"

SCRIPT_PATH = ROOT / SCRIPT_NAME
TELEGRAM_PROXY_PATH = SRC_DIR / "zapret_gui" / "telegram_proxy.py"
BYPASS_SERVICE_PATH = SRC_DIR / "bypass_service.py"
TG_WS_PROXY_VENDOR_DIR = SRC_DIR / "tg_ws_proxy_vendor"
ICON_PATH = RESOURCES_DIR / "flags" / "Z.ico"
VERSION_FILE = ROOT / "version.txt"
FLAGS_DIR = RESOURCES_DIR / "flags"
CORE_DIR = RESOURCES_DIR / "core"
ADAPTIVE_RUNTIME_DIR = RESOURCES_DIR / "adaptive-runtime"
ADAPTIVE_RUNTIME_MANIFEST = ADAPTIVE_RUNTIME_DIR / "manifest.json"
ADAPTIVE_STRATEGY_DIR = SRC_DIR / "adaptive_strategy"
APP_MODULES_DIR = SRC_DIR / "zapret_gui" / "app_modules"
APP_MODULE_FILES = (
    "runtime_setup.py",
    "app_config.py",
    "ui_base.py",
    "runtime_data.py",
    "dns_service.py",
    "list_management.py",
    "updates.py",
    "dialogs_and_workers.py",
    "adaptive_ui.py",
    "ui_controls.py",
    "site_manager.py",
    "main_window.py",
    "application_lifecycle.py",
)
AI_DNS_SEED_PATH = CORE_DIR / "lists" / "dns_malw_hosts_seed.txt"
SERVICE_DIR = RESOURCES_DIR / "background_service"
SERVICE_SOURCE_DIR = TOOLS_DIR / "background_service"
BUILD_DIR = ROOT / "build"
DIST_DIR = ROOT / "dist"
AI_DNS_MAIN_SOURCES = (
    ("github-api", "https://api.github.com/repos/ImMALWARE/dns.malw.link/contents/hosts?ref=master", "github-api"),
    ("raw", "https://raw.githubusercontent.com/ImMALWARE/dns.malw.link/master/hosts", "text"),
    ("jsdelivr", "https://cdn.jsdelivr.net/gh/ImMALWARE/dns.malw.link@master/hosts", "text"),
    ("gcore-jsdelivr", "https://gcore.jsdelivr.net/gh/ImMALWARE/dns.malw.link@master/hosts", "text"),
    ("fastly-jsdelivr", "https://fastly.jsdelivr.net/gh/ImMALWARE/dns.malw.link@master/hosts", "text"),
)
AI_DNS_ADDITIONAL_SOURCES = (
    ("github-api", "https://api.github.com/repos/AvenCores/Goida-AI-Unlocker/contents/additional_hosts.py?ref=main", "github-api"),
    ("raw", "https://raw.githubusercontent.com/AvenCores/Goida-AI-Unlocker/main/additional_hosts.py", "text"),
    ("jsdelivr", "https://cdn.jsdelivr.net/gh/AvenCores/Goida-AI-Unlocker@main/additional_hosts.py", "text"),
    ("gcore-jsdelivr", "https://gcore.jsdelivr.net/gh/AvenCores/Goida-AI-Unlocker@main/additional_hosts.py", "text"),
    ("fastly-jsdelivr", "https://fastly.jsdelivr.net/gh/AvenCores/Goida-AI-Unlocker@main/additional_hosts.py", "text"),
)
AI_DNS_ADDITIONAL_VERSION_RE = re.compile(r'version_add\s*=\s*["\\\']([^"\\\']+)["\\\']')
AI_DNS_ADDITIONAL_HOSTS_RE = re.compile(
    r'hosts_add\s*=\s*(?:r|R)?(?P<quote>"""|\'\'\')(?P<body>.*?)(?P=quote)',
    re.S,
)

# PyInstaller writes generated specs to BUILD_DIR. The maintained example spec
# under packaging/ is source-controlled and must never be deleted by a build.
SPEC_FILES: tuple[Path, ...] = ()

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
import requests


def require_path(path: Path, description: str) -> None:
    if not path.exists():
        raise FileNotFoundError(f"{description} not found: {path}")


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_app_version() -> str:
    config_path = APP_MODULES_DIR / "app_config.py"
    source_path = config_path if config_path.exists() else SCRIPT_PATH
    text = source_path.read_text(encoding="utf-8")
    match = re.search(r'^APP_VERSION\s*=\s*[\'"]([^\'"]+)[\'"]', text, re.MULTILINE)
    if not match:
        raise RuntimeError(f"APP_VERSION not found in {source_path}")
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


def ai_dns_hosts_looks_useful(text: str) -> bool:
    hay = (text or "").casefold()
    return any(token in hay for token in ("openai", "chatgpt", "claude", "gemini", "anthropic"))


def decode_github_contents_payload(response: requests.Response) -> str:
    payload = response.json()
    if not isinstance(payload, dict):
        raise RuntimeError("unexpected GitHub contents API response")
    content = str(payload.get("content") or "")
    encoding = str(payload.get("encoding") or "").casefold()
    if not content or encoding != "base64":
        raise RuntimeError("GitHub contents API did not return base64 content")
    return base64.b64decode(content.encode("ascii"), validate=False).decode("utf-8", errors="replace")


def fetch_release_text_source(session: requests.Session, source: tuple[str, str, str]) -> str:
    _label, url, kind = source
    response = session.get(url, timeout=(5.0, 30.0), allow_redirects=True)
    response.raise_for_status()
    if kind == "github-api":
        return decode_github_contents_payload(response)
    return (response.content or b"").decode("utf-8", errors="replace")


def fetch_first_release_text(sources: tuple[tuple[str, str, str], ...], required: bool) -> tuple[str, str]:
    errors = []
    session = requests.Session()
    session.headers.update({"User-Agent": "ZapretGUI-ReleaseBuilder"})
    try:
        for source in sources:
            label = source[0]
            try:
                text = fetch_release_text_source(session, source)
                if text.strip():
                    return text, label
                errors.append(f"{label}: empty response")
            except Exception as e:
                msg = str(e).replace("\r", " ").replace("\n", " ").strip()
                errors.append(f"{label}: {msg}")
        if required:
            raise RuntimeError("all Ai DNS seed sources failed:\n- " + "\n- ".join(errors))
        return "", ""
    finally:
        session.close()


def ensure_ai_dns_release_seed() -> None:
    existing = AI_DNS_SEED_PATH.read_text(encoding="utf-8", errors="ignore") if AI_DNS_SEED_PATH.exists() else ""
    try:
        main_hosts, main_source = fetch_first_release_text(AI_DNS_MAIN_SOURCES, required=True)
        main_hosts = main_hosts.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not ai_dns_hosts_looks_useful(main_hosts):
            raise RuntimeError(f"Ai DNS seed from {main_source} does not look useful")

        additional_text, additional_source = fetch_first_release_text(AI_DNS_ADDITIONAL_SOURCES, required=False)
        additional_block = ""
        additional_version = ""
        if additional_text:
            m_ver = AI_DNS_ADDITIONAL_VERSION_RE.search(additional_text)
            m_hosts = AI_DNS_ADDITIONAL_HOSTS_RE.search(additional_text)
            if m_ver:
                additional_version = m_ver.group(1).strip()
            if m_hosts:
                additional_block = (m_hosts.group("body") or "").strip()

        pieces = [
            f"# ZapretGUI bundled Ai DNS hosts seed",
            f"# Source: {main_source}",
            main_hosts,
        ]
        if additional_block:
            header = "# Goida-AI-Unlocker additional hosts"
            if additional_version:
                header += f" ({additional_version})"
            header += f" via {additional_source}"
            pieces.extend((header, additional_block))

        final_text = "\n\n".join(part for part in pieces if part).strip() + "\n"
        if not ai_dns_hosts_looks_useful(final_text):
            raise RuntimeError("Final Ai DNS seed does not look useful")

        AI_DNS_SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
        AI_DNS_SEED_PATH.write_text(final_text, encoding="utf-8", newline="\n")
        print(f"Ai DNS seed ready: {AI_DNS_SEED_PATH} ({main_source})", flush=True)
    except Exception:
        if existing.strip() and ai_dns_hosts_looks_useful(existing):
            print(f"Warning: couldn't refresh Ai DNS seed, keeping existing {AI_DNS_SEED_PATH}", flush=True)
            return
        raise


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


def validate_adaptive_runtime() -> None:
    require_path(ADAPTIVE_RUNTIME_MANIFEST, "adaptive runtime manifest")
    try:
        manifest = json.loads(ADAPTIVE_RUNTIME_MANIFEST.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as e:
        raise RuntimeError(f"Cannot read adaptive runtime manifest: {e}") from e

    if not isinstance(manifest, dict) or manifest.get("schema") != 1:
        raise RuntimeError("Unsupported adaptive runtime manifest schema")
    if not str(manifest.get("version") or "").strip():
        raise RuntimeError("Adaptive runtime manifest version is missing")

    entries = manifest.get("files")
    if not isinstance(entries, list) or not entries:
        raise RuntimeError("Adaptive runtime manifest does not contain files")

    runtime_root = ADAPTIVE_RUNTIME_DIR.resolve()
    seen_paths: set[str] = set()
    errors = []
    for index, entry in enumerate(entries, start=1):
        if not isinstance(entry, dict):
            errors.append(f"entry #{index}: expected an object")
            continue

        relative_text = str(entry.get("path") or "")
        relative_path = PurePosixPath(relative_text)
        path_key = relative_text.casefold()
        if (
            not relative_text
            or "\\" in relative_text
            or relative_path.is_absolute()
            or any(part in {"", ".", ".."} or ":" in part for part in relative_text.split("/"))
        ):
            errors.append(f"entry #{index}: unsafe path {relative_text!r}")
            continue
        if path_key in seen_paths:
            errors.append(f"entry #{index}: duplicate path {relative_text!r}")
            continue
        seen_paths.add(path_key)

        destination_text = entry.get("destination")
        if destination_text is not None:
            destination_text = str(destination_text)
            project_prefix = "project/"
            destination_path = PurePosixPath(destination_text[len(project_prefix):])
            if (
                not destination_text.startswith(project_prefix)
                or "\\" in destination_text
                or destination_path.is_absolute()
                or any(
                    part in {"", ".", ".."} or ":" in part
                    for part in destination_text[len(project_prefix):].split("/")
                )
            ):
                errors.append(f"{relative_text}: unsafe destination {destination_text!r}")
                continue

        expected_size = entry.get("size")
        expected_hash = str(entry.get("sha256") or "").casefold()
        if isinstance(expected_size, bool) or not isinstance(expected_size, int) or expected_size < 0:
            errors.append(f"{relative_text}: invalid size in manifest")
            continue
        if re.fullmatch(r"[0-9a-f]{64}", expected_hash) is None:
            errors.append(f"{relative_text}: invalid SHA256 in manifest")
            continue

        file_path = (runtime_root / Path(*relative_path.parts)).resolve()
        try:
            file_path.relative_to(runtime_root)
        except ValueError:
            errors.append(f"{relative_text}: path escapes adaptive runtime folder")
            continue
        if not file_path.is_file():
            errors.append(f"{relative_text}: file is missing")
            continue
        actual_size = file_path.stat().st_size
        if actual_size != expected_size:
            errors.append(f"{relative_text}: size {actual_size}, expected {expected_size}")
            continue
        actual_hash = file_sha256(file_path)
        if actual_hash != expected_hash:
            errors.append(f"{relative_text}: SHA256 {actual_hash}, expected {expected_hash}")

    if errors:
        raise RuntimeError("Adaptive runtime validation failed:\n- " + "\n- ".join(errors))
    print(f"Adaptive runtime OK: {len(entries)} files verified locally", flush=True)


def validate_resources() -> None:
    required_paths = [
        (SCRIPT_PATH, "main application module"),
        (TELEGRAM_PROXY_PATH, "Telegram proxy module"),
        (BYPASS_SERVICE_PATH, "bypass service client"),
        (SERVICE_DIR / "ZapretGUI.Service.exe", "background service binary"),
        (SERVICE_SOURCE_DIR / "build.py", "background service build script"),
        (SERVICE_SOURCE_DIR / "Service.cs", "background service source"),
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
        (ADAPTIVE_STRATEGY_DIR, "adaptive strategy package"),
        (ADAPTIVE_STRATEGY_DIR / "__init__.py", "adaptive strategy package init"),
        (APP_MODULES_DIR, "application source modules"),
        (APP_MODULES_DIR / "__init__.py", "application source modules init"),
        *[(APP_MODULES_DIR / name, f"application source module: {name}") for name in APP_MODULE_FILES],
        (ADAPTIVE_STRATEGY_DIR / "catalog.py", "adaptive strategy catalog"),
        (ADAPTIVE_STRATEGY_DIR / "engine.py", "adaptive strategy engine"),
        (ADAPTIVE_STRATEGY_DIR / "generator.py", "adaptive strategy generator"),
        (ADAPTIVE_STRATEGY_DIR / "hostlist.py", "adaptive strategy host list"),
        (ADAPTIVE_STRATEGY_DIR / "models.py", "adaptive strategy models"),
        (ADAPTIVE_STRATEGY_DIR / "probe.py", "adaptive strategy probes"),
        (ADAPTIVE_STRATEGY_DIR / "resources.py", "adaptive strategy resources"),
        (ADAPTIVE_STRATEGY_DIR / "runtime.py", "adaptive strategy runtime"),
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
        (CORE_DIR / "bin" / "cygwin1.dll", "winws Cygwin compatibility DLL"),
        (CORE_DIR / "bin" / "tls_clienthello_www_google_com.bin", "Google TLS payload"),
        (CORE_DIR / "bin" / "tls_clienthello_max_ru.bin", "MAX TLS payload"),
        (CORE_DIR / "bin" / "tls_clienthello_4pda_to.bin", "4PDA TLS payload"),
        (CORE_DIR / "bin" / "tls_clienthello_sochi_park.bin", "ALT13 TLS payload"),
        (CORE_DIR / "bin" / "stun.bin", "STUN payload"),
        (CORE_DIR / "bin" / "stun2.bin", "ALT11 STUN2 payload"),
        (CORE_DIR / "bin" / "quic_initial_www_google_com.bin", "Google QUIC payload"),
        (CORE_DIR / "bin" / "ACTIVE_DISCORD_UDP.bin", "Discord UDP payload"),
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

    try:
        importlib.import_module("adaptive_strategy")
    except Exception as e:
        raise RuntimeError(f"Adaptive strategy package cannot be imported: {e}") from e

    validate_adaptive_runtime()

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


def build_background_service() -> None:
    """Compile the trusted helper before validating/package it."""
    subprocess.run(
        [sys.executable, str(SERVICE_SOURCE_DIR / "build.py")],
        check=True,
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
    )


def run_preflight() -> None:
    validate_resources()
    validate_versions()
    print(f"Preflight OK: {BASE_NAME} {read_app_version()}", flush=True)


build_background_service()
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
    f"--specpath={BUILD_DIR}",
    f"--paths={SRC_DIR}",
    add_data(FLAGS_DIR, "flags"),
    add_data(CORE_DIR, "core"),
    add_data(ADAPTIVE_RUNTIME_DIR, "adaptive-runtime"),
    add_data(APP_MODULES_DIR, "app_modules"),
    add_data(SERVICE_DIR / "ZapretGUI.Service.exe", "background_service"),
    "--version-file", str(VERSION_FILE),
    "--collect-data=certifi",
    "--collect-submodules=tg_ws_proxy_vendor",
    "--collect-submodules=adaptive_strategy",
    "--hidden-import=PyQt6.sip",
    "--hidden-import=psutil",
    "--hidden-import=requests",
    "--hidden-import=cryptography",
    "--hidden-import=zapret_gui.telegram_proxy",
    "--hidden-import=bypass_service",
    "--hidden-import=adaptive_strategy",
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
