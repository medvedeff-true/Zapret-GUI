from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adaptive_strategy.catalog import strategies_for, tcp_strategy_by_id
from adaptive_strategy.models import ProbeResult, Protocol, probe_matrix_passed
from adaptive_strategy.probe import parse_targets, select_profile_builder_targets


FIXED_TARGETS = """
https://www.youtube.com/generate_204
https://discord.com/api/v10/gateway
"""


class FixedTargetParsingTests(unittest.TestCase):
    def test_fixed_targets_expand_into_the_expected_probe_matrix(self) -> None:
        targets = parse_targets(FIXED_TARGETS, include_quic=True)

        self.assertEqual(5, len(targets))
        by_key = {(target.url, target.validator): target for target in targets}

        youtube = by_key[("https://www.youtube.com/generate_204", "http")]
        self.assertEqual("youtube", youtube.service)
        self.assertEqual("youtube", youtube.profile)
        self.assertEqual((Protocol.HTTPS, Protocol.QUIC), youtube.protocols)

        discord_gateway = by_key[("https://discord.com/api/v10/gateway", "http")]
        self.assertEqual("discord_app", discord_gateway.profile)
        self.assertIn(
            ("https://updates.discord.com/distributions/app/manifests/latest?channel=stable&platform=win&arch=x64", "discord_update"),
            by_key,
        )
        self.assertNotIn(
            ("https://updates.discord.com/distributions/app/manifests/latest?channel=stable&platform=win&arch=x64", "http"),
            by_key,
        )
        self.assertIn(
            ("wss://gateway.discord.gg/?v=10&encoding=json", "websocket"),
            by_key,
        )

        self.assertFalse(any(target.service == "telegram" for target in targets))
        self.assertFalse(any(target.service == "custom" for target in targets))

    def test_fixed_targets_are_deduplicated_after_service_expansion(self) -> None:
        targets = parse_targets(FIXED_TARGETS + "\nhttps://discord.com/api/v10/gateway", include_quic=True)
        keys = [(target.url, target.validator) for target in targets]

        self.assertEqual(len(keys), len(set(keys)))
        self.assertEqual(1, keys.count(("https://discord.com/api/v10/gateway", "http")))

    def test_profile_builder_ignores_generic_sites_instead_of_making_them_fatal(self) -> None:
        targets = parse_targets(
            FIXED_TARGETS + "\nhttps://rutracker.org/forum/index.php",
            include_quic=True,
        )

        selected, ignored = select_profile_builder_targets(targets)

        self.assertEqual({"youtube", "discord"}, {target.service for target in selected})
        self.assertEqual(
            ["https://rutracker.org/forum/index.php"],
            [target.url for target in ignored],
        )

    def test_probe_matrix_keeps_same_url_validator_identities_separate(self) -> None:
        http_target = parse_targets("https://www.youtube.com/generate_204")[0]
        specialised_target = type(http_target)(
            http_target.url,
            http_target.hostname,
            http_target.protocols,
            service=http_target.service,
            profile=http_target.profile,
            validator="special",
            alternative_group="special-route",
        )
        fallback_target = type(http_target)(
            "https://fallback.youtube.com/generate_204",
            "fallback.youtube.com",
            http_target.protocols,
            service=http_target.service,
            profile=http_target.profile,
            validator="special",
            alternative_group="special-route",
        )
        probes = [
            ProbeResult(http_target, "cygwin", True, 204, 0.01, remote_ip="203.0.113.1"),
            ProbeResult(specialised_target, "special", False, None, 0.01, error="failed"),
            ProbeResult(fallback_target, "special", True, 204, 0.01, remote_ip="203.0.113.2"),
        ]

        self.assertTrue(probe_matrix_passed(probes))


class FlowsealAltCatalogTests(unittest.TestCase):
    def test_alt11_alt12_alt13_candidates_are_present_in_fast_catalogs(self) -> None:
        expected_ids = {
            "ts-overlap-664-stun2",
            "ts-overlap-681-google-r8",
            "ts-overlap-681-google-r7",
            "ts-hostfakesplit-mail-sochi",
            "split-overlap-568-4pda",
        }
        discord_ids = {strategy.id for strategy in strategies_for(Protocol.HTTPS, "discord_app")}
        custom_ids = {strategy.id for strategy in strategies_for(Protocol.HTTPS, "custom")}

        self.assertTrue(expected_ids.issubset(discord_ids))
        self.assertTrue(
            {
                "ts-overlap-664-stun2",
                "ts-hostfakesplit-mail-sochi",
            }.issubset(custom_ids)
        )

    def test_alt_candidates_keep_the_flowseal_specific_options(self) -> None:
        overlap_stun2 = tcp_strategy_by_id("ts-overlap-664-stun2")
        discord_r8 = tcp_strategy_by_id("ts-overlap-681-google-r8")
        discord_r7 = tcp_strategy_by_id("ts-overlap-681-google-r7")
        sochi = tcp_strategy_by_id("ts-hostfakesplit-mail-sochi")
        overlap_4pda = tcp_strategy_by_id("split-overlap-568-4pda")

        self.assertIn("--dpi-desync-split-seqovl=664", overlap_stun2.options)
        self.assertIn("--dpi-desync-fake-tls={fake_stun2}", overlap_stun2.options)
        self.assertIn("--dpi-desync-split-seqovl-pattern={fake_tls_max}", overlap_stun2.options)
        self.assertIn("--dpi-desync-fake-http={fake_tls_max}", overlap_stun2.options)
        self.assertIn("--dpi-desync-repeats=8", discord_r8.options)
        self.assertIn("--dpi-desync-repeats=7", discord_r7.options)
        self.assertIn("--dpi-desync-hostfakesplit-mod=host=mail.ru,altorder=1", sochi.options)
        self.assertIn("--dpi-desync-fake-tls={fake_tls_sochi}", sochi.options)
        self.assertIn("--dpi-desync-fake-http={fake_tls_sochi}", sochi.options)
        self.assertIn("--dpi-desync-split-seqovl=568", overlap_4pda.options)
        self.assertIn("--dpi-desync-split-seqovl-pattern={fake_tls_4pda}", overlap_4pda.options)

    def test_every_new_placeholder_renders_to_a_concrete_payload_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bin_dir = Path(temporary) / "bin"
            fake_tls = bin_dir / "tls_clienthello_www_google_com.bin"
            fake_quic = bin_dir / "quic_initial_www_google_com.bin"
            fake_tls_max = bin_dir / "tls_clienthello_max_ru.bin"
            fake_tls_4pda = bin_dir / "tls_clienthello_4pda_to.bin"

            options = []
            for strategy_id in (
                "ts-overlap-664-stun2",
                "ts-hostfakesplit-mail-sochi",
                "split-overlap-568-4pda",
            ):
                options.extend(
                    tcp_strategy_by_id(strategy_id).render(
                        fake_tls,
                        fake_quic,
                        fake_tls_max,
                        fake_tls_4pda,
                    )
                )

            rendered = "\n".join(options)
            self.assertNotIn("{fake_", rendered)
            for filename in (
                "stun2.bin",
                "tls_clienthello_sochi_park.bin",
                "tls_clienthello_max_ru.bin",
                "tls_clienthello_4pda_to.bin",
            ):
                self.assertIn(str(bin_dir / filename), rendered)


if __name__ == "__main__":
    unittest.main()
