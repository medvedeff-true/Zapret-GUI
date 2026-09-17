# --- DNS.MALW.LINK and hosts-file integration ------------------------------

def _dns_malw_link_common_powershell() -> str:
    return r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Normalize-Servers([object[]]$servers) {
    return @(
        $servers |
        Where-Object { $_ } |
        ForEach-Object { $_.ToString().Trim().ToLowerInvariant() } |
        Sort-Object -Unique
    )
}

function Test-SameServers([object[]]$left, [object[]]$right) {
    $a = Normalize-Servers $left
    $b = Normalize-Servers $right
    if ($a.Count -ne $b.Count) {
        return $false
    }
    for ($i = 0; $i -lt $a.Count; $i++) {
        if ($a[$i] -ne $b[$i]) {
            return $false
        }
    }
    return $true
}

function Get-AdminState() {
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        return $false
    }
}

$ipv4Servers = @(__IPV4__)
$ipv6Servers = @(__IPV6__)
$desiredServers = @($ipv4Servers + $ipv6Servers)
$dohTemplate = '__DOH__'
"""


def _build_dns_malw_link_status_script() -> str:
    script = _dns_malw_link_common_powershell() + r"""
$result = [ordered]@{
    ok = $false
    active = $false
    error = ''
    admin = Get-AdminState
    adapters = 0
    matched = 0
    method = ''
}

try {
    $getDnsClient = Get-Command Get-DnsClient -ErrorAction SilentlyContinue
    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClient -and $getDnsClientServerAddress) {
        $result.method = 'dnsclient'
        $adapters = @(
            Get-DnsClient |
            Where-Object {
                $_.InterfaceAlias -and
                $_.InterfaceOperationalStatus -eq 'Up' -and
                $_.InterfaceAlias -notmatch 'Loopback|isatap|Teredo'
            } |
            Sort-Object InterfaceIndex -Unique
        )
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @(
                Get-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ErrorAction SilentlyContinue |
                ForEach-Object { @($_.ServerAddresses) } |
                Where-Object { $_ }
            )
            if (Test-SameServers $currentServers $desiredServers) {
                $result.matched += 1
            }
        }
    } elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        $result.method = 'cim'
        $adapters = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            if (Test-SameServers @($adapter.DNSServerSearchOrder) $desiredServers) {
                $result.matched += 1
            }
        }
    } elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {
        $result.method = 'wmi'
        $adapters = @(Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            if (Test-SameServers @($adapter.DNSServerSearchOrder) $desiredServers) {
                $result.matched += 1
            }
        }
    } else {
        throw 'No DNS query backend available'
    }

    $result.active = ($result.adapters -gt 0 -and $result.matched -eq $result.adapters)
    $result.ok = $true
} catch {
    $result.error = [string]$_.Exception.Message
}

$result | ConvertTo-Json -Compress
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _build_dns_malw_link_enable_script() -> str:
    script = _dns_malw_link_common_powershell() + r"""
$result = [ordered]@{
    ok = $false
    error = ''
    admin = Get-AdminState
    adapters = 0
    applied = 0
    updated = 0
    doh = $false
    method = ''
    snapshot = @()
}

try {
    if (-not $result.admin) {
        throw 'not-admin'
    }

    $addDohCommand = Get-Command Add-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $setDohCommand = Get-Command Set-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $getDohCommand = Get-Command Get-DnsClientDohServerAddress -ErrorAction SilentlyContinue

    if ($addDohCommand -or $setDohCommand) {
        foreach ($server in $desiredServers) {
            try {
                $hasExisting = $false
                if ($getDohCommand) {
                    $existing = @(Get-DnsClientDohServerAddress -ServerAddress $server -ErrorAction SilentlyContinue)
                    $hasExisting = ($existing.Count -gt 0)
                }

                if ($hasExisting -and $setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }
                if ($addDohCommand) {
                    Add-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }
                if ($setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                }
            } catch {
                try {
                    if ($setDohCommand) {
                        Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                        $result.doh = $true
                    }
                } catch {
                }
            }
        }
    }

    $getDnsClient = Get-Command Get-DnsClient -ErrorAction SilentlyContinue
    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue
    $setDnsClientServerAddress = Get-Command Set-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClient -and $getDnsClientServerAddress -and $setDnsClientServerAddress) {
        $result.method = 'dnsclient'
        $adapters = @(
            Get-DnsClient |
            Where-Object {
                $_.InterfaceAlias -and
                $_.InterfaceOperationalStatus -eq 'Up' -and
                $_.InterfaceAlias -notmatch 'Loopback|isatap|Teredo'
            } |
            Sort-Object InterfaceIndex -Unique
        )
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @(
                Get-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ErrorAction SilentlyContinue |
                ForEach-Object { @($_.ServerAddresses) } |
                Where-Object { $_ }
            )
            $result.snapshot += [pscustomobject]@{
                interface_index = $adapter.InterfaceIndex
                alias = $adapter.InterfaceAlias
                servers = @($currentServers)
            }
            if (Test-SameServers $currentServers $desiredServers) {
                $result.applied += 1
                continue
            }

            Set-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ServerAddresses $desiredServers -ErrorAction Stop | Out-Null
            $result.updated += 1
            $result.applied += 1
        }
    } elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        $result.method = 'cim'
        $adapters = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @($adapter.DNSServerSearchOrder)
            $result.snapshot += [pscustomobject]@{
                interface_index = [int]$adapter.InterfaceIndex
                alias = [string]$adapter.Description
                servers = @($currentServers)
            }
            if (Test-SameServers $currentServers $desiredServers) {
                $result.applied += 1
                continue
            }

            $invokeResult = Invoke-CimMethod -InputObject $adapter -MethodName SetDNSServerSearchOrder -Arguments @{DNSServerSearchOrder = $desiredServers} -ErrorAction Stop
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                $result.updated += 1
                $result.applied += 1
            }
        }
    } elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {
        $result.method = 'wmi'
        $adapters = @(Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            $currentServers = @($adapter.DNSServerSearchOrder)
            $result.snapshot += [pscustomobject]@{
                interface_index = [int]$adapter.InterfaceIndex
                alias = [string]$adapter.Description
                servers = @($currentServers)
            }
            if (Test-SameServers $currentServers $desiredServers) {
                $result.applied += 1
                continue
            }

            $invokeResult = $adapter.SetDNSServerSearchOrder($desiredServers)
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                $result.updated += 1
                $result.applied += 1
            }
        }
    } else {
        throw 'No DNS configuration backend available'
    }

    if ($result.adapters -le 0) {
        throw 'no-active-adapters'
    }
    if ($result.applied -le 0) {
        throw 'dns-apply-failed'
    }

    try {
        if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {
            Clear-DnsClientCache | Out-Null
        } else {
            & ipconfig /flushdns | Out-Null
        }
    } catch {
    }

    $result.ok = $true
} catch {
    $result.error = [string]$_.Exception.Message
}

$result | ConvertTo-Json -Compress -Depth 6
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _build_dns_malw_link_disable_script(snapshot_json: str) -> str:
    escaped_snapshot = snapshot_json.replace("'", "''")
    script = _dns_malw_link_common_powershell() + rf"""
$result = [ordered]@{{
    ok = $false
    error = ''
    admin = Get-AdminState
    adapters = 0
    applied = 0
    updated = 0
    method = ''
}}

try {{
    if (-not $result.admin) {{
        throw 'not-admin'
    }}

    $snapshotRaw = @'
{escaped_snapshot}
'@
    $snapshot = @()
    if ($snapshotRaw.Trim()) {{
        $snapshot = @((ConvertFrom-Json $snapshotRaw -ErrorAction Stop))
    }}
    if ($snapshot.Count -le 0) {{
        throw 'no-snapshot'
    }}
    $result.adapters = $snapshot.Count

    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue
    $setDnsClientServerAddress = Get-Command Set-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClientServerAddress -and $setDnsClientServerAddress) {{
        $result.method = 'dnsclient'
        foreach ($adapter in $snapshot) {{
            $index = [int]$adapter.interface_index
            $servers = @($adapter.servers)
            $currentServers = @(
                Get-DnsClientServerAddress -InterfaceIndex $index -ErrorAction SilentlyContinue |
                ForEach-Object {{ @($_.ServerAddresses) }} |
                Where-Object {{ $_ }}
            )
            if (Test-SameServers $currentServers $servers) {{
                $result.applied += 1
                continue
            }}

            if ($servers.Count -gt 0) {{
                Set-DnsClientServerAddress -InterfaceIndex $index -ServerAddresses $servers -ErrorAction Stop | Out-Null
            }} else {{
                Set-DnsClientServerAddress -InterfaceIndex $index -ResetServerAddresses -ErrorAction Stop | Out-Null
            }}
            $result.updated += 1
            $result.applied += 1
        }}
    }} elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {{
        $result.method = 'cim'
        foreach ($entry in $snapshot) {{
            $index = [int]$entry.interface_index
            $servers = @($entry.servers)
            $adapter = Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop | Where-Object {{ [int]$_.InterfaceIndex -eq $index }} | Select-Object -First 1
            if (-not $adapter) {{
                continue
            }}
            $currentServers = @($adapter.DNSServerSearchOrder)
            if (Test-SameServers $currentServers $servers) {{
                $result.applied += 1
                continue
            }}
            $target = if ($servers.Count -gt 0) {{ $servers }} else {{ $null }}
            $invokeResult = Invoke-CimMethod -InputObject $adapter -MethodName SetDNSServerSearchOrder -Arguments @{{DNSServerSearchOrder = $target}} -ErrorAction Stop
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {{
                $result.updated += 1
                $result.applied += 1
            }}
        }}
    }} elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {{
        $result.method = 'wmi'
        foreach ($entry in $snapshot) {{
            $index = [int]$entry.interface_index
            $servers = @($entry.servers)
            $adapter = Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop | Where-Object {{ [int]$_.InterfaceIndex -eq $index }} | Select-Object -First 1
            if (-not $adapter) {{
                continue
            }}
            $currentServers = @($adapter.DNSServerSearchOrder)
            if (Test-SameServers $currentServers $servers) {{
                $result.applied += 1
                continue
            }}
            $target = if ($servers.Count -gt 0) {{ $servers }} else {{ $null }}
            $invokeResult = $adapter.SetDNSServerSearchOrder($target)
            if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {{
                $result.updated += 1
                $result.applied += 1
            }}
        }}
    }} else {{
        throw 'No DNS configuration backend available'
    }}

    if ($result.applied -le 0) {{
        throw 'dns-restore-failed'
    }}

    try {{
        if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {{
            Clear-DnsClientCache | Out-Null
        }} else {{
            & ipconfig /flushdns | Out-Null
        }}
    }} catch {{
    }}

    $result.ok = $true
}} catch {{
    $result.error = [string]$_.Exception.Message
}}

$result | ConvertTo-Json -Compress
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _run_hidden_powershell_json(script: str, timeout: int = 35) -> dict:
    result = {"ok": False, "error": "powershell-launch-failed"}
    try:
        encoded_script = base64.b64encode(script.encode("utf-16le")).decode("ascii")
        completed = _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-EncodedCommand",
                encoded_script,
            ],
            timeout=timeout,
        )
        if completed is None:
            return result

        stdout = (completed.stdout or "").strip()
        stderr = (completed.stderr or "").strip()
        if stdout:
            for line in reversed([line.strip() for line in stdout.splitlines() if line.strip()]):
                try:
                    payload = json.loads(line)
                except Exception:
                    continue
                if isinstance(payload, dict):
                    if "error" not in payload:
                        payload["error"] = ""
                    return payload

        if stderr:
            result["error"] = stderr.splitlines()[-1].strip()
        elif completed.returncode not in (0, None):
            result["error"] = f"powershell-exit-{completed.returncode}"
        else:
            result["error"] = "empty-powershell-result"
    except Exception as e:
        result["error"] = str(e)
    return result


def _normalize_dns_server_string(value: str) -> str:
    s = (value or "").strip().lower()
    if not s or s in {"none", "нет"}:
        return ""
    if "%" in s:
        s = s.split("%", 1)[0].strip()
    return s


def _parse_netsh_dns_servers(text: str) -> dict[str, list[str]]:
    blocks: dict[str, list[str]] = {}
    current = None
    collecting = False

    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        m = re.match(r'^\s*(?:Configuration for interface|Настройка интерфейса)\s+"(.*)"\s*$', line)
        if m:
            current = m.group(1).strip()
            blocks.setdefault(current, [])
            collecting = False
            continue

        if current is None:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if (
            "Register with which suffix" in stripped
            or "Зарегистрировать с суффиксом" in stripped
        ):
            collecting = False
            continue

        if (
            "DNS Servers" in stripped
            or "DNS servers" in stripped
            or "DNS-серверы" in stripped
        ):
            collecting = True
            _, _, value_part = stripped.partition(":")
            candidate = _normalize_dns_server_string(value_part)
            if candidate:
                blocks[current].append(candidate)
            continue

        if collecting and raw_line[:1].isspace():
            candidate = _normalize_dns_server_string(stripped)
            if candidate:
                blocks[current].append(candidate)

    return {name: _merge_unique(values) for name, values in blocks.items()}


def _get_connected_interface_names() -> list[str]:
    try:
        completed = subprocess.run(
            ["netsh", "interface", "show", "interface"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        output = completed.stdout or ""
    except Exception:
        return []

    names = []
    excluded_markers = (
        "loopback",
        "bluetooth",
        "virtual",
        "hyper-v",
        "vmware",
        "vbox",
        "tap",
        "tun",
        "vpn",
        "wintun",
        "teredo",
    )
    for line in output.splitlines():
        if not line.strip():
            continue
        if (
            line.lstrip().startswith("Admin State")
            or line.lstrip().startswith("Состояние адм.")
            or set(line.strip()) == {"-"}
        ):
            continue
        m = re.match(r'^\s*\S+\s+(?:Connected|Подключен)\s+\S+\s+(.+?)\s*$', line)
        if not m:
            continue
        name = m.group(1).strip()
        name_cf = name.casefold()
        if name and not any(marker in name_cf for marker in excluded_markers):
            names.append(name)
    return names


def _parse_netsh_dns_details(text: str) -> dict[str, dict]:
    blocks: dict[str, dict] = {}
    current = None
    collecting = False

    for raw_line in (text or "").splitlines():
        line = raw_line.rstrip()
        m = re.match(r'^\s*(?:Configuration for interface|Настройка интерфейса)\s+"(.*)"\s*$', line)
        if m:
            current = m.group(1).strip()
            blocks[current] = {"mode": "", "servers": []}
            collecting = False
            continue

        if current is None:
            continue

        stripped = line.strip()
        if not stripped:
            continue

        if (
            "Register with which suffix" in stripped
            or "Зарегистрировать с суффиксом" in stripped
        ):
            collecting = False
            continue

        if (
            "DNS Servers" in stripped
            or "DNS servers" in stripped
            or "DNS-серверы" in stripped
        ):
            collecting = True
            low = stripped.casefold()
            if "dhcp" in low:
                blocks[current]["mode"] = "dhcp"
            elif ("static" in low) or ("статичес" in low):
                blocks[current]["mode"] = "static"
            _, _, value_part = stripped.partition(":")
            candidate = _normalize_dns_server_string(value_part)
            if candidate:
                blocks[current]["servers"].append(candidate)
            continue

        if collecting and raw_line[:1].isspace():
            candidate = _normalize_dns_server_string(stripped)
            if candidate:
                blocks[current]["servers"].append(candidate)

    for name, info in blocks.items():
        info["servers"] = _merge_unique(info.get("servers", []))
        if not info.get("mode"):
            info["mode"] = "static" if info["servers"] else "dhcp"
    return blocks


def _run_netsh_command(args: list[str]) -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            args,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        ok = completed.returncode == 0
        msg = (completed.stderr or completed.stdout or "").strip()
        return ok, msg
    except Exception as e:
        return False, str(e)


def _get_current_dns_snapshot(interface_names: list[str] | None = None) -> list[dict]:
    names = interface_names if interface_names is not None else _get_connected_interface_names()
    ipv4_ok, ipv4_text = _run_netsh_command(["netsh", "interface", "ipv4", "show", "dnsservers"])
    ipv6_ok, ipv6_text = _run_netsh_command(["netsh", "interface", "ipv6", "show", "dnsservers"])
    ipv4_details = _parse_netsh_dns_details(ipv4_text if ipv4_ok else "")
    ipv6_details = _parse_netsh_dns_details(ipv6_text if ipv6_ok else "")
    snapshot = []
    for name in names:
        snapshot.append({
            "name": name,
            "ipv4": dict(ipv4_details.get(name, {"mode": "dhcp", "servers": []})),
            "ipv6": dict(ipv6_details.get(name, {"mode": "dhcp", "servers": []})),
        })
    return snapshot


def _apply_netsh_dns_family(interface_name: str, family: str, mode: str, servers: list[str]) -> tuple[bool, str]:
    fam = "ipv6" if family == "ipv6" else "ipv4"
    normalized = [_normalize_dns_server_string(s) for s in servers if _normalize_dns_server_string(s)]
    quoted_name = f'name="{interface_name}"' if fam == "ipv4" else interface_name

    if mode == "dhcp":
        args = ["netsh", "interface", fam, "set", "dnsservers"]
        if fam == "ipv4":
            args.extend([quoted_name, "source=dhcp", "validate=no"])
        else:
            args.extend([quoted_name, "source=dhcp", "validate=no"])
        return _run_netsh_command(args)

    if not normalized:
        return _run_netsh_command(
            ["netsh", "interface", fam, "set", "dnsservers", quoted_name, "source=dhcp", "validate=no"]
        )

    if fam == "ipv4":
        ok, msg = _run_netsh_command(
            ["netsh", "interface", "ipv4", "set", "dnsservers", quoted_name, "static", normalized[0], "primary", "validate=no"]
        )
    else:
        ok, msg = _run_netsh_command(
            ["netsh", "interface", "ipv6", "set", "dnsservers", quoted_name, "static", normalized[0], "primary", "validate=no"]
        )
    if not ok:
        return ok, msg

    for index, server in enumerate(normalized[1:], start=2):
        if fam == "ipv4":
            ok, msg = _run_netsh_command(
                ["netsh", "interface", "ipv4", "add", "dnsservers", quoted_name, server, f"index={index}", "validate=no"]
            )
        else:
            ok, msg = _run_netsh_command(
                ["netsh", "interface", "ipv6", "add", "dnsservers", quoted_name, server, f"index={index}", "validate=no"]
            )
        if not ok:
            return ok, msg
    return True, ""


def _is_dns_malw_link_enabled_by_app(settings: QSettings | None = None) -> bool:
    try:
        qs = _load_settings_if_needed(settings)
        return bool(qs.value(DNS_MALW_ENABLED_BY_APP_KEY, False, type=bool))
    except Exception:
        return False


def _set_dns_malw_link_enabled_by_app(enabled: bool, settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    qs.setValue(DNS_MALW_ENABLED_BY_APP_KEY, bool(enabled))
    qs.sync()


def _load_dns_malw_link_snapshot(settings: QSettings | None = None) -> list[dict]:
    try:
        qs = _load_settings_if_needed(settings)
        raw = str(qs.value(DNS_MALW_RESTORE_SNAPSHOT_KEY, "") or "").strip()
        if not raw:
            return []
        payload = json.loads(raw)
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def _save_dns_malw_link_snapshot(snapshot: list[dict], settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    try:
        raw = json.dumps(snapshot or [], ensure_ascii=False)
    except Exception:
        raw = "[]"
    qs.setValue(DNS_MALW_RESTORE_SNAPSHOT_KEY, raw)
    qs.sync()


def _read_hosts_file(path: str = DNS_MALW_HOSTS_PATH) -> str:
    try:
        with open(path, "rb") as f:
            raw = f.read()
    except Exception:
        return ""

    return _decode_hosts_bytes(raw)


def _read_hosts_file_strict(path: str = DNS_MALW_HOSTS_PATH) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    return _decode_hosts_bytes(raw)


def _decode_hosts_bytes(raw: bytes) -> str:
    for enc in ("utf-8-sig", "utf-8", "utf-16", "cp1251", "mbcs"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="ignore")


def _write_hosts_file(content: str, path: str = DNS_MALW_HOSTS_PATH) -> None:
    normalized = (content or "").replace("\r\n", "\n").replace("\r", "\n")
    if normalized and not normalized.endswith("\n"):
        normalized += "\n"
    data = normalized.encode("utf-8")
    is_system_hosts = os.path.normcase(path) == os.path.normcase(DNS_MALW_HOSTS_PATH)
    attempts = 8 if is_system_hosts else 1
    last_error = None

    for attempt in range(attempts):
        try:
            with open(path, "wb") as f:
                f.write(data)
            return
        except (PermissionError, OSError) as e:
            last_error = e
            is_permission_error = isinstance(e, PermissionError) or getattr(e, "errno", None) == 13 or getattr(e, "winerror", None) == 5
            if not is_permission_error:
                raise
            if attempt >= attempts - 1:
                break
            try:
                os.chmod(path, 0o666)
            except Exception:
                pass
            time.sleep(0.28 + attempt * 0.34)

    if is_system_hosts:
        ps_error = _write_system_hosts_file_via_powershell(data, path)
        if not ps_error:
            return
        if last_error is None:
            raise PermissionError(ps_error)

    if last_error is not None:
        raise last_error


def _write_system_hosts_file_via_powershell(data: bytes, path: str = DNS_MALW_HOSTS_PATH) -> str:
    tmp_path = ""
    script_path = ""
    try:
        os.makedirs(APP_DIR, exist_ok=True)
        fd, tmp_path = tempfile.mkstemp(prefix="hosts-write-", suffix=".tmp", dir=APP_DIR)
        with os.fdopen(fd, "wb") as f:
            f.write(data)

        script = r"""
param([string]$src, [string]$dst)
$ErrorActionPreference = 'Stop'
$bytes = [System.IO.File]::ReadAllBytes($src)
$lastError = $null

for ($i = 0; $i -lt 8; $i++) {
    try {
        if (Test-Path -LiteralPath $dst) {
            try { & attrib.exe -R -S -H $dst 2>$null | Out-Null } catch {}
        }
        [System.IO.File]::WriteAllBytes($dst, $bytes)
        exit 0
    } catch {
        $lastError = $_.Exception.Message
        Start-Sleep -Milliseconds (260 + ($i * 280))
    }
}

throw $lastError
"""
        fd_script, script_path = tempfile.mkstemp(prefix="hosts-write-", suffix=".ps1", dir=APP_DIR)
        with os.fdopen(fd_script, "w", encoding="utf-8") as f:
            f.write(script.lstrip())

        completed = _run_hidden(
            [
                "powershell",
                "-NoProfile",
                "-ExecutionPolicy", "Bypass",
                "-File",
                script_path,
                tmp_path,
                path,
            ],
            timeout=12,
        )
        if completed is not None and completed.returncode == 0:
            return ""
        if completed is None:
            return "powershell-hosts-write-failed"
        return (completed.stderr or completed.stdout or f"powershell-exit-{completed.returncode}").strip()
    except Exception as e:
        return str(e)
    finally:
        if tmp_path:
            try:
                os.remove(tmp_path)
            except Exception:
                pass
        if script_path:
            try:
                os.remove(script_path)
            except Exception:
                pass


def _is_hosts_permission_error_message(error: str) -> bool:
    s = (error or "").casefold()
    return (
        "permission denied" in s
        or "access is denied" in s
        or "отказано в доступе" in s
        or "errno 13" in s
        or "winerror 5" in s
        or DNS_MALW_HOSTS_PATH.casefold() in s
    )


def _hosts_contains_ai_marker(text: str) -> bool:
    hay = (text or "").casefold()
    return (
        DNS_MALW_HOSTS_BLOCK_BEGIN.casefold() in hay
        or "dns.malw.link" in hay
        or "goida ai unlocker" in hay
        or "openai.com.cdn.cloudflare.net" in hay
        or "claude.ai.cdn.cloudflare.net" in hay
    )


def _hosts_contains_dns_malw_managed_block(text: str) -> bool:
    hay = (text or "").casefold()
    return (
        DNS_MALW_HOSTS_BLOCK_BEGIN.casefold() in hay
        and DNS_MALW_HOSTS_BLOCK_END.casefold() in hay
    )


def _hosts_bundle_looks_useful(text: str) -> bool:
    hay = (text or "").casefold()
    return any(token in hay for token in ("openai", "chatgpt", "claude", "gemini", "anthropic"))


def _strip_dns_malw_hosts_block(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    pattern = re.compile(
        rf"(?:^|\n)[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_BEGIN)}[^\n]*\n.*?"
        rf"[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_END)}[^\n]*(?:\n|$)",
        re.S,
    )
    cleaned = pattern.sub("\n", normalized)
    cleaned = _strip_dns_malw_legacy_hosts_blocks(cleaned)
    cleaned = _strip_dns_malw_unmanaged_legacy_lines(cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned).strip()
    return cleaned + ("\n" if cleaned else "")


def _strip_dns_malw_legacy_hosts_blocks(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    main_pattern = re.compile(
        rf"(?:^|\n)[ \t]*{re.escape(DNS_MALW_LEGACY_HOSTS_BLOCK_BEGIN)}[^\n]*\n.*?"
        rf"[ \t]*{re.escape(DNS_MALW_LEGACY_HOSTS_BLOCK_END)}[^\n]*(?:\n|$)",
        re.S | re.I,
    )
    cleaned = main_pattern.sub("\n", normalized)

    additional_pattern = re.compile(
        rf"(?:^|\n)[ \t]*{re.escape(DNS_MALW_LEGACY_ADDITIONAL_BLOCK_BEGIN)}[^\n]*(?:\n.*)?$",
        re.S | re.I,
    )
    return additional_pattern.sub("\n", cleaned)


def _extract_dns_malw_hosts_block_body(text: str) -> str:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    pattern = re.compile(
        rf"[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_BEGIN)}[^\n]*\n(?P<body>.*?)"
        rf"\n[ \t]*{re.escape(DNS_MALW_HOSTS_BLOCK_END)}[^\n]*",
        re.S,
    )
    m = pattern.search(normalized)
    return (m.group("body") if m else "").strip()


def _hosts_line_target_hostname(line: str) -> str:
    clean = (line or "").split("#", 1)[0].strip()
    if not clean:
        return ""
    parts = clean.split()
    if len(parts) < 2:
        return ""
    return parts[1].strip().rstrip(".").casefold()


def _dns_malw_host_matches_legacy_ai_host(host: str) -> bool:
    h = (host or "").strip().rstrip(".").casefold()
    if not h:
        return False
    if h in DNS_MALW_PROTECTED_HOSTS:
        return True
    for suffix in DNS_MALW_LEGACY_AI_HOST_SUFFIXES:
        s = suffix.casefold()
        if h == s or h.endswith("." + s):
            return True
    return any(token in h for token in DNS_MALW_LEGACY_AI_HOST_TOKENS)


def _strip_dns_malw_unmanaged_legacy_lines(text: str) -> str:
    lines = (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines()
    kept = []
    changed = False

    for line in lines:
        host = _hosts_line_target_hostname(line)
        if host and _dns_malw_host_matches_legacy_ai_host(host):
            changed = True
            continue
        kept.append(line.rstrip())

    if not changed:
        return text
    return "\n".join(kept).strip() + ("\n" if kept else "")


def _filter_dns_malw_hosts_bundle(text: str) -> str:
    protected = {host.casefold() for host in DNS_MALW_PROTECTED_HOSTS}
    kept = []
    seen_hosts = set()
    for line in (text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        host = _hosts_line_target_hostname(line)
        if host and host in protected:
            continue
        # dns.malw.link is the canonical source.  Optional supplementary lists
        # must not replace a current mapping (in particular Gemini) with an
        # older address later in the same hosts block.
        if host and host in seen_hosts:
            continue
        if host:
            seen_hosts.add(host)
        kept.append(line.rstrip())
    out = "\n".join(kept).strip()
    return out + ("\n" if out else "")


def _compose_dns_malw_hosts(original_hosts: str, managed_hosts: str) -> str:
    base = _strip_dns_malw_hosts_block(original_hosts).rstrip()
    block_body = _filter_dns_malw_hosts_bundle(managed_hosts).strip()
    block = f"{DNS_MALW_HOSTS_BLOCK_BEGIN}\n{block_body}\n{DNS_MALW_HOSTS_BLOCK_END}\n"
    if base:
        return base + "\n\n" + block
    return block


def _repair_dns_malw_hosts_for_app_network(settings: QSettings | None = None) -> bool:
    if not _is_dns_malw_link_enabled_by_app(settings):
        return False
    try:
        current_hosts = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
        if not _hosts_contains_dns_malw_managed_block(current_hosts):
            cleaned_hosts = _strip_dns_malw_hosts_block(current_hosts)
            if cleaned_hosts != current_hosts:
                _write_hosts_file(cleaned_hosts, DNS_MALW_HOSTS_PATH)
                _run_hidden(["ipconfig", "/flushdns"])
                return True
            return False

        block_body = _extract_dns_malw_hosts_block_body(current_hosts)
        filtered_body = _filter_dns_malw_hosts_bundle(block_body)
        base_hosts = _strip_dns_malw_hosts_block(current_hosts)
        recomposed_hosts = _compose_dns_malw_hosts(base_hosts, filtered_body)
        if filtered_body.strip() == block_body.strip() and recomposed_hosts == current_hosts:
            return False

        _write_hosts_file(recomposed_hosts, DNS_MALW_HOSTS_PATH)
        _run_hidden(["ipconfig", "/flushdns"])
        return True
    except Exception:
        return False


def _is_dns_malw_backup_usable(text: str) -> bool:
    return bool((text or "").strip()) and not _hosts_contains_ai_marker(text)


def _load_dns_malw_backup() -> str:
    if not os.path.exists(DNS_MALW_HOSTS_BACKUP_PATH):
        return ""
    return _read_hosts_file(DNS_MALW_HOSTS_BACKUP_PATH)


def _load_dns_malw_seed_hosts() -> str:
    for path in (
        DNS_MALW_HOSTS_CACHE_PATH,
        DNS_MALW_HOSTS_SEED_PATH,
        _bundled_path("core", "lists", "dns_malw_hosts_seed.txt"),
    ):
        if not path or not os.path.exists(path):
            continue
        text = _read_hosts_file(path)
        if text.strip() and _hosts_bundle_looks_useful(text):
            return _filter_dns_malw_hosts_bundle(text)
    return ""


def _save_dns_malw_backup_if_safe(current_hosts: str, settings: QSettings | None = None) -> str:
    qs = _load_settings_if_needed(settings)
    existing = _load_dns_malw_backup()
    if _is_dns_malw_link_enabled_by_app(qs) and _is_dns_malw_backup_usable(existing):
        return existing

    cleaned = _strip_dns_malw_hosts_block(current_hosts)
    if _hosts_contains_ai_marker(cleaned) and _is_dns_malw_backup_usable(existing):
        return existing

    if (not _hosts_contains_ai_marker(cleaned)) or not existing:
        _write_hosts_file(cleaned, DNS_MALW_HOSTS_BACKUP_PATH)
        return cleaned

    return existing


def _download_ai_hosts_bundle() -> tuple[str, str]:
    headers = {"User-Agent": "ZapretGUI-AiDNS"}
    session = None
    errors = []

    def _fetch_text_url(url: str, timeout: tuple[float, float] = (4.0, 16.0)) -> str:
        resp = session.get(url, timeout=timeout, allow_redirects=True)
        resp.raise_for_status()
        return (resp.content or b"").decode("utf-8", errors="replace")

    def _record_error(source: str, error: Exception) -> None:
        msg = str(error).replace("\r", " ").replace("\n", " ").strip()
        if len(msg) > 240:
            msg = msg[:240] + "..."
        errors.append(f"{source}: {msg}")

    def _download_main_hosts() -> str:
        try:
            return _download_github_contents_bytes(
                session,
                "ImMALWARE/dns.malw.link",
                "hosts",
                ref="master",
            ).decode("utf-8", errors="replace")
        except Exception as e:
            _record_error("github-api", e)

        for label, url in (("raw", DNS_MALW_HOSTS_URL),) + tuple(
            (f"mirror-{idx}", url) for idx, url in enumerate(DNS_MALW_HOSTS_MIRROR_URLS, 1)
        ):
            try:
                text = _fetch_text_url(url)
                if text.strip():
                    return text
            except Exception as e:
                _record_error(label, e)

        seed_hosts = _load_dns_malw_seed_hosts()
        if seed_hosts.strip():
            return seed_hosts

        detail = "; ".join(errors[-5:]) if errors else "all sources failed"
        raise RuntimeError(f"ai-hosts-download-failed: {detail}")

    def _download_additional_hosts_text() -> str:
        try:
            return _download_github_contents_bytes(
                session,
                "AvenCores/Goida-AI-Unlocker",
                "additional_hosts.py",
                ref="main",
            ).decode("utf-8", errors="replace")
        except Exception:
            pass

        for url in (DNS_MALW_ADDITIONAL_URL,) + tuple(DNS_MALW_ADDITIONAL_MIRROR_URLS):
            try:
                text = _fetch_text_url(url, timeout=(4.0, 10.0))
                if text.strip():
                    return text
            except Exception:
                pass
        return ""

    try:
        session = requests.Session()
        session.headers.update(headers)
        main_hosts = _download_main_hosts()
        main_hosts = main_hosts.replace("\r\n", "\n").replace("\r", "\n").strip()

        additional_block = ""
        additional_version = ""
        try:
            add_text = _download_additional_hosts_text()
            m_ver = DNS_MALW_ADDITIONAL_VERSION_RE.search(add_text)
            m_hosts = DNS_MALW_ADDITIONAL_HOSTS_RE.search(add_text)
            if m_ver:
                additional_version = m_ver.group(1).strip()
            if m_hosts:
                additional_block = (m_hosts.group("body") or "").strip()
        except Exception:
            additional_block = ""
            additional_version = ""

        pieces = [main_hosts]
        if additional_block:
            header = "# Goida-AI-Unlocker additional hosts"
            if additional_version:
                header += f" ({additional_version})"
            pieces.append(header)
            pieces.append(additional_block)

        final_hosts = "\n\n".join(part for part in pieces if part).strip() + "\n"
        if len([line for line in final_hosts.splitlines() if line.strip() and not line.lstrip().startswith("#")]) < 3:
            raise RuntimeError("downloaded-hosts-too-small")
        if not _hosts_bundle_looks_useful(final_hosts):
            raise RuntimeError("downloaded-hosts-do-not-contain-ai-domains")
        final_hosts = _filter_dns_malw_hosts_bundle(final_hosts)
        _write_hosts_file(final_hosts, DNS_MALW_HOSTS_CACHE_PATH)
        return final_hosts, additional_version
    except Exception as e:
        seed_hosts = _load_dns_malw_seed_hosts()
        if seed_hosts.strip():
            return seed_hosts, "cached"
        raise e
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass


def _sync_ai_dns_if_enabled(
    settings: QSettings | None = None,
    min_retry_seconds: int = 0,
) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {"ok": False, "skipped": False, "error": ""}
    if not _is_dns_malw_link_enabled_by_app(qs):
        result["skipped"] = True
        return result

    if min_retry_seconds > 0:
        try:
            last_success = _safe_int_setting(qs, DNS_MALW_LAST_SUCCESS_KEY, 0)
            if (
                last_success > 0
                and (int(time.time()) - last_success) < max(60, int(min_retry_seconds))
                and _hosts_contains_dns_malw_managed_block(_read_hosts_file(DNS_MALW_HOSTS_PATH))
            ):
                result["ok"] = True
                result["skipped"] = True
                return result
        except Exception:
            pass

    try:
        is_admin_now = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        is_admin_now = False

    if not is_admin_now:
        result["skipped"] = True
        return result

    sync_result = _enable_dns_malw_link(qs)
    result["ok"] = bool(sync_result.get("ok"))
    result["error"] = str(sync_result.get("error", "") or "")
    return result


def _get_dns_malw_link_status() -> dict:
    result = {
        "ok": True,
        "active": False,
        "error": "",
        "admin": False,
        "adapters": 0,
        "matched": 0,
        "method": "hosts",
    }

    try:
        hosts_text = _read_hosts_file(DNS_MALW_HOSTS_PATH)
        result["active"] = _hosts_contains_ai_marker(hosts_text)
    except Exception as e:
        result["ok"] = False
        result["error"] = str(e)

    return result


def _enable_dns_malw_link(settings: QSettings | None = None) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "error": "",
        "admin": False,
        "adapters": 1,
        "applied": 0,
        "updated": 0,
        "doh": False,
        "method": "hosts",
        "snapshot": [],
    }

    try:
        result["admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        result["admin"] = False

    if not result["admin"]:
        result["error"] = "not-admin"
    else:
        try:
            try:
                current_hosts = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
            except FileNotFoundError:
                current_hosts = ""
            backup_hosts = _save_dns_malw_backup_if_safe(current_hosts, qs)
            network_safe_hosts = _strip_dns_malw_hosts_block(current_hosts)
            if network_safe_hosts != current_hosts:
                _write_hosts_file(network_safe_hosts, DNS_MALW_HOSTS_PATH)
                _run_hidden(["ipconfig", "/flushdns"])
                current_hosts = network_safe_hosts
            new_hosts, additional_version = _download_ai_hosts_bundle()
            base_hosts = _strip_dns_malw_hosts_block(current_hosts)
            if _hosts_contains_ai_marker(base_hosts):
                if _is_dns_malw_backup_usable(backup_hosts):
                    base_hosts = backup_hosts
                else:
                    raise RuntimeError("no-clean-snapshot")
            final_hosts = _compose_dns_malw_hosts(base_hosts, new_hosts)
            _write_hosts_file(final_hosts, DNS_MALW_HOSTS_PATH)
            _run_hidden(["ipconfig", "/flushdns"])
            _run_hidden(["ipconfig", "/registerdns"])
            result["ok"] = True
            result["applied"] = 1
            result["updated"] = 1
            result["snapshot"] = [{
                "backup": DNS_MALW_HOSTS_BACKUP_PATH,
                "mode": "hosts-managed-block",
                "additional_version": additional_version,
            }]
        except Exception as e:
            result["error"] = str(e)

    try:
        qs.setValue(DNS_MALW_LAST_ATTEMPT_KEY, int(time.time()))
        qs.setValue(DNS_MALW_LAST_STATUS_KEY, "ok" if result.get("ok") else "error")
        qs.setValue(DNS_MALW_LAST_ERROR_KEY, str(result.get("error", "") or ""))
        qs.setValue(DNS_MALW_LAST_UPDATED_KEY, int(result.get("updated", 0) or 0))
        qs.setValue(DNS_MALW_LAST_DOH_KEY, bool(result.get("doh")))
        if result.get("ok"):
            qs.setValue(DNS_MALW_LAST_SUCCESS_KEY, int(time.time()))
            _save_dns_malw_link_snapshot(result.get("snapshot") or [], qs)
            qs.setValue(DNS_MALW_ENABLED_BY_APP_KEY, True)
        qs.sync()
    except Exception:
        pass
    return result


def _disable_dns_malw_link(settings: QSettings | None = None) -> dict:
    qs = _load_settings_if_needed(settings)
    result = {
        "ok": False,
        "error": "",
        "admin": False,
        "adapters": 1,
        "applied": 0,
        "updated": 0,
        "method": "hosts",
    }
    try:
        result["admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        result["admin"] = False

    if not result["admin"]:
        result["error"] = "not-admin"
    else:
        try:
            try:
                current_hosts = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
            except FileNotFoundError:
                current_hosts = ""
            backup_hosts = _load_dns_malw_backup()
            if _hosts_contains_dns_malw_managed_block(current_hosts):
                restored_hosts = _strip_dns_malw_hosts_block(current_hosts)
                if _hosts_contains_ai_marker(restored_hosts):
                    if _is_dns_malw_backup_usable(backup_hosts):
                        restored_hosts = backup_hosts
                    else:
                        raise RuntimeError("no-clean-snapshot")
            elif _is_dns_malw_backup_usable(backup_hosts):
                restored_hosts = backup_hosts
            else:
                restored_hosts = _strip_dns_malw_hosts_block(current_hosts)
                if _hosts_contains_ai_marker(restored_hosts):
                    raise RuntimeError("no-clean-snapshot")
            _write_hosts_file(restored_hosts, DNS_MALW_HOSTS_PATH)
            _run_hidden(["ipconfig", "/flushdns"])
            _run_hidden(["ipconfig", "/registerdns"])
            result["ok"] = True
            result["applied"] = 1
            result["updated"] = 1
        except Exception as e:
            result["error"] = str(e)

    try:
        qs.setValue(DNS_MALW_LAST_ATTEMPT_KEY, int(time.time()))
        qs.setValue(DNS_MALW_LAST_STATUS_KEY, "ok" if result.get("ok") else "error")
        qs.setValue(DNS_MALW_LAST_ERROR_KEY, str(result.get("error", "") or ""))
        if result.get("ok"):
            qs.setValue(DNS_MALW_ENABLED_BY_APP_KEY, False)
            qs.setValue(DNS_MALW_RESTORE_SNAPSHOT_KEY, "")
            qs.setValue(DNS_MALW_LAST_UPDATED_KEY, int(result.get("updated", 0) or 0))
        qs.sync()
    except Exception:
        pass
    return result


def _run_self_as_admin_for_dns_action(action: str) -> bool:
    try:
        action = (action or "").strip().lower()
        if action not in {"enable", "disable"}:
            return False

        if getattr(sys, "frozen", False):
            executable = sys.executable
            params = subprocess.list2cmdline([f"--app-dir={APP_DIR}", f"--dns-malw-link-action={action}"])
        else:
            executable = sys.executable
            params = subprocess.list2cmdline([os.path.abspath(sys.argv[0]), f"--app-dir={APP_DIR}", f"--dns-malw-link-action={action}"])

        res = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            0,
        )
        return int(res) > 32
    except Exception:
        return False


def _run_self_as_admin_for_telegram_hosts_action(action: str) -> bool:
    try:
        action = (action or "").strip().lower()
        if action not in {"enable", "disable"}:
            return False

        if getattr(sys, "frozen", False):
            executable = sys.executable
            params = subprocess.list2cmdline([f"--app-dir={APP_DIR}", f"--telegram-mode-hosts-action={action}"])
        else:
            executable = sys.executable
            params = subprocess.list2cmdline([os.path.abspath(sys.argv[0]), f"--app-dir={APP_DIR}", f"--telegram-mode-hosts-action={action}"])

        res = ctypes.windll.shell32.ShellExecuteW(
            None,
            "runas",
            executable,
            params,
            None,
            0,
        )
        return int(res) > 32
    except Exception:
        return False


def _build_dns_malw_link_script() -> str:
    script = r"""
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

function Normalize-Servers([object[]]$servers) {
    return @(
        $servers |
        Where-Object { $_ } |
        ForEach-Object { $_.ToString().Trim().ToLowerInvariant() } |
        Sort-Object -Unique
    )
}

function Test-SameServers([object[]]$left, [object[]]$right) {
    $a = Normalize-Servers $left
    $b = Normalize-Servers $right
    if ($a.Count -ne $b.Count) {
        return $false
    }
    for ($i = 0; $i -lt $a.Count; $i++) {
        if ($a[$i] -ne $b[$i]) {
            return $false
        }
    }
    return $true
}

$result = [ordered]@{
    ok = $false
    skipped = $false
    reason = ''
    error = ''
    admin = $false
    adapters = 0
    applied = 0
    updated = 0
    doh = $false
    method = ''
}

try {
    try {
        $principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
        $result.admin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    } catch {
        $result.admin = $false
    }

    if (-not $result.admin) {
        $result.skipped = $true
        $result.reason = 'not-admin'
        $result | ConvertTo-Json -Compress
        exit 0
    }

    $ipv4Servers = @(__IPV4__)
    $ipv6Servers = @(__IPV6__)
    $desiredServers = @($ipv4Servers + $ipv6Servers)
    $dohTemplate = '__DOH__'

    $addDohCommand = Get-Command Add-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $setDohCommand = Get-Command Set-DnsClientDohServerAddress -ErrorAction SilentlyContinue
    $getDohCommand = Get-Command Get-DnsClientDohServerAddress -ErrorAction SilentlyContinue

    if ($addDohCommand -or $setDohCommand) {
        foreach ($server in $desiredServers) {
            try {
                $hasExisting = $false
                if ($getDohCommand) {
                    $existing = @(Get-DnsClientDohServerAddress -ServerAddress $server -ErrorAction SilentlyContinue)
                    $hasExisting = ($existing.Count -gt 0)
                }

                if ($hasExisting -and $setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }

                if ($addDohCommand) {
                    Add-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                    continue
                }

                if ($setDohCommand) {
                    Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                    $result.doh = $true
                }
            } catch {
                try {
                    if ($setDohCommand) {
                        Set-DnsClientDohServerAddress -ServerAddress $server -DohTemplate $dohTemplate -AutoUpgrade $true -AllowFallbackToUdp $true -ErrorAction Stop | Out-Null
                        $result.doh = $true
                    }
                } catch {
                }
            }
        }
    }

    $getDnsClient = Get-Command Get-DnsClient -ErrorAction SilentlyContinue
    $getDnsClientServerAddress = Get-Command Get-DnsClientServerAddress -ErrorAction SilentlyContinue
    $setDnsClientServerAddress = Get-Command Set-DnsClientServerAddress -ErrorAction SilentlyContinue

    if ($getDnsClient -and $getDnsClientServerAddress -and $setDnsClientServerAddress) {
        $result.method = 'dnsclient'
        $adapters = @(
            Get-DnsClient |
            Where-Object {
                $_.InterfaceAlias -and
                $_.InterfaceOperationalStatus -eq 'Up' -and
                $_.InterfaceAlias -notmatch 'Loopback|isatap|Teredo'
            } |
            Sort-Object InterfaceIndex -Unique
        )
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            try {
                $currentServers = @(
                    Get-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ErrorAction SilentlyContinue |
                    ForEach-Object { @($_.ServerAddresses) } |
                    Where-Object { $_ }
                )
                if (Test-SameServers $currentServers $desiredServers) {
                    $result.applied += 1
                    continue
                }

                Set-DnsClientServerAddress -InterfaceIndex $adapter.InterfaceIndex -ServerAddresses $desiredServers -ErrorAction Stop | Out-Null
                $result.updated += 1
                $result.applied += 1
            } catch {
            }
        }
    } elseif (Get-Command Get-CimInstance -ErrorAction SilentlyContinue) {
        $result.method = 'cim'
        $adapters = @(Get-CimInstance Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            try {
                $currentServers = @($adapter.DNSServerSearchOrder)
                if (Test-SameServers $currentServers $desiredServers) {
                    $result.applied += 1
                    continue
                }

                $invokeResult = Invoke-CimMethod -InputObject $adapter -MethodName SetDNSServerSearchOrder -Arguments @{DNSServerSearchOrder = $desiredServers} -ErrorAction Stop
                if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                    $result.updated += 1
                    $result.applied += 1
                }
            } catch {
            }
        }
    } elseif (Get-Command Get-WmiObject -ErrorAction SilentlyContinue) {
        $result.method = 'wmi'
        $adapters = @(Get-WmiObject Win32_NetworkAdapterConfiguration -Filter "IPEnabled=TRUE" -ErrorAction Stop)
        $result.adapters = $adapters.Count

        foreach ($adapter in $adapters) {
            try {
                $currentServers = @($adapter.DNSServerSearchOrder)
                if (Test-SameServers $currentServers $desiredServers) {
                    $result.applied += 1
                    continue
                }

                $invokeResult = $adapter.SetDNSServerSearchOrder($desiredServers)
                if (($invokeResult.ReturnValue -eq 0) -or ($invokeResult.ReturnValue -eq 1)) {
                    $result.updated += 1
                    $result.applied += 1
                }
            } catch {
            }
        }
    } else {
        throw 'No DNS configuration backend available'
    }

    if ($result.adapters -le 0) {
        $result.skipped = $true
        $result.reason = 'no-active-adapters'
        $result | ConvertTo-Json -Compress
        exit 0
    }

    if ($result.applied -le 0) {
        throw 'dns-apply-failed'
    }

    try {
        if (Get-Command Clear-DnsClientCache -ErrorAction SilentlyContinue) {
            Clear-DnsClientCache | Out-Null
        } else {
            & ipconfig /flushdns | Out-Null
        }
    } catch {
    }

    $result.ok = $true
} catch {
    $result.error = [string]$_.Exception.Message
}

$result | ConvertTo-Json -Compress
"""
    return (
        script
        .replace("__IPV4__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV4_SERVERS))
        .replace("__IPV6__", ", ".join(f"'{server}'" for server in DNS_MALW_IPV6_SERVERS))
        .replace("__DOH__", DNS_MALW_DOH_TEMPLATE)
    )


def _ensure_dns_malw_link(
    settings: QSettings | None = None,
    min_retry_seconds: int = 0,
) -> dict:
    result = {
        "ok": False,
        "skipped": False,
        "reason": "",
        "error": "",
        "admin": False,
        "adapters": 0,
        "applied": 0,
        "updated": 0,
        "doh": False,
        "method": "",
    }

    qs = _load_settings_if_needed(settings)
    now = int(time.time())
    last_attempt_to_store = now

    if not sys.platform.startswith("win"):
        result["skipped"] = True
        result["reason"] = "non-windows"
    else:
        should_run = True
        if min_retry_seconds > 0:
            last_attempt = _safe_int_setting(qs, DNS_MALW_LAST_ATTEMPT_KEY, 0)
            last_status = str(qs.value(DNS_MALW_LAST_STATUS_KEY, "") or "").strip().lower()
            if last_attempt > 0 and (now - last_attempt) < min_retry_seconds:
                result["skipped"] = True
                result["reason"] = "recent-attempt"
                last_attempt_to_store = last_attempt
                should_run = False
                if last_status == "ok":
                    result["ok"] = True
                    result["doh"] = bool(qs.value(DNS_MALW_LAST_DOH_KEY, False, type=bool))
                    result["updated"] = _safe_int_setting(qs, DNS_MALW_LAST_UPDATED_KEY, 0)
                try:
                    result["admin"] = bool(ctypes.windll.shell32.IsUserAnAdmin())
                except Exception:
                    result["admin"] = False
        if should_run:
            encoded_script = base64.b64encode(
                _build_dns_malw_link_script().encode("utf-16le")
            ).decode("ascii")
            completed = _run_hidden(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy", "Bypass",
                    "-EncodedCommand",
                    encoded_script,
                ],
                timeout=35,
            )

            if completed is None:
                result["error"] = "powershell-launch-failed"
            else:
                stdout = (completed.stdout or "").strip()
                stderr = (completed.stderr or "").strip()
                payload = None
                if stdout:
                    lines = [line.strip() for line in stdout.splitlines() if line.strip()]
                    for line in reversed(lines):
                        try:
                            parsed = json.loads(line)
                        except Exception:
                            continue
                        if isinstance(parsed, dict):
                            payload = parsed
                            break

                if isinstance(payload, dict):
                    for key in result:
                        if key in payload:
                            result[key] = payload[key]
                elif stderr:
                    result["error"] = stderr.splitlines()[-1].strip()

                if completed.returncode not in (0, None) and not result["error"]:
                    result["error"] = f"powershell-exit-{completed.returncode}"

    try:
        qs.setValue(DNS_MALW_LAST_ATTEMPT_KEY, last_attempt_to_store)
        qs.setValue(
            DNS_MALW_LAST_STATUS_KEY,
            "ok" if result["ok"] else ("skipped" if result["skipped"] else "error"),
        )
        qs.setValue(
            DNS_MALW_LAST_ERROR_KEY,
            str(result.get("error") or result.get("reason") or "").strip(),
        )
        qs.setValue(DNS_MALW_LAST_UPDATED_KEY, int(result.get("updated", 0) or 0))
        qs.setValue(DNS_MALW_LAST_DOH_KEY, bool(result.get("doh")))
        if result["ok"]:
            qs.setValue(DNS_MALW_LAST_SUCCESS_KEY, now)
        qs.sync()
    except Exception:
        pass

    return result


