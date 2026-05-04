import asyncio
import ipaddress
import socket
import ssl
import struct
import threading
import time


TELEGRAM_PROXY_RANGES = (
    "91.108.56.0/22",
    "91.108.4.0/22",
    "91.108.8.0/22",
    "91.108.16.0/22",
    "91.108.12.0/22",
    "149.154.160.0/20",
    "91.105.192.0/23",
    "91.108.20.0/22",
    "185.76.151.0/24",
    "2001:b28:f23d::/48",
    "2001:b28:f23f::/48",
    "2001:67c:4e8::/48",
    "2001:b28:f23c::/48",
    "2a0a:f280::/32",
)

TELEGRAM_NETWORKS = tuple(ipaddress.ip_network(item) for item in TELEGRAM_PROXY_RANGES)

DC_FALLBACK_RANGES = (
    ("149.154.160.0/22", 1),
    ("149.154.164.0/22", 2),
    ("149.154.168.0/22", 3),
    ("149.154.172.0/22", 2),
    ("91.108.56.0/22", 5),
    ("91.108.8.0/22", 3),
    ("91.108.12.0/22", 4),
    ("91.105.192.0/23", 2),
    ("185.76.151.0/24", 2),
    ("91.108.4.0/22", 2),
    ("91.108.16.0/22", 2),
    ("91.108.20.0/22", 2),
)

DC_FALLBACK_NETWORKS = tuple(
    (ipaddress.ip_network(network), dc)
    for network, dc in DC_FALLBACK_RANGES
)


class TelegramProxyError(RuntimeError):
    pass


class TelegramProxyController:
    def __init__(self) -> None:
        self._thread = None
        self._loop = None
        self._server = None
        self._started = threading.Event()
        self._stopped = threading.Event()
        self._lock = threading.RLock()
        self._host = "127.0.0.1"
        self._port = 1080
        self._active_writers = set()
        self._stats = {
            "started_at": 0.0,
            "connections_total": 0,
            "connections_active": 0,
            "telegram_connections": 0,
            "direct_connections": 0,
            "errors": 0,
            "last_error": "",
        }

    def start(self, port: int = 1080) -> None:
        with self._lock:
            if self.is_running():
                if int(port) != self._port:
                    raise TelegramProxyError(f"Telegram proxy already runs on port {self._port}")
                return

            self._port = int(port or 1080)
            self._started.clear()
            self._stopped.clear()
            self._thread = threading.Thread(
                target=self._thread_main,
                name="ZapretGUI-TelegramProxy",
                daemon=True,
            )
            self._thread.start()

        if not self._started.wait(5.0):
            self.stop()
            raise TelegramProxyError("Telegram proxy start timed out")

        err = self._stats.get("last_error", "")
        if err and not self.is_running():
            raise TelegramProxyError(err)

    def stop(self) -> None:
        loop = self._loop
        if loop is not None and loop.is_running():
            try:
                future = asyncio.run_coroutine_threadsafe(self._stop_async(), loop)
                future.result(timeout=5.0)
            except Exception:
                pass
            try:
                loop.call_soon_threadsafe(loop.stop)
            except Exception:
                pass

        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=5.0)

        with self._lock:
            self._thread = None
            self._loop = None
            self._server = None
            self._stats["connections_active"] = 0

    def is_running(self) -> bool:
        loop = self._loop
        return bool(
            self._server is not None
            and loop is not None
            and loop.is_running()
            and self._thread is not None
            and self._thread.is_alive()
        )

    def stats(self) -> dict:
        with self._lock:
            data = dict(self._stats)
            data["running"] = self.is_running()
            data["host"] = self._host
            data["port"] = self._port
            return data

    def _thread_main(self) -> None:
        loop = asyncio.new_event_loop()
        self._loop = loop
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._start_async())
            self._started.set()
            loop.run_forever()
        except Exception as e:
            with self._lock:
                self._stats["last_error"] = str(e)
                self._stats["errors"] += 1
            self._started.set()
        finally:
            try:
                loop.run_until_complete(self._stop_async())
            except Exception:
                pass
            try:
                pending = [task for task in asyncio.all_tasks(loop) if not task.done()]
                for task in pending:
                    task.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            loop.close()
            self._stopped.set()

    async def _start_async(self) -> None:
        self._check_optional_dependencies()
        try:
            server = await asyncio.start_server(
                self._handle_client,
                host=self._host,
                port=self._port,
                family=socket.AF_INET,
                start_serving=True,
            )
        except OSError as e:
            raise TelegramProxyError(f"Cannot bind 127.0.0.1:{self._port}: {e}") from e

        with self._lock:
            self._server = server
            self._stats["started_at"] = time.time()
            self._stats["last_error"] = ""

    async def _stop_async(self) -> None:
        server = self._server
        self._server = None
        if server is not None:
            server.close()
            try:
                await server.wait_closed()
            except Exception:
                pass

        writers = list(self._active_writers)
        for writer in writers:
            self._close_writer(writer)
        if writers:
            await asyncio.sleep(0)

    @staticmethod
    def _check_optional_dependencies() -> None:
        try:
            import websockets  # noqa: F401
        except Exception as e:
            raise TelegramProxyError(
                "Missing dependency: websockets. Install requirements.txt or rebuild the release."
            ) from e

    def _remember_writer(self, writer) -> None:
        self._active_writers.add(writer)

    def _forget_writer(self, writer) -> None:
        self._active_writers.discard(writer)

    @staticmethod
    def _close_writer(writer) -> None:
        try:
            writer.close()
        except Exception:
            pass

    async def _wait_writer_closed(self, writer) -> None:
        try:
            await writer.wait_closed()
        except Exception:
            pass

    def _bump_stat(self, key: str, delta: int = 1) -> None:
        with self._lock:
            self._stats[key] = int(self._stats.get(key, 0) or 0) + int(delta)

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self._remember_writer(writer)
        self._bump_stat("connections_total")
        self._bump_stat("connections_active")
        try:
            dest_host, dest_port = await self._socks5_handshake(reader, writer)
            if self._is_telegram_destination(dest_host):
                self._bump_stat("telegram_connections")
                await self._handle_telegram(reader, writer, dest_host)
            else:
                self._bump_stat("direct_connections")
                await self._handle_direct(reader, writer, dest_host, dest_port)
        except Exception as e:
            self._bump_stat("errors")
            with self._lock:
                self._stats["last_error"] = str(e)
            self._close_writer(writer)
        finally:
            self._forget_writer(writer)
            self._bump_stat("connections_active", -1)
            self._close_writer(writer)
            await self._wait_writer_closed(writer)

    async def _socks5_handshake(self, reader, writer) -> tuple[str, int]:
        header = await asyncio.wait_for(reader.readexactly(2), timeout=10.0)
        ver, nmethods = header[0], header[1]
        if ver != 5 or nmethods <= 0:
            raise TelegramProxyError("Invalid SOCKS5 greeting")
        methods = await asyncio.wait_for(reader.readexactly(nmethods), timeout=10.0)
        if 0 not in methods:
            writer.write(b"\x05\xff")
            await writer.drain()
            raise TelegramProxyError("SOCKS5 no-auth method is not offered")

        writer.write(b"\x05\x00")
        await writer.drain()

        req = await asyncio.wait_for(reader.readexactly(4), timeout=10.0)
        ver, cmd, _rsv, atyp = req
        if ver != 5 or cmd != 1:
            writer.write(b"\x05\x07\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            raise TelegramProxyError("Only SOCKS5 CONNECT is supported")

        if atyp == 1:
            raw = await asyncio.wait_for(reader.readexactly(4), timeout=10.0)
            dest_host = socket.inet_ntop(socket.AF_INET, raw)
        elif atyp == 3:
            ln = await asyncio.wait_for(reader.readexactly(1), timeout=10.0)
            raw = await asyncio.wait_for(reader.readexactly(ln[0]), timeout=10.0)
            dest_host = raw.decode("idna", errors="strict")
        elif atyp == 4:
            raw = await asyncio.wait_for(reader.readexactly(16), timeout=10.0)
            dest_host = socket.inet_ntop(socket.AF_INET6, raw)
        else:
            writer.write(b"\x05\x08\x00\x01\x00\x00\x00\x00\x00\x00")
            await writer.drain()
            raise TelegramProxyError("Unsupported SOCKS5 address type")

        port_raw = await asyncio.wait_for(reader.readexactly(2), timeout=10.0)
        dest_port = struct.unpack("!H", port_raw)[0]
        return dest_host, dest_port

    async def _send_socks_success(self, writer) -> None:
        writer.write(b"\x05\x00\x00\x01\x00\x00\x00\x00\x00\x00")
        await writer.drain()

    async def _send_socks_error(self, writer, code: int = 1) -> None:
        writer.write(bytes((5, code, 0, 1, 0, 0, 0, 0, 0, 0)))
        await writer.drain()

    @staticmethod
    def _ip_for_host(host: str):
        try:
            return ipaddress.ip_address(str(host).strip())
        except ValueError:
            return None

    def _is_telegram_destination(self, host: str) -> bool:
        ip = self._ip_for_host(host)
        if ip is None:
            return False
        return any(ip in network for network in TELEGRAM_NETWORKS)

    def _fallback_dc_for_host(self, host: str) -> int:
        ip = self._ip_for_host(host)
        if ip is not None:
            for network, dc in DC_FALLBACK_NETWORKS:
                if ip in network:
                    return dc
        return 2

    @staticmethod
    def _extract_dc_from_init(init_packet: bytes) -> int | None:
        if len(init_packet) < 64:
            return None
        try:
            from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

            key = init_packet[8:40]
            iv = init_packet[40:56]
            decryptor = Cipher(algorithms.AES(key), modes.CTR(iv)).decryptor()
            decrypted = decryptor.update(init_packet[:64]) + decryptor.finalize()
            dc_id = struct.unpack("<i", decrypted[60:64])[0]
            dc = abs(int(dc_id))
            if 1 <= dc <= 5:
                return dc
        except Exception:
            return None
        return None

    async def _handle_telegram(self, reader, writer, dest_host: str) -> None:
        await self._send_socks_success(writer)
        init_packet = await asyncio.wait_for(reader.readexactly(64), timeout=12.0)
        dc = self._extract_dc_from_init(init_packet) or self._fallback_dc_for_host(dest_host)
        dc = max(1, min(5, int(dc)))

        try:
            from websockets.asyncio.client import connect
        except Exception:
            from websockets import connect

        ssl_ctx = ssl.create_default_context()
        uri = f"wss://kws{dc}.web.telegram.org/apiws"
        async with connect(
            uri,
            subprotocols=["binary"],
            ssl=ssl_ctx,
            ping_interval=None,
            max_size=None,
        ) as ws:
            await ws.send(init_packet)
            await self._relay_tcp_websocket(reader, writer, ws)

    async def _handle_direct(self, reader, writer, dest_host: str, dest_port: int) -> None:
        try:
            remote_reader, remote_writer = await asyncio.wait_for(
                asyncio.open_connection(dest_host, dest_port),
                timeout=12.0,
            )
        except Exception:
            await self._send_socks_error(writer, 5)
            raise

        self._remember_writer(remote_writer)
        try:
            await self._send_socks_success(writer)
            await self._relay_tcp_pair(reader, writer, remote_reader, remote_writer)
        finally:
            self._forget_writer(remote_writer)
            self._close_writer(remote_writer)
            await self._wait_writer_closed(remote_writer)

    async def _relay_tcp_pair(self, left_reader, left_writer, right_reader, right_writer) -> None:
        async def pump(src, dst):
            try:
                while True:
                    data = await src.read(65536)
                    if not data:
                        break
                    dst.write(data)
                    await dst.drain()
            finally:
                self._close_writer(dst)

        tasks = (
            asyncio.create_task(pump(left_reader, right_writer)),
            asyncio.create_task(pump(right_reader, left_writer)),
        )
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*done, *pending, return_exceptions=True)

    async def _relay_tcp_websocket(self, reader, writer, ws) -> None:
        async def tcp_to_ws():
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                await ws.send(data)
            try:
                await ws.close()
            except Exception:
                pass

        async def ws_to_tcp():
            async for message in ws:
                if isinstance(message, str):
                    continue
                writer.write(message)
                await writer.drain()
            self._close_writer(writer)

        tasks = (
            asyncio.create_task(tcp_to_ws()),
            asyncio.create_task(ws_to_tcp()),
        )
        done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in pending:
            task.cancel()
        await asyncio.gather(*done, *pending, return_exceptions=True)
