from __future__ import annotations

import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1] / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

import os
import re
import subprocess
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from adaptive_strategy.catalog import QUIC_STRATEGIES, tcp_strategy_by_id
from adaptive_strategy.generator import (
    ADAPTIVE_MARKER,
    ZapretGuiBatGenerator,
    normalize_strategy_name,
    normalized_strategy_stem,
    profile_requires_telegram_hosts,
    validate_strategy_name,
)
from adaptive_strategy.models import SearchOutcome
from adaptive_strategy.probe import parse_targets
from adaptive_strategy.runtime import CREATE_NO_WINDOW, RuntimePaths, system_executable


FIXED_TARGETS = """
https://www.youtube.com/generate_204
https://discord.com/api/v10/gateway
https://rutracker.org/forum/index.php
"""


def make_runtime_paths(root: Path) -> RuntimePaths:
    bin_dir = root / "core" / "bin"
    validators = root / "user" / "adaptive-runtime"
    paths = RuntimePaths(
        project_root=root,
        bundle_root=validators,
        winws_dir=bin_dir,
        winws=bin_dir / "winws.exe",
        fake_tls=bin_dir / "tls_clienthello_www_google_com.bin",
        fake_tls_max=bin_dir / "tls_clienthello_max_ru.bin",
        fake_tls_4pda=bin_dir / "tls_clienthello_4pda_to.bin",
        fake_quic=bin_dir / "quic_initial_www_google_com.bin",
        fake_udp_dbank=bin_dir / "quic_initial_dbankcloud_ru.bin",
        fake_discord=bin_dir / "ACTIVE_DISCORD_UDP.bin",
        fake_stun=bin_dir / "stun.bin",
        cygwin_bash=validators / "cygwin" / "bin" / "bash.exe",
        cygwin_curl=validators / "cygwin" / "usr" / "local" / "bin" / "curl.exe",
        cygwin_curl_kyber=validators / "cygwin" / "usr" / "local" / "bin" / "curl-kyber.exe",
        browser=None,
    )
    for path in (
        paths.fake_tls,
        paths.fake_tls_max,
        paths.fake_tls_4pda,
        paths.fake_quic,
        paths.fake_udp_dbank,
        paths.fake_stun,
        paths.winws_dir / "stun2.bin",
        paths.winws_dir / "tls_clienthello_sochi_park.bin",
        paths.winws_dir / "ACTIVE_DISCORD_UDP.bin",
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"test-runtime-component")
    return paths


class StrategyNameTests(unittest.TestCase):
    def test_cyrillic_name_and_bat_extension_are_supported(self) -> None:
        self.assertEqual(
            "Моя стратегия.bat",
            normalize_strategy_name("  Моя   стратегия.BAT  "),
        )

    def test_invalid_filename_characters_and_emoji_are_rejected(self) -> None:
        invalid_names = (
            "bad/name",
            "bad\\name",
            "bad:name",
            "bad*name",
            "bad?name",
            'bad"name',
            "bad<name",
            "bad>name",
            "bad|name",
            "Стратегия🙂",
            ".hidden",
            "name.",
        )
        for value in invalid_names:
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalized_strategy_stem(value, lang="en")

    def test_windows_device_names_are_rejected_even_with_extensions(self) -> None:
        for value in ("CON", "con.txt", "NUL.bat", "Lpt9.BAT", "COM1.profile"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    normalized_strategy_stem(value, lang="en")

    def test_user_supplied_bat_extension_is_normalized_not_duplicated(self) -> None:
        self.assertEqual("Adaptive 3.bat", normalize_strategy_name("Adaptive 3.bat"))
        self.assertEqual("Adaptive 3.bat", normalize_strategy_name("Adaptive 3.BAT"))

    def test_collision_check_is_case_insensitive(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            destination = Path(temporary)
            (destination / "Моя Стратегия.BAT").write_bytes(b"existing")

            ok, message, filename = validate_strategy_name(
                "моя стратегия",
                str(destination),
                lang="en",
            )

            self.assertFalse(ok)
            self.assertTrue(message)
            self.assertEqual("моя стратегия.bat", filename)

    def test_generator_and_runtime_accept_string_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            runtime = RuntimePaths.for_zapret_gui(str(root), str(root / "runtime"))
            generator = ZapretGuiBatGenerator(runtime, str(root / "user" / "strategies"))

            self.assertEqual(root.resolve(), runtime.project_root)
            self.assertEqual((root / "runtime").resolve(), runtime.bundle_root)
            self.assertEqual((root / "user" / "strategies").resolve(), generator.strategies_dir)

    def test_empty_name_uses_a_deterministic_timestamped_default(self) -> None:
        filename = normalize_strategy_name(
            "   ",
            now=datetime(2026, 9, 2, 21, 5, 7),
        )

        self.assertEqual("NewAdaptiveBAT_2026-09-02_21-05-07.bat", filename)


class OneBatGeneratorTests(unittest.TestCase):
    @staticmethod
    def _split_segments(arguments: list[str]) -> list[list[str]]:
        segments: list[list[str]] = [[]]
        for argument in arguments:
            if argument == "--new":
                segments.append([])
            else:
                segments[-1].append(argument)
        return segments

    def test_generate_writes_one_self_contained_profile_and_dry_runs_runtime_args(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            strategies_dir = root / "user" / "strategies"
            paths = make_runtime_paths(root)
            targets = parse_targets(FIXED_TARGETS, include_quic=True)
            outcome = SearchOutcome(
                True,
                targets,
                [],
                # Deliberately use the wrong insertion order: generator must impose
                # first-match ordering itself.
                tcp_profiles={
                    "discord_app": tcp_strategy_by_id("ts-hostfakesplit-mail-sochi"),
                    "custom": tcp_strategy_by_id("ts-fake"),
                    "youtube": tcp_strategy_by_id("disorder-midsld"),
                    "discord_update": tcp_strategy_by_id("ipid-hostfakesplit-google"),
                },
                quic_profiles={"youtube": QUIC_STRATEGIES[0]},
            )
            generator = ZapretGuiBatGenerator(paths, strategies_dir)
            runtime_arguments = generator.build_arguments(outcome, for_bat=False)

            with patch.object(generator, "_dry_run") as dry_run:
                destination = generator.generate(outcome, "Рабочая стратегия")

            dry_run.assert_called_once_with(runtime_arguments)
            self.assertFalse(any("%BIN%" in argument for argument in dry_run.call_args.args[0]))
            self.assertFalse(any("%LISTS%" in argument for argument in dry_run.call_args.args[0]))
            self.assertFalse(any("%GameFilter" in argument for argument in dry_run.call_args.args[0]))
            self.assertEqual(destination, outcome.output_dir)
            self.assertEqual("Рабочая стратегия.bat", destination.name)

            generated_files = [path for path in strategies_dir.rglob("*") if path.is_file()]
            self.assertEqual([destination], generated_files)
            content = destination.read_text(encoding="utf-8-sig")
            self.assertIn(ADAPTIVE_MARKER, content)
            self.assertNotIn("ZAPRETGUI_ADAPTIVE_TELEGRAM_HOSTS=1", content)
            self.assertFalse(profile_requires_telegram_hosts(destination))
            self.assertIn("--hostlist-domains=", content)
            self.assertIn('--hostlist="%LISTS%list-general.txt"', content)
            self.assertIn('--hostlist="%LISTS%list-general-user.txt"', content)
            self.assertIn('--hostlist-exclude="%LISTS%list-exclude.txt"', content)
            self.assertIn('--hostlist-exclude="%LISTS%list-exclude-user.txt"', content)
            self.assertIn('--ipset="%LISTS%ipset-all.txt"', content)
            self.assertIn('--ipset-exclude="%LISTS%ipset-exclude.txt"', content)
            self.assertIn('--ipset-exclude="%LISTS%ipset-exclude-user.txt"', content)
            self.assertIn("%GameFilterTCP%", content)
            self.assertIn("%GameFilterUDP%", content)
            self.assertIn("conservative bundled general profile", content)
            self.assertNotIn(".search-hosts-", content)
            self.assertNotIn(".json", content)

            for hostname in (
                "www.youtube.com",
                "discord.com",
                "updates.discord.com",
                "rutracker.org",
            ):
                self.assertIn(hostname, content)

            segments = self._split_segments(runtime_arguments)
            updater_index = next(
                index
                for index, segment in enumerate(segments)
                if "--filter-tcp=443" in segment
                and any("updates.discord.com" in argument for argument in segment)
                and not any("^discord.com" in argument for argument in segment)
            )
            app_index = next(
                index
                for index, segment in enumerate(segments)
                if "--filter-tcp=443" in segment
                and any("^discord.com" in argument for argument in segment)
            )
            self.assertLess(updater_index, app_index)

            first_shared_list_index = next(
                index
                for index, segment in enumerate(segments)
                if any("list-general.txt" in argument for argument in segment)
            )
            last_fixed_service_index = max(
                index
                for index, segment in enumerate(segments)
                if any("--hostlist-domains=" in argument for argument in segment)
            )
            self.assertGreater(first_shared_list_index, last_fixed_service_index)

            custom_options = set(tcp_strategy_by_id("ts-fake").render(
                paths.fake_tls,
                paths.fake_quic,
                paths.fake_tls_max,
                paths.fake_tls_4pda,
            ))
            shared_tcp_segments = [
                segment for segment in segments
                if any("list-general.txt" in argument for argument in segment)
                and "--filter-tcp=80,443" in segment
            ]
            self.assertEqual(1, len(shared_tcp_segments))
            self.assertTrue(custom_options.issubset(set(shared_tcp_segments[0])))

            runtime_lists_dir = str((paths.winws_dir.parent / "lists").resolve())
            runtime_list_arguments = [
                argument for argument in runtime_arguments
                if argument.startswith(("--hostlist=", "--hostlist-exclude=", "--ipset=", "--ipset-exclude="))
            ]
            self.assertTrue(runtime_list_arguments)
            self.assertTrue(all(runtime_lists_dir in argument for argument in runtime_list_arguments))
            self.assertIn("--filter-tcp=12", runtime_arguments)
            self.assertIn("--filter-udp=12", runtime_arguments)

            bat_hostlists = [
                argument for argument in generator.build_arguments(outcome, for_bat=True)
                if "--hostlist-domains=" in argument
            ]
            self.assertTrue(bat_hostlists)
            self.assertFalse(any(argument.startswith('"--hostlist-domains=') for argument in bat_hostlists))
            self.assertTrue(any(argument.startswith('--hostlist-domains="') for argument in bat_hostlists))

    def test_missing_bin_is_repaired_before_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = make_runtime_paths(root)
            paths.fake_udp_dbank.unlink()
            outcome = SearchOutcome(
                True,
                parse_targets(FIXED_TARGETS, include_quic=True),
                [],
                tcp_profiles={"custom": tcp_strategy_by_id("ts-fake")},
                quic_profiles={"youtube": QUIC_STRATEGIES[0]},
            )
            import shutil

            runtime_source = root / "runtime-source"
            shutil.copytree(
                Path(__file__).resolve().parents[1] / "resources" / "adaptive-runtime",
                runtime_source,
            )
            generator = ZapretGuiBatGenerator(
                paths,
                root / "user" / "strategies",
                runtime_source=runtime_source,
            )
            with patch.object(generator, "_dry_run"):
                generator.generate(outcome, "recovered")

            self.assertTrue(paths.fake_udp_dbank.is_file())

    def test_missing_bin_reports_runtime_source_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            paths = make_runtime_paths(root)
            paths.fake_udp_dbank.unlink()
            outcome = SearchOutcome(
                True,
                parse_targets(FIXED_TARGETS, include_quic=True),
                [],
                tcp_profiles={"custom": tcp_strategy_by_id("ts-fake")},
                quic_profiles={"youtube": QUIC_STRATEGIES[0]},
            )
            generator = ZapretGuiBatGenerator(
                paths,
                root / "user" / "strategies",
                runtime_source=root / "missing-official-runtime",
            )
            with self.assertRaisesRegex(
                RuntimeError,
                r"(?s)Не удалось восстановить компонент runtime.*нет доступа к официальному источнику обновления",
            ):
                generator.generate(outcome, "unavailable")
            self.assertFalse((root / "user" / "strategies" / "unavailable.bat").exists())

    def test_atomic_publish_does_not_replace_a_racing_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            strategies_dir = root / "user" / "strategies"
            paths = make_runtime_paths(root)
            targets = parse_targets("https://www.youtube.com/generate_204")
            outcome = SearchOutcome(
                True,
                targets,
                [],
                tcp_profiles={"youtube": tcp_strategy_by_id("disorder-midsld")},
            )
            generator = ZapretGuiBatGenerator(paths, strategies_dir)
            original_publish = generator._publish_without_overwrite

            def create_collision(temporary_path: Path, destination: Path) -> None:
                destination.write_bytes(b"existing strategy")
                original_publish(temporary_path, destination)

            with (
                patch.object(generator, "_dry_run"),
                patch.object(generator, "_publish_without_overwrite", side_effect=create_collision),
                self.assertRaises(ValueError),
            ):
                generator.generate(outcome, "Race")

            self.assertEqual(b"existing strategy", (strategies_dir / "Race.bat").read_bytes())
            self.assertEqual([], list(strategies_dir.glob("*.installing")))

    @unittest.skipUnless(os.name == "nt", "cmd.exe BAT parsing is Windows-specific")
    def test_bat_arguments_survive_real_cmd_parser(self) -> None:
        repository_root = Path(__file__).resolve().parents[1]
        paths = RuntimePaths.for_zapret_gui(
            repository_root / "resources",
            repository_root / "resources" / "adaptive-runtime",
        )
        if not paths.winws.is_file():
            self.skipTest("resources/core/bin/winws.exe is not available")

        targets = parse_targets(FIXED_TARGETS, include_quic=True)
        outcome = SearchOutcome(
            True,
            targets,
            [],
            tcp_profiles={
                "discord_app": tcp_strategy_by_id("ts-hostfakesplit-mail-sochi"),
                "custom": tcp_strategy_by_id("ts-fake"),
                "youtube": tcp_strategy_by_id("disorder-midsld"),
                "discord_update": tcp_strategy_by_id("ipid-hostfakesplit-google"),
            },
            quic_profiles={"youtube": QUIC_STRATEGIES[0]},
        )
        generator = ZapretGuiBatGenerator(paths, Path(tempfile.gettempdir()))
        arguments = generator.build_arguments(outcome, for_bat=True)
        expected_profiles = arguments.count("--new") + 1
        first, *remaining = arguments
        lines = [
            "@echo off",
            'set "BIN=.\\"',
            'set "LISTS=..\\lists\\"',
            'set "GameFilterTCP=12"',
            'set "GameFilterUDP=12"',
            f'"{paths.winws}" --dry-run {first} ^',
        ]
        for index, argument in enumerate(remaining):
            continuation = " ^" if index < len(remaining) - 1 else ""
            lines.append(argument + continuation)

        with tempfile.TemporaryDirectory() as temporary:
            smoke_bat = Path(temporary) / "adaptive-cmd-smoke.bat"
            smoke_bat.write_bytes(("\r\n".join(lines) + "\r\n").encode("utf-8-sig"))
            completed = subprocess.run(
                [system_executable("cmd.exe"), "/d", "/c", str(smoke_bat)],
                cwd=paths.winws_dir,
                capture_output=True,
                timeout=20,
                creationflags=CREATE_NO_WINDOW,
                check=False,
            )

        stdout = completed.stdout.decode("utf-8", errors="replace")
        stderr = completed.stderr.decode("utf-8", errors="replace")
        self.assertEqual(0, completed.returncode, stderr or stdout)
        match = re.search(r"we have (\d+) user defined desync profile", stdout)
        self.assertIsNotNone(match, stdout)
        self.assertEqual(expected_profiles, int(match.group(1)))


if __name__ == "__main__":
    unittest.main()
