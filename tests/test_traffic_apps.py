from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from zapret_gui import traffic_apps
from zapret_gui.traffic_apps import (
    SOURCE_FILE,
    SOURCE_INSTALLED,
    SOURCE_PROCESS,
    TrafficAppStore,
    enumerate_installed_applications,
    enumerate_processes,
    enumerate_services,
)


class TrafficAppStoreTests(unittest.TestCase):
    def test_paths_are_deduplicated_and_sources_are_merged(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Example.exe"
            executable.write_bytes(b"MZ")
            store = TrafficAppStore(Path(directory) / "apps.json", auto_save=False)

            first = store.add(executable, source=SOURCE_FILE)
            second = store.add(str(executable).upper(), source=SOURCE_PROCESS)

            self.assertIsNotNone(first)
            self.assertIsNotNone(second)
            records = store.records()
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].sources, {SOURCE_FILE, SOURCE_PROCESS})
            self.assertEqual(store.selected_paths(), [records[0].path])

    def test_persistence_is_versioned_and_atomic_from_callers_perspective(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "Editor.exe"
            executable.write_bytes(b"MZ")
            storage = root / "nested" / "traffic_apps.json"

            store = TrafficAppStore(storage)
            store.add(executable, source=SOURCE_INSTALLED, label="Editor")
            store.set_enabled(executable, False)

            payload = json.loads(storage.read_text(encoding="utf-8"))
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(len(payload["records"]), 1)
            self.assertFalse(payload["records"][0]["enabled"])

            restored = TrafficAppStore(storage)
            record = restored.get(executable)
            self.assertIsNotNone(record)
            self.assertEqual(record.label, "Editor")
            self.assertFalse(record.enabled)
            self.assertEqual(record.sources, {SOURCE_INSTALLED})

    def test_missing_files_are_safe_and_excluded_without_losing_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            existing = root / "present.exe"
            existing.write_bytes(b"MZ")
            missing = root / "later.exe"
            store = TrafficAppStore(root / "apps.json", auto_save=False)
            store.add(existing)
            store.add(missing, source=SOURCE_PROCESS)

            self.assertEqual(store.selected_paths(), [str(existing)])
            missing_record = store.get(missing)
            self.assertIsNotNone(missing_record)
            self.assertTrue(missing_record.missing)
            self.assertEqual(len(store.missing_records()), 1)

            missing.write_bytes(b"MZ")
            self.assertEqual(
                {Path(path).name for path in store.selected_paths()},
                {"present.exe", "later.exe"},
            )

    def test_removing_one_source_keeps_shared_selection(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Shared.exe"
            executable.write_bytes(b"MZ")
            store = TrafficAppStore(Path(directory) / "apps.json", auto_save=False)
            store.add(executable, source=SOURCE_FILE)
            store.add(executable, source=SOURCE_INSTALLED)

            self.assertTrue(store.remove(executable, source=SOURCE_FILE))
            record = store.get(executable)
            self.assertIsNotNone(record)
            self.assertEqual(record.sources, {SOURCE_INSTALLED})
            self.assertTrue(store.remove(executable))
            self.assertIsNone(store.get(executable))

    def test_corrupt_json_does_not_break_startup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            storage = Path(directory) / "apps.json"
            storage.write_text("{not-json", encoding="utf-8")
            store = TrafficAppStore(storage, auto_save=False)
            self.assertEqual(store.records(), [])
            self.assertTrue(store.last_load_error)
            self.assertTrue(storage.exists())

    def test_legacy_list_and_duplicate_entries_are_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            executable = root / "Legacy.exe"
            executable.write_bytes(b"MZ")
            storage = root / "apps.json"
            storage.write_text(
                json.dumps(
                    [
                        {"path": str(executable), "enabled": False, "sources": ["file"]},
                        {"path": str(executable).upper(), "enabled": True, "sources": ["process"]},
                    ]
                ),
                encoding="utf-8",
            )
            store = TrafficAppStore(storage, auto_save=False)
            record = store.get(executable)
            self.assertIsNotNone(record)
            self.assertTrue(record.enabled)
            self.assertEqual(record.sources, {SOURCE_FILE, SOURCE_PROCESS})


class DiscoveryTests(unittest.TestCase):
    def test_process_snapshot_skips_unresolved_processes_and_marks_session_zero(self) -> None:
        class FakeProcess:
            def __init__(self, pid: int, name: str, path: str, session: int) -> None:
                self.pid = pid
                self.info = {
                    "pid": pid,
                    "name": name,
                    "exe": path,
                    "username": "user",
                    "status": "running",
                    "ppid": 1,
                }
                self._session = session

            def session_id(self) -> int:
                return self._session

        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "worker.exe"
            executable.write_bytes(b"MZ")
            processes = [
                FakeProcess(20, "worker.exe", str(executable), 1),
                FakeProcess(10, "service.exe", str(executable), 0),
                FakeProcess(30, "hidden.exe", "", 1),
            ]
            with patch.object(traffic_apps.psutil, "process_iter", return_value=processes):
                snapshot = enumerate_processes()

            self.assertEqual([item.pid for item in snapshot], [10, 20])
            self.assertTrue(snapshot[0].is_service)
            self.assertFalse(snapshot[1].is_service)
            self.assertEqual(snapshot[0].path_key, snapshot[1].path_key)

    def test_process_snapshot_can_include_unresolved_entries(self) -> None:
        class FakeProcess:
            pid = 7
            info = {
                "pid": 7,
                "name": "unknown.exe",
                "exe": "",
                "username": "",
                "status": "",
                "ppid": None,
            }

            def session_id(self) -> int:
                raise traffic_apps.psutil.AccessDenied()

        with patch.object(traffic_apps.psutil, "process_iter", return_value=[FakeProcess()]):
            snapshot = enumerate_processes(include_unresolved=True)
        self.assertEqual(len(snapshot), 1)
        self.assertFalse(snapshot[0].selectable)
        self.assertIsNone(snapshot[0].session_id)

    def test_installed_entries_are_deduplicated_by_executable_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Suite.exe"
            executable.write_bytes(b"MZ")
            entries = [
                {
                    "DisplayName": "Suite",
                    "DisplayIcon": str(executable),
                    "InstallLocation": str(Path(directory)),
                    "Publisher": "A",
                    "DisplayVersion": "1",
                    "_registry_source": "HKLM:64:first",
                },
                {
                    "DisplayName": "Suite (duplicate)",
                    "DisplayIcon": str(executable).upper(),
                    "InstallLocation": str(Path(directory)),
                    "Publisher": "B",
                    "DisplayVersion": "2",
                    "_registry_source": "HKCU:32:second",
                },
            ]
            with patch.object(traffic_apps, "_registry_uninstall_entries", return_value=iter(entries)):
                applications = enumerate_installed_applications(include_unresolved=False)
            self.assertEqual(len(applications), 1)
            self.assertEqual(applications[0].path_key, traffic_apps.executable_path_key(executable))

    def test_display_icon_with_quotes_and_icon_index_is_parsed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Player.exe"
            executable.write_bytes(b"MZ")
            value = f'"{executable}",0'
            self.assertEqual(
                traffic_apps._extract_executable_path(value),
                traffic_apps.normalize_executable_path(executable),
            )

    def test_services_are_separate_and_command_paths_are_parsed(self) -> None:
        class FakeService:
            def __init__(self, payload: dict) -> None:
                self.payload = payload

            def as_dict(self) -> dict:
                return self.payload

        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "host.exe"
            executable.write_bytes(b"MZ")
            services = [
                FakeService(
                    {
                        "name": "SelectedService",
                        "display_name": "Selected service",
                        "binpath": f'"{executable}" --service',
                        "status": "running",
                        "start_type": "auto",
                        "username": "LocalSystem",
                        "pid": 42,
                        "description": "test",
                    }
                ),
                FakeService(
                    {
                        "name": "UnresolvedService",
                        "display_name": "Unresolved service",
                        "binpath": r"C:\missing\missing.exe --service",
                        "status": "stopped",
                    }
                ),
            ]
            with patch.object(traffic_apps.sys, "platform", "win32"), \
                 patch.object(traffic_apps.psutil, "win_service_iter", return_value=services):
                snapshot = enumerate_services()

            self.assertEqual(len(snapshot), 2)
            self.assertEqual(snapshot[0].display_name, "Selected service")
            self.assertTrue(snapshot[0].selectable)
            self.assertEqual(snapshot[0].pid, 42)
            self.assertFalse(snapshot[1].selectable)
            with patch.object(traffic_apps.sys, "platform", "win32"), \
                 patch.object(traffic_apps.psutil, "win_service_iter", return_value=services):
                selectable = enumerate_services(include_unresolved=False)
            self.assertEqual(len(selectable), 1)


if __name__ == "__main__":
    unittest.main()
