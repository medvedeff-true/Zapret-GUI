"""Official public Smart DNS sources; bounded downloads, no system DNS changes."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import time

import dns.message
import dns.exception
import dns.rdatatype
import dns.rcode
import httpx

from .ai_dns import GROUPS, MAX_BUNDLE_BYTES, group_for_host, is_direct_google, parse_bundle
from .hosts_transaction import atomic_write


HOST_SOURCES = {
    "geohide-ru": "https://raw.githubusercontent.com/Internet-Helper/GeoHideDNS/main/hosts/hosts",
    "geohide-eu": "https://raw.githubusercontent.com/Internet-Helper/GeoHideDNS/main/hosts/eu/hosts",
    "geohide-us": "https://raw.githubusercontent.com/Internet-Helper/GeoHideDNS/main/hosts/us/hosts",
}
# Only official endpoints that answered RFC 8484 queries during integration.
# Multiple regions of GeoHide are not counted as independent operators.
DOH_SOURCES = {
    "malw-doh": "https://dns.malw.link/dns-query",
    "dns-ai": "https://dns.dns-ai.ru/dns-query",
    "geodema": "https://dns.geodema.love/dns-query",
    "comss": "https://dns.comss.one/dns-query",
    "bezmezhau-sync": "https://sync.bezmezhau.com/dns-query",
}
SOURCE_IDS = set(HOST_SOURCES) | set(DOH_SOURCES) | {"upstream"}
SUPPORT_HOSTS = {
    "openai": ("cdn.oaistatic.com", "files.oaiusercontent.com", "auth0.openai.com"),
    "gemini": ("geminiweb-pa.clients6.google.com", "geminiweb-pa.clients.google.com"),
    "google_studio": ("alkalimakersuite-pa.clients6.google.com",
                      "webchannel-alkalimakersuite-pa.clients6.google.com"),
}


def _canonical(text):
    if not isinstance(text, str):
        raise ValueError("Invalid hosts source")
    parsed = parse_bundle(text)
    return "".join(f"{ip} {host}\n" for host, ips in sorted(parsed.items()) for ip in ips)


def _read_records(path):
    try:
        if Path(path).stat().st_size > 4 * MAX_BUNDLE_BYTES:
            return {}
        data = Path(path).read_bytes()
        if len(data) > 4 * MAX_BUNDLE_BYTES:
            return {}
        payload = json.loads(data)
        return payload if isinstance(payload, dict) else {}
    except (OSError, ValueError):
        return {}


def load_profiles(path):
    """Two snapshots/provider; neither cached bytes nor age confer trust."""
    profiles = []
    for source, records in _read_records(path).items():
        if source not in SOURCE_IDS or not isinstance(records, list):
            continue
        for index, record in enumerate(records[:2]):
            try:
                text = _canonical(record["hosts"])
                if text:
                    profiles.append((f"cached-{source}-{index}", text))
            except (ValueError, TypeError, KeyError):
                continue
    return profiles


def save_profiles(path, profiles):
    """Merge partial refreshes by group, retaining the preceding snapshot."""
    # Discard unknown keys/corrupt entries before carrying anything forward.
    clean = {}
    for label, text in load_profiles(path):
        source = label.removeprefix("cached-").rsplit("-", 1)[0]
        clean.setdefault(source, []).append({"hosts": text, "updated_at": 0})
    for source, text in profiles:
        if source not in SOURCE_IDS:
            continue
        parsed = parse_bundle(text)
        if not parsed:
            continue
        old = clean.get(source, [])
        previous = parse_bundle(old[0]["hosts"]) if old else {}
        updated_groups = {group_for_host(host) for host in parsed}
        merged = {host: ips for host, ips in previous.items()
                  if group_for_host(host) not in updated_groups}
        merged.update(parsed)
        current = _canonical("".join(f"{ip} {host}\n" for host, ips in merged.items() for ip in ips))
        history = [{"hosts": current, "updated_at": int(time.time())}]
        history.extend(item for item in old if item["hosts"] != current)
        clean[source] = history[:2]
    atomic_write(Path(path), json.dumps(clean, ensure_ascii=False).encode("utf-8"))


def _body(client, method, url, **kwargs):
    deadline = time.monotonic() + 12
    with client.stream(method, url, **kwargs) as response:
        response.raise_for_status()
        data = bytearray()
        for chunk in response.iter_bytes(chunk_size=16384):
            if time.monotonic() > deadline:
                raise TimeoutError("Ai DNS source deadline exceeded")
            data.extend(chunk)
            if len(data) > MAX_BUNDLE_BYTES:
                raise ValueError("Ai DNS source exceeds 2 MiB")
        return bytes(data)


def download_hosts(groups):
    """GeoHide region lists, downloaded independently; all returned IPs untrusted."""
    if not groups:
        return []
    def fetch(item):
        source, url = item
        try:
            with httpx.Client(http2=True, timeout=8, follow_redirects=False) as client:
                text = _canonical(_body(client, "GET", url).decode("utf-8-sig"))
                text = "".join(line + "\n" for line in text.splitlines()
                               if group_for_host(line.split()[1]) in groups)
                return (source, text) if text else None
        except (OSError, ValueError, httpx.HTTPError):
            return None
    with ThreadPoolExecutor(max_workers=3, thread_name_prefix="ai-hosts") as pool:
        return [result for result in pool.map(fetch, HOST_SOURCES.items()) if result]


def query_doh(client, url, host):
    query = dns.message.make_query(host, dns.rdatatype.A)
    data = _body(client, "POST", url, content=query.to_wire(), headers={
        "Content-Type": "application/dns-message", "Accept": "application/dns-message",
    })
    response = dns.message.from_wire(data)
    if not query.is_response(response) or response.rcode() != dns.rcode.NOERROR:
        return []
    # Accept only A records attached to the question's CNAME chain, not
    # unrelated answers/additional records supplied by a remote resolver.
    names = {query.question[0].name}
    for _ in range(8):
        for rrset in response.answer:
            if rrset.name in names and rrset.rdtype == dns.rdatatype.CNAME:
                names.update(item.target for item in rrset)
    ips = [item.address for rrset in response.answer
           if rrset.name in names and rrset.rdtype == dns.rdatatype.A for item in rrset]
    return [ip for ip in parse_bundle("".join(f"{ip} {host}\n" for ip in ips)).get(host, [])
            if not is_direct_google(ip, host)]


def download_doh(groups):
    """Query only unresolved groups, without altering the OS DNS configuration."""
    hosts = list(dict.fromkeys(
        host for key, group in GROUPS.items() if key in groups
        for host in (*group.probes, *SUPPORT_HOSTS.get(key, ()))
    ))[:48]
    if not hosts:
        return []

    def fetch(item):
        source, url = item
        results = {}
        try:
            with httpx.Client(http2=True, timeout=5, follow_redirects=False) as client:
                # One initial request is the circuit breaker for an offline
                # source; do not spend a timeout on every service at that source.
                results[hosts[0]] = query_doh(client, url, hosts[0])
                def resolve(host):
                    try:
                        return host, query_doh(client, url, host)
                    except (OSError, ValueError, dns.exception.DNSException, httpx.HTTPError):
                        return host, []
                with ThreadPoolExecutor(max_workers=3) as pool:
                    results.update(pool.map(resolve, hosts[1:]))
        except (OSError, ValueError, dns.exception.DNSException, httpx.HTTPError):
            return None
        text = "".join(f"{ip} {host}\n" for host, ips in results.items() for ip in ips)
        return (source, text) if text else None

    with ThreadPoolExecutor(max_workers=5, thread_name_prefix="ai-doh") as pool:
        return [result for result in pool.map(fetch, DOH_SOURCES.items()) if result]
