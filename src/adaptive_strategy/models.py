from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from pathlib import Path
from typing import Any


class Protocol(str, Enum):
    HTTPS = "https"
    QUIC = "quic"


@dataclass(frozen=True)
class Target:
    url: str
    hostname: str
    protocols: tuple[Protocol, ...] = (Protocol.HTTPS,)
    service: str = "custom"
    profile: str = ""
    validator: str = "http"
    resolve_ip: str = ""
    alternative_group: str = ""


@dataclass(frozen=True)
class Strategy:
    id: str
    name: str
    family: str
    protocol: Protocol
    options: tuple[str, ...]
    tier: int = 1
    risk: int = 1
    description: str = ""

    def render(
        self,
        fake_tls: Path,
        fake_quic: Path,
        fake_tls_max: Path | None = None,
        fake_tls_4pda: Path | None = None,
    ) -> list[str]:
        values = {
            "fake_tls": str(fake_tls),
            "fake_tls_max": str(fake_tls_max or fake_tls),
            "fake_tls_4pda": str(fake_tls_4pda or fake_tls),
            "fake_stun": str(fake_tls.parent / "stun.bin"),
            "fake_stun2": str(fake_tls.parent / "stun2.bin"),
            "fake_tls_sochi": str(fake_tls.parent / "tls_clienthello_sochi_park.bin"),
            "fake_discord_active": str(fake_tls.parent / "ACTIVE_DISCORD_UDP.bin"),
            "fake_quic": str(fake_quic),
        }
        return [option.format_map(values) for option in self.options]


@dataclass(frozen=True)
class ProbeResult:
    target: Target
    validator: str
    success: bool
    http_code: int | None
    elapsed: float
    remote_ip: str = ""
    error: str = ""


@dataclass
class CandidateResult:
    strategy: Strategy
    probes: list[ProbeResult] = field(default_factory=list)
    startup_ok: bool = True
    error: str = ""
    profile: str = ""
    confirmation: list[ProbeResult] = field(default_factory=list)

    @property
    def successes(self) -> int:
        return sum(item.success for item in self.probes)

    @property
    def total(self) -> int:
        return len(self.probes)

    @property
    def pass_rate(self) -> float:
        return self.successes / self.total if self.total else 0.0

    @property
    def mean_time(self) -> float:
        successful = [item.elapsed for item in self.probes if item.success]
        return sum(successful) / len(successful) if successful else float("inf")

    @property
    def passed(self) -> bool:
        return self.startup_ok and probe_matrix_passed(self.probes)


@dataclass
class SearchOutcome:
    success: bool
    targets: list[Target]
    baseline: list[ProbeResult]
    tcp_strategy: Strategy | None = None
    quic_strategy: Strategy | None = None
    tcp_profiles: dict[str, Strategy] = field(default_factory=dict)
    quic_profiles: dict[str, Strategy] = field(default_factory=dict)
    validation: list[ProbeResult] = field(default_factory=list)
    candidates: list[CandidateResult] = field(default_factory=list)
    confidence: str = "not-validated"
    message: str = ""
    output_dir: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        def strategy_dict(value: Strategy | None) -> dict[str, Any] | None:
            if value is None:
                return None
            return {
                "id": value.id,
                "name": value.name,
                "family": value.family,
                "protocol": value.protocol.value,
                "options": list(value.options),
                "tier": value.tier,
                "risk": value.risk,
                "description": value.description,
            }

        def probe_dict(value: ProbeResult) -> dict[str, Any]:
            return {
                "url": value.target.url,
                "hostname": value.target.hostname,
                "service": value.target.service,
                "profile": value.target.profile or value.target.service,
                "probe_kind": value.target.validator,
                "validator": value.validator,
                "success": value.success,
                "http_code": value.http_code,
                "elapsed": round(value.elapsed, 3),
                "remote_ip": value.remote_ip,
                "error": value.error,
            }

        return {
            "success": self.success,
            "message": self.message,
            "confidence": self.confidence,
            "targets": [target.url for target in self.targets],
            "baseline": [probe_dict(item) for item in self.baseline],
            "tcp_strategy": strategy_dict(self.tcp_strategy),
            "quic_strategy": strategy_dict(self.quic_strategy),
            "tcp_profiles": {name: strategy_dict(value) for name, value in self.tcp_profiles.items()},
            "quic_profiles": {name: strategy_dict(value) for name, value in self.quic_profiles.items()},
            "validation": [probe_dict(item) for item in self.validation],
            "candidates": [
                {
                    "strategy": strategy_dict(item.strategy),
                    "startup_ok": item.startup_ok,
                    "error": item.error,
                    "profile": item.profile,
                    "pass_rate": round(item.pass_rate, 3),
                    "mean_time": round(item.mean_time, 3) if math.isfinite(item.mean_time) else None,
                    "probes": [probe_dict(probe) for probe in item.probes],
                    "confirmation": [probe_dict(probe) for probe in item.confirmation],
                }
                for item in self.candidates
            ],
        }


def probe_matrix_passed(probes: list[ProbeResult]) -> bool:
    """Require every normal target and one fully passing target per alternative group."""
    if not probes:
        return False
    by_target: dict[tuple[str, str], list[ProbeResult]] = {}
    for probe in probes:
        # The same URL can legitimately have two protocol-specific target
        # definitions. Do not let a successful generic HTTP probe satisfy (or
        # get poisoned by) a specialised validator for that same URL.
        key = (probe.target.url, probe.target.validator)
        by_target.setdefault(key, []).append(probe)

    alternatives: dict[str, list[bool]] = {}
    for target_probes in by_target.values():
        target = target_probes[0].target
        target_passed = bool(target_probes) and all(probe.success for probe in target_probes)
        if target.alternative_group:
            alternatives.setdefault(target.alternative_group, []).append(target_passed)
        elif not target_passed:
            return False
    return all(any(values) for values in alternatives.values())
