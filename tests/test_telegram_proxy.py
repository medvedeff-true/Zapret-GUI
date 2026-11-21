import socket
import unittest
from unittest.mock import AsyncMock, patch

from tg_ws_proxy_vendor.proxy import __version__, tg_ws_proxy
from zapret_gui.telegram_proxy import TelegramProxyController, TelegramProxyError


class TelegramProxyTests(unittest.TestCase):
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
