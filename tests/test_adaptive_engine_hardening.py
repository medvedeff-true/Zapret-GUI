from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from adaptive_strategy.engine import (
    COMBINED_VALIDATION_REQUIRED_ROUNDS,
    COMBINED_VALIDATION_ROUNDS,
    SearchEngine,
)
from adaptive_strategy.models import CandidateResult, ProbeResult, Protocol, SearchOutcome, Strategy, Target
from adaptive_strategy.probe import dns_addresses_with_deadline
from adaptive_strategy.runtime import RuntimePaths


def probe(
    target: Target,
    validator: str,
    success: bool,
    *,
    error: str = "",
) -> ProbeResult:
    return ProbeResult(
        target,
        validator,
        success,
        200 if success else None,
        0.01,
        remote_ip="203.0.113.10" if success else "",
        error=error,
    )


class BaselineHardeningTests(unittest.TestCase):
    def test_baseline_retries_only_required_failures_and_uses_retry_result(self) -> None:
        target = Target("https://example.test/a", "example.test")
        initial = [
            probe(target, "cygwin", False, error="temporary timeout"),
            probe(target, "native", False, error="SEC_E_NO_CREDENTIALS"),
        ]
        recovered = probe(target, "cygwin", True)
        engine = SearchEngine(RuntimePaths.discover())
        engine.probes.probe_many = Mock(side_effect=[initial, [recovered]])

        with (
            patch(
                "adaptive_strategy.engine.dns_addresses_with_deadline",
                return_value={target: ["203.0.113.10"]},
            ),
            patch("adaptive_strategy.engine.time.sleep", return_value=None),
        ):
            outcome = engine._run([target], {"custom": [target]})

        self.assertEqual("baseline-reachable", outcome.confidence)
        self.assertEqual(recovered, outcome.baseline[0])
        self.assertEqual(initial[1], outcome.baseline[1])
        self.assertEqual(2, engine.probes.probe_many.call_count)
        retry_requests = engine.probes.probe_many.call_args_list[1].args[0]
        self.assertEqual([(target, Protocol.HTTPS, "cygwin")], retry_requests)
        self.assertEqual({"workers": 1}, engine.probes.probe_many.call_args_list[1].kwargs)


class BaselineClassificationTests(unittest.TestCase):
    def test_https_results_are_matched_by_url_not_hostname(self) -> None:
        reachable = Target("https://same.test/reachable", "same.test")
        blocked = Target("https://same.test/blocked", "same.test")
        baseline = [
            probe(reachable, "cygwin", True),
            probe(reachable, "native", True),
            probe(blocked, "cygwin", False),
            probe(blocked, "native", True),
        ]

        self.assertEqual(
            [blocked],
            SearchEngine._blocked_https_targets([reachable, blocked], baseline),
        )

    def test_cygwin_failure_still_marks_application_route_as_blocked(self) -> None:
        target = Target("https://example.test/", "example.test")

        self.assertEqual(
            [target],
            SearchEngine._blocked_https_targets(
                [target],
                [
                    probe(target, "cygwin", False, error="helper timeout"),
                    probe(target, "native", True),
                ],
            ),
        )

    def test_https_result_must_match_target_validator_identity(self) -> None:
        http_target = Target("https://same.test/api", "same.test", validator="http")
        websocket_target = Target("https://same.test/api", "same.test", validator="websocket")
        # The actual validator name happens to match, but this result belongs to
        # the HTTP target and must not satisfy the websocket target.
        baseline = [probe(http_target, "websocket", True)]

        self.assertEqual(
            [websocket_target],
            SearchEngine._blocked_https_targets([websocket_target], baseline),
        )

    def test_quic_results_are_matched_by_full_probe_identity(self) -> None:
        reachable = Target(
            "https://same.test/reachable",
            "same.test",
            (Protocol.QUIC,),
        )
        blocked = Target(
            "https://same.test/blocked",
            "same.test",
            (Protocol.QUIC,),
        )
        baseline = [probe(reachable, "http3", True), probe(blocked, "http3", False)]

        self.assertEqual(
            [blocked],
            SearchEngine._blocked_targets(
                [reachable, blocked], baseline, Protocol.QUIC, "http3"
            ),
        )

    def test_one_reachable_telegram_websocket_satisfies_alternative_group(self) -> None:
        kws2 = Target(
            "wss://kws2.web.telegram.org/apiws",
            "kws2.web.telegram.org",
            validator="websocket",
            alternative_group="telegram-websocket",
        )
        kws4 = Target(
            "wss://kws4.web.telegram.org/apiws",
            "kws4.web.telegram.org",
            validator="websocket",
            alternative_group="telegram-websocket",
        )
        one_reachable = [probe(kws2, "websocket", False), probe(kws4, "websocket", True)]
        both_blocked = [probe(kws2, "websocket", False), probe(kws4, "websocket", False)]

        self.assertEqual([], SearchEngine._blocked_https_targets([kws2, kws4], one_reachable))
        self.assertEqual(
            [kws2, kws4],
            SearchEngine._blocked_https_targets([kws2, kws4], both_blocked),
        )


class NetworkPreflightTests(unittest.TestCase):
    def test_dns_preflight_uses_probe_budget_instead_of_three_second_cap(self) -> None:
        target = Target("https://example.test/", "example.test")
        engine = SearchEngine(RuntimePaths.discover(), timeout=7.0)
        with patch(
            "adaptive_strategy.engine.dns_addresses_with_deadline",
            return_value={target: ["203.0.113.10"]},
        ) as resolve:
            # A small stub is enough to reach the DNS call without starting
            # the full network tournament.
            with tempfile.TemporaryDirectory() as temporary:
                engine.hostlists["custom"] = Path(temporary) / "hosts.txt"
                engine.hostlists["custom"].write_text("example.test\n", encoding="utf-8")
                engine.probes.probe_many = Mock(return_value=[])
                engine._run([target], {"custom": [target]})

        self.assertEqual(7.0, resolve.call_args.kwargs["timeout"])

    def test_stalled_dns_does_not_claim_that_vpn_is_enabled(self) -> None:
        target = Target("https://example.test/", "example.test")
        blocker = threading.Event()

        with patch(
            "adaptive_strategy.probe.dns_addresses",
            side_effect=lambda _target: blocker.wait(1.0) and [],
        ):
            started = time.monotonic()
            resolved = dns_addresses_with_deadline([target], timeout=0.05)
            elapsed = time.monotonic() - started
            blocker.set()

        self.assertLess(elapsed, 0.4)
        self.assertEqual([], resolved[target])

        engine = SearchEngine(RuntimePaths.discover())
        dns_failure = probe(
            target,
            "cygwin",
            False,
            error="curl: (6) Could not resolve host: example.test",
        )
        native_dns_failure = probe(
            target,
            "native",
            False,
            error="curl: (6) Could not resolve host: example.test",
        )
        engine.probes.probe_many = Mock(
            side_effect=[
                [dns_failure, native_dns_failure],
                [dns_failure],
                [native_dns_failure],
            ]
        )
        with patch(
            "adaptive_strategy.engine.dns_addresses_with_deadline",
            return_value={target: []},
        ), patch("adaptive_strategy.engine.time.sleep", return_value=None):
            outcome = engine._run([target], {"custom": [target]})

        self.assertFalse(outcome.success)
        self.assertEqual("network-routing-error", outcome.confidence)
        self.assertIn("не является признаком VPN", outcome.message)
        self.assertNotIn("Отключите VPN", outcome.message)
        self.assertEqual(3, engine.probes.probe_many.call_count)

    def test_unresolved_preflight_continues_when_protocol_probe_is_not_a_dns_failure(self) -> None:
        target = Target("https://example.test/", "example.test")
        engine = SearchEngine(RuntimePaths.discover())
        baseline = [
            probe(target, "cygwin", False, error="Connection timed out"),
            probe(target, "native", False, error="Connection timed out"),
        ]
        engine.probes.probe_many = Mock(side_effect=[baseline, baseline[:1], baseline[1:]])
        engine._search_protocol = Mock(return_value=None)

        with patch(
            "adaptive_strategy.engine.dns_addresses_with_deadline",
            return_value={target: []},
        ), patch("adaptive_strategy.engine.time.sleep", return_value=None):
            outcome = engine._run([target], {"custom": [target]})

        self.assertEqual("not-validated", outcome.confidence)
        self.assertIn("стратегия", outcome.message)
        engine._search_protocol.assert_called_once()


class FinalValidationScopeTests(unittest.TestCase):
    def test_unmanaged_baseline_service_cannot_reject_combined_profile(self) -> None:
        selected = Target(
            "https://www.youtube.com/generate_204",
            "www.youtube.com",
            service="youtube",
            profile="youtube",
        )
        telegram_web = Target(
            "https://web.telegram.org/k/",
            "web.telegram.org",
            service="telegram",
            profile="telegram",
            resolve_ip="149.154.167.220",
        )
        telegram_socket = Target(
            "wss://kws2.web.telegram.org/apiws",
            "kws2.web.telegram.org",
            service="telegram",
            profile="telegram",
            validator="websocket",
            resolve_ip="149.154.167.220",
            alternative_group="telegram-websocket",
        )
        selected_strategy = Strategy("test", "Test", "test", Protocol.HTTPS, ())

        requests = SearchEngine._validation_requests(
            [selected, telegram_web, telegram_socket],
            {},
            {"youtube": selected_strategy},
        )

        self.assertEqual(
            [(selected, Protocol.HTTPS, "native"),
             (selected, Protocol.HTTPS, "cygwin"),
             (selected, Protocol.HTTPS, "kyber")],
            requests,
        )

    def test_telegram_final_validation_uses_native_or_cygwin_and_one_websocket(self) -> None:
        telegram = Target(
            "https://web.telegram.org/k/",
            "web.telegram.org",
            service="telegram",
            profile="telegram",
            resolve_ip="149.154.167.220",
        )
        socket_target = Target(
            "wss://kws2.web.telegram.org/apiws",
            "kws2.web.telegram.org",
            service="telegram",
            profile="telegram",
            validator="websocket",
            resolve_ip="149.154.167.220",
            alternative_group="telegram-websocket",
        )
        requests = SearchEngine._validation_requests(
            [telegram, socket_target],
            {},
            {"telegram": Strategy("test", "Test", "test", Protocol.HTTPS, ())},
        )
        self.assertEqual(
            [
                (telegram, Protocol.HTTPS, "native"),
                (telegram, Protocol.HTTPS, "cygwin"),
                (socket_target, Protocol.HTTPS, "websocket"),
            ],
            requests,
        )

        results = [
            probe(telegram, "native", True),
            probe(telegram, "cygwin", False, error="provider route timeout"),
            probe(socket_target, "websocket", True),
        ]
        self.assertTrue(SearchEngine._validation_passed(results))


class CombinedValidationTests(unittest.TestCase):
    def test_final_validation_attempts_every_round_after_an_initial_failure(self) -> None:
        target = Target("https://example.test/", "example.test")
        engine = SearchEngine(RuntimePaths.discover())
        failed_round = [probe(target, "native", False, error="temporary timeout")]
        passed_round = [
            probe(target, "native", True),
            probe(target, "cygwin", True),
            probe(target, "kyber", True),
        ]
        second_passed_round = list(passed_round)

        class FakeWinws:
            starts = 0

            def __init__(self, *_args) -> None:
                pass

            def __enter__(self):
                type(self).starts += 1
                return self

            def __exit__(self, *_args) -> None:
                return None

        engine._probe_staged = Mock(
            side_effect=[failed_round, passed_round, second_passed_round]
        )
        with tempfile.TemporaryDirectory() as temporary:
            engine.hostlists["custom"] = Path(temporary) / "hosts.txt"
            engine.hostlists["custom"].write_text("example.test\n", encoding="utf-8")
            with (
                patch("adaptive_strategy.engine.WinwsProcess", FakeWinws),
                patch("adaptive_strategy.engine.time.sleep", return_value=None),
            ):
                results, passed_rounds = engine._validate_combined(
                    [target],
                    {"custom": Strategy("test", "Test", "test", Protocol.HTTPS, ())},
                    {},
                )

        self.assertEqual(COMBINED_VALIDATION_ROUNDS, FakeWinws.starts)
        self.assertEqual(2, passed_rounds)
        self.assertEqual(failed_round + passed_round + second_passed_round, results)

    def test_validation_requires_results_for_every_requested_target(self) -> None:
        first = Target("https://first.test/", "first.test")
        second = Target("https://second.test/", "second.test")
        requests = [
            (first, Protocol.HTTPS, "native"),
            (first, Protocol.HTTPS, "cygwin"),
            (second, Protocol.HTTPS, "native"),
            (second, Protocol.HTTPS, "cygwin"),
        ]
        results = [probe(first, "native", True), probe(first, "cygwin", True)]

        self.assertFalse(SearchEngine._validation_passed(results, requests))

    def test_required_rounds_tolerate_one_transient_round(self) -> None:
        self.assertEqual(3, COMBINED_VALIDATION_ROUNDS)
        self.assertEqual(2, COMBINED_VALIDATION_REQUIRED_ROUNDS)

    def test_single_candidate_confirmation_uses_https_quorum_and_is_reported(self) -> None:
        target = Target("https://example.test/", "example.test")
        strategy = Strategy("test", "Test", "test", Protocol.HTTPS, ())
        engine = SearchEngine(RuntimePaths.discover(), timeout=5.0)
        confirmation = [
            probe(target, "native", False, error="temporary Schannel timeout"),
            probe(target, "cygwin", True),
            probe(target, "kyber", True),
        ]
        observed_timeouts: list[float] = []

        class FakeWinws:
            def __init__(self, *_args) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

        def staged(_requests, retry_failures=False):
            self.assertTrue(retry_failures)
            observed_timeouts.append(engine.probes.timeout)
            return confirmation

        with tempfile.TemporaryDirectory() as temporary:
            engine.hostlists["custom"] = Path(temporary) / "hosts.txt"
            engine.hostlists["custom"].write_text("example.test\n", encoding="utf-8")
            engine._probe_staged = Mock(side_effect=staged)
            with patch("adaptive_strategy.engine.WinwsProcess", FakeWinws):
                passed, results = engine._validate_single(
                    strategy, [target], "custom"
                )

        self.assertTrue(passed)
        self.assertEqual(confirmation, results)
        self.assertEqual([8.0], observed_timeouts)
        self.assertEqual(5.0, engine.probes.timeout)

        candidate = CandidateResult(
            strategy,
            probes=[probe(target, "cygwin", True)],
            confirmation=results,
            profile="custom",
        )
        outcome = SearchOutcome(
            False,
            [target],
            [],
            candidates=[candidate],
        )
        serialized = outcome.to_dict()["candidates"][0]
        self.assertEqual(3, len(serialized["confirmation"]))
        self.assertIn("Schannel", serialized["confirmation"][0]["error"])

    def test_two_https_helpers_accept_a_transient_failure_in_the_third(self) -> None:
        telegram = Target("https://web.telegram.org/k/", "web.telegram.org")
        kws2 = Target(
            "wss://kws2.web.telegram.org/apiws",
            "kws2.web.telegram.org",
            validator="websocket",
            alternative_group="telegram-websocket",
        )
        kws4 = Target(
            "wss://kws4.web.telegram.org/apiws",
            "kws4.web.telegram.org",
            validator="websocket",
            alternative_group="telegram-websocket",
        )
        results = [
            probe(telegram, "native", True),
            probe(telegram, "cygwin", False, error="temporary timeout"),
            probe(telegram, "kyber", True),
            probe(kws2, "websocket", False, error="timed out"),
            probe(kws4, "websocket", True),
        ]

        self.assertTrue(SearchEngine._validation_passed(results))

    def test_https_quorum_and_http3_remain_required(self) -> None:
        target = Target(
            "https://www.youtube.com/generate_204",
            "www.youtube.com",
            (Protocol.HTTPS, Protocol.QUIC),
        )
        only_one_https_helper = [
            probe(target, "native", True),
            probe(target, "cygwin", False),
            probe(target, "kyber", False),
            probe(target, "http3", True),
        ]
        quic_failed = [
            probe(target, "native", True),
            probe(target, "cygwin", True),
            probe(target, "kyber", True),
            probe(target, "http3", False),
        ]

        self.assertFalse(SearchEngine._validation_passed(only_one_https_helper))
        self.assertFalse(SearchEngine._validation_passed(quic_failed))


class HostlistLifecycleTests(unittest.TestCase):
    def test_each_run_uses_a_fresh_temp_directory_cleans_it_and_resets_candidates(self) -> None:
        target = Target(
            "https://example.test/",
            "example.test",
            service="custom",
            profile="custom",
        )
        strategy = Strategy("test", "Test", "test", Protocol.HTTPS, ())
        stale = CandidateResult(strategy, profile="stale")
        fresh = CandidateResult(strategy, profile="custom")
        engine = SearchEngine(RuntimePaths.discover())
        engine.candidate_results.append(stale)
        run_directories: list[Path] = []
        candidates_at_entry: list[list[CandidateResult]] = []

        def fake_run(run_targets: list[Target], _groups: dict[str, list[Target]]) -> SearchOutcome:
            candidates_at_entry.append(list(engine.candidate_results))
            hostlists = list(engine.hostlists.values())
            self.assertEqual(1, len(hostlists))
            self.assertTrue(hostlists[0].is_file())
            self.assertEqual("example.test\n", hostlists[0].read_text(encoding="utf-8"))
            run_directories.append(hostlists[0].parent)
            engine.candidate_results.append(fresh)
            return SearchOutcome(
                True,
                run_targets,
                [],
                candidates=engine.candidate_results,
            )

        with (
            patch.object(RuntimePaths, "missing", return_value=[]),
            patch("adaptive_strategy.engine.runtime_helper_errors", return_value=[]),
            patch("adaptive_strategy.engine.conflicting_processes", return_value=[]),
            patch.object(engine, "_run", side_effect=fake_run),
        ):
            first = engine.run([target])
            second = engine.run([target])

        self.assertEqual([[], []], candidates_at_entry)
        self.assertEqual(1, len(first.candidates))
        self.assertEqual(1, len(second.candidates))
        self.assertEqual(2, len(set(run_directories)))
        self.assertTrue(all(not directory.exists() for directory in run_directories))
        self.assertEqual({}, engine.hostlists)


if __name__ == "__main__":
    unittest.main()
