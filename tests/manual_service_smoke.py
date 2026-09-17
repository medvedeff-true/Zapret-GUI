"""Opt-in SCM/WinDivert smoke test. Installs the real service with Windows consent.

The filter is literally 'false': it opens WinDivert without intercepting traffic.
The installed idle service is retained for the application after this test.
"""
from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import psutil
from bypass_service import Controller, current_user_sid, service_pid


def session_id(pid):
    result = wintypes.DWORD()
    if not ctypes.windll.kernel32.ProcessIdToSessionId(pid, ctypes.byref(result)):
        if ctypes.windll.kernel32.GetLastError() == 5:
            # Some Windows process ACLs deny cross-account session queries.
            # The elevated run checks session 0; the standard run checks IPC.
            return None
        raise ctypes.WinError()
    return result.value


def wait_gone(pid):
    deadline = time.monotonic() + 8
    while psutil.pid_exists(pid) and time.monotonic() < deadline:
        time.sleep(0.1)
    assert not psutil.pid_exists(pid), f"winws {pid} survived GUI shutdown"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--existing", action="store_true")
    parser.add_argument("--child-result")
    options = parser.parse_args()
    if not options.install and not options.existing and not options.child_result:
        parser.error("--install is required to opt in to system service installation")
    core = ROOT / "resources/core/bin"
    helper = ROOT / "resources/background_service/ZapretGUI.Service.exe"
    command = subprocess.list2cmdline([str(core / "winws.exe"), "--wf-raw=false", "--filter-tcp=65534", "--dpi-desync=fake"])
    controller = Controller()
    if options.existing:
        # Never trigger setup while checking a non-administrative token.
        service_pid("ZapretGUI.Bypass." + current_user_sid(), start=True)
    if options.child_result:
        process = controller.start(command, core, helper)
        Path(options.child_result).write_text(json.dumps({"pid": process.pid}), encoding="utf-8")
        time.sleep(90)
        controller.close()
        return
    assert not any(str(p.info["name"]).lower() == "winws.exe" for p in psutil.process_iter(["name"])), "Stop the existing bypass before this test"
    results = {"gui_admin": bool(ctypes.windll.shell32.IsUserAnAdmin()), "cycles": []}
    try:
        controller.ensure(helper, core)
        sid = current_user_sid()
        pid = service_pid("ZapretGUI.Bypass." + sid)
        results["service_pid"] = pid
        results["service_session"] = session_id(pid)
        assert results["service_session"] in (0, None)
        for _ in range(3):
            process = controller.start(command, core, helper)
            state = controller.snapshot()
            state["session"] = session_id(process.pid)
            assert state["session"] in (0, None)
            assert process.poll() is None
            controller.stop()
            wait_gone(process.pid)
            results["cycles"].append(state)
    finally:
        controller.close()
    child_result = ROOT / "tests/.service-smoke-child.json"
    child_result.unlink(missing_ok=True)
    child = subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "--child-result", str(child_result)],
                             creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        deadline = time.monotonic() + 20
        while not child_result.exists() and time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError("GUI test child exited before starting winws")
            time.sleep(0.1)
        process_pid = json.loads(child_result.read_text(encoding="utf-8"))["pid"]
        child.kill()
        child.wait(timeout=5)
        wait_gone(process_pid)
        results["gui_crash_cleanup"] = True
    finally:
        if child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        child_result.unlink(missing_ok=True)
    report = ROOT / "tests" / ("service-smoke-result.json" if results["gui_admin"] else "service-smoke-standard-result.json")
    report.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
