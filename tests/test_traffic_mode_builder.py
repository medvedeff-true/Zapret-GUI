from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from zapret_gui.traffic_mode_builder import (
    UserListSelection,
    build_traffic_segments,
    build_winws_command,
    normalize_path,
)


class TrafficModeBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="traffic-mode-builder-")
        self.root = Path(self.temp.name)
        self.core_lists = self.root / "core" / "lists"
        self.user_lists = self.root / "user"
        self.core_lists.mkdir(parents=True)
        self.user_lists.mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _write(self, path: Path, text: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def test_all_mode_preserves_strategy_and_normalizes_list_paths(self) -> None:
        relative = Path("core") / "lists" / ".." / "lists" / "general.txt"
        segment = (
            '--filter-tcp=80,443 --hostlist="'
            + str(relative)
            + '" --dpi-desync=fake --new'
        )

        result = build_traffic_segments([segment], mode="all", base_dir=self.root)

        expected = normalize_path(relative, base_dir=self.root)
        self.assertEqual(len(result), 1)
        self.assertIn(f'--hostlist="{expected}"', result[0])
        self.assertIn("--filter-tcp=80,443", result[0])
        self.assertIn("--dpi-desync=fake", result[0])
        self.assertNotIn("--hosts", result[0].casefold())
        self.assertNotIn("--dns", result[0].casefold())

    def test_lists_mode_replaces_core_lists_with_selected_domain_files(self) -> None:
        domain = self._write(self.user_lists / "domains.txt", "example.com\n")
        exclude = self._write(self.user_lists / "exclude.txt", "safe.example\n")
        segment = (
            '--filter-tcp=80,443 --hostlist="core/list-general.txt" '
            '--hostlist="core/list-general-user.txt" '
            '--hostlist-exclude="core/list-exclude.txt" '
            '--hostlist-exclude="core/list-exclude-user.txt" '
            '--dpi-desync=fake,split2 --new'
        )

        result = build_traffic_segments(
            [segment],
            mode="lists",
            selected_lists=UserListSelection((domain,), (exclude,), (), ()),
            base_dir=self.root,
        )

        self.assertEqual(len(result), 1)
        self.assertIn(f'--hostlist="{normalize_path(domain)}"', result[0])
        self.assertIn(f'--hostlist-exclude="{normalize_path(exclude)}"', result[0])
        self.assertNotIn("core", result[0])
        self.assertIn("--dpi-desync=fake,split2", result[0])
        self.assertFalse(result[0].endswith("--new"))

    def test_lists_mode_can_split_a_segment_with_domain_and_ip_selectors(self) -> None:
        domain = self._write(self.user_lists / "domains.txt", "example.com\n")
        ip = self._write(self.user_lists / "ips.txt", "203.0.113.10\n")
        segment = (
            '--filter-tcp=443 --hostlist="core/domains.txt" '
            '--ipset="core/ips.txt" --dpi-desync=fake --new'
        )

        result = build_traffic_segments(
            [segment],
            mode="lists",
            selected_lists=UserListSelection((domain,), (), (ip,), ()),
            base_dir=self.root,
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(any("--hostlist=" in item and "--ipset=" not in item for item in result))
        self.assertTrue(any("--ipset=" in item and "--hostlist=" not in item for item in result))
        self.assertTrue(all("core" not in item for item in result))

    def test_lists_mode_separates_domain_and_ip_variants_when_strategy_omits_new(self) -> None:
        domain = self._write(self.user_lists / "domains.txt", "example.com\n")
        ip = self._write(self.user_lists / "ips.txt", "203.0.113.10\n")

        result = build_traffic_segments(
            ['--filter-tcp=443 --hostlist=core/domains.txt --ipset=core/ips.txt'],
            mode="lists",
            selected_lists=UserListSelection((domain,), (), (ip,), ()),
            base_dir=self.root,
        )

        self.assertEqual(len(result), 2)
        self.assertTrue(result[0].endswith(" --new"))
        self.assertFalse(result[1].endswith(" --new"))

    def test_empty_selected_files_are_ignored_and_never_create_broad_segments(self) -> None:
        empty_domain = self._write(self.user_lists / "empty-domains.txt", "# only a comment\n")
        ip = self._write(self.user_lists / "ips.txt", "203.0.113.10\n")
        empty_exclude = self._write(self.user_lists / "empty-exclude.txt", "")
        broad = "--filter-tcp=80,443 --dpi-desync=fake --new"
        domain_segment = '--filter-tcp=443 --hostlist="core/domains.txt" --new'
        ip_segment = '--filter-udp=443 --ipset="core/ips.txt" --new'

        result = build_traffic_segments(
            [broad, domain_segment, ip_segment],
            mode="lists",
            selected_lists=UserListSelection(
                (empty_domain,),
                (empty_exclude,),
                (ip,),
                (),
            ),
            base_dir=self.root,
        )

        self.assertEqual(len(result), 1)
        self.assertIn(f'--ipset="{normalize_path(ip)}"', result[0])
        self.assertNotIn("--hostlist=", result[0])
        self.assertNotIn("--dpi-desync=fake --new", result[0])

    def test_missing_files_and_non_list_segments_result_in_no_command(self) -> None:
        result = build_traffic_segments(
            [
                '--filter-tcp=443 --hostlist="core/domains.txt" --new',
                "--filter-udp=443 --filter-l7=discord --new",
            ],
            mode="lists",
            selected_lists={"domains_add": (self.user_lists / "gone.txt",)},
            base_dir=self.root,
        )

        self.assertEqual(result, ())
        self.assertEqual(
            build_winws_command(
                self.root / "bin" / "winws.exe",
                ["--filter-tcp=443 --hostlist=core/domains.txt --new"],
                mode="lists",
                selected_lists={"domains_add": (self.user_lists / "gone.txt",)},
                base_dir=self.root,
            ),
            "",
        )

    def test_selected_paths_are_deduplicated_after_normalization(self) -> None:
        domain = self._write(self.user_lists / "domains.txt", "example.com\n")
        duplicate = self.user_lists / "." / "domains.txt"
        result = build_traffic_segments(
            ['--filter-tcp=443 --hostlist="core/domains.txt" --new'],
            mode="lists",
            selected_lists={"domains_add": (domain, duplicate)},
            base_dir=self.root,
        )

        self.assertEqual(result[0].count("--hostlist="), 1)

    def test_all_mode_normalizes_bare_relative_list_paths(self) -> None:
        result = build_traffic_segments(
            ["--filter-tcp=443 --hostlist=list-general-user.txt --new"],
            mode="all",
            base_dir=self.root,
        )

        self.assertIn(
            f'--hostlist="{normalize_path("list-general-user.txt", base_dir=self.root)}"',
            result[0],
        )

    def test_build_command_is_side_effect_free_and_quotes_executable(self) -> None:
        domain = self._write(self.user_lists / "domains.txt", "example.com\n")
        command = build_winws_command(
            self.root / "bin" / "winws.exe",
            ['--filter-tcp=443 --hostlist="core/domains.txt" --new'],
            mode="lists",
            selected_lists={"domains_add": (domain,)},
            base_dir=self.root,
        )

        self.assertTrue(command.startswith(f'"{normalize_path(self.root / "bin" / "winws.exe")}" '))
        self.assertIn(f'--hostlist="{normalize_path(domain)}"', command)
        self.assertFalse((self.root / "hosts").exists())


if __name__ == "__main__":
    unittest.main()
