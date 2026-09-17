from __future__ import annotations

import threading
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from .catalog import strategies_for
from .hostlist import grouped_targets, profile_hosts
from .models import (
    CandidateResult,
    ProbeResult,
    Protocol,
    SearchOutcome,
    Strategy,
    Target,
    probe_matrix_passed,
)
from .probe import ProbeRunner, dns_addresses_with_deadline
from .runtime import (
    RuntimePaths,
    WinwsProcess,
    conflicting_processes,
    runtime_helper_errors,
    winws_arguments,
)


ProgressCallback = Callable[[float, str], None]
COMBINED_VALIDATION_ROUNDS = 3
COMBINED_VALIDATION_REQUIRED_ROUNDS = 2
VALIDATION_TIMEOUT_FLOOR = 8.0
# Final rounds are intentionally separated in addition to the process-level
# WinDivert restart cooldown. This makes them independent samples rather than
# back-to-back requests through one short-lived network state.
COMBINED_VALIDATION_ROUND_DELAY = 0.75


class SearchCancelled(RuntimeError):
    pass


class SearchEngine:
    def __init__(
        self,
        paths: RuntimePaths,
        timeout: float = 5.0,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.paths = paths
        self.timeout = max(1.0, float(timeout))
        self.probes = ProbeRunner(paths, self.timeout)
        self.progress = progress or (lambda _value, _label: None)
        self.cancel_event = cancel_event or threading.Event()
        self.candidate_results: list[CandidateResult] = []
        self.hostlists: dict[str, Path] = {}

    def run(self, targets: list[Target]) -> SearchOutcome:
        # A SearchEngine instance may be reused after a completed or cancelled
        # search.  Diagnostics from an earlier run must never leak into the next
        # outcome.
        self.candidate_results = []
        self.hostlists.clear()
        missing = self.paths.missing()
        if missing:
            names = ", ".join(str(path) for path in missing)
            return SearchOutcome(False, targets, [], message=f"Не найдены компоненты: {names}")
        helper_errors = runtime_helper_errors(self.paths)
        if helper_errors:
            return SearchOutcome(
                False,
                targets,
                [],
                confidence="runtime-error",
                message=(
                    "Не запустились встроенные компоненты проверки; поиск стратегий не выполнялся: "
                    + "; ".join(helper_errors)
                ),
            )
        conflicts = conflicting_processes()
        if conflicts:
            return SearchOutcome(
                False,
                targets,
                [],
                message="Перед поиском закройте активные средства обхода: " + ", ".join(conflicts),
            )

        groups = grouped_targets(targets)
        try:
            # Per-run hostlists belong in one unique temporary directory.  This
            # prevents concurrent GUI instances (and stale crashed runs) from
            # overwriting each other's filter input.
            with tempfile.TemporaryDirectory(prefix="ZapretGUI-adaptive-") as temporary:
                hostlist_dir = Path(temporary)
                for index, (profile, profile_targets) in enumerate(groups.items()):
                    safe_name = re_safe_name(profile)
                    path = hostlist_dir / f"{index:02d}-hosts-{safe_name}.txt"
                    path.write_text(
                        "\n".join(profile_hosts(profile, profile_targets)) + "\n",
                        encoding="utf-8",
                    )
                    self.hostlists[profile] = path
                return self._run(targets, groups)
        except SearchCancelled:
            return SearchOutcome(False, targets, [], candidates=self.candidate_results, message="Поиск отменён")
        finally:
            self.hostlists.clear()

    def _run(self, targets: list[Target], groups: dict[str, list[Target]]) -> SearchOutcome:
        self._notify(0.01, "Проверка DNS")
        resolved = dns_addresses_with_deadline(
            targets,
            # DNS is a preflight guard, not the actual probe.  It must still
            # fit inside the probe budget, but a hard three-second cap made
            # slow provider/VPN DNS look like a missing strategy.
            timeout=self.timeout,
            cancel_event=self.cancel_event,
        )
        self._check_cancelled()
        # DNS is diagnostic telemetry only. A resolver timeout, filtered
        # NXDOMAIN or split-DNS setup is not proof that a VPN is enabled.
        # Continue to the real protocol probes and classify the failure from
        # their errors instead of rejecting a healthy PC at preflight.
        unresolved = {target.hostname for target in targets if not resolved.get(target)}

        baseline_requests: list[tuple[Target, Protocol, str]] = []
        for target in targets:
            if target.validator == "discord_browser":
                continue
            # Static resolution is part of the generated Telegram solution, not the baseline.
            # Probe the normal system DNS route first so a hosts-only restriction is detected.
            baseline_target = replace(target, resolve_ip="") if target.resolve_ip else target
            if Protocol.HTTPS in target.protocols:
                # Cygwin curl is the same reliable base used by official blockcheck.
                # Native Schannel is useful extra telemetry but can be unavailable in some Windows tokens.
                if target.validator in {"websocket", "discord_update"}:
                    baseline_requests.append((baseline_target, Protocol.HTTPS, "websocket"))
                    if target.validator == "discord_update":
                        baseline_requests[-1] = (baseline_target, Protocol.HTTPS, "discord_update")
                else:
                    baseline_requests.extend(
                        ((baseline_target, Protocol.HTTPS, "cygwin"), (baseline_target, Protocol.HTTPS, "native"))
                    )
            if Protocol.QUIC in target.protocols:
                baseline_requests.append((baseline_target, Protocol.QUIC, "http3"))
        self._notify(0.04, "Базовая проверка без zapret")
        baseline = self.probes.probe_many(baseline_requests)
        baseline = self._retry_failed_probes(baseline_requests, baseline)
        required_baseline = [result for result in baseline if self._probe_is_required(result)]
        if (
            unresolved
            and required_baseline
            and not any(result.success for result in required_baseline)
            and all(
                result.target.hostname in unresolved
                and self._looks_like_dns_failure(result.error)
                for result in required_baseline
            )
        ):
            return SearchOutcome(
                False,
                targets,
                baseline,
                confidence="network-routing-error",
                message=(
                    "Системный DNS не смог разрешить выбранные адреса: "
                    + ", ".join(sorted(unresolved))
                    + ". Это не является признаком VPN. Проверьте подключение, "
                    "настройки DNS/прокси и повторите подбор."
                ),
            )
        blocked_tcp_groups = {
            profile: profile_targets
            for profile, profile_targets in groups.items()
            if self._blocked_https_targets(profile_targets, baseline)
        }
        blocked_quic_groups = {
            profile: profile_targets
            for profile, profile_targets in groups.items()
            if self._blocked_targets(profile_targets, baseline, Protocol.QUIC, "http3")
        }
        if not blocked_tcp_groups and not blocked_quic_groups:
            return SearchOutcome(
                False,
                targets,
                baseline,
                confidence="baseline-reachable",
                message="Все выбранные цели уже доступны без zapret; генерировать вмешивающуюся стратегию небезопасно.",
            )

        tcp_profiles: dict[str, Strategy] = {}
        quic_profiles: dict[str, Strategy] = {}
        tcp_items = list(blocked_tcp_groups.items())
        for index, (profile, profile_targets) in enumerate(tcp_items):
            start = 0.10 + 0.52 * index / max(1, len(tcp_items))
            end = 0.10 + 0.52 * (index + 1) / max(1, len(tcp_items))
            strategy = self._search_protocol(profile_targets, Protocol.HTTPS, start, end, profile)
            if strategy is None:
                return SearchOutcome(
                    False, targets, baseline, candidates=self.candidate_results,
                    tcp_profiles=tcp_profiles,
                    message=(f"Быстрая TCP/HTTPS-стратегия для группы «{profile}» не найдена. "
                             "Диагностика сохранена в отчёте поиска."),
                )
            tcp_profiles[profile] = strategy
        quic_items = list(blocked_quic_groups.items())
        for index, (profile, profile_targets) in enumerate(quic_items):
            start = 0.62 + 0.16 * index / max(1, len(quic_items))
            end = 0.62 + 0.16 * (index + 1) / max(1, len(quic_items))
            strategy = self._search_protocol(profile_targets, Protocol.QUIC, start, end, profile)
            if strategy is None:
                self._notify(
                    end,
                    f"{profile}: QUIC не подтверждён, используется проверенный TCP fallback",
                )
                continue
            quic_profiles[profile] = strategy

        self._notify(0.80, "Финальная проверка объединённого BAT-профиля")
        validation, completed_rounds = self._validate_combined(targets, tcp_profiles, quic_profiles)
        passed = completed_rounds >= COMBINED_VALIDATION_REQUIRED_ROUNDS
        if not passed:
            return SearchOutcome(
                False,
                targets,
                baseline,
                tcp_strategy=next(iter(tcp_profiles.values()), None),
                quic_strategy=next(iter(quic_profiles.values()), None),
                tcp_profiles=tcp_profiles,
                quic_profiles=quic_profiles,
                validation=validation,
                candidates=self.candidate_results,
                message=(
                    "Победитель не прошёл повторную проверку "
                    f"({completed_rounds}/{COMBINED_VALIDATION_ROUNDS} раундов подтверждено, "
                    f"нужно {COMBINED_VALIDATION_REQUIRED_ROUNDS}); BAT не создан."
                ),
            )

        rounds = completed_rounds
        self._notify(1.0, "Стратегия подтверждена")
        return SearchOutcome(
            True,
            targets,
            baseline,
            tcp_strategy=next(iter(tcp_profiles.values()), None),
            quic_strategy=next(iter(quic_profiles.values()), None),
            tcp_profiles=tcp_profiles,
            quic_profiles=quic_profiles,
            validation=validation,
            candidates=self.candidate_results,
            confidence=f"validated-{rounds}-of-{COMBINED_VALIDATION_ROUNDS}-rounds",
            message=(
                f"Стратегия прошла {rounds} из {COMBINED_VALIDATION_ROUNDS} "
                "независимых раундов проверки."
            ),
        )

    def _search_protocol(
        self,
        targets: list[Target],
        protocol: Protocol,
        progress_start: float,
        progress_end: float,
        profile: str,
    ) -> Strategy | None:
        candidates = strategies_for(protocol, profile)
        for index, strategy in enumerate(candidates):
            self._check_cancelled()
            fraction = progress_start + (progress_end - progress_start) * (index / max(1, len(candidates)))
            self._notify(fraction, f"{profile}: {strategy.name}")
            result = self._evaluate(strategy, targets, profile)
            self.candidate_results.append(result)
            if result.passed:
                self._notify(fraction, f"{profile}: подтверждение {strategy.name}")
                confirmed, confirmation = self._validate_single(strategy, targets, profile)
                result.confirmation = confirmation
                if confirmed:
                    return strategy
        return None

    def _evaluate(self, strategy: Strategy, targets: list[Target], profile: str) -> CandidateResult:
        requests = [
            (
                target,
                strategy.protocol,
                "http3" if strategy.protocol is Protocol.QUIC else (
                    target.validator
                    if target.validator in {"websocket", "discord_browser", "discord_update"}
                    else "cygwin"
                ),
            )
            for target in targets
            if strategy.protocol in target.protocols
        ]
        options = strategy.render(
            self.paths.fake_tls, self.paths.fake_quic,
            self.paths.fake_tls_max, self.paths.fake_tls_4pda,
        )
        args = winws_arguments(strategy.protocol.value, options, self.hostlists[profile])
        try:
            with WinwsProcess(self.paths, args):
                probes = self._probe_staged(requests)
        except (OSError, RuntimeError) as exc:
            return CandidateResult(strategy, startup_ok=False, error=str(exc), profile=profile)
        return CandidateResult(strategy, probes=probes, profile=profile)

    def _validate_single(
        self,
        strategy: Strategy,
        targets: list[Target],
        profile: str,
    ) -> tuple[bool, list[ProbeResult]]:
        if strategy.protocol is Protocol.QUIC:
            validators = ("http3",)
        else:
            validators = ("native", "cygwin", "kyber")
        requests: list[tuple[Target, Protocol, str]] = []
        for target in targets:
            if strategy.protocol not in target.protocols:
                continue
            target_validators = (
                (target.validator,)
                if target.validator in {"websocket", "discord_browser", "discord_update"}
                else validators
            )
            requests.extend((target, strategy.protocol, validator) for validator in target_validators)
        options = strategy.render(
            self.paths.fake_tls, self.paths.fake_quic,
            self.paths.fake_tls_max, self.paths.fake_tls_4pda,
        )
        args = winws_arguments(strategy.protocol.value, options, self.hostlists[profile])
        try:
            with WinwsProcess(self.paths, args):
                with self._validation_timeout():
                    results = self._probe_staged(requests, retry_failures=True)
        except (OSError, RuntimeError) as exc:
            startup = ProbeResult(
                targets[0],
                "startup",
                False,
                None,
                0.0,
                error=str(exc),
            ) if targets else None
            return False, [startup] if startup is not None else []
        required = [result for result in results if self._probe_is_required(result)]
        # Discovery uses one reliable Cygwin probe per target for speed, while
        # confirmation deliberately uses several independent clients. Requiring
        # every helper to pass turned one transient Schannel/kyber timeout into
        # a false rejection of a strategy that had already returned HTTP 200.
        return self._validation_passed(required, requests), results

    def _validate_combined(
        self,
        targets: list[Target],
        tcp_profiles: dict[str, Strategy],
        quic_profiles: dict[str, Strategy],
    ) -> tuple[list[ProbeResult], int]:
        """Run independent final rounds without blending their outcomes.

        Every configured round is attempted, even when an earlier one fails.
        In particular, do not report ``0/2`` after attempting just one round:
        startup races and short routing outages must get the same independent
        retry that a successful first round gets.  The returned count is the
        number of *passed* rounds; callers still require all rounds to pass.
        """
        rounds = COMBINED_VALIDATION_ROUNDS
        args = self._combined_arguments(tcp_profiles, quic_profiles)
        all_results: list[ProbeResult] = []
        completed_rounds = 0
        for round_index in range(rounds):
            self._check_cancelled()
            self._notify(0.80 + 0.19 * (round_index / rounds), f"Проверка {round_index + 1}/{rounds}")
            requests = self._validation_requests(targets, quic_profiles, tcp_profiles)
            try:
                with WinwsProcess(self.paths, args):
                    with self._validation_timeout():
                        round_results = self._probe_staged(requests, retry_failures=True)
                    all_results.extend(round_results)
            except (OSError, RuntimeError) as exc:
                if targets:
                    all_results.append(ProbeResult(targets[0], "startup", False, None, 0.0, error=str(exc)))
            else:
                if self._validation_passed(round_results, requests):
                    completed_rounds += 1
            if round_index + 1 < rounds:
                # This is intentionally outside the try block: a failed
                # startup must get a clean retry too.
                time.sleep(COMBINED_VALIDATION_ROUND_DELAY)
        return all_results, completed_rounds

    @staticmethod
    def _validation_requests(
        targets: list[Target],
        quic_profiles: dict[str, Strategy],
        tcp_profiles: dict[str, Strategy] | None = None,
    ) -> list[tuple[Target, Protocol, str]]:
        requests: list[tuple[Target, Protocol, str]] = []
        selected_tcp_profiles = tcp_profiles or {}
        for target in targets:
            profile = target.profile or target.service
            # The final stage certifies only rules that were actually added to
            # the generated BAT.  A service that was reachable at baseline has
            # no selected strategy, so a later transient failure in its normal
            # route must not reject an otherwise validated profile.
            if profile not in selected_tcp_profiles and profile not in quic_profiles:
                continue
            effective_target = target
            if Protocol.HTTPS in target.protocols:
                validators = SearchEngine._validation_validators(target)
                requests.extend((effective_target, Protocol.HTTPS, validator) for validator in validators)
            if Protocol.QUIC in target.protocols and profile in quic_profiles:
                requests.append((effective_target, Protocol.QUIC, "http3"))
        return requests

    def _probe_staged(
        self,
        requests: list[tuple[Target, Protocol, str]],
        retry_failures: bool = False,
    ) -> list[ProbeResult]:
        """Run package probes only after the cheap network matrix passes."""
        expensive = {"discord_browser", "discord_update"}
        primary = [request for request in requests if request[2] not in expensive]
        secondary = [request for request in requests if request[2] in expensive]
        results = self.probes.probe_many(primary)
        if retry_failures:
            results = self._retry_failed_probes(primary, results)
        required = [result for result in results if self._probe_is_required(result)]
        primary_passed = (
            not primary
            or (
                self._validation_passed(required, primary)
                if retry_failures
                else probe_matrix_passed(required)
            )
        )
        if primary_passed and secondary:
            secondary_results = self.probes.probe_many(secondary, workers=1)
            if retry_failures:
                secondary_results = self._retry_failed_probes(secondary, secondary_results)
            results.extend(secondary_results)
        return results

    def _retry_failed_probes(
        self,
        requests: list[tuple[Target, Protocol, str]],
        results: list[ProbeResult],
    ) -> list[ProbeResult]:
        """Retry transient failures sequentially and keep only the latest result."""
        failed_keys = {
            self._probe_key(result)
            for result in results
            if not result.success and self._probe_is_required(result)
        }
        retry_requests = [
            request for request in requests
            if self._request_key(request) in failed_keys
        ]
        if not retry_requests:
            return results
        self._check_cancelled()
        time.sleep(0.25)
        retries: list[ProbeResult] = []
        for request in retry_requests:
            self._check_cancelled()
            retries.extend(self.probes.probe_many([request], workers=1))
        retry_by_key = {self._probe_key(result): result for result in retries}
        return [retry_by_key.get(self._probe_key(result), result) for result in results]

    @staticmethod
    def _probe_key(result: ProbeResult) -> tuple[str, str, str]:
        return result.target.url, result.target.validator, result.validator

    @staticmethod
    def _request_key(request: tuple[Target, Protocol, str]) -> tuple[str, str, str]:
        target, _protocol, validator = request
        return target.url, target.validator, validator

    @contextmanager
    def _validation_timeout(self):
        """Temporarily allow slower confirmation probes without slowing the tournament."""
        old_timeout = getattr(self.probes, "timeout", None)
        if old_timeout is None:
            yield
            return
        self.probes.timeout = max(float(old_timeout), VALIDATION_TIMEOUT_FLOOR)
        try:
            yield
        finally:
            self.probes.timeout = old_timeout

    @staticmethod
    def _looks_like_dns_failure(error: str) -> bool:
        lowered = (error or "").lower()
        markers = (
            "could not resolve host",
            "name or service not known",
            "no such host is known",
            "getaddrinfo failed",
            "temporary failure in name resolution",
            "имя узла не разрешено",
        )
        return any(marker in lowered for marker in markers)

    def _combined_arguments(
        self,
        tcp_profiles: dict[str, Strategy],
        quic_profiles: dict[str, Strategy],
    ) -> list[str]:
        args: list[str] = []
        if tcp_profiles:
            args.append("--wf-tcp=80,443")
        if quic_profiles:
            args.append("--wf-udp=443")
        strategy_profiles: list[list[str]] = []
        for profile, strategy in quic_profiles.items():
            strategy_profiles.append([
                "--filter-udp=443", "--filter-l7=quic", f"--hostlist={self.hostlists[profile]}",
                *strategy.render(
                    self.paths.fake_tls, self.paths.fake_quic,
                    self.paths.fake_tls_max, self.paths.fake_tls_4pda,
                ),
            ])
        if tcp_profiles:
            if not self.hostlists:
                raise RuntimeError("Hostlists are not prepared")
            union_hostlist = next(iter(self.hostlists.values())).parent / "hosts-all.txt"
            union_hostlist.write_text(
                "\n".join(sorted({host for path in self.hostlists.values() for host in path.read_text(encoding="utf-8").splitlines()})) + "\n",
                encoding="utf-8",
            )
            self.hostlists["__all__"] = union_hostlist
            strategy_profiles.append([
                "--filter-tcp=80", f"--hostlist={union_hostlist}",
                "--dpi-desync=multisplit", "--dpi-desync-split-pos=method+2,midsld",
            ])
        for profile, strategy in tcp_profiles.items():
            strategy_profiles.append([
                "--filter-tcp=443", f"--hostlist={self.hostlists[profile]}",
                *strategy.render(
                    self.paths.fake_tls, self.paths.fake_quic,
                    self.paths.fake_tls_max, self.paths.fake_tls_4pda,
                ),
            ])
        for index, profile_args in enumerate(strategy_profiles):
            if index:
                args.append("--new")
            args.extend(profile_args)
        return args

    @staticmethod
    def _blocked_https_targets(targets: list[Target], baseline: list[ProbeResult]) -> list[Target]:
        by_probe = {
            SearchEngine._probe_key(result): result
            for result in baseline
        }
        classified: list[tuple[Target, bool]] = []
        for target in targets:
            if Protocol.HTTPS not in target.protocols:
                continue
            if target.validator in {"discord_browser", "discord_update"}:
                specialized = by_probe.get((target.url, target.validator, target.validator))
                classified.append((target, specialized is None or not specialized.success))
                continue
            if target.validator == "websocket":
                websocket = by_probe.get((target.url, target.validator, "websocket"))
                classified.append((target, websocket is None or not websocket.success))
                continue
            cygwin = by_probe.get((target.url, target.validator, "cygwin"))
            native = by_probe.get((target.url, target.validator, "native"))
            cygwin_failed = cygwin is None or not cygwin.success
            native_failed = (
                native is not None
                and SearchEngine._probe_is_required(native)
                and not native.success
            )
            classified.append((target, cygwin_failed or native_failed))
        return SearchEngine._collapse_alternative_classification(classified)

    @staticmethod
    def _blocked_targets(
        targets: list[Target],
        baseline: list[ProbeResult],
        protocol: Protocol,
        validator: str,
    ) -> list[Target]:
        result_by_probe = {
            SearchEngine._probe_key(result): result
            for result in baseline
            if result.validator == validator
        }
        classified = [
            (
                target,
                not result_by_probe.get(
                    (target.url, target.validator, validator),
                    ProbeResult(target, validator, False, None, 0),
                ).success,
            )
            for target in targets
            if protocol in target.protocols
        ]
        return SearchEngine._collapse_alternative_classification(classified)

    @staticmethod
    def _collapse_alternative_classification(
        classified: list[tuple[Target, bool]],
    ) -> list[Target]:
        """Treat an alternative group as reachable when one target fully passes."""
        reachable_alternatives = {
            target.alternative_group
            for target, is_blocked in classified
            if target.alternative_group and not is_blocked
        }
        return [
            target
            for target, is_blocked in classified
            if is_blocked and target.alternative_group not in reachable_alternatives
        ]

    @staticmethod
    def _candidate_sort_key(result: CandidateResult) -> tuple[float, int, float]:
        return (-result.pass_rate, result.strategy.risk, result.mean_time)

    @staticmethod
    def _validation_passed(
        results: list[ProbeResult],
        requests: list[tuple[Target, Protocol, str]] | None = None,
    ) -> bool:
        """Evaluate exactly one final validation round.

        The search already selects every TCP profile through Cygwin curl, then
        the final BAT is checked by three independent HTTPS clients.  A single
        short-lived failure in one helper must not reject a profile when two
        other validators reach the same endpoint.  Protocol-specific checks
        (HTTP/3, Discord update and WebSocket) stay strict, and a Telegram
        WebSocket alternative group still requires at least one reachable node.
        """
        if not results:
            return False

        by_target: dict[tuple[str, str], list[ProbeResult]] = {}
        for result in results:
            if not SearchEngine._probe_is_required(result):
                continue
            key = (result.target.url, result.target.validator)
            by_target.setdefault(key, []).append(result)
        expected_targets: dict[tuple[str, str], Target] = {}
        if requests is not None:
            for target, _protocol, _validator in requests:
                expected_targets[(target.url, target.validator)] = target
        else:
            expected_targets = {
                key: target_results[0].target
                for key, target_results in by_target.items()
            }
        if not expected_targets:
            return False

        alternatives: dict[str, list[bool]] = {}
        for key, target in expected_targets.items():
            target_results = by_target.get(key, [])
            special_target = target.validator in {"websocket", "discord_browser", "discord_update"}
            if special_target:
                target_passed = bool(target_results) and all(result.success for result in target_results)
            elif target.service == "telegram":
                # Telegram Web is deliberately checked through a fixed,
                # known endpoint and its WebSocket alternative group.  The
                # native and Cygwin clients do not have equivalent reliability
                # on all Windows providers: one can time out while the other
                # reaches the same Telegram IP immediately.  Requiring a
                # two-client HTTPS quorum here made the refactored final BAT
                # validator reject a working strategy even when the native
                # route and one WebSocket node were both healthy.
                https_results = [result for result in target_results if result.validator != "http3"]
                https_passed = any(result.success for result in https_results)
                http3_results = [result for result in target_results if result.validator == "http3"]
                http3_passed = not http3_results or all(result.success for result in http3_results)
                target_passed = https_passed and http3_passed
            else:
                # native, Cygwin curl and curl-kyber check the same HTTPS
                # endpoint. Two successful, distinct helpers form a stable
                # quorum; HTTP/3 remains an independent strict requirement.
                https_results = [result for result in target_results if result.validator != "http3"]
                successful_https_helpers = {
                    result.validator for result in https_results if result.success
                }
                https_passed = len(successful_https_helpers) >= 2
                http3_results = [result for result in target_results if result.validator == "http3"]
                http3_passed = not http3_results or all(result.success for result in http3_results)
                target_passed = https_passed and http3_passed

            if target.alternative_group:
                alternatives.setdefault(target.alternative_group, []).append(target_passed)
            elif not target_passed:
                return False
        return all(any(values) for values in alternatives.values())

    @staticmethod
    def _validation_validators(target: Target) -> tuple[str, ...]:
        """Return validators appropriate for a target's actual protocol.

        The kyber curl helper is valuable telemetry for ordinary HTTPS, but it
        is not an independent requirement for Telegram Web.  Telegram's
        fixed-IP route can be accepted by Schannel while either Cygwin build
        is temporarily unavailable, and the WebSocket alternative below is
        the protocol-specific proof that the Telegram route works.
        """
        if target.validator in {"websocket", "discord_browser", "discord_update"}:
            return (target.validator,)
        if target.service == "telegram":
            return ("native", "cygwin")
        return ("native", "cygwin", "kyber")

    @staticmethod
    def _probe_is_required(result: ProbeResult) -> bool:
        if result.validator != "native":
            return True
        infrastructure_errors = (
            "SEC_E_NO_CREDENTIALS",
            "No such file or directory",
            "not recognized as an internal",
            "WinError 2",
        )
        return not any(marker.lower() in result.error.lower() for marker in infrastructure_errors)

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise SearchCancelled()

    def _notify(self, value: float, label: str) -> None:
        self.progress(max(0.0, min(1.0, value)), label)


def re_safe_name(value: str) -> str:
    return "".join(character if character.isalnum() or character in "-_" else "_" for character in value)
