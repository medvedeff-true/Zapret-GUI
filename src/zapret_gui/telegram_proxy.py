import asyncio
import ipaddress
import logging
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlencode

from tg_ws_proxy_vendor.logging_setup import build_log_handler
from tg_ws_proxy_vendor.proxy import tg_ws_proxy as flowseal_proxy
from tg_ws_proxy_vendor.proxy.config import (
    coerce_domain_list, parse_dc_ip_list, proxy_config, stop_cfproxy_domain_refresh,
)
from tg_ws_proxy_vendor.proxy.stats import stats as flowseal_stats


log = logging.getLogger(__name__)


class TelegramProxyError(RuntimeError):
    pass


def _normalize_secret(secret: str | None) -> str:
    value = str(secret or "").strip().lower()
    if not value:
        return os.urandom(16).hex()
    if value.startswith("dd") and len(value) == 34:
        value = value[2:]
    if not re.fullmatch(r"[a-f0-9]{32}", value):
        raise TelegramProxyError("MTProto secret must contain exactly 32 hexadecimal characters")
    return value


def _proxy_domains(domains) -> tuple[str, ...]:
    result = []
    for value in coerce_domain_list(domains):
        domain = value.lower().rstrip(".")
        if len(domain) > 253 or "." not in domain or not all(
            re.fullmatch(r"[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?", part)
            for part in domain.split(".")
        ):
            raise ValueError(f"Invalid relay domain: {value}")
        if domain not in result:
            result.append(domain)
    return tuple(result)


@dataclass(frozen=True)
class TelegramProxyOptions:
    host: str = "127.0.0.1"
    port: int = 1443
    secret: str = field(default="", repr=False)
    dc_rules: tuple[str, ...] = ("2:149.154.167.220", "4:149.154.167.220")
    cf_enabled: bool = True
    h2_media: bool = True
    custom_cf: bool = False
    cf_domains: tuple[str, ...] = ()
    custom_worker: bool = False
    worker_domains: tuple[str, ...] = ()
    verbose: bool = False
    disable_tls: bool = False
    buffer_kib: int = 256
    pool_size: int = 4
    log_max_mb: float = 5.0

    def __post_init__(self):
        host = ipaddress.ip_address(self.host.strip())
        if host.is_multicast or (host.version == 6 and host.scope_id):
            raise ValueError("Enter a local IP address without a scope ID")
        object.__setattr__(self, "host", str(host))
        object.__setattr__(self, "secret", _normalize_secret(self.secret))
        if not 1 <= self.port <= 65535:
            raise ValueError("Port must be between 1 and 65535")
        if not 32 <= self.buffer_kib <= 4096 or not 0 <= self.pool_size <= 32:
            raise ValueError("Buffer must be 32–4096 KiB, and WebSocket pool size 0–32")
        if not 0.1 <= self.log_max_mb <= 100:
            raise ValueError("Log size must be between 0.1 and 100 MB")
        rules = tuple(rule.strip() for rule in self.dc_rules if rule.strip())
        redirects = parse_dc_ip_list(list(rules))
        if len(rules) != len(redirects) or any(not 1 <= dc <= 32767 for dc in redirects):
            raise ValueError("Use unique DC numbers (1–32767), one DC:IPv4 rule per line")
        object.__setattr__(self, "dc_rules", tuple(f"{dc}:{ip}" for dc, ip in redirects.items()))
        object.__setattr__(self, "cf_domains", _proxy_domains(self.cf_domains))
        object.__setattr__(self, "worker_domains", _proxy_domains(self.worker_domains))
        if self.cf_enabled and self.custom_cf and not self.cf_domains:
            raise ValueError("Enter a custom Cloudflare Proxy domain or clear its checkbox")
        if self.custom_worker and not self.worker_domains:
            raise ValueError("Enter a Cloudflare Worker domain or clear its checkbox")

    @property
    def client_host(self) -> str:
        return {"0.0.0.0": "127.0.0.1", "::": "::1"}.get(self.host, self.host)

    def link(self) -> str:
        return "tg://proxy?" + urlencode({
            "server": self.client_host, "port": self.port, "secret": "dd" + self.secret,
        })


class TelegramProxyController:
    STOP_TIMEOUT = 6.0
    CLEANUP_TIMEOUT = 1.0

    def __init__(self, log_path: str | None = None) -> None:
        self._thread = None
        self._loop = None
        self._stop_event = None
        self._stop_requested = threading.Event()
        self._started = threading.Event()
        self._stopped = threading.Event()
        self._lock = threading.RLock()
        self._options = TelegramProxyOptions()
        self._log_path = log_path
        self._started_at = 0.0
        self._last_error = ""

    @property
    def options(self) -> TelegramProxyOptions:
        return self._options

    def start(
        self, port: int = 1443, secret: str | None = None, *,
        options: TelegramProxyOptions | None = None, cancelled=None,
    ) -> None:
        options = options if options is not None else TelegramProxyOptions(
            port=int(port or 1443), secret=secret or "",
        )
        with self._lock:
            if cancelled is not None and cancelled():
                raise TelegramProxyError("Telegram proxy start cancelled")
            if self.is_running():
                if options != self._options:
                    raise TelegramProxyError("Restart Telegram proxy to apply different settings")
                return
            if self._thread is not None and self._thread.is_alive():
                raise TelegramProxyError("Telegram MTProto proxy is still starting or stopping")

            self._options = options
            self._last_error = ""
            self._started_at = 0.0
            self._started.clear()
            self._stopped.clear()
            self._stop_requested.clear()
            self._thread = threading.Thread(
                target=self._thread_main,
                name="ZapretGUI-TelegramMTProtoProxy",
                daemon=True,
            )
            self._thread.start()

        if not self._started.wait(8.0):
            self.stop()
            raise TelegramProxyError("Telegram MTProto proxy start timed out")

        err = self._last_error
        if err or not self.is_running():
            raise TelegramProxyError(err or "Telegram MTProto proxy stopped during startup")

    def restart(self, options: TelegramProxyOptions, *, cancelled=None) -> None:
        previous = self._options if self.is_running() else None
        self.stop(cancelled=cancelled)
        try:
            self.start(options=options, cancelled=cancelled)
        except Exception:
            if previous is not None and not (cancelled and cancelled()):
                try:
                    # A listener that failed to bind can still be cleaning up.
                    self.stop(cancelled=cancelled)
                    self.start(options=previous, cancelled=cancelled)
                except Exception:
                    log.exception("Could not restore the previous Telegram proxy settings")
            raise

    def stop(self, *, cancelled=None) -> None:
        thread = self.request_stop(cancelled=cancelled)

        if thread is not None and thread.is_alive():
            thread.join(timeout=self.STOP_TIMEOUT)
            if thread.is_alive():
                raise TelegramProxyError("Telegram MTProto proxy stop timed out")

        with self._lock:
            if self._thread is thread:
                self._thread = None
                self._loop = None
                self._stop_event = None

    def request_stop(self, *, cancelled=None):
        """Signal the proxy without waiting for its network thread."""
        with self._lock:
            if cancelled is not None and cancelled():
                raise TelegramProxyError("Telegram proxy stop cancelled")
            self._stop_requested.set()
            loop = self._loop
            stop_event = self._stop_event
            thread = self._thread
        if loop is not None and stop_event is not None:
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                pass

        return thread

    def is_running(self) -> bool:
        thread = self._thread
        return bool(
            thread is not None
            and thread.is_alive()
            and self._started.is_set()
            and not self._stop_requested.is_set()
            and not self._stopped.is_set()
        )

    def proxy_link(self) -> str:
        return self._options.link()

    def stats(self) -> dict:
        return {
            "running": self.is_running(),
            "host": self._options.host,
            "port": self._options.port,
            "secret": self._options.secret,
            "link": self.proxy_link(),
            "started_at": self._started_at,
            "last_error": self._last_error,
            "connections_total": int(getattr(flowseal_stats, "connections_total", 0) or 0),
            "connections_active": int(getattr(flowseal_stats, "connections_active", 0) or 0),
            "connections_ws": int(getattr(flowseal_stats, "connections_ws", 0) or 0),
            "connections_tcp_fallback": int(getattr(flowseal_stats, "connections_tcp_fallback", 0) or 0),
            "connections_cfproxy": int(getattr(flowseal_stats, "connections_cfproxy", 0) or 0),
            "connections_bad": int(getattr(flowseal_stats, "connections_bad", 0) or 0),
            "ws_errors": int(getattr(flowseal_stats, "ws_errors", 0) or 0),
        }

    def _thread_main(self) -> None:
        loop = None
        proxy_log = logging.getLogger("tg-mtproto-proxy")
        previous_level = proxy_log.level
        previous_propagate = proxy_log.propagate
        handler = None
        try:
            if self._log_path:
                try:
                    Path(self._log_path).parent.mkdir(parents=True, exist_ok=True)
                    handler = build_log_handler(self._log_path, self._options.log_max_mb)
                    handler.addFilter(lambda record: not (
                        self._options.secret in record.getMessage().lower()
                    ))
                    proxy_log.addHandler(handler)
                    proxy_log.setLevel(logging.DEBUG if self._options.verbose else logging.INFO)
                    proxy_log.propagate = False
                except OSError:
                    log.warning("Telegram proxy log is not writable", exc_info=True)
            # The embedded proxy only needs sockets. Keep it off Windows IOCP
            # (including its special asyncio wakeup socket recovery path).
            loop = asyncio.SelectorEventLoop() if sys.platform == "win32" else asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            with self._lock:
                self._loop = loop
                self._stop_event = asyncio.Event()
                if self._stop_requested.is_set():
                    self._stop_event.set()
            self._configure_flowseal_proxy()
            self._reset_flowseal_stats()
            loop.run_until_complete(self._run_flowseal_proxy())
        except Exception as e:
            self._last_error = str(e)
        finally:
            try:
                stop_cfproxy_domain_refresh()
                pending = asyncio.all_tasks(loop) if loop is not None else ()
                for task in pending:
                    task.cancel()
                if pending:
                    _, remaining = loop.run_until_complete(
                        asyncio.wait(pending, timeout=self.CLEANUP_TIMEOUT)
                    )
                    if remaining:
                        log.warning("Telegram proxy shutdown left %d cancelled tasks", len(remaining))
            except Exception:
                log.exception("Telegram proxy cleanup failed")
            finally:
                try:
                    if loop is not None:
                        loop.close()
                finally:
                    if handler is not None:
                        proxy_log.removeHandler(handler)
                        proxy_log.setLevel(previous_level)
                        proxy_log.propagate = previous_propagate
                        handler.close()
                    self._stopped.set()
                    self._started.set()

    async def _run_flowseal_proxy(self) -> None:
        if self._stop_event.is_set():
            return
        task = asyncio.create_task(flowseal_proxy._run(self._stop_event))
        stop = asyncio.create_task(self._stop_event.wait())
        try:
            while not task.done() and not self._stop_event.is_set():
                server = flowseal_proxy._server_instance
                if server is not None and server.is_serving():
                    self._started_at = time.time()
                    self._started.set()
                    break
                await asyncio.sleep(0.05)

            done, _ = await asyncio.wait((task, stop), return_when=asyncio.FIRST_COMPLETED)
            if stop in done and not task.done():
                # Reserve part of the caller's join budget for cancellation
                # and final event-loop cleanup if a transport misbehaves.
                done, _ = await asyncio.wait((task,), timeout=self.STOP_TIMEOUT * 0.5)
                if not done:
                    log.warning("Telegram proxy graceful shutdown timed out; cancelling")
                    return
            await task
            if not self._started.is_set() and not self._stop_event.is_set():
                raise TelegramProxyError("Telegram MTProto proxy did not open its listener")
        finally:
            stop.cancel()
            if not task.done():
                task.cancel()

    def _configure_flowseal_proxy(self) -> None:
        options = self._options
        proxy_config.host = options.host
        proxy_config.port = options.port
        proxy_config.secret = options.secret
        proxy_config.dc_redirects = parse_dc_ip_list(list(options.dc_rules))
        # Apply Flowseal's HTTP/2 media route only to DC2, without removing
        # the working login route. If H2 setup fails, try direct WS before
        # the ordinary CF WebSocket relay (which can accept but stall media).
        proxy_config.media_cf_first = {2}
        proxy_config.buffer_size = options.buffer_kib * 1024
        proxy_config.pool_size = options.pool_size
        proxy_config.fallback_cfproxy = options.cf_enabled
        proxy_config.cfproxy_user_domains = list(options.cf_domains) if options.custom_cf else []
        proxy_config.cfproxy_worker_domains = list(options.worker_domains) if options.custom_worker else []
        proxy_config.cfproxy_h2_media = options.h2_media
        proxy_config.disable_secure = options.disable_tls
        proxy_config.force_test_dc = False
        proxy_config.fake_tls_domain = ""
        proxy_config.proxy_protocol = False

    @staticmethod
    def _reset_flowseal_stats() -> None:
        for key, value in vars(flowseal_stats).items():
            if isinstance(value, int):
                setattr(flowseal_stats, key, 0)
