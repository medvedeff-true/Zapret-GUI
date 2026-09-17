from __future__ import annotations

from .models import Target


# YouTube group mirrors the list shipped in the official zapret-win-bundle.
YOUTUBE_DOMAINS = frozenset(
    {
        "googlevideo.com",
        "youtubei.googleapis.com",
        "ytimg.com",
        "yt3.ggpht.com",
        "yt4.ggpht.com",
        "youtube.com",
        "youtubeembeddedplayer.googleapis.com",
        "ytimg.l.google.com",
        "jnn-pa.googleapis.com",
        "youtube-nocookie.com",
        "youtube-ui.l.google.com",
        "yt-video-upload.l.google.com",
        "wide-youtube.l.google.com",
        "youtu.be",
    }
)

DISCORD_DOMAINS = frozenset(
    {
        "dis.gd",
        "discord.app",
        "discord.co",
        "discord.com",
        "discord.design",
        "discord.gg",
        "discord.media",
        "discordapp.com",
        "discordapp.net",
        "discordcdn.com",
        "discord.dev",
        "discord.gift",
        "discord.gifts",
        "discord.new",
        "discord.store",
        "discord.status",
        "discord-activities.com",
        "discordactivities.com",
        "discordmerch.com",
        "discordpartygames.com",
        "discordsays.com",
        "discordsez.com",
        "discordstatus.com",
        "discord-attachments-uploads-prd.storage.googleapis.com",
        "updates.discord.com",
        "dl.discordapp.net",
        "stable.dl2.discordapp.net",
    }
)

# Chromium can hide Discord's real SNI with Cloudflare ECH. These are cover names,
# not Discord services themselves, so they must not trigger Discord classification.
DISCORD_COVER_DOMAINS = frozenset(
    {
        "cloudflare-ech.com",
        "encryptedsni.com",
        "cloudfront.net",
    }
)

DISCORD_UPDATE_DOMAINS = frozenset(
    {
        "updates.discord.com",
        "dl.discordapp.net",
        "stable.dl2.discordapp.net",
        "discord-attachments-uploads-prd.storage.googleapis.com",
    }
)

TELEGRAM_DOMAINS = frozenset(
    {
        "web.telegram.org",
        "webk.telegram.org",
        "telegram.org",
        "t.me",
        "telegram.me",
        "telegram.dog",
        "telegram.space",
        "telesco.pe",
        "cdn.telesco.pe",
        "cdn1.telesco.pe",
        "cdn2.telesco.pe",
        "cdn3.telesco.pe",
        "cdn4.telesco.pe",
        "cdn5.telesco.pe",
        "api.telegram.org",
        "my.telegram.org",
        "oauth.telegram.org",
        "core.telegram.org",
        "td.telegram.org",
        "tg.dev",
        "vesta.web.telegram.org",
        "vesta-1.web.telegram.org",
        "venus.web.telegram.org",
        "venus-1.web.telegram.org",
        "kws2.web.telegram.org",
        "kws2-1.web.telegram.org",
        "kws4.web.telegram.org",
        "kws4-1.web.telegram.org",
        "zws2.web.telegram.org",
        "zws2-1.web.telegram.org",
        "zws4.web.telegram.org",
        "zws4-1.web.telegram.org",
    }
)

TELEGRAM_WEB_IP = "149.154.167.220"
DISCORD_MEDIA_IP = "104.25.158.178"


def expanded_hosts(targets: list[Target]) -> list[str]:
    hosts = {target.hostname for target in targets}
    if any(_belongs(host, YOUTUBE_DOMAINS) for host in hosts):
        hosts.update(YOUTUBE_DOMAINS)
    if any(_belongs(host, DISCORD_DOMAINS) for host in hosts):
        hosts.update(DISCORD_DOMAINS)
        hosts.update(DISCORD_COVER_DOMAINS)
    if any(_belongs(host, TELEGRAM_DOMAINS) for host in hosts):
        hosts.update(TELEGRAM_DOMAINS)
    return sorted(hosts)


def service_for_host(host: str) -> str:
    if _belongs(host, YOUTUBE_DOMAINS):
        return "youtube"
    if _belongs(host, DISCORD_DOMAINS):
        return "discord"
    if _belongs(host, TELEGRAM_DOMAINS):
        return "telegram"
    return "custom"


def grouped_targets(targets: list[Target]) -> dict[str, list[Target]]:
    groups: dict[str, list[Target]] = {}
    for target in targets:
        groups.setdefault(target.profile or target.service, []).append(target)
    return groups


def profile_hosts(profile: str, targets: list[Target]) -> list[str]:
    if profile == "discord_app":
        hosts = set((DISCORD_DOMAINS - DISCORD_UPDATE_DOMAINS) | DISCORD_COVER_DOMAINS)
        # `discord.com` and `discordapp.net` would otherwise include updater subdomains
        # because hostlists match subdomains by default. `^` makes these two entries exact.
        hosts.discard("discord.com")
        hosts.discard("discordapp.net")
        hosts.update({"^discord.com", "^discordapp.net"})
        hosts.update(
            f"^{target.hostname}" if target.hostname in {"discord.com", "discordapp.net"} else target.hostname
            for target in targets
        )
        return sorted(hosts)
    if profile == "discord_update":
        return sorted(DISCORD_UPDATE_DOMAINS)
    return expanded_hosts(targets)


def host_overrides(targets: list[Target]) -> dict[str, str]:
    overrides: dict[str, str] = {}
    if any(target.service == "telegram" for target in targets):
        overrides.update({host: TELEGRAM_WEB_IP for host in TELEGRAM_DOMAINS})
    if any(target.service == "discord" for target in targets):
        overrides.update(
            {f"finland{index}.discord.media": DISCORD_MEDIA_IP for index in range(10000, 10200)}
        )
    return overrides


def _belongs(host: str, domains: frozenset[str]) -> bool:
    return any(host == domain or host.endswith("." + domain) for domain in domains)

