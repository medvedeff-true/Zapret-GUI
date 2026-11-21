import asyncio
import logging
import os
import threading
import time

from tg_ws_proxy_vendor.proxy import tg_ws_proxy as flowseal_proxy
from tg_ws_proxy_vendor.proxy.config import proxy_config, stop_cfproxy_domain_refresh
from tg_ws_proxy_vendor.proxy.stats import stats as flowseal_stats


log = logging.getLogger(__name__)


class TelegramProxyError(RuntimeError):
    pass


class TelegramProxyController:
    STOP_TIMEOUT = 6.0
    CLEANUP_TIMEOUT = 1.0

    def __init__(self) -> None:
        self._thread = None
        self._loop = None
        self._stop_event = None
        self._stop_requested = threading.Event()
        self._started = threading.Event()
        self._stopped = threading.Event()
        self._lock = threading.RLock()
        self._host = "127.0.0.1"
        self._port = 1443
        self._secret = ""
        self._started_at = 0.0
        self._last_error = ""

    def start(self, port: int = 1443, secret: str | None = None) -> None:
        port = int(port or 1443)
        secret = self._normalize_secret(secret)

        with self._lock:
            if self.is_running():
                if port != self._port:
                    raise TelegramProxyError(f"Telegram proxy already runs on port {self._port}")
                if secret != self._secret:
                    raise TelegramProxyError("Telegram proxy already runs with another secret")
                return
            if self._thread is not None and self._thread.is_alive():
                raise TelegramProxyError("Telegram MTProto proxy is still starting or stopping")

            self._port = port
            self._secret = secret
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

    def stop(self) -> None:
        with self._lock:
            self._stop_requested.set()
            loop = self._loop
            stop_event = self._stop_event
            thread = self._thread
        if loop is not None and stop_event is not None:
            try:
                loop.call_soon_threadsafe(stop_event.set)
            except RuntimeError:
                pass

        if thread is not None and thread.is_alive():
            thread.join(timeout=self.STOP_TIMEOUT)
            if thread.is_alive():
                raise TelegramProxyError("Telegram MTProto proxy stop timed out")

        with self._lock:
            if self._thread is thread:
                self._thread = None
                self._loop = None
                self._stop_event = None

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
        return f"tg://proxy?server={self._host}&port={int(self._port)}&secret=dd{self._secret}"

    def stats(self) -> dict:
        return {
            "running": self.is_running(),
            "host": self._host,
            "port": self._port,
            "secret": self._secret,
            "link": self.proxy_link() if self._secret else "",
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
        try:
            loop = asyncio.new_event_loop()
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
        proxy_config.host = self._host
        proxy_config.port = int(self._port)
        proxy_config.secret = self._secret
        proxy_config.dc_redirects = {2: "149.154.167.220", 4: "149.154.167.220"}
        proxy_config.buffer_size = 256 * 1024
        proxy_config.pool_size = 4
        proxy_config.fallback_cfproxy = True
        proxy_config.cfproxy_user_domains = []
        proxy_config.cfproxy_worker_domains = []
        proxy_config.cfproxy_h2_media = True
        proxy_config.disable_secure = False
        proxy_config.force_test_dc = False
        proxy_config.fake_tls_domain = ""
        proxy_config.proxy_protocol = False

    @staticmethod
    def _reset_flowseal_stats() -> None:
        for key, value in vars(flowseal_stats).items():
            if isinstance(value, int):
                setattr(flowseal_stats, key, 0)

    @staticmethod
    def _normalize_secret(secret: str | None) -> str:
        value = str(secret or "").strip().lower()
        if not value:
            return os.urandom(16).hex()
        if value.startswith("dd") and len(value) == 34:
            value = value[2:]
        if len(value) != 32:
            raise TelegramProxyError("Telegram MTProto secret must be 32 hex chars")
        try:
            bytes.fromhex(value)
        except ValueError as e:
            raise TelegramProxyError("Telegram MTProto secret must be valid hex") from e
        return value
