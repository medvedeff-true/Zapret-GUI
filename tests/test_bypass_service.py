from __future__ import annotations

import ctypes
import gzip
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import threading
import time
import tracemalloc
import unittest
import uuid
from unittest import mock

import psutil
import bypass_service as client


ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(os.name == "nt", "Windows process/pipe integration")
class ServiceIntegrationTests(unittest.TestCase):
    """Real Win32 processes and IPC, with an inert engine that never opens WinDivert."""

    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="zapret-service-test-")
        cls.root = Path(cls.temp.name)
        (cls.root / "engine").mkdir()
        source = cls.root / "FakeEngine.cs"
        source.write_text(r'''
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Threading;
using System.Text;
class FakeEngine {
    [DllImport("kernel32.dll")] static extern IntPtr GetConsoleWindow();
    static int Main(string[] args) {
        Console.OutputEncoding = Encoding.UTF8;
        Console.WriteLine("console=" + GetConsoleWindow());
        foreach (string arg in args) Console.WriteLine("arg=" + arg);
        if (Array.IndexOf(args, "--comment=exit") >= 0) { Console.Error.WriteLine("driver denied (test)"); return 42; }
        if (Array.IndexOf(args, "--comment=app-ready") >= 0)
            Console.WriteLine("medvedeff-winws: application capture ready");
        if (Array.IndexOf(args, "--comment=tree") >= 0) {
            var si = new ProcessStartInfo(Process.GetCurrentProcess().MainModule.FileName);
            si.UseShellExecute = false; si.CreateNoWindow = true;
            Console.WriteLine("descendant=" + Process.Start(si).Id);
        }
        if (Array.IndexOf(args, "--dry-run") >= 0) return 0;
        Thread.Sleep(60000); return 0;
    }
}''', encoding="utf-8")
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        subprocess.run([str(compiler), "/nologo", "/out:" + str(cls.root / "engine/winws.exe"), str(source)],
                       check=True, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
        app_engine = cls.root / "engine/medvedeff-winws/medvedeff-winws.exe"
        app_engine.parent.mkdir()
        shutil.copyfile(cls.root / "engine/winws.exe", app_engine)
        (cls.root / "engine.sha256").write_text("test-engine", encoding="ascii")
        cls.sid = client.current_user_sid()

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def setUp(self):
        self.name = "ZapretGUI.Test." + uuid.uuid4().hex
        self.host = subprocess.Popen([
            str(ROOT / "resources/background_service/ZapretGUI.Service.exe"), "--test-host", self.sid, str(self.root), self.name,
        ], creationflags=subprocess.CREATE_NO_WINDOW)
        self.pipe = None
        error = ""
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            try:
                self.pipe = client.Pipe(self.name, authenticate=False)
                break
            except OSError as exc:
                error = str(exc)
                time.sleep(0.1)
        if self.pipe is None:
            self.host.kill()
            self.host.wait(timeout=10)
            log = self.root / "service-last-error.txt"
            self.fail("Test service pipe did not open: " + error + "\n" + (log.read_text(encoding="utf-8-sig") if log.exists() else "no service log"))

    def tearDown(self):
        log = self.root / "service-last-error.txt"
        if log.exists():
            print(log.read_text(encoding="utf-8-sig"))
            log.unlink()
        if self.pipe:
            try:
                self.pipe.request({"op": "stop"})
            except (OSError, RuntimeError, ValueError):
                pass
            self.pipe.close()
        self.host.kill()
        self.host.wait(timeout=10)

    def start(self, value="running", **extra):
        return self.pipe.request({"op": "start", "args": [{"name": "comment", "value": value}], **extra})

    def wait_stopped(self, pid):
        deadline = time.monotonic() + 6
        while psutil.pid_exists(pid) and time.monotonic() < deadline:
            time.sleep(0.05)
        self.assertFalse(psutil.pid_exists(pid), "Process survived its owner/job")

    def test_launch_has_no_console_and_stop_waits_for_exit(self):
        result = self.start('Кириллица with "quotes" and trailing\\')
        self.assertTrue(result["running"])
        self.assertIn("console=0", result["log"])
        self.assertIn('arg=--comment=Кириллица with "quotes" and trailing\\', result["log"])
        self.assertFalse(self.pipe.request({"op": "stop"})["running"])
        self.wait_stopped(result["pid"])

    def test_disconnect_kills_the_entire_process_tree(self):
        result = self.start("tree")
        descendant = int(result["log"].split("descendant=")[1].splitlines()[0])
        self.pipe.close()
        self.wait_stopped(result["pid"])
        self.wait_stopped(descendant)

    def test_service_crash_kills_process(self):
        result = self.start()
        self.host.kill()
        self.host.wait(timeout=10)
        self.wait_stopped(result["pid"])

    def test_early_exit_reports_exit_code_and_stderr(self):
        with self.assertRaisesRegex(RuntimeError, "42.*driver denied"):
            # Dot must include newline because the native output is preserved.
            try:
                self.start("exit")
            except RuntimeError as exc:
                raise RuntimeError(str(exc).replace("\n", " "))
        self.assertFalse(self.pipe.request({"op": "status"})["running"])

    def test_service_rejects_arbitrary_files_executables_and_option_abbreviations(self):
        for args in (
            [{"name": "pidfile", "value": r"C:\Windows\test.txt"}],
            [{"name": "debug", "value": r"@C:\Windows\test.txt"}],
            [{"name": "hostlist", "value": r"C:\Windows\win.ini"}],
            [{"name": "dpi-desync-fake-tls", "value": r"@C:\Windows\win.ini"}],
            [{"name": "wf-raw", "value": r"@C:\Windows\win.ini"}],
            [{"name": "lua-init", "value": "arbitrary"}],
            [{"name": "daemon"}], [{"name": "debugger"}], [{"name": "hostlist-a", "value": "any"}],
        ):
            with self.subTest(args=args), self.assertRaises(RuntimeError):
                self.pipe.request({"op": "start", "args": args})
        self.assertFalse(self.pipe.request({"op": "status"})["running"])

    def test_uploaded_files_are_materialized_without_caller_paths(self):
        source = self.root / "uploaded.txt"
        source.write_bytes(b"example.com\n")
        request = client.profile_request(subprocess.list2cmdline([
            str(self.root / "winws.exe"), "--hostlist=" + str(source),
        ]), self.root)
        result = self.pipe.request(request)
        staged = result["log"].split("arg=--hostlist=")[1].splitlines()[0]
        self.assertEqual(Path(staged).read_text(), "example.com\n")
        self.pipe.request({"op": "stop"})
        self.assertFalse(Path(staged).exists())

    def test_application_engine_launch_waits_for_capture_ready_and_stages_scope(self):
        source = self.root / "applications.txt"
        source.write_bytes(b"C:\\Browser\\browser.exe\n")
        request = client.profile_request(subprocess.list2cmdline([
            str(self.root / "medvedeff-winws/medvedeff-winws.exe"),
            "--app-scope-file=" + str(source), "--comment=app-ready",
        ]), self.root)
        result = self.pipe.request(request)
        self.assertEqual(Path(psutil.Process(result["pid"]).exe()).name, "medvedeff-winws.exe")
        staged = Path(result["log"].split("arg=--app-scope-file=")[1].splitlines()[0])
        self.assertNotEqual(source, staged)
        self.assertEqual(source.read_bytes(), staged.read_bytes())
        self.pipe.request({"op": "stop"})
        self.assertFalse(staged.exists())

    def test_application_engine_does_not_report_running_without_capture_ready(self):
        source = self.root / "applications.txt"
        source.write_bytes(b"C:\\Browser\\browser.exe\n")
        request = client.profile_request(subprocess.list2cmdline([
            str(self.root / "medvedeff-winws/medvedeff-winws.exe"),
            "--app-scope-file=" + str(source),
        ]), self.root)
        with self.assertRaisesRegex(RuntimeError, "did not initialize application capture"):
            self.pipe.request(request)
        self.assertFalse(self.pipe.request({"op": "status"})["running"])

    def test_bundled_application_engine_validates_alt13_with_real_binary(self):
        from PyQt6.QtCore import QSettings
        import EzUnBlock as app

        core = ROOT / "resources/core"
        source = self.root / "applications.txt"
        source.write_bytes("C:\\Program Files\\Браузер\\firefox.exe\n".encode("utf-8"))
        settings = QSettings(str(self.root / "app-profile-test.ini"), QSettings.Format.IniFormat)
        command = app._build_game_mode_winws_command(
            str(core / "general (ALT13).bat"), str(core), settings,
            traffic_mode=app.TRAFFIC_MODE_APPLICATIONS, app_scope_path=str(source),
        )
        request = client.profile_request(command, core / "bin")
        request["op"] = "validate"
        engine = self.root / "engine/medvedeff-winws"
        backup = engine.with_name("fake-app-engine")
        engine.rename(backup)
        try:
            shutil.copytree(core / "bin/medvedeff-winws", engine)
            result = self.pipe.request(request)
            self.assertEqual(result["exit_code"], 0, result.get("log"))
        finally:
            shutil.rmtree(engine)
            backup.rename(engine)

    def test_second_start_does_not_orphan_first_process(self):
        result = self.start()
        with self.assertRaisesRegex(RuntimeError, "already running"):
            self.start()
        self.assertEqual(self.pipe.request({"op": "status"})["pid"], result["pid"])

    def test_large_streamed_list_has_bounded_memory_and_exact_contents(self):
        source = self.root / "large-hosts.txt"
        block = b"example.com\n" * 21845
        digest = hashlib.sha256()
        with source.open("wb") as stream:
            for _ in range(160):  # 40 MiB: above the former total-file limit.
                stream.write(block)
                digest.update(block)
        command = subprocess.list2cmdline([
            str(self.root / "winws.exe"), "--hostlist=" + str(source),
            "--hostlist-exclude=" + str(source),
        ])
        tracemalloc.start()
        try:
            request = client.profile_request(command, self.root)
            result = self.pipe.request(request)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self.assertLess(peak, 5 * 1024 * 1024)
        self.assertEqual(len(request["files"]), 1)
        staged = Path(result["log"].split("arg=--hostlist=")[1].splitlines()[0])
        self.assertEqual(staged.stat().st_size, source.stat().st_size)
        actual = hashlib.sha256()
        with staged.open("rb") as stream:
            for data in iter(lambda: stream.read(client.BLOCK_BYTES), b""):
                actual.update(data)
        self.assertEqual(actual.digest(), digest.digest())
        self.assertEqual(self.pipe.request({"op": "hello"})["protocol"], client.PROTOCOL)
        self.pipe.request({"op": "stop"})
        self.assertFalse(staged.exists())

    def test_gzip_input_is_not_double_compressed_or_reinterpreted(self):
        source = self.root / "hosts.txt.gz"
        source.write_bytes(gzip.compress(b"example.com\n" * 1000, mtime=0))
        request = client.profile_request(subprocess.list2cmdline([
            str(self.root / "winws.exe"), "--hostlist=" + str(source),
        ]), self.root)
        self.assertTrue(request["files"][0]["gzip"])
        self.assertFalse(request.sources[0].compress)
        result = self.pipe.request(request)
        staged = Path(result["log"].split("arg=--hostlist=")[1].splitlines()[0])
        self.assertTrue(str(staged).endswith(".dat.gz"))
        self.assertEqual(staged.read_bytes(), source.read_bytes())

    def test_invalid_upload_metadata_and_arguments_do_not_start_binary_transfer(self):
        for metadata, arguments in (
            ([{"size": -1}], [{"name": "hostlist", "file": 0}]),
            ([{"size": client.MAX_PROFILE_BYTES + 1}], [{"name": "hostlist", "file": 0}]),
            ([{"size": 0}] * 257, [{"name": "hostlist", "file": 0}]),
            ([{"size": 1}], [{"name": "pidfile", "file": 0}]),
            ([{"size": 0}], [{"name": "comment", "value": "unused upload"}]),
            ([{"size": client.MAX_PAYLOAD_BYTES + 1}], [{"name": "dpi-desync-fake-tls", "file": 0}]),
        ):
            with self.subTest(metadata=metadata[:1]), self.assertRaises(RuntimeError):
                self.pipe.request({"op": "start", "args": arguments, "files": metadata})
            self.assertFalse(self.pipe.request({"op": "status"})["running"])
            self.assertFalse(list((self.root / "runs").iterdir()))

    def test_corrupt_upload_is_rejected_and_staging_is_removed(self):
        self.pipe._send_control({
            "op": "start", "args": [{"name": "hostlist", "file": 0}],
            "files": [{"size": 3, "gzip": False}],
        })
        self.assertTrue(self.pipe._reply()["upload"])
        self.pipe._write(client.BLOCK_HEADER.pack(3, 3, 0) + b"abc")
        self.pipe._write(client.BLOCK_HEADER.pack(0, 0, 0) + bytes(32))
        with self.assertRaisesRegex(RuntimeError, "SHA-256"):
            self.pipe._reply()
        deadline = time.monotonic() + 3
        while list((self.root / "runs").iterdir()) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(list((self.root / "runs").iterdir()))

    def test_compressed_bomb_is_rejected_without_unbounded_expansion(self):
        self.pipe._send_control({
            "op": "start", "args": [{"name": "hostlist", "file": 0}],
            "files": [{"size": 1}],
        })
        self.assertTrue(self.pipe._reply()["upload"])
        bomb = gzip.compress(b"A" * (2 * client.BLOCK_BYTES))
        self.pipe._write(client.BLOCK_HEADER.pack(1, len(bomb), 1) + bomb)
        with self.assertRaisesRegex(RuntimeError, "declared size"):
            self.pipe._reply()
        self.assertFalse(list((self.root / "runs").iterdir()))

    def test_disconnect_during_upload_removes_partial_files(self):
        self.pipe._send_control({
            "op": "start", "args": [{"name": "hostlist", "file": 0}],
            "files": [{"size": 10 * client.BLOCK_BYTES}],
        })
        self.assertTrue(self.pipe._reply()["upload"])
        self.pipe._write(client.BLOCK_HEADER.pack(3, 3, 0) + b"abc")
        self.pipe.close()
        deadline = time.monotonic() + 3
        while list((self.root / "runs").iterdir()) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertFalse(list((self.root / "runs").iterdir()))

    def test_bundled_profiles_pass_real_winws_dry_run_through_protocol(self):
        if not ctypes.windll.shell32.IsUserAnAdmin():
            self.skipTest("Real winws has a requireAdministrator manifest; run this test elevated")
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtCore import QSettings
        import EzUnBlock as app
        real = self.root / "real-engine"
        shutil.copytree(ROOT / "resources/core/bin", real, dirs_exist_ok=True)
        fake = self.root / "engine"
        saved = self.root / "fake-engine"
        fake.rename(saved)
        real.rename(fake)
        try:
            settings = QSettings(str(self.root / "profile-test.ini"), QSettings.Format.IniFormat)
            profiles = list((ROOT / "resources/core").glob("general*.bat"))
            self.assertGreater(len(profiles), 20)
            for profile in profiles:
                with self.subTest(profile=profile.name):
                    command = app._build_game_mode_winws_command(str(profile), str(ROOT / "resources/core"), settings)
                    request = client.profile_request(command, ROOT / "resources/core/bin")
                    request["op"] = "validate"
                    result = self.pipe.request(request)
                    self.assertEqual(result["exit_code"], 0, result.get("log"))
        finally:
            fake.rename(real)
            saved.rename(fake)

    def test_all_bundled_profiles_pass_streaming_protocol_with_inert_engine(self):
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
        from PyQt6.QtCore import QSettings
        import EzUnBlock as app
        settings = QSettings(str(self.root / "profile-test.ini"), QSettings.Format.IniFormat)
        profiles = list((ROOT / "resources/core").glob("general*.bat"))
        self.assertGreater(len(profiles), 20)
        for profile in profiles:
            with self.subTest(profile=profile.name):
                command = app._build_game_mode_winws_command(
                    str(profile), str(ROOT / "resources/core"), settings)
                request = client.profile_request(command, ROOT / "resources/core/bin")
                request["op"] = "validate"
                result = self.pipe.request(request)
                self.assertEqual(result["exit_code"], 0, result.get("log"))


@unittest.skipUnless(os.name == "nt", "Windows command line parsing")
class ProfileTests(unittest.TestCase):
    def test_incomplete_application_engine_does_not_change_stock_fingerprint(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in client.STOCK_ENGINE_FILES:
                (root / name).write_bytes(name.encode("ascii"))
            stock = client.engine_fingerprint(root)
            for name in client.APP_ENGINE_FILES[:-1]:
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"component")
            self.assertEqual(stock, client.engine_fingerprint(root))
            (root / client.APP_ENGINE_FILES[-1]).write_bytes(b"last component")
            self.assertNotEqual(stock, client.engine_fingerprint(root))

    def test_ai_dns_ack_does_not_erase_live_bypass_snapshot(self):
        controller = client.Controller()
        controller.pipe = mock.Mock()
        live = {"ok": True, "running": True, "pid": 14332, "exit_code": None, "log": "running"}
        controller.state = dict(live)
        process = client.ServiceProcess(controller, live["pid"])
        for mode in ("apply", "restore"):
            with self.subTest(mode=mode):
                controller.pipe.request.return_value = {"ok": True, "applied": 1}
                with mock.patch.object(controller, "ensure"), mock.patch.object(client, "install_service") as install:
                    reply = controller.ai_dns_hosts("test", "0" * 64, mode, "helper", "bin")
                self.assertTrue(reply["ok"])
                self.assertEqual(controller.snapshot(), live)
                self.assertIsNone(process.poll())
                install.assert_not_called()

    def test_control_ack_cannot_hide_a_real_exit(self):
        controller = client.Controller()
        controller.pipe = mock.Mock()
        controller.state = {"ok": True, "running": True, "pid": 99}
        process = client.ServiceProcess(controller, 99)
        exited = {"ok": True, "running": False, "pid": 99, "exit_code": 42, "log": "driver failed"}
        controller.pipe.request.return_value = exited
        controller._request({"op": "status"})
        self.assertEqual(process.poll(), 42)
        controller.pipe.request.return_value = {"ok": True, "applied": 1}
        controller._request({"op": "ai-dns-hosts"})
        self.assertEqual(controller.snapshot(), exited)
        self.assertEqual(process.poll(), 42)

    def test_inputs_are_read_by_client_and_deduplicated(self):
        with tempfile.TemporaryDirectory() as root:
            file = Path(root) / "список test.txt"
            file.write_bytes(b"example.com\n")
            command = subprocess.list2cmdline([str(Path(root) / "winws.exe"), "--hostlist=" + str(file),
                                               "--hostlist-exclude=" + str(file)])
            request = client.profile_request(command, root)
            self.assertEqual(len(request["files"]), 1)
            self.assertEqual([arg["file"] for arg in request["args"]], [0, 0])
            self.assertNotIn(str(file), json.dumps(request))

    def test_shell_and_config_file_preambles_are_rejected(self):
        for command in ('cmd.exe /c example.bat', '"C:\\core\\winws.exe" @config.txt'):
            with self.assertRaises(ValueError):
                client.profile_request(command, r"C:\core")

    def test_large_files_are_metadata_only_and_report_true_sizes(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "hosts.txt"
            with source.open("wb") as stream:
                stream.truncate(1024 ** 3 + 1)
            request = client.profile_request(subprocess.list2cmdline([
                str(Path(root) / "winws.exe"), "--hostlist=" + str(source),
            ]), root)
            self.assertEqual(request["files"], [{"size": 1024 ** 3 + 1, "gzip": False}])
            self.assertLess(len(json.dumps(request)), 300)

    def test_changed_source_aborts_stream_instead_of_sending_stale_metadata(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "hosts.txt"
            source.write_bytes(b"example.com\n")
            request = client.profile_request(subprocess.list2cmdline([
                str(Path(root) / "winws.exe"), "--hostlist=" + str(source),
            ]), root)
            source.write_bytes(b"changed.example.com\n")
            pipe = object.__new__(client.Pipe)
            with mock.patch.object(pipe, "_send_control"), \
                 mock.patch.object(pipe, "_reply", return_value={"ok": True, "upload": True}), \
                 mock.patch.object(pipe, "_write") as write, \
                 mock.patch.object(pipe, "close") as close, \
                 self.assertRaises(client.UploadError):
                pipe.request(request)
            write.assert_not_called()
            close.assert_called_once()

    def test_cancelled_upload_never_sends_a_block(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "hosts.txt"
            source.write_bytes(b"example.com\n")
            metadata = client.ProfileSource(source, source.stat().st_size, source.stat().st_mtime_ns, True)
            cancelled = threading.Event()
            cancelled.set()
            pipe = object.__new__(client.Pipe)
            with mock.patch.object(pipe, "_write") as write, self.assertRaises(client.UploadError):
                pipe._upload_file(metadata, cancelled)
            write.assert_not_called()

    def test_binary_payload_limit_is_separate_from_hostlist_limit(self):
        with tempfile.TemporaryDirectory() as root:
            source = Path(root) / "huge-payload.bin"
            with source.open("wb") as stream:
                stream.truncate(client.MAX_PAYLOAD_BYTES + 1)
            command = subprocess.list2cmdline([
                str(Path(root) / "winws.exe"), "--dpi-desync-fake-tls=" + str(source),
            ])
            with self.assertRaisesRegex(ValueError, "16"):
                client.profile_request(command, root)

    def test_broken_connection_is_discarded_and_not_replayed(self):
        controller = client.Controller()
        pipe = controller.pipe = mock.Mock()
        pipe.request.side_effect = BrokenPipeError()
        with self.assertRaises(BrokenPipeError):
            controller.stop()
        pipe.close.assert_called_once()
        self.assertIsNone(controller.pipe)

    def test_disconnect_keeps_controller_reusable(self):
        controller = client.Controller()
        pipe = controller.pipe = mock.Mock()
        controller.state = {"running": True}
        controller.disconnect()
        pipe.close.assert_called_once()
        self.assertIsNone(controller.pipe)
        self.assertEqual({}, controller.state)
        self.assertFalse(controller.closed)


if __name__ == "__main__":
    unittest.main()
