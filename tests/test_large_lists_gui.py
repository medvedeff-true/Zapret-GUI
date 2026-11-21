import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest import mock

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QApplication
import EzUnBlock as app


class LargeListGuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.qt = QApplication.instance() or QApplication([])

    def test_search_worker_caps_results_and_can_find_end_of_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "hosts.txt"
            path.write_text("example.test\n" * 2000 + "needle.example\n")
            results = []
            worker = app._SiteListSearchWorker(str(path), "")
            worker.ready.connect(lambda *result: results.append(result))
            worker.run()
            self.assertEqual(len(results[0][2]), 1000)
            self.assertTrue(results[0][3])
            worker = app._SiteListSearchWorker(str(path), "needle")
            worker.ready.connect(lambda *result: results.append(result))
            worker.run()
            self.assertEqual(results[1][2], ["needle.example"])
            self.assertFalse(results[1][3])

    def test_import_worker_normalizes_and_reports_exact_added_count(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "source.txt", root / "user.txt"
            target.write_text("existing.test\n")
            source.write_text("https://NEW.test/path\nEXISTING.TEST\nnew.test\ninvalid\n")
            results = []
            worker = app._SiteListImportWorker(str(target), str(source))
            worker.ready.connect(lambda *result: results.append(result))
            worker.run()
            self.assertEqual(results, [(str(target), 1, "")])
            self.assertEqual(target.read_text(), "existing.test\nnew.test\n")
            self.assertFalse(list(root.glob("import-*.txt")))

    def test_large_dialog_uses_worker_not_full_file_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "hosts.txt"
            with path.open("w") as stream:
                stream.write("example.test\n" * 330000)
            settings = QSettings(str(root / "settings.ini"), QSettings.Format.IniFormat)
            dialog = app.SiteManagerDialog(settings=settings)
            try:
                with mock.patch.object(dialog, "_selected_file_path", return_value=str(path)), \
                     mock.patch.object(app, "_read_lines_utf8", side_effect=AssertionError("whole-file read")):
                    dialog.reload_current_file()
                    deadline = time.monotonic() + 5
                    while dialog.sites_list.count() == 0 and time.monotonic() < deadline:
                        self.qt.processEvents()
                        time.sleep(0.005)
                    self.assertTrue(dialog._large_list_mode)
                    self.assertEqual(dialog.sites_list.count(), 1000)
            finally:
                dialog._cancel_large_list_search()
                for worker in list(app._SITE_LIST_WORKERS):
                    if hasattr(worker, "cancelled"):
                        worker.cancelled.set()
                    worker.wait(5000)
                self.qt.processEvents()
                dialog.close()
                dialog.deleteLater()
                self.qt.processEvents()

    def test_launch_merge_errors_are_strict_only_when_requested(self):
        with mock.patch.object(app, "_rebuild_runtime_list_files", side_effect=OSError("disk full")):
            app._rebuild_runtime_lists()
            with self.assertRaisesRegex(OSError, "disk full"):
                app._rebuild_runtime_lists(strict=True)


if __name__ == "__main__":
    unittest.main()
