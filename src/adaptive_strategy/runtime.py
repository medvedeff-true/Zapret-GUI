from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)
_EXTERNAL_PROCESS_LOCK = threading.Lock()
WINWS_STARTUP_DELAY = 0.45
WINWS_RESTART_COOLDOWN = 0.75


def is_frozen() -> bool:
    return bool(getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"))


def system_executable(filename: str) -> str:
    """Return a trusted absolute path for a Windows system executable."""
    if not filename or filename in {".", ".."} or Path(filename).name != filename:
        raise ValueError(f"Expected a system executable filename, got {filename!r}")
    if os.name != "nt":
        return filename

    buffer = ctypes.create_unicode_buffer(32768)
    function = ctypes.windll.kernel32.GetSystemDirectoryW
    function.argtypes = (ctypes.c_wchar_p, ctypes.c_uint)
    function.restype = ctypes.c_uint
    length = function(buffer, len(buffer))
    if not length or length >= len(buffer):
        raise ctypes.WinError(ctypes.windll.kernel32.GetLastError())
    return str(Path(buffer.value) / filename)


def _set_dll_directory(path: str | None) -> None:
    function = ctypes.windll.kernel32.SetDllDirectoryW
    function.argtypes = (ctypes.c_wchar_p,)
    function.restype = ctypes.c_int
    if not function(path):
        raise ctypes.WinError(ctypes.get_last_error())


def _sanitized_external_environment(
    environment: os._Environ[str] | dict[str, str] | None,
) -> dict[str, str]:
    """Remove PyInstaller-owned search paths inherited by external tools."""
    sanitized = dict(os.environ if environment is None else environment)
    bundle_root = Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
    for key in tuple(sanitized):
        if key.upper() != "PATH":
            continue
        entries: list[str] = []
        for entry in sanitized[key].split(os.pathsep):
            try:
                anchored_in_bundle = Path(entry.strip('"')).resolve().is_relative_to(bundle_root)
            except (OSError, ValueError):
                anchored_in_bundle = False
            if not anchored_in_bundle:
                entries.append(entry)
        sanitized[key] = os.pathsep.join(entries)
    return sanitized


def popen_external(
    command: Sequence[str] | str,
    **kwargs: object,
) -> subprocess.Popen:
    """Start an external executable without PyInstaller's DLL search override.

    SetDllDirectoryW is process-wide, so the small create-process window is
    serialized. The child keeps the clean setting it inherited while this
    process immediately restores its own bundled DLL directory.
    """
    if os.name != "nt" or not is_frozen():
        return subprocess.Popen(command, **kwargs)

    options = dict(kwargs)
    options["env"] = _sanitized_external_environment(options.get("env"))  # type: ignore[arg-type]
    bundle_root = str(Path(sys._MEIPASS).resolve())  # type: ignore[attr-defined]
    with _EXTERNAL_PROCESS_LOCK:
        _set_dll_directory(None)
        try:
            return subprocess.Popen(command, **options)
        finally:
            _set_dll_directory(bundle_root)


def run_external(
    command: Sequence[str] | str,
    *,
    input: bytes | str | None = None,
    capture_output: bool = False,
    timeout: float | None = None,
    check: bool = False,
    **kwargs: object,
) -> subprocess.CompletedProcess:
    """A subprocess.run-compatible wrapper that sanitizes only process creation."""
    if input is not None:
        if kwargs.get("stdin") is not None:
            raise ValueError("stdin and input arguments may not both be used")
        kwargs["stdin"] = subprocess.PIPE
    if capture_output:
        if kwargs.get("stdout") is not None or kwargs.get("stderr") is not None:
            raise ValueError("stdout and stderr arguments may not be used with capture_output")
        kwargs["stdout"] = subprocess.PIPE
        kwargs["stderr"] = subprocess.PIPE

    with popen_external(command, **kwargs) as process:
        try:
            stdout, stderr = process.communicate(input, timeout=timeout)
        except subprocess.TimeoutExpired as exc:
            process.kill()
            exc.stdout, exc.stderr = process.communicate()
            raise
        except BaseException:
            process.kill()
            raise
        returncode = process.poll()
    if check and returncode:
        raise subprocess.CalledProcessError(returncode, command, output=stdout, stderr=stderr)
    return subprocess.CompletedProcess(command, returncode, stdout, stderr)


@dataclass(frozen=True)
class RuntimePaths:
    project_root: Path
    bundle_root: Path
    winws_dir: Path
    winws: Path
    fake_tls: Path
    fake_tls_max: Path
    fake_tls_4pda: Path
    fake_quic: Path
    fake_udp_dbank: Path
    fake_discord: Path
    fake_stun: Path
    cygwin_bash: Path
    cygwin_curl: Path
    cygwin_curl_kyber: Path
    browser: Path | None

    @classmethod
    def for_zapret_gui(
        cls,
        app_dir: Path | str,
        runtime_root: Path | str | None = None,
    ) -> "RuntimePaths":
        """Build paths for Zapret GUI's shared, persistent runtime.

        The generated profiles reuse ``core/bin``.  Only the Cygwin curl
        validators live in ``user/adaptive-runtime`` so Flowseal core updates
        cannot remove them and every generated strategy shares one copy.
        """
        root = Path(app_dir).resolve()
        core_bin = root / "core" / "bin"
        validators = Path(runtime_root or (root / "user" / "adaptive-runtime")).resolve()
        cygwin = validators / "cygwin"
        local_app_data = Path(os.environ.get("LOCALAPPDATA", "C:/__missing_local_app_data__"))
        browser_candidates = (
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            local_app_data / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
            local_app_data / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        )
        browser = next((path for path in browser_candidates if path.is_file()), None)
        return cls(
            project_root=root,
            bundle_root=validators,
            winws_dir=core_bin,
            winws=core_bin / "winws.exe",
            fake_tls=core_bin / "tls_clienthello_www_google_com.bin",
            fake_tls_max=core_bin / "tls_clienthello_max_ru.bin",
            fake_tls_4pda=core_bin / "tls_clienthello_4pda_to.bin",
            fake_quic=core_bin / "quic_initial_www_google_com.bin",
            fake_udp_dbank=core_bin / "quic_initial_dbankcloud_ru.bin",
            # Kept for compatibility with the standalone generator.  The GUI
            # search and one-BAT generator do not consume this field.
            fake_discord=core_bin / "quic_initial_dbankcloud_ru.bin",
            fake_stun=core_bin / "stun.bin",
            cygwin_bash=cygwin / "bin" / "bash.exe",
            cygwin_curl=cygwin / "usr" / "local" / "bin" / "curl.exe",
            cygwin_curl_kyber=cygwin / "usr" / "local" / "bin" / "curl-kyber.exe",
            browser=browser,
        )

    @classmethod
    def discover(cls, project_root: Path | None = None) -> "RuntimePaths":
        if project_root is not None:
            root = project_root.resolve()
            resource_root = root
        elif is_frozen():
            root = Path(sys.executable).resolve().parent
            resource_root = Path(sys._MEIPASS).resolve()  # type: ignore[attr-defined]
        else:
            source_root = Path(__file__).resolve().parents[2]
            root = source_root
            resource_root = source_root / "resources"
        if (root / "core" / "bin" / "winws.exe").is_file():
            return cls.for_zapret_gui(root)
        if (resource_root / "core" / "bin" / "winws.exe").is_file():
            return cls.for_zapret_gui(resource_root)

        bundle = resource_root / "vendor" / "zapret-win-bundle-master"
        flowseal_patterns = resource_root / "vendor" / "flowseal-patterns"
        winws_dir = bundle / "zapret-winws"
        local_app_data = Path(os.environ.get("LOCALAPPDATA", "C:/__missing_local_app_data__"))
        browser_candidates = (
            Path("C:/Program Files/Google/Chrome/Application/chrome.exe"),
            Path("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
            local_app_data / "Google" / "Chrome" / "Application" / "chrome.exe",
            Path("C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe"),
            Path("C:/Program Files/Microsoft/Edge/Application/msedge.exe"),
            local_app_data / "Microsoft" / "Edge" / "Application" / "msedge.exe",
        )
        browser = next((path for path in browser_candidates if path.is_file()), None)
        return cls(
            project_root=root,
            bundle_root=bundle,
            winws_dir=winws_dir,
            winws=winws_dir / "winws.exe",
            fake_tls=bundle / "blockcheck" / "zapret" / "files" / "fake" / "tls_clienthello_www_google_com.bin",
            fake_tls_max=flowseal_patterns / "tls_clienthello_max_ru.bin",
            fake_tls_4pda=flowseal_patterns / "tls_clienthello_4pda_to.bin",
            fake_quic=winws_dir / "files" / "quic_initial_www_google_com.bin",
            fake_udp_dbank=flowseal_patterns / "quic_initial_dbankcloud_ru.bin",
            fake_discord=bundle / "blockcheck" / "zapret" / "files" / "fake" / "discord-ip-discovery-without-port.bin",
            fake_stun=bundle / "blockcheck" / "zapret" / "files" / "fake" / "stun.bin",
            cygwin_bash=bundle / "cygwin" / "bin" / "bash.exe",
            cygwin_curl=bundle / "cygwin" / "usr" / "local" / "bin" / "curl.exe",
            cygwin_curl_kyber=bundle / "cygwin" / "usr" / "local" / "bin" / "curl-kyber.exe",
            browser=browser,
        )

    def missing(self) -> list[Path]:
        """Return components required by the search engine.

        Generator-only assets from the old standalone bundle are deliberately
        excluded; Zapret GUI produces a single BAT which reuses ``core/bin``.
        """
        required = (
            self.winws,
            self.winws_dir / "WinDivert.dll",
            self.winws_dir / "WinDivert64.sys",
            self.winws_dir / "cygwin1.dll",
            self.fake_tls,
            self.fake_tls_max,
            self.fake_tls_4pda,
            self.fake_quic,
            self.fake_udp_dbank,
            self.fake_stun,
            self.winws_dir / "stun2.bin",
            self.winws_dir / "tls_clienthello_sochi_park.bin",
            self.winws_dir / "ACTIVE_DISCORD_UDP.bin",
            self.cygwin_bash,
            self.cygwin_curl,
            self.cygwin_curl_kyber,
        )
        return [path for path in required if not path.is_file()]


def is_admin() -> bool:
    if os.name != "nt":
        return os.geteuid() == 0
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except (AttributeError, OSError):
        return False


def relaunch_as_admin() -> bool:
    if os.name != "nt" or is_admin():
        return False
    executable, args, working_directory = _elevation_command()
    result = ctypes.windll.shell32.ShellExecuteW(
        None, "runas", executable, args, working_directory, 1
    )
    return result > 32


def _elevation_command() -> tuple[str, str, str]:
    """Return a UAC command without passing a frozen EXE to itself as a script."""
    executable = str(Path(sys.executable).resolve())
    parameters = list(sys.argv[1:])
    if not is_frozen():
        parameters.insert(0, str(Path(sys.argv[0]).resolve()))
    args = subprocess.list2cmdline(parameters)
    working_directory = str(Path(executable).parent)
    return executable, args, working_directory


def conflicting_processes() -> list[str]:
    if os.name != "nt":
        return []
    found: list[str] = []
    tasklist = system_executable("tasklist.exe")
    for image in ("winws.exe", "winws2.exe", "goodbyedpi.exe", "nfqws.exe"):
        completed = run_external(
            [tasklist, "/FI", f"IMAGENAME eq {image}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=CREATE_NO_WINDOW,
            check=False,
        )
        if image.lower() in completed.stdout.lower():
            found.append(image)
    return found


class WinwsProcess:
    _lifecycle_lock = threading.Lock()
    _last_stop_at = 0.0

    def __init__(self, paths: RuntimePaths, arguments: Sequence[str]) -> None:
        self.paths = paths
        self.arguments = list(arguments)
        self.process: subprocess.Popen[bytes] | None = None

    def __enter__(self) -> "WinwsProcess":
        with self._lifecycle_lock:
            elapsed = time.monotonic() - type(self)._last_stop_at
            if type(self)._last_stop_at and elapsed < WINWS_RESTART_COOLDOWN:
                time.sleep(WINWS_RESTART_COOLDOWN - elapsed)
            command = [str(self.paths.winws), *self.arguments]
            self.process = popen_external(
                command,
                cwd=self.paths.winws_dir,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=CREATE_NO_WINDOW,
            )
        # Loading WinDivert is asynchronous. The previous 350 ms pause was
        # shorter than the unload/reload cycle on some systems.
        time.sleep(WINWS_STARTUP_DELAY)
        if self.process.poll() is not None:
            with self._lifecycle_lock:
                type(self)._last_stop_at = time.monotonic()
            raise RuntimeError(f"winws завершился с кодом {self.process.returncode}")
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.stop()

    def stop(self) -> None:
        process = self.process
        if process is None:
            return
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
        finally:
            with self._lifecycle_lock:
                type(self)._last_stop_at = time.monotonic()


def runtime_helper_errors(paths: RuntimePaths) -> list[str]:
    """Verify that bundled native/Cygwin helpers can really execute."""
    if paths.missing():
        return []
    checks: tuple[tuple[str, list[str], Path], ...] = (
        (
            "Cygwin curl",
            [
                str(paths.cygwin_bash),
                "--noprofile",
                "--norc",
                "-lc",
                "export PATH=/usr/local/bin:/usr/bin:$PATH; exec /usr/local/bin/curl --version",
            ],
            paths.bundle_root / "cygwin",
        ),
        (
            "Cygwin curl-kyber",
            [
                str(paths.cygwin_bash),
                "--noprofile",
                "--norc",
                "-lc",
                "export PATH=/usr/local/bin:/usr/bin:$PATH; exec /usr/local/bin/curl-kyber --version",
            ],
            paths.bundle_root / "cygwin",
        ),
        (
            "winws",
            [
                str(paths.winws),
                "--dry-run",
                "--wf-tcp=443",
                "--filter-tcp=443",
                "--dpi-desync=multisplit",
                "--dpi-desync-split-pos=1,midsld",
            ],
            paths.winws_dir,
        ),
    )
    errors: list[str] = []
    for label, command, cwd in checks:
        try:
            completed = run_external(
                command,
                cwd=cwd,
                capture_output=True,
                timeout=10,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            errors.append(f"{label}: {exc}")
            continue
        if completed.returncode == 0:
            continue
        raw_error = completed.stderr or completed.stdout or b""
        if isinstance(raw_error, bytes):
            detail = raw_error.decode("utf-8", errors="replace").strip()
        else:
            detail = raw_error.strip()
        suffix = f": {detail[-300:]}" if detail else ""
        errors.append(f"{label}: код {completed.returncode}{suffix}")
    return errors


def winws_arguments(protocol: str, rendered_options: Sequence[str], hostlist: Path | None = None) -> list[str]:
    if protocol == "quic":
        args = ["--wf-udp=443", "--filter-udp=443", "--filter-l7=quic"]
    else:
        args = ["--wf-tcp=80,443", "--filter-tcp=443"]
    if hostlist:
        args.append(f"--hostlist={hostlist}")
    args.extend(rendered_options)
    return args
