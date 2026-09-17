# --- Shared Qt primitives and base dialogs ----------------------------------

def _was_started_by_autostart(argv: list[str] | None = None) -> bool:
    args = sys.argv[1:] if argv is None else argv
    return any(str(arg).strip().casefold() == AUTOSTART_LAUNCH_ARGUMENT for arg in args)


def _was_started_after_update(argv: list[str] | None = None) -> bool:
    args = sys.argv[1:] if argv is None else argv
    return any(str(arg).strip().casefold() == "--post-update" for arg in args)


def _should_start_minimized(start_minimized_enabled: bool, launched_by_autostart: bool) -> bool:
    """The setting applies only to the Task Scheduler launch, never a manual one."""
    return bool(start_minimized_enabled and launched_by_autostart)


def _build_autostart_task_command(
    executable: str | None = None,
    script: str | None = None,
    app_dir: str | None = None,
    frozen: bool | None = None,
) -> str:
    """Build the exact Task Scheduler command for a system-start launch."""
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else bool(frozen)
    app_path = os.path.abspath(app_dir or APP_DIR)
    if is_frozen:
        parts = [os.path.realpath(executable or sys.executable)]
    else:
        interpreter = Path(executable or sys.executable)
        windowless = interpreter.with_name("pythonw.exe")
        parts = [
            os.path.realpath(windowless if windowless.is_file() else interpreter),
            os.path.abspath(script or sys.argv[0]),
        ]
    parts.extend([f"--app-dir={app_path}", AUTOSTART_LAUNCH_ARGUMENT])
    return subprocess.list2cmdline(parts)

def _ensure_no_update_input(lines: int = 12) -> str:
    try:
        if not os.path.exists(NOUPDATE_INP):
            with open(NOUPDATE_INP, "w", encoding="ascii", newline="\n") as f:
                for _ in range(lines):
                    f.write("n\n")
    except Exception:
        pass
    return NOUPDATE_INP

def _patch_bat_inplace_remove_updates(bat_path: str) -> bool:
    try:
        if not os.path.exists(bat_path):
            return False

        with open(bat_path, "rb") as f:
            raw = f.read()

        enc = "utf-8"
        bom = b""
        if raw.startswith(b"\xff\xfe"):
            enc = "utf-16le"; bom = b"\xff\xfe"
        elif raw.startswith(b"\xfe\xff"):
            enc = "utf-16be"; bom = b"\xfe\xff"
        elif raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8"; bom = b"\xef\xbb\xbf"
        else:
            try:
                raw.decode("utf-8")
                enc = "utf-8"
            except Exception:
                enc = "cp1251"

        text = raw[len(bom):].decode(enc, errors="replace")
        lines = text.splitlines()

        new_lines = []
        changed = False

        for ln in lines:
            s = ln.strip().lower()
            if "service.bat" in s and "check_updates" in s:
                if s.startswith("call ") or s.startswith("service.bat") or '"service.bat"' in s or "%~dp0" in s:
                    changed = True
                    continue
            new_lines.append(ln)

        stripped = []
        i = 0
        while i < len(new_lines):
            s = new_lines[i].strip().lower()
            if s.startswith("net session") and "||" in s and "(" in s:
                j = i + 1
                found_runas = False
                while j < len(new_lines) and j < i + 12:
                    sj = new_lines[j].strip().lower()
                    if "-verb runas" in sj or "start-process" in sj:
                        found_runas = True
                    if sj == ")":
                        break
                    j += 1
                if found_runas and j < len(new_lines) and new_lines[j].strip() == ")":
                    changed = True
                    i = j + 1
                    continue
            stripped.append(new_lines[i])
            i += 1

        if not stripped:
            return False

        out_text = "\r\n".join(stripped) + "\r\n"
        out_raw = bom + out_text.encode(enc, errors="replace")

        if out_raw == raw:
            return False

        with open(bat_path, "wb") as f:
            f.write(out_raw)

        return changed
    except Exception:
        return False

def _patch_bat_inplace_hide_windows(bat_path: str) -> bool:
    try:
        if not os.path.exists(bat_path):
            return False

        with open(bat_path, "rb") as f:
            raw = f.read()

        enc = "utf-8"
        bom = b""
        if raw.startswith(b"\xff\xfe"):
            enc = "utf-16le"; bom = b"\xff\xfe"
        elif raw.startswith(b"\xfe\xff"):
            enc = "utf-16be"; bom = b"\xfe\xff"
        elif raw.startswith(b"\xef\xbb\xbf"):
            enc = "utf-8"; bom = b"\xef\xbb\xbf"
        else:
            try:
                raw.decode("utf-8")
                enc = "utf-8"
            except Exception:
                enc = "cp1251"

        text = raw[len(bom):].decode(enc, errors="replace")
        lines = text.splitlines()

        changed = False
        out_lines = []

        for ln in lines:
            if re.match(r"(?i)^\s*start\b", ln):
                low = ln.lower()
                if re.search(r"(?i)(\s)/b(\s|$)", ln) is None:
                    new_ln = re.sub(r"(?i)(\s)/min(\s|$)", r"\1/b\2", ln, count=1)
                    if new_ln != ln:
                        ln = new_ln
                        changed = True

            out_lines.append(ln)

        if not changed:
            return False

        out_text = "\r\n".join(out_lines) + "\r\n"
        out_raw = bom + out_text.encode(enc, errors="replace")

        if out_raw == raw:
            return False

        with open(bat_path, "wb") as f:
            f.write(out_raw)

        return True
    except Exception:
        return False

def _patch_profiles_hide_windows(core_dir: str) -> None:
    try:
        if not os.path.isdir(core_dir):
            return
        for fn in os.listdir(core_dir):
            low = fn.lower()
            if not low.endswith(".bat"):
                continue
            if low.startswith("__noupdate__"):
                continue
            if low in ("service.bat", "cloudflare_switch.bat"):
                continue
            _patch_bat_inplace_hide_windows(os.path.join(core_dir, fn))
    except Exception:
        pass


def _read_text(path: str) -> str:
    try:
        with open(path, "rb") as f:
            data = f.read()
    except FileNotFoundError:
        return ""
    except Exception:
        return ""

    for enc in ("utf-8", "cp1251", "utf-16"):
        try:
            return data.decode(enc).strip()
        except Exception:
            pass
    return data.decode("utf-8", errors="replace").strip()

def _theme_text_color_hex(w: QWidget) -> str:
    c = w.palette().color(QPalette.ColorRole.Text)
    return c.name()


def _apply_unified_qt_style(app: QApplication) -> None:
    try:
        app.setStyle("Fusion")
    except Exception:
        pass

    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#171717"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#111111"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#1c1c1c"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#1f1f1f"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#f2f2f2"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#202020"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#f7f7f7"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#2db45f"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(190, 190, 190, 180))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#989898"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#a1a1a1"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.WindowText, QColor("#a1a1a1"))
    try:
        app.setPalette(palette)
    except Exception:
        pass


def _available_geometry_for_widget(widget: QWidget | None = None):
    try:
        screen = widget.screen() if widget is not None and hasattr(widget, "screen") else None
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        if screen is not None:
            return screen.availableGeometry()
    except Exception:
        pass
    return None


def _center_widget_on_screen(widget: QWidget, parent: QWidget | None = None) -> None:
    try:
        geom = _available_geometry_for_widget(parent if parent is not None else widget)
        if geom is None:
            return
        frame = widget.frameGeometry()
        frame.moveCenter(geom.center())
        widget.move(frame.topLeft())
    except Exception:
        pass


def _show_centered_message(
    parent: QWidget | None,
    icon: QMessageBox.Icon,
    title: str,
    text: str,
    buttons: QMessageBox.StandardButton = QMessageBox.StandardButton.Ok,
) -> QMessageBox.StandardButton:
    msg = QMessageBox(parent)
    msg.setWindowTitle(title)
    msg.setText(text)
    msg.setIcon(icon)
    msg.setStandardButtons(buttons)
    msg.adjustSize()
    _center_widget_on_screen(msg, parent)
    return msg.exec()


WINDOW_RADIUS = 12.0


def _rounded_window_path(rect: QRectF, radius: float = WINDOW_RADIUS) -> QPainterPath:
    path = QPainterPath()
    path.addRoundedRect(rect.adjusted(0.5, 0.5, -0.5, -0.5), radius, radius)
    return path


def _update_rounded_window_mask(widget: QWidget, radius: float = WINDOW_RADIUS) -> None:
    try:
        if widget.width() <= 0 or widget.height() <= 0:
            return
        path = _rounded_window_path(QRectF(widget.rect()), radius)
        widget.setMask(QRegion(path.toFillPolygon().toPolygon()))
    except Exception:
        pass


def _make_window_root_layout(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    return layout


def _make_window_content_layout(
    root_layout: QVBoxLayout,
    parent: QWidget,
    margins: tuple[int, int, int, int] = (12, 12, 12, 12),
    spacing: int = 8,
) -> QVBoxLayout:
    content = QWidget(parent)
    content.setObjectName("windowContent")
    content.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
    layout = QVBoxLayout(content)
    layout.setContentsMargins(*margins)
    layout.setSpacing(spacing)
    root_layout.addWidget(content, 1)
    return layout


def _paint_app_surface(painter: QPainter, rect: QRectF, accented: bool = False) -> None:
    path = _rounded_window_path(rect)
    bg = QLinearGradient(rect.topLeft(), rect.bottomRight())
    bg.setColorAt(0.00, QColor("#191b1b"))
    bg.setColorAt(0.46, QColor("#111313"))
    bg.setColorAt(1.00, QColor("#0c0e0e"))

    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    painter.setClipPath(path)
    painter.fillPath(path, QBrush(bg))

    stripe_alpha = 15 if accented else 10
    stripe_step = 34 if accented else 42
    painter.setPen(QPen(QColor(255, 255, 255, stripe_alpha), 1.0))
    for x in range(-int(rect.height()), int(rect.width() + rect.height()), stripe_step):
        painter.drawLine(QPoint(x, int(rect.height())), QPoint(x + int(rect.height()), 0))

    painter.setPen(QPen(QColor(45, 180, 95, 22 if accented else 14), 1.0))
    for x in range(-int(rect.height()) + stripe_step // 2, int(rect.width() + rect.height()), stripe_step * 3):
        painter.drawLine(QPoint(x, int(rect.height())), QPoint(x + int(rect.height()), 0))

    edge = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.top())
    edge.setColorAt(0.0, QColor(45, 180, 95, 0))
    edge.setColorAt(0.5, QColor(45, 180, 95, 34 if accented else 22))
    edge.setColorAt(1.0, QColor(45, 180, 95, 0))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.setBrush(QBrush(edge))
    painter.drawRect(QRectF(rect.left(), rect.top(), rect.width(), 1.2))

    painter.setPen(QPen(QColor(255, 255, 255, 24 if accented else 18), 1.0))
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawPath(path)
    painter.restore()


def _app_dialog_stylesheet() -> str:
    return """
        QDialog {
            color: #f2f2f2;
            background: transparent;
        }
        QLabel {
            color: #f2f2f2;
        }
        QCheckBox {
            color: #f1f1f1;
            spacing: 7px;
        }
        QPushButton {
            min-height: 30px;
            border: 1px solid rgba(255,255,255,0.14);
            border-radius: 8px;
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(44,50,50,235),
                stop:0.36 rgba(34,40,40,238),
                stop:0.72 rgba(24,30,29,238),
                stop:1 rgba(26,49,36,235));
            color: #f6fff8;
            font-weight: 600;
            padding: 0 10px;
        }
        QPushButton:hover {
            border-color: rgba(45,180,95,0.72);
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(54,64,61,240),
                stop:0.38 rgba(40,49,46,240),
                stop:0.74 rgba(29,39,35,240),
                stop:1 rgba(33,79,51,238));
        }
        QPushButton:pressed {
            background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                stop:0 rgba(28,35,33,245),
                stop:1 rgba(38,96,58,242));
        }
        QPushButton:disabled {
            color: #929292;
            border-color: rgba(255,255,255,0.08);
            background: rgba(255,255,255,0.035);
        }
        QToolButton {
            color: #f3f3f3;
        }
        QLineEdit, QTextBrowser, QListWidget {
            color: #f2f2f2;
            background: rgba(255,255,255,0.026);
            border: 1px solid rgba(255,255,255,0.12);
            border-radius: 8px;
        }
    """


class CustomTitleBar(QWidget):
    def __init__(self, title: str = "", parent=None, allow_minimize: bool = True):
        super().__init__(parent)
        self._window = parent
        self._drag_pos = None
        self.setFixedHeight(30)
        self.setObjectName("customTitleBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(11, 0, 4, 0)
        layout.setSpacing(5)

        icon_lbl = QLabel(self)
        icon_lbl.setFixedSize(16, 16)
        icon_path = os.path.join(APP_DIR, "flags", "Z.ico")
        if not os.path.exists(icon_path):
            icon_path = _bundled_path("flags", "Z.ico")
        pm = QIcon(icon_path).pixmap(16, 16) if os.path.exists(icon_path) else QPixmap()
        icon_lbl.setPixmap(pm)
        layout.addWidget(icon_lbl, 0, Qt.AlignmentFlag.AlignVCenter)

        self.title_lbl = QLabel(title, self)
        self.title_lbl.setObjectName("customTitleText")
        self.title_lbl.setAlignment(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.title_lbl, 1)

        self.min_btn = QPushButton("–", self)
        self.close_btn = QPushButton("×", self)
        for btn in (self.min_btn, self.close_btn):
            btn.setFixedSize(28, 28)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            btn.setObjectName("titleButton")

        self.close_btn.setObjectName("titleCloseButton")
        self.min_btn.clicked.connect(lambda: self.window().showMinimized())
        self.close_btn.clicked.connect(self._request_window_close)
        self.min_btn.setVisible(bool(allow_minimize))
        layout.addWidget(self.min_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(self.close_btn, 0, Qt.AlignmentFlag.AlignVCenter)

        self.setStyleSheet("""
            QWidget#customTitleBar {
                background: transparent;
                border-bottom: 1px solid rgba(255,255,255,0.07);
            }
            QLabel#customTitleText {
                color: rgba(245,245,245,0.96);
                font-size: 12px;
                font-weight: 650;
            }
            QPushButton#titleButton, QPushButton#titleCloseButton {
                border: none;
                border-radius: 6px;
                background: transparent;
                color: rgba(245,245,245,0.92);
                font-size: 15px;
                font-weight: 700;
                padding: 0;
                min-height: 0;
            }
            QPushButton#titleButton:hover {
                border-color: rgba(45,180,95,0.55);
                background: rgba(45,180,95,0.14);
            }
            QPushButton#titleCloseButton:hover {
                border-color: rgba(226,84,84,0.66);
                background: rgba(226,84,84,0.20);
            }
            QPushButton#titleCloseButton[attention="true"] {
                border: 1px solid rgba(255,92,92,0.95);
                background: rgba(226,84,84,0.36);
                color: #ffffff;
            }
            QPushButton#titleButton:pressed, QPushButton#titleCloseButton:pressed {
                background: rgba(255,255,255,0.12);
            }
        """)

    def setTitle(self, title: str) -> None:
        self.title_lbl.setText(title or "")

    def _request_window_close(self) -> None:
        window = self.window()
        if hasattr(window, "_request_manual_close"):
            window._request_manual_close()
        else:
            window.close()

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = event.globalPosition().toPoint() - self.window().frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_pos is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.window().move(event.globalPosition().toPoint() - self._drag_pos)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_pos = None
        super().mouseReleaseEvent(event)


class StyledDialog(QDialog):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, False)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setStyleSheet(_app_dialog_stylesheet())
        self._title_bar = None
        self._attention_flash_on = False
        self._attention_flash_timer = None
        self._attention_flash_steps = 0

    def setWindowTitle(self, title: str) -> None:
        super().setWindowTitle(title)
        if getattr(self, "_title_bar", None) is not None:
            self._title_bar.setTitle(title)

    def install_title_bar(self, layout: QVBoxLayout, title: str | None = None, allow_minimize: bool = False) -> CustomTitleBar:
        self.setWindowFlags(
            (self.windowFlags() | Qt.WindowType.FramelessWindowHint)
            & ~Qt.WindowType.WindowTitleHint
        )
        if title is not None:
            self.setWindowTitle(title)
        if self._title_bar is None:
            self._title_bar = CustomTitleBar(self.windowTitle(), self, allow_minimize=allow_minimize)
            layout.insertWidget(0, self._title_bar)
        else:
            self._title_bar.setTitle(self.windowTitle())
        return self._title_bar

    def _set_attention_flash(self, active: bool) -> None:
        self._attention_flash_on = bool(active)
        title_bar = getattr(self, "_title_bar", None)
        close_btn = getattr(title_bar, "close_btn", None)
        if close_btn is not None:
            try:
                close_btn.setProperty("attention", bool(active))
                close_btn.style().unpolish(close_btn)
                close_btn.style().polish(close_btn)
                close_btn.update()
            except Exception:
                pass
        self.update()

    def flash_attention(self) -> None:
        if self._attention_flash_timer is not None:
            try:
                self._attention_flash_timer.stop()
            except Exception:
                pass
        self._attention_flash_steps = 0
        self._set_attention_flash(True)
        timer = QTimer(self)
        timer.setInterval(120)
        self._attention_flash_timer = timer

        def _tick() -> None:
            self._attention_flash_steps += 1
            self._set_attention_flash(self._attention_flash_steps % 2 == 0)
            if self._attention_flash_steps >= 7:
                timer.stop()
                self._set_attention_flash(False)
                try:
                    timer.deleteLater()
                except Exception:
                    pass
                if self._attention_flash_timer is timer:
                    self._attention_flash_timer = None

        timer.timeout.connect(_tick)
        timer.start()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        _paint_app_surface(painter, QRectF(self.rect()), accented=False)
        if self._attention_flash_on:
            painter.setPen(QPen(QColor(255, 82, 82, 235), 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPath(_rounded_window_path(QRectF(self.rect()).adjusted(1.5, 1.5, -1.5, -1.5)))
        painter.end()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        _update_rounded_window_mask(self)


class TextInputDialog(StyledDialog):
    def __init__(
        self,
        title: str,
        label: str,
        ok_text: str = "OK",
        cancel_text: str = "Cancel",
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(330, 150)

        root = _make_window_root_layout(self)
        self.install_title_bar(root, title, allow_minimize=False)
        layout = _make_window_content_layout(root, self, margins=(10, 8, 10, 10), spacing=7)

        self.label = QLabel(label, self)
        self.label.setWordWrap(False)
        layout.addWidget(self.label)

        self.line_edit = QLineEdit(self)
        self.line_edit.setMinimumHeight(30)
        self.line_edit.setStyleSheet("""
            QLineEdit {
                padding: 0 10px;
                border-radius: 8px;
                border: 1px solid rgba(255,255,255,0.13);
                background: rgba(255,255,255,0.045);
                color: #f5f5f5;
                selection-background-color: rgba(45,180,95,0.55);
            }
            QLineEdit:focus {
                border-color: rgba(45,180,95,0.72);
                background: rgba(255,255,255,0.060);
            }
        """)
        self.line_edit.returnPressed.connect(self.accept)
        layout.addWidget(self.line_edit)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.cancel_btn = QPushButton(cancel_text, self)
        self.ok_btn = QPushButton(ok_text, self)
        self.cancel_btn.setFixedHeight(28)
        self.ok_btn.setFixedHeight(28)
        self.cancel_btn.clicked.connect(self.reject)
        self.ok_btn.clicked.connect(self.accept)
        btn_row.addWidget(self.cancel_btn)
        btn_row.addWidget(self.ok_btn)
        layout.addLayout(btn_row)

    def setTextValue(self, text: str) -> None:
        self.line_edit.setText(text or "")
        self.line_edit.selectAll()

    def textValue(self) -> str:
        return self.line_edit.text()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        QTimer.singleShot(0, self.line_edit.setFocus)

