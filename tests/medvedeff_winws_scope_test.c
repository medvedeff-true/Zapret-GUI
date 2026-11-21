/* Driver-free regression test, compiled with Cygwin and the WinDivert DLL. */
#include "../tools/medvedeff-winws/app_scope.c"
#include <assert.h>

static const uint32_t local[4] = {0xc0000201, 0xffff, 0, 0};
static const uint32_t remote[4] = {0xc6336401, 0xffff, 0, 0};
static const uint16_t local_port = 49152, remote_port = 443;
static const DWORD system_pid = 4;
static DWORD selected_pid, table_pid;
static unsigned int table_reads;

static DWORD WINAPI fake_tcp_table(PVOID buffer, PDWORD size, WINBOOL sort,
    ULONG family, TCP_TABLE_CLASS type, ULONG reserved)
{
    const DWORD needed = sizeof(MIB_TCPTABLE_OWNER_PID);
    assert(!sort && family == AF_INET && type == TCP_TABLE_OWNER_PID_CONNECTIONS && !reserved);
    if (!buffer || *size < needed)
    {
        *size = needed;
        return ERROR_INSUFFICIENT_BUFFER;
    }
    ++table_reads;
    MIB_TCPTABLE_OWNER_PID *table = buffer;
    table->dwNumEntries = table_pid ? 1 : 0;
    table->table[0] = (MIB_TCPROW_OWNER_PID) {
        MIB_TCP_STATE_ESTAB, WinDivertHelperHtonl(local[0]), WinDivertHelperHtons(local_port),
        WinDivertHelperHtonl(remote[0]), WinDivertHelperHtons(remote_port), table_pid
    };
    return NO_ERROR;
}

int main(void)
{
    WCHAR image[MAX_PATH];
    DWORD length = MAX_PATH;
    selected_pid = GetCurrentProcessId();
    assert(QueryFullProcessImageNameW(GetCurrentProcess(), 0, image, &length));
    apps[0].path = malloc((length + 1) * sizeof(*image));
    assert(apps[0].path);
    memcpy(apps[0].path, image, (length + 1) * sizeof(*image));
    app_count = 1;
    InitializeCriticalSection(&flow_lock);
    InitializeConditionVariable(&flow_changed);
    flow_lock_ready = true;
    get_extended_tcp_table = fake_tcp_table;

    const uint8_t tcp_packet[] = {
        0x45, 0, 0, 40, 0, 0, 0, 0, 64, 6, 0, 0, 192, 0, 2, 1, 198, 51, 100, 1,
        0xc0, 0, 0x01, 0xbb, 0, 0, 0, 1, 0, 0, 0, 1, 0x50, 0x18, 0, 0, 0, 0, 0, 0
    };
    const uint8_t udp_packet[] = {
        0x45, 0, 0, 28, 0, 0, 0, 0, 64, 17, 0, 0, 192, 0, 2, 1, 198, 51, 100, 1,
        0xc0, 0, 0x01, 0xbb, 0, 8, 0, 0
    };
    const WINDIVERT_ADDRESS outbound = { .Outbound = 1, .Timestamp = 1 };

    remember_flow_values(IPPROTO_TCP, local, remote, local_port, remote_port, selected_pid, 10, 1, true);
    assert(app_scope_packet_allowed(tcp_packet, sizeof(tcp_packet), &outbound));
    assert(table_reads == 0);

    remember_flow_values(IPPROTO_TCP, local, remote, local_port, remote_port, system_pid, 11, 1, true);
    assert(!app_scope_packet_allowed(tcp_packet, sizeof(tcp_packet), &outbound));
    assert(table_reads == 1);

    /* The new connection can be absent from the cached TCP table. */
    table_pid = selected_pid;
    assert(app_scope_packet_allowed(tcp_packet, sizeof(tcp_packet), &outbound));
    assert(table_reads == 2);

    /* Do not grant the selected PID priority over the real TCP owner. */
    table_pid = system_pid;
    owners[0].valid = false;
    assert(!app_scope_packet_allowed(tcp_packet, sizeof(tcp_packet), &outbound));
    assert(table_reads == 3);

    remember_flow_values(IPPROTO_UDP, local, remote, local_port, remote_port, selected_pid, 12, 1, true);
    assert(app_scope_packet_allowed(udp_packet, sizeof(udp_packet), &outbound));
    remember_flow_values(IPPROTO_UDP, local, remote, local_port, remote_port, system_pid, 13, 1, true);
    assert(!app_scope_packet_allowed(udp_packet, sizeof(udp_packet), &outbound));
    assert(table_reads == 3);

    app_scope_stop();
    puts("application scope regression passed");
    return 0;
}
