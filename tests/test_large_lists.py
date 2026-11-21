from pathlib import Path
import ipaddress
import tempfile
import tracemalloc
import unittest
from unittest import mock

from zapret_gui import large_lists


class LargeListTests(unittest.TestCase):
    def test_merge_files_validation_skips_malformed_entries(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            source = root / "source.txt"
            output = root / "output.txt"
            source.write_text("203.0.113.10\nnot-an-ip.example\n", encoding="utf-8")

            large_lists.merge_files(
                output,
                [source],
                validate=lambda value: ipaddress.ip_network(value, strict=False),
                validation_tag="ipset-v2",
            )

            self.assertEqual("203.0.113.10\n", output.read_text(encoding="utf-8"))

    def test_merge_is_stable_case_insensitive_and_strips_comments(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            a, b, output = root / "a.txt", root / "b.txt", root / "out.txt"
            a.write_text("\ufeff  Example.com \n# comment\n\nother.org\n", encoding="utf-8")
            b.write_text("EXAMPLE.COM\nnew.example\n", encoding="utf-8")
            self.assertTrue(large_lists.merge_files(output, [a, b, root / "missing.txt"]))
            self.assertEqual(output.read_text(), "Example.com\nother.org\nnew.example\n")
            mtime = output.stat().st_mtime_ns
            self.assertFalse(large_lists.merge_files(output, [a, b, root / "missing.txt"]))
            self.assertEqual(output.stat().st_mtime_ns, mtime)
            b.write_text("changed.example\n", encoding="utf-8")
            self.assertTrue(large_lists.merge_files(output, [a, b]))
            self.assertIn("changed.example", output.read_text())

    def test_disk_backed_deduplication_matches_small_list_behavior(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "in.txt"
            source.write_text("First.test\nsecond.test\nFIRST.TEST\nthird.test\n", encoding="utf-8")
            with mock.patch.object(large_lists, "MEMORY_THRESHOLD", 0):
                large_lists.merge_files(root / "disk.txt", [source, source])
            large_lists.merge_files(root / "memory.txt", [source, source])
            self.assertEqual((root / "disk.txt").read_bytes(), (root / "memory.txt").read_bytes())
            self.assertFalse(any(path.name.startswith("list-index-") for path in root.iterdir()))

    def test_huge_number_of_entries_does_not_build_python_sets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "in.txt", root / "out.txt"
            with source.open("w") as stream:
                for index in range(160000):
                    stream.write(f"host-{index:08d}.example.test\n")
            tracemalloc.start()
            try:
                large_lists.merge_files(output, [source, source])
                _, peak = tracemalloc.get_traced_memory()
            finally:
                tracemalloc.stop()
            self.assertLess(peak, 2 * 1024 * 1024)
            with output.open() as stream:
                self.assertEqual(sum(1 for _ in stream), 160000)

    def test_failure_preserves_previous_output_and_cleans_temporary_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            output, source = root / "out.txt", root / "in.txt"
            output.write_text("previous.example\n")
            source.write_bytes(b"A" * (large_lists.MAX_LINE_BYTES + 1))
            with self.assertRaisesRegex(ValueError, "64"):
                large_lists.merge_files(output, [source])
            self.assertEqual(output.read_text(), "previous.example\n")
            self.assertEqual(set(path.name for path in root.iterdir()), {"out.txt", "in.txt"})

    def test_modified_output_invalidates_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "in.txt", root / "out.txt"
            source.write_text("real.example\n")
            large_lists.merge_files(output, [source])
            output.write_text("externally-modified.example\n")
            self.assertTrue(large_lists.merge_files(output, [source]))
            self.assertEqual(output.read_text(), "real.example\n")

    def test_import_merge_reports_only_new_unique_values(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target, source = root / "user.txt", root / "import.txt"
            target.write_text("existing.test\n")
            source.write_text("EXISTING.TEST\nnew.test\nNEW.TEST\nsecond.test\n")
            with mock.patch.object(large_lists, "MEMORY_THRESHOLD", 0):
                self.assertEqual(large_lists.merge_import_file(target, source), 2)
            self.assertEqual(target.read_text(), "existing.test\nnew.test\nsecond.test\n")
            self.assertFalse(source.exists())

    def test_append_and_remove_do_not_truncate_unselected_entries(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "user.txt"
            path.write_text("Existing.test\nother.test")
            self.assertFalse(large_lists.append_unique_value(path, "EXISTING.TEST"))
            self.assertTrue(large_lists.append_unique_value(path, "new.test"))
            self.assertEqual(path.read_text(), "Existing.test\nother.test\nnew.test\n")
            self.assertEqual(large_lists.remove_values(path, ["existing.test"]), 1)
            self.assertEqual(path.read_text(), "other.test\nnew.test\n")

    def test_normalized_import_is_streamed_and_cleans_bad_values(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "user.txt"
            temporary, count = large_lists.normalized_values_file(
                target, iter(["Good.test", "invalid", "second.test"]),
                str.lower, lambda value: "." in value,
            )
            try:
                self.assertEqual(count, 2)
                self.assertEqual(temporary.read_text(), "good.test\nsecond.test\n")
            finally:
                temporary.unlink()

    def test_import_encoding_and_delimiters_are_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "cp1251.txt"
            source.write_bytes("# комментарий\nfirst.test; second.test,third.test\n".encode("cp1251"))
            self.assertEqual(list(large_lists.iter_delimited_text_values(source)),
                             ["first.test", "second.test", "third.test"])
            source.write_text("# комментарий\nfirst.test\nsecond.test\n", encoding="utf-16")
            self.assertEqual(list(large_lists.iter_delimited_text_values(source)),
                             ["first.test", "second.test"])


if __name__ == "__main__":
    unittest.main()
