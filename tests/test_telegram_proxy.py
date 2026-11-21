import asyncio
import hashlib
import socket
import struct
import threading
import time
import unittest
from collections import deque
from unittest.mock import AsyncMock, Mock, patch

from tg_ws_proxy_vendor.proxy import __version__, bridge, raw_websocket, tg_ws_proxy
from tg_ws_proxy_vendor.proxy.config import ProxyConfig
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


class TelegramMediaRoutingTests(unittest.IsolatedAsyncioTestCase):
    async def test_warmup_preserves_main_dc2_without_warming_relay_first_media(self):
        config = ProxyConfig()
        config.dc_redirects = {2: "main-dc2", 4: "main-dc4"}
        config.media_cf_first = {2}
        pool = type(tg_ws_proxy.ws_pool)()

        with (
            patch("tg_ws_proxy_vendor.proxy.pool.proxy_config", config),
            patch.object(pool, "_schedule_refill") as refill,
        ):
            await pool.warmup()

        self.assertEqual(
            [call.args[:2] for call in refill.call_args_list],
            [
                ((2, False, False), "main-dc2"),
                ((4, False, False), "main-dc4"),
                ((4, True, False), "main-dc4"),
            ],
        )

    async def test_initial_dc2_route_waits_for_cold_pool(self):
        config = ProxyConfig()
        pool = type(tg_ws_proxy.ws_pool)()
        key = (2, False, False)
        socket_ready = Mock()

        async def refill():
            await asyncio.sleep(0.01)
            pool._idle[key] = deque([(socket_ready, time.monotonic())])
            pool._refilling.pop(key)

        def schedule(refill_key, *_args):
            if not refill_task.done() and not pool._idle[refill_key]:
                pool._refilling[refill_key] = refill_task

        refill_task = asyncio.create_task(refill())
        with (
            patch("zapret_gui.telegram_proxy.proxy_config", config),
            patch("tg_ws_proxy_vendor.proxy.pool.proxy_config", config),
            patch.object(pool, "_is_stale", return_value=False),
            patch.object(pool, "_schedule_refill", side_effect=schedule),
        ):
            TelegramProxyController()._configure_flowseal_proxy()
            self.assertEqual(set(config.dc_redirects), {2, 4})
            self.assertEqual(config.media_cf_first, {2})
            self.assertIs(await asyncio.wait_for(pool.get(2, False), 1), socket_ready)
        await refill_task

    async def test_direct_media_does_not_spend_whole_budget_on_first_attempt(self):
        direct_ws = Mock()
        calls = []

        async def connect(*args, **kwargs):
            calls.append(kwargs.get("sni"))
            if len(calls) == 1:
                await asyncio.Future()
            return direct_ws

        pool = type(tg_ws_proxy.ws_pool)()
        with (
            patch("tg_ws_proxy_vendor.proxy.pool.proxy_config", ProxyConfig()),
            patch("tg_ws_proxy_vendor.proxy.pool.DIRECT_MEDIA_ATTEMPT_TIMEOUT", 0.02),
            patch.object(raw_websocket.RawWebSocket, "connect", side_effect=connect),
        ):
            self.assertIs(await asyncio.wait_for(pool.connect_direct(4, True), 1), direct_ws)
        self.assertEqual(len(calls), 2)

    async def test_failed_ws_init_falls_back_before_reading_client_payload(self):
        ws = Mock(send=AsyncMock(side_effect=ConnectionResetError))
        writer = Mock(wait_closed=AsyncMock())
        writer.get_extra_info.return_value = ("127.0.0.1", 12345)
        reader = Mock()
        with (
            patch.object(tg_ws_proxy.ws_pool, "get", new=AsyncMock(return_value=ws)),
            patch.object(tg_ws_proxy, "set_sock_opts"),
            patch.object(tg_ws_proxy, "_read_client_init",
                         new=AsyncMock(return_value=(b"", reader, writer, "test"))),
            patch.object(tg_ws_proxy, "_try_handshake",
                         return_value=(2, False, tg_ws_proxy.PROTO_TAG_SECURE, b"\x01" * 48)),
            patch.object(tg_ws_proxy, "do_fallback", new=AsyncMock(return_value=True)) as fallback,
        ):
            await tg_ws_proxy._handle_client(reader, writer, b"\x01" * 16)
        ws.writer.transport.abort.assert_called_once()
        reader.read.assert_not_called()
        fallback.assert_awaited_once()

    async def test_stalled_cf_ws_attempts_do_not_delay_tcp_indefinitely(self):
        async def unresponsive(*_args, **_kwargs):
            await asyncio.Future()

        with (
            patch.object(bridge, "proxy_config", ProxyConfig()),
            patch.object(bridge.balancer, "get_domains_for_dc",
                         return_value=iter(f"test{i}.invalid" for i in range(20))),
            patch.object(raw_websocket.RawWebSocket, "connect",
                         new=AsyncMock(side_effect=unresponsive)),
            patch.object(bridge, "CF_WS_ATTEMPT_TIMEOUT", 0.02),
            patch.object(bridge, "CF_WS_SETUP_TIMEOUT", 0.05),
            patch.object(bridge, "_tcp_fallback", new=AsyncMock(return_value=True)) as tcp,
        ):
            self.assertTrue(await asyncio.wait_for(
                bridge.do_fallback(Mock(), Mock(), b"", "test", 2, False, False, "", Mock()),
                1,
            ))
        tcp.assert_awaited_once()

    async def test_media_relay_first_tries_cf_before_direct(self):
        steps = []

        async def cf_unavailable(*_args, **_kwargs):
            steps.append("cf")
            return False

        async def direct_available():
            steps.append("direct")
            return True

        with (
            patch.object(bridge, "proxy_config", ProxyConfig()),
            patch.object(bridge, "_cfproxy_fallback", side_effect=cf_unavailable),
        ):
            self.assertTrue(await bridge.do_fallback(
                Mock(), Mock(), b"", "media", 2, False, True, " media",
                Mock(), h2_pool=None, proto_tag=tg_ws_proxy.PROTO_TAG_SECURE,
                try_direct=direct_available,
            ))
        self.assertEqual(steps, ["cf", "direct"])

    async def test_media_relay_that_never_answers_is_skipped_on_reconnect(self):
        async def blocked():
            await asyncio.Future()

        def client_reader():
            reader = asyncio.StreamReader()
            reader.feed_data(b"file request")
            return reader

        cipher = Mock()
        cipher.update.side_effect = lambda data: data
        ctx = bridge.CryptoCtx(cipher, cipher, cipher, cipher)
        ws = Mock(send=AsyncMock(), recv=AsyncMock(side_effect=blocked), close=AsyncMock())
        direct = AsyncMock(return_value=True)
        with (
            patch.object(bridge, "proxy_config", ProxyConfig()),
            patch.object(bridge, "_media_cf_retry_after", {}),
            patch.object(bridge, "CF_MEDIA_FIRST_REPLY_TIMEOUT", 0.02),
            patch.object(bridge.balancer, "get_domains_for_dc", return_value=["relay.invalid"]),
            patch.object(bridge.balancer, "update_domain_for_dc"),
            patch.object(raw_websocket.RawWebSocket, "connect", new=AsyncMock(return_value=ws)) as connect,
        ):
            async def attempt():
                return await bridge.do_fallback(
                    client_reader(), Mock(), b"init", "media", 2, False, True, " media", ctx,
                    try_direct=direct,
                )

            self.assertTrue(await asyncio.wait_for(attempt(), 1))
            ws.close.assert_awaited_once()
            direct.assert_not_awaited()  # do not replay a stream already sent to CF
            self.assertTrue(await asyncio.wait_for(attempt(), 1))
            direct.assert_awaited_once()
            connect.assert_awaited_once()

    async def test_media_relay_forwards_large_payload_after_negative_dc_handshake(self):
        config = ProxyConfig(media_cf_first={2}, cfproxy_h2_media=False)
        secret = b"\x01" * 16
        handshake = tg_ws_proxy._generate_relay_init(tg_ws_proxy.PROTO_TAG_SECURE, -2)
        keys = handshake[8:56]
        # Encrypt the native handshake tail the same way Desktop does
        # (with the local proxy's secret, unlike the upstream handshake).
        def key_stream(key):
            return tg_ws_proxy.Cipher(
                tg_ws_proxy.algorithms.AES(key), tg_ws_proxy.modes.CTR(keys[32:]),
            ).encryptor().update(bytes(64))[56:]

        tail = bytes(a ^ b ^ c for a, b, c in zip(
            handshake[56:], key_stream(keys[:32]), key_stream(hashlib.sha256(keys[:32] + secret).digest()),
        ))
        handshake = handshake[:56] + tail
        # Use fresh CTR states for subsequent traffic.
        native = tg_ws_proxy._build_crypto_ctx(keys, secret, handshake)
        request = struct.pack("<I", 64) + b"r" * 64
        media = bytes(range(256)) * 1024
        reply = struct.pack("<I", len(media)) + media
        sent_request = asyncio.Event()
        finished = asyncio.Event()
        relay_ctx = None
        reply_sent = False

        async def send(data):
            nonlocal relay_ctx
            if relay_ctx is None:
                self.assertEqual(len(data), 64)
                relay_ctx = tg_ws_proxy._build_crypto_ctx(keys, secret, data)
            else:
                self.assertEqual(relay_ctx.tg_enc.update(data), request)
                sent_request.set()

        async def recv():
            nonlocal reply_sent
            if reply_sent:
                await asyncio.Future()
            await sent_request.wait()
            reply_sent = True
            return relay_ctx.tg_dec.update(reply)

        async def handle(reader, writer):
            try:
                await tg_ws_proxy._handle_client(reader, writer, secret)
            finally:
                finished.set()

        ws = Mock(send=AsyncMock(side_effect=send), recv=AsyncMock(side_effect=recv), close=AsyncMock())
        with (
            patch.object(tg_ws_proxy, "proxy_config", config),
            patch.object(bridge, "proxy_config", config),
            patch.object(bridge, "_media_cf_retry_after", {}),
            patch.object(bridge.balancer, "get_domains_for_dc", return_value=["relay.invalid"]),
            patch.object(bridge.balancer, "update_domain_for_dc"),
            patch.object(raw_websocket.RawWebSocket, "connect", new=AsyncMock(return_value=ws)),
            patch.object(tg_ws_proxy.ws_pool, "get", new=AsyncMock()) as direct_get,
        ):
            server = await asyncio.start_server(handle, "127.0.0.1", 0)
            async with server:
                reader, writer = await asyncio.open_connection(*server.sockets[0].getsockname())
                try:
                    writer.write(handshake + native.clt_dec.update(request))
                    await writer.drain()
                    response = await asyncio.wait_for(reader.readexactly(len(reply)), 2)
                    self.assertEqual(native.clt_enc.update(response), reply)
                finally:
                    writer.close()
                    await writer.wait_closed()
                await asyncio.wait_for(finished.wait(), 1)
        direct_get.assert_not_awaited()

    async def test_cold_primary_connection_tries_direct_ws_before_cf(self):
        config = ProxyConfig()
        direct = Mock()
        with (
            patch.object(tg_ws_proxy, "proxy_config", config),
            patch.object(tg_ws_proxy.ws_pool, "get", new=AsyncMock(return_value=None)),
            patch.object(tg_ws_proxy.ws_pool, "connect_direct",
                         new=AsyncMock(return_value=direct)) as direct_connect,
            patch.object(tg_ws_proxy, "send_ws_relay_init",
                         new=AsyncMock(return_value=True)),
            patch.object(tg_ws_proxy, "bridge_ws_reencrypt",
                         new=AsyncMock()) as bridge_ws,
            patch.object(tg_ws_proxy, "set_sock_opts"),
            patch.object(tg_ws_proxy, "_read_client_init",
                         new=AsyncMock(return_value=(b"", Mock(), Mock(), "test"))),
            patch.object(tg_ws_proxy, "_try_handshake",
                         return_value=(2, False, tg_ws_proxy.PROTO_TAG_SECURE, b"\x01" * 48)),
        ):
            writer = Mock(wait_closed=AsyncMock())
            writer.get_extra_info.return_value = ("127.0.0.1", 12345)
            await tg_ws_proxy._handle_client(Mock(), writer, b"\x01" * 16)
        direct_connect.assert_awaited_once_with(2, False, is_test_dc=False)
        bridge_ws.assert_awaited_once()


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
