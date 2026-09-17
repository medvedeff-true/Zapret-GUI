from __future__ import annotations

import re
import shlex
import socket
import ssl
import subprocess
import tempfile
import threading
import time
import base64
import hashlib
import json
import os
from ipaddress import ip_address
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

from .hostlist import TELEGRAM_WEB_IP, service_for_host
from .models import ProbeResult, Protocol, Target
from .runtime import (
    CREATE_NO_WINDOW,
    RuntimePaths,
    popen_external,
    run_external,
    system_executable,
)


RESULT_MARKER = "__DPIWIZARD__"
WEBSOCKET_TIMEOUT_FLOOR = 8.0
KNOWN_HTTP3_SUFFIXES = (
    "google.com",
    "googlevideo.com",
    "youtube.com",
    "youtu.be",
    "cloudflare.com",
    "facebook.com",
)
PROFILE_BUILDER_SERVICES = frozenset({"youtube", "discord"})


def parse_targets(text: str, include_quic: bool = False) -> list[Target]:
    targets: list[Target] = []
    seen: set[str] = set()
    raw_items = re.split(r"[\s,;]+", text.strip())
    for raw in raw_items:
        if not raw:
            continue
        value = raw if "://" in raw else f"https://{raw}"
        parsed = urlparse(value)
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError(f"Некорректная цель: {raw}")
        if parsed.username or parsed.password:
            raise ValueError("URL с логином или паролем не поддерживается")
        try:
            port = parsed.port
        except ValueError as exc:
            raise ValueError(f"Некорректный порт в цели: {raw}") from exc
        if port not in (None, 80, 443):
            raise ValueError("Для поиска поддерживаются только порты 80 и 443")
        hostname = parsed.hostname.encode("idna").decode("ascii").lower().rstrip(".")
        try:
            ip_address(hostname)
        except ValueError:
            pass
        else:
            raise ValueError("Укажите доменное имя: zapret не обходит блокировки по IP")
        normalized = parsed._replace(netloc=hostname + (f":{port}" if port else ""), fragment="").geturl()
        if normalized in seen:
            continue
        seen.add(normalized)
        service = service_for_host(hostname)
        protocols = [Protocol.HTTPS]
        supports_http3 = any(
            hostname == suffix or hostname.endswith("." + suffix)
            for suffix in KNOWN_HTTP3_SUFFIXES
        )
        if include_quic and supports_http3:
            protocols.append(Protocol.QUIC)
        resolve_ip = TELEGRAM_WEB_IP if service == "telegram" else ""
        profile = "discord_app" if service == "discord" else service
        targets.append(
            Target(
                normalized,
                hostname,
                tuple(protocols),
                service=service,
                profile=profile,
                resolve_ip=resolve_ip,
            )
        )
    if not targets:
        raise ValueError("Укажите хотя бы один домен или URL")
    if len(targets) > 12:
        raise ValueError("За один поиск можно проверить не более 12 целей")
    return _expand_service_targets(targets)


def select_profile_builder_targets(
    targets: Iterable[Target],
) -> tuple[list[Target], list[Target]]:
    """Keep only services covered by the automatic profile certification matrix.

    Generic sites can be unstable, provider-specific, or temporarily offline.
    They still remain supported by the lower-level search engine, but the GUI's
    standard YouTube/Discord profile must not fail because one unrelated site
    was accidentally added to its configured target list.
    """
    selected: list[Target] = []
    ignored: list[Target] = []
    for target in targets:
        destination = selected if target.service in PROFILE_BUILDER_SERVICES else ignored
        destination.append(target)
    return selected, ignored


def _expand_service_targets(targets: list[Target]) -> list[Target]:
    services = {target.service for target in targets}
    # A Discord URL entered by the user is a service selector. Do not make the
    # browser page a required target: the desktop application's API/CDN/Gateway
    # traffic is the primary success criterion.
    discord_targets = (
                Target(
                    "https://discord.com/api/v10/gateway", "discord.com",
                    service="discord", profile="discord_app",
                ),
                Target(
                    "wss://gateway.discord.gg/?v=10&encoding=json",
                    "gateway.discord.gg",
                    service="discord",
                    profile="discord_app",
                    validator="websocket",
                ),
                Target(
                    "https://cdn.discordapp.com/embed/avatars/0.png",
                    "cdn.discordapp.com",
                    service="discord",
                    profile="discord_app",
                ),
                # The specialised validator checks both the update manifest
                # and the referenced package.  A second generic curl probe of
                # the same manifest only gates that validator and can turn a
                # transient helper timeout into a false "no strategy" result.
                Target(
                    "https://updates.discord.com/distributions/app/manifests/latest?channel=stable&platform=win&arch=x64",
                    "updates.discord.com",
                    service="discord",
                    profile="discord_update",
                    validator="discord_update",
                ),
    )
    expanded: list[Target] = []
    discord_added = False
    for target in targets:
        if target.service != "discord":
            expanded.append(target)
        elif not discord_added:
            expanded.extend(discord_targets)
            discord_added = True
    if "telegram" in services:
        expanded.extend(
            (
                Target(
                    "https://web.telegram.org/k/",
                    "web.telegram.org",
                    service="telegram",
                    profile="telegram",
                    resolve_ip=TELEGRAM_WEB_IP,
                ),
                Target(
                    "wss://kws2.web.telegram.org/apiws",
                    "kws2.web.telegram.org",
                    service="telegram",
                    profile="telegram",
                    validator="websocket",
                    resolve_ip=TELEGRAM_WEB_IP,
                    alternative_group="telegram-websocket",
                ),
                Target(
                    "wss://kws4.web.telegram.org/apiws",
                    "kws4.web.telegram.org",
                    service="telegram",
                    profile="telegram",
                    validator="websocket",
                    resolve_ip=TELEGRAM_WEB_IP,
                    alternative_group="telegram-websocket",
                ),
            )
        )
    unique: list[Target] = []
    seen: set[tuple[str, str]] = set()
    for target in expanded:
        key = (target.url, target.validator)
        if key not in seen:
            seen.add(key)
            unique.append(target)
    return unique


def dns_addresses(target: Target) -> list[str]:
    if target.resolve_ip:
        return [target.resolve_ip]
    try:
        records = socket.getaddrinfo(target.hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        return []
    return sorted({record[4][0] for record in records})


def dns_addresses_with_deadline(
    targets: Iterable[Target],
    *,
    timeout: float = 3.0,
    cancel_event: threading.Event | None = None,
) -> dict[Target, list[str]]:
    """Resolve targets without letting a stalled system DNS call block a run.

    Windows can leave ``getaddrinfo`` waiting while a VPN adapter is connecting
    or has installed an unusable DNS route.  ``getaddrinfo`` itself has no
    portable timeout, so each lookup runs in a daemon worker and the caller
    receives the results collected before one shared deadline.  Late workers
    cannot keep the application alive during shutdown.
    """
    unique_targets = list(dict.fromkeys(targets))
    results: dict[Target, list[str]] = {
        target: [target.resolve_ip] if target.resolve_ip else []
        for target in unique_targets
    }
    pending = [target for target in unique_targets if not target.resolve_ip]
    if not pending:
        return results

    completed = threading.Event()
    remaining = len(pending)
    remaining_lock = threading.Lock()

    def resolve(target: Target) -> None:
        nonlocal remaining
        try:
            addresses = dns_addresses(target)
        except Exception:
            addresses = []
        with remaining_lock:
            results[target] = addresses
            remaining -= 1
            if remaining == 0:
                completed.set()

    for target in pending:
        threading.Thread(target=resolve, args=(target,), daemon=True).start()

    deadline = time.monotonic() + max(0.1, float(timeout))
    while not completed.is_set():
        if cancel_event is not None and cancel_event.is_set():
            break
        remaining_time = deadline - time.monotonic()
        if remaining_time <= 0:
            break
        completed.wait(min(0.05, remaining_time))
    return results


class ProbeRunner:
    def __init__(self, paths: RuntimePaths, timeout: float = 5.0) -> None:
        self.paths = paths
        self.timeout = max(2.0, timeout)

    def probe(self, target: Target, protocol: Protocol, validator: str | None = None) -> ProbeResult:
        selected = validator or ("http3" if protocol is Protocol.QUIC else "native")
        if selected == "websocket":
            return self._websocket(target)
        if selected == "discord_browser":
            return self._discord_browser(target)
        if selected == "discord_update":
            return self._discord_update(target)
        if selected == "native":
            return self._native_curl(target)
        if selected in {"cygwin", "kyber", "http3"}:
            return self._cygwin_curl(target, selected)
        raise ValueError(f"Неизвестный валидатор: {selected}")

    def probe_many(
        self,
        items: Iterable[tuple[Target, Protocol, str]],
        workers: int = 8,
    ) -> list[ProbeResult]:
        requests = list(items)
        if not requests:
            return []
        results: list[ProbeResult] = []
        with ThreadPoolExecutor(max_workers=min(workers, len(requests))) as pool:
            futures = {
                pool.submit(self.probe, target, protocol, validator): (target, protocol, validator)
                for target, protocol, validator in requests
            }
            for future in as_completed(futures):
                target, _protocol, validator = futures[future]
                try:
                    results.append(future.result())
                except Exception as exc:  # a failed probe must not abort the tournament
                    results.append(ProbeResult(target, validator, False, None, 0.0, error=str(exc)))
        return results

    def _native_curl(self, target: Target) -> ProbeResult:
        write_out = f"{RESULT_MARKER}%{{http_code}}|%{{remote_ip}}|%{{time_total}}|%{{size_download}}"
        command = [
            system_executable("curl.exe"),
            "--silent",
            "--show-error",
            "--location",
            "--max-redirs", "3",
            # Do not silently cap the connection phase at three seconds.  The
            # adaptive UI intentionally gives each probe five seconds by
            # default; using only three here caused an otherwise working
            # strategy to fail final validation on slower routes/devices.
            "--connect-timeout", str(self.timeout),
            "--max-time", str(self.timeout),
            "--http1.1",
            "--ssl-no-revoke",
            "--noproxy", "*",
            "--range", "0-2047",
            "--output", "NUL",
            "--write-out", write_out,
        ]
        if target.resolve_ip:
            command.extend(("--resolve", f"{target.hostname}:443:{target.resolve_ip}"))
        command.append(target.url)
        return self._run(command, target, "native", cwd=self.paths.project_root)

    def _cygwin_curl(self, target: Target, validator: str) -> ProbeResult:
        binary = "/usr/local/bin/curl-kyber" if validator == "kyber" else "/usr/local/bin/curl"
        protocol_args = "--http3-only" if validator == "http3" else "--http2"
        write_out = f"{RESULT_MARKER}%{{http_code}}|%{{remote_ip}}|%{{time_total}}|%{{size_download}}"
        resolve_arg = (
            f"--resolve {shlex.quote(f'{target.hostname}:443:{target.resolve_ip}')}"
            if target.resolve_ip else ""
        )
        curl_command = " ".join(
            (
                "exec",
                binary,
                "--silent --show-error --location --max-redirs 3",
                f"--connect-timeout {self.timeout} --max-time {self.timeout}",
                protocol_args,
                "--noproxy '*' --range 0-2047 --output /dev/null",
                resolve_arg,
                "--write-out", shlex.quote(write_out),
                shlex.quote(target.url),
            )
        )
        shell_command = f"export PATH=/usr/local/bin:/usr/bin:$PATH; {curl_command}"
        command = [str(self.paths.cygwin_bash), "--noprofile", "--norc", "-lc", shell_command]
        return self._run(command, target, validator, cwd=self.paths.bundle_root / "cygwin")

    def _websocket(self, target: Target) -> ProbeResult:
        started = time.monotonic()
        # Telegram WebSocket nodes can need longer than an ordinary HTTPS
        # handshake, especially when hosts-file routing is being picked up by
        # Windows after winws starts.  Keep the normal probe budget for other
        # services, but do not reject a valid Telegram route just because the
        # default five-second budget is too short for the first handshake.
        socket_timeout = max(self.timeout, WEBSOCKET_TIMEOUT_FLOOR) if target.service == "telegram" else self.timeout
        parsed = urlparse(target.url)
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query
        key = base64.b64encode(os.urandom(16)).decode("ascii")
        expected_accept = base64.b64encode(
            hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode("ascii")).digest()
        ).decode("ascii")
        address = target.resolve_ip or target.hostname
        try:
            with socket.create_connection((address, 443), timeout=socket_timeout) as raw:
                context = ssl.create_default_context()
                with context.wrap_socket(raw, server_hostname=target.hostname) as tls:
                    tls.settimeout(socket_timeout)
                    telegram_protocol = (
                        "Sec-WebSocket-Protocol: binary\r\n" if target.service == "telegram" else ""
                    )
                    request = (
                        f"GET {path} HTTP/1.1\r\n"
                        f"Host: {target.hostname}\r\n"
                        "Connection: Upgrade\r\n"
                        "Upgrade: websocket\r\n"
                        f"Sec-WebSocket-Key: {key}\r\n"
                        "Sec-WebSocket-Version: 13\r\n"
                        f"{telegram_protocol}"
                        f"Origin: https://{'web.telegram.org' if target.service == 'telegram' else 'discord.com'}\r\n"
                        "User-Agent: Mozilla/5.0\r\n\r\n"
                    )
                    tls.sendall(request.encode("ascii"))
                    response = bytearray()
                    while b"\r\n\r\n" not in response and len(response) < 16384:
                        chunk = tls.recv(4096)
                        if not chunk:
                            break
                        response.extend(chunk)
                    header = response.decode("iso-8859-1", errors="replace")
                    lines = header.split("\r\n")
                    status_ok = bool(lines and " 101 " in lines[0])
                    headers = {
                        name.strip().lower(): value.strip()
                        for line in lines[1:]
                        if ":" in line
                        for name, value in (line.split(":", 1),)
                    }
                    accept_ok = headers.get("sec-websocket-accept", "") == expected_accept
                    protocol_ok = (
                        target.service != "telegram"
                        or headers.get("sec-websocket-protocol", "").lower() == "binary"
                    )
                    success = status_ok and accept_ok and protocol_ok
                    peer = tls.getpeername()[0]
                    if success:
                        error = ""
                    elif not status_ok:
                        error = lines[0] if lines else "no websocket response"
                    elif not accept_ok:
                        error = "invalid Sec-WebSocket-Accept"
                    else:
                        error = "Telegram WebSocket did not negotiate binary subprotocol"
                    return ProbeResult(
                        target,
                        "websocket",
                        success,
                        101 if status_ok else None,
                        time.monotonic() - started,
                        remote_ip=peer,
                        error=error,
                    )
        except (OSError, ssl.SSLError) as exc:
            return ProbeResult(
                target,
                "websocket",
                False,
                None,
                time.monotonic() - started,
                error=str(exc)[-500:],
            )

    def _discord_browser(self, target: Target) -> ProbeResult:
        started = time.monotonic()
        browser = self.paths.browser
        if browser is None:
            return ProbeResult(
                target, "discord_browser", False, None, 0.0,
                error="Microsoft Edge или Google Chrome не найден: невозможно проверить отрисовку Discord",
            )
        virtual_time = max(8000, int(self.timeout * 1600))
        last_error = ""
        # Chromium can occasionally finish --dump-dom before Discord's async
        # application bundle mounts. Retry only a clean, empty DOM with a fresh
        # profile; a rendered DOM remains strict proof of success.
        for attempt in range(2):
            try:
                completed = self._discord_browser_dump(browser, target, virtual_time)
            except (OSError, subprocess.TimeoutExpired) as exc:
                return ProbeResult(
                    target, "discord_browser", False, None,
                    time.monotonic() - started, error=str(exc)[-500:],
                )
            except TimeoutError as exc:
                return ProbeResult(
                    target, "discord_browser", False, None,
                    time.monotonic() - started, error=str(exc),
                )

            dom = completed.stdout.decode("utf-8", errors="replace")
            rendered = self._discord_dom_rendered(dom)
            success = completed.returncode == 0 and rendered and len(dom) >= 20_000
            if success:
                return ProbeResult(
                    target,
                    "discord_browser",
                    True,
                    200,
                    time.monotonic() - started,
                )

            stderr = completed.stderr.decode("utf-8", errors="replace").strip()[-300:]
            last_error = (
                f"Discord остался на пустом app-mount "
                f"(DOM={len(dom)}, exit={completed.returncode}, попытка={attempt + 1}/2)"
                + (f": {stderr}" if stderr else "")
            )
            if completed.returncode != 0:
                break
            time.sleep(0.25)

        return ProbeResult(
            target,
            "discord_browser",
            False,
            None,
            time.monotonic() - started,
            error=last_error,
        )

    def _discord_browser_dump(
        self,
        browser: Path,
        target: Target,
        virtual_time: int,
    ) -> subprocess.CompletedProcess:
        with tempfile.TemporaryDirectory(prefix="dpiwizard-browser-", ignore_cleanup_errors=True) as profile:
            command = [
                str(browser),
                "--headless=new",
                "--disable-gpu",
                "--disable-gpu-compositing",
                "--disable-gpu-sandbox",
                "--in-process-gpu",
                "--disable-quic",
                "--disable-extensions",
                "--no-first-run",
                "--no-default-browser-check",
                f"--user-data-dir={profile}",
                f"--virtual-time-budget={virtual_time}",
                "--dump-dom",
                target.url,
            ]
            stdout_path = Path(profile) / "dom.html"
            stderr_path = Path(profile) / "browser.log"
            with stdout_path.open("wb") as stdout_file, stderr_path.open("wb") as stderr_file:
                process = popen_external(
                    command,
                    cwd=self.paths.project_root,
                    stdout=stdout_file,
                    stderr=stderr_file,
                    creationflags=CREATE_NO_WINDOW,
                )
                try:
                    returncode = process.wait(timeout=self.timeout + 10)
                except subprocess.TimeoutExpired:
                    run_external(
                        [system_executable("taskkill.exe"), "/PID", str(process.pid), "/T", "/F"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                        creationflags=CREATE_NO_WINDOW,
                        check=False,
                    )
                    try:
                        process.wait(timeout=2)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=2)
                    raise TimeoutError(
                        f"Chromium не завершил проверку Discord за {self.timeout + 10:.0f} сек"
                    )
            return subprocess.CompletedProcess(
                command,
                returncode,
                stdout_path.read_bytes(),
                stderr_path.read_bytes(),
            )

    @staticmethod
    def _discord_dom_rendered(dom: str) -> bool:
        mount = re.search(
            r"id=[\"']app-mount[\"'][^>]*>(?P<body>.*?)</div>",
            dom,
            flags=re.IGNORECASE | re.DOTALL,
        )
        return bool(
            mount
            and re.search(
                r"<(?:div|main|form|section|input|button)\b",
                mount.group("body"),
                flags=re.IGNORECASE,
            )
        )

    def _discord_update(self, target: Target) -> ProbeResult:
        started = time.monotonic()
        manifest, body = self._cygwin_body(target)
        if not manifest.success:
            return ProbeResult(
                target, "discord_update", False, manifest.http_code,
                time.monotonic() - started,
                remote_ip=manifest.remote_ip,
                error="manifest: " + manifest.error,
            )
        try:
            payload = json.loads(body.decode("utf-8"))
            package_url = str(payload["full"]["url"])
            parsed = urlparse(package_url)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("invalid package URL")
        except (KeyError, TypeError, ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            return ProbeResult(
                target, "discord_update", False, manifest.http_code,
                time.monotonic() - started,
                remote_ip=manifest.remote_ip,
                error=f"не удалось разобрать manifest: {exc}",
            )
        package_target = Target(
            package_url,
            parsed.hostname.lower(),
            service="discord",
            profile="discord_update",
        )
        package = self._cygwin_curl(package_target, "cygwin")
        success = package.success
        return ProbeResult(
            target,
            "discord_update",
            success,
            manifest.http_code,
            time.monotonic() - started,
            remote_ip=package.remote_ip or manifest.remote_ip,
            error="" if success else f"package {parsed.hostname}: {package.error}",
        )

    def _cygwin_body(self, target: Target) -> tuple[ProbeResult, bytes]:
        started = time.monotonic()
        write_out = f"\n{RESULT_MARKER}%{{http_code}}|%{{remote_ip}}|%{{time_total}}|%{{size_download}}"
        resolve_arg = (
            f"--resolve {shlex.quote(f'{target.hostname}:443:{target.resolve_ip}')}"
            if target.resolve_ip else ""
        )
        curl_command = " ".join(
            (
                "exec /usr/local/bin/curl",
                "--silent --show-error --location --max-redirs 3 --compressed",
                f"--connect-timeout {self.timeout} --max-time {self.timeout + 2}",
                "--http2 --noproxy '*' --max-filesize 2097152",
                resolve_arg,
                "--write-out", shlex.quote(write_out),
                shlex.quote(target.url),
            )
        )
        shell_command = f"export PATH=/usr/local/bin:/usr/bin:$PATH; {curl_command}"
        command = [str(self.paths.cygwin_bash), "--noprofile", "--norc", "-lc", shell_command]
        try:
            completed = run_external(
                command,
                cwd=self.paths.bundle_root / "cygwin",
                capture_output=True,
                timeout=self.timeout + 5,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            result = ProbeResult(target, "cygwin-body", False, None, time.monotonic() - started, error=str(exc))
            return result, b""
        marker = ("\n" + RESULT_MARKER).encode("ascii")
        position = completed.stdout.rfind(marker)
        if position < 0:
            error = completed.stderr.decode("utf-8", errors="replace").strip()
            result = ProbeResult(
                target, "cygwin-body", False, None, time.monotonic() - started,
                error=error or f"curl exit={completed.returncode}, no result marker",
            )
            return result, b""
        body = completed.stdout[:position]
        metadata = completed.stdout[position + 1:].decode("ascii", errors="replace")
        code, remote_ip, reported_time, _downloaded = self._parse_result(metadata)
        success = completed.returncode == 0 and code is not None and 200 <= code < 300 and bool(body)
        error = ""
        if not success:
            error = completed.stderr.decode("utf-8", errors="replace").strip()
            error = error or f"curl exit={completed.returncode}, HTTP={code or 0}, bytes={len(body)}"
        result = ProbeResult(
            target,
            "cygwin-body",
            success,
            code,
            reported_time or (time.monotonic() - started),
            remote_ip=remote_ip,
            error=error[-500:],
        )
        return result, body

    def _run(self, command: list[str], target: Target, validator: str, cwd: Path) -> ProbeResult:
        started = time.monotonic()
        try:
            completed = run_external(
                command,
                cwd=cwd,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.timeout + 3,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return ProbeResult(target, validator, False, None, time.monotonic() - started, error=str(exc))
        elapsed = time.monotonic() - started
        code, remote_ip, reported_time, downloaded = self._parse_result(completed.stdout)
        success = self._curl_succeeded(completed.returncode, code, remote_ip, downloaded)
        error = ""
        if not success:
            error = completed.stderr.strip() or f"curl exit={completed.returncode}, HTTP={code or 0}"
        return ProbeResult(
            target=target,
            validator=validator,
            success=success,
            http_code=code,
            elapsed=reported_time or elapsed,
            remote_ip=remote_ip,
            error=error[-500:],
        )

    @staticmethod
    def _parse_result(output: str) -> tuple[int | None, str, float | None, float]:
        position = output.rfind(RESULT_MARKER)
        if position < 0:
            return None, "", None, 0.0
        payload = output[position + len(RESULT_MARKER):].strip().splitlines()[0]
        parts = payload.split("|")
        try:
            code = int(parts[0])
        except (IndexError, ValueError):
            code = None
        remote_ip = parts[1] if len(parts) > 1 else ""
        try:
            elapsed = float(parts[2])
        except (IndexError, ValueError):
            elapsed = None
        try:
            downloaded = float(parts[3])
        except (IndexError, ValueError):
            downloaded = 0.0
        return code, remote_ip, elapsed, downloaded

    @staticmethod
    def _curl_succeeded(
        returncode: int,
        code: int | None,
        remote_ip: str,
        downloaded: float,
    ) -> bool:
        http_ok = code is not None and 200 <= code < 500 and code != 451 and bool(remote_ip)
        if not http_ok:
            return False
        if returncode == 0:
            return True
        # Some Cloudflare pages ignore Range and keep transferring beyond the short probe timeout.
        # A verified TLS response with a valid status and a meaningful body proves reachability.
        return returncode == 28 and downloaded >= 512
