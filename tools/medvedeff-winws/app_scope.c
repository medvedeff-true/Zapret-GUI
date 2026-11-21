#ifdef __CYGWIN__

#include <winsock2.h>
#include "app_scope.h"

#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include <wchar.h>
#include <iphlpapi.h>

#include "windivert/windivert.h"

#define APP_SCOPE_MAX_APPS 256
#define APP_SCOPE_MAX_PATH 32768
#define APP_SCOPE_MAX_FLOWS 16384

typedef struct
{
    WCHAR *path;
} selected_app;

typedef struct
{
    bool used;
    bool ipv6;
    bool selected;
    uint8_t protocol;
    uint32_t local_addr[4];
    uint32_t remote_addr[4];
    uint16_t local_port;
    uint16_t remote_port;
    DWORD process_id;
    UINT64 endpoint_id;
    INT64 timestamp;
    bool established;
} app_flow;

typedef struct
{
    HANDLE handle;
    HANDLE thread;
} tracker_thread;

static selected_app apps[APP_SCOPE_MAX_APPS];
static size_t app_count;
static app_flow flows[APP_SCOPE_MAX_FLOWS];
static size_t flow_end;
static CRITICAL_SECTION flow_lock;
static CONDITION_VARIABLE flow_changed;
static bool flow_lock_ready;
static volatile LONG stopping;
static volatile LONG tracker_failed;
static tracker_thread socket_tracker;
static tracker_thread flow_tracker;
static HMODULE iphlpapi_module;
static INT64 event_max_age;

typedef struct
{
    BYTE *data;
    DWORD capacity;
    ULONGLONG updated;
    bool valid;
} owner_snapshot;

/* Owned by the NETWORK loop only. Never persist a snapshot match in flows. */
static owner_snapshot owners[2];

typedef DWORD (WINAPI *get_extended_tcp_table_fn)(
    PVOID, PDWORD, WINBOOL, ULONG, TCP_TABLE_CLASS, ULONG
);
static get_extended_tcp_table_fn get_extended_tcp_table;

static bool load_ip_helper_api(void)
{
    if (get_extended_tcp_table) return true;
    iphlpapi_module = LoadLibraryExW(L"iphlpapi.dll", NULL, LOAD_LIBRARY_SEARCH_SYSTEM32);
    if (!iphlpapi_module) return false;
    get_extended_tcp_table = (get_extended_tcp_table_fn)GetProcAddress(
        iphlpapi_module, "GetExtendedTcpTable"
    );
    if (!get_extended_tcp_table)
    {
        FreeLibrary(iphlpapi_module);
        iphlpapi_module = NULL;
        get_extended_tcp_table = NULL;
        return false;
    }
    return true;
}

static void unload_ip_helper_api(void)
{
    if (iphlpapi_module) FreeLibrary(iphlpapi_module);
    iphlpapi_module = NULL;
    get_extended_tcp_table = NULL;
}

static bool is_zero_address(const uint32_t *address)
{
    return !address[0] && !address[1] && !address[2] && !address[3];
}

static bool address_is_ipv4(const uint32_t addr[4])
{
    return addr[1] == 0xFFFF && !addr[2] && !addr[3];
}

static void ipv4_key(uint32_t raw, uint32_t addr[4])
{
    addr[0] = WinDivertHelperNtohl(raw);
    addr[1] = 0xFFFF;
    addr[2] = addr[3] = 0;
}

static const WCHAR *path_without_prefix(const WCHAR *path)
{
    return wcsncmp(path, L"\\\\?\\", 4) == 0 && path[4] && path[5] == L':'
        ? path + 4 : path;
}

static bool is_absolute_executable(const WCHAR *path)
{
    const WCHAR *p = path_without_prefix(path);
    return (((p[0] >= L'A' && p[0] <= L'Z') || (p[0] >= L'a' && p[0] <= L'z')) &&
            p[1] == L':' && p[2] == L'\\') || (p[0] == L'\\' && p[1] == L'\\');
}

static bool process_is_selected(DWORD pid)
{
    HANDLE process;
    WCHAR wide_path[APP_SCOPE_MAX_PATH];
    DWORD length = (DWORD)(sizeof(wide_path) / sizeof(wide_path[0]));
    const WCHAR *path;
    size_t i;

    if (!pid) return false;
    process = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, FALSE, pid);
    if (!process) return false;
    if (!QueryFullProcessImageNameW(process, 0, wide_path, &length))
    {
        CloseHandle(process);
        return false;
    }
    CloseHandle(process);
    path = path_without_prefix(wide_path);
    for (i = 0; i < app_count; ++i)
        if (CompareStringOrdinal(path, -1, path_without_prefix(apps[i].path), -1, TRUE)
            == CSTR_EQUAL) return true;
    return false;
}

static bool same_flow(
    const app_flow *flow,
    bool ipv6,
    uint8_t protocol,
    const uint32_t *local_addr,
    const uint32_t *remote_addr,
    uint16_t local_port,
    uint16_t remote_port,
    DWORD process_id,
    UINT64 endpoint_id
)
{
    return flow->used && flow->ipv6 == ipv6 && flow->protocol == protocol &&
        flow->local_port == local_port && flow->remote_port == remote_port &&
        flow->process_id == process_id &&
        flow->endpoint_id == endpoint_id &&
        !memcmp(flow->local_addr, local_addr, sizeof(flow->local_addr)) &&
        !memcmp(flow->remote_addr, remote_addr, sizeof(flow->remote_addr));
}

static void remember_flow_values(
    uint8_t protocol,
    const uint32_t *local_addr,
    const uint32_t *remote_addr,
    uint16_t local_port,
    uint16_t remote_port,
    DWORD process_id,
    UINT64 endpoint_id,
    INT64 timestamp,
    bool established
)
{
    app_flow *free_slot = NULL;
    size_t i;
    bool selected, ipv6;

    if ((protocol != IPPROTO_TCP && protocol != IPPROTO_UDP) ||
        !local_port || !remote_port || !endpoint_id ||
        is_zero_address(local_addr) || is_zero_address(remote_addr)) return;
    ipv6 = !address_is_ipv4(local_addr) || !address_is_ipv4(remote_addr);
    selected = process_is_selected(process_id);

    EnterCriticalSection(&flow_lock);
    for (i = 0; i < flow_end; ++i)
    {
        if (same_flow(
            &flows[i], ipv6, protocol, local_addr, remote_addr,
            local_port, remote_port, process_id, endpoint_id
        ))
        {
            flows[i].established |= established;
            if (flows[i].timestamp <= timestamp)
            {
                flows[i].timestamp = timestamp;
                flows[i].selected = selected;
            }
            WakeConditionVariable(&flow_changed);
            LeaveCriticalSection(&flow_lock);
            return;
        }
        if ((!flows[i].used || (!flows[i].established &&
             timestamp - flows[i].timestamp > event_max_age)) && !free_slot)
            free_slot = &flows[i];
    }
    if (!free_slot && flow_end < APP_SCOPE_MAX_FLOWS)
        free_slot = &flows[flow_end++];
    if (free_slot)
    {
        memset(free_slot, 0, sizeof(*free_slot));
        free_slot->used = true;
        free_slot->ipv6 = ipv6;
        free_slot->selected = selected;
        free_slot->protocol = protocol;
        memcpy(free_slot->local_addr, local_addr, sizeof(free_slot->local_addr));
        memcpy(free_slot->remote_addr, remote_addr, sizeof(free_slot->remote_addr));
        free_slot->local_port = local_port;
        free_slot->remote_port = remote_port;
        free_slot->process_id = process_id;
        free_slot->endpoint_id = endpoint_id;
        free_slot->timestamp = timestamp;
        free_slot->established = established;
        WakeConditionVariable(&flow_changed);
    }
    LeaveCriticalSection(&flow_lock);
}

static void remember_socket(const WINDIVERT_ADDRESS *address)
{
    const WINDIVERT_DATA_SOCKET *socket_data = &address->Socket;
    remember_flow_values(
        socket_data->Protocol,
        socket_data->LocalAddr, socket_data->RemoteAddr,
        socket_data->LocalPort, socket_data->RemotePort,
        socket_data->ProcessId, socket_data->EndpointId, address->Timestamp, false
    );
}

static void remember_flow_event(const WINDIVERT_ADDRESS *address)
{
    const WINDIVERT_DATA_FLOW *flow_data = &address->Flow;
    remember_flow_values(
        flow_data->Protocol,
        flow_data->LocalAddr, flow_data->RemoteAddr,
        flow_data->LocalPort, flow_data->RemotePort,
        flow_data->ProcessId, flow_data->EndpointId, address->Timestamp, true
    );
}

static void forget_flow_values(
    uint8_t protocol,
    const uint32_t *local_addr,
    const uint32_t *remote_addr,
    uint16_t local_port,
    uint16_t remote_port,
    DWORD process_id,
    UINT64 endpoint_id,
    INT64 timestamp
)
{
    size_t i;

    bool ipv6 = !address_is_ipv4(local_addr) || !address_is_ipv4(remote_addr);
    EnterCriticalSection(&flow_lock);
    for (i = 0; i < flow_end; ++i)
    {
        if (flows[i].timestamp <= timestamp && same_flow(
            &flows[i], ipv6, protocol, local_addr, remote_addr,
            local_port, remote_port, process_id, endpoint_id
        ))
        {
            flows[i].used = false;
            break;
        }
    }
    LeaveCriticalSection(&flow_lock);
}

static void forget_socket(const WINDIVERT_ADDRESS *address)
{
    const WINDIVERT_DATA_SOCKET *socket_data = &address->Socket;
    size_t i;
    EnterCriticalSection(&flow_lock);
    for (i = 0; i < flow_end; ++i)
        if (flows[i].used && flows[i].endpoint_id == socket_data->EndpointId &&
            flows[i].process_id == socket_data->ProcessId &&
            flows[i].timestamp <= address->Timestamp)
            flows[i].used = false;
    LeaveCriticalSection(&flow_lock);
}

static void forget_flow_event(const WINDIVERT_ADDRESS *address)
{
    const WINDIVERT_DATA_FLOW *flow_data = &address->Flow;
    forget_flow_values(
        flow_data->Protocol,
        flow_data->LocalAddr, flow_data->RemoteAddr,
        flow_data->LocalPort, flow_data->RemotePort,
        flow_data->ProcessId, flow_data->EndpointId, address->Timestamp
    );
}

static DWORD WINAPI tracker_main(void *context)
{
    tracker_thread *tracker = (tracker_thread *)context;
    WINDIVERT_ADDRESS address;
    UINT received;

    while (!InterlockedCompareExchange(&stopping, 0, 0))
    {
        memset(&address, 0, sizeof(address));
        received = 0;
        if (!WinDivertRecv(tracker->handle, NULL, 0, &received, &address))
        {
            if (InterlockedCompareExchange(&stopping, 0, 0)) break;
            fprintf(stderr, "Application scope: WinDivert receive failed (%lu)\n",
                (unsigned long)GetLastError());
            InterlockedExchange(&tracker_failed, 1);
            break;
        }
        if (address.Layer == WINDIVERT_LAYER_SOCKET)
        {
            if (address.Event == WINDIVERT_EVENT_SOCKET_CONNECT ||
                address.Event == WINDIVERT_EVENT_SOCKET_ACCEPT)
                remember_socket(&address);
            else if (address.Event == WINDIVERT_EVENT_SOCKET_CLOSE)
                forget_socket(&address);
        }
        else if (address.Layer == WINDIVERT_LAYER_FLOW)
        {
            if (address.Event == WINDIVERT_EVENT_FLOW_ESTABLISHED)
                remember_flow_event(&address);
            else if (address.Event == WINDIVERT_EVENT_FLOW_DELETED)
                forget_flow_event(&address);
        }
    }
    return 0;
}

static bool load_selected_apps(const char *paths_file)
{
    FILE *input = fopen(paths_file, "rb");
    char *line = NULL;
    size_t capacity = 0;
    size_t total = 0;
    ssize_t n;
    bool valid = true;

    if (!input) return false;
    if (fseek(input, 0, SEEK_END) || ftell(input) > 1024 * 1024 || fseek(input, 0, SEEK_SET))
    { fclose(input); return false; }
    while ((n = getline(&line, &capacity, input)) >= 0)
    {
        char *text = line;
        int length;
        WCHAR *wide;
        total += (size_t)n;
        if (total > 1024 * 1024 || memchr(line, '\0', n)) { valid = false; break; }
        if (total == (size_t)n && n >= 3 && !memcmp(line, "\xef\xbb\xbf", 3)) text += 3;
        while (n > 0 && (line[n - 1] == '\r' || line[n - 1] == '\n')) line[--n] = 0;
        if (!*text) continue;
        for (char *p = text; *p; ++p) if (*p == '/') *p = '\\';
        length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, NULL, 0);
        if (!length || length > APP_SCOPE_MAX_PATH || app_count == APP_SCOPE_MAX_APPS)
        { valid = false; break; }
        wide = malloc(length * sizeof(*wide));
        if (!wide) { valid = false; break; }
        if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, text, -1, wide, length) ||
            length < 5 || !is_absolute_executable(wide) ||
            CompareStringOrdinal(wide + length - 5, -1, L".exe", -1, TRUE) != CSTR_EQUAL)
        { free(wide); valid = false; break; }
        apps[app_count++].path = wide;
    }
    valid = valid && feof(input) && !ferror(input) && app_count != 0;
    free(line);
    fclose(input);
    return valid;
}

/* TCP's owner table supplies exact tuples for sockets already open at startup
 * and for packets that arrived before the SOCKET/FLOW reader caught up.
 * UDP's owner table has no peer and cannot safely identify shared endpoints. */
static const void *refresh_tcp_snapshot(bool ipv6)
{
    owner_snapshot *snapshot = &owners[ipv6 ? 1 : 0];
    DWORD size = snapshot->capacity;
    DWORD result;

    snapshot->valid = false;
    if (!load_ip_helper_api()) return NULL;
    result = get_extended_tcp_table(snapshot->data, &size, FALSE, ipv6 ? AF_INET6 : AF_INET,
        TCP_TABLE_OWNER_PID_CONNECTIONS, 0);
    if (result == ERROR_INSUFFICIENT_BUFFER && size <= 16 * 1024 * 1024)
    {
        BYTE *buffer = realloc(snapshot->data, size);
        if (!buffer) return NULL;
        snapshot->data = buffer;
        snapshot->capacity = size;
        result = get_extended_tcp_table(buffer, &size, FALSE, ipv6 ? AF_INET6 : AF_INET,
            TCP_TABLE_OWNER_PID_CONNECTIONS, 0);
    }
    if (result != NO_ERROR) return NULL;
    snapshot->valid = true;
    snapshot->updated = GetTickCount64();
    return snapshot->data;
}

static DWORD tcp_snapshot_pid(const void *snapshot, bool ipv6, const uint32_t *local,
    const uint32_t *remote, uint16_t local_port, uint16_t remote_port)
{
    DWORD pid = 0;
    if (!snapshot) return 0;
    if (ipv6)
    {
        const MIB_TCP6TABLE_OWNER_PID *table = snapshot;
        for (DWORD i = 0; i < table->dwNumEntries; ++i)
        {
            const MIB_TCP6ROW_OWNER_PID *row = &table->table[i];
            uint32_t l[4], r[4], l_raw[4], r_raw[4];
            if (row->dwState == MIB_TCP_STATE_TIME_WAIT || !row->dwOwningPid ||
                WinDivertHelperNtohs((uint16_t)row->dwLocalPort) != local_port ||
                WinDivertHelperNtohs((uint16_t)row->dwRemotePort) != remote_port) continue;
            memcpy(l_raw, row->ucLocalAddr, sizeof(l_raw));
            memcpy(r_raw, row->ucRemoteAddr, sizeof(r_raw));
            WinDivertHelperNtohIPv6Address(l_raw, l);
            WinDivertHelperNtohIPv6Address(r_raw, r);
            if (memcmp(l, local, sizeof(l)) || memcmp(r, remote, sizeof(r))) continue;
            if (pid && pid != row->dwOwningPid) return 0;
            pid = row->dwOwningPid;
        }
    }
    else
    {
        const MIB_TCPTABLE_OWNER_PID *table = snapshot;
        for (DWORD i = 0; i < table->dwNumEntries; ++i)
        {
            const MIB_TCPROW_OWNER_PID *row = &table->table[i];
            if (row->dwState == MIB_TCP_STATE_TIME_WAIT || !row->dwOwningPid ||
                WinDivertHelperNtohs((uint16_t)row->dwLocalPort) != local_port ||
                WinDivertHelperNtohs((uint16_t)row->dwRemotePort) != remote_port ||
                WinDivertHelperNtohl(row->dwLocalAddr) != local[0] ||
                WinDivertHelperNtohl(row->dwRemoteAddr) != remote[0]) continue;
            if (pid && pid != row->dwOwningPid) return 0;
            pid = row->dwOwningPid;
        }
    }
    return pid;
}

static bool tcp_owner_is_selected(bool ipv6, const uint32_t *local, const uint32_t *remote,
    uint16_t local_port, uint16_t remote_port)
{
    const owner_snapshot *cached = &owners[ipv6 ? 1 : 0];
    bool reuse = cached->valid && GetTickCount64() - cached->updated < 100;
    DWORD pid = tcp_snapshot_pid(reuse ? cached->data : refresh_tcp_snapshot(ipv6), ipv6,
        local, remote, local_port, remote_port);
    /* A connection can complete its handshake inside the snapshot lifetime.
     * On a miss, refresh before letting the first application data pass. */
    if (!pid && reuse)
        pid = tcp_snapshot_pid(refresh_tcp_snapshot(ipv6), ipv6,
            local, remote, local_port, remote_port);
    return process_is_selected(pid);
}

static void close_tracker(tracker_thread *tracker)
{
    if (!tracker->handle || tracker->handle == INVALID_HANDLE_VALUE) return;
    if (!WinDivertShutdown(tracker->handle, WINDIVERT_SHUTDOWN_RECV))
    {
        WinDivertClose(tracker->handle);
        if (tracker->thread) WaitForSingleObject(tracker->thread, INFINITE);
        tracker->handle = NULL;
    }
    if (tracker->thread)
    {
        WaitForSingleObject(tracker->thread, INFINITE);
        CloseHandle(tracker->thread);
        tracker->thread = NULL;
    }
    if (tracker->handle) WinDivertClose(tracker->handle);
    tracker->handle = NULL;
}

bool app_scope_validate(const char *paths_file)
{
    bool valid = paths_file && load_selected_apps(paths_file);
    app_scope_stop();
    return valid;
}

bool app_scope_start(const char *paths_file)
{
    LARGE_INTEGER frequency;
    if (!paths_file || !load_selected_apps(paths_file))
    {
        fprintf(stderr, "Application scope: expected a nonempty UTF-8 list of executable paths\n");
        app_scope_stop();
        return false;
    }
    QueryPerformanceFrequency(&frequency);
    event_max_age = frequency.QuadPart * 60;
    InitializeCriticalSection(&flow_lock);
    InitializeConditionVariable(&flow_changed);
    flow_lock_ready = true;
    InterlockedExchange(&stopping, 0);
    InterlockedExchange(&tracker_failed, 0);

    /*
     * SOCKET catches connect() before the first network packet. FLOW is a
     * second source for stacks which do not expose a useful SOCKET event.
     * Both handles are sniff-only and never interfere with the application.
     */
    socket_tracker.handle = WinDivertOpen(
        "!loopback and (protocol == 6 or protocol == 17)", WINDIVERT_LAYER_SOCKET, 0,
        WINDIVERT_FLAG_SNIFF | WINDIVERT_FLAG_RECV_ONLY
    );
    if (socket_tracker.handle == INVALID_HANDLE_VALUE)
    {
        fprintf(stderr, "Application scope: cannot open SOCKET layer (%lu)\n",
            (unsigned long)GetLastError());
        goto fail;
    }
    flow_tracker.handle = WinDivertOpen(
        "!loopback and (protocol == 6 or protocol == 17)", WINDIVERT_LAYER_FLOW, 0,
        WINDIVERT_FLAG_SNIFF | WINDIVERT_FLAG_RECV_ONLY
    );
    if (flow_tracker.handle == INVALID_HANDLE_VALUE)
    {
        fprintf(stderr, "Application scope: cannot open FLOW layer (%lu)\n",
            (unsigned long)GetLastError());
        goto fail;
    }
    socket_tracker.thread = CreateThread(NULL, 0, tracker_main, &socket_tracker, 0, NULL);
    flow_tracker.thread = CreateThread(NULL, 0, tracker_main, &flow_tracker, 0, NULL);
    if (!socket_tracker.thread || !flow_tracker.thread) goto fail;
    return true;

fail:
    app_scope_stop();
    return false;
}

void app_scope_stop(void)
{
    InterlockedExchange(&stopping, 1);
    close_tracker(&socket_tracker);
    close_tracker(&flow_tracker);
    if (flow_lock_ready)
    {
        DeleteCriticalSection(&flow_lock);
        flow_lock_ready = false;
    }
    memset(flows, 0, sizeof(flows));
    flow_end = 0;
    for (size_t i = 0; i < app_count; ++i) free(apps[i].path);
    memset(apps, 0, sizeof(apps));
    app_count = 0;
    for (size_t i = 0; i < sizeof(owners) / sizeof(*owners); ++i) free(owners[i].data);
    memset(owners, 0, sizeof(owners));
    unload_ip_helper_api();
}

bool app_scope_healthy(void)
{
    return !InterlockedCompareExchange(&tracker_failed, 0, 0);
}

typedef enum
{
    FLOW_OWNER_UNKNOWN,
    FLOW_OWNER_AMBIGUOUS,
    FLOW_OWNER_UNSELECTED,
    FLOW_OWNER_SELECTED
} flow_owner;

static flow_owner packet_flow_owner(
    const WINDIVERT_ADDRESS *address,
    bool ipv6,
    uint8_t protocol,
    const uint32_t *source_addr,
    const uint32_t *destination_addr,
    uint16_t source_port,
    uint16_t destination_port
)
{
    size_t i;
    const uint32_t *local_addr = address->Outbound ? source_addr : destination_addr;
    const uint32_t *remote_addr = address->Outbound ? destination_addr : source_addr;
    uint16_t local_port = address->Outbound ? source_port : destination_port;
    uint16_t remote_port = address->Outbound ? destination_port : source_port;

    DWORD pid = 0;
    flow_owner owner = FLOW_OWNER_UNKNOWN;
    for (i = 0; i < flow_end; ++i)
    {
        if (flows[i].used && flows[i].ipv6 == ipv6 && flows[i].protocol == protocol &&
            (flows[i].established || address->Timestamp - flows[i].timestamp <= event_max_age) &&
            flows[i].local_port == local_port && flows[i].remote_port == remote_port &&
            !memcmp(flows[i].local_addr, local_addr, sizeof(flows[i].local_addr)) &&
            !memcmp(flows[i].remote_addr, remote_addr, sizeof(flows[i].remote_addr)))
        {
            flow_owner candidate = flows[i].selected ? FLOW_OWNER_SELECTED : FLOW_OWNER_UNSELECTED;
            if (owner != FLOW_OWNER_UNKNOWN &&
                (pid != flows[i].process_id || owner != candidate))
                return FLOW_OWNER_AMBIGUOUS;
            owner = candidate;
            pid = flows[i].process_id;
        }
    }
    return owner;
}

bool app_scope_packet_allowed(
    const void *packet,
    size_t packet_len,
    const WINDIVERT_ADDRESS *address
)
{
    PWINDIVERT_IPHDR ip = NULL;
    PWINDIVERT_IPV6HDR ipv6 = NULL;
    PWINDIVERT_TCPHDR tcp = NULL;
    PWINDIVERT_UDPHDR udp = NULL;
    UINT8 protocol = 0;
    uint16_t source_port, destination_port;
    uint32_t source_addr[4] = {0}, destination_addr[4] = {0};
    flow_owner owner;
    bool native_ipv6;

    if (!flow_lock_ready || !app_scope_healthy() || !packet || !address) return false;
    if (!WinDivertHelperParsePacket(
        packet, (UINT)packet_len, &ip, &ipv6, &protocol,
        NULL, NULL, &tcp, &udp, NULL, NULL, NULL, NULL
    )) return false;
    if (protocol != IPPROTO_TCP && protocol != IPPROTO_UDP) return false;
    if (ipv6)
    {
        uint32_t src_raw[4], dst_raw[4];
        memcpy(src_raw, ipv6->SrcAddr, sizeof(src_raw));
        memcpy(dst_raw, ipv6->DstAddr, sizeof(dst_raw));
        WinDivertHelperNtohIPv6Address(src_raw, source_addr);
        WinDivertHelperNtohIPv6Address(dst_raw, destination_addr);
    }
    else if (ip)
    {
        ipv4_key(ip->SrcAddr, source_addr);
        ipv4_key(ip->DstAddr, destination_addr);
    }
    else return false;
    if (tcp)
    {
        source_port = WinDivertHelperNtohs(tcp->SrcPort);
        destination_port = WinDivertHelperNtohs(tcp->DstPort);
    }
    else if (udp)
    {
        source_port = WinDivertHelperNtohs(udp->SrcPort);
        destination_port = WinDivertHelperNtohs(udp->DstPort);
    }
    else return false;

    native_ipv6 = !address_is_ipv4(source_addr) || !address_is_ipv4(destination_addr);
    EnterCriticalSection(&flow_lock);
    owner = packet_flow_owner(
        address, native_ipv6, protocol, source_addr, destination_addr,
        source_port, destination_port
    );
    /* UDP has no safe owner-table fallback. Give an observed connect/flow
     * event a short chance to arrive before the first outbound datagram. */
    if (owner == FLOW_OWNER_UNKNOWN && udp && address->Outbound && flow_end < APP_SCOPE_MAX_FLOWS)
    {
        SleepConditionVariableCS(&flow_changed, &flow_lock, 2);
        owner = packet_flow_owner(
            address, native_ipv6, protocol, source_addr, destination_addr,
            source_port, destination_port
        );
    }
    LeaveCriticalSection(&flow_lock);

    /* Windows can report a System endpoint as well as the application for
     * the same TCP tuple. Neither event wins: use the TCP owner table to
     * resolve the conflict, or pass through if it cannot identify one PID. */
    if ((owner == FLOW_OWNER_UNKNOWN || owner == FLOW_OWNER_AMBIGUOUS) && tcp)
        owner = tcp_owner_is_selected(native_ipv6,
            address->Outbound ? source_addr : destination_addr,
            address->Outbound ? destination_addr : source_addr,
            address->Outbound ? source_port : destination_port,
            address->Outbound ? destination_port : source_port) ? FLOW_OWNER_SELECTED : FLOW_OWNER_UNSELECTED;

    return owner == FLOW_OWNER_SELECTED;
}

#endif
