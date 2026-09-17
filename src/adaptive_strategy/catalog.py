from __future__ import annotations

from dataclasses import replace

from .models import Protocol, Strategy


TLS_FAKE = "--dpi-desync-fake-tls={fake_tls}"
QUIC_FAKE = "--dpi-desync-fake-quic={fake_quic}"


TCP_STRATEGIES: tuple[Strategy, ...] = (
    Strategy(
        "ipid-hostfakesplit-google", "IP-ID zero + Host fake split", "ipid-hostfake", Protocol.HTTPS,
        ("--ip-id=zero", "--dpi-desync=hostfakesplit", "--dpi-desync-fooling=ts",
         "--dpi-desync-hostfakesplit-mod=host=www.google.com"),
        tier=1, risk=1,
        description="CDN/updater-профиль с обнулением IPv4 ID и подменой Host.",
    ),
    Strategy(
        "ipid-fakedsplit-zero", "IP-ID zero + fake-data split", "ipid-fakedsplit", Protocol.HTTPS,
        ("--ip-id=zero", "--dpi-desync=fake,fakedsplit", "--dpi-desync-repeats=6",
         "--dpi-desync-fooling=ts", "--dpi-desync-fakedsplit-pattern=0x00", TLS_FAKE),
        tier=1, risk=1,
        description="Google/CDN-вариант fake-data split с нулевым IPv4 ID.",
    ),
    Strategy(
        "ipid-overlap-681", "IP-ID zero + TLS overlap 681", "ipid-overlap", Protocol.HTTPS,
        ("--ip-id=zero", "--dpi-desync=fake,multisplit", "--dpi-desync-split-seqovl=681",
         "--dpi-desync-split-pos=1", "--dpi-desync-fooling=ts", "--dpi-desync-repeats=8",
         "--dpi-desync-split-seqovl-pattern={fake_tls}", TLS_FAKE),
        tier=1, risk=1,
        description="Google/CDN-вариант overlap 681 с нулевым IPv4 ID.",
    ),
    Strategy(
        "ts-overlap-664", "TLS overlap 664 + TCP timestamp", "timestamp-overlap", Protocol.HTTPS,
        ("--dpi-desync=fake,multisplit", "--dpi-desync-split-seqovl=664", "--dpi-desync-split-pos=1",
         "--dpi-desync-fooling=ts", "--dpi-desync-repeats=8",
         "--dpi-desync-split-seqovl-pattern={fake_tls_max}",
         "--dpi-desync-fake-tls={fake_stun}", "--dpi-desync-fake-tls={fake_tls_max}",
         "--dpi-desync-fake-http={fake_tls_max}"),
        tier=1, risk=1,
        description="Семейство overlap с 664-байтным ClientHello и timestamp fooling.",
    ),
    Strategy(
        "ts-overlap-664-stun2", "TLS overlap 664 + STUN2", "timestamp-overlap", Protocol.HTTPS,
        ("--dpi-desync=fake,multisplit", "--dpi-desync-split-seqovl=664", "--dpi-desync-split-pos=1",
         "--dpi-desync-fooling=ts", "--dpi-desync-repeats=8",
         "--dpi-desync-split-seqovl-pattern={fake_tls_max}",
         "--dpi-desync-fake-tls={fake_stun2}", "--dpi-desync-fake-tls={fake_tls_max}",
         "--dpi-desync-fake-http={fake_tls_max}"),
        tier=1, risk=1,
        description="Точный general-вариант ALT11: overlap 664 с новым STUN2 и max.ru ClientHello.",
    ),
    Strategy(
        "ts-fake-4pda", "Fake 4PDA + TCP timestamp", "timestamp-fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-repeats=6", "--dpi-desync-fooling=ts",
         "--dpi-desync-fake-tls={fake_stun}", "--dpi-desync-fake-tls={fake_tls_4pda}"),
        tier=1, risk=1,
        description="Timestamp fake с альтернативным коротким ClientHello.",
    ),
    Strategy(
        "badseq-fakedsplit-rnd", "Fake-data split + badseq TLS mods", "badseq-fakedsplit", Protocol.HTTPS,
        ("--dpi-desync=fake,fakedsplit", "--dpi-desync-split-pos=1",
         "--dpi-desync-fooling=badseq", "--dpi-desync-badseq-increment=2",
         "--dpi-desync-repeats=8", "--dpi-desync-fake-tls-mod=rnd,dupsid,sni=www.google.com"),
        tier=1, risk=2,
        description="Fake-data split с badseq и синтетическими TLS-модификациями.",
    ),
    Strategy(
        "badseq-fake-google", "Google fake + badseq", "badseq-fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-repeats=6", "--dpi-desync-fooling=badseq",
         "--dpi-desync-badseq-increment=2", TLS_FAKE),
        tier=1, risk=2,
        description="Простой TLS fake с badseq increment 2.",
    ),
    Strategy(
        "split-overlap-568-4pda", "Multi-split overlap 568", "split-overlap", Protocol.HTTPS,
        ("--dpi-desync=multisplit", "--dpi-desync-split-seqovl=568",
         "--dpi-desync-split-pos=1", "--dpi-desync-split-seqovl-pattern={fake_tls_4pda}"),
        tier=1, risk=1,
        description="Чистый multisplit с альтернативным overlap-паттерном.",
    ),
    Strategy(
        "ts-fake", "Fake + TCP timestamp", "timestamp-fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-repeats=6", "--dpi-desync-fooling=ts",
         "--dpi-desync-fake-tls={fake_stun}", TLS_FAKE,
         "--dpi-desync-fake-tls-mod=none"),
        tier=1, risk=1,
        description="Fake TLS с repeats и TCP timestamp fooling.",
    ),
    Strategy(
        "ts-fakedsplit-zero", "Fake-data split + TCP timestamp", "timestamp-fakedsplit", Protocol.HTTPS,
        ("--dpi-desync=fake,fakedsplit", "--dpi-desync-repeats=6", "--dpi-desync-fooling=ts",
         "--dpi-desync-fakedsplit-pattern=0x00", "--dpi-desync-fake-tls={fake_stun}", TLS_FAKE),
        tier=1, risk=1,
        description="Fake-data split с нулевым шаблоном и TCP timestamp fooling.",
    ),
    Strategy(
        "ts-overlap-681", "TLS overlap 681 + TCP timestamp", "timestamp-overlap", Protocol.HTTPS,
        ("--dpi-desync=fake,multisplit", "--dpi-desync-split-seqovl=681", "--dpi-desync-split-pos=1",
         "--dpi-desync-fooling=ts", "--dpi-desync-repeats=8",
         "--dpi-desync-split-seqovl-pattern={fake_tls}",
         "--dpi-desync-fake-tls={fake_stun}", TLS_FAKE),
        tier=1, risk=1,
        description="Перекрытие полного Google ClientHello с TCP timestamp fooling.",
    ),
    Strategy(
        "ts-overlap-681-google-r8", "TLS overlap 681 Google x8", "timestamp-overlap", Protocol.HTTPS,
        ("--dpi-desync=fake,multisplit", "--dpi-desync-split-seqovl=681", "--dpi-desync-split-pos=1",
         "--dpi-desync-fooling=ts", "--dpi-desync-repeats=8",
         "--dpi-desync-split-seqovl-pattern={fake_tls}", "--dpi-desync-fake-tls={fake_tls}"),
        tier=1, risk=1,
        description="Точный Discord media-вариант ALT11/ALT12 без дополнительного STUN payload.",
    ),
    Strategy(
        "ts-overlap-681-google-r7", "TLS overlap 681 Google x7", "timestamp-overlap", Protocol.HTTPS,
        ("--dpi-desync=fake,multisplit", "--dpi-desync-split-seqovl=681", "--dpi-desync-split-pos=1",
         "--dpi-desync-fooling=ts", "--dpi-desync-repeats=7",
         "--dpi-desync-split-seqovl-pattern={fake_tls}", "--dpi-desync-fake-tls={fake_tls}"),
        tier=1, risk=1,
        description="Точный Discord media-вариант ALT13 с repeats 7.",
    ),
    Strategy(
        "ts-hostfakesplit-mail-sochi", "Mail.ru host fake split + Sochi", "timestamp-hostfake", Protocol.HTTPS,
        ("--dpi-desync=fake,hostfakesplit", "--dpi-desync-fooling=ts",
         "--dpi-desync-hostfakesplit-mod=host=mail.ru,altorder=1", "--dpi-desync-repeats=5",
         "--dpi-desync-fake-tls={fake_tls_sochi}", "--dpi-desync-fake-tls={fake_stun2}",
         "--dpi-desync-fake-http={fake_tls_sochi}"),
        tier=1, risk=1,
        description="Новый general-профиль ALT13: altorder hostfakesplit и Sochi/STUN2 payloads.",
    ),
    Strategy(
        "ts-hostfakesplit-google", "Host fake split + TCP timestamp", "timestamp-hostfake", Protocol.HTTPS,
        ("--dpi-desync=hostfakesplit", "--dpi-desync-fooling=ts",
         "--dpi-desync-hostfakesplit-mod=host=www.google.com"),
        tier=1, risk=1,
        description="Подмена Host внутри fake split; полезна для CDN и updater-трафика.",
    ),
    Strategy(
        "split-midsld", "Multi-split по SLD", "split", Protocol.HTTPS,
        ("--dpi-desync=multisplit", "--dpi-desync-split-pos=1,midsld"),
        tier=1, risk=1,
    ),
    Strategy(
        "disorder-midsld", "Multi-disorder по SLD", "disorder", Protocol.HTTPS,
        ("--dpi-desync=multidisorder", "--dpi-desync-split-pos=1,midsld"),
        tier=1, risk=1,
    ),
    Strategy(
        "split-overlap-fast", "Multi-split с TLS overlap", "split-overlap", Protocol.HTTPS,
        ("--dpi-desync=multisplit", "--dpi-desync-split-pos=1", "--dpi-desync-split-seqovl=517", "--dpi-desync-split-seqovl-pattern={fake_tls}"),
        tier=1, risk=1,
        description="Overlap-профиль на официальном TLS fake из zapret-win-bundle.",
    ),
    Strategy(
        "fake-split-overlap-fast", "Fake + split + TLS overlap", "fake-split-overlap", Protocol.HTTPS,
        ("--dpi-desync=fake,multisplit", "--dpi-desync-split-pos=1", "--dpi-desync-split-seqovl=517", "--dpi-desync-split-seqovl-pattern={fake_tls}", "--dpi-desync-fooling=badseq,md5sig", "--dpi-desync-repeats=6", TLS_FAKE),
        tier=1, risk=2,
    ),
    Strategy(
        "fake-tlsmods-fast", "Fake TLS mod + md5sig", "fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=md5sig", "--dpi-desync-repeats=6", TLS_FAKE, "--dpi-desync-fake-tls-mod=rnd,rndsni,dupsid"),
        tier=1, risk=2,
    ),
    Strategy(
        "fake-badseq", "Fake + badseq", "fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=badseq", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=1, risk=2,
    ),
    Strategy(
        "fake-md5sig", "Fake + md5sig", "fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=md5sig", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=1, risk=2,
    ),
    Strategy(
        "fake-disorder", "Fake + multi-disorder", "fake-disorder", Protocol.HTTPS,
        ("--dpi-desync=fake,multidisorder", "--dpi-desync-split-pos=1,midsld", "--dpi-desync-fooling=badseq", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=1, risk=2,
    ),
    Strategy(
        "fake-split", "Fake + multi-split", "fake-split", Protocol.HTTPS,
        ("--dpi-desync=fake,multisplit", "--dpi-desync-split-pos=1,midsld", "--dpi-desync-fooling=md5sig", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=1, risk=2,
    ),
    Strategy(
        "fakedsplit", "Fake-data split", "fakedsplit", Protocol.HTTPS,
        ("--dpi-desync=fakedsplit", "--dpi-desync-split-pos=midsld", "--dpi-desync-fooling=badseq", "--dpi-desync-fakedsplit-pattern={fake_tls}"),
        tier=1, risk=2,
    ),
    Strategy(
        "hostfakesplit", "Host fake split", "hostfakesplit", Protocol.HTTPS,
        ("--dpi-desync=hostfakesplit", "--dpi-desync-hostfakesplit-midhost=midsld"),
        tier=1, risk=2,
    ),
    Strategy(
        "fake-autottl", "Fake + AutoTTL", "autottl", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-autottl=-2", "--dpi-desync-fooling=badseq", "--dpi-desync-repeats=4", TLS_FAKE),
        tier=2, risk=3,
    ),
    Strategy(
        "fake-badsum", "Fake + badsum", "fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=badsum", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=2, risk=2,
    ),
    Strategy(
        "fake-datanoack", "Fake + datanoack", "fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=datanoack", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=2, risk=2,
    ),
    Strategy(
        "fakeddisorder", "Fake-data disorder", "fakeddisorder", Protocol.HTTPS,
        ("--dpi-desync=fakeddisorder", "--dpi-desync-split-pos=midsld", "--dpi-desync-fooling=badseq", "--dpi-desync-fakedsplit-pattern={fake_tls}"),
        tier=2, risk=3,
    ),
    Strategy(
        "syndata-split", "SYN-data + split", "syndata", Protocol.HTTPS,
        ("--dpi-desync=syndata,multisplit", "--dpi-desync-split-pos=midsld", "--dpi-desync-fake-syndata={fake_tls}"),
        tier=2, risk=3,
    ),
    Strategy(
        "split-overlap", "Split с перекрытием", "split-overlap", Protocol.HTTPS,
        ("--dpi-desync=multisplit", "--dpi-desync-split-pos=10,midsld", "--dpi-desync-split-seqovl=1"),
        tier=2, risk=2,
    ),
    Strategy(
        "fake-ttl-3", "Fake с TTL 3", "ttl", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-ttl=3", "--dpi-desync-repeats=4", TLS_FAKE),
        tier=2, risk=3,
    ),
    Strategy(
        "wssize", "Server window size", "wssize", Protocol.HTTPS,
        ("--wssize=1:6",), tier=3, risk=4,
    ),
    Strategy(
        "ipfrag2", "TCP fragmentation", "fragment", Protocol.HTTPS,
        ("--dpi-desync=ipfrag2", "--dpi-desync-ipfrag-pos-tcp=32"),
        tier=3, risk=4,
    ),
    Strategy(
        "fake-ts", "Fake + TCP timestamp", "fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=ts", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=3, risk=4,
        description="Работает только при включенных TCP timestamps в Windows.",
    ),
    Strategy(
        "fake-hopbyhop", "Fake + IPv6 hop-by-hop", "ipv6", Protocol.HTTPS,
        ("--filter-l3=ipv6", "--dpi-desync=fake", "--dpi-desync-fooling=hopbyhop", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=3, risk=4,
    ),
    Strategy(
        "fake-tlsmods", "Fake с TLS-модификациями", "fake", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=md5sig", "--dpi-desync-repeats=6", TLS_FAKE, "--dpi-desync-fake-tls-mod=rnd,rndsni,dupsid"),
        tier=3, risk=3,
    ),
    Strategy(
        "fakeknown-badseq", "Known fake + badseq", "fakeknown", Protocol.HTTPS,
        ("--dpi-desync=fakeknown", "--dpi-desync-fooling=badseq", "--dpi-desync-repeats=2", TLS_FAKE),
        tier=3, risk=3,
    ),
    Strategy(
        "rst", "RST против пассивного DPI", "reset", Protocol.HTTPS,
        ("--dpi-desync=rst",), tier=3, risk=4,
    ),
    Strategy(
        "rstack", "RST+ACK против пассивного DPI", "reset", Protocol.HTTPS,
        ("--dpi-desync=rstack",), tier=3, risk=4,
    ),
    Strategy(
        "synack-split", "Разделение TCP handshake", "handshake", Protocol.HTTPS,
        ("--synack-split=syn",), tier=3, risk=4,
    ),
    Strategy(
        "fake-orig-ttl", "Fake + подавление первого ACK", "orig-ttl", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=badseq", "--orig-ttl=1", "--orig-mod-start=s1", "--orig-mod-cutoff=d1", TLS_FAKE),
        tier=3, risk=4,
    ),
    Strategy(
        "fake-dup-md5", "Fake + дубликат md5sig", "duplicate", Protocol.HTTPS,
        ("--dpi-desync=fake", "--dpi-desync-fooling=md5sig", "--dup=1", "--dup-cutoff=n2", "--dup-fooling=md5sig", TLS_FAKE),
        tier=3, risk=4,
    ),
)


QUIC_STRATEGIES: tuple[Strategy, ...] = (
    Strategy(
        "quic-fake-2", "QUIC fake x2", "quic-fake", Protocol.QUIC,
        ("--dpi-desync=fake", "--dpi-desync-repeats=2", QUIC_FAKE), tier=1, risk=1,
    ),
    Strategy(
        "quic-fake-6", "QUIC fake x6", "quic-fake", Protocol.QUIC,
        ("--dpi-desync=fake", "--dpi-desync-repeats=6", QUIC_FAKE), tier=1, risk=2,
    ),
    Strategy(
        "quic-fake-11", "QUIC fake x11", "quic-fake", Protocol.QUIC,
        ("--dpi-desync=fake", "--dpi-desync-repeats=11", QUIC_FAKE), tier=2, risk=2,
    ),
    Strategy(
        "quic-ipfrag-8", "QUIC fragment 8", "quic-fragment", Protocol.QUIC,
        ("--dpi-desync=ipfrag2", "--dpi-desync-ipfrag-pos-udp=8"), tier=2, risk=3,
    ),
    Strategy(
        "quic-ipfrag-24", "QUIC fragment 24", "quic-fragment", Protocol.QUIC,
        ("--dpi-desync=ipfrag2", "--dpi-desync-ipfrag-pos-udp=24"), tier=3, risk=3,
    ),
    Strategy(
        "quic-fake-ipfrag", "QUIC fake + fragment", "quic-combined", Protocol.QUIC,
        ("--dpi-desync=fake,ipfrag2", "--dpi-desync-repeats=6", "--dpi-desync-ipfrag-pos-udp=24", QUIC_FAKE),
        tier=3, risk=4,
    ),
    Strategy(
        "quic-udplen", "QUIC UDP length", "quic-udplen", Protocol.QUIC,
        ("--dpi-desync=udplen", "--dpi-desync-udplen-increment=2"), tier=3, risk=4,
    ),
    Strategy(
        "quic-fake-default", "QUIC built-in fake", "quic-fake", Protocol.QUIC,
        ("--dpi-desync=fake", "--dpi-desync-repeats=6"), tier=3, risk=3,
    ),
)


FAST_TCP_BY_SERVICE: dict[str, tuple[str, ...]] = {
    "discord_app": (
        "ts-fakedsplit-zero",
        "ts-fake",
        "ts-overlap-681-google-r8",
        "ts-overlap-681-google-r7",
        "ts-hostfakesplit-mail-sochi",
        "ts-overlap-664-stun2",
        "ts-overlap-664",
        "ts-overlap-681",
        "ts-fake-4pda",
        "ts-hostfakesplit-google",
        "badseq-fakedsplit-rnd",
        "badseq-fake-google",
        "split-overlap-568-4pda",
        "disorder-midsld",
        "fake-tlsmods-fast",
        "fake-autottl",
    ),
    "discord_update": (
        "ipid-hostfakesplit-google",
        "ipid-overlap-681",
        "ipid-fakedsplit-zero",
        "ts-hostfakesplit-google",
        "ts-overlap-681",
        "ts-fake",
        "ts-fakedsplit-zero",
        "disorder-midsld",
        "fake-badseq",
        "fake-md5sig",
        "fake-autottl",
    ),
    "youtube": (
        "disorder-midsld",
        "split-midsld",
        "ts-hostfakesplit-google",
        "ts-fake",
        "ts-fakedsplit-zero",
        "ts-overlap-664",
        "ts-overlap-681",
    ),
    "telegram": (
        "disorder-midsld",
        "ts-hostfakesplit-mail-sochi",
        "ts-overlap-664-stun2",
        "ts-fake",
        "ts-fakedsplit-zero",
        "ts-overlap-681",
        "split-midsld",
    ),
    "custom": (
        "ts-hostfakesplit-mail-sochi",
        "ts-overlap-664-stun2",
        "ts-fake",
        "ts-fakedsplit-zero",
        "ts-overlap-664",
        "ts-overlap-681",
        "ts-fake-4pda",
        "disorder-midsld",
        "split-midsld",
        "badseq-fakedsplit-rnd",
        "badseq-fake-google",
        "fake-tlsmods-fast",
    ),
}


def tcp_strategy_by_id(strategy_id: str) -> Strategy:
    return next(strategy for strategy in TCP_STRATEGIES if strategy.id == strategy_id)


def strategies_for(protocol: Protocol, service: str = "custom") -> list[Strategy]:
    if protocol is Protocol.QUIC:
        fast_ids = ("quic-fake-2", "quic-fake-6", "quic-fake-11")
        by_id = {strategy.id: strategy for strategy in QUIC_STRATEGIES}
        preferred = [by_id[strategy_id] for strategy_id in fast_ids]
        return preferred + [strategy for strategy in QUIC_STRATEGIES if strategy.id not in fast_ids]
    fast_ids = FAST_TCP_BY_SERVICE.get(service, FAST_TCP_BY_SERVICE["custom"])
    preferred = [tcp_strategy_by_id(strategy_id) for strategy_id in fast_ids]
    return preferred + [strategy for strategy in TCP_STRATEGIES if strategy.id not in fast_ids]


def refinements_for(strategy: Strategy) -> list[Strategy]:
    """Produce a small local search around a successful family representative."""
    if strategy.protocol is Protocol.QUIC:
        return [item for item in QUIC_STRATEGIES if item.family == strategy.family and item.id != strategy.id]

    refinements: list[Strategy] = []
    if strategy.family in {"split", "disorder", "fake-split", "fake-disorder"}:
        for suffix, position in (("sni", "sniext+1,midsld"), ("wide", "1,sniext+4,midsld")):
            options = tuple(
                f"--dpi-desync-split-pos={position}" if option.startswith("--dpi-desync-split-pos=") else option
                for option in strategy.options
            )
            refinements.append(replace(strategy, id=f"{strategy.id}-{suffix}", name=f"{strategy.name} ({suffix})", options=options))
    if strategy.family in {"fake", "fake-split", "fake-disorder", "autottl", "ttl"}:
        for repeats in (1, 6):
            options = tuple(
                f"--dpi-desync-repeats={repeats}" if option.startswith("--dpi-desync-repeats=") else option
                for option in strategy.options
            )
            refinements.append(replace(strategy, id=f"{strategy.id}-r{repeats}", name=f"{strategy.name} x{repeats}", options=options))
    return refinements[:4]
