import asyncio
import logging
import struct
import time

from typing import Dict, List, Optional, Set, Tuple
from urllib.parse import urlencode

from .utils import *
from .stats import stats
from .balancer import balancer
from .config import proxy_config
from .raw_websocket import RawWebSocket
from .pool import cf_worker_pool
from .network_debug import WsActivity
from .cf_h2 import bridge_h2


log = logging.getLogger('tg-mtproto-proxy')
media_log = logging.getLogger('zapret_gui.startup.telegram_media')
_st_I_le = struct.Struct('<I')

RELAY_INIT_TIMEOUT = 10.0
CF_WS_SETUP_TIMEOUT = 8.0
CF_WS_ATTEMPT_TIMEOUT = 3.0
CF_WS_RETRY_DELAY = 30.0
CF_MEDIA_FIRST_REPLY_TIMEOUT = 12.0
TCP_BACKOFF_INITIAL = 30.0
TCP_BACKOFF_MAX = 3600.0
_tcp_failures: Dict[Tuple[str, int], int] = {}
_tcp_retry_after: Dict[Tuple[str, int], float] = {}
_tcp_connecting: Set[Tuple[str, int]] = set()
_media_cf_retry_after: Dict[int, float] = {}
_media_cf_plain_until: Dict[int, float] = {}


def reset_route_backoff() -> None:
    _tcp_failures.clear()
    _tcp_retry_after.clear()
    _tcp_connecting.clear()
    _media_cf_retry_after.clear()
    _media_cf_plain_until.clear()


class CryptoCtx:
    __slots__ = ('clt_dec', 'clt_enc', 'tg_enc', 'tg_dec')

    def __init__(self, clt_dec, clt_enc, tg_enc, tg_dec):
        self.clt_dec = clt_dec  # decrypt from client
        self.clt_enc = clt_enc  # encrypt to client
        self.tg_enc = tg_enc    # encrypt to telegram
        self.tg_dec = tg_dec    # decrypt from telegram


class MsgSplitter:
    """
    Splits TCP stream data into individual MTProto transport packets
    so each can be sent as a separate WS frame.
    """
    __slots__ = ('_proto', '_cipher_buf', '_plain_buf', '_disabled')

    def __init__(self, proto_int: int):
        self._proto = proto_int
        self._cipher_buf = bytearray()
        self._plain_buf = bytearray()
        self._disabled = False

    def split(self, chunk: bytes, plain: bytes) -> List[bytes]:
        if not chunk:
            return []
        if self._disabled:
            return [chunk]

        self._cipher_buf.extend(chunk)
        self._plain_buf.extend(plain)

        parts = []
        offset = 0
        buf_len = len(self._cipher_buf)
        while offset < buf_len:
            packet_len = self._next_packet_len(offset, buf_len - offset)
            if packet_len is None:
                break
            if packet_len <= 0:
                parts.append(bytes(self._cipher_buf) if offset == 0 else bytes(self._cipher_buf[offset:]))
                offset = buf_len
                self._disabled = True
                break
            if offset == 0 and packet_len == buf_len:
                parts.append(bytes(self._cipher_buf))
            else:
                parts.append(bytes(self._cipher_buf[offset:offset + packet_len]))
            offset += packet_len

        if offset:
            del self._cipher_buf[:offset]
            del self._plain_buf[:offset]
        return parts

    def flush(self) -> List[bytes]:
        if not self._cipher_buf:
            return []
        tail = bytes(self._cipher_buf)
        self._cipher_buf.clear()
        self._plain_buf.clear()
        return [tail]

    def _next_packet_len(self, offset: int, avail: int) -> Optional[int]:
        if avail <= 0:
            return None
        if self._proto == PROTO_ABRIDGED_INT:
            return self._next_abridged_len(offset, avail)
        if self._proto in (PROTO_INTERMEDIATE_INT,
                           PROTO_PADDED_INTERMEDIATE_INT):
            return self._next_intermediate_len(offset, avail)
        return 0

    def _next_abridged_len(self, offset: int, avail: int) -> Optional[int]:
        first = self._plain_buf[offset]
        if first in (0x7F, 0xFF):
            if avail < 4:
                return None
            payload_len = int.from_bytes(
                self._plain_buf[offset + 1:offset + 4], 'little') * 4
            header_len = 4
        else:
            payload_len = (first & 0x7F) * 4
            header_len = 1
        if payload_len <= 0:
            return 0
        packet_len = header_len + payload_len
        if avail < packet_len:
            return None
        return packet_len

    def _next_intermediate_len(self, offset: int, avail: int) -> Optional[int]:
        if avail < 4:
            return None
        payload_len = _st_I_le.unpack_from(self._plain_buf, offset)[0] & 0x7FFFFFFF
        if payload_len <= 0:
            return 0
        packet_len = 4 + payload_len
        if avail < packet_len:
            return None
        return packet_len


async def do_fallback(reader, writer, relay_init, label,
                       dc: int, is_test_dc: bool, is_media: bool, media_tag: str,
                       ctx: CryptoCtx, splitter=None, *, h2_pool=None, proto_tag=None,
                       try_direct=None):
    ip_table = DC_TEST_IPS if is_test_dc else DC_DEFAULT_IPS
    fallback_dst = ip_table.get(dc)
    use_cf = proxy_config.fallback_cfproxy and not is_test_dc
    worker_domains = proxy_config.cfproxy_worker_domains

    methods: List[str] = []

    if worker_domains and fallback_dst:
        methods.append('cf_worker')
    if use_cf and is_media and h2_pool is not None and proto_tag is not None:
        methods.append('h2')
    if try_direct is not None:
        methods.append('direct')
    if use_cf:
        methods.append('cf')
    if fallback_dst:
        methods.append('tcp')

    for method in methods:
        if method == 'cf_worker' and fallback_dst:
            ok = await _cfproxy_worker_fallback(
                reader, writer, relay_init, label, ctx,
                dc=dc, is_test_dc=is_test_dc, is_media=is_media,
                fallback_dst=fallback_dst, splitter=splitter)
            if ok:
                return True
        elif method == 'h2':
            # Media relay-first must still use Flowseal's HTTP transport.
            # A successful CF WebSocket upgrade does not guarantee that
            # the relay will deliver file requests. Setup is bounded by
            # CfH2Pool; if unavailable, try direct WS before CF WS.
            channel = await h2_pool.open(dc, label)
            if channel is not None:
                media_log.info("Telegram Desktop media DC%d: CF HTTP/2", dc)
                stats.connections_h2 += 1
                stats.connections_cfproxy += 1
                await bridge_h2(reader, writer, channel, ctx, proto_tag)
                return True
        elif method == 'cf':
            ok = await _cfproxy_fallback(
                reader, writer, relay_init, label, ctx,
                dc=dc, is_media=is_media,
                splitter=splitter)
            if ok:
                return True
        elif method == 'direct':
            if await try_direct():
                return True
        elif method == 'tcp' and fallback_dst:
            ok = await _tcp_fallback(
                reader, writer, fallback_dst, 443,
                relay_init, label, ctx, media_dc=dc if is_media else None)
            if ok:
                return True
    return False


async def _cfproxy_worker_fallback(reader, writer, relay_init, label,
                                   ctx: CryptoCtx,
                                   dc: int, is_test_dc: bool, is_media: bool,
                                   fallback_dst: str,
                                   splitter=None):
    media_tag = ' media' if is_media else ''
    worker_domains = proxy_config.cfproxy_worker_domains
    if not worker_domains:
        return False

    pooled = None if is_test_dc else await cf_worker_pool.get(
        dc, fallback_dst, worker_domains)
    if pooled:
        ws, worker_domain = pooled
        log.info("[%s] DC%d%s -> CF worker pool hit via %s for %s",
                 label, dc, media_tag, worker_domain, fallback_dst)
    else:
        query = urlencode({
            'dst': fallback_dst,
            'dc': str(dc),
        })
        path = f'/apiws?{query}'

        ws = None
        for worker_domain in cf_worker_pool.available_domains(worker_domains):
            log.info("[%s] DC%d%s -> trying CF worker %s for %s",
                     label, dc, media_tag, worker_domain, fallback_dst)

            try:
                ws = await RawWebSocket.connect(worker_domain, worker_domain,
                                                timeout=10.0, path=path,
                                                secure=not proxy_config.disable_secure)
                break
            except Exception as exc:
                cf_worker_pool.report_failure(worker_domain, exc)
                log.warning("[%s] DC%d%s CF worker %s failed: %s",
                            label, dc, media_tag, worker_domain, repr(exc))
                continue

        if ws is None:
            return False

    if not await send_ws_relay_init(ws, relay_init):
        return False
    stats.connections_cfproxy += 1
    await bridge_ws_reencrypt(reader, writer, ws, label, ctx,
                              dc=dc, is_media=is_media,
                              splitter=None)
    return True


async def _cfproxy_fallback(reader, writer, relay_init, label,
                            ctx: CryptoCtx,
                            dc: int, is_media: bool,
                            splitter=None):
    media_tag = ' media' if is_media else ''
    ws = None
    chosen_domain = None
    chosen_secure = not proxy_config.disable_secure

    log.info("[%s] DC%d%s -> trying CF proxy",
            label, dc, media_tag)
    connect_started = time.monotonic()

    loop = asyncio.get_running_loop()
    if is_media and loop.time() < _media_cf_retry_after.get(dc, 0):
        return False
    secure_modes = (not proxy_config.disable_secure,)
    if is_media and not proxy_config.disable_secure:
        # Some networks block CF TLS while the same MTProto WS relay is
        # reachable on port 80. MTProto payloads remain encrypted; only the
        # outer TLS layer is absent. Leave message/direct/H2 transports
        # untouched and periodically retry TLS.
        secure_modes = ((False, True) if loop.time() < _media_cf_plain_until.get(dc, 0)
                        else (True, False))
    deadline = loop.time() + CF_WS_SETUP_TIMEOUT
    for base_domain in balancer.get_domains_for_dc(dc):
        domain = f'kws{dc}.{base_domain}'
        for secure in secure_modes:
            remaining = deadline - loop.time()
            if remaining <= 0:
                break
            try:
                timeout = min(remaining, CF_WS_ATTEMPT_TIMEOUT)
                candidate = await asyncio.wait_for(
                    RawWebSocket.connect(domain, domain, timeout=timeout, secure=secure),
                    timeout,
                )
                remaining = deadline - loop.time()
                if not await send_ws_relay_init(candidate, relay_init, timeout=remaining):
                    continue
                ws = candidate
                chosen_domain = base_domain
                chosen_secure = secure
                break
            except Exception as exc:
                log.warning("[%s] DC%d%s CF proxy port %d failed: %s",
                            label, dc, media_tag, 443 if secure else 80, repr(exc))
        if ws is not None or loop.time() >= deadline:
            break

    if ws is None:
        if is_media:
            _media_cf_retry_after[dc] = loop.time() + CF_WS_RETRY_DELAY
        return False

    if is_media:
        _media_cf_retry_after.pop(dc, None)
        if chosen_secure:
            _media_cf_plain_until.pop(dc, None)
        elif not proxy_config.disable_secure and secure_modes[0]:
            _media_cf_plain_until[dc] = loop.time() + CF_WS_RETRY_DELAY
    log.debug('[%s] WS CONNECT DC%d%s route=cf setup_ms=%.0f',
              label, dc, media_tag, (time.monotonic() - connect_started) * 1000)
    if is_media:
        media_log.info("Telegram Desktop media DC%d: CF WebSocket port %d",
                       dc, 443 if chosen_secure else 80)
    if chosen_domain and balancer.update_domain_for_dc(dc, chosen_domain):
        log.info("[%s] Switched active CF domain", label)

    stats.connections_cfproxy += 1
    up, down = await bridge_ws_reencrypt(
        reader, writer, ws, label, ctx, dc=dc, is_media=is_media, splitter=splitter,
        first_reply_timeout=CF_MEDIA_FIRST_REPLY_TIMEOUT if is_media else None,
    )
    if is_media and up and not down:
        # A successful WS upgrade can still lead to a dead relay. Let
        # Desktop reconnect on another route; never replay encrypted data.
        _media_cf_retry_after[dc] = loop.time() + CF_WS_RETRY_DELAY
    return True


async def send_ws_relay_init(ws, relay_init, *, timeout=RELAY_INIT_TIMEOUT) -> bool:
    """Don't consume native payload before an upstream is ready."""
    ready = False
    try:
        await asyncio.wait_for(ws.send(relay_init), timeout)
        ready = True
        return True
    except (OSError, asyncio.TimeoutError):
        return False
    finally:
        if not ready:
            # An incomplete handshake isn't a live WebSocket session.
            ws.writer.transport.abort()


async def _tcp_fallback(reader, writer, dst, port, relay_init, label, ctx: CryptoCtx, *, media_dc=None):
    key = (dst, port)
    if key in _tcp_connecting or time.monotonic() < _tcp_retry_after.get(key, 0):
        log.debug("[%s] TCP fallback to %s:%d skipped (backoff or connecting)",
                  label, dst, port)
        return False

    _tcp_connecting.add(key)
    rw = None
    try:
        try:
            log.info("[%s] TCP fallback to %s:%d", label, dst, port)
            rr, rw = await asyncio.wait_for(
                asyncio.open_connection(dst, port), timeout=10)
            rw.write(relay_init)
            await asyncio.wait_for(rw.drain(), RELAY_INIT_TIMEOUT)
        except Exception as exc:
            failures = _tcp_failures.get(key, 0) + 1
            _tcp_failures[key] = failures
            delay = min(TCP_BACKOFF_INITIAL * 2 ** min(failures - 1, 7),
                        TCP_BACKOFF_MAX)
            _tcp_retry_after[key] = time.monotonic() + delay
            log.warning("[%s] TCP fallback to %s:%d failed: %r; retry in %.0fs",
                        label, dst, port, exc, delay)
            return False
        finally:
            _tcp_connecting.discard(key)

        _tcp_failures.pop(key, None)
        _tcp_retry_after.pop(key, None)
        stats.connections_tcp_fallback += 1
        if media_dc is not None:
            media_log.info("Telegram Desktop media DC%d: TCP", media_dc)
        await _bridge_tcp_reencrypt(reader, writer, rr, rw, label, ctx)
        return True
    finally:
        if rw is not None:
            await close_stream(rw)


async def bridge_ws_reencrypt(reader, writer, ws: RawWebSocket, label,
                               ctx: CryptoCtx,
                               dc=None, is_media=False,
                               splitter: Optional[MsgSplitter] = None, *,
                               first_reply_timeout=None):
    """
    Bidirectional TCP(client) <-> WS(telegram) with re-encryption.
    client ciphertext → decrypt(clt_key) → encrypt(tg_key) → WS
    WS data → decrypt(tg_key) → encrypt(clt_key) → client TCP
    """
    dc_tag = f"DC{dc}{'m' if is_media else ''}" if dc else "DC?"

    up_bytes = 0
    down_bytes = 0
    up_packets = 0
    down_packets = 0
    start_time = asyncio.get_running_loop().time()
    close_reason = 'normal'
    activity = WsActivity(label, dc_tag) if log.isEnabledFor(logging.DEBUG) else None
    first_upload = asyncio.Event() if first_reply_timeout is not None else None
    first_download = asyncio.Event() if first_reply_timeout is not None else None

    async def tcp_to_ws():
        nonlocal up_bytes, up_packets, close_reason
        try:
            while True:
                chunk = await reader.read(65536)
                if not chunk:
                    if splitter:
                        tail = splitter.flush()
                        if tail:
                            if activity is not None:
                                activity.send_started()
                            await asyncio.wait_for(ws.send(tail[0]), STREAM_CLOSE_TIMEOUT)
                            if activity is not None:
                                activity.sent(len(tail[0]))
                    break
                n = len(chunk)
                if activity is not None:
                    activity.input(n)
                stats.bytes_up += n
                up_bytes += n
                up_packets += 1
                plain = ctx.clt_dec.update(chunk)
                chunk = ctx.tg_enc.update(plain)
                if splitter:
                    parts = splitter.split(chunk, plain)
                    if not parts:
                        continue
                    if first_upload is not None:
                        first_upload.set()
                    if activity is not None:
                        activity.send_started()
                    if len(parts) > 1:
                        await ws.send_batch(parts)
                    else:
                        await ws.send(parts[0])
                    if activity is not None:
                        activity.sent(sum(map(len, parts)))
                else:
                    if first_upload is not None:
                        first_upload.set()
                    if activity is not None:
                        activity.send_started()
                    await ws.send(chunk)
                    if activity is not None:
                        activity.sent(len(chunk))
        except asyncio.CancelledError:
            return
        except (ConnectionError, OSError) as e:
            close_reason = f"client: {type(e).__name__}"
        except Exception as e:
            close_reason = f"client: {type(e).__name__}: {e}"
            log.debug("[%s] tcp->ws ended: %s", label, e)

    async def ws_to_tcp():
        nonlocal down_bytes, down_packets, close_reason
        try:
            while True:
                data = await ws.recv()
                if data is None:
                    if close_reason == 'normal':
                        close_reason = 'upstream: ws_close'
                    break
                n = len(data)
                if n and first_download is not None:
                    first_download.set()
                if activity is not None:
                    activity.received(n)
                stats.bytes_down += n
                down_bytes += n
                down_packets += 1
                plain = ctx.tg_dec.update(data)
                data = ctx.clt_enc.update(plain)
                writer.write(data)
                await writer.drain()
                if activity is not None:
                    activity.delivered(n)
        except asyncio.CancelledError:
            return
        except (ConnectionError, OSError) as e:
            close_reason = f"upstream: {type(e).__name__}"
        except asyncio.IncompleteReadError:
            close_reason = 'upstream: tcp_reset'
        except Exception as e:
            close_reason = f"upstream: {type(e).__name__}: {e}"
            log.debug("[%s] ws->tcp ended: %s", label, e)

    tasks = [asyncio.create_task(tcp_to_ws()),
             asyncio.create_task(ws_to_tcp())]
    if first_upload is not None:
        async def wait_first_reply():
            nonlocal close_reason
            await first_upload.wait()
            try:
                await asyncio.wait_for(first_download.wait(), first_reply_timeout)
            except asyncio.TimeoutError:
                close_reason = "upstream: first media reply timeout"
            else:
                # Once the first response arrives, normal Desktop retry
                # and idle handling apply.
                await asyncio.Future()
        tasks.append(asyncio.create_task(wait_first_reply()))
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            if activity is not None:
                activity.close()
            elapsed = asyncio.get_running_loop().time() - start_time
            log.info("[%s] %s WS session closed (%s): "
                     "^%s (%d pkts) v%s (%d pkts) in %.1fs",
                     label, dc_tag, close_reason,
                     human_bytes(up_bytes), up_packets,
                     human_bytes(down_bytes), down_packets,
                     elapsed)
            if is_media and up_bytes:
                media_log.info("Telegram Desktop media DC%d: sent=%d received=%d elapsed=%.1fs",
                               dc, up_bytes, down_bytes, elapsed)
            await ws.close()
    return up_bytes, down_bytes


async def _bridge_tcp_reencrypt(reader, writer, remote_reader, remote_writer,
                                label, ctx: CryptoCtx):
    """Bidirectional TCP <-> TCP with re-encryption."""

    async def forward(src, dst_w, is_up):
        try:
            while True:
                data = await src.read(65536)
                if not data:
                    break
                n = len(data)
                if is_up:
                    stats.bytes_up += n
                    plain = ctx.clt_dec.update(data)
                    data = ctx.tg_enc.update(plain)
                else:
                    stats.bytes_down += n
                    plain = ctx.tg_dec.update(data)
                    data = ctx.clt_enc.update(plain)
                dst_w.write(data)
                await dst_w.drain()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.debug("[%s] forward ended: %s", label, e)

    tasks = [
        asyncio.create_task(forward(reader, remote_writer, True)),
        asyncio.create_task(forward(remote_reader, writer, False)),
    ]
    try:
        await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    finally:
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
