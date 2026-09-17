from __future__ import annotations

import os
import re
import subprocess
import tempfile
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .catalog import tcp_strategy_by_id
from .hostlist import grouped_targets, profile_hosts
from .models import SearchOutcome, Strategy
from .runtime import CREATE_NO_WINDOW, RuntimePaths, run_external


ADAPTIVE_MARKER = "ZAPRETGUI_ADAPTIVE_PROFILE=1"
TELEGRAM_HOSTS_MARKER = "ZAPRETGUI_ADAPTIVE_TELEGRAM_HOSTS=1"
MAX_STRATEGY_NAME_LENGTH = 64
MAX_SAFE_CMD_COMMAND_LENGTH = 7800
_ALLOWED_PUNCTUATION = frozenset(" _-.()")
_RESERVED_WINDOWS_NAMES = {
    "con", "prn", "aux", "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}
_PROFILE_ORDER = ("discord_update", "discord_app", "youtube", "telegram", "custom")
_GENERAL_TCP_FALLBACK_ID = "split-overlap-568-4pda"


@dataclass(frozen=True)
class ValidatedStrategyName:
    stem: str
    filename: str
    automatic: bool


def _name_error(message_ru: str, message_en: str, lang: str) -> ValueError:
    return ValueError(message_ru if lang == "ru" else message_en)


def normalized_strategy_stem(
    value: str,
    *,
    now: datetime | None = None,
    lang: str = "ru",
) -> ValidatedStrategyName:
    raw = unicodedata.normalize("NFC", str(value or "")).strip()
    if raw.lower().endswith(".bat"):
        raw = raw[:-4].rstrip()
    automatic = not raw
    if automatic:
        moment = now or datetime.now()
        raw = "NewAdaptiveBAT_" + moment.strftime("%Y-%m-%d_%H-%M-%S")

    raw = re.sub(r"\s+", " ", raw)
    if len(raw) > MAX_STRATEGY_NAME_LENGTH:
        raise _name_error(
            f"Название должно быть не длиннее {MAX_STRATEGY_NAME_LENGTH} символов.",
            f"The name must be at most {MAX_STRATEGY_NAME_LENGTH} characters.",
            lang,
        )
    if raw.startswith(".") or raw.endswith((".", " ")):
        raise _name_error(
            "Название не может начинаться с точки или заканчиваться точкой/пробелом.",
            "The name cannot start with a dot or end with a dot/space.",
            lang,
        )

    has_letter_or_digit = False
    for character in raw:
        category = unicodedata.category(character)
        if category[0] in {"L", "N"}:
            has_letter_or_digit = True
            continue
        if character in _ALLOWED_PUNCTUATION:
            continue
        raise _name_error(
            "Разрешены буквы, цифры, пробелы и символы _ - . ( ).",
            "Use letters, digits, spaces, and _ - . ( ) only.",
            lang,
        )
    if not has_letter_or_digit:
        raise _name_error(
            "Название должно содержать хотя бы одну букву или цифру.",
            "The name must contain at least one letter or digit.",
            lang,
        )

    device_prefix = raw.split(".", 1)[0].rstrip(" .").casefold()
    if device_prefix in _RESERVED_WINDOWS_NAMES:
        raise _name_error(
            "Это имя зарезервировано Windows. Выберите другое.",
            "This name is reserved by Windows. Choose another one.",
            lang,
        )
    return ValidatedStrategyName(raw, raw + ".bat", automatic)


def normalize_strategy_name(
    value: str,
    *,
    now: datetime | None = None,
    lang: str = "ru",
) -> str:
    return normalized_strategy_stem(value, now=now, lang=lang).filename


def validate_strategy_name(
    value: str,
    destination_dir: Path | str | None = None,
    *,
    now: datetime | None = None,
    lang: str = "ru",
) -> tuple[bool, str, str]:
    try:
        validated = normalized_strategy_stem(value, now=now, lang=lang)
    except ValueError as exc:
        return False, str(exc), ""

    directory = Path(destination_dir) if destination_dir is not None else None
    if directory is not None and directory.is_dir():
        wanted = validated.filename.casefold()
        try:
            collision = any(
                item.is_file() and item.name.casefold() == wanted
                for item in directory.iterdir()
            )
        except OSError as exc:
            message = (
                f"Не удалось проверить папку стратегий: {exc}"
                if lang == "ru" else
                f"Could not inspect the strategy folder: {exc}"
            )
            return False, message, ""
        if collision:
            message = (
                "Стратегия с таким именем уже существует. Выберите другое название."
                if lang == "ru" else
                "A strategy with this name already exists. Choose another name."
            )
            return False, message, validated.filename
    return True, "", validated.filename


class ZapretGuiBatGenerator:
    """Render a confirmed outcome as one Zapret GUI profile BAT."""

    def __init__(self, paths: RuntimePaths, strategies_dir: Path | str) -> None:
        self.paths = paths
        self.strategies_dir = Path(strategies_dir).resolve()

    def generate(self, outcome: SearchOutcome, requested_name: str, *, lang: str = "ru") -> Path:
        if not outcome.success:
            raise ValueError(
                "BAT создаётся только для подтверждённого результата"
                if lang == "ru" else
                "A BAT can only be created from a confirmed result"
            )
        ok, error, filename = validate_strategy_name(
            requested_name,
            self.strategies_dir,
            lang=lang,
        )
        if not ok:
            raise ValueError(error)

        runtime_arguments = self.build_arguments(outcome, for_bat=False)
        self._dry_run(runtime_arguments)
        bat_arguments = self.build_arguments(outcome, for_bat=True)
        content = self._bat_text(outcome, bat_arguments)

        self.strategies_dir.mkdir(parents=True, exist_ok=True)
        destination = self.strategies_dir / filename
        encoded = content.encode("utf-8-sig")
        descriptor: int | None = None
        temporary: Path | None = None
        try:
            descriptor, temporary_name = tempfile.mkstemp(
                prefix=".adaptive-strategy-",
                suffix=".bat.installing",
                dir=self.strategies_dir,
            )
            temporary = Path(temporary_name)
            with os.fdopen(descriptor, "wb") as handle:
                descriptor = None
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            self._publish_without_overwrite(temporary, destination)
            temporary = None
        except FileExistsError as exc:
            raise ValueError(
                "Стратегия с таким именем уже существует."
                if lang == "ru" else
                "A strategy with this name already exists."
            ) from exc
        finally:
            if descriptor is not None:
                os.close(descriptor)
            try:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)
            except OSError:
                pass
        outcome.output_dir = destination
        return destination

    @staticmethod
    def _publish_without_overwrite(temporary: Path, destination: Path) -> None:
        """Publish a complete BAT atomically without replacing an existing one."""
        if os.name == "nt":
            # On Windows, rename is atomic and fails when destination exists.
            os.rename(temporary, destination)
            return

        # POSIX rename replaces an existing path, so publish through an atomic
        # hard-link creation instead. Both paths are always in the same folder.
        os.link(temporary, destination)
        temporary.unlink()

    def build_arguments(self, outcome: SearchOutcome, *, for_bat: bool) -> list[str]:
        tcp_profiles = self._tcp_profiles(outcome)
        quic_profiles = self._quic_profiles(outcome)
        target_groups = grouped_targets(outcome.targets)
        has_discord = any(target.service == "discord" for target in outcome.targets)

        # Adaptive BATs remain full Zapret GUI profiles: the sentinel port 12
        # disables a game filter in a dry run, while service.bat/the GUI expands
        # the placeholders to the user's current game-filter mode at launch.
        tcp_ports = "80,443,2053,2083,2087,2096,8443" if has_discord else "80,443"
        udp_ports = "443,19294-19344,50000-50100" if has_discord else "443"
        arguments: list[str] = [
            f"--wf-tcp={tcp_ports},{self._game_filter_port('tcp', for_bat)}",
            f"--wf-udp={udp_ports},{self._game_filter_port('udp', for_bat)}",
        ]

        segments: list[list[str]] = []
        for profile in self._ordered_profiles(quic_profiles):
            strategy = quic_profiles[profile]
            hosts = profile_hosts(profile, target_groups.get(profile, outcome.targets))
            segments.append([
                "--filter-udp=443",
                "--filter-l7=quic",
                self._hostlist_domains_argument(hosts, for_bat),
                *self._strategy_options(strategy, for_bat),
            ])

        if has_discord:
            active = self._bin_reference("ACTIVE_DISCORD_UDP.bin", for_bat)
            segments.append([
                "--filter-udp=19294-19344,50000-50100",
                "--filter-l7=discord,stun",
                "--dpi-desync=fake",
                f"--dpi-desync-fake-discord={active}",
                f"--dpi-desync-fake-stun={active}",
                "--dpi-desync-repeats=6",
            ])
            discord_strategy = tcp_profiles.get("discord_app") or tcp_strategy_by_id("ts-fakedsplit-zero")
            segments.append([
                "--filter-tcp=2053,2083,2087,2096,8443",
                "--hostlist-domains=discord.media",
                *self._strategy_options(discord_strategy, for_bat),
            ])

        # First-match semantics make the narrower Discord updater profile come
        # before the broader discord.com application group.
        for profile in self._ordered_profiles(tcp_profiles):
            strategy = tcp_profiles[profile]
            hosts = profile_hosts(profile, target_groups.get(profile, outcome.targets))
            segments.append([
                "--filter-tcp=443",
                self._hostlist_domains_argument(hosts, for_bat),
                *self._strategy_options(strategy, for_bat),
            ])

        # Everything above is scoped to the fixed services exercised by the
        # adaptive search. Append broader Zapret GUI compatibility rules only
        # after them so winws first-match semantics cannot change a validated
        # YouTube/Discord/Telegram/Rutracker result.
        segments.extend(self._compatibility_segments(tcp_profiles, for_bat))

        for index, segment in enumerate(segments):
            if index:
                arguments.append("--new")
            arguments.extend(segment)
        return arguments

    def _compatibility_segments(
        self,
        tcp_profiles: dict[str, Strategy],
        for_bat: bool,
    ) -> list[list[str]]:
        """Preserve standard-profile lists and game-filter behavior.

        A selected ``custom`` strategy was validated on the general/custom
        HTTPS target, so it is the best available rule for the user's domain
        lists and IP set. If that target was already reachable, retain the
        conservative TCP rule from the bundled ``general.bat`` instead.

        Arbitrary game protocols and ports are outside the adaptive probe
        matrix. They intentionally keep the existing conservative Flowseal
        fallback instead of extrapolating a service-specific winner.
        """
        general_tcp = tcp_profiles.get("custom") or tcp_strategy_by_id(_GENERAL_TCP_FALLBACK_ID)
        general_lists = [
            self._list_option("hostlist", "list-general.txt", for_bat),
            self._list_option("hostlist", "list-general-user.txt", for_bat),
            *self._exclude_list_options(for_bat),
        ]
        ipset_lists = [
            self._list_option("ipset", "ipset-all.txt", for_bat),
            *self._exclude_list_options(for_bat),
        ]
        game_ipset_lists = [
            self._list_option("ipset", "ipset-all.txt", for_bat),
            self._list_option("ipset-exclude", "ipset-exclude.txt", for_bat),
            self._list_option("ipset-exclude", "ipset-exclude-user.txt", for_bat),
        ]

        return [
            [
                "--filter-tcp=80,443",
                *general_lists,
                *self._strategy_options(general_tcp, for_bat),
            ],
            [
                "--filter-tcp=80,443,8443",
                *ipset_lists,
                *self._strategy_options(general_tcp, for_bat),
            ],
            [
                f"--filter-tcp={self._game_filter_port('tcp', for_bat)}",
                *game_ipset_lists,
                "--dpi-desync=multisplit",
                "--dpi-desync-any-protocol=1",
                "--dpi-desync-cutoff=n3",
                "--dpi-desync-split-seqovl=568",
                "--dpi-desync-split-pos=1",
                f"--dpi-desync-split-seqovl-pattern={self._bin_reference('tls_clienthello_4pda_to.bin', for_bat)}",
            ],
            [
                f"--filter-udp={self._game_filter_port('udp', for_bat)}",
                *game_ipset_lists,
                "--dpi-desync=fake",
                "--dpi-desync-repeats=12",
                "--dpi-desync-any-protocol=1",
                f"--dpi-desync-fake-unknown-udp={self._bin_reference('quic_initial_dbankcloud_ru.bin', for_bat)}",
                "--dpi-desync-cutoff=n2",
            ],
        ]

    def _exclude_list_options(self, for_bat: bool) -> list[str]:
        return [
            self._list_option("hostlist-exclude", "list-exclude.txt", for_bat),
            self._list_option("hostlist-exclude", "list-exclude-user.txt", for_bat),
            self._list_option("ipset-exclude", "ipset-exclude.txt", for_bat),
            self._list_option("ipset-exclude", "ipset-exclude-user.txt", for_bat),
        ]

    def _list_option(self, option: str, filename: str, for_bat: bool) -> str:
        if for_bat:
            return f'--{option}="%LISTS%{filename}"'
        # subprocess receives each list item as one argument, so an absolute
        # path containing spaces must not be decorated with literal quotes.
        lists_dir = (self.paths.winws_dir.parent / "lists").resolve()
        return f"--{option}={lists_dir / filename}"

    @staticmethod
    def _game_filter_port(protocol: str, for_bat: bool) -> str:
        if not for_bat:
            return "12"
        return "%GameFilterTCP%" if protocol == "tcp" else "%GameFilterUDP%"

    def _dry_run(self, arguments: list[str]) -> None:
        command = [str(self.paths.winws), "--dry-run", *arguments]
        try:
            completed = run_external(
                command,
                cwd=self.paths.winws_dir,
                capture_output=True,
                timeout=15,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise RuntimeError(f"Не удалось проверить итоговый BAT: {exc}") from exc
        if completed.returncode != 0:
            raw = completed.stderr or completed.stdout or b""
            if isinstance(raw, bytes):
                detail = raw.decode("utf-8", errors="replace").strip()
            else:
                detail = str(raw).strip()
            raise RuntimeError(
                "winws отклонил итоговую стратегию"
                + (f": {detail[-1000:]}" if detail else f" (код {completed.returncode})")
            )

    def _bat_text(self, outcome: SearchOutcome, arguments: list[str]) -> str:
        needs_telegram_hosts = "telegram" in self._tcp_profiles(outcome)
        simulated_arguments = " ".join(arguments)
        simulated_arguments = (
            simulated_arguments
            .replace("%BIN%", ".\\")
            .replace("%LISTS%", "..\\lists\\")
            .replace("%GameFilterTCP%", "1024-65535")
            .replace("%GameFilterUDP%", "1024-65535")
        )
        simulated_command = 'start "zapret: strategy" /min ".\\winws.exe" ' + simulated_arguments
        if len(simulated_command) > MAX_SAFE_CMD_COMMAND_LENGTH:
            raise RuntimeError(
                "Итоговая команда BAT превышает безопасный лимит cmd.exe"
            )
        lines = [
            "@echo off",
            "chcp 65001 > nul",
            f":: {ADAPTIVE_MARKER}",
            f":: {TELEGRAM_HOSTS_MARKER if needs_telegram_hosts else 'ZAPRETGUI_ADAPTIVE_TELEGRAM_HOSTS=0'}",
            ":: Generated and validated by Zapret GUI adaptive selection",
            ":: Fixed-service rules are first; shared lists are applied afterwards.",
            ":: GameFilter extras use the conservative bundled general profile (not adaptively probed).",
            "",
            "cd /d \"%~dp0..\\..\\core\"",
            "call service.bat status_zapret",
            "call service.bat check_updates",
            "call service.bat load_game_filter",
            "call service.bat load_user_lists",
            "echo:",
            "",
            "set \"BIN=%~dp0..\\..\\core\\bin\\\"",
            "cd /d \"%BIN%\"",
            # Keep repeated expansions short enough for cmd.exe's 8191-char
            # command limit. The direct GUI launcher expands both placeholders
            # to absolute paths before calling CreateProcess.
            "set \"BIN=.\\\"",
            "set \"LISTS=..\\lists\\\"",
            "",
        ]
        if not arguments:
            raise ValueError("Итоговая стратегия не содержит аргументов winws")
        first, *remaining = arguments
        lines.append(f'start "zapret: %~n0" /min "%BIN%winws.exe" {first} ^')
        for index, argument in enumerate(remaining):
            continuation = " ^" if index < len(remaining) - 1 else ""
            lines.append(argument + continuation)
        lines.append("")
        return "\r\n".join(lines)

    def _strategy_options(self, strategy: Strategy, for_bat: bool) -> list[str]:
        if not for_bat:
            return strategy.render(
                self.paths.fake_tls,
                self.paths.fake_quic,
                self.paths.fake_tls_max,
                self.paths.fake_tls_4pda,
            )
        replacements = {
            "{fake_tls}": self._bin_reference("tls_clienthello_www_google_com.bin", True),
            "{fake_tls_max}": self._bin_reference("tls_clienthello_max_ru.bin", True),
            "{fake_tls_4pda}": self._bin_reference("tls_clienthello_4pda_to.bin", True),
            "{fake_stun}": self._bin_reference("stun.bin", True),
            "{fake_stun2}": self._bin_reference("stun2.bin", True),
            "{fake_tls_sochi}": self._bin_reference("tls_clienthello_sochi_park.bin", True),
            "{fake_discord_active}": self._bin_reference("ACTIVE_DISCORD_UDP.bin", True),
            "{fake_quic}": self._bin_reference("quic_initial_www_google_com.bin", True),
        }
        rendered: list[str] = []
        for option in strategy.options:
            value = option
            for placeholder, replacement in replacements.items():
                value = value.replace(placeholder, replacement)
            rendered.append(value)
        return rendered

    def _bin_reference(self, filename: str, for_bat: bool) -> str:
        if for_bat:
            return f'"%BIN%{filename}"'
        return str(self.paths.winws_dir / filename)

    @staticmethod
    def _hostlist_domains_argument(hosts: list[str], for_bat: bool) -> str:
        domains = ",".join(hosts)
        if for_bat:
            # Keep the option name outside quotes. A continuation line which
            # starts with a quoted token terminates cmd.exe's preceding `^`
            # chain, causing the remaining winws options to run as commands.
            return f'--hostlist-domains="{domains}"'
        return "--hostlist-domains=" + domains

    @staticmethod
    def _ordered_profiles(profiles: dict[str, Strategy]) -> list[str]:
        rank = {name: index for index, name in enumerate(_PROFILE_ORDER)}
        return sorted(profiles, key=lambda name: (rank.get(name, len(rank)), name.casefold()))

    @staticmethod
    def _tcp_profiles(outcome: SearchOutcome) -> dict[str, Strategy]:
        if outcome.tcp_profiles:
            return dict(outcome.tcp_profiles)
        return {"custom": outcome.tcp_strategy} if outcome.tcp_strategy else {}

    @staticmethod
    def _quic_profiles(outcome: SearchOutcome) -> dict[str, Strategy]:
        if outcome.quic_profiles:
            return dict(outcome.quic_profiles)
        return {"custom": outcome.quic_strategy} if outcome.quic_strategy else {}


def profile_requires_telegram_hosts(path: Path | str) -> bool:
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return False
    return ADAPTIVE_MARKER in text and TELEGRAM_HOSTS_MARKER in text
