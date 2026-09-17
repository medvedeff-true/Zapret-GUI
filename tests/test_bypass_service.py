from __future__ import annotations

import ctypes
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
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
        if (Array.IndexOf(args, "--comment=tree") >= 0) {
            var si = new ProcessStartInfo(Process.GetCurrentProcess().MainModule.FileName);
            si.UseShellExecute = false; si.CreateNoWindow = true;
            Console.WriteLine("descendant=" + Process.Start(si).Id);
        }
        Thread.Sleep(60000); return 0;
    }
}''', encoding="utf-8")
        compiler = Path(os.environ["WINDIR"]) / "Microsoft.NET/Framework64/v4.0.30319/csc.exe"
        subprocess.run([str(compiler), "/nologo", "/out:" + str(cls.root / "engine/winws.exe"), str(source)],
                       check=True, creationflags=subprocess.CREATE_NO_WINDOW, capture_output=True)
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
        result = self.pipe.request({"op": "start", "args": [{"name": "hostlist", "file": 0}], "files": ["ZXhhbXBsZS5jb20K"]})
        staged = result["log"].split("arg=--hostlist=")[1].splitlines()[0]
        self.assertEqual(Path(staged).read_text(), "example.com\n")
        self.pipe.request({"op": "stop"})
        self.assertFalse(Path(staged).exists())

    def test_second_start_does_not_orphan_first_process(self):
        result = self.start()
        with self.assertRaisesRegex(RuntimeError, "already running"):
            self.start()
        self.assertEqual(self.pipe.request({"op": "status"})["pid"], result["pid"])

    def test_bundled_profiles_pass_real_winws_dry_run_through_protocol(self):
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


@unittest.skipUnless(os.name == "nt", "Windows command line parsing")
class ProfileTests(unittest.TestCase):
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
