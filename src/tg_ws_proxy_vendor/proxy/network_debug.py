import logging
import time
from collections import defaultdict

log = logging.getLogger('tg-mtproto-proxy')


class WsActivity:
    active = set()

    def __init__(self, label, dc):
        self.label, self.dc = label, dc
        self.started = time.monotonic()
        self.native_up = self.ws_up = self.ws_down = self.native_down = 0
        self.first_input = self.first_reply = self.last_rx = self.last_tx = None
        self.awaiting_rx = self.sending = self.writing_native = None
        self.max_rx_gap = self.max_send = self.max_native_write = 0.0
        self.sample = (self.started, 0, 0, 0, 0)
        self.active.add(self)
        log.debug('[%s] WS OPEN %s', self.label, self.dc)

    def input(self, length):
        self.native_up += length
        if self.first_input is None:
            self.first_input = time.monotonic()

    def send_started(self):
        self.sending = time.monotonic()

    def sent(self, length):
        now = time.monotonic()
        self.ws_up += length
        if self.sending is not None:
            self.max_send = max(self.max_send, now - self.sending)
            if self.awaiting_rx is None and (self.last_rx is None or self.last_rx < self.sending):
                self.awaiting_rx = self.sending
        self.last_tx, self.sending = now, None

    def received(self, length):
        now = time.monotonic()
        self.ws_down += length
        self.last_rx = now
        if self.awaiting_rx is not None:
            self.max_rx_gap = max(self.max_rx_gap, now - self.awaiting_rx)
        if self.first_reply is None and self.first_input is not None:
            self.first_reply = now - self.first_input
        self.awaiting_rx = None
        self.writing_native = now

    def delivered(self, length):
        self.native_down += length
        if self.writing_native is not None:
            self.max_native_write = max(self.max_native_write, time.monotonic() - self.writing_native)
        self.writing_native = None

    def summary(self, now):
        current = (now, self.native_up, self.ws_up, self.ws_down, self.native_down)
        previous, self.sample = self.sample, current
        return ('client=%s window_ms=%.0f native_up=%d ws_up=%d ws_down=%d native_down=%d '
                'rx_gap_ms=%.0f last_rx_ms=%.0f ws_write_ms=%.0f native_write_ms=%.0f' % (
                    self.label, (now - previous[0]) * 1000,
                    *(current[index] - previous[index] for index in range(1, 5)),
                    0 if self.awaiting_rx is None else (now - self.awaiting_rx) * 1000,
                    -1 if self.last_rx is None else (now - self.last_rx) * 1000,
                    0 if self.sending is None else (now - self.sending) * 1000,
                    0 if self.writing_native is None else (now - self.writing_native) * 1000))

    def close(self):
        now = time.monotonic()
        self.active.discard(self)
        log.debug('WS END %s %s first_reply_ms=%.0f max_rx_gap_ms=%.0f '
                  'max_ws_write_ms=%.0f max_native_write_ms=%.0f',
                  self.dc, self.summary(now),
                  -1 if self.first_reply is None else self.first_reply * 1000,
                  self.max_rx_gap * 1000, self.max_send * 1000, self.max_native_write * 1000)


def log_ws_flow(now):
    if not log.isEnabledFor(logging.DEBUG):
        return
    groups = defaultdict(list)
    for activity in WsActivity.active:
        groups[activity.dc].append(activity)
    for dc, activities in sorted(groups.items()):
        activities.sort(key=lambda item: item.label)
        for offset in range(0, len(activities), 8):
            log.debug('WS FLOW %s [%s]', dc,
                      '; '.join(item.summary(now) for item in activities[offset:offset + 8]))
