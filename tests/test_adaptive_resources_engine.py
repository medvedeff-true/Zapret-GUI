from __future__ import annotations

import hashlib
import json
import subprocess
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from adaptive_strategy.engine import SearchCancelled, SearchEngine
from adaptive_strategy.models import ProbeResult, Protocol, Target
from adaptive_strategy.resources import (
    _OBSOLETE_NOTICE_SHA256,
    ensure_adaptive_runtime,
    load_runtime_manifest,
)
from adaptive_strategy.runtime import RuntimePaths, runtime_helper_errors


def make_runtime_paths(root: Path) -> RuntimePaths:
    bin_dir = root / "core" / "bin"
    validators = root / "user" / "adaptive-runtime"
    return RuntimePaths(
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


def write_manifest(source: Path, files: dict[str, bytes]) -> None:
    entries = []
    for relative, data in files.items():
        path = source / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        entries.append(
            {
                "path": relative,
                "size": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
    (source / "manifest.json").write_text(
        json.dumps({"schema": 1, "version": "test-runtime", "files": entries}),
        encoding="utf-8",
    )


class RuntimeManifestInstallerTests(unittest.TestCase):
    def test_runtime_paths_require_dbank_fake_udp_component(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = make_runtime_paths(Path(temporary))
            self.assertIn(paths.fake_udp_dbank, paths.missing())

    def test_packaged_runtime_does_not_include_notice_file(self) -> None:
        packaged = Path(__file__).resolve().parents[1] / "resources" / "adaptive-runtime"
        manifest = load_runtime_manifest(packaged)

        self.assertEqual("https://github.com/bol-van/zapret-win-bundle", manifest["source"])
        self.assertNotIn("NOTICE.txt", [entry["path"] for entry in manifest["files"]])
        self.assertIn(
            "core/bin/quic_initial_dbankcloud_ru.bin",
            [entry["path"] for entry in manifest["files"]],
        )
        self.assertFalse((packaged / "NOTICE.txt").exists())

    def test_installer_reuses_verified_files_and_repairs_corruption(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "packaged"
            destination = root / "installed"
            files = {
                "cygwin/bin/bash.exe": b"bash-binary",
                "cygwin/usr/local/bin/curl.exe": b"curl-binary",
            }
            write_manifest(source, files)
            destination.mkdir(parents=True)
            unknown = destination / "user-note.txt"
            unknown.write_text("keep me", encoding="utf-8")

            first = ensure_adaptive_runtime(source, destination)
            second = ensure_adaptive_runtime(source, destination)

            self.assertEqual(2, first["copied"])
            self.assertEqual(0, first["reused"])
            self.assertEqual(0, second["copied"])
            self.assertEqual(2, second["reused"])
            self.assertEqual("keep me", unknown.read_text(encoding="utf-8"))

            damaged_relative = "cygwin/bin/bash.exe"
            damaged = destination / damaged_relative
            # Keep the original size so this specifically proves hash checking.
            damaged.write_bytes(b"X" * len(files[damaged_relative]))
            (destination / "manifest.json").write_text("corrupt manifest", encoding="utf-8")

            repaired = ensure_adaptive_runtime(source, destination)

            self.assertEqual(1, repaired["copied"])
            self.assertEqual(1, repaired["reused"])
            self.assertEqual(files[damaged_relative], damaged.read_bytes())
            self.assertEqual(
                (source / "manifest.json").read_bytes(),
                (destination / "manifest.json").read_bytes(),
            )
            self.assertEqual([], list(destination.rglob("*.installing")))

    def test_installer_repairs_project_runtime_component(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "packaged"
            destination = root / "installed"
            write_manifest(
                source,
                {"core/bin/quic_initial_dbankcloud_ru.bin": b"dbank-component"},
            )
            manifest_path = source / "manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["files"][0]["destination"] = "project/core/bin/quic_initial_dbankcloud_ru.bin"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            ensure_adaptive_runtime(source, destination, project_root=root)

            restored = root / "core/bin/quic_initial_dbankcloud_ru.bin"
            self.assertEqual(b"dbank-component", restored.read_bytes())

    def test_installer_removes_only_the_legacy_generated_notice(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "packaged"
            destination = root / "installed"
            write_manifest(source, {"cygwin/bin/bash.exe": b"bash-binary"})
            destination.mkdir()
            notice = destination / "NOTICE.txt"
            notice.write_text(
                "legacy generated notice", encoding="utf-8"
            )

            with patch(
                "adaptive_strategy.resources._sha256",
                side_effect=lambda path: (
                    _OBSOLETE_NOTICE_SHA256
                    if path == notice
                    else hashlib.sha256(path.read_bytes()).hexdigest()
                ),
            ):
                ensure_adaptive_runtime(source, destination)

            self.assertFalse(notice.exists())

    def test_helper_preflight_executes_both_cygwin_curl_variants(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = make_runtime_paths(Path(temporary))
            successful = subprocess.CompletedProcess([], 0, b"", b"")
            with (
                patch.object(RuntimePaths, "missing", return_value=[]),
                patch("adaptive_strategy.runtime.run_external", return_value=successful) as run,
            ):
                errors = runtime_helper_errors(paths)

            self.assertEqual([], errors)
            commands = [call.args[0] for call in run.call_args_list]
            shell_commands = [
                command[-1]
                for command in commands
                if command and command[0] == str(paths.cygwin_bash)
            ]
            self.assertTrue(any("/usr/local/bin/curl --version" in command for command in shell_commands))
            self.assertTrue(any("/usr/local/bin/curl-kyber --version" in command for command in shell_commands))


class RecordingProbeRunner:
    def __init__(self, result_factory):
        self.result_factory = result_factory
        self.calls: list[tuple[list[tuple[Target, Protocol, str]], int]] = []

    def probe_many(self, requests, workers=8):
        copied = list(requests)
        self.calls.append((copied, workers))
        return [self.result_factory(*request) for request in copied]


class SearchEngineRegressionTests(unittest.TestCase):
    def test_discord_update_has_its_specialized_baseline_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            paths = make_runtime_paths(Path(temporary))
            target = Target(
                "https://updates.discord.com/distributions/app/manifests/latest?channel=stable&platform=win&arch=x64",
                "updates.discord.com",
                service="discord",
                profile="discord_update",
                validator="discord_update",
            )
            runner = RecordingProbeRunner(
                lambda requested_target, _protocol, validator: ProbeResult(
                    requested_target,
                    validator,
                    True,
                    200,
                    0.01,
                    remote_ip="203.0.113.10",
                )
            )
            engine = SearchEngine(paths)
            engine.probes = runner

            with patch(
                "adaptive_strategy.engine.dns_addresses_with_deadline",
                return_value={target: ["203.0.113.10"]},
            ):
                outcome = engine._run([target], {"discord_update": [target]})

            self.assertEqual("baseline-reachable", outcome.confidence)
            self.assertEqual(1, len(runner.calls))
            requests, _workers = runner.calls[0]
            self.assertEqual([(target, Protocol.HTTPS, "discord_update")], requests)
            self.assertEqual("discord_update", outcome.baseline[0].validator)

    def test_transient_failure_is_retried_and_replaced_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Target("https://example.test/", "example.test")
            request = (target, Protocol.HTTPS, "cygwin")
            failed = ProbeResult(target, "cygwin", False, None, 0.01, error="temporary")
            runner = RecordingProbeRunner(
                lambda requested_target, _protocol, validator: ProbeResult(
                    requested_target,
                    validator,
                    True,
                    200,
                    0.01,
                    remote_ip="203.0.113.20",
                )
            )
            engine = SearchEngine(make_runtime_paths(Path(temporary)))
            engine.probes = runner

            with patch("adaptive_strategy.engine.time.sleep", return_value=None):
                results = engine._retry_failed_probes([request], [failed])

            self.assertTrue(results[0].success)
            self.assertEqual(1, len(runner.calls))
            self.assertEqual([request], runner.calls[0][0])
            self.assertEqual(1, runner.calls[0][1])

    def test_cancellation_during_retry_delay_prevents_the_retry_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cancel_event = threading.Event()
            target = Target("https://example.test/", "example.test")
            request = (target, Protocol.HTTPS, "cygwin")
            failed = ProbeResult(target, "cygwin", False, None, 0.01, error="temporary")
            runner = RecordingProbeRunner(
                lambda *_args: self.fail("probe_many must not run after cancellation")
            )
            engine = SearchEngine(make_runtime_paths(Path(temporary)), cancel_event=cancel_event)
            engine.probes = runner

            with patch("adaptive_strategy.engine.time.sleep", side_effect=lambda _seconds: cancel_event.set()):
                with self.assertRaises(SearchCancelled):
                    engine._retry_failed_probes([request], [failed])

            self.assertEqual([], runner.calls)


if __name__ == "__main__":
    unittest.main()
