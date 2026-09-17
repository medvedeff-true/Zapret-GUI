# --- Reusable controls -------------------------------------------------------

class AnimatedPowerToggleButton(QPushButton):

    def __init__(self, icon_off: QIcon | None = None, icon_on: QIcon | None = None, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setContentsMargins(0, 0, 0, 0)

        self._max_pulse_px = 10
        self._border_w = 2
        self._base_pad = self._max_pulse_px + self._border_w + 2  # чтобы свечение не резалось

        self._progress = 1.0 if self.isChecked() else 0.0
        self._pulse = 0.0

        self._icon_off_pix = None
        self._icon_on_pix = None

        def _icon_to_pix(ic: QIcon | None) -> QPixmap | None:
            if ic is None or ic.isNull():
                return None
            pm = ic.pixmap(512, 512)
            return pm if (pm is not None and not pm.isNull()) else None

        self._icon_off_pix = _icon_to_pix(icon_off)
        self._icon_on_pix = _icon_to_pix(icon_on)

        # текущая иконка
        self._cur_icon_pix = self._icon_on_pix if self.isChecked() else self._icon_off_pix

        self._anim_progress = QPropertyAnimation(self, b"progress", self)
        self._anim_progress.setDuration(220)
        self._anim_progress.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_pulse = QPropertyAnimation(self, b"pulse", self)
        self._anim_pulse.setDuration(1200)
        self._anim_pulse.setStartValue(0.0)
        self._anim_pulse.setEndValue(1.0)
        self._anim_pulse.setLoopCount(-1)
        self._anim_pulse.setEasingCurve(QEasingCurve.Type.InOutSine)

        self._icon_angle = 0.0
        self._icon_scale = 1.0

        self._anim_icon_angle = QPropertyAnimation(self, b"iconAngle", self)
        self._anim_icon_angle.setDuration(420)
        self._anim_icon_angle.setEasingCurve(QEasingCurve.Type.InOutCubic)

        self._anim_icon_scale = QPropertyAnimation(self, b"iconScale", self)
        self._anim_icon_scale.setDuration(420)
        self._anim_icon_scale.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._anim_icon_group = QParallelAnimationGroup(self)
        self._anim_icon_group.addAnimation(self._anim_icon_angle)
        self._anim_icon_group.addAnimation(self._anim_icon_scale)

        self._pending_icon = None
        self._swapped_during_scale = False
        self._anim_icon_scale.valueChanged.connect(self._maybe_swap_icon_on_scale)

        self._anim_icon_group.finished.connect(self._reset_icon_transform)

        self._blink_on = False
        self._blink_color = QColor("#2db45f")
        self._idle_border = QColor(45, 180, 95, 90)

        self.toggled.connect(self._on_toggled)

        if self._anim_pulse.state() != QPropertyAnimation.State.Running:
            self._anim_pulse.start()

        self._on_toggled(self.isChecked())

    def setBlinkOn(self, on: bool):
        self._blink_on = bool(on)
        self.update()

    def setBorderColorHex(self, hex_color: str):
        try:
            c = QColor(hex_color)
            if c.isValid():
                self._blink_color = c
        except Exception:
            pass
        self.update()

    def getProgress(self) -> float:
        return float(self._progress)

    def setProgress(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        if abs(self._progress - v) > 1e-4:
            self._progress = v
            self.update()

    progress = pyqtProperty(float, fget=getProgress, fset=setProgress)

    def getPulse(self) -> float:
        return float(self._pulse)

    def setPulse(self, v: float):
        v = max(0.0, min(1.0, float(v)))
        if abs(self._pulse - v) > 1e-4:
            self._pulse = v
            self.update()

    pulse = pyqtProperty(float, fget=getPulse, fset=setPulse)

    def getIconAngle(self) -> float:
        return float(self._icon_angle)

    def setIconAngle(self, v: float):
        v = float(v)
        if abs(self._icon_angle - v) > 1e-3:
            self._icon_angle = v
            self.update()

    iconAngle = pyqtProperty(float, fget=getIconAngle, fset=setIconAngle)

    def getIconScale(self) -> float:
        return float(self._icon_scale)

    def setIconScale(self, v: float):
        v = max(0.60, min(1.20, float(v)))
        if abs(self._icon_scale - v) > 1e-3:
            self._icon_scale = v
            self.update()

    iconScale = pyqtProperty(float, fget=getIconScale, fset=setIconScale)

    @staticmethod
    def _lerp_color(c1: QColor, c2: QColor, t: float) -> QColor:
        t = max(0.0, min(1.0, float(t)))
        r = int(c1.red()   + (c2.red()   - c1.red())   * t)
        g = int(c1.green() + (c2.green() - c1.green()) * t)
        b = int(c1.blue()  + (c2.blue()  - c1.blue())  * t)
        a = int(c1.alpha() + (c2.alpha() - c1.alpha()) * t)
        return QColor(r, g, b, a)

    def _reset_icon_transform(self):
        self._cur_icon_pix = self._icon_on_pix if self.isChecked() else self._icon_off_pix
        self._icon_angle = 0.0
        self._icon_scale = 1.0
        self._pending_icon = None
        self._swapped_during_scale = False
        self.update()

    def _maybe_swap_icon_on_scale(self, v):
        if self._pending_icon is None or self._swapped_during_scale:
            return
        try:
            vv = float(v)
        except Exception:
            return
        if vv < 0.94:
            self._cur_icon_pix = self._pending_icon
            self._swapped_during_scale = True
            self.update()

    def _start_icon_anim(self, direction: int, pending_icon: QPixmap | None):
        self._anim_icon_group.stop()
        self._pending_icon = pending_icon
        self._swapped_during_scale = False

        self._anim_icon_angle.setStartValue(0.0)
        self._anim_icon_angle.setEndValue(360.0 * float(direction))

        self._anim_icon_scale.setKeyValueAt(0.00, 1.00)
        self._anim_icon_scale.setKeyValueAt(0.78, 1.00)
        self._anim_icon_scale.setKeyValueAt(0.90, 0.86)
        self._anim_icon_scale.setKeyValueAt(1.00, 1.00)

        self._anim_icon_group.start()

    def _on_toggled(self, checked: bool):
        self._anim_progress.stop()
        self._anim_progress.setStartValue(self._progress)
        self._anim_progress.setEndValue(1.0 if checked else 0.0)
        self._anim_progress.start()

        if checked:
            self._start_icon_anim(direction=+1, pending_icon=self._icon_on_pix)
        else:
            self._start_icon_anim(direction=-1, pending_icon=self._icon_off_pix)

        self.update()

    def syncVisualState(self, animated: bool = True):
        checked = self.isChecked()
        if animated:
            self._on_toggled(checked)
            return
        try:
            self._anim_progress.stop()
            self._anim_icon_group.stop()
        except Exception:
            pass
        self._progress = 1.0 if checked else 0.0
        self._cur_icon_pix = self._icon_on_pix if checked else self._icon_off_pix
        self._reset_icon_transform()

    def paintEvent(self, event):
        w = self.width()
        h = self.height()

        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        outer = self.rect().adjusted(self._base_pad, self._base_pad, -self._base_pad, -self._base_pad)

        off_col = QColor(220, 50, 50)
        on_col = QColor(45, 180, 95)

        t = self._progress
        base_col = self._lerp_color(off_col, on_col, t)
        if self.isDown():
            base_col = base_col.darker(116)

        state_ring_col = on_col if self.isChecked() else off_col

        pulse_wave = 1.0 - abs(self._pulse * 2.0 - 1.0)  # 0..1..0
        grow = int(self._max_pulse_px * (0.35 + 0.65 * pulse_wave))
        alpha = int(18 + 90 * pulse_wave)

        ring = QColor(state_ring_col)
        ring.setAlpha(alpha)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(ring)
        p.drawEllipse(outer.adjusted(-grow, -grow, grow, grow))

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(base_col)
        p.drawEllipse(outer)

        inner_pad = max(10, min(w, h) // 11)
        inner = outer.adjusted(inner_pad, inner_pad, -inner_pad, -inner_pad)

        shade = QColor(0, 0, 0, int(52 + 40 * (1.0 - t)))
        if self.isDown():
            shade.setAlpha(min(95, shade.alpha() + 20))

        p.setBrush(shade)
        p.drawEllipse(inner)

        highlight = QColor(255, 255, 255, int(14 + 18 * t))
        p.setBrush(highlight)
        hl = inner.adjusted(-2, -2, -2, -2)
        hl.setHeight(max(6, hl.height() // 2))
        p.drawEllipse(hl)

        pm = self._cur_icon_pix
        if pm is not None and not pm.isNull():
            target = int(min(w, h) * 0.40)

            dpr = float(pm.devicePixelRatio()) if hasattr(pm, "devicePixelRatio") else 1.0
            logical_w = pm.width() / max(1.0, dpr)
            logical_h = pm.height() / max(1.0, dpr)

            scale_to_target = target / max(1.0, float(min(logical_w, logical_h)))

            cx = w / 2.0
            cy = h / 2.0

            p.save()
            p.translate(cx, cy)

            p.rotate(self._icon_angle)
            s = scale_to_target * self._icon_scale
            p.scale(s, s)

            p.translate(-pm.width() / 2.0, -pm.height() / 2.0)
            p.drawPixmap(0, 0, pm)
            p.restore()

        p.end()

class ToggleSwitch(QCheckBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(44, 24)

    def sizeHint(self):
        return QSize(44, 24)

    def hitButton(self, pos):
        return self.rect().contains(pos)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        r = self.rect().adjusted(1, 1, -1, -1)
        radius = r.height() / 2

        if self.isChecked():
            bg = QColor("#2db45f")
            knob_x = r.right() - r.height() + 1
        else:
            bg = QColor(110, 110, 110)
            knob_x = r.left()

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(bg)
        p.drawRoundedRect(r, radius, radius)

        knob_rect = QRectF(knob_x, r.top(), r.height(), r.height()).adjusted(2, 2, -2, -2)
        p.setBrush(QColor("white"))
        p.drawEllipse(knob_rect)

        p.end()


class ModernCheckBox(QCheckBox):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet("QCheckBox { background: transparent; spacing: 0; }")

    def sizeHint(self) -> QSize:
        fm = self.fontMetrics()
        return QSize(24 + fm.horizontalAdvance(self.text()) + 10, max(24, fm.height() + 8))

    def hitButton(self, pos) -> bool:
        return self.rect().contains(pos)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        box_size = 18
        box = QRectF(1, (self.height() - box_size) / 2.0, box_size, box_size)
        checked = self.isChecked()
        hover = self.underMouse()
        enabled = self.isEnabled()

        if checked:
            fill = QLinearGradient(box.topLeft(), box.bottomRight())
            fill.setColorAt(0.0, QColor("#39d879" if enabled else "#5c8f6d"))
            fill.setColorAt(1.0, QColor("#238c4b" if enabled else "#476352"))
            border = QColor(91, 232, 143, 230 if enabled else 120)
        else:
            fill = QLinearGradient(box.topLeft(), box.bottomRight())
            fill.setColorAt(0.0, QColor(255, 255, 255, 22 if enabled else 10))
            fill.setColorAt(1.0, QColor(255, 255, 255, 8 if enabled else 4))
            border = QColor(255, 255, 255, 74 if enabled else 32)

        if hover and enabled and not checked:
            border = QColor(45, 180, 95, 150)

        p.setPen(QPen(border, 1.2))
        p.setBrush(QBrush(fill))
        p.drawRoundedRect(box, 5, 5)

        if checked:
            pen = QPen(QColor(255, 255, 255, 242 if enabled else 150), 2.0)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            p.setPen(pen)
            p.drawLine(QPoint(int(box.left() + 4), int(box.center().y() + 1)), QPoint(int(box.left() + 8), int(box.bottom() - 5)))
            p.drawLine(QPoint(int(box.left() + 8), int(box.bottom() - 5)), QPoint(int(box.right() - 4), int(box.top() + 5)))

        text_rect = QRectF(box.right() + 8, 0, max(0, self.width() - box.right() - 8), self.height())
        p.setPen(QColor(242, 242, 242, 245 if enabled else 120))
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, self.text())
        p.end()


class StableComboPopupView(QListView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setUniformItemSizes(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setAutoFillBackground(True)
        self.viewport().setAutoFillBackground(True)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.viewport().setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, False)
        self.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerItem)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setMouseTracking(True)
        self.verticalScrollBar().valueChanged.connect(lambda _=0: self.viewport().update())

        pal = self.palette()
        pal.setColor(QPalette.ColorRole.Base, QColor("#171717"))
        pal.setColor(QPalette.ColorRole.Window, QColor("#171717"))
        self.setPalette(pal)
        self.viewport().setPalette(pal)

        self.setStyleSheet("""
            QListView {
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: #171717;
                color: #f3f3f3;
                padding: 4px;
                outline: none;
                selection-background-color: rgba(45,180,95,0.34);
                selection-color: #ffffff;
            }
            QListView::item {
                min-height: 26px;
                padding: 5px 8px;
                border-radius: 6px;
                background: transparent;
            }
            QListView::item:hover {
                background: rgba(255,255,255,0.075);
            }
            QListView::item:selected {
                background: rgba(45,180,95,0.34);
            }
        """)

    def paintEvent(self, event) -> None:
        painter = QPainter(self.viewport())
        painter.fillRect(self.viewport().rect(), QColor("#171717"))
        painter.end()
        super().paintEvent(event)

    def scrollContentsBy(self, dx: int, dy: int) -> None:
        super().scrollContentsBy(dx, dy)
        self.viewport().update()


class StableComboBox(QComboBox):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("stableComboBox")
        self._hovered = False
        self._popup_open = False
        self._arrow_progress = 0.0
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self.setAutoFillBackground(False)
        self._arrow_anim = QPropertyAnimation(self, b"arrowProgress", self)
        self._arrow_anim.setDuration(150)
        self._arrow_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setMinimumHeight(31)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        popup_view = StableComboPopupView(self)
        self.setView(popup_view)
        self.setMaxVisibleItems(10)

    def getArrowProgress(self) -> float:
        return float(self._arrow_progress)

    def setArrowProgress(self, value: float) -> None:
        self._arrow_progress = max(0.0, min(1.0, float(value)))
        self.update()

    arrowProgress = pyqtProperty(float, fget=getArrowProgress, fset=setArrowProgress)

    def sizeHint(self) -> QSize:
        hint = super().sizeHint()
        return QSize(max(hint.width(), 120), max(hint.height(), 31))

    def minimumSizeHint(self) -> QSize:
        hint = super().minimumSizeHint()
        return QSize(max(hint.width(), 96), 31)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def _animate_arrow(self, target: float) -> None:
        try:
            self._arrow_anim.stop()
            self._arrow_anim.setStartValue(self._arrow_progress)
            self._arrow_anim.setEndValue(float(target))
            self._arrow_anim.start()
        except Exception:
            self.setArrowProgress(target)

    def showPopup(self) -> None:
        try:
            view = self.view()
            if view is not None:
                popup_width = max(self.width(), self.sizeHint().width())
                view.setMinimumWidth(popup_width)
                view.setMaximumWidth(max(popup_width + 2, popup_width))
        except Exception:
            pass
        self._popup_open = True
        self._animate_arrow(1.0)
        super().showPopup()
        self._fit_popup_window()
        self._shape_popup_window()
        QTimer.singleShot(0, lambda: (self._fit_popup_window(), self._shape_popup_window()))

    def _fit_popup_window(self) -> None:
        try:
            view = self.view()
            popup = view.window()
            visible_rows = max(1, min(int(self.maxVisibleItems()), int(self.count())))
            row_h = view.sizeHintForRow(0)
            if row_h <= 0:
                row_h = 30
            target_h = visible_rows * row_h + 10
            popup.resize(max(popup.width(), self.width()), target_h)
            view.resize(popup.size())
        except Exception:
            pass

    def _shape_popup_window(self) -> None:
        try:
            popup = self.view().window()
            popup.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
            popup.setAutoFillBackground(True)
            popup.setStyleSheet("background: #171717;")
            _update_rounded_window_mask(popup, 8.0)
        except Exception:
            pass

    def hidePopup(self) -> None:
        super().hidePopup()
        self._popup_open = False
        self._animate_arrow(0.0)

    def paintEvent(self, event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)

        rect = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        enabled = self.isEnabled()
        active = self._popup_open or self.hasFocus()
        bg_grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        if active:
            bg_grad.setColorAt(0.00, QColor("#313a35"))
            bg_grad.setColorAt(0.34, QColor("#29312d"))
            bg_grad.setColorAt(0.72, QColor("#1f2523"))
            bg_grad.setColorAt(1.00, QColor(29, 74, 48, 190))
        else:
            bg_grad.setColorAt(0.00, QColor("#252b2b" if self._hovered else "#202424"))
            bg_grad.setColorAt(0.38, QColor("#1d2222"))
            bg_grad.setColorAt(0.74, QColor("#171a1b"))
            bg_grad.setColorAt(1.00, QColor(27, 54, 39, 180 if self._hovered else 150))
        border = QColor("#2db45f" if active else ("#617069" if self._hovered else "#3b4642"))
        text_color = QColor("#f4f4f4" if enabled else "#8f8f8f")

        p.setPen(QPen(border, 1.0))
        p.setBrush(QBrush(bg_grad))
        p.drawRoundedRect(rect, 8, 8)

        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(255, 255, 255, 18 if not active else 26))
        p.drawRoundedRect(rect.adjusted(3, 3, -3, -rect.height() * 0.54), 6, 6)

        text_rect = rect.adjusted(11, 0, -34, 0)
        metrics = self.fontMetrics()
        text = metrics.elidedText(self.currentText(), Qt.TextElideMode.ElideRight, max(12, int(text_rect.width())))
        p.setPen(text_color)
        p.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        arrow_center = rect.center()
        arrow_center.setX(rect.right() - 17)
        p.save()
        p.translate(arrow_center)
        p.rotate(180.0 * self._arrow_progress)
        arrow_pen = QPen(QColor("#ededed" if enabled else "#8f8f8f"), 1.8)
        arrow_pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        arrow_pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        p.setPen(arrow_pen)
        p.drawLine(-5, -2, 0, 3)
        p.drawLine(0, 3, 5, -2)
        p.restore()

        p.end()


PROFILE_ROW_KIND_ROLE = int(Qt.ItemDataRole.UserRole) + 31
PROFILE_ROW_PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 32
PROFILE_ROW_ADD = "add"
PROFILE_ROW_EMPTY = "empty"
PROFILE_ROW_PROFILE = "profile"


class ProfileScopeSwitch(QWidget):
    """A compact, code-drawn profile-source switch with an animated thumb."""

    scopeChanged = pyqtSignal(str)

    def __init__(self, scope: str = "standard", parent=None):
        super().__init__(parent)
        self._scope = "user" if scope == "user" else "standard"
        self._position = 1.0 if self._scope == "user" else 0.0
        self._hovered = False
        self.setFixedSize(74, 26)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setToolTip("Встроенные профили" if self._scope == "standard" else "Пользовательские профили")

        self._animation = QPropertyAnimation(self, b"scopePosition", self)
        self._animation.setDuration(220)
        self._animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def getScopePosition(self) -> float:
        return float(self._position)

    def setScopePosition(self, value: float) -> None:
        self._position = max(0.0, min(1.0, float(value)))
        self.update()

    scopePosition = pyqtProperty(float, fget=getScopePosition, fset=setScopePosition)

    def scope(self) -> str:
        return self._scope

    def setScope(self, scope: str, animated: bool = True, emit: bool = False) -> None:
        scope = "user" if scope == "user" else "standard"
        changed = scope != self._scope
        self._scope = scope
        target = 1.0 if scope == "user" else 0.0
        self.setToolTip("Пользовательские профили" if scope == "user" else "Встроенные профили")
        if animated:
            self._animation.stop()
            self._animation.setStartValue(self._position)
            self._animation.setEndValue(target)
            self._animation.start()
        else:
            self.setScopePosition(target)
        if changed and emit:
            self.scopeChanged.emit(scope)

    def enterEvent(self, event) -> None:
        self._hovered = True
        self.update()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._hovered = False
        self.update()
        super().leaveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            target = "user" if event.position().x() >= self.width() / 2 else "standard"
            self.setScope(target, animated=True, emit=True)
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Space, Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Left, Qt.Key.Key_Right):
            target = "user" if self._scope == "standard" else "standard"
            if event.key() == Qt.Key.Key_Left:
                target = "standard"
            elif event.key() == Qt.Key.Key_Right:
                target = "user"
            self.setScope(target, animated=True, emit=True)
            event.accept()
            return
        super().keyPressEvent(event)

    @staticmethod
    def _draw_list_icon(painter: QPainter, center: QPointF, color: QColor) -> None:
        pen = QPen(color, 1.45)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        for offset in (-4.5, 0.0, 4.5):
            y = center.y() + offset
            painter.drawLine(QPointF(center.x() - 6.0, y), QPointF(center.x() - 4.5, y))
            painter.drawLine(QPointF(center.x() - 1.3, y), QPointF(center.x() + 6.2, y))

    @staticmethod
    def _draw_person_icon(painter: QPainter, center: QPointF, color: QColor) -> None:
        pen = QPen(color, 1.45)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(QRectF(center.x() - 2.7, center.y() - 6.4, 5.4, 5.4))
        path = QPainterPath()
        path.moveTo(center.x() - 6.5, center.y() + 6.1)
        path.cubicTo(center.x() - 5.8, center.y() + 0.9, center.x() + 5.8, center.y() + 0.9, center.x() + 6.5, center.y() + 6.1)
        painter.drawPath(path)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        frame = QRectF(self.rect()).adjusted(0.7, 0.7, -0.7, -0.7)
        hover_alpha = 12 if self._hovered else 0
        painter.setPen(QPen(QColor(86, 103, 95, 190 if self._hovered else 135), 1.0))
        painter.setBrush(QColor(23, 28, 27, 245))
        painter.drawRoundedRect(frame, 12.0, 12.0)

        inner = frame.adjusted(2.0, 2.0, -2.0, -2.0)
        segment_width = inner.width() / 2.0
        thumb = QRectF(inner.left() + segment_width * self._position, inner.top(), segment_width, inner.height())
        thumb_gradient = QLinearGradient(thumb.topLeft(), thumb.bottomRight())
        thumb_gradient.setColorAt(0.0, QColor(43, 177, 93, 230))
        thumb_gradient.setColorAt(1.0, QColor(25, 111, 61, 238))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(thumb_gradient)
        painter.drawRoundedRect(thumb, 9.5, 9.5)

        left_strength = 1.0 - self._position
        right_strength = self._position
        inactive = QColor(174, 184, 179, 166 + hover_alpha)
        left_color = QColor(
            int(inactive.red() * (1.0 - left_strength) + 255 * left_strength),
            int(inactive.green() * (1.0 - left_strength) + 255 * left_strength),
            int(inactive.blue() * (1.0 - left_strength) + 255 * left_strength),
            238,
        )
        right_color = QColor(
            int(inactive.red() * (1.0 - right_strength) + 255 * right_strength),
            int(inactive.green() * (1.0 - right_strength) + 255 * right_strength),
            int(inactive.blue() * (1.0 - right_strength) + 255 * right_strength),
            238,
        )
        self._draw_list_icon(painter, QPointF(inner.left() + segment_width / 2.0, inner.center().y()), left_color)
        self._draw_person_icon(painter, QPointF(inner.right() - segment_width / 2.0, inner.center().y()), right_color)
        painter.end()


class UserProfilePopupDelegate(QStyledItemDelegate):
    """Paints action rows and unobtrusive inline edit/delete controls."""

    def __init__(self, combo, parent=None):
        super().__init__(parent)
        self.combo = combo

    def sizeHint(self, option, index):
        if self.combo.profileMode() == "user":
            return QSize(max(80, option.rect.width()), 34)
        return super().sizeHint(option, index)

    @staticmethod
    def _icon_pen(color: QColor) -> QPen:
        pen = QPen(color, 1.55)
        pen.setCapStyle(Qt.PenCapStyle.RoundCap)
        pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
        return pen

    @staticmethod
    def _draw_plus(painter: QPainter, center: QPointF, color: QColor) -> None:
        painter.setPen(UserProfilePopupDelegate._icon_pen(color))
        painter.drawLine(QPointF(center.x() - 4.0, center.y()), QPointF(center.x() + 4.0, center.y()))
        painter.drawLine(QPointF(center.x(), center.y() - 4.0), QPointF(center.x(), center.y() + 4.0))

    @staticmethod
    def _draw_pencil(painter: QPainter, center: QPointF, color: QColor) -> None:
        """Draw a compact vector edit glyph; avoid the platform emoji font."""
        painter.save()
        painter.translate(center)
        painter.rotate(-45.0)
        painter.setPen(UserProfilePopupDelegate._icon_pen(color))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRoundedRect(QRectF(-2.8, -7.2, 5.6, 11.2), 1.1, 1.1)
        painter.drawLine(QPointF(-2.8, -8.5), QPointF(0.0, -11.4))
        painter.drawLine(QPointF(0.0, -11.4), QPointF(2.8, -8.5))
        painter.restore()
    @staticmethod
    def _draw_cross(painter: QPainter, center: QPointF, color: QColor) -> None:
        painter.setPen(UserProfilePopupDelegate._icon_pen(color))
        painter.drawLine(QPointF(center.x() - 3.6, center.y() - 3.6), QPointF(center.x() + 3.6, center.y() + 3.6))
        painter.drawLine(QPointF(center.x() + 3.6, center.y() - 3.6), QPointF(center.x() - 3.6, center.y() + 3.6))

    def actionAt(self, view: QListView, index, position: QPoint) -> str:
        if self.combo.profileMode() != "user" or not index.isValid():
            return ""
        if str(index.data(PROFILE_ROW_KIND_ROLE) or "") != PROFILE_ROW_PROFILE:
            return ""
        rect = view.visualRect(index)
        if not rect.contains(position):
            return ""
        if position.x() >= rect.right() - 28:
            return "delete"
        if position.x() >= rect.right() - 53:
            return "rename"
        return ""

    def paint(self, painter, option, index) -> None:
        if self.combo.profileMode() != "user":
            super().paint(painter, option, index)
            return

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(option.rect).adjusted(2.0, 1.0, -2.0, -1.0)
        kind = str(index.data(PROFILE_ROW_KIND_ROLE) or PROFILE_ROW_PROFILE)
        selected = bool(option.state & QStyle.StateFlag.State_Selected)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)

        if kind == PROFILE_ROW_ADD:
            fill = QColor(45, 180, 95, 52 if hovered else 34)
            border = QColor(45, 180, 95, 152 if hovered else 102)
            painter.setPen(QPen(border, 1.0))
            painter.setBrush(fill)
            painter.drawRoundedRect(rect, 6.0, 6.0)
            self._draw_plus(painter, QPointF(rect.left() + 16.0, rect.center().y()), QColor("#65d991"))
            painter.setPen(QColor("#dff8e7"))
            painter.drawText(rect.adjusted(30.0, 0.0, -8.0, 0.0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, "Добавить .bat")
            painter.restore()
            return

        if kind == PROFILE_ROW_EMPTY:
            painter.setPen(QColor(184, 191, 187, 188))
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Сгенерируйте или добавьте стратегию")
            painter.restore()
            return

        background = QColor(45, 180, 95, 88) if selected else QColor(255, 255, 255, 15 if hovered else 0)
        if background.alpha() > 0:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(background)
            painter.drawRoundedRect(rect, 6.0, 6.0)

        text_rect = rect.adjusted(9.0, 0.0, -60.0, 0.0)
        profile_name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        text = option.fontMetrics.elidedText(profile_name, Qt.TextElideMode.ElideRight, max(10, int(text_rect.width())))
        painter.setPen(QColor("#f4f4f4"))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, text)

        hover_row, hover_action = self.combo.popupHoverAction()
        is_this_row = hover_row == index.row()
        pencil_color = QColor("#d7e6dd") if is_this_row and hover_action == "rename" else QColor(177, 192, 184, 205)
        delete_color = QColor("#ffb8ae") if is_this_row and hover_action == "delete" else QColor(204, 170, 166, 198)
        self._draw_pencil(painter, QPointF(rect.right() - 42.0, rect.center().y()), pencil_color)
        self._draw_cross(painter, QPointF(rect.right() - 16.0, rect.center().y()), delete_color)
        painter.restore()


class ProfileComboBox(StableComboBox):
    """Profile selector with non-selectable user-profile action rows."""

    addRequested = pyqtSignal()
    renameRequested = pyqtSignal(str, str)
    deleteRequested = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._profile_mode = "standard"
        self._empty_display_text = ""
        self._popup_hover_row = -1
        self._popup_hover_action = ""
        self._profile_delegate = UserProfilePopupDelegate(self, self.view())
        self.view().setItemDelegate(self._profile_delegate)
        self.view().viewport().installEventFilter(self)

    def profileMode(self) -> str:
        return self._profile_mode

    def setProfileMode(self, mode: str) -> None:
        self._profile_mode = "user" if mode == "user" else "standard"
        self._popup_hover_row = -1
        self._popup_hover_action = ""
        self.view().viewport().update()
        self.update()

    def setEmptyDisplayText(self, text: str) -> None:
        self._empty_display_text = str(text or "")
        self.update()

    def popupHoverAction(self) -> tuple[int, str]:
        return self._popup_hover_row, self._popup_hover_action

    def eventFilter(self, watched, event) -> bool:
        if watched is self.view().viewport() and self._profile_mode == "user":
            if event.type() == QEvent.Type.MouseMove:
                index = self.view().indexAt(event.position().toPoint())
                action = self._profile_delegate.actionAt(self.view(), index, event.position().toPoint())
                row = index.row() if index.isValid() and action else -1
                if (row, action) != (self._popup_hover_row, self._popup_hover_action):
                    self._popup_hover_row, self._popup_hover_action = row, action
                    self.view().viewport().update()
            elif event.type() == QEvent.Type.Leave:
                if self._popup_hover_row != -1:
                    self._popup_hover_row, self._popup_hover_action = -1, ""
                    self.view().viewport().update()
            elif event.type() == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
                index = self.view().indexAt(event.position().toPoint())
                if not index.isValid():
                    return False
                kind = str(index.data(PROFILE_ROW_KIND_ROLE) or "")
                if kind == PROFILE_ROW_ADD:
                    self.hidePopup()
                    QTimer.singleShot(0, self.addRequested.emit)
                    return True
                if kind == PROFILE_ROW_EMPTY:
                    return True
                action = self._profile_delegate.actionAt(self.view(), index, event.position().toPoint())
                if action:
                    name = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
                    path = str(index.data(PROFILE_ROW_PATH_ROLE) or "")
                    self.hidePopup()
                    if action == "rename":
                        QTimer.singleShot(0, lambda n=name, p=path: self.renameRequested.emit(n, p))
                    else:
                        QTimer.singleShot(0, lambda n=name, p=path: self.deleteRequested.emit(n, p))
                    return True
        return super().eventFilter(watched, event)

    def paintEvent(self, event) -> None:
        if self.currentIndex() < 0 and self._empty_display_text:
            previous = self._empty_display_text
            self._empty_display_text = ""
            super().paintEvent(event)
            self._empty_display_text = previous
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            rect = QRectF(self.rect()).adjusted(12, 1, -35, -1)
            painter.setPen(QColor(177, 188, 182, 190))
            painter.drawText(rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, previous)
            painter.end()
            return
        super().paintEvent(event)


class AnimatedActionButton(QPushButton):
    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self._hover_progress = 0.0
        self._hover_anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._hover_anim.setDuration(170)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setStyleSheet("QPushButton { border: none; background: transparent; padding: 0; }")

    def getHoverProgress(self) -> float:
        return float(self._hover_progress)

    def setHoverProgress(self, value: float) -> None:
        self._hover_progress = max(0.0, min(1.0, float(value)))
        self.update()

    hoverProgress = pyqtProperty(float, fget=getHoverProgress, fset=setHoverProgress)

    def _animate_hover(self, target: float) -> None:
        try:
            self._hover_anim.stop()
            self._hover_anim.setStartValue(self._hover_progress)
            self._hover_anim.setEndValue(float(target))
            self._hover_anim.start()
        except Exception:
            self.setHoverProgress(target)

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        super().leaveEvent(event)

    def paintEvent(self, event) -> None:
        del event
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        rect = QRectF(self.rect()).adjusted(1.0, 1.0, -1.0, -1.0)
        hover = self._hover_progress
        down = 1.0 if self.isDown() else 0.0
        radius = 9.0

        base_top = QColor(39, 44, 46, 236)
        base_bottom = QColor(20, 23, 24, 242)
        if hover > 0:
            base_top = QColor(
                int(base_top.red() + 18 * hover),
                int(base_top.green() + 26 * hover),
                int(base_top.blue() + 20 * hover),
                base_top.alpha(),
            )
            base_bottom = QColor(
                int(base_bottom.red() + 8 * hover),
                int(base_bottom.green() + 18 * hover),
                int(base_bottom.blue() + 12 * hover),
                base_bottom.alpha(),
            )

        if down:
            rect.translate(0, 1.0)

        grad = QLinearGradient(rect.topLeft(), rect.bottomRight())
        grad.setColorAt(0.00, base_top)
        grad.setColorAt(0.34, QColor(
            int(base_top.red() * 0.62 + 24 * 0.38),
            int(base_top.green() * 0.62 + 28 * 0.38),
            int(base_top.blue() * 0.62 + 28 * 0.38),
            240,
        ))
        grad.setColorAt(0.72, QColor(24, 28, 28, 240))
        grad.setColorAt(1.00, QColor(29, 72, 48, int(118 + 54 * hover)))
        bg = QBrush(grad)

        border = QColor(255, 255, 255, int(34 + 38 * hover))
        if hover > 0:
            border = QColor(45, 180, 95, int(85 + 80 * hover))

        p.setPen(QPen(border, 1.0))
        p.setBrush(bg)
        p.drawRoundedRect(rect, radius, radius)

        shine = QColor(255, 255, 255, int(18 + 30 * hover))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(shine)
        p.drawRoundedRect(rect.adjusted(3, 3, -3, -rect.height() * 0.52), radius - 2, radius - 2)

        if hover > 0:
            sweep = QRectF(rect)
            sweep_w = rect.width() * 0.32
            sweep_x = rect.left() - sweep_w + (rect.width() + sweep_w * 2) * hover
            sweep = QRectF(sweep_x, rect.top(), sweep_w, rect.height())
            p.setBrush(QColor(113, 255, 172, int(18 * hover)))
            p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(sweep, radius, radius)

        text_color = QColor("#f5fff8" if self.isEnabled() else "#8f8f8f")
        p.setPen(text_color)
        font = p.font()
        font.setPixelSize(12)
        font.setWeight(650)
        p.setFont(font)
        p.drawText(rect, Qt.AlignmentFlag.AlignCenter, self.text())
        p.end()


class SegmentedControl(QWidget):
    currentChanged = pyqtSignal(int)
    tabBarClicked = pyqtSignal(int)

    def __init__(self, parent=None, attention_enabled: bool = False):
        super().__init__(parent)
        self._buttons = []
        self._current_index = 0
        self._attention_alpha = 0
        self._mode_activated = True
        self._attention_enabled = bool(attention_enabled)
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 2, 0, 4)
        self._layout.setSpacing(5)
        self.setFixedHeight(38)

    def addTab(self, _widget: QWidget, text: str) -> int:
        index = len(self._buttons)
        btn = QPushButton(text, self)
        btn.setCheckable(True)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        btn.setFixedHeight(32)
        btn.clicked.connect(lambda _checked=False, i=index: self._button_clicked(i))
        self._layout.addWidget(btn, 1)
        self._buttons.append(btn)
        if index == self._current_index:
            btn.setChecked(True)
        self._sync_button_styles()
        return index

    def _button_clicked(self, index: int) -> None:
        if not self.signalsBlocked():
            self.tabBarClicked.emit(index)
        self.setCurrentIndex(index)

    def currentIndex(self) -> int:
        return self._current_index

    def setCurrentIndex(self, index: int) -> None:
        index = int(index)
        if index >= len(self._buttons):
            index = -1
        if index == self._current_index:
            self._sync_button_styles()
            return
        self._current_index = index
        for i, btn in enumerate(self._buttons):
            btn.blockSignals(True)
            btn.setChecked(i == index)
            btn.blockSignals(False)
        self._sync_button_styles()
        if not self.signalsBlocked():
            self.currentChanged.emit(index)

    def set_attention_state(self, alpha: int) -> None:
        self._attention_alpha = max(0, min(255, int(alpha)))
        self._sync_button_styles()

    def clear_attention(self) -> None:
        self._attention_alpha = 0
        self._sync_button_styles()

    def set_mode_activated(self, activated: bool) -> None:
        self._mode_activated = bool(activated)
        self._sync_button_styles()

    def _sync_button_styles(self) -> None:
        for i, btn in enumerate(self._buttons):
            selected = i == self._current_index and self._mode_activated
            alpha = self._attention_alpha if (self._attention_enabled and not self._mode_activated) else 0
            border = f"rgba(45,180,95,{max(70, alpha)})" if alpha > 0 else "rgba(255,255,255,38)"
            bg = "rgba(45,180,95,210)" if selected else "rgba(255,255,255,10)"
            color = "#ffffff" if selected else "#e9e9e9"
            hover_bg = "rgba(45,180,95,54)" if not selected else "rgba(45,180,95,230)"
            btn.setStyleSheet(f"""
                QPushButton {{
                    border: 1px solid {border};
                    border-radius: 9px;
                    background: {bg};
                    color: {color};
                    font-size: 12px;
                    font-weight: 650;
                    padding: 0 10px;
                }}
                QPushButton:hover {{
                    background: {hover_bg};
                    border-color: rgba(45,180,95,165);
                }}
                QPushButton:pressed {{
                    background: rgba(45,180,95,185);
                }}
            """)


class ClickableLabel(QLabel):
    clicked = pyqtSignal()

    def __init__(self, text: str = "", parent=None):
        super().__init__(text, parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()
            event.accept()
            return
        super().mouseReleaseEvent(event)

class SmallCircleButton(QPushButton):
    def __init__(self, text: str = "", icon_kind: str = "text", parent=None):
        super().__init__(text, parent)
        self._visual_active = True
        self._icon_kind = icon_kind or "text"
        self._display_text = text or ""
        self._pixmap = None
        self._pixmap_cache = {}
        self._pixmap_scale = 1.0
        self._pixmap_offset = QPoint(0, 0)
        self._busy = False
        self._busy_phase = 0.0
        self._busy_timer = QTimer(self)
        self._busy_timer.setInterval(28)
        self._busy_timer.timeout.connect(self._advance_busy_indicator)

        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setFlat(True)
        self.setStyleSheet(
            "QPushButton { background: transparent; border: none; padding: 0; }"
        )

    def setVisualActive(self, active: bool) -> None:
        active = bool(active)
        if self._visual_active != active:
            self._visual_active = active
            self.update()

    def setIconKind(self, icon_kind: str) -> None:
        icon_kind = icon_kind or "text"
        if self._icon_kind != icon_kind:
            self._icon_kind = icon_kind
            self.update()

    def setPixmapPath(self, path: str) -> None:
        pm = QPixmap()
        if path and os.path.exists(path):
            image = QImage(path)
            if not image.isNull():
                image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
                pm = QPixmap.fromImage(image)
        if not pm.isNull():
            pm = self._trim_transparent_pixmap(pm)
        self._pixmap = pm if not pm.isNull() else None
        self._pixmap_cache = {}
        self.update()

    def setPixmapTuning(self, scale: float = 1.0, offset_x: int = 0, offset_y: int = 0) -> None:
        self._pixmap_scale = max(0.2, min(1.4, float(scale)))
        self._pixmap_offset = QPoint(int(offset_x), int(offset_y))
        self._pixmap_cache = {}
        self.update()

    def _trim_transparent_pixmap(self, pixmap: QPixmap) -> QPixmap:
        try:
            image = pixmap.toImage()
            if not image.hasAlphaChannel():
                return pixmap
            left = image.width()
            top = image.height()
            right = -1
            bottom = -1
            for y in range(image.height()):
                for x in range(image.width()):
                    if image.pixelColor(x, y).alpha() > 8:
                        left = min(left, x)
                        top = min(top, y)
                        right = max(right, x)
                        bottom = max(bottom, y)
            if right < left or bottom < top:
                return pixmap
            if left <= 1 and top <= 1 and right >= image.width() - 2 and bottom >= image.height() - 2:
                return pixmap
            image = image.copy(left, top, right - left + 1, bottom - top + 1)
            image = image.convertToFormat(QImage.Format.Format_ARGB32_Premultiplied)
            return QPixmap.fromImage(image)
        except Exception:
            return pixmap

    def _scaled_pixmap_for_target(self, width: float, height: float) -> QPixmap:
        if self._pixmap is None or self._pixmap.isNull():
            return QPixmap()

        sample_scale = 2.0
        target_size = QSize(
            max(1, int(round(width * sample_scale))),
            max(1, int(round(height * sample_scale))),
        )
        key = (target_size.width(), target_size.height())
        cached = self._pixmap_cache.get(key)
        if cached is not None and not cached.isNull():
            return cached

        pm = self._pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self._pixmap_cache[key] = pm
        return pm

    def setBusy(self, busy: bool) -> None:
        busy = bool(busy)
        if self._busy == busy:
            return
        self._busy = busy
        if busy:
            self._busy_timer.start()
        else:
            self._busy_timer.stop()
            self._busy_phase = 0.0
        self.update()

    def _advance_busy_indicator(self) -> None:
        self._busy_phase = (self._busy_phase + 7.0) % 360.0
        self.update()

    def setText(self, text: str) -> None:
        self._display_text = text or ""
        super().setText(text)
        self.update()

    def _alpha(self, color: QColor, factor: float) -> QColor:
        c = QColor(color)
        c.setAlpha(max(0, min(255, int(c.alpha() * factor))))
        return c

    def _colors(self) -> tuple[QColor, QColor, QColor]:
        if self._visual_active:
            border = QColor(45, 180, 95, 238)
            fill = QColor(45, 180, 95, 54)
            symbol = QColor(138, 240, 176, 255)
        else:
            border = QColor(120, 120, 120, 232)
            fill = QColor(110, 110, 110, 34)
            symbol = QColor(222, 222, 222, 245)

        if self.isChecked() and self._visual_active:
            fill = QColor(45, 180, 95, 76)
            symbol = QColor(167, 255, 198, 255)

        if self.underMouse():
            fill.setAlpha(min(255, fill.alpha() + 18))

        if self.isDown():
            fill.setAlpha(min(255, fill.alpha() + 28))

        if not self.isEnabled():
            border = self._alpha(border, 0.84)
            fill = self._alpha(fill, 0.90)
            symbol = self._alpha(symbol, 0.88)

        return border, fill, symbol

    def _draw_text_symbol(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        text = self._display_text or self.text() or ""
        if not text:
            return

        painter.setPen(color)
        font = painter.font()
        font.setBold(True)

        size_ratio = 0.46 if len(text) == 1 else 0.38
        if text == "A":
            size_ratio = 0.58
        elif text == "Ai":
            size_ratio = 0.49
        font.setPixelSize(max(9, int(min(rect.width(), rect.height()) * size_ratio)))
        painter.setFont(font)

        text_rect = QRectF(rect)
        if text.lower() == "i":
            text_rect.translate(0, -0.6)
        elif len(text) > 1:
            text_rect.translate(0, -0.2)

        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_gear_symbol(self, painter: QPainter, rect: QRectF, color: QColor, hole_color: QColor) -> None:
        cx = rect.center().x()
        cy = rect.center().y()
        scale = min(rect.width(), rect.height()) / 28.0

        pen = QPen(color, max(1.5, 1.6 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        inner_r = 4.0 * scale
        outer_r = 6.2 * scale
        for i in range(8):
            angle = (math.pi / 4.0) * i
            x1 = cx + math.cos(angle) * inner_r
            y1 = cy + math.sin(angle) * inner_r
            x2 = cx + math.cos(angle) * outer_r
            y2 = cy + math.sin(angle) * outer_r
            painter.drawLine(int(round(x1)), int(round(y1)), int(round(x2)), int(round(y2)))

        gear_rect = QRectF(cx - 3.8 * scale, cy - 3.8 * scale, 7.6 * scale, 7.6 * scale)
        painter.drawEllipse(gear_rect)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(hole_color)
        hole_rect = QRectF(cx - 1.8 * scale, cy - 1.8 * scale, 3.6 * scale, 3.6 * scale)
        painter.drawEllipse(hole_rect)

    def _draw_gamepad_symbol(self, painter: QPainter, rect: QRectF, color: QColor) -> None:
        cx = rect.center().x()
        cy = rect.center().y()
        scale = min(rect.width(), rect.height()) / 28.0

        pen = QPen(color, max(1.45, 1.55 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        body = QRectF(cx - 7.0 * scale, cy - 4.2 * scale, 14.0 * scale, 8.4 * scale)
        painter.drawRoundedRect(body, 3.6 * scale, 3.6 * scale)

        painter.drawLine(
            int(round(cx - 5.0 * scale)),
            int(round(cy)),
            int(round(cx - 2.2 * scale)),
            int(round(cy)),
        )
        painter.drawLine(
            int(round(cx - 3.6 * scale)),
            int(round(cy - 1.4 * scale)),
            int(round(cx - 3.6 * scale)),
            int(round(cy + 1.4 * scale)),
        )

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(color)
        button_r = 1.2 * scale
        painter.drawEllipse(QRectF(cx + 2.1 * scale - button_r, cy - 1.3 * scale - button_r, button_r * 2, button_r * 2))
        painter.drawEllipse(QRectF(cx + 4.8 * scale - button_r, cy + 0.7 * scale - button_r, button_r * 2, button_r * 2))

    def _draw_pixmap_symbol(self, painter: QPainter, rect: QRectF) -> None:
        if self._pixmap is None or self._pixmap.isNull():
            return
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        pad = max(1.5, min(rect.width(), rect.height()) * 0.09)
        box = QRectF(rect).adjusted(pad, pad, -pad, -pad)
        pm_size = self._pixmap.size()
        if pm_size.width() <= 0 or pm_size.height() <= 0:
            return
        scale = min(box.width() / pm_size.width(), box.height() / pm_size.height()) * float(self._pixmap_scale)
        target_w = max(1.0, round(pm_size.width() * scale))
        target_h = max(1.0, round(pm_size.height() * scale))
        target = QRectF(
            round(box.center().x() - target_w / 2.0 + self._pixmap_offset.x()),
            round(box.center().y() - target_h / 2.0 + self._pixmap_offset.y()),
            target_w,
            target_h,
        )
        scaled = self._scaled_pixmap_for_target(target_w, target_h)
        if scaled.isNull():
            return
        painter.save()
        painter.setOpacity(1.0 if self._visual_active else 0.56)
        painter.drawPixmap(target, scaled, QRectF(scaled.rect()))
        painter.restore()

    def _draw_busy_indicator(self, painter: QPainter, rect: QRectF) -> None:
        arc_rect = QRectF(rect).adjusted(1.6, 1.6, -1.6, -1.6)
        start_angle = int((90.0 - self._busy_phase) * 16)

        tail = QColor(78, 231, 137, 118)
        if self._visual_active:
            tail = QColor(153, 255, 190, 118)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(tail, 2.35, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawArc(arc_rect, start_angle, -86 * 16)

    def paintEvent(self, event):
        del event

        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(1.25, 1.25, -1.25, -1.25)
        border, fill, symbol = self._colors()

        painter.setPen(QPen(border, 1.15))
        painter.setBrush(fill)
        painter.drawEllipse(rect)

        highlight = QRectF(
            rect.left() + 3,
            rect.top() + 3,
            max(0.0, rect.width() - 6),
            max(0.0, rect.height() * 0.42),
        )
        if highlight.width() > 0 and highlight.height() > 0:
            gloss = QColor(255, 255, 255, 22 if self._visual_active else 14)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(gloss)
            painter.drawEllipse(highlight)

        hole_color = QColor("#151515")
        hole_color.setAlpha(230)

        if self._icon_kind == "gear":
            self._draw_gear_symbol(painter, rect, symbol, hole_color)
        elif self._icon_kind == "gamepad":
            self._draw_gamepad_symbol(painter, rect, symbol)
        elif self._icon_kind == "pixmap":
            self._draw_pixmap_symbol(painter, rect)
        else:
            self._draw_text_symbol(painter, rect, symbol)

        if self._busy:
            self._draw_busy_indicator(painter, rect)

        painter.end()

class SiteManagerTutorButton(QToolButton):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setToolTip("Обучение по менеджеру сайтов")
        self.setFixedSize(30, 30)
        self.setAutoRaise(True)
        self.setStyleSheet("QToolButton { border: none; background: transparent; }")

        self._pulse = 0.0
        self._pulse_anim = QPropertyAnimation(self, b"pulse", self)
        self._pulse_anim.setDuration(1150)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)

    def start_pulse(self) -> None:
        if self._pulse_anim.state() != QPropertyAnimation.State.Running:
            self._pulse_anim.start()

    def stop_pulse(self) -> None:
        self._pulse_anim.stop()
        self._pulse = 0.0
        self.update()

    def getPulse(self) -> float:
        return float(self._pulse)

    def setPulse(self, value: float) -> None:
        value = max(0.0, min(1.0, float(value)))
        if abs(self._pulse - value) > 1e-4:
            self._pulse = value
            self.update()

    pulse = pyqtProperty(float, fget=getPulse, fset=setPulse)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        rect = QRectF(self.rect()).adjusted(2, 2, -2, -2)
        pulse_wave = 1.0 - abs(self._pulse * 2.0 - 1.0)

        bg = QColor(255, 255, 255, 22 if not self.isDown() else 36)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(bg)
        painter.drawEllipse(rect)

        if self._pulse_anim.state() == QPropertyAnimation.State.Running:
            glow_rect = QRectF(rect).adjusted(1.5, 1.5, -1.5, -1.5)
            glow = QColor("#2db45f")
            glow.setAlpha(int(26 + 78 * pulse_wave))
            painter.setBrush(glow)
            painter.drawEllipse(glow_rect)

            border = QColor("#66d58c")
            border.setAlpha(int(95 + 120 * pulse_wave))
            painter.setPen(QPen(border, 2.2))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(glow_rect.adjusted(0.5, 0.5, -0.5, -0.5))

            inner_glow = QColor(255, 255, 255, int(18 + 34 * pulse_wave))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(inner_glow)
            painter.drawEllipse(QRectF(rect).adjusted(6, 6, -6, -6))

        badge_rect = QRectF(rect).adjusted(5, 5, -5, -5)
        badge_color = QColor("#279f55" if self.isDown() else "#2db45f")
        painter.setPen(QPen(QColor(255, 255, 255, 52), 1.0))
        painter.setBrush(badge_color)
        painter.drawEllipse(badge_rect)

        highlight = QRectF(badge_rect).adjusted(3, 2, -3, -10)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, 36))
        painter.drawEllipse(highlight)

        font = painter.font()
        font.setBold(True)
        font.setPointSizeF(13.5)
        painter.setFont(font)
        painter.setPen(QColor(255, 255, 255, 238))
        painter.drawText(badge_rect.toRect(), Qt.AlignmentFlag.AlignCenter, "i")
        painter.end()

