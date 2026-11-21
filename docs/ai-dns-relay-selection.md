# Ai DNS: adaptive relay selection

## November 20: independent providers and cache-first recovery

No network-change
watcher or new background timer is added. Existing activation/manual refresh
and the existing startup worker use the same selector:

1. Revalidate last-known-good and currently managed mappings first.
2. For unresolved groups only, try cached public-provider snapshots, the
   preceding MALW download and installed/bundled seeds.
3. Fetch current MALW and GeoHide RU/EU/US lists alongside official MALW,
   DNS-AI, Geodema, Comss and Bezmezhau Sync DoH answers for unresolved groups.
   HTTP/2 and RFC 8484 wire format are supported. Fetching in parallel avoids
   waiting to exhaust all failed addresses from one operator first.
4. Check recent MALW history for **any unresolved group**, even when others work.

Good groups are preserved without repeated probes during one refresh. Failed
`(IP, SNI)` probes are also memoized. Repeated entries in GeoHide lists remain
alternate candidates, up to eight addresses per hostname. Regions are not
independent providers. Zapret DNS timed out during integration and was not
included; the deleted Goida-AI-Unlocker source is no longer downloaded.

Gemini web, AI Studio and auxiliary Google tools have separate statuses.
Gemini API (`generativelanguage.googleapis.com`) is excluded from selection,
DoH queries, publication and status, including old cached profiles.
Google checks inspect bounded response bodies for region denial and
CAPTCHA, unexpected/unsupported/consent redirects, access denial, rate limiting
and upstream failure. Mapped Gemini and Studio RPC hosts are checked too. Login redirects
are transport success, **not authenticated account eligibility**.

`ai_dns_sources.json` under the existing user application directory holds the
latest and previous distinct snapshot per source. Partial refreshes merge
service groups without dropping unrelated cached groups. Downloaded and cached
data are never trusted without live relay validation. Missing/corrupt caches
are ignored, so old installations need no manual migration.

`dns_malw_hosts_last_good.txt` is updated with the merged verified result only
after service publication succeeds. When no group passes, neither hosts nor
the last-good list is changed. No bypass-engine or service changes are needed.

Only public addresses and explicit AI domain suffixes are used. DoH accepts
only addresses in the original question's CNAME chain. Downloads, response
bodies, candidates and concurrency are bounded; TLS verification stays on.
Dependencies and release packaging include DNS-wire and HTTP/2 support.
No EXE was built. Free public providers still cannot guarantee future uptime.

## Direct-Google false positives and latency fix

Some Smart DNS resolvers return ordinary Google frontend A records, not relay
addresses, for Google services. Previously these were accepted as "working
Gemini" because the unauthenticated shell returned HTTP 200. An actual browser
account still saw a regional restriction. This was a false-positive route
selection, not evidence that the regional restriction had been bypassed.

Google-operated frontend networks (including the screenshot's 142.251/142.250,
64.233.162 and 173.194 addresses) are now rejected as Google relay candidates
before opening sockets. The same guard applies to cached/last-good mappings
and RPC hosts, and DoH filters direct answers before caching them. The frontend
range snapshot was verified against Google's official `goog.json` on November
20, 2026. Generic Google Cloud tenant ranges are not indiscriminately blocked.

Single-group candidates run in batches of four with a bounded worker pool
instead of one serial candidate per six-second timeout. Failed frontends skip
RPC checks. Selection stages have 8-second local/cache budgets, a 24-second
per-selection budget and one shared 50-second operation deadline (source
downloads use their own bounded HTTP timeouts). Fresh exact DoH mappings
precede static-list alternates. Removing API eliminates its retries and
history recovery altogether. These are bounds, not a fixed UI response time.

The live migration check replaced the screenshot's direct Google addresses
with Bezmezhau Sync relay mappings, including Gemini and Studio RPC endpoints:
first search approximately 31 seconds, second last-good validation 3 seconds.
All caches in that check were temporary; no system hosts changes or browser
account validation were performed. This is **not** a claim of authenticated
Gemini use; the UI now includes that qualification.


## Transport and atomic publication

Non-Google services retain transport-only checks: an HTTP response alone does
not prove login, API authorization or regional eligibility. Google frontend
HTTP 200 responses also require an expected service marker, not a generic
proxy page. No credentials, cookies or TLS interception are used.

The existing privileged service atomically publishes only verified mappings,
preserves unrelated hosts entries, and rejects concurrent hosts changes.
Failed groups are omitted from a partial publication rather than pinned to
dead IPs. Per-group attempts and timestamps remain available in settings.
