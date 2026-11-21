"""Lazy Windows executable icons, decoded off the GUI thread.

No Shell extensions, directory enumeration, subprocesses or per-row widgets.
Only visible rows request an icon; one worker and a bounded LRU are shared.
QImage crosses threads; QPixmap/QIcon are created on the GUI thread only.
"""
from __future__ import annotations

from collections import OrderedDict
import ctypes
from ctypes import wintypes
import os
import queue
import sys

from PyQt6.QtCore import QObject, QThread, pyqtSignal, Qt
from PyQt6.QtGui import QImage, QIcon, QPixmap
from PyQt6.QtWidgets import QApplication, QStyle


def executable_icon_image(path: str, size: int = 128, icon_index: int = 0) -> QImage:
    if sys.platform != "win32" or not path or path.startswith(("\\\\", "//")):
        return QImage()
    shell = ctypes.WinDLL("shell32", use_last_error=True)
    user = ctypes.WinDLL("user32", use_last_error=True)
    gdi = ctypes.WinDLL("gdi32", use_last_error=True)
    shell.ExtractIconExW.argtypes = [
        wintypes.LPCWSTR, ctypes.c_int, ctypes.POINTER(wintypes.HICON),
        ctypes.POINTER(wintypes.HICON), wintypes.UINT,
    ]
    shell.ExtractIconExW.restype = wintypes.UINT
    user.DestroyIcon.argtypes = [wintypes.HICON]
    user.DrawIconEx.argtypes = [
        wintypes.HDC, ctypes.c_int, ctypes.c_int, wintypes.HICON,
        ctypes.c_int, ctypes.c_int, wintypes.UINT, wintypes.HBRUSH, wintypes.UINT,
    ]
    gdi.CreateCompatibleDC.argtypes = [wintypes.HDC]
    gdi.CreateCompatibleDC.restype = wintypes.HDC
    gdi.CreateDIBSection.argtypes = [
        wintypes.HDC, ctypes.c_void_p, wintypes.UINT,
        ctypes.POINTER(ctypes.c_void_p), wintypes.HANDLE, wintypes.DWORD,
    ]
    gdi.CreateDIBSection.restype = wintypes.HBITMAP
    gdi.SelectObject.argtypes = [wintypes.HDC, wintypes.HANDLE]
    gdi.SelectObject.restype = wintypes.HANDLE
    gdi.DeleteObject.argtypes = [wintypes.HANDLE]
    gdi.DeleteDC.argtypes = [wintypes.HDC]
    large, small = wintypes.HICON(), wintypes.HICON()
    generic = None
    dc = bitmap = previous = None
    try:
        if not shell.ExtractIconExW(path, icon_index, ctypes.byref(large), ctypes.byref(small), 1):
            class SHFILEINFOW(ctypes.Structure):
                _fields_ = [
                    ("hIcon", wintypes.HICON),
                    ("iIcon", ctypes.c_int),
                    ("dwAttributes", wintypes.DWORD),
                    ("szDisplayName", wintypes.WCHAR * 260),
                    ("szTypeName", wintypes.WCHAR * 80),
                ]

            info = SHFILEINFOW()
            shell.SHGetFileInfoW.argtypes = [
                wintypes.LPCWSTR, wintypes.DWORD, ctypes.POINTER(SHFILEINFOW),
                wintypes.UINT, wintypes.UINT,
            ]
            shell.SHGetFileInfoW.restype = ctypes.c_size_t
            # USEFILEATTRIBUTES makes Windows return its generic executable
            # icon even for an unresolved/missing path.
            if not shell.SHGetFileInfoW(
                path or "application.exe",
                0x80,
                ctypes.byref(info),
                ctypes.sizeof(info),
                0x100 | 0x1 | 0x10,
            ) or not info.hIcon:
                return QImage()
            generic = info.hIcon
            large = wintypes.HICON(generic)
        # Ask Windows for a size-specific resource instead of enlarging the
        # fixed 32px ExtractIconEx result on high-DPI monitors.
        user.PrivateExtractIconsW.argtypes = [
            wintypes.LPCWSTR, ctypes.c_int, ctypes.c_int, ctypes.c_int,
            ctypes.POINTER(wintypes.HICON), ctypes.POINTER(wintypes.UINT),
            wintypes.UINT, wintypes.UINT,
        ]
        user.PrivateExtractIconsW.restype = wintypes.UINT
        high_res = wintypes.HICON()
        resource_id = wintypes.UINT()
        if user.PrivateExtractIconsW(path, icon_index, size, size, ctypes.byref(high_res),
                                     ctypes.byref(resource_id), 1, 0) == 1 and high_res:
            if large and large.value != generic:
                user.DestroyIcon(large)
            large = high_res
        icon = large or small
        if not icon:
            return QImage()
        # BITMAPINFOHEADER with a top-down, 32-bit BGRA DIB.
        import struct
        info = ctypes.create_string_buffer(struct.pack(
            "<IiiHHIIiiII", 40, size, -size, 1, 32, 0, size * size * 4, 0, 0, 0, 0,
        ))
        dc = gdi.CreateCompatibleDC(None)
        bits = ctypes.c_void_p()
        bitmap = gdi.CreateDIBSection(dc, info, 0, ctypes.byref(bits), None, 0)
        if not dc or not bitmap or not bits:
            return QImage()
        previous = gdi.SelectObject(dc, bitmap)
        ctypes.memset(bits, 0, size * size * 4)
        if not user.DrawIconEx(dc, 0, 0, icon, size, size, 0, None, 3):
            return QImage()
        data = bytearray(ctypes.string_at(bits, size * size * 4))
        # Legacy icons use a mask instead of alpha. Do not leave them invisible.
        if not any(data[3::4]):
            for offset in range(3, len(data), 4):
                data[offset] = 255
        return QImage(bytes(data), size, size, size * 4, QImage.Format.Format_ARGB32).copy()
    finally:
        if previous:
            gdi.SelectObject(dc, previous)
        if bitmap:
            gdi.DeleteObject(bitmap)
        if dc:
            gdi.DeleteDC(dc)
        if large and large.value != generic:
            user.DestroyIcon(large)
        if small and small.value != large.value and small.value != generic:
            user.DestroyIcon(small)
        if generic:
            user.DestroyIcon(generic)


class _IconWorker(QThread):
    decoded = pyqtSignal(str, QImage)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.requests = queue.Queue(maxsize=128)

    def run(self):
        while not self.isInterruptionRequested():
            try:
                path = self.requests.get(timeout=0.15)
            except queue.Empty:
                continue
            try:
                image = executable_icon_image(path)
            except Exception:
                image = QImage()
            self.decoded.emit(path, image)


class ApplicationIcons(QObject):
    ready = pyqtSignal(str)

    def __init__(self, parent=None, capacity=384):
        super().__init__(parent)
        self.capacity = capacity
        self.cache = OrderedDict()
        self.pending = set()
        fallback_path = os.path.join(
            os.environ.get("WINDIR", r"C:\Windows"),
            "System32",
            "imageres.dll",
        )
        fallback_image = executable_icon_image(fallback_path, 128, icon_index=2)
        self.fallback = (
            QIcon(QPixmap.fromImage(fallback_image))
            if not fallback_image.isNull()
            else QApplication.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon)
        )
        self.worker = _IconWorker(self)
        self.worker.decoded.connect(self._decoded)
        self.worker.start()
        QApplication.instance().aboutToQuit.connect(self.shutdown)

    @staticmethod
    def key(path):
        # No stat/realpath in paint/scroll callbacks.
        return os.path.normcase(os.path.normpath(str(path))) if path else ""

    def icon(self, path):
        key = self.key(path)
        if not key:
            return self.fallback
        if key in self.cache:
            self.cache.move_to_end(key)
            return self.cache[key]
        if key not in self.pending and self.worker is not None and not self.worker.isInterruptionRequested():
            try:
                self.worker.requests.put_nowait(key)
                self.pending.add(key)
            except queue.Full:
                pass
        return self.fallback

    def _decoded(self, path, image):
        self.pending.discard(path)
        icon = QIcon(QPixmap.fromImage(image)) if not image.isNull() else self.fallback
        self.cache[path] = icon
        self.cache.move_to_end(path)
        while len(self.cache) > self.capacity:
            self.cache.popitem(last=False)
        self.ready.emit(path)

    def shutdown(self):
        if self.worker is None:
            return
        self.worker.requestInterruption()
        if self.worker.isRunning():
            self.worker.wait(1500)
        self.worker = None

    def __del__(self):
        try:
            self.shutdown()
        except Exception:
            pass


_icons = None


def application_icons():
    global _icons
    if _icons is None:
        _icons = ApplicationIcons(QApplication.instance())
    return _icons
