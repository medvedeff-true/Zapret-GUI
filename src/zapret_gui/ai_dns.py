"""Bounded, credential-free HTTPS relay selection. No DNS/hosts modifications."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import ipaddress
import http.client
import re
import socket
import ssl
import time


@dataclass(frozen=True)
class Group:
    label: str
    probes: tuple[str, ...]
    suffixes: tuple[str, ...]
    required: bool = False


# Do not import upstream's unrelated game, advertising or GitHub mappings into
# a feature advertised as AI-only. Extend this explicit catalog deliberately.
GROUPS = {
    "openai": Group("ChatGPT / OpenAI", ("chatgpt.com", "auth.openai.com", "api.openai.com"),
                    ("chatgpt.com", "openai.com", "oaistatic.com", "oaiusercontent.com"), True),
    "gemini": Group("Gemini",
                    ("gemini.google.com",),
                    ("gemini.google.com",
                     "geminiweb-pa.clients6.google.com",
                     "geminiweb-pa.clients.google.com",
                     "assistant-s3-pa.googleapis.com", "proactivebackend-pa.googleapis.com",
                     "robinfrontend-pa.googleapis.com"), True),
    "google_studio": Group("Google AI Studio", ("aistudio.google.com",),
                    ("aistudio.google.com",
                     "webchannel-alkalimakersuite-pa.clients6.google.com",
                     "alkalimakersuite-pa.clients6.google.com", "alkalimakersuite-pa.googleapis.com"), True),
    "google_labs": Group("Google AI tools", (),
                    ("aisandbox-pa.googleapis.com",
                     "aitestkitchen.withgoogle.com", "labs.google", "notebooklm.google.com",
                     "notebook.google.com", "jules.google.com", "stitch.withgoogle.com",
                     "flow.google.com")),
    "claude": Group("Claude / Anthropic", ("claude.ai", "api.anthropic.com"),
                    ("claude.ai", "anthropic.com", "claude.com"), True),
    "copilot": Group("Microsoft / GitHub Copilot", ("copilot.microsoft.com",),
                     ("copilot.microsoft.com", "githubcopilot.com", "sydney.bing.com", "edgeservices.bing.com")),
    "grok": Group("Grok", ("grok.com",), ("grok.com", "x.ai")),
    "perplexity": Group("Perplexity", ("perplexity.ai",), ("perplexity.ai",)),
    "elevenlabs": Group("ElevenLabs", ("elevenlabs.io",), ("elevenlabs.io",)),
    "developer": Group("Windsurf / JetBrains AI", (),
                       ("windsurf.com", "codeium.com", "api.jetbrains.ai", "datalore.jetbrains.com")),
}
MAX_BUNDLE_BYTES = 2 * 1024 * 1024
MAX_ENTRIES = 2048
MAX_GROUP_CANDIDATES = 32
MAX_SOURCE_PROFILES = 8
MAX_RELAYS_PER_PROFILE = 8
PROBE_TIMEOUT = 6.0
PROBE_BATCH_SIZE = 4
SELECTION_TIMEOUT = 24.0
GOOGLE_GROUPS = {"gemini", "google_studio", "google_labs"}
# Google-operated frontend ranges, not generic Google Cloud tenant networks.
# Snapshot verified against https://www.gstatic.com/ipranges/goog.json,
# 2026-11-20. A Smart DNS answer in these ranges is direct Google, NOT proof of
# an SNI relay/foreign egress. Also reject old last-good entries from that bug.
_GOOGLE_FRONTENDS = tuple(ipaddress.ip_network(prefix) for prefix in (
    "64.233.160.0/19", "66.102.0.0/20", "66.249.64.0/19",
    "72.14.192.0/18", "74.125.0.0/16", "108.177.0.0/17",
    "142.250.0.0/15", "172.217.0.0/16", "172.253.0.0/16",
    "173.194.0.0/16", "209.85.128.0/17", "216.58.192.0/19",
    "216.239.32.0/19", "2001:4860::/32", "2404:6800::/32",
    "2607:f8b0::/32", "2800:3f0::/32", "2a00:1450::/32",
))
_HOST = re.compile(r"(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z0-9-]{2,63}\Z")


def is_direct_google(ip: str, host: str) -> bool:
    if group_for_host(host) not in GOOGLE_GROUPS:
        return False
    address = ipaddress.ip_address(ip)
    return any(address.version == network.version and address in network
               for network in _GOOGLE_FRONTENDS)


def group_for_host(host: str) -> str:
    for key, group in GROUPS.items():
        if any(host == suffix or host.endswith("." + suffix) for suffix in group.suffixes):
            return key
    return ""


def parse_bundle(text: str) -> dict[str, list[str]]:
    if len(text.encode("utf-8")) > MAX_BUNDLE_BYTES:
        raise ValueError("Ai DNS bundle exceeds 2 MiB")
    hosts: dict[str, list[str]] = {}
    count = 0
    for line in text.splitlines():
        parts = line.split("#", 1)[0].split()
        if len(parts) < 2:
            continue
        try:
            address = ipaddress.ip_address(parts[0])
        except ValueError:
            continue
        # Never probe LAN, loopback, link-local or upstream ad-block sinkholes.
        if not address.is_global:
            continue
        for raw in parts[1:]:
            host = raw.lower().rstrip(".")
            if not _HOST.fullmatch(host) or not group_for_host(host):
                continue
            addresses = hosts.setdefault(host, [])
            ip = str(address)
            if ip not in addresses and len(addresses) < MAX_SOURCE_PROFILES:
                addresses.append(ip)
                count += 1
                if count > MAX_ENTRIES:
                    raise ValueError("Too many Ai DNS mappings")
    return hosts


def render_bundle(hosts: dict[str, str]) -> str:
    return "".join(f"{ip} {host}\n" for host, ip in sorted(hosts.items()))


def classify_response(host: str, code: int, location: str = "", body: bytes = b"") -> str:
    """Empty means usable transport; never claims authenticated account access."""
    if not 200 <= code <= 599:
        return "invalid-http"
    if group_for_host(host) not in GOOGLE_GROUPS:
        return ""
    text = body.decode("utf-8", errors="replace").lower()
    target = location.lower()
    if any(token in target for token in ("/sorry", "/unsupported", "consent.google.")):
        return "google-challenge-or-region"
    if any(token in text for token in (
        "user location is not supported", "not available in your country",
        "not available in your region", "isn't available in your country",
        "isn’t available in your country", "unsupported_country",
        "country, region, or territory", "location is not supported",
        "недоступен в вашей стране", "недоступен в вашем регионе",
        "недоступно в вашей стране", "недоступно в вашем регионе",
    )):
        return "google-region-blocked"
    if "recaptcha" in text or "our systems have detected unusual traffic" in text:
        return "google-captcha"
    if code in {403, 451}:
        return "google-access-denied"
    if code == 429:
        return "google-rate-limited"
    if code == 421 or code >= 500:
        return "google-upstream-unavailable"
    # A web frontend returning a generic error is not a working Gemini page.
    if host in {"gemini.google.com", "aistudio.google.com"} and code >= 400:
        return "google-web-unavailable"
    if host in {"gemini.google.com", "aistudio.google.com"} and code == 200:
        markers = ("gemini",) if host == "gemini.google.com" else (
            "google ai studio", "aistudio.google.com", "alkalimakersuite",
        )
        if not any(marker in text for marker in markers):
            return "google-unexpected-page"
    if 300 <= code < 400:
        from urllib.parse import urlsplit
        redirect = urlsplit(location)
        if not location or redirect.scheme not in {"", "https"} or (
            redirect.netloc and redirect.hostname not in {host, "accounts.google.com"}
        ):
            return "google-unexpected-redirect"
    return ""


def probe_relay(ip: str, host: str, *, timeout: float = PROBE_TIMEOUT, context=None) -> dict:
    """Force a literal IP while retaining SNI/Host and normal certificate checks.

    Google responses are screened for regional denial/challenges. No cookies,
    account tokens or redirect following; login/account eligibility is unknown.
    """
    started = time.monotonic()
    deadline = started + timeout
    stage = "tcp"
    try:
        address = ipaddress.ip_address(ip)
        if not address.is_global:
            return {"ok": False, "error": "non-public-address"}
        if host == "generativelanguage.googleapis.com":
            return {"ok": False, "error": "api-disabled"}
        if is_direct_google(ip, host):
            return {"ok": False, "error": "google-direct-not-relay"}
        context = context or ssl.create_default_context()
        family = socket.AF_INET6 if address.version == 6 else socket.AF_INET
        with socket.socket(family, socket.SOCK_STREAM) as raw:
            raw.settimeout(max(0.01, deadline - time.monotonic()))
            raw.connect((ip, 443))
            stage = "tls"
            raw.settimeout(max(0.01, deadline - time.monotonic()))
            with context.wrap_socket(raw, server_hostname=host) as secure:
                stage = "http"
                secure.settimeout(max(0.01, deadline - time.monotonic()))
                path = "/app" if host == "gemini.google.com" else "/"
                secure.sendall((
                    f"GET {path} HTTP/1.1\r\nHost: {host}\r\n"
                    "User-Agent: Mozilla/5.0 ZapretGUI-AiDNS\r\n"
                    "Accept: */*\r\nAccept-Encoding: identity\r\nConnection: close\r\n\r\n"
                ).encode("ascii"))
                with http.client.HTTPResponse(secure) as response:
                    response.begin()
                    code = response.status
                    location = response.getheader("Location", "")
                    body = bytearray()
                    if group_for_host(host) in GOOGLE_GROUPS:
                        # read1 never waits to fill the whole requested buffer;
                        # every iteration shares the original overall deadline.
                        while len(body) < 65536:
                            remaining = deadline - time.monotonic()
                            if remaining <= 0:
                                raise TimeoutError()
                            secure.settimeout(remaining)
                            chunk = response.read1(min(4096, 65536 - len(body)))
                            if not chunk:
                                break
                            body.extend(chunk)
                    error = classify_response(host, code, location, bytes(body))
                return {"ok": not error, "http": code, "error": error,
                        "access": "account-not-verified",
                        "ms": round((time.monotonic() - started) * 1000)}
    except ssl.SSLCertVerificationError:
        error = "tls-certificate"
    except (TimeoutError, socket.timeout):
        error = stage + "-timeout"
    except PermissionError:
        error = stage + "-access-denied"
    except (OSError, ssl.SSLError, ValueError, http.client.HTTPException):
        error = stage + "-failed"
    return {"ok": False, "error": error, "ms": round((time.monotonic() - started) * 1000)}


def select_relays(sources: list[tuple[str, str]], *, probe=None, groups=None,
                  probe_cache=None, seen_profiles=None, deadline=None) -> tuple[str, dict]:
    """Try ordered source profiles, independently per group. Recheck all LKGs.

    Preserve explicit per-host mappings. Alternative same-group relay IPs are
    eligible only after the control SNI checks; never borrow another group's IP.
    Candidate counts, concurrent sockets and per-socket deadlines are bounded.
    """
    parsed = []
    for label, text in sources[:32]:
        try:
            parsed.append((label, parse_bundle(text)))
        except ValueError:
            continue
    enabled = {key for key, group in GROUPS.items() if group.required}
    enabled.update(group_for_host(host) for _, hosts in parsed for host in hosts)
    enabled.discard("")
    if groups is not None:
        enabled &= set(groups)
    statuses = {key: {"status": "unavailable", "relay": "", "source": "", "checks": []}
                for key in GROUPS if key in enabled}
    profiles = {key: [] for key in statuses}
    alternatives = {key: [] for key in statuses}
    for source, hosts in parsed:
        for key in profiles:
            group_hosts = {host: ips for host, ips in hosts.items() if group_for_host(host) == key}
            if not group_hosts:
                continue
            # The original mapping first; then same-group alternate relay IPs.
            original = {host: ips[0] for host, ips in group_hosts.items()}
            options = [original]
            ips = list(dict.fromkeys(ip for values in group_hosts.values() for ip in values))
            for ip in ips[:MAX_SOURCE_PROFILES]:
                options.append({host: ip for host in group_hosts})
            for option in options:
                group = GROUPS[key]
                if len(set(option.values())) > MAX_RELAYS_PER_PROFILE:
                    continue
                if group.probes:
                    default_ip = next(iter(option.values()))
                    for host in group.probes:
                        option.setdefault(host, default_ip)
                fingerprint = tuple(sorted(option.items()))
                if seen_profiles is not None and fingerprint in seen_profiles.get(key, set()):
                    continue
                if any(existing[2] == fingerprint for existing in profiles[key] + alternatives[key]):
                    continue
                target = profiles[key] if option is original else alternatives[key]
                target.append((source, option, fingerprint))
    for key in profiles:
        profiles[key] = (profiles[key] + alternatives[key])[:MAX_GROUP_CANDIDATES]

    deadline = min(deadline or float("inf"), time.monotonic() + SELECTION_TIMEOUT)
    context = ssl.create_default_context() if probe is None else None
    def run_probe(ip, host):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {"ok": False, "error": "selection-time-budget"}
        if is_direct_google(ip, host):
            return {"ok": False, "error": "google-direct-not-relay"}
        return probe(ip, host) if probe is not None else probe_relay(
            ip, host, context=context, timeout=min(PROBE_TIMEOUT, remaining))
    cache = probe_cache if probe_cache is not None else {}
    selected = {}
    history = {key: [] for key in statuses}
    checked_at = int(time.time())
    with ThreadPoolExecutor(max_workers=12, thread_name_prefix="ai-relay") as pool:
        def check_pairs(pairs):
            jobs = {}
            for pair in pairs:
                if pair not in cache and pair not in jobs:
                    jobs[pair] = pool.submit(run_probe, *pair)
            for pair, future in jobs.items():
                try:
                    value = future.result()
                    cache[pair] = value if isinstance(value, dict) else {"ok": bool(value)}
                except Exception:
                    cache[pair] = {"ok": False, "error": "probe-failed"}

        # Several alternative profiles per group run concurrently, but source
        # preference stays deterministic. Probe frontend(s) first; do not spend
        # sockets/time on RPC/CDN hosts of an already failed frontend.
        for index in range(0, MAX_GROUP_CANDIDATES, PROBE_BATCH_SIZE):
            if time.monotonic() >= deadline:
                break
            attempts = []
            for key, options in profiles.items():
                if key in selected:
                    continue
                for source, mapping, fingerprint in options[index:index + PROBE_BATCH_SIZE]:
                    if seen_profiles is not None:
                        seen_profiles.setdefault(key, set()).add(fingerprint)
                    primary = list(GROUPS[key].probes) or list(mapping)[:1]
                    controls = list(primary)
                    if key == "gemini":
                        controls.extend(host for host in (
                            "geminiweb-pa.clients6.google.com", "geminiweb-pa.clients.google.com",
                        ) if host in mapping)
                    if key == "openai":
                        controls.extend(host for host in (
                            "auth0.openai.com", "cdn.oaistatic.com", "files.oaiusercontent.com",
                        ) if host in mapping)
                    if key == "google_studio":
                        controls.extend(host for host in (
                            "alkalimakersuite-pa.clients6.google.com",
                            "webchannel-alkalimakersuite-pa.clients6.google.com",
                        ) if host in mapping)
                    covered = {mapping[host] for host in controls}
                    for host, ip in mapping.items():
                        if ip not in covered:
                            controls.append(host)
                            covered.add(ip)
                    attempts.append((key, source, mapping, primary, controls))
            check_pairs((mapping[host], host) for _, _, mapping, primary, _ in attempts
                        for host in primary)
            ready = [(key, source, mapping, controls) for key, source, mapping, primary, controls in attempts
                     if all(cache[(mapping[host], host)].get("ok") for host in primary)]
            check_pairs((mapping[host], host) for _, _, mapping, controls in ready for host in controls)
            for key, source, mapping, primary, controls in attempts:
                if key in selected:
                    continue
                controls = [host for host in controls if (mapping[host], host) in cache]
                checks = [dict(cache[(mapping[host], host)], host=host, ip=mapping[host]) for host in controls]
                ok = all(check.get("ok") for check in checks)
                history[key].append({"source": source, "checks": checks})
                statuses[key] = {
                    "status": "ok" if ok else "unavailable", "source": source,
                    "relay": ", ".join(dict.fromkeys(mapping.values())), "checks": checks,
                    "checked_at": checked_at,
                    "attempts": list(history[key]),
                    "access": "account-not-verified" if key in GOOGLE_GROUPS else "transport-only",
                }
                if ok:
                    selected[key] = mapping
    output = {}
    for mapping in selected.values():
        output.update(mapping)
    return render_bundle(output), statuses


class RelaySelection:
    """One manual refresh: preserve good groups and memoize failed checks too."""
    def __init__(self, *, probe=None):
        self.probe = probe
        self.cache = {}
        self.seen = {}
        self.statuses = {}
        self.hosts = {}
        self.deadline = time.monotonic() + 50.0

    @property
    def missing(self):
        expected = {key for key, group in GROUPS.items() if group.required} | set(self.statuses)
        return {key for key in expected if self.statuses.get(key, {}).get("status") != "ok"}

    def add(self, sources, *, timeout=SELECTION_TIMEOUT):
        # Include newly discovered optional services, but never recheck a
        # successful group during this refresh.
        sources = list(sources)
        available = set()
        valid = []
        for label, text in sources:
            try:
                available.update(group_for_host(host) for host in parse_bundle(text))
                valid.append((label, text))
            except ValueError:
                continue
        targets = (self.missing | available) - {
            key for key, status in self.statuses.items() if status.get("status") == "ok"
        }
        text, statuses = select_relays(valid, probe=self.probe, groups=targets,
                                      probe_cache=self.cache, seen_profiles=self.seen,
                                      deadline=min(self.deadline, time.monotonic() + timeout))
        for key, status in statuses.items():
            old = self.statuses.get(key, {})
            # An already tried candidate is absent on later stages; keep its
            # diagnostic rather than replacing it with an empty failure.
            if not status.get("attempts") and old:
                continue
            status["attempts"] = old.get("attempts", []) + status.get("attempts", [])
            self.statuses[key] = status
        for host, ips in parse_bundle(text).items():
            self.hosts[host] = ips[0]
        return render_bundle(self.hosts), self.statuses


def summary(statuses: dict) -> str:
    groups = [info for key, info in statuses.items() if key in GROUPS and isinstance(info, dict)]
    working = sum(info.get("status") == "ok" for info in groups)
    return "none" if not working else "full" if working == len(groups) else "partial"
