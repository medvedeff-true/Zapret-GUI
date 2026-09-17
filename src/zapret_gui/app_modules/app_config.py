APP_VERSION = "3.0.0"

# Application-wide settings and bundled runtime paths.
APP_DIR = _app_dir_from_cli_or_default()
os.makedirs(APP_DIR, exist_ok=True)

USER_DIR = os.path.join(APP_DIR, "user")
os.makedirs(USER_DIR, exist_ok=True)
USER_STRATEGY_BACKUP_DIR = os.path.join(USER_DIR, "strategy-backups")
ADAPTIVE_STRATEGY_DIR = os.path.join(USER_DIR, "adaptive-strategies")
# Generated and manually imported profiles intentionally share one user-owned
# directory.  Built-in profiles are only read from ``core``.
USER_PROFILE_DIR = ADAPTIVE_STRATEGY_DIR
ADAPTIVE_RUNTIME_DIR = os.path.join(USER_DIR, "adaptive-runtime")
ADAPTIVE_REPORT_FILE = os.path.join(USER_DIR, "adaptive-search-last.json")
# The automatic profile builder certifies the two services for which it has a
# complete, protocol-specific probe matrix. Other blocked sites are handled by
# the user/general domain lists and must never become mandatory build gates.
ADAPTIVE_TARGET_URLS = (
    "https://www.youtube.com/generate_204",
    "https://discord.com/api/v10/gateway",
)
ADAPTIVE_TIMEOUT_SECONDS = 5.0

FLOWSEAL_REPO = "Flowseal/zapret-discord-youtube"
FLOWSEAL_DEFAULT_VER = "1.10.2"
FLOWSEAL_VER_KEY = "flowseal_release"
FLOWSEAL_VERSION_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/.service/version.txt"

FLOWSEAL_LIST_BASE_URL = "https://raw.githubusercontent.com/Flowseal/zapret-discord-youtube/main/lists/"
FLOWSEAL_LIST_FILES = (
    "ipset-all.txt",
    "ipset-exclude.txt",
    "list-exclude.txt",
    "list-general.txt",
    "list-google.txt",
)

GAMING_LISTS_REPO = "medvedeff-true/ru-gaming-blocklist"
GAMING_LISTS_API_URL = f"https://api.github.com/repos/{GAMING_LISTS_REPO}/contents/"
GUI_REPO = "medvedeff-true/Zapret-GUI"
GUI_RELEASES_URL = f"https://github.com/{GUI_REPO}/releases"
GUI_SKIPPED_UPDATE_KEY = "gui_update/skipped_version"
GUI_UPDATE_STARTUP_LAST_CHECK_KEY = "gui_update/startup_last_check"
GUI_UPDATE_STARTUP_MIN_INTERVAL_SECONDS = 6 * 60 * 60
TG_WS_PROXY_REPO = "Flowseal/tg-ws-proxy"
TG_WS_PROXY_RELEASES_URL = f"https://github.com/{TG_WS_PROXY_REPO}/releases"
TG_WS_PROXY_VENDOR_VERSION = "1.6.5"
GAME_MODE_KEY = "game_mode_enabled"
GAME_MODE_MAIN_BYPASS_KEY = "game_mode/main_bypass_enabled"
GAME_MODE_USER_LISTS_KEY = "game_mode/user_lists_enabled"
GAME_MODE_DISCORD_KEY = "game_mode/discord_enabled"
GAME_LIST_DOMAIN_SHA_KEY = "gaming_lists/domain_remote_sha"
GAME_LIST_DOMAIN_HASH_KEY = "gaming_lists/domain_local_sha256"
GAME_LIST_IP_SHA_KEY = "gaming_lists/ip_remote_sha"
GAME_LIST_IP_HASH_KEY = "gaming_lists/ip_local_sha256"
LISTS_SYNC_LAST_ATTEMPT_KEY = "lists_sync/last_attempt"
LISTS_SYNC_LAST_SUCCESS_KEY = "lists_sync/last_success"
LISTS_SYNC_MIN_INTERVAL_SECONDS = 6 * 60 * 60
LISTS_STARTUP_RETRY_DELAYS_SECONDS = (2.0, 5.0)
GAME_FILTER_FLAG_MODE = "all"
TELEGRAM_MODE_ENABLED_KEY = "telegram_mode/enabled"
TELEGRAM_MODE_PROXY_ENABLED_KEY = "telegram_mode/proxy_enabled"
TELEGRAM_MODE_PROXY_PORT_KEY = "telegram_mode/proxy_port"
TELEGRAM_MODE_PROXY_SECRET_KEY = "telegram_mode/proxy_secret"
TELEGRAM_MODE_LAST_ERROR_KEY = "telegram_mode/last_error"
TELEGRAM_MODE_HOSTS_ENABLED_KEY = "telegram_mode/hosts_enabled_by_app"
TELEGRAM_MODE_HOSTS_LAST_ATTEMPT_KEY = "telegram_mode/hosts_last_attempt"
TELEGRAM_MODE_HOSTS_LAST_STATUS_KEY = "telegram_mode/hosts_last_status"
TELEGRAM_MODE_HOSTS_LAST_ERROR_KEY = "telegram_mode/hosts_last_error"
FLOWSEAL_TELEGRAM_HOSTS_BEGIN = "# ZapretGUI Flowseal Telegram Web hosts begin"
FLOWSEAL_TELEGRAM_HOSTS_END = "# ZapretGUI Flowseal Telegram Web hosts end"

SETTINGS_FILE = os.path.join(APP_DIR, 'settings.ini')
VERSION_FILE = os.path.join(APP_DIR, '.app_version')
AUTOLOG_FILE = os.path.join(APP_DIR, "autotest_last.log")
AUTORESULT_FILE = os.path.join(APP_DIR, "autotest_result.json")

REMOVE_BAT = os.path.join(APP_DIR, "uninstall.bat")

NOUPDATE_INP = os.path.join(APP_DIR, "_no_update_input.txt")

USER_GENERAL_FILE = os.path.join(USER_DIR, "list-general-user.txt")
USER_EXCLUDE_FILE = os.path.join(USER_DIR, "list-exclude-user.txt")
USER_IP_ALL_FILE = os.path.join(USER_DIR, "ipset-all-user.txt")
USER_IP_EXCLUDE_FILE = os.path.join(USER_DIR, "ipset-exclude-user.txt")
USER_GAME_DOMAIN_FILE = os.path.join(USER_DIR, "medvedeff-game-list-all.txt")
USER_GAME_IP_FILE = os.path.join(USER_DIR, "medvedeff-game-ipset.txt")
USER_TELEGRAM_DOMAIN_FILE = os.path.join(USER_DIR, "telegram-domains.txt")
USER_TELEGRAM_IP_FILE = os.path.join(USER_DIR, "telegram-ipset.txt")
FLOWSEAL_SOURCE_PREFIX = "flowseal-source-"
CORE_STRATEGY_RESERVED_BAT_NAMES = {
    "service.bat",
    "cloudflare_switch.bat",
    "discord.bat",
}

RUNTIME_GENERAL_FILE = os.path.join(APP_DIR, "core", "lists", "list-general.txt")
RUNTIME_EXCLUDE_FILE = os.path.join(APP_DIR, "core", "lists", "list-exclude.txt")
RUNTIME_IP_ALL_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-all.txt")
RUNTIME_IP_EXCLUDE_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-exclude.txt")
RUNTIME_GOOGLE_FILE = os.path.join(APP_DIR, "core", "lists", "list-google.txt")
RUNTIME_DISCORD_FILE = os.path.join(APP_DIR, "core", "lists", "list-discord.txt")
RUNTIME_GENERAL_USER_FILE = os.path.join(APP_DIR, "core", "lists", "list-general-user.txt")
RUNTIME_EXCLUDE_USER_FILE = os.path.join(APP_DIR, "core", "lists", "list-exclude-user.txt")
RUNTIME_IP_ALL_USER_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-all-user.txt")
RUNTIME_IP_EXCLUDE_USER_FILE = os.path.join(APP_DIR, "core", "lists", "ipset-exclude-user.txt")
RUNTIME_TELEGRAM_DOMAIN_FILE = os.path.join(APP_DIR, "core", "lists", "telegram-domains.txt")
RUNTIME_TELEGRAM_IP_FILE = os.path.join(APP_DIR, "core", "lists", "telegram-ipset.txt")
GAME_FILTER_FLAG_FILE = os.path.join(APP_DIR, "core", "utils", "game_filter.enabled")
USER_LIST_SEEDED_BACKUP_SUFFIX = ".seeded-backup"
USER_LIST_SEEDED_OVERLAP_RATIO = 0.60
PLACEHOLDER_ITEM_ROLE = int(Qt.ItemDataRole.UserRole) + 1

EMPTY_USER_LIST_PLACEHOLDERS = {
    USER_GENERAL_FILE: ["example.com"],
    USER_EXCLUDE_FILE: ["example.org"],
    USER_IP_ALL_FILE: ["203.0.113.10"],
    USER_IP_EXCLUDE_FILE: ["203.0.113.11"],
}

USER_LIST_FILE_MAP = {
    ("domain", "add"): USER_GENERAL_FILE,
    ("domain", "exclude"): USER_EXCLUDE_FILE,
    ("ip", "add"): USER_IP_ALL_FILE,
    ("ip", "exclude"): USER_IP_EXCLUDE_FILE,
}

GAMING_LIST_TARGETS = {
    "medvedeff-game-list-all.txt": {
        "path": USER_GAME_DOMAIN_FILE,
        "remote_sha_key": GAME_LIST_DOMAIN_SHA_KEY,
        "local_hash_key": GAME_LIST_DOMAIN_HASH_KEY,
    },
    "medvedeff-game-ipset.txt": {
        "path": USER_GAME_IP_FILE,
        "remote_sha_key": GAME_LIST_IP_SHA_KEY,
        "local_hash_key": GAME_LIST_IP_HASH_KEY,
    },
}

# Curated Telegram Web list. Keep it in sync with Telegram Web endpoint changes.
TELEGRAM_WEB_DOMAINS = (
    "web.telegram.org",
    "webk.telegram.org",
    "webz.telegram.org",
    "weba.telegram.org",
    "telegram.org",
    "t.me",
    "telegram.me",
    "telegram.dog",
    "telegram.space",
    "telesco.pe",
    "tg.dev",
    "api.telegram.org",
    "td.telegram.org",
    "kws1.web.telegram.org",
    "kws2.web.telegram.org",
    "kws3.web.telegram.org",
    "kws4.web.telegram.org",
    "kws5.web.telegram.org",
    "zws2.web.telegram.org",
    "zws4.web.telegram.org",
    "pluto.web.telegram.org",
    "venus.web.telegram.org",
    "aurora.web.telegram.org",
    "vesta.web.telegram.org",
    "flora.web.telegram.org",
    "kws2-1.web.telegram.org",
    "kws4-1.web.telegram.org",
    "zws2-1.web.telegram.org",
    "zws4-1.web.telegram.org",
    "pluto-1.web.telegram.org",
    "venus-1.web.telegram.org",
    "aurora-1.web.telegram.org",
    "vesta-1.web.telegram.org",
    "flora-1.web.telegram.org",
)

FLOWSEAL_TELEGRAM_WEB_HOSTS = (
    ("149.154.167.220", "my.telegram.org"),
    ("149.154.167.220", "desktop.telegram.org"),
    ("149.154.167.220", "macos.telegram.org"),
    ("149.154.167.220", "oauth.telegram.org"),
    ("149.154.167.220", "oauth.tg.dev"),
    ("149.154.167.220", "cdn.telesco.pe"),
    ("149.154.167.220", "cdn1.telesco.pe"),
    ("149.154.167.220", "cdn2.telesco.pe"),
    ("149.154.167.220", "cdn3.telesco.pe"),
    ("149.154.167.220", "cdn4.telesco.pe"),
    ("149.154.167.220", "cdn5.telesco.pe"),
    ("149.154.167.220", "cdn6.telesco.pe"),
    ("149.154.167.220", "core.telegram.org"),
    ("149.154.167.220", "zws4.web.telegram.org"),
    ("149.154.167.220", "vesta.web.telegram.org"),
    ("149.154.167.220", "vesta-1.web.telegram.org"),
    ("149.154.167.220", "venus-1.web.telegram.org"),
    ("149.154.167.220", "telegram.me"),
    ("149.154.167.220", "telegram.dog"),
    ("149.154.167.220", "telegram.space"),
    ("149.154.167.220", "telesco.pe"),
    ("149.154.167.220", "tg.dev"),
    ("149.154.167.220", "telegram.org"),
    ("149.154.167.220", "t.me"),
    ("149.154.167.220", "api.telegram.org"),
    ("149.154.167.220", "td.telegram.org"),
    ("149.154.167.220", "venus.web.telegram.org"),
    ("149.154.167.220", "web.telegram.org"),
    ("149.154.167.220", "kws2-1.web.telegram.org"),
    ("149.154.167.220", "kws2.web.telegram.org"),
    ("149.154.167.220", "kws4-1.web.telegram.org"),
    ("149.154.167.220", "kws4.web.telegram.org"),
    ("149.154.167.220", "zws2-1.web.telegram.org"),
    ("149.154.167.220", "zws2.web.telegram.org"),
    ("149.154.167.220", "zws4-1.web.telegram.org"),
)

# Based on https://core.telegram.org/resources/cidr.txt. Update periodically.
TELEGRAM_IP_RANGES = (
    "91.108.56.0/22",
    "91.108.4.0/22",
    "91.108.8.0/22",
    "91.108.16.0/22",
    "91.108.12.0/22",
    "149.154.160.0/20",
    "91.105.192.0/23",
    "91.108.20.0/22",
    "185.76.151.0/24",
    "2001:b28:f23d::/48",
    "2001:b28:f23f::/48",
    "2001:67c:4e8::/48",
    "2001:b28:f23c::/48",
    "2a0a:f280::/32",
)

DNS_MALW_IPV4_SERVERS = (
    "84.21.189.133",
    "193.23.209.189",
)
DNS_MALW_IPV6_SERVERS = (
    "2a12:bec4:1460:294::2",
    "2a01:ecc0:680:120::2",
)
DNS_MALW_DOH_TEMPLATE = "https://dns.malw.link/dns-query"
DNS_MALW_LAST_ATTEMPT_KEY = "dns_malw_link/last_attempt"
DNS_MALW_LAST_SUCCESS_KEY = "dns_malw_link/last_success"
DNS_MALW_LAST_STATUS_KEY = "dns_malw_link/last_status"
DNS_MALW_LAST_ERROR_KEY = "dns_malw_link/last_error"
DNS_MALW_LAST_UPDATED_KEY = "dns_malw_link/last_updated"
DNS_MALW_LAST_DOH_KEY = "dns_malw_link/last_doh"
DNS_MALW_ENABLED_BY_APP_KEY = "dns_malw_link/enabled_by_app"
DNS_MALW_RESTORE_SNAPSHOT_KEY = "dns_malw_link/restore_snapshot"
# Ai DNS hosts change independently from a ZapretGUI release.  Keep an enabled
# installation fresh soon after the next launch instead of letting an old cache
# stay in use for most of a day.
DNS_MALW_STARTUP_SYNC_MIN_INTERVAL_SECONDS = 30 * 60
DNS_MALW_HOSTS_URL = "https://raw.githubusercontent.com/ImMALWARE/dns.malw.link/master/hosts"
DNS_MALW_ADDITIONAL_URL = "https://raw.githubusercontent.com/AvenCores/Goida-AI-Unlocker/main/additional_hosts.py"
DNS_MALW_HOSTS_MIRROR_URLS = (
    "https://cdn.jsdelivr.net/gh/ImMALWARE/dns.malw.link@master/hosts",
    "https://gcore.jsdelivr.net/gh/ImMALWARE/dns.malw.link@master/hosts",
    "https://fastly.jsdelivr.net/gh/ImMALWARE/dns.malw.link@master/hosts",
)
DNS_MALW_ADDITIONAL_MIRROR_URLS = (
    "https://cdn.jsdelivr.net/gh/AvenCores/Goida-AI-Unlocker@main/additional_hosts.py",
    "https://gcore.jsdelivr.net/gh/AvenCores/Goida-AI-Unlocker@main/additional_hosts.py",
    "https://fastly.jsdelivr.net/gh/AvenCores/Goida-AI-Unlocker@main/additional_hosts.py",
)
DNS_MALW_HOSTS_PATH = r"C:\Windows\System32\drivers\etc\hosts"
DNS_MALW_HOSTS_BACKUP_PATH = os.path.join(APP_DIR, "dns_malw_hosts_backup.txt")
DNS_MALW_HOSTS_CACHE_PATH = os.path.join(APP_DIR, "dns_malw_hosts_cache.txt")
DNS_MALW_HOSTS_SEED_PATH = os.path.join(APP_DIR, "core", "lists", "dns_malw_hosts_seed.txt")
DNS_MALW_HOSTS_BLOCK_BEGIN = "# ZapretGUI Ai DNS BEGIN"
DNS_MALW_HOSTS_BLOCK_END = "# ZapretGUI Ai DNS END"
DNS_MALW_LEGACY_HOSTS_BLOCK_BEGIN = "### dns.malw.link: hosts file"
DNS_MALW_LEGACY_HOSTS_BLOCK_END = "### dns.malw.link: end hosts file"
DNS_MALW_LEGACY_ADDITIONAL_BLOCK_BEGIN = "# Goida-AI-Unlocker additional hosts"
DNS_MALW_ADDITIONAL_VERSION_RE = re.compile(r'version_add\s*=\s*["\\\']([^"\\\']+)["\\\']')
DNS_MALW_ADDITIONAL_HOSTS_RE = re.compile(
    r'hosts_add\s*=\s*(?:r|R)?(?P<quote>"""|\'\'\')(?P<body>.*?)(?P=quote)',
    re.S,
)
DNS_MALW_PROTECTED_HOSTS = {
    "api.github.com",
    "github.com",
    "www.github.com",
    "raw.githubusercontent.com",
    "objects.githubusercontent.com",
    "codeload.github.com",
}
DNS_MALW_LEGACY_AI_HOST_SUFFIXES = (
    "ai.com",
    "chat.com",
    "chatgpt.com",
    "openai.com",
    "oaistatic.com",
    "oaiusercontent.com",
    "claude.ai",
    "anthropic.com",
    "gemini.google.com",
    "aistudio.google.com",
    "generativelanguage.googleapis.com",
    "makersuite.google.com",
    "perplexity.ai",
    "poe.com",
    "grok.com",
    "x.ai",
    "copilot.microsoft.com",
    "edgeservices.bing.com",
)
DNS_MALW_LEGACY_AI_HOST_TOKENS = (
    "dns.malw.link",
    "goida-ai-unlocker",
    "chatgpt",
    "openai",
    "oaistatic",
    "oaiusercontent",
    "claude",
    "anthropic",
    "gemini",
    "generativelanguage",
    "makersuite",
    "aistudio",
    "perplexity",
    "grok",
)

AUTOSTART_LAUNCH_ARGUMENT = "--autostart"
APP_SHUTTING_DOWN = threading.Event()
UPDATE_CHECK_RECOVERABLE_STATUSES = {"offline", "error", "winws-running"}
