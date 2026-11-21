#pragma once

#ifdef __CYGWIN__

#include <stdbool.h>
#include <stddef.h>

#include "windows/windivert/windivert.h"

/*
 * Start/stop the process-aware scope tracker.
 *
 * The SOCKET/FLOW handles are sniff-only and therefore never block or modify
 * application sockets. The NETWORK handle remains owned by the normal winws
 * packet loop; app_scope_packet_allowed() only decides whether the existing
 * desync pipeline should see a packet.
 */
bool app_scope_start(const char *paths_file);
bool app_scope_validate(const char *paths_file);
bool app_scope_healthy(void);
void app_scope_stop(void);
bool app_scope_packet_allowed(
    const void *packet,
    size_t packet_len,
    const WINDIVERT_ADDRESS *address
);

#endif
