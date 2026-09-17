# --- Game mode and domain/IP list synchronization --------------------------

def _is_game_mode_enabled(settings: QSettings | None = None) -> bool:
    try:
        qs = _load_settings_if_needed(settings)
        return bool(qs.value(GAME_MODE_KEY, False, type=bool))
    except Exception:
        return False


def _set_game_mode_enabled(enabled: bool, settings: QSettings | None = None) -> None:
    qs = _load_settings_if_needed(settings)
    qs.setValue(GAME_MODE_KEY, bool(enabled))
    qs.sync()


def _get_game_mode_options(settings: QSettings | None = None) -> dict:
    try:
        qs = _load_settings_if_needed(settings)
        return {
            "main_bypass_enabled": bool(qs.value(GAME_MODE_MAIN_BYPASS_KEY, True, type=bool)),
            "user_lists_enabled": bool(qs.value(GAME_MODE_USER_LISTS_KEY, True, type=bool)),
            "discord_enabled": bool(qs.value(GAME_MODE_DISCORD_KEY, False, type=bool)),
        }
    except Exception:
        return {
            "main_bypass_enabled": True,
            "user_lists_enabled": True,
            "discord_enabled": False,
        }


def _set_game_mode_options(
    main_bypass_enabled: bool | None = None,
    user_lists_enabled: bool | None = None,
    discord_enabled: bool | None = None,
    settings: QSettings | None = None,
) -> None:
    qs = _load_settings_if_needed(settings)
    if main_bypass_enabled is not None:
        qs.setValue(GAME_MODE_MAIN_BYPASS_KEY, bool(main_bypass_enabled))
    if user_lists_enabled is not None:
        qs.setValue(GAME_MODE_USER_LISTS_KEY, bool(user_lists_enabled))
    if discord_enabled is not None:
        qs.setValue(GAME_MODE_DISCORD_KEY, bool(discord_enabled))
    qs.sync()


def _get_effective_game_mode_options(settings: QSettings | None = None) -> dict:
    if not _is_game_mode_enabled(settings):
        return {
            "main_bypass_enabled": True,
            "user_lists_enabled": True,
            "discord_enabled": False,
        }
    return _get_game_mode_options(settings)


def _get_game_filter_ports(settings: QSettings | None = None) -> tuple[str, str]:
    if not _is_game_mode_enabled(settings):
        return ("12", "12")

    mode = (GAME_FILTER_FLAG_MODE or "all").strip().casefold()
    if mode == "tcp":
        return ("1024-65535", "12")
    if mode == "udp":
        return ("12", "1024-65535")
    return ("1024-65535", "1024-65535")


def _apply_game_mode_state_to_core(settings: QSettings | None = None) -> None:
    enabled = _is_game_mode_enabled(settings)
    try:
        if enabled:
            os.makedirs(os.path.dirname(GAME_FILTER_FLAG_FILE), exist_ok=True)
            _atomic_write_bytes(GAME_FILTER_FLAG_FILE, (GAME_FILTER_FLAG_MODE + "\n").encode("ascii"))
        else:
            if os.path.exists(GAME_FILTER_FLAG_FILE):
                os.remove(GAME_FILTER_FLAG_FILE)
    except Exception:
        pass


def _create_lists_sync_session(user_agent: str) -> requests.Session:
    session = requests.Session()
    session.headers.update({
        "User-Agent": user_agent,
        "Accept": "*/*",
        "Cache-Control": "no-cache",
    })
    return session


def _download_sync_bytes(session: requests.Session, url: str) -> bytes:
    r = session.get(
        url,
        timeout=(2.5, 6.0),
        allow_redirects=True,
    )
    r.raise_for_status()
    return r.content


def _download_github_contents_bytes(
    session: requests.Session,
    repo: str,
    path: str,
    ref: str = "main",
    api_url: str = "",
) -> bytes:
    if api_url:
        url = api_url
    else:
        quoted_path = "/".join(quote(part) for part in (path or "").strip("/").split("/"))
        url = f"https://api.github.com/repos/{repo}/contents/{quoted_path}?ref={quote(ref or 'main')}"

    r = session.get(
        url,
        timeout=(3.0, 8.0),
        allow_redirects=True,
        headers={"Accept": "application/vnd.github+json"},
    )
    r.raise_for_status()
    payload = r.json()
    if isinstance(payload, dict):
        content = str(payload.get("content") or "")
        encoding = str(payload.get("encoding") or "").casefold()
        if content and encoding == "base64":
            return base64.b64decode(content.encode("ascii"), validate=False)
    raise RuntimeError("Unexpected GitHub contents API response")


def _download_flowseal_list_bytes(session: requests.Session, filename: str) -> bytes:
    api_error = None
    try:
        return _download_github_contents_bytes(
            session,
            FLOWSEAL_REPO,
            f"lists/{filename}",
            ref="main",
        )
    except Exception as e:
        api_error = e

    try:
        return _download_sync_bytes(session, FLOWSEAL_LIST_BASE_URL + filename)
    except Exception as e:
        if api_error is not None:
            raise RuntimeError(f"{api_error}; raw fallback failed: {e}") from e
        raise


def _sync_gaming_lists(settings: QSettings | None = None, session: requests.Session | None = None) -> dict:
    result = {
        "ok": False,
        "updated": 0,
        "error": "",
        "offline": False,
        "silent_missing": False,
    }

    qs = _load_settings_if_needed(settings)
    own_session = session is None
    missing_before = sum(0 if os.path.exists(meta["path"]) else 1 for meta in GAMING_LIST_TARGETS.values())

    try:
        os.makedirs(USER_DIR, exist_ok=True)

        if session is None:
            session = _create_lists_sync_session("ZapretGUI-GamingLists")

        response = session.get(
            GAMING_LISTS_API_URL,
            timeout=(2.5, 6.0),
            allow_redirects=True,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, list):
            raise RuntimeError("Unexpected gaming lists API response")

        remote_items = {
            str(item.get("name")): item
            for item in payload
            if isinstance(item, dict) and item.get("type") == "file"
        }

        for name, meta in GAMING_LIST_TARGETS.items():
            remote = remote_items.get(name)
            if not remote:
                continue

            dst = meta["path"]
            remote_sha = str(remote.get("sha") or "").strip()
            remote_api_url = str(remote.get("url") or "").strip()
            download_url = str(remote.get("download_url") or "").strip()
            stored_remote_sha = str(qs.value(meta["remote_sha_key"], "") or "").strip()
            stored_local_hash = str(qs.value(meta["local_hash_key"], "") or "").strip()
            local_data = _read_file_bytes(dst)
            local_hash = _sha256_bytes(local_data)

            needs_download = (
                not os.path.exists(dst)
                or not local_hash
                or local_hash != stored_local_hash
                or (remote_sha and remote_sha != stored_remote_sha)
            )

            if needs_download and (remote_api_url or download_url):
                try:
                    remote_data = _download_github_contents_bytes(
                        session,
                        GAMING_LISTS_REPO,
                        name,
                        api_url=remote_api_url,
                    )
                except Exception:
                    if not download_url:
                        raise
                    remote_data = _download_sync_bytes(session, download_url)
                remote_hash = _sha256_bytes(remote_data)
                if remote_hash != local_hash:
                    _atomic_write_bytes(dst, remote_data)
                    result["updated"] += 1
                local_hash = remote_hash

            if remote_sha:
                qs.setValue(meta["remote_sha_key"], remote_sha)
            if local_hash:
                qs.setValue(meta["local_hash_key"], local_hash)

        qs.sync()
        result["ok"] = True
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["error"] = str(e)
        if missing_before > 0:
            result["silent_missing"] = True
    except Exception as e:
        result["error"] = str(e)
        if missing_before > 0:
            result["silent_missing"] = True
    finally:
        if own_session and session is not None:
            try:
                session.close()
            except Exception:
                pass

    return result


def _is_valid_domain_like(s: str) -> bool:
    s = _normalize_domain_candidate(s)
    if not s:
        return False
    if _is_ip_address_like(s):
        return False
    if "." not in s or s.endswith("."):
        return False
    if " " in s or "\t" in s:
        return False
    if not re.fullmatch(r"[a-z0-9._-]+", s):
        return False
    parts = s.split(".")
    if any(not part for part in parts):
        return False
    return not any(part.startswith("-") or part.endswith("-") for part in parts)


def _is_ip_address_like(s: str) -> bool:
    try:
        ipaddress.ip_address((s or "").strip())
        return True
    except ValueError:
        return False


def _is_single_ip_address_like(s: str) -> bool:
    try:
        ipaddress.ip_address(_normalize_ip_candidate(s))
        return True
    except ValueError:
        return False


def _normalize_domain_candidate(raw: str) -> str:
    s = (raw or "").strip().lower()
    if not s:
        return ""

    s = s.split("#", 1)[0].strip().strip("\"'[](){}<>")
    if not s:
        return ""

    if "://" in s:
        s = s.split("://", 1)[1]

    s = s.split("/", 1)[0].split("\\", 1)[0].strip()
    if ":" in s:
        host, port = s.rsplit(":", 1)
        if port.isdigit():
            s = host

    return s.lstrip(".").strip().strip("\"'[](){}<>")


def _normalize_ip_candidate(raw: str) -> str:
    s = (raw or "").strip()
    if not s:
        return ""

    s = s.split("#", 1)[0].strip().strip("\"'(){}<>")
    if not s:
        return ""

    if "://" in s:
        try:
            s = (urlsplit(s).hostname or "").strip()
        except Exception:
            s = s.split("://", 1)[1]

    s = s.split("\\", 1)[0].strip()
    if s.startswith("[") and "]" in s:
        s = s[1:s.index("]")]
    elif "/" in s:
        host, suffix = s.split("/", 1)
        if not suffix.isdigit():
            s = host

    if s.count(":") == 1 and "." in s:
        host, port = s.rsplit(":", 1)
        if port.isdigit():
            s = host

    return s.strip().strip("\"'[](){}<>")


def _is_valid_ip_or_network_like(s: str) -> bool:
    try:
        ipaddress.ip_network(_normalize_ip_candidate(s), strict=False)
        return True
    except ValueError:
        return False


def _entity_kind_for_target_file(target_file: str) -> str:
    if target_file in (USER_IP_ALL_FILE, USER_IP_EXCLUDE_FILE):
        return "ip"
    return "domain"


def _normalize_value_for_target_file(target_file: str, raw: str) -> str:
    if _entity_kind_for_target_file(target_file) == "ip":
        return _normalize_ip_candidate(raw)
    return _normalize_domain_candidate(raw)


def _is_valid_value_for_target_file(target_file: str, value: str) -> bool:
    if _entity_kind_for_target_file(target_file) == "ip":
        return _is_valid_ip_or_network_like(value)
    return _is_valid_domain_like(value)


def _extract_string_values(value) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        out = []
        for item in value:
            out.extend(_extract_string_values(item))
        return out
    if isinstance(value, dict):
        out = []
        for item in value.values():
            out.extend(_extract_string_values(item))
        return out
    return []


def _extract_domain_candidates_from_text(raw_text: str) -> list[str]:
    out = []
    for line in (raw_text or "").splitlines():
        cleaned = line.split("#", 1)[0].strip()
        if not cleaned:
            continue
        out.extend(part for part in re.split(r"[;,]", cleaned) if part.strip())
    return out


def _extract_domain_candidates_from_file(source_path: str, raw_text: str) -> list[str]:
    ext = os.path.splitext(source_path)[1].lower()

    if ext == ".json":
        try:
            return _extract_string_values(json.loads(raw_text))
        except Exception:
            return _extract_domain_candidates_from_text(raw_text)

    if ext == ".csv":
        out = []
        try:
            for row in csv.reader(io.StringIO(raw_text)):
                for cell in row:
                    out.extend(part for part in re.split(r"[;,]", cell) if part.strip())
            return out
        except Exception:
            return _extract_domain_candidates_from_text(raw_text)

    return _extract_domain_candidates_from_text(raw_text)


def _merge_unique(*lists: list[str]) -> list[str]:
    out = []
    seen = set()
    for arr in lists:
        for x in arr:
            s = (x or "").strip()
            if not s:
                continue
            k = s.casefold()
            if k in seen:
                continue
            seen.add(k)
            out.append(s)
    return out


def _rebuild_runtime_lists(settings: QSettings | None = None) -> None:
    try:
        _ensure_flowseal_source_lists()
        _ensure_user_lists_initialized()
        game_mode_enabled = _is_game_mode_enabled(settings)
        effective_options = _get_effective_game_mode_options(settings)
        main_bypass_enabled = bool(effective_options["main_bypass_enabled"])
        user_lists_enabled = bool(effective_options["user_lists_enabled"])
        discord_enabled = bool(effective_options["discord_enabled"])

        core_general = _read_flowseal_base_lines("list-general.txt") if main_bypass_enabled else []
        core_exclude = _read_flowseal_base_lines("list-exclude.txt") if main_bypass_enabled else []
        core_google = _read_flowseal_base_lines("list-google.txt") if main_bypass_enabled else []
        core_ip_all = _read_flowseal_base_lines("ipset-all.txt") if main_bypass_enabled else []
        core_ip_exclude = _read_flowseal_base_lines("ipset-exclude.txt") if main_bypass_enabled else []

        user_general = _read_lines_utf8(USER_GENERAL_FILE) if user_lists_enabled else []
        user_exclude = _read_lines_utf8(USER_EXCLUDE_FILE) if user_lists_enabled else []
        user_ip_all = _read_lines_utf8(USER_IP_ALL_FILE) if user_lists_enabled else []
        user_ip_exclude = _read_lines_utf8(USER_IP_EXCLUDE_FILE) if user_lists_enabled else []
        user_game_domains = _read_lines_utf8(USER_GAME_DOMAIN_FILE) if game_mode_enabled else []
        user_game_ip = _read_lines_utf8(USER_GAME_IP_FILE) if game_mode_enabled else []
        discord_domains = _read_lines_utf8(RUNTIME_DISCORD_FILE) if (game_mode_enabled and discord_enabled) else []
        telegram_enabled = _is_telegram_mode_enabled(settings)
        if telegram_enabled:
            if not os.path.exists(USER_TELEGRAM_DOMAIN_FILE) or not os.path.exists(USER_TELEGRAM_IP_FILE):
                _write_telegram_managed_lists()
            telegram_domains = _read_lines_utf8(USER_TELEGRAM_DOMAIN_FILE)
            telegram_ip = _read_lines_utf8(USER_TELEGRAM_IP_FILE)
        else:
            telegram_domains = []
            telegram_ip = []

        merged_general = _merge_unique(core_general, telegram_domains, user_general, user_game_domains, discord_domains)
        merged_exclude = _merge_unique(core_exclude, user_exclude)
        merged_google = _merge_unique(core_google)
        merged_ip_all = _merge_unique(core_ip_all, telegram_ip, user_ip_all, user_game_ip)
        merged_ip_exclude = _merge_unique(core_ip_exclude, user_ip_exclude)

        _write_lines_utf8(RUNTIME_GENERAL_FILE, merged_general)
        _write_lines_utf8(RUNTIME_EXCLUDE_FILE, merged_exclude)
        _write_lines_utf8(RUNTIME_GOOGLE_FILE, merged_google)
        _write_lines_utf8(RUNTIME_IP_ALL_FILE, merged_ip_all)
        _write_lines_utf8(RUNTIME_IP_EXCLUDE_FILE, merged_ip_exclude)
        for runtime_user_path in _runtime_user_list_paths():
            _write_lines_utf8(runtime_user_path, [])
        _apply_game_mode_state_to_core(settings)
        _sync_telegram_runtime_lists(settings)
    except Exception:
        pass


def _sync_flowseal_lists(
    settings: QSettings | None = None,
    skip_recent: bool = False,
    min_interval_seconds: int = LISTS_SYNC_MIN_INTERVAL_SECONDS,
) -> dict:
    result = {
        "ok": False,
        "offline": False,
        "flowseal_updated": 0,
        "flowseal_error": "",
        "flowseal_offline": False,
        "gaming_updated": 0,
        "gaming_error": "",
        "gaming_offline": False,
        "gaming_silent_missing": False,
        "skipped_recent": False,
        "error": "",
    }
    session = None
    qs = _load_settings_if_needed(settings)
    try:
        os.makedirs(USER_DIR, exist_ok=True)
        _ensure_flowseal_source_lists()
        _repair_dns_malw_hosts_for_app_network(settings)

        now = int(time.time())
        if skip_recent and _flowseal_source_lists_are_ready():
            last_success = _safe_int_setting(qs, LISTS_SYNC_LAST_SUCCESS_KEY, 0)
            if last_success > 0 and (now - last_success) < max(60, int(min_interval_seconds or 0)):
                _ensure_user_lists_initialized()
                _rebuild_runtime_lists(settings)
                result["ok"] = True
                result["skipped_recent"] = True
                return result

        qs.setValue(LISTS_SYNC_LAST_ATTEMPT_KEY, now)
        qs.sync()

        session = _create_lists_sync_session("ZapretGUI-ListsSync")

        flowseal_updates = []
        flowseal_errors = []
        for fn in FLOWSEAL_LIST_FILES:
            dst = _flowseal_source_path(fn)
            local_data = _read_file_bytes(dst)
            try:
                remote_data = _download_flowseal_list_bytes(session, fn)
            except Exception as e:
                if local_data:
                    flowseal_errors.append(f"{fn}: {e}")
                    continue
                raise

            if _sha256_bytes(local_data) != _sha256_bytes(remote_data):
                flowseal_updates.append((dst, remote_data))

        for dst, data in flowseal_updates:
            _atomic_write_bytes(dst, data)

        gaming_result = _sync_gaming_lists(settings, session=session)
        _ensure_user_lists_initialized()
        _rebuild_runtime_lists(settings)

        result["ok"] = True
        result["flowseal_updated"] = len(flowseal_updates)
        result["flowseal_error"] = "; ".join(flowseal_errors)
        result["flowseal_offline"] = bool(flowseal_errors)
        result["gaming_updated"] = gaming_result.get("updated", 0)
        result["gaming_error"] = gaming_result.get("error", "")
        result["gaming_offline"] = bool(gaming_result.get("offline"))
        result["gaming_silent_missing"] = bool(gaming_result.get("silent_missing"))
        qs.setValue(LISTS_SYNC_LAST_SUCCESS_KEY, int(time.time()))
        qs.sync()
    except requests.exceptions.RequestException as e:
        result["offline"] = True
        result["error"] = str(e)
    except Exception as e:
        result["error"] = str(e)
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                pass
    return result


def _format_lists_status_text(result: dict, lang: str = "ru") -> str:
    flowseal_updated = int(result.get("flowseal_updated", 0) or 0)
    flowseal_error = str(result.get("flowseal_error", "") or "").strip()
    gaming_updated = int(result.get("gaming_updated", 0) or 0)
    gaming_error = str(result.get("gaming_error", "") or "").strip()
    gaming_silent_missing = bool(result.get("gaming_silent_missing"))

    if lang == "ru":
        parts = []
        if flowseal_updated > 0:
            parts.append(f"Основные списки обновлены: {flowseal_updated}")
        elif flowseal_error:
            parts.append("Основные списки не удалось обновить, используются локальные файлы.")
        else:
            parts.append("Основные списки актуальны.")

        if gaming_updated > 0:
            parts.append(f"Игровые списки обновлены: {gaming_updated}")
        elif gaming_error and not gaming_silent_missing:
            parts.append("Игровые списки не удалось обновить, используются локальные файлы.")

        return "\n".join(parts)

    parts = []
    if flowseal_updated > 0:
        parts.append(f"Main lists updated: {flowseal_updated}")
    elif flowseal_error:
        parts.append("Main lists could not be updated; local files are kept.")
    else:
        parts.append("Main lists are up to date.")

    if gaming_updated > 0:
        parts.append(f"Gaming lists updated: {gaming_updated}")
    elif gaming_error and not gaming_silent_missing:
        parts.append("Gaming lists could not be updated; local files are kept.")

    return "\n".join(parts)


def _read_text_full(path: str) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except Exception:
        return ""

    for enc in ("utf-8", "cp1251", "utf-16"):
        try:
            return data.decode(enc)
        except Exception:
            pass
    return data.decode("utf-8", errors="replace")


_WINWS_LAUNCH_MARKER_RE = re.compile(
    r'(?i)(?:"?%BIN%[\\/]*winws\.exe"?|"?winws\.exe"?)'
)


def _split_after_winws_launch_marker(line: str) -> tuple[bool, str]:
    m = _WINWS_LAUNCH_MARKER_RE.search(line or "")
    if not m:
        return False, ""
    return True, (line or "")[m.end():].strip()


def _extract_profile_launch_parts(script_path: str) -> tuple[str, list[str]]:
    raw_text = _read_text_full(script_path)
    if not raw_text:
        raise RuntimeError("Profile script is empty")

    lines = raw_text.splitlines()
    start_index = None
    for idx, line in enumerate(lines):
        found, _ = _split_after_winws_launch_marker(line)
        if found:
            start_index = idx
            break

    if start_index is None:
        raise RuntimeError("winws launch command not found")

    collected = []
    for idx in range(start_index, len(lines)):
        line = lines[idx].strip()
        if not line:
            continue
        collected.append(line)
        if not line.rstrip().endswith("^"):
            break

    if not collected:
        raise RuntimeError("winws launch command is empty")

    found, preamble = _split_after_winws_launch_marker(collected[0])
    if not found:
        raise RuntimeError("winws marker not found")

    if preamble.endswith("^"):
        preamble = preamble[:-1].rstrip()

    segments = []
    for raw_line in collected[1:]:
        segment = raw_line.rstrip()
        if segment.endswith("^"):
            segment = segment[:-1].rstrip()
        if segment:
            segments.append(segment)

    return preamble, segments


def _expand_profile_placeholders(
    text: str,
    core_dir: str,
    game_filter_tcp: str,
    game_filter_udp: str,
) -> str:
    bin_dir = os.path.join(core_dir, "bin") + os.sep
    lists_dir = os.path.join(core_dir, "lists") + os.sep
    game_filter_any = "1024-65535" if (game_filter_tcp != "12" or game_filter_udp != "12") else "12"
    return (
        text.replace("%BIN%", bin_dir)
        .replace("%LISTS%", lists_dir)
        .replace("%GameFilterTCP%", game_filter_tcp)
        .replace("%GameFilterUDP%", game_filter_udp)
        .replace("%GameFilter%", game_filter_any)
        .replace("^!", "!")
        .strip()
    )


def _build_telegram_mode_winws_segments(core_dir: str, settings: QSettings | None = None) -> list[str]:
    if not _is_telegram_mode_enabled(settings):
        return []

    bin_dir = os.path.join(core_dir, "bin")
    lists_dir = os.path.join(core_dir, "lists")
    telegram_domains = os.path.join(lists_dir, "telegram-domains.txt")
    telegram_ipset = os.path.join(lists_dir, "telegram-ipset.txt")
    exclude_domains = os.path.join(lists_dir, "list-exclude.txt")
    exclude_domains_user = os.path.join(lists_dir, "list-exclude-user.txt")
    exclude_ipset = os.path.join(lists_dir, "ipset-exclude.txt")
    exclude_ipset_user = os.path.join(lists_dir, "ipset-exclude-user.txt")
    fake_tls = os.path.join(bin_dir, "tls_clienthello_www_google_com.bin")
    fake_quic = os.path.join(bin_dir, "quic_initial_www_google_com.bin")

    return [
        (
            f'--filter-tcp=80,443 --hostlist="{telegram_domains}" '
            f'--hostlist-exclude="{exclude_domains}" --hostlist-exclude="{exclude_domains_user}" '
            '--dpi-desync=syndata,multidisorder --dpi-desync-split-pos=1,midsld '
            '--dpi-desync-repeats=8 --dpi-desync-fooling=ts,badseq '
            f'--dpi-desync-fake-tls="{fake_tls}" --new'
        ),
        (
            f'--filter-tcp=80,443 --ipset="{telegram_ipset}" '
            f'--ipset-exclude="{exclude_ipset}" --ipset-exclude="{exclude_ipset_user}" '
            '--dpi-desync=syndata,multidisorder --dpi-desync-split-pos=1,midsld '
            '--dpi-desync-repeats=8 --dpi-desync-fooling=ts,badseq '
            f'--dpi-desync-fake-tls="{fake_tls}" --new'
        ),
        (
            f'--filter-udp=443 --hostlist="{telegram_domains}" '
            f'--hostlist-exclude="{exclude_domains}" --hostlist-exclude="{exclude_domains_user}" '
            '--dpi-desync=fake --dpi-desync-repeats=10 '
            f'--dpi-desync-fake-quic="{fake_quic}" --new'
        ),
        (
            f'--filter-udp=443 --ipset="{telegram_ipset}" '
            f'--ipset-exclude="{exclude_ipset}" --ipset-exclude="{exclude_ipset_user}" '
            '--dpi-desync=fake --dpi-desync-repeats=10 '
            f'--dpi-desync-fake-quic="{fake_quic}" --new'
        ),
    ]


def _build_game_mode_winws_command(
    script_path: str,
    core_dir: str,
    settings: QSettings | None = None,
) -> str:
    preamble, segments = _extract_profile_launch_parts(script_path)
    game_filter_tcp, game_filter_udp = _get_game_filter_ports(settings)
    effective_options = _get_effective_game_mode_options(settings)
    main_bypass_enabled = bool(effective_options["main_bypass_enabled"])
    discord_enabled = bool(effective_options["discord_enabled"])
    include_discord_segments = main_bypass_enabled or discord_enabled

    winws_path = os.path.join(core_dir, "bin", "winws.exe")
    expanded_segments = []
    for segment in segments:
        lower = segment.casefold()
        if "list-google.txt" in lower and not main_bypass_enabled:
            continue
        if "discord" in lower and not include_discord_segments:
            continue
        expanded_segments.append(
            _expand_profile_placeholders(segment, core_dir, game_filter_tcp, game_filter_udp)
        )

    telegram_segments = _build_telegram_mode_winws_segments(core_dir, settings)
    expanded_preamble = _expand_profile_placeholders(
        preamble,
        core_dir,
        game_filter_tcp,
        game_filter_udp,
    )
    command_parts = [f'"{winws_path}"']
    if expanded_preamble:
        command_parts.append(expanded_preamble)
    command_parts.extend(seg for seg in telegram_segments if seg)
    command_parts.extend(seg for seg in expanded_segments if seg)
    return " ".join(command_parts).strip()


def _ensure_background_service(core_dir: str) -> None:
    if APP_SHUTTING_DOWN.is_set():
        raise RuntimeError("Application is shutting down")
    helper = _bundled_path("background_service", "ZapretGUI.Service.exe")
    if not os.path.isfile(helper):
        raise RuntimeError("Не найден компонент фонового запуска. Переустановите Zapret GUI.")
    _bypass_service.ensure(helper, os.path.join(core_dir, "bin"))


def _launch_profile_process_core(script: str, core_dir: str, settings: QSettings | None = None):
    """BAT is data only. Never execute its START/runas/update preamble."""
    if APP_SHUTTING_DOWN.is_set():
        raise RuntimeError("Application is shutting down")
    commandline = _build_game_mode_winws_command(script, core_dir, settings)
    return _bypass_service.start(
        commandline, os.path.join(core_dir, "bin"),
        _bundled_path("background_service", "ZapretGUI.Service.exe"),
    )


def _prepare_adaptive_profile_hosts_for_launch(script: str, settings: QSettings | None = None) -> bool:
    """Apply the Telegram hosts block required by an adaptive profile.

    The returned flag records whether this launch owns that block and therefore
    has to remove it again when the bypass is stopped.
    """
    if not profile_requires_telegram_hosts(os.path.abspath(str(script or ""))):
        return False
    try:
        existing_text = _read_hosts_file_strict(DNS_MALW_HOSTS_PATH)
    except FileNotFoundError:
        existing_text = ""
    except Exception:
        existing_text = _read_hosts_file(DNS_MALW_HOSTS_PATH)
    already_present = _hosts_contains_flowseal_telegram_block(existing_text)
    if not already_present and not _apply_flowseal_telegram_hosts(True, settings):
        raise RuntimeError(
            "Не удалось применить проверенный адрес Telegram в системный hosts."
        )
    return not already_present


def _release_adaptive_profile_hosts_after_stop(owned: bool, settings: QSettings | None = None) -> str:
    if not owned or _is_telegram_mode_enabled(settings):
        return ""
    if not _apply_flowseal_telegram_hosts(False, settings):
        return "Could not remove adaptive Telegram hosts block"
    return ""


def _wait_for_winws_exit(timeout: float = 10.0) -> bool:
    deadline = time.monotonic() + max(0.1, float(timeout))
    while _is_winws_running_silent():
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.1)
    return True


def _force_stop_blockers(core_dir: str | None = None, timeout: float = 12.0):
    """Stop winws and recover once from a stale/broken service connection.

    The GUI never starts profile BAT files directly.  If the service pipe was
    interrupted while winws is still alive, reconnecting to the per-user
    service lets it terminate the process tree from the elevated side instead
    of leaving a console/process that the non-elevated GUI cannot control.
    """
    core_dir = os.path.abspath(core_dir or os.path.join(APP_DIR, "core"))
    deadline = time.monotonic() + max(3.0, float(timeout))
    first_error = None

    try:
        _bypass_service.stop()
    except Exception as error:
        first_error = error

    # A healthy service confirms stop synchronously. Give a just-disconnected
    # service a short grace period to run its pipe-finally/job cleanup first.
    if _wait_for_winws_exit(min(2.0, max(0.1, deadline - time.monotonic()))):
        return

    recovery_error = None
    try:
        _ensure_background_service(core_dir)
        _bypass_service.stop()
    except Exception as error:
        recovery_error = error

    if _wait_for_winws_exit(max(0.1, deadline - time.monotonic())):
        return

    details = [str(error) for error in (first_error, recovery_error) if error]
    suffix = f" Детали: {'; '.join(details)}" if details else ""
    raise RuntimeError(
        "winws всё ещё работает. Возможно, он запущен другой копией zapret. "
        "Остановите её перед переключением обхода." + suffix
    )


def _stop_winws_for_update_check() -> bool:
    """Stop the active bypass and wait until winws has actually exited."""
    if not _is_winws_running_silent():
        return False

    _force_stop_blockers(os.path.join(APP_DIR, "core"))
    if _is_winws_running_silent():
        raise RuntimeError("winws process did not stop")
    return True


def _check_flowseal_update_with_winws_recovery(
    settings: QSettings | None = None,
    should_cancel=None,
    phase_callback=None,
) -> dict:
    """Check core updates without requiring a manual winws reset."""
    def _cancelled() -> bool:
        try:
            return bool(should_cancel and should_cancel())
        except Exception:
            return False

    def _phase(name: str) -> None:
        try:
            if phase_callback:
                phase_callback(name)
        except Exception:
            pass

    def _cancelled_result() -> dict:
        return {"ok": False, "status": "cancelled", "error": "cancelled", "offline": False}

    bypass_stopped = False
    reset_performed = False
    retried = False

    try:
        if _cancelled():
            result = _cancelled_result()
            result["bypass_stopped"] = bypass_stopped
            result["winws_reset"] = reset_performed
            result["update_retried"] = retried
            return result
        if _is_winws_running_silent():
            _phase("stopping-bypass")
            bypass_stopped = _stop_winws_for_update_check()
        if _cancelled():
            result = _cancelled_result()
            result["bypass_stopped"] = bypass_stopped
            result["winws_reset"] = reset_performed
            result["update_retried"] = retried
            return result

        result = _check_flowseal_update_async(
            settings,
            should_cancel=should_cancel,
            phase_callback=phase_callback,
        )

        # A stale WinDivert/winws state can break the first network check right
        # after stopping the bypass. Reset once and make one clean retry.
        if (
            not _cancelled()
            and not result.get("ok")
            and str(result.get("status") or "") in UPDATE_CHECK_RECOVERABLE_STATUSES
        ):
            _phase("resetting-winws")
            _force_stop_blockers()
            if _is_winws_running_silent():
                raise RuntimeError("winws process did not stop after reset")
            reset_performed = True
            _phase("retrying-update")
            retried = True
            result = _check_flowseal_update_async(
                settings,
                should_cancel=should_cancel,
                phase_callback=phase_callback,
            )
    except Exception as error:
        result = {
            "ok": False,
            "status": "winws-reset-failed",
            "error": str(error),
            "offline": False,
        }

    result["bypass_stopped"] = bypass_stopped
    result["winws_reset"] = reset_performed
    result["update_retried"] = retried
    return result


def _is_winws_running_silent() -> bool:
    import psutil
    for process in psutil.process_iter(["name"]):
        try:
            if str(process.info.get("name") or "").casefold() == "winws.exe":
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue
    return False


