import asyncio
import socket
import threading
import time
import unittest
from unittest.mock import AsyncMock, Mock, patch

from tg_ws_proxy_vendor.proxy import __version__, raw_websocket, tg_ws_proxy
from zapret_gui.telegram_proxy import TelegramProxyController, TelegramProxyError


class TelegramProxyTests(unittest.TestCase):
    def test_disconnected_client_with_stuck_upstream_is_reaped(self):
        with socket.socket() as address:
            address.bind(("127.0.0.1", 0))
            port = address.getsockname()[1]

        bridged = threading.Event()
        aborted = threading.Event()

        async def blocked_read(_count):
            bridged.set()
            await asyncio.Future()

        async def blocked_close():
            await asyncio.Future()

        writer = Mock()
        writer.is_closing.return_value = False
        writer.drain = AsyncMock()
        writer.wait_closed = AsyncMock(side_effect=blocked_close)
        writer.transport.abort.side_effect = aborted.set
        upstream = raw_websocket.RawWebSocket(Mock(), writer)
        upstream.reader.readexactly = AsyncMock(side_effect=blocked_read)

        proxy = TelegramProxyController()
        secret = "01" * 16
        with (
            patch.object(tg_ws_proxy, "start_cfproxy_domain_refresh"),
            patch.object(tg_ws_proxy.ws_pool, "warmup", new_callable=AsyncMock),
            patch.object(tg_ws_proxy.cf_worker_pool, "warmup", new_callable=AsyncMock),
            patch.object(tg_ws_proxy.ws_pool, "get", new=AsyncMock(return_value=upstream)),
            patch.object(tg_ws_proxy, "_try_handshake",
                         return_value=(2, False, tg_ws_proxy.PROTO_TAG_SECURE, b"\x01" * 48)),
            patch.object(raw_websocket, "STREAM_CLOSE_TIMEOUT", 0.1),
        ):
            proxy.start(port, secret)
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                    client.sendall(b"x" * 64)
                    self.assertTrue(bridged.wait(2), "client never reached the WebSocket bridge")
                self.assertTrue(aborted.wait(2), "client close left the upstream transport hanging")
                self.assertTrue(proxy.is_running())
                # Keep the next client's handshake incomplete during stop.
                with socket.create_connection(("127.0.0.1", port), timeout=2) as client:
                    client.sendall(b"x")
                    proxy.stop()
                self.assertFalse(tg_ws_proxy._client_tasks)
                self.assertIsNone(tg_ws_proxy._server_instance)
                proxy.start(port, secret)
                self.assertTrue(proxy.is_running())
            finally:
                proxy.stop()

    def test_embedded_proxy_restarts_locally_without_external_network(self):
        self.assertEqual("1.11.4", __version__)
        with socket.socket() as address:
            address.bind(("127.0.0.1", 0))
            port = address.getsockname()[1]

        proxy = TelegramProxyController()
        # Exercise the real listener and shutdown; no background Internet calls.
        with (
            patch.object(tg_ws_proxy, "start_cfproxy_domain_refresh"),
            patch.object(tg_ws_proxy.ws_pool, "warmup", new_callable=AsyncMock),
            patch.object(tg_ws_proxy.cf_worker_pool, "warmup", new_callable=AsyncMock),
        ):
            for _ in range(2):
                proxy.start(port, "01" * 16)
                try:
                    self.assertTrue(proxy.is_running())
                    with socket.create_connection(("127.0.0.1", port), timeout=2):
                        pass
                finally:
                    proxy.stop()
                self.assertFalse(proxy.is_running())
                self.assertIsNone(tg_ws_proxy._server_instance)

    def test_occupied_port_reports_error_instead_of_running(self):
        proxy = TelegramProxyController()
        with socket.socket() as address, patch.object(tg_ws_proxy, "start_cfproxy_domain_refresh"):
            address.bind(("127.0.0.1", 0))
            address.listen()
            try:
                with self.assertRaises(TelegramProxyError):
                    proxy.start(address.getsockname()[1], "01" * 16)
            finally:
                proxy.stop()
        self.assertFalse(proxy.is_running())

    def test_stop_cancels_stalled_graceful_shutdown(self):
        cancelled = threading.Event()

        async def stalled_cleanup(stop_event):
            tg_ws_proxy._server_instance = Mock()
            try:
                await stop_event.wait()
                await asyncio.Future()
            finally:
                tg_ws_proxy._server_instance = None
                cancelled.set()

        proxy = TelegramProxyController()
        with (
            patch.object(tg_ws_proxy, "_run", stalled_cleanup),
            patch.object(proxy, "STOP_TIMEOUT", 2.0),
        ):
            proxy.start(1443, "01" * 16)
            try:
                start = time.monotonic()
                proxy.stop()
                self.assertLess(time.monotonic() - start, 2.0)
                self.assertTrue(cancelled.is_set())
                self.assertFalse(proxy.is_running())
            finally:
                proxy.stop()


class WebSocketCloseTests(unittest.IsolatedAsyncioTestCase):
    async def test_hanging_close_frame_aborts_transport(self):
        async def blocked_drain():
            await asyncio.Future()

        writer = Mock()
        writer.is_closing.return_value = False
        writer.drain = AsyncMock(side_effect=blocked_drain)
        ws = raw_websocket.RawWebSocket(Mock(), writer)
        with patch.object(raw_websocket, "STREAM_CLOSE_TIMEOUT", 0.05):
            await asyncio.wait_for(ws.close(), timeout=1)
        writer.transport.abort.assert_called_once()
