import unittest
from pathlib import Path
import tempfile
from unittest.mock import patch

from zapret_gui.ai_dns import GROUPS, RelaySelection, classify_response, parse_bundle, select_relays, summary
from zapret_gui.hosts_transaction import atomic_write


class AiDnsRelaySelectionTests(unittest.TestCase):
    @staticmethod
    def complete(ip="1.1.1.1"):
        return "".join(f"{ip} {host}\n" for group in GROUPS.values() if group.required
                       for host in group.probes)

    def test_incremental_recovery_never_reprobes_or_replaces_good_groups(self):
        calls = []
        def probe(ip, host):
            calls.append((ip, host))
            return {"ok": not (ip == "1.1.1.1" and host == "gemini.google.com")}
        selector = RelaySelection(probe=probe)
        selector.add([("last-known-good", self.complete())])
        self.assertEqual({"gemini"}, selector.missing)
        before = list(calls)
        text, status = selector.add([("new-provider", self.complete("8.8.8.8"))])
        self.assertEqual([("8.8.8.8", "gemini.google.com")], calls[len(before):])
        self.assertIn("1.1.1.1 chatgpt.com", text)
        self.assertIn("8.8.8.8 gemini.google.com", text)
        self.assertEqual("last-known-good", status["openai"]["source"])
        self.assertEqual("full", summary(status))
        selector.add([("same-bytes-different-source", self.complete())])
        self.assertEqual(len(before) + 1, len(calls))

    def test_duplicate_failed_candidate_is_not_retried_on_next_stage(self):
        calls = []
        selector = RelaySelection(probe=lambda ip, host: calls.append((ip, host)) or {"ok": False})
        selector.add([("cache", self.complete())])
        before = len(calls)
        _, status = selector.add([("download", self.complete())])
        self.assertEqual(before, len(calls))
        self.assertEqual("cache", status["gemini"]["source"])

    def test_all_geohide_addresses_are_retained(self):
        ips = ["1.1.1.1", "8.8.8.8", "9.9.9.9", "4.4.4.4", "5.5.5.5", "6.6.6.6", "7.7.7.7"]
        bundle = "".join(f"{ip} gemini.google.com\n" for ip in ips)
        text, status = select_relays([("geohide", bundle)], groups={"gemini"},
                                    probe=lambda ip, host: {"ok": ip == ips[-1]})
        self.assertEqual("7.7.7.7 gemini.google.com\n", text)
        self.assertEqual("ok", status["gemini"]["status"])

    def test_google_denial_and_redirect_classification(self):
        for code, location, body, error in [
            (403, "", b"Forbidden", "google-access-denied"),
            (200, "", b"Gemini is not available in your country", "google-region-blocked"),
            (302, "https://google.com/sorry/index", b"", "google-challenge-or-region"),
            (200, "", b"recaptcha", "google-captcha"),
            (503, "", b"", "google-upstream-unavailable"),
            (302, "https://evil.example/login", b"", "google-unexpected-redirect"),
            (302, "https://accounts.google.com/ServiceLogin", b"", ""),
            (200, "", b"Gemini", ""),
            (200, "", b"Proxy is running", "google-unexpected-page"),
        ]:
            with self.subTest(code=code, location=location, body=body):
                self.assertEqual(error, classify_response("gemini.google.com", code, location, body))
        self.assertEqual("google-region-blocked", classify_response(
            "gemini.google.com", 200, body=b"User location is not supported"))

    def test_gemini_web_does_not_require_studio_or_api_to_succeed(self):
        selector = RelaySelection(probe=lambda ip, host: {"ok": host == "gemini.google.com"})
        text, status = selector.add([("source", self.complete())])
        self.assertIn("gemini.google.com", text)
        self.assertNotIn("aistudio.google.com", text)
        self.assertEqual("ok", status["gemini"]["status"])
        self.assertEqual("unavailable", status["google_studio"]["status"])

    def test_studio_only_last_good_is_valid(self):
        import EzUnBlock as app
        self.assertTrue(app._hosts_bundle_looks_useful("1.1.1.1 aistudio.google.com\n"))

    def test_verified_local_state_needs_no_network_source_download(self):
        import EzUnBlock as app
        with (
            patch.object(app, "_ai_dns_fallback_profiles", return_value=[("last-known-good", self.complete())]),
            patch("zapret_gui.ai_dns.probe_relay", return_value={"ok": True}),
            patch.object(app._ai_dns_sources, "load_profiles", return_value=[]),
            patch.object(app, "_download_ai_hosts_bundle") as malw,
            patch.object(app._ai_dns_sources, "download_hosts") as hosts,
            patch.object(app._ai_dns_sources, "download_doh", return_value=[]) as doh,
            patch.object(app, "_download_ai_dns_previous_profiles") as history,
        ):
            text, status = app._resolve_ai_dns_profiles("")
        self.assertTrue(text)
        self.assertEqual("full", summary(status))
        for mock in (malw, hosts, doh, history):
            mock.assert_not_called()

    def test_history_recovers_only_failed_group_when_others_are_working(self):
        import EzUnBlock as app
        with (
            patch.object(app, "_ai_dns_fallback_profiles", return_value=[("last-known-good", self.complete())]),
            patch("zapret_gui.ai_dns.probe_relay",
                  side_effect=lambda ip, host, **kw: {"ok": ip == "8.8.8.8" or host != "gemini.google.com"}),
            patch.object(app, "_download_ai_hosts_bundle", side_effect=RuntimeError("offline")),
            patch.object(app._ai_dns_sources, "load_profiles", return_value=[]),
            patch.object(app._ai_dns_sources, "save_profiles"),
            patch.object(app._ai_dns_sources, "download_hosts", return_value=[]),
            patch.object(app._ai_dns_sources, "download_doh", return_value=[]),
            patch.object(app, "_download_ai_dns_previous_profiles",
                         return_value=[("history", "8.8.8.8 gemini.google.com\n")]) as history,
        ):
            text, status = app._resolve_ai_dns_profiles("")
        history.assert_called_once()
        self.assertIn("8.8.8.8 gemini.google.com", text)
        self.assertEqual("last-known-good", status["openai"]["source"])

    def test_provider_snapshots_merge_partial_refresh_and_keep_previous(self):
        from zapret_gui.ai_dns_sources import save_profiles, load_profiles
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            save_profiles(path, [("dns-ai", "1.1.1.1 gemini.google.com\n8.8.8.8 chatgpt.com\n")])
            save_profiles(path, [("dns-ai", "9.9.9.9 gemini.google.com\n")])
            profiles = load_profiles(path)
            self.assertEqual(2, len(profiles))
            self.assertIn("8.8.8.8 chatgpt.com", profiles[0][1])
            self.assertIn("9.9.9.9 gemini.google.com", profiles[0][1])
            self.assertIn("1.1.1.1 gemini.google.com", profiles[1][1])
            self.assertFalse(list(Path(directory).glob("*.tmp")))

    def test_doh_rejects_unrelated_and_private_answers(self):
        import dns.message
        import dns.rrset
        from zapret_gui.ai_dns_sources import query_doh
        def answer(client, method, url, **kw):
            query = dns.message.from_wire(kw["content"])
            response = dns.message.make_response(query)
            response.answer.extend([
                dns.rrset.from_text("gemini.google.com.", 60, "IN", "CNAME", "relay.example."),
                dns.rrset.from_text("relay.example.", 60, "IN", "A", "8.8.8.8", "127.0.0.1"),
                dns.rrset.from_text("unrelated.example.", 60, "IN", "A", "9.9.9.9"),
            ])
            return response.to_wire()
        with patch("zapret_gui.ai_dns_sources._body", side_effect=answer):
            self.assertEqual(["8.8.8.8"], query_doh(None, "https://provider.example/dns-query", "gemini.google.com"))

    def test_corrupt_provider_cache_is_ignored(self):
        from zapret_gui.ai_dns_sources import load_profiles, save_profiles
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sources.json"
            for data in (
                b"broken json", b"[]",
                b'{"dns-ai":[{},{"hosts":42}],"unexpected":[{"hosts":"8.8.8.8 gemini.google.com"}]}',
            ):
                path.write_bytes(data)
                self.assertEqual([], load_profiles(path))
            save_profiles(path, [("dns-ai", "8.8.8.8 gemini.google.com\n")])
            self.assertEqual(1, len(load_profiles(path)))

    def test_dead_hosts_source_does_not_hide_other_regions(self):
        from zapret_gui.ai_dns_sources import download_hosts
        def fetch(client, method, url, **kw):
            if "/eu/" in url:
                raise TimeoutError("offline")
            return b"8.8.8.8 gemini.google.com\n1.1.1.1 chatgpt.com\n127.0.0.1 gemini.google.com\n"
        with patch("zapret_gui.ai_dns_sources._body", side_effect=fetch):
            profiles = download_hosts({"gemini"})
        self.assertEqual(["geohide-ru", "geohide-us"], [label for label, _ in profiles])
        self.assertTrue(all(text == "8.8.8.8 gemini.google.com\n" for _, text in profiles))

    def test_doh_queries_only_failed_service_and_survives_dead_provider(self):
        from zapret_gui.ai_dns_sources import download_doh
        from unittest.mock import MagicMock
        calls = []
        def query(client, url, host):
            calls.append((url, host))
            if "dns-ai.ru" in url:
                raise TimeoutError("offline")
            return ["8.8.8.8"]
        with (
            patch("zapret_gui.ai_dns_sources.query_doh", side_effect=query),
            patch("zapret_gui.ai_dns_sources.httpx.Client", return_value=MagicMock()),
        ):
            profiles = download_doh({"gemini"})
        self.assertTrue(profiles)
        self.assertNotIn("dns-ai", [label for label, _ in profiles])
        self.assertEqual({"gemini.google.com", "geminiweb-pa.clients6.google.com",
                          "geminiweb-pa.clients.google.com"}, {host for _, host in calls})

    def test_disabled_api_is_not_parsed_probed_or_reported_even_from_old_cache(self):
        from zapret_gui.ai_dns_sources import download_doh
        calls = []
        selector = RelaySelection(probe=lambda ip, host: calls.append(host) or {"ok": True})
        text, status = selector.add([("old-last-good", self.complete() +
                                    "1.1.1.1 generativelanguage.googleapis.com\n")])
        self.assertNotIn("google_api", status)
        self.assertNotIn("generativelanguage.googleapis.com", text)
        self.assertNotIn("generativelanguage.googleapis.com", calls)
        self.assertEqual([], download_doh({"google_api"}))

    def test_google_frontend_ips_from_user_screenshot_are_not_relays(self):
        from zapret_gui.ai_dns import is_direct_google, probe_relay
        ips = ["142.251.150.2", "142.250.178.106", "173.194.221.138", "64.233.162.100",
               "2607:f8b0:4005:805::200e"]
        with patch("zapret_gui.ai_dns.socket.socket") as connect:
            for ip in ips:
                self.assertTrue(is_direct_google(ip, "gemini.google.com"))
                result = probe_relay(ip, "gemini.google.com")
                self.assertFalse(result["ok"])
                self.assertEqual("google-direct-not-relay", result["error"])
        connect.assert_not_called()
        # Do not broadly ban cloud tenants, Microsoft-hosted relays, etc.
        for ip in ["194.110.174.251", "48.102.233.174", "34.1.2.3"]:
            self.assertFalse(is_direct_google(ip, "gemini.google.com"))

    def test_poisoned_last_good_direct_google_is_replaced_not_accepted(self):
        calls = []
        selector = RelaySelection(probe=lambda ip, host: calls.append((ip, host)) or {"ok": True})
        _, status = selector.add([("last-known-good", "142.251.150.2 gemini.google.com\n")])
        self.assertEqual("unavailable", status["gemini"]["status"])
        text, status = selector.add([("real-relay", "194.110.174.251 gemini.google.com\n")])
        self.assertEqual("real-relay", status["gemini"]["source"])
        self.assertNotIn("142.251.", text)
        self.assertEqual([("194.110.174.251", "gemini.google.com")], calls)

    def test_direct_google_rpc_invalidates_relay_frontend_mapping(self):
        _, status = select_relays([("mixed", "194.110.174.251 gemini.google.com\n"
                                   "173.194.221.138 geminiweb-pa.clients6.google.com\n")],
                                  groups={"gemini"}, probe=lambda ip, host: {"ok": ip == "194.110.174.251"})
        # Uniform real-relay alternative may be selected only after rechecking
        # RPC on that relay, never the original direct RPC mapping.
        self.assertNotIn("173.194.", status["gemini"].get("relay", ""))

    def test_studio_rpc_is_checked_even_on_same_ip_as_frontend(self):
        text, status = select_relays([("relay", "194.110.174.251 aistudio.google.com\n"
                                     "194.110.174.251 alkalimakersuite-pa.clients6.google.com\n"
                                     "194.110.174.251 webchannel-alkalimakersuite-pa.clients6.google.com\n")],
                                     groups={"google_studio"},
                                     probe=lambda ip, host: {"ok": host == "aistudio.google.com"})
        self.assertEqual("", text)
        self.assertEqual("unavailable", status["google_studio"]["status"])
        self.assertEqual(3, len(status["google_studio"]["checks"]))

    def test_doh_direct_google_answers_are_not_saved_as_relay_candidates(self):
        import dns.message
        import dns.rrset
        from zapret_gui.ai_dns_sources import query_doh
        def answer(client, method, url, **kw):
            query = dns.message.from_wire(kw["content"])
            response = dns.message.make_response(query)
            response.answer.append(dns.rrset.from_text(
                "gemini.google.com.", 60, "IN", "A", "142.251.150.2", "194.110.174.251"))
            return response.to_wire()
        with patch("zapret_gui.ai_dns_sources._body", side_effect=answer):
            self.assertEqual(["194.110.174.251"],
                             query_doh(None, "https://resolver.example/dns-query", "gemini.google.com"))

    def test_retired_api_status_is_hidden_when_loading_older_settings(self):
        import EzUnBlock as app
        from PyQt6.QtCore import QSettings
        import json
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            settings.setValue(app.DNS_MALW_GROUP_STATUS_KEY, json.dumps({
                "google_api": {"status": "unavailable"}, "gemini": {"status": "ok"},
            }))
            self.assertEqual({"gemini": {"status": "ok"}}, app._load_dns_malw_group_status(settings))

    def test_probes_are_concurrent_even_for_one_service(self):
        import threading
        barrier = threading.Barrier(4, timeout=2)
        ips = ["1.1.1.1", "8.8.8.8", "9.9.9.9", "4.4.4.4"]
        def probe(ip, host):
            barrier.wait()
            return {"ok": ip == ips[-1]}
        text, status = select_relays([("provider", "".join(f"{ip} gemini.google.com\n" for ip in ips))],
                                    groups={"gemini"}, probe=probe)
        self.assertEqual("4.4.4.4 gemini.google.com\n", text)
        self.assertEqual("ok", status["gemini"]["status"])

    def test_expired_check_budget_does_not_start_sockets(self):
        import time
        calls = []
        text, status = select_relays([("provider", "8.8.8.8 gemini.google.com\n")],
                                    groups={"gemini"}, deadline=time.monotonic() - 1,
                                    probe=lambda *pair: calls.append(pair) or {"ok": True})
        self.assertEqual([], calls)
        self.assertEqual("", text)
        self.assertEqual("unavailable", status["gemini"]["status"])

    def test_invalid_malw_api_data_tries_live_mirror_before_seed(self):
        import EzUnBlock as app
        from unittest.mock import MagicMock
        session = MagicMock()
        response = session.get.return_value.__enter__.return_value
        response.iter_content.return_value = [self.complete().encode("utf-8")]
        with (
            patch.object(app.requests, "Session", return_value=session),
            patch.object(app, "_download_github_contents_bytes", return_value=b"<html>unavailable</html>"),
            patch.object(app, "_load_dns_malw_seed_hosts") as seed,
            patch.object(app, "_write_hosts_file", side_effect=PermissionError("cache read-only")),
        ):
            text, version = app._download_ai_hosts_bundle()
        self.assertIn("gemini.google.com", text)
        self.assertEqual("", version)
        seed.assert_not_called()
        self.assertTrue(session.get.call_args.kwargs["stream"])

    def test_cached_optional_group_is_recovered_even_if_required_local_groups_work(self):
        import EzUnBlock as app
        with (
            patch.object(app, "_ai_dns_fallback_profiles", return_value=[("last-known-good", self.complete())]),
            patch("zapret_gui.ai_dns.probe_relay", side_effect=lambda ip, host, **kw: {"ok": ip != "9.9.9.9"}),
            patch.object(app._ai_dns_sources, "load_profiles",
                         return_value=[("cached-dns-ai-0", "9.9.9.9 grok.com\n")]),
            patch.object(app._ai_dns_sources, "save_profiles"),
            patch.object(app, "_download_ai_hosts_bundle", return_value=("", "")),
            patch.object(app._ai_dns_sources, "download_hosts",
                         return_value=[("geohide-eu", "8.8.8.8 grok.com\n")]) as hosts,
            patch.object(app._ai_dns_sources, "download_doh", return_value=[]) as doh,
        ):
            text, status = app._resolve_ai_dns_profiles("")
        hosts.assert_called_once_with({"grok"})
        doh.assert_called_once_with({"grok"})
        self.assertIn("8.8.8.8 grok.com", text)
        self.assertEqual("last-known-good", status["gemini"]["source"])

    def test_last_good_updated_only_after_successful_service_publication(self):
        import EzUnBlock as app
        from PyQt6.QtCore import QSettings
        for service_ok in (False, True):
            with self.subTest(service_ok=service_ok), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                (root / "core" / "bin").mkdir(parents=True)
                helper = root / "ZapretGUI.Service.exe"
                helper.touch()
                path = root / "hosts"
                path.write_text("127.0.0.1 localhost\n", encoding="utf-8")
                settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
                selected = "8.8.8.8 gemini.google.com\n"
                with (
                    patch.object(app, "APP_DIR", str(root)),
                    patch.object(app, "DNS_MALW_HOSTS_PATH", str(path)),
                    patch.object(app, "_bundled_path", return_value=str(helper)),
                    patch.object(app, "_read_hosts_file_strict", return_value=path.read_text()),
                    patch.object(app, "_save_dns_malw_backup_if_safe", return_value=path.read_text()),
                    patch.object(app, "_resolve_ai_dns_profiles", return_value=(selected, {
                        "gemini": {"status": "ok"}, "openai": {"status": "unavailable"},
                    })),
                    patch.object(app._bypass_service, "ai_dns_hosts",
                                 return_value={"ok": service_ok, "error": "test-publish-failed"}) as publish,
                    patch.object(app, "_run_hidden"),
                    patch.object(app, "_save_dns_malw_last_good") as save_good,
                ):
                    result = app._enable_dns_malw_link(settings)
                self.assertEqual(service_ok, result["ok"])
                self.assertIn("127.0.0.1 localhost", publish.call_args.args[0])
                self.assertIn(selected, publish.call_args.args[0])
                if service_ok:
                    save_good.assert_called_once_with(selected)
                else:
                    save_good.assert_not_called()

    def test_cached_and_seed_profiles_are_available_independently(self):
        import EzUnBlock as app
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "cache.txt"
            seed = root / "seed.txt"
            cache.write_text("1.1.1.1 chatgpt.com\n", encoding="utf-8")
            seed.write_text("8.8.8.8 gemini.google.com\n", encoding="utf-8")
            with (
                patch.object(app, "_load_dns_malw_last_good", return_value=""),
                patch.object(app, "_extract_dns_malw_hosts_block_body", return_value=""),
                patch.object(app, "_hosts_bundle_looks_useful", side_effect=lambda text: bool(text.strip())),
                patch.object(app, "DNS_MALW_HOSTS_CACHE_PATH", str(cache)),
                patch.object(app, "DNS_MALW_HOSTS_SEED_PATH", str(seed)),
                patch.object(app, "_bundled_path", return_value=str(seed)),
            ):
                profiles = app._ai_dns_fallback_profiles("")
            self.assertEqual(["previous-cache", "installed-seed"], [source for source, _ in profiles])
            # Source bytes have been captured before any download can overwrite the cache.
            cache.write_text("9.9.9.9 chatgpt.com\n", encoding="utf-8")
            self.assertIn("1.1.1.1", profiles[0][1])

    def test_no_working_relays_does_not_publish_hosts_or_report_permission_error(self):
        import EzUnBlock as app
        from PyQt6.QtCore import QSettings
        with tempfile.TemporaryDirectory() as directory:
            settings = QSettings(str(Path(directory) / "settings.ini"), QSettings.Format.IniFormat)
            with (
                patch.object(app, "_read_hosts_file_strict", return_value="# existing hosts\n"),
                patch.object(app, "_save_dns_malw_backup_if_safe", return_value="# existing hosts\n"),
                patch.object(app, "_resolve_ai_dns_profiles", return_value=("", {
                    "openai": {"status": "unavailable", "checks": [{"ok": False, "error": "tcp-timeout"}]},
                })),
                patch.object(app._bypass_service, "ai_dns_hosts") as publish,
            ):
                result = app._enable_dns_malw_link(settings)
            self.assertFalse(result["ok"])
            self.assertEqual("ai-no-working-relays", result["error"])
            publish.assert_not_called()

    def test_failed_profile_diagnostics_are_retained_when_fallback_is_tried(self):
        bundle = "1.1.1.1 chatgpt.com\n1.1.1.1 auth.openai.com\n1.1.1.1 api.openai.com\n"
        fallback = bundle.replace("1.1.1.1", "8.8.8.8")
        _, statuses = select_relays([("upstream", bundle), ("previous-cache", fallback)],
                                    probe=lambda *_: {"ok": False, "error": "tcp-timeout"})
        self.assertEqual(["upstream", "previous-cache"],
                         [attempt["source"] for attempt in statuses["openai"]["attempts"]])

    def test_permission_denial_has_distinct_diagnostic(self):
        from zapret_gui.ai_dns import probe_relay
        with patch("zapret_gui.ai_dns.socket.socket", side_effect=PermissionError("blocked")):
            self.assertEqual("tcp-access-denied", probe_relay("1.1.1.1", "chatgpt.com", context=object())["error"])

    def test_history_fallback_uses_only_bounded_official_commit_refs(self):
        import EzUnBlock as app
        from unittest.mock import MagicMock
        session = MagicMock()
        session.get.return_value.json.return_value = [
            {"sha": "a" * 40}, {"sha": "../../invalid"}, {"sha": "b" * 40}, {"sha": "c" * 40},
            {"sha": "d" * 40},
        ]
        with (
            patch.object(app.requests, "Session") as create,
            patch.object(app, "_download_github_contents_bytes", return_value=b"1.1.1.1 chatgpt.com\n") as fetch,
            patch.object(app, "_hosts_bundle_looks_useful", return_value=True),
        ):
            create.return_value.__enter__.return_value = session
            profiles = app._download_ai_dns_previous_profiles()
        self.assertEqual(1, len(profiles))
        self.assertEqual(["b" * 40, "c" * 40], [call.kwargs["ref"] for call in fetch.call_args_list])
        self.assertTrue(all(call.args[1:3] == ("ImMALWARE/dns.malw.link", "hosts")
                            for call in fetch.call_args_list))

    def test_selects_groups_independently_and_excludes_non_ai_entries(self):
        bundle = (
            "9.9.9.9 chatgpt.com\n"
            "9.9.9.9 auth.openai.com\n"
            "9.9.9.9 api.openai.com\n"
            "8.8.8.8 gemini.google.com\n"
            "8.8.8.8 aistudio.google.com\n"
            "8.8.8.8 generativelanguage.googleapis.com\n"
            "7.7.7.7 claude.ai\n"
            "7.7.7.7 api.anthropic.com\n"
            "0.0.0.0 ads.example\n"
        )

        def probe(ip, host):
            return {"ok": ip in {"9.9.9.9", "8.8.8.8"}}

        rendered, statuses = select_relays([("upstream", bundle)], probe=probe)
        self.assertIn("9.9.9.9 chatgpt.com", rendered)
        self.assertIn("8.8.8.8 gemini.google.com", rendered)
        self.assertNotIn("7.7.7.7 claude.ai", rendered)
        self.assertNotIn("ads.example", rendered)
        self.assertEqual("partial", summary(statuses))
        self.assertEqual("unavailable", statuses["claude"]["status"])

    def test_last_known_good_profile_is_used_only_for_failed_group(self):
        candidate = (
            "1.1.1.1 chatgpt.com\n1.1.1.1 auth.openai.com\n1.1.1.1 api.openai.com\n"
            "2.2.2.2 gemini.google.com\n2.2.2.2 aistudio.google.com\n"
            "2.2.2.2 generativelanguage.googleapis.com\n"
            "3.3.3.3 claude.ai\n3.3.3.3 api.anthropic.com\n"
        )
        last_good = (
            "3.3.3.3 chatgpt.com\n3.3.3.3 auth.openai.com\n3.3.3.3 api.openai.com\n"
            "4.4.4.4 gemini.google.com\n4.4.4.4 aistudio.google.com\n"
            "4.4.4.4 generativelanguage.googleapis.com\n"
        )

        def probe(ip, host):
            return {"ok": ip in {"3.3.3.3", "2.2.2.2"}}

        rendered, statuses = select_relays(
            [("upstream", candidate), ("last-known-good", last_good)],
            probe=probe,
        )
        self.assertIn("3.3.3.3 chatgpt.com", rendered)
        self.assertIn("2.2.2.2 gemini.google.com", rendered)
        self.assertNotIn("1.1.1.1 chatgpt.com", rendered)
        self.assertEqual("full", summary(statuses))
        self.assertEqual("last-known-good", statuses["openai"]["source"])

    def test_invalid_and_private_relays_are_not_candidates(self):
        parsed = parse_bundle(
            "192.168.1.1 chatgpt.com\n"
            "0.0.0.0 gemini.google.com\n"
            "198.51.100.10 chatgpt.com\n"
        )
        self.assertEqual({}, parsed)

    def test_no_working_groups_are_red_state(self):
        rendered, statuses = select_relays(
            [("upstream", "1.1.1.1 chatgpt.com\n1.1.1.1 auth.openai.com\n")],
            probe=lambda *_: {"ok": False},
        )
        self.assertEqual("", rendered)
        self.assertEqual("none", summary(statuses))

    def test_cache_publication_is_atomic_and_replaces_old_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "last-good.txt"
            path.write_bytes(b"old\n")
            atomic_write(path, b"new\n")
            self.assertEqual(b"new\n", path.read_bytes())
            self.assertFalse(list(Path(directory).glob(".*.tmp")))
            self.assertFalse(list(Path(directory).glob("*.rollback")))


if __name__ == "__main__":
    unittest.main()
