class AdaptiveSearchVisual(QWidget):

    gameStateChanged = pyqtSignal(bool, int, bool)  # active, score, collided

    _CORE_RADIUS = 24.0
    _RING_GAP = 2.5
    _RING_WIDTH = 3.2

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Adaptive strategy progress")
        self._progress = 0.0
        self._pulse = 0.0
        self._running = False

        self._game_active = False
        self._game_over = False
        self._game_score = 0
        self._game_lang = "ru"
        self._game_elapsed = 0.0
        self._game_player_offset = 0.0
        self._game_velocity = 0.0
        self._game_player_x = 0.0
        self._player_radius = 48.0
        self._game_spawn_after = 1.15
        self._game_obstacles: list[dict[str, float]] = []
        self._hint_visible = False
        self._space_hint_consumed = False
        logo_path = _bundled_path("flags", "z-green.png")
        self._logo_pixmap = QPixmap(logo_path) if os.path.exists(logo_path) else QPixmap()
        self._game_timer = QTimer(self)
        self._game_timer.setInterval(16)
        self._game_timer.timeout.connect(self._advance_game)

        self._progress_anim = QPropertyAnimation(self, b"progress", self)
        self._progress_anim.setDuration(260)
        self._progress_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._player_x_anim = QPropertyAnimation(self, b"gamePlayerX", self)
        self._player_x_anim.setDuration(280)
        self._player_x_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._player_radius_anim = QPropertyAnimation(self, b"playerRadius", self)
        self._player_radius_anim.setDuration(260)
        self._player_radius_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._pulse_anim = QVariantAnimation(self)
        self._pulse_anim.setDuration(1150)
        self._pulse_anim.setStartValue(0.0)
        self._pulse_anim.setEndValue(1.0)
        self._pulse_anim.setLoopCount(-1)
        self._pulse_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._pulse_anim.valueChanged.connect(self._set_pulse)

        self._space_hint_timer = QTimer(self)
        self._space_hint_timer.setSingleShot(True)
        # The game is intentionally unobtrusive: show the key once per search
        # screen and hide it without changing the layout.
        self._space_hint_timer.setInterval(8_000)
        self._space_hint_timer.timeout.connect(self._hide_space_hint)
        self._space_hint_anim = QVariantAnimation(self)
        self._space_hint_anim.setDuration(1050)
        self._space_hint_anim.setStartValue(0.0)
        self._space_hint_anim.setKeyValueAt(0.25, 1.0)
        self._space_hint_anim.setKeyValueAt(0.50, 0.0)
        self._space_hint_anim.setKeyValueAt(0.75, 1.0)
        self._space_hint_anim.setEndValue(0.0)
        self._space_hint_anim.setLoopCount(-1)
        self._space_hint_anim.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._space_hint_anim.valueChanged.connect(lambda _value: self.update())

    def sizeHint(self) -> QSize:
        return QSize(520, 154)

    def getProgress(self) -> float:
        return float(self._progress)

    def setProgress(self, value: float) -> None:
        self._progress = max(0.0, min(1.0, float(value)))
        self.update()

    progress = pyqtProperty(float, fget=getProgress, fset=setProgress)

    def getGamePlayerX(self) -> float:
        if self._game_player_x <= 0.0:
            return self._normal_center().x()
        return float(self._game_player_x)

    def setGamePlayerX(self, value: float) -> None:
        self._game_player_x = max(0.0, float(value))
        self.update()

    gamePlayerX = pyqtProperty(float, fget=getGamePlayerX, fset=setGamePlayerX)

    def getPlayerRadius(self) -> float:
        return float(self._player_radius)

    def setPlayerRadius(self, value: float) -> None:
        self._player_radius = max(self._CORE_RADIUS, min(52.0, float(value)))
        self.update()

    playerRadius = pyqtProperty(float, fget=getPlayerRadius, fset=setPlayerRadius)

    def animate_to_progress(self, value: float) -> None:
        target = max(self._progress, min(1.0, max(0.0, float(value))))
        self._progress_anim.stop()
        self._progress_anim.setStartValue(self._progress)
        self._progress_anim.setEndValue(target)
        self._progress_anim.start()

    def setLanguage(self, lang: str) -> None:
        self._game_lang = "ru" if lang == "ru" else "en"
        self.update()

    def _set_pulse(self, value) -> None:
        self._pulse = float(value)
        self.update()

    def _normal_center(self) -> QPointF:
        return QPointF(self.width() / 2.0, self.height() / 2.0 + 1.0)

    def _game_player_x_target(self) -> float:
        return max(46.0, min(62.0, self.width() * 0.11))

    def _animate_player_x(self, target: float) -> None:
        self._player_x_anim.stop()
        self._player_x_anim.setStartValue(self.getGamePlayerX())
        self._player_x_anim.setEndValue(float(target))
        self._player_x_anim.start()

    def _animate_player_radius(self, target: float) -> None:
        self._player_radius_anim.stop()
        self._player_radius_anim.setStartValue(self._player_radius)
        self._player_radius_anim.setEndValue(float(target))
        self._player_radius_anim.start()

    def _reset_game(self) -> None:
        self._game_timer.stop()
        self._player_x_anim.stop()
        self._player_radius_anim.stop()
        self._game_active = False
        self._game_over = False
        self._game_score = 0
        self._game_elapsed = 0.0
        self._game_player_offset = 0.0
        self._game_velocity = 0.0
        self._game_player_x = self._normal_center().x()
        self._player_radius = 48.0
        self._game_spawn_after = 1.15
        self._game_obstacles = []
        self._hint_visible = False
        self._space_hint_timer.stop()
        self._space_hint_anim.stop()

    def start(self) -> None:
        self._reset_game()
        if self._running:
            self.update()
            return
        self._running = True
        self._pulse_anim.start()
        if not self._space_hint_consumed:
            self._space_hint_consumed = True
            self._hint_visible = True
            self._space_hint_anim.start()
            self._space_hint_timer.start()
        else:
            self._hint_visible = False
            self._space_hint_anim.stop()
            self._space_hint_timer.stop()
        self.update()

    def stop(self) -> None:
        self._running = False
        self._pulse_anim.stop()
        self._progress_anim.stop()
        self._reset_game()
        self.update()

    def toggle_game(self) -> None:
        if not self._running:
            return
        if self._game_active:
            self._jump()
            return

        self._game_active = True
        self._hint_visible = False
        self._space_hint_timer.stop()
        self._space_hint_anim.stop()
        self._game_over = False
        self._game_score = 0
        self._game_elapsed = 0.0
        self._game_player_offset = 0.0
        self._game_velocity = 0.0
        self._game_player_x = self._normal_center().x()
        self._game_spawn_after = 1.15
        self._game_obstacles = []
        self._animate_player_x(self._game_player_x_target())
        self._animate_player_radius(self._CORE_RADIUS)
        self._game_timer.start()
        self.gameStateChanged.emit(True, 0, False)
        self.update()

    def _jump(self) -> None:
        if self._game_player_offset >= -0.5:
            # About 0.8 s in the air and ~66 px of clearance: every generated obstacle is jumpable.
            self._game_velocity = -330.0

    @staticmethod
    def _circle_hits_rect(center: QPointF, radius: float, rect: QRectF) -> bool:
        closest_x = max(rect.left(), min(center.x(), rect.right()))
        closest_y = max(rect.top(), min(center.y(), rect.bottom()))
        dx = center.x() - closest_x
        dy = center.y() - closest_y
        return dx * dx + dy * dy <= radius * radius

    def _finish_game_after_collision(self) -> None:
        self._game_active = False
        self._game_over = True
        self._game_player_offset = 0.0
        self._game_velocity = 0.0
        self._game_obstacles = []
        self._game_timer.stop()
        self._animate_player_x(self._normal_center().x())
        self._animate_player_radius(48.0)
        self.gameStateChanged.emit(False, self._game_score, True)

    def _advance_game(self) -> None:
        if not self._game_active or not self._running:
            self._game_timer.stop()
            return

        step = 0.016
        self._game_elapsed += step
        self._game_score = int(self._game_elapsed * 10.0)

        self._game_velocity += 820.0 * step
        self._game_player_offset += self._game_velocity * step
        if self._game_player_offset >= 0.0:
            self._game_player_offset = 0.0
            self._game_velocity = 0.0

        self._game_spawn_after -= step
        if self._game_spawn_after <= 0.0:
            variant = (self._game_score * 17 + len(self._game_obstacles) * 11) % 7
            self._game_obstacles.append({
                "x": float(self.width() + 18),
                "width": float(17 + variant),
                "height": float(28 + variant * 1.8),
            })
            # Deliberately leave a long, human-reaction-sized gap after each obstacle.
            self._game_spawn_after = 1.65 + (variant % 4) * 0.16

        speed = 170.0 + min(42.0, self._game_elapsed * 1.4)
        for obstacle in self._game_obstacles:
            obstacle["x"] -= speed * step
        self._game_obstacles = [
            obstacle for obstacle in self._game_obstacles
            if obstacle["x"] + obstacle["width"] > -8.0
        ]

        base_center, ground_y, player_radius = self._game_geometry()
        player_center = QPointF(base_center.x(), base_center.y() + self._game_player_offset)
        for obstacle in self._game_obstacles:
            rect = QRectF(
                obstacle["x"],
                ground_y - obstacle["height"],
                obstacle["width"],
                obstacle["height"],
            )
            if self._circle_hits_rect(player_center, player_radius, rect):
                self._finish_game_after_collision()
                break
        self.update()

    def _game_geometry(self) -> tuple[QPointF, float, float]:
        if not self._game_active:
            center = self._normal_center()
            return center, center.y() + self._CORE_RADIUS, self._CORE_RADIUS * 0.66
        ground_y = max(self._CORE_RADIUS * 2.0 + 18.0, self.height() - 31.0)
        base_center = QPointF(self.getGamePlayerX(), ground_y - self._CORE_RADIUS)
        return base_center, ground_y, self._CORE_RADIUS * 0.66

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self._game_active:
            self._game_player_x = self._normal_center().x()

    def _hide_space_hint(self) -> None:
        self._hint_visible = False
        self._space_hint_anim.stop()
        self.update()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Space:
            self.toggle_game()
            event.accept()
            return
        super().keyPressEvent(event)

    def mousePressEvent(self, event) -> None:
        self.setFocus(Qt.FocusReason.MouseFocusReason)
        super().mousePressEvent(event)

    def _draw_game_layer(self, painter: QPainter, ground_y: float) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        left = 1.0
        right = max(left + 1.0, self.width() - 1.0)
        field = QRectF(left, 23.0, right - left, max(16.0, ground_y - 12.0))
        painter.setPen(QPen(QColor(108, 215, 148, 42), 1.0))
        painter.setBrush(QColor(10, 23, 15, 94))
        painter.drawRoundedRect(field, 12.0, 12.0)

        painter.setPen(QPen(QColor(139, 198, 158, 150), 1.25, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        painter.drawLine(QPointF(left + 8.0, ground_y), QPointF(right - 8.0, ground_y))
        painter.setPen(QPen(QColor(98, 216, 145, 42), 1.0, Qt.PenStyle.DashLine))
        painter.drawLine(QPointF(left + 8.0, ground_y + 6.0), QPointF(right - 8.0, ground_y + 6.0))

        for obstacle in self._game_obstacles:
            rect = QRectF(
                obstacle["x"],
                ground_y - obstacle["height"],
                obstacle["width"],
                obstacle["height"],
            )
            gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
            gradient.setColorAt(0.0, QColor(255, 93, 83, 250))
            gradient.setColorAt(1.0, QColor(135, 24, 42, 250))
            painter.setPen(QPen(QColor(255, 216, 209, 245), 1.2))
            painter.setBrush(QBrush(gradient))
            painter.drawRoundedRect(rect, 3.5, 3.5)
            font = painter.font()
            font.setPixelSize(int(max(8.0, min(11.0, obstacle.get("height", 28.0) * 0.26))))
            font.setWeight(800)
            painter.setFont(font)
            letters = ("Т", "С", "П", "У")
            line_height = rect.height() / len(letters)
            for index, letter in enumerate(letters):
                line = QRectF(rect.left(), rect.top() + index * line_height, rect.width(), line_height)
                painter.setPen(QColor(44, 8, 12, 230))
                painter.drawText(line.translated(0.8, 0.8), Qt.AlignmentFlag.AlignCenter, letter)
                painter.setPen(QColor(255, 248, 242, 255))
                painter.drawText(line, Qt.AlignmentFlag.AlignCenter, letter)
        painter.restore()

    def _player_scale(self) -> tuple[float, float]:
        if not self._game_active or self._game_player_offset >= -0.5:
            return 1.0, 1.0
        travel = min(1.0, abs(self._game_velocity) / 330.0)
        if self._game_velocity < 0.0:
            return 1.0 - 0.045 * travel, 1.0 + 0.085 * travel
        return 1.0 + 0.075 * travel, 1.0 - 0.05 * travel

    def _draw_progress_player(self, painter: QPainter, center: QPointF, scale_x: float, scale_y: float) -> None:
        radius = self._player_radius
        core_x = radius * scale_x
        core_y = radius * scale_y
        ring_x = (radius + self._RING_GAP) * scale_x
        ring_y = (radius + self._RING_GAP) * scale_y
        ring_rect = QRectF(center.x() - ring_x, center.y() - ring_y, ring_x * 2.0, ring_y * 2.0)
        pulse_wave = 1.0 - abs(self._pulse * 2.0 - 1.0)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        if self._progress > 0.0:
            painter.setPen(QPen(QColor(98, 216, 145, int(36 + 32 * pulse_wave)), self._RING_WIDTH + 3.4, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(ring_rect, 90 * 16, int(-360.0 * self._progress * 16))
            painter.setPen(QPen(QColor("#46c976"), self._RING_WIDTH, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawArc(ring_rect, 90 * 16, int(-360.0 * self._progress * 16))

        core_rect = QRectF(center.x() - core_x, center.y() - core_y, core_x * 2.0, core_y * 2.0)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(63, 65, 67, 255))
        painter.drawEllipse(core_rect)

        if not self._logo_pixmap.isNull():
            # Use the original image for each paint instead of an already
            # reduced thumbnail: it stays sharp on HiDPI displays and fills
            # the complete circular core.
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
            painter.drawPixmap(core_rect.toRect(), self._logo_pixmap, self._logo_pixmap.rect())
            painter.restore()
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(98, 216, 145, 205), 1.2))
        painter.drawEllipse(core_rect)

    def focusInEvent(self, event) -> None:
        self.update()
        super().focusInEvent(event)

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        base_center, ground_y, _player_radius = self._game_geometry()
        if self._game_active:
            self._draw_game_layer(painter, ground_y)
            center = QPointF(base_center.x(), base_center.y() + self._game_player_offset)
        else:
            center = self._normal_center()

        scale_x, scale_y = self._player_scale()
        self._draw_progress_player(painter, center, scale_x, scale_y)

        if self._game_active or self._game_over:
            score_font = painter.font()
            score_font.setPixelSize(10)
            score_font.setWeight(700)
            painter.setFont(score_font)
            painter.setPen(QColor(231, 246, 236, 225))
            if self._game_lang == "ru":
                score_text = f"Счёт {self._game_score}" if self._game_active else f"Счёт: {self._game_score}"
            else:
                score_text = f"Score {self._game_score}" if self._game_active else f"Score: {self._game_score}"
            alignment = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter if self._game_active else Qt.AlignmentFlag.AlignCenter
            painter.drawText(QRectF(18.0, 4.0, max(0.0, self.width() - 36.0), 15.0), alignment, score_text)
        elif self._hint_visible:
            press = float(self._space_hint_anim.currentValue() or 0.0)
            hint_alpha = int(120 + 85 * press)
            key_width = 64.0
            key_height = 19.0 - press
            hint_rect = QRectF(
                center.x() - key_width / 2.0,
                center.y() + self._player_radius + 8.0 + press * 1.2,
                key_width,
                key_height,
            )
            painter.setPen(QPen(QColor(98, 216, 145, hint_alpha), 1.0))
            painter.setBrush(QColor(24, 52, 37, 210))
            painter.drawRoundedRect(hint_rect, 5.0, 5.0)
            hint_font = painter.font()
            hint_font.setPixelSize(10)
            hint_font.setWeight(700)
            painter.setFont(hint_font)
            painter.setPen(QColor(224, 246, 232, 245))
            painter.drawText(
                hint_rect,
                Qt.AlignmentFlag.AlignCenter,
                "пробел" if self._game_lang == "ru" else "space",
            )
        painter.end()


class AdaptiveResultCard(QFrame):
    activated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("adaptiveResultCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setFixedHeight(78)
        self.setAccessibleName("Adaptive strategy result")
        self.setStyleSheet("""
            QFrame#adaptiveResultCard {
                background: rgba(45,180,95,20);
                border: 1px solid rgba(88,220,138,90);
                border-radius: 12px;
            }
            QFrame#adaptiveResultCard:hover, QFrame#adaptiveResultCard:focus {
                background: rgba(45,180,95,31);
                border-color: rgba(88,220,138,180);
            }
        """)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(15, 9, 15, 9)
        layout.setSpacing(3)
        self.name_label = QLabel("")
        self.name_label.setStyleSheet("border:none; background:transparent; color:#eaf9ef; font-size:13px; font-weight:700;")
        self.path_label = QLabel("")
        self.path_label.setStyleSheet("border:none; background:transparent; color:rgba(205,219,210,180); font-size:10px;")
        layout.addWidget(self.name_label)
        layout.addWidget(self.path_label)
        for widget in (self.name_label, self.path_label):
            widget.setCursor(Qt.CursorShape.PointingHandCursor)
            widget.installEventFilter(self)

    def set_result_path(self, path: str) -> None:
        result = os.path.abspath(path)
        self.name_label.setText(os.path.basename(result))
        self.path_label.setText(result)
        self.path_label.setToolTip(result)
        self.setToolTip(result)
        self.setAccessibleDescription(result)

    def eventFilter(self, obj, event):
        if obj in (self.name_label, self.path_label) and event.type() == QEvent.Type.MouseButtonDblClick:
            self.activated.emit()
            return True
        return super().eventFilter(obj, event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.activated.emit()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def keyPressEvent(self, event) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_Space):
            self.activated.emit()
            event.accept()
            return
        super().keyPressEvent(event)


class AutoModeCardButton(QPushButton):
    """Animated mode card used by the unified auto-selection window."""

    def __init__(
        self,
        mode: str,
        title: str,
        caption: str,
        tooltip: str,
        parent=None,
    ):
        super().__init__(parent)
        self.mode = str(mode or "legacy")
        self.card_title = title
        self.card_caption = caption
        self._hover_progress = 0.0
        self._glow_phase = 0.0
        logo_path = _bundled_path("flags", "z-green.png")
        self._new_mode_logo = QPixmap(logo_path) if os.path.exists(logo_path) else QPixmap()
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.setMinimumWidth(250)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setToolTip(tooltip)
        self.setAccessibleName(title)
        self.setAccessibleDescription(tooltip)
        self.setStyleSheet("""
            QPushButton {
                border: none;
                background: transparent;
                padding: 0;
                min-height: 230px;
                max-height: 230px;
            }
        """)
        # Apply height after QSS: the global button rule contains its own minimum height.
        self.setMinimumHeight(230)
        self.setMaximumHeight(230)

        self._hover_anim = QPropertyAnimation(self, b"hoverProgress", self)
        self._hover_anim.setDuration(210)
        self._hover_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        self._glow_anim = QVariantAnimation(self)
        self._glow_anim.setDuration(1500)
        self._glow_anim.setStartValue(0.0)
        self._glow_anim.setEndValue(1.0)
        self._glow_anim.setLoopCount(-1)
        self._glow_anim.valueChanged.connect(self._set_glow_phase)

    def getHoverProgress(self) -> float:
        return float(self._hover_progress)

    def setHoverProgress(self, value: float) -> None:
        self._hover_progress = max(0.0, min(1.0, float(value)))
        self.update()

    hoverProgress = pyqtProperty(float, fget=getHoverProgress, fset=setHoverProgress)

    def _set_glow_phase(self, value) -> None:
        try:
            self._glow_phase = float(value)
        except Exception:
            self._glow_phase = 0.0
        self.update()

    def _animate_hover(self, target: float) -> None:
        self._hover_anim.stop()
        self._hover_anim.setStartValue(self._hover_progress)
        self._hover_anim.setEndValue(float(target))
        self._hover_anim.start()

    def enterEvent(self, event) -> None:
        self._animate_hover(1.0)
        if self._glow_anim.state() != QVariantAnimation.State.Running:
            self._glow_anim.start()
        super().enterEvent(event)

    def leaveEvent(self, event) -> None:
        self._animate_hover(0.0)
        self._glow_anim.stop()
        self._glow_phase = 0.0
        self.update()
        super().leaveEvent(event)

    @staticmethod
    def _mix(first: QColor, second: QColor, amount: float) -> QColor:
        t = max(0.0, min(1.0, float(amount)))
        return QColor(
            int(first.red() + (second.red() - first.red()) * t),
            int(first.green() + (second.green() - first.green()) * t),
            int(first.blue() + (second.blue() - first.blue()) * t),
            int(first.alpha() + (second.alpha() - first.alpha()) * t),
        )

    def _draw_mode_icon(self, painter: QPainter, center: QPoint, accent: QColor) -> None:
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(accent, 2.1, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if self.mode == "new":
            if not self._new_mode_logo.isNull():
                diameter = 50
                target = QRectF(
                    center.x() - diameter / 2,
                    center.y() - diameter / 2,
                    diameter,
                    diameter,
                )
                painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
                painter.drawPixmap(target.toRect(), self._new_mode_logo, self._new_mode_logo.rect())
        else:
            for offset, width in ((-8, 18), (0, 13), (8, 16)):
                y = center.y() + offset
                painter.drawLine(center.x() - 8, y, center.x() - 8 + width, y)
                painter.setBrush(accent)
                painter.drawEllipse(QRectF(center.x() - 15, y - 2.1, 4.2, 4.2))
                painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.restore()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)

        hover = float(self._hover_progress)
        pressed = 1.0 if self.isDown() else 0.0
        inset = 2.0 - hover * 0.8
        rect = QRectF(self.rect()).adjusted(inset, inset, -inset, -inset)
        rect.translate(0.0, pressed - hover * 0.8)

        accent = QColor("#62d891" if self.mode == "new" else "#2db45f")
        top = self._mix(QColor(39, 43, 45, 246), QColor(48, 70, 59, 250), hover)
        bottom = self._mix(QColor(18, 21, 22, 248), QColor(19, 42, 30, 250), hover)
        gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
        gradient.setColorAt(0.0, top)
        gradient.setColorAt(0.56, QColor(25, 30, 29, 248))
        gradient.setColorAt(1.0, bottom)

        glow_wave = 0.5 + 0.5 * math.sin(self._glow_phase * math.tau)
        border_alpha = int(66 + 130 * hover + 34 * hover * glow_wave)
        border = QColor(accent)
        border.setAlpha(border_alpha)
        painter.setPen(QPen(border, 1.15 + 0.45 * hover))
        painter.setBrush(QBrush(gradient))
        painter.drawRoundedRect(rect, 15.0, 15.0)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(255, 255, 255, int(12 + 20 * hover)))
        painter.drawRoundedRect(rect.adjusted(4, 4, -4, -rect.height() * 0.62), 11, 11)

        if hover > 0.01:
            sweep_width = rect.width() * 0.28
            sweep_x = rect.left() - sweep_width + (rect.width() + sweep_width * 2) * self._glow_phase
            clip_path = QPainterPath()
            clip_path.addRoundedRect(rect, 15.0, 15.0)
            sweep = QLinearGradient(sweep_x, rect.top(), sweep_x + sweep_width, rect.top())
            sweep.setColorAt(0.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            sweep.setColorAt(0.5, QColor(accent.red(), accent.green(), accent.blue(), int(31 * hover)))
            sweep.setColorAt(1.0, QColor(accent.red(), accent.green(), accent.blue(), 0))
            painter.save()
            painter.setClipPath(clip_path)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QBrush(sweep))
            painter.drawRect(QRectF(sweep_x, rect.top(), sweep_width, rect.height()))
            painter.restore()

        icon_center = QPoint(int(rect.center().x()), int(rect.top() + 62))
        pulse = hover * (1.0 + 0.08 * glow_wave)
        icon_radius = 25.0 + 2.0 * pulse
        painter.setPen(QPen(QColor(accent.red(), accent.green(), accent.blue(), 150 + int(70 * hover)), 1.2))
        painter.setBrush(
            QColor(63, 65, 67, 238)
            if self.mode == "new"
            else QColor(accent.red(), accent.green(), accent.blue(), 24 + int(25 * hover))
        )
        painter.drawEllipse(QRectF(
            icon_center.x() - icon_radius,
            icon_center.y() - icon_radius,
            icon_radius * 2,
            icon_radius * 2,
        ))
        self._draw_mode_icon(painter, icon_center, QColor(151, 246, 187, 245))

        title_rect = QRectF(rect.left() + 12, rect.top() + 98, rect.width() - 24, 28)
        painter.setPen(QColor(246, 250, 247, 252))
        title_font = painter.font()
        title_font.setPixelSize(16)
        title_font.setWeight(700)
        painter.setFont(title_font)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, self.card_title)

        caption_rect = QRectF(rect.left() + 18, rect.top() + 129, rect.width() - 36, rect.height() - 140)
        painter.setPen(QColor(201, 211, 205, 220 + int(22 * hover)))
        caption_font = painter.font()
        caption_font.setPixelSize(11)
        caption_font.setWeight(500)
        painter.setFont(caption_font)
        painter.drawText(
            caption_rect,
            Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop | Qt.TextFlag.TextWordWrap,
            self.card_caption,
        )

        painter.end()


class AutoProgressDialog(StyledDialog):
    """One window for mode selection, progress, naming and results."""

    legacy_requested = pyqtSignal()
    new_requested = pyqtSignal()
    adaptive_save_requested = pyqtSignal(str)
    adaptive_retry_requested = pyqtSignal()
    adaptive_open_folder_requested = pyqtSignal()
    adaptive_canceled = pyqtSignal()
    canceled = pyqtSignal()

    def __init__(
        self,
        title: str,
        left_text: str,
        cancel_text: str,
        lang: str = "ru",
        strategy_dir: str = "",
        parent=None,
    ):
        super().__init__(parent)
        self.lang = "ru" if lang == "ru" else "en"
        self._left_text = left_text
        self._cancel_text = cancel_text
        self._progress_active = False
        self._cancel_emitted = False
        self._page_anim = None
        self._page_effect = None
        self._open_anim = None
        self._active_mode = ""
        self.strategy_dir = Path(strategy_dir or ADAPTIVE_STRATEGY_DIR)
        self._adaptive_default_filename = ""
        self._adaptive_result_path = ""
        self._adaptive_progress_anim = None

        self.setWindowTitle(title)
        self.setWindowModality(Qt.WindowModality.NonModal)

        # Apply the frameless flags before constraining the native window.
        # On Windows, changing from a standard dialog to a frameless one after
        # setFixedSize() makes Qt recalculate the non-client frame during the
        # first show.  The resulting 28 px height mismatch is rejected by the
        # fixed min/max geometry and can leave this modal dialog unresponsive.
        root = _make_window_root_layout(self)
        self.install_title_bar(root, title)
        self.setFixedSize(620, 430)
        content = _make_window_content_layout(root, self, margins=(16, 11, 16, 15), spacing=0)

        self.stack = QStackedWidget(self)
        self.stack.setStyleSheet("QStackedWidget { background: transparent; border: none; }")
        content.addWidget(self.stack, 1)

        self.selection_page = self._build_selection_page()
        self.progress_page = self._build_progress_page()
        self.adaptive_progress_page = self._build_adaptive_progress_page()
        self.adaptive_name_page = self._build_adaptive_name_page()
        self.adaptive_result_page = self._build_adaptive_result_page()
        self.notice_page = self._build_notice_page()
        self.results_page = self._build_results_page()
        for page in (
            self.selection_page,
            self.progress_page,
            self.adaptive_progress_page,
            self.adaptive_name_page,
            self.adaptive_result_page,
            self.notice_page,
            self.results_page,
        ):
            self.stack.addWidget(page)
        self.stack.setCurrentWidget(self.selection_page)

    def _build_selection_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(4, 3, 4, 0)
        layout.setSpacing(10)

        heading = QLabel("Выберите режим автоподбора" if self.lang == "ru" else "Choose an auto-selection mode")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("color:#f5f7f5; font-size:20px; font-weight:750;")
        layout.addWidget(heading)

        subtitle = QLabel(
            "Готовые профили или персональная стратегия с нуля"
            if self.lang == "ru" else
            "Test ready-made profiles or build a personal strategy from scratch"
        )
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subtitle.setStyleSheet("color:rgba(218,225,220,185); font-size:11px;")
        layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.setContentsMargins(0, 3, 0, 0)
        cards.setSpacing(12)
        cards.setAlignment(Qt.AlignmentFlag.AlignVCenter)
        legacy_tip = (
            "Проверяет по очереди все существующие готовые стратегии и выбирает доступную."
            if self.lang == "ru" else
            "Tests every existing ready-made strategy and selects one that works."
        )
        new_tip = (
            "Проверит подключение, подберёт и подтвердит методы обхода для основных сервисов."
            if self.lang == "ru" else
            "Checks your connection and validates bypass methods for the main services."
        )
        self.legacy_mode_btn = AutoModeCardButton(
            "legacy",
            "Перебор стратегий" if self.lang == "ru" else "Strategy scan",
            "Проверка всех готовых профилей" if self.lang == "ru" else "Test every ready-made profile",
            legacy_tip,
            page,
        )
        self.new_mode_btn = AutoModeCardButton(
            "new",
            "Новая стратегия" if self.lang == "ru" else "New strategy",
            "Создание персонального BAT-профиля" if self.lang == "ru" else "Create a personal BAT profile",
            new_tip,
            page,
        )
        self.legacy_mode_btn.clicked.connect(self.legacy_requested.emit)
        self.new_mode_btn.clicked.connect(self._activate_new_mode)
        cards.addWidget(self.legacy_mode_btn, 1)
        cards.addWidget(self.new_mode_btn, 1)
        layout.addLayout(cards, 1)

        self.selection_status = QLabel("")
        self.selection_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.selection_status.setWordWrap(True)
        self.selection_status.setMinimumHeight(34)
        self.selection_status.setStyleSheet("color:rgba(204,216,208,190); font-size:11px;")
        layout.addWidget(self.selection_status)
        return page

    def _build_progress_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(28, 3, 28, 2)
        layout.setSpacing(8)

        heading = QLabel("Перебор стандартных стратегий" if self.lang == "ru" else "Scanning standard strategies")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("color:#f5f7f5; font-size:19px; font-weight:750;")
        layout.addWidget(heading)

        row = QHBoxLayout()
        self.lbl_left = QLabel(self._left_text)
        self.lbl_left.setStyleSheet("color:rgba(232,237,233,220); font-weight:600;")
        self.lbl_right = QLabel("")
        self.lbl_right.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.lbl_right.setStyleSheet("color:rgba(255,255,255,235); font-weight:650;")
        row.addWidget(self.lbl_left, 1)
        row.addWidget(self.lbl_right, 0)
        layout.addLayout(row)

        self.spinner = AdaptiveSearchVisual(page)
        self.spinner.setLanguage(self.lang)
        self.spinner.setFixedHeight(154)
        self.spinner.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        spin_row = QHBoxLayout()
        spin_row.addWidget(self.spinner)
        layout.addLayout(spin_row, 1)

        self.lbl_profile = QLabel("")
        self.lbl_profile.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_profile.setStyleSheet("color:rgba(255,255,255,235); font-size:12px; font-weight:650;")
        shadow = QGraphicsDropShadowEffect(self.lbl_profile)
        shadow.setBlurRadius(10)
        shadow.setOffset(0, 2)
        shadow.setColor(QColor(0, 0, 0, 180))
        self.lbl_profile.setGraphicsEffect(shadow)
        layout.addWidget(self.lbl_profile)

        self.progress_hint = QLabel(
            "Не закрывайте программу до завершения проверки"
            if self.lang == "ru" else
            "Keep the application open until the scan finishes"
        )
        self.progress_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.progress_hint.setStyleSheet("color:rgba(190,201,194,155); font-size:10px;")
        layout.addWidget(self.progress_hint)

        btn_row = QHBoxLayout()
        btn_row.addStretch()
        self.btn_cancel = QPushButton(self._cancel_text)
        self.btn_cancel.setFixedSize(144, 34)
        self.btn_cancel.clicked.connect(self._on_cancel)
        btn_row.addWidget(self.btn_cancel)
        btn_row.addStretch()
        layout.addLayout(btn_row)
        return page

    def _build_adaptive_progress_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(22, 3, 22, 2)
        layout.setSpacing(5)

        heading = QLabel("Создаём новую стратегию" if self.lang == "ru" else "Creating a new strategy")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("color:#f5f7f5; font-size:19px; font-weight:750;")
        layout.addWidget(heading)

        self.adaptive_visual = AdaptiveSearchVisual(page)
        self.adaptive_visual.setLanguage(self.lang)
        self.adaptive_visual.gameStateChanged.connect(self._on_adaptive_game_state_changed)
        self.adaptive_visual.setFixedHeight(154)
        self.adaptive_visual.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout.addWidget(self.adaptive_visual, 1)

        phase_row = QHBoxLayout()
        phase_row.setSpacing(8)
        self.adaptive_phase_label = QLabel("")
        self.adaptive_phase_label.setStyleSheet("color:rgba(237,243,239,235); font-size:12px; font-weight:650;")
        self.adaptive_percent_label = QLabel("0%")
        self.adaptive_percent_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.adaptive_percent_label.setStyleSheet("color:#9af0ba; font-size:12px; font-weight:700;")
        phase_row.addWidget(self.adaptive_phase_label, 1)
        phase_row.addWidget(self.adaptive_percent_label)
        layout.addLayout(phase_row)

        self.adaptive_progress_bar = QProgressBar(page)
        self.adaptive_progress_bar.setRange(0, 1000)
        self.adaptive_progress_bar.setValue(0)
        self.adaptive_progress_bar.setTextVisible(False)
        self.adaptive_progress_bar.setFixedHeight(10)
        self.adaptive_progress_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                border-radius: 5px;
                background: rgba(255,255,255,20);
            }
            QProgressBar::chunk {
                border-radius: 5px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #259f52,stop:1 #62d891);
            }
        """)
        layout.addWidget(self.adaptive_progress_bar)
        self._adaptive_progress_anim = QVariantAnimation(self)
        self._adaptive_progress_anim.setDuration(260)
        self._adaptive_progress_anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._adaptive_progress_anim.valueChanged.connect(
            lambda value: self.adaptive_progress_bar.setValue(int(float(value)))
        )

        details_row = QHBoxLayout()
        self.adaptive_stage_label = QLabel("")
        self.adaptive_stage_label.setStyleSheet("color:rgba(190,201,194,175); font-size:10px;")
        self.adaptive_stage_label.hide()
        self.adaptive_eta_label = QLabel("")
        self.adaptive_eta_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.adaptive_eta_label.setStyleSheet("color:rgba(205,220,210,195); font-size:10px;")
        details_row.addStretch()
        details_row.addWidget(self.adaptive_eta_label)
        layout.addLayout(details_row)

        self.adaptive_hint_label = QLabel(
            "Не закрывайте программу до завершения автоподбора"
            if self.lang == "ru" else
            "Keep the application open until auto-selection finishes"
        )
        self.adaptive_hint_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adaptive_hint_label.setStyleSheet("color:rgba(190,201,194,145); font-size:10px;")
        layout.addWidget(self.adaptive_hint_label)

        cancel_row = QHBoxLayout()
        cancel_row.addStretch()
        self.adaptive_cancel_btn = QPushButton(self._cancel_text)
        self.adaptive_cancel_btn.setFixedSize(144, 34)
        self.adaptive_cancel_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.adaptive_cancel_btn.clicked.connect(self._on_adaptive_cancel)
        cancel_row.addWidget(self.adaptive_cancel_btn)
        cancel_row.addStretch()
        layout.addLayout(cancel_row)
        return page

    def _build_adaptive_name_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(58, 15, 58, 10)
        layout.setSpacing(9)

        icon = QLabel("✓")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(64, 64)
        icon.setStyleSheet("""
            QLabel {
                color:#a5f2c1; background:rgba(45,180,95,32);
                border:1px solid rgba(88,220,138,145); border-radius:32px;
                font-size:29px; font-weight:800;
            }
        """)
        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(icon)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        heading = QLabel("Стратегия найдена" if self.lang == "ru" else "Strategy found")
        heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        heading.setStyleSheet("color:#f5f7f5; font-size:20px; font-weight:750;")
        layout.addWidget(heading)
        description = QLabel(
            "Проверки завершены. Осталось сохранить новый профиль."
            if self.lang == "ru" else
            "Validation is complete. Save the new profile."
        )
        description.setAlignment(Qt.AlignmentFlag.AlignCenter)
        description.setStyleSheet("color:rgba(218,225,220,195); font-size:11px;")
        layout.addWidget(description)

        name_label = QLabel("Название стратегии" if self.lang == "ru" else "Strategy name")
        name_label.setStyleSheet("color:rgba(238,243,239,230); font-size:11px; font-weight:650;")
        layout.addWidget(name_label)
        self.adaptive_name_edit = QLineEdit(page)
        self.adaptive_name_edit.setMaxLength(64)
        self.adaptive_name_edit.setFixedHeight(38)
        self.adaptive_name_edit.setPlaceholderText(
            "Оставьте пустым для автоматического названия"
            if self.lang == "ru" else
            "Leave empty to create a name automatically"
        )
        self.adaptive_name_edit.textChanged.connect(self._validate_adaptive_name)
        self.adaptive_name_edit.returnPressed.connect(self._request_adaptive_save)
        layout.addWidget(self.adaptive_name_edit)

        self.adaptive_name_preview = QLabel("")
        self.adaptive_name_preview.setWordWrap(True)
        self.adaptive_name_preview.setStyleSheet("color:rgba(178,210,188,205); font-size:10px;")
        layout.addWidget(self.adaptive_name_preview)
        self.adaptive_name_error = QLabel("")
        self.adaptive_name_error.setWordWrap(True)
        self.adaptive_name_error.setMinimumHeight(28)
        self.adaptive_name_error.setStyleSheet("color:#ffc1b5; font-size:10px;")
        layout.addWidget(self.adaptive_name_error)
        layout.addStretch()

        buttons = QHBoxLayout()
        self.adaptive_name_back_btn = QPushButton("К выбору режимов" if self.lang == "ru" else "Choose another mode")
        self.adaptive_name_back_btn.setFixedHeight(34)
        self.adaptive_name_back_btn.clicked.connect(self.show_selection)
        self.adaptive_save_btn = QPushButton("Сохранить стратегию" if self.lang == "ru" else "Save strategy")
        self.adaptive_save_btn.setFixedHeight(34)
        self.adaptive_save_btn.clicked.connect(self._request_adaptive_save)
        buttons.addWidget(self.adaptive_name_back_btn)
        buttons.addStretch()
        buttons.addWidget(self.adaptive_save_btn)
        layout.addLayout(buttons)
        return page

    def _build_adaptive_result_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(40, 10, 40, 8)
        layout.setSpacing(7)

        self.adaptive_result_icon = QLabel("")
        self.adaptive_result_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adaptive_result_icon.setFixedSize(72, 72)
        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(self.adaptive_result_icon)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        self.adaptive_result_heading = QLabel("")
        self.adaptive_result_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adaptive_result_heading.setStyleSheet("color:#f5f7f5; font-size:20px; font-weight:750;")
        self.adaptive_result_heading.installEventFilter(self)
        layout.addWidget(self.adaptive_result_heading)
        self.adaptive_result_body = QLabel("")
        self.adaptive_result_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adaptive_result_body.setWordWrap(True)
        self.adaptive_result_body.setStyleSheet("color:rgba(218,225,220,205); font-size:11px;")
        self.adaptive_result_body.installEventFilter(self)
        layout.addWidget(self.adaptive_result_body)

        self.adaptive_result_card = AdaptiveResultCard(page)
        self.adaptive_result_card.activated.connect(self.adaptive_open_folder_requested.emit)
        layout.addWidget(self.adaptive_result_card)

        self.adaptive_error_browser = QTextBrowser(page)
        self.adaptive_error_browser.setOpenExternalLinks(False)
        self.adaptive_error_browser.setFixedHeight(106)
        self.adaptive_error_browser.setStyleSheet("""
            QTextBrowser {
                color:#f1d7d2; background:rgba(25,10,9,95);
                border:1px solid rgba(240,112,96,90); border-radius:10px;
                padding:8px; font-size:10px;
            }
        """)
        layout.addWidget(self.adaptive_error_browser, 1)

        self.adaptive_result_hint = QLabel("")
        self.adaptive_result_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.adaptive_result_hint.setStyleSheet("color:rgba(182,211,192,175); font-size:10px;")
        layout.addWidget(self.adaptive_result_hint)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.adaptive_retry_btn = QPushButton("Повторить подбор" if self.lang == "ru" else "Try again")
        self.adaptive_retry_btn.setFixedHeight(34)
        self.adaptive_retry_btn.clicked.connect(self.adaptive_retry_requested.emit)
        self.adaptive_result_back_btn = QPushButton("К выбору режимов" if self.lang == "ru" else "Choose another mode")
        self.adaptive_result_back_btn.setFixedHeight(34)
        self.adaptive_result_back_btn.clicked.connect(self.show_selection)
        self.adaptive_open_btn = QPushButton("Открыть папку" if self.lang == "ru" else "Open folder")
        self.adaptive_open_btn.setFixedHeight(34)
        self.adaptive_open_btn.clicked.connect(self.adaptive_open_folder_requested.emit)
        self.adaptive_done_btn = QPushButton("Готово" if self.lang == "ru" else "Done")
        self.adaptive_done_btn.setFixedSize(105, 34)
        self.adaptive_done_btn.clicked.connect(self.close)
        for button in (
            self.adaptive_retry_btn,
            self.adaptive_result_back_btn,
            self.adaptive_open_btn,
            self.adaptive_done_btn,
        ):
            buttons.addWidget(button)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _build_notice_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(68, 24, 68, 18)
        layout.setSpacing(12)
        layout.addStretch()

        self.notice_icon = QLabel("A+")
        self.notice_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice_icon.setFixedSize(82, 82)
        self.notice_icon.setStyleSheet("""
            QLabel {
                color: #9af0ba;
                background: rgba(45,180,95,35);
                border: 1px solid rgba(88,220,138,150);
                border-radius: 41px;
                font-size: 25px;
                font-weight: 800;
            }
        """)
        icon_row = QHBoxLayout()
        icon_row.addStretch()
        icon_row.addWidget(self.notice_icon)
        icon_row.addStretch()
        layout.addLayout(icon_row)

        self.notice_heading = QLabel("")
        self.notice_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice_heading.setStyleSheet("color:#f5f7f5; font-size:20px; font-weight:750;")
        layout.addWidget(self.notice_heading)

        self.notice_body = QLabel("")
        self.notice_body.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.notice_body.setWordWrap(True)
        self.notice_body.setStyleSheet("color:rgba(218,225,220,205); font-size:12px; line-height:1.35;")
        layout.addWidget(self.notice_body)
        layout.addStretch()

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.notice_back_btn = QPushButton("Назад к режимам" if self.lang == "ru" else "Back to modes")
        self.notice_back_btn.setFixedSize(170, 35)
        self.notice_back_btn.clicked.connect(self.show_selection)
        buttons.addWidget(self.notice_back_btn)
        buttons.addStretch()
        layout.addLayout(buttons)
        return page

    def _build_results_page(self) -> QWidget:
        page = QWidget(self)
        layout = QVBoxLayout(page)
        layout.setContentsMargins(12, 3, 12, 2)
        layout.setSpacing(8)

        self.results_heading = QLabel("Результаты перебора" if self.lang == "ru" else "Strategy scan results")
        self.results_heading.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.results_heading.setStyleSheet("color:#f5f7f5; font-size:19px; font-weight:750;")
        layout.addWidget(self.results_heading)

        self.results_browser = QTextBrowser(page)
        self.results_browser.setOpenExternalLinks(False)
        self.results_browser.setStyleSheet("""
            QTextBrowser {
                color: #edf2ee;
                background: rgba(10,13,12,125);
                border: 1px solid rgba(91,224,142,75);
                border-radius: 12px;
                padding: 10px;
                selection-background-color: rgba(45,180,95,150);
            }
        """)
        layout.addWidget(self.results_browser, 1)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.results_back_btn = QPushButton("К выбору режимов" if self.lang == "ru" else "Choose another mode")
        self.results_back_btn.setFixedHeight(34)
        self.results_back_btn.clicked.connect(self.show_selection)
        self.results_close_btn = QPushButton("Готово" if self.lang == "ru" else "Done")
        self.results_close_btn.setFixedSize(105, 34)
        self.results_close_btn.clicked.connect(self.close)
        buttons.addWidget(self.results_back_btn)
        buttons.addWidget(self.results_close_btn)
        layout.addLayout(buttons)
        return page

    def _show_page(self, page: QWidget) -> None:
        if self.stack.currentWidget() is page:
            return
        if self._page_anim is not None:
            try:
                self._page_anim.stop()
            except Exception:
                pass
        self.stack.setCurrentWidget(page)
        effect = QGraphicsOpacityEffect(page)
        effect.setOpacity(0.0)
        page.setGraphicsEffect(effect)
        anim = QPropertyAnimation(effect, b"opacity", self)
        anim.setDuration(240)
        anim.setStartValue(0.0)
        anim.setEndValue(1.0)
        anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._page_effect = effect
        self._page_anim = anim

        def _finish_transition() -> None:
            if page.graphicsEffect() is effect:
                page.setGraphicsEffect(None)
            if self._page_anim is anim:
                self._page_anim = None
                self._page_effect = None

        anim.finished.connect(_finish_transition)
        anim.start()

    def show_selection(self, message: str = "", warning: bool = False) -> None:
        if isinstance(message, bool):
            message = ""
        self._progress_active = False
        self._cancel_emitted = False
        self._active_mode = ""
        self.spinner.stop()
        try:
            self.adaptive_visual.stop()
        except Exception:
            pass
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText(self._cancel_text)
        self.adaptive_cancel_btn.setEnabled(True)
        self.adaptive_cancel_btn.setText(self._cancel_text)
        self.set_selection_status(message, warning=warning)
        self._show_page(self.selection_page)

    def set_selection_status(self, text: str, warning: bool = False) -> None:
        color = "rgba(255,163,134,235)" if warning else "rgba(204,216,208,190)"
        self.selection_status.setStyleSheet(f"color:{color}; font-size:11px; font-weight:600;")
        self.selection_status.setText(text or "")

    def _on_adaptive_game_state_changed(self, active: bool, score: int, collided: bool) -> None:
        """Keep the mini-game hidden from the adaptive-search copy."""
        del active, score, collided

    def _activate_new_mode(self) -> None:
        self.new_requested.emit()

    def show_error(self, heading: str, text: str) -> None:
        self._progress_active = False
        self._active_mode = ""
        self.spinner.stop()
        self.notice_icon.setText("!")
        self.notice_icon.setStyleSheet("""
            QLabel {
                color: #ffc1b5;
                background: rgba(218,78,64,34);
                border: 1px solid rgba(240,112,96,155);
                border-radius: 41px;
                font-size: 30px;
                font-weight: 800;
            }
        """)
        self.notice_heading.setText(heading)
        self.notice_body.setText(text)
        self._show_page(self.notice_page)

    def begin_legacy_test(self) -> None:
        self._progress_active = True
        self._cancel_emitted = False
        self._active_mode = "legacy"
        try:
            self.adaptive_visual.stop()
        except Exception:
            pass
        self.lbl_left.setText(self._left_text)
        self.lbl_right.setText("≈ —")
        self.lbl_profile.setText("")
        self.btn_cancel.setEnabled(True)
        self.btn_cancel.setText(self._cancel_text)
        self.set_progress(0, 1)
        self.spinner.start()
        self._show_page(self.progress_page)
        QTimer.singleShot(0, lambda: self.spinner.setFocus(Qt.FocusReason.OtherFocusReason))

    def show_results(self, html: str) -> None:
        self._progress_active = False
        self._active_mode = ""
        self.spinner.stop()
        self.results_browser.setHtml(html or "")
        self.results_browser.moveCursor(self.results_browser.textCursor().MoveOperation.Start)
        self._show_page(self.results_page)

    def closeEvent(self, event) -> None:
        if self._progress_active and not self._cancel_emitted:
            self._cancel_emitted = True
            if self._active_mode == "adaptive":
                self.adaptive_canceled.emit()
            else:
                self.canceled.emit()
        self._progress_active = False
        self._active_mode = ""
        try:
            self.spinner.stop()
        except Exception:
            pass
        try:
            self.adaptive_visual.stop()
        except Exception:
            pass
        super().closeEvent(event)

    def eventFilter(self, obj, event):
        if (
            obj in (getattr(self, "adaptive_result_heading", None), getattr(self, "adaptive_result_body", None))
            and event.type() == QEvent.Type.MouseButtonDblClick
            and bool(self._adaptive_result_path)
        ):
            self.adaptive_open_folder_requested.emit()
            return True
        return super().eventFilter(obj, event)

    def keyPressEvent(self, event) -> None:
        if (
            event.key() == Qt.Key.Key_Space
            and self._active_mode in {"adaptive", "legacy"}
            and self._progress_active
        ):
            visual = self.adaptive_visual if self._active_mode == "adaptive" else self.spinner
            visual.toggle_game()
            event.accept()
            return
        super().keyPressEvent(event)

    def focusInEvent(self, event) -> None:
        super().focusInEvent(event)
        if self._progress_active:
            visual = self.adaptive_visual if self._active_mode == "adaptive" else self.spinner
            QTimer.singleShot(0, lambda v=visual: v.setFocus(Qt.FocusReason.OtherFocusReason))

    def showEvent(self, event) -> None:
        super().showEvent(event)
        try:
            self.setWindowOpacity(0.0)
            anim = QPropertyAnimation(self, b"windowOpacity", self)
            anim.setDuration(220)
            anim.setStartValue(0.0)
            anim.setEndValue(1.0)
            anim.setEasingCurve(QEasingCurve.Type.OutCubic)
            self._open_anim = anim
            anim.start()
        except Exception:
            self.setWindowOpacity(1.0)

    def set_progress(self, cur: int, total: int) -> None:
        total = max(1, int(total))
        cur = max(0, min(int(cur), total))
        frac = float(cur) / float(total)
        self.spinner.animate_to_progress(frac)

    def set_current_profile(self, name: str) -> None:
        prefix = "Профиль" if self.lang == "ru" else "Profile"
        self.lbl_profile.setText(f"{prefix}: {name}" if name else "")

    def _on_cancel(self) -> None:
        if self._active_mode != "legacy" or not self._progress_active or self._cancel_emitted:
            return
        self._cancel_emitted = True
        self.btn_cancel.setEnabled(False)
        self.btn_cancel.setText("Останавливаем..." if self.lang == "ru" else "Stopping...")
        self.canceled.emit()

    def set_eta_text(self, text: str) -> None:
        self.lbl_right.setText(text or "")

    def _adaptive_stage(self, fraction: float) -> tuple[int, str]:
        fraction = max(0.0, min(1.0, float(fraction)))
        if fraction < 0.04:
            return 1, ("Проверяем подключение" if self.lang == "ru" else "Checking connection")
        if fraction < 0.10:
            return 2, ("Проверяем доступность сервисов" if self.lang == "ru" else "Checking service availability")
        if fraction < 0.62:
            return 3, ("Подбираем основные методы" if self.lang == "ru" else "Selecting primary methods")
        if fraction < 0.80:
            return 4, ("Проверяем быстрый трафик" if self.lang == "ru" else "Checking fast traffic")
        return 5, ("Подтверждаем стабильность" if self.lang == "ru" else "Confirming stability")

    def begin_adaptive_test(self) -> None:
        self._progress_active = True
        self._cancel_emitted = False
        self._active_mode = "adaptive"
        self._adaptive_result_path = ""
        try:
            self.spinner.stop()
        except Exception:
            pass
        if self._adaptive_progress_anim is not None:
            self._adaptive_progress_anim.stop()
        self.adaptive_progress_bar.setValue(0)
        self.adaptive_visual.setProgress(0.0)
        self.adaptive_percent_label.setText("0%")
        _stage_number, stage_text = self._adaptive_stage(0.0)
        self.adaptive_phase_label.setText(stage_text)
        self.adaptive_stage_label.setText("")
        self.adaptive_eta_label.setText("≈ —")
        self.adaptive_hint_label.setText(
            "Не закрывайте программу до завершения автоподбора"
            if self.lang == "ru" else
            "Keep the application open until auto-selection finishes"
        )
        self.adaptive_cancel_btn.setEnabled(True)
        self.adaptive_cancel_btn.setText(self._cancel_text)
        self.adaptive_visual.start()
        self._show_page(self.adaptive_progress_page)
        QTimer.singleShot(0, lambda: self.adaptive_visual.setFocus(Qt.FocusReason.OtherFocusReason))

    def set_adaptive_progress(self, fraction: float, raw_label: str = "") -> None:
        fraction = max(0.0, min(1.0, float(fraction)))
        target = int(round(fraction * 1000.0))
        current = int(self.adaptive_progress_bar.value())
        target = max(current, target)
        if self._adaptive_progress_anim is not None:
            self._adaptive_progress_anim.stop()
            self._adaptive_progress_anim.setStartValue(current)
            self._adaptive_progress_anim.setEndValue(target)
            self._adaptive_progress_anim.start()
        else:
            self.adaptive_progress_bar.setValue(target)
        self.adaptive_visual.animate_to_progress(float(target) / 1000.0)
        self.adaptive_percent_label.setText(f"{int(round(target / 10.0))}%")
        _stage_number, stage_text = self._adaptive_stage(float(target) / 1000.0)
        self.adaptive_phase_label.setText(stage_text)
        self.adaptive_stage_label.setText("")
        self.adaptive_stage_label.setToolTip(raw_label or "")

    def set_adaptive_eta_text(self, text: str) -> None:
        self.adaptive_eta_label.setText(text or "")

    def _on_adaptive_cancel(self) -> None:
        if self._active_mode != "adaptive" or not self._progress_active or self._cancel_emitted:
            return
        self._cancel_emitted = True
        self.adaptive_cancel_btn.setEnabled(False)
        self.adaptive_cancel_btn.setText("Останавливаем…" if self.lang == "ru" else "Stopping…")
        self.adaptive_phase_label.setText("Завершаем текущую проверку" if self.lang == "ru" else "Finishing current check")
        self.adaptive_hint_label.setText(
            "Остановка может занять несколько секунд"
            if self.lang == "ru" else
            "Stopping may take a few seconds"
        )
        self.adaptive_canceled.emit()

    def show_adaptive_name(self) -> None:
        self._progress_active = False
        self._active_mode = ""
        self._cancel_emitted = False
        try:
            self.adaptive_visual.stop()
        except Exception:
            pass
        _ok, _error, generated = validate_strategy_name("", now=datetime.now(), lang=self.lang)
        try:
            occupied = {
                item.name.casefold()
                for item in self.strategy_dir.iterdir()
                if item.is_file()
            } if self.strategy_dir.is_dir() else set()
            if generated.casefold() in occupied:
                stem = Path(generated).stem
                index = 2
                while f"{stem}_{index}.bat".casefold() in occupied:
                    index += 1
                generated = f"{stem}_{index}.bat"
        except OSError:
            pass
        self._adaptive_default_filename = generated
        self.adaptive_name_edit.clear()
        self.adaptive_save_btn.setEnabled(True)
        self.adaptive_save_btn.setText("Сохранить стратегию" if self.lang == "ru" else "Save strategy")
        self._validate_adaptive_name()
        self._show_page(self.adaptive_name_page)
        self.adaptive_name_edit.setFocus(Qt.FocusReason.OtherFocusReason)

    def _validate_adaptive_name(self, _text: str = "") -> bool:
        raw = self.adaptive_name_edit.text()
        candidate = raw if raw.strip() else self._adaptive_default_filename
        ok, error, filename = validate_strategy_name(candidate, self.strategy_dir, lang=self.lang)
        if ok:
            prefix = "Будет сохранено:" if self.lang == "ru" else "Will be saved as:"
            self.adaptive_name_preview.setText(f"{prefix}  {filename}")
            self.adaptive_name_error.setText("")
            self.adaptive_name_edit.setStyleSheet(
                "QLineEdit { color:#f5f7f5; background:rgba(255,255,255,7); "
                "border:1px solid rgba(98,216,145,105); border-radius:9px; padding:0 11px; } "
                "QLineEdit:focus { border-color:rgba(98,216,145,210); background:rgba(255,255,255,10); }"
            )
        else:
            self.adaptive_name_preview.setText("")
            self.adaptive_name_error.setText(error)
            self.adaptive_name_edit.setStyleSheet(
                "QLineEdit { color:#ffd7d0; background:rgba(218,78,64,12); "
                "border:1px solid rgba(240,112,96,180); border-radius:9px; padding:0 11px; }"
            )
        self.adaptive_save_btn.setEnabled(ok)
        return ok

    def _request_adaptive_save(self) -> None:
        if not self._validate_adaptive_name():
            return
        raw = self.adaptive_name_edit.text()
        candidate = raw if raw.strip() else self._adaptive_default_filename
        ok, error, filename = validate_strategy_name(candidate, self.strategy_dir, lang=self.lang)
        if not ok:
            self.adaptive_name_error.setText(error)
            return
        self.adaptive_save_btn.setEnabled(False)
        self.adaptive_save_btn.setText("Сохраняем…" if self.lang == "ru" else "Saving…")
        self.adaptive_save_requested.emit(filename)

    def set_adaptive_save_error(self, text: str) -> None:
        self.adaptive_save_btn.setEnabled(True)
        self.adaptive_save_btn.setText("Сохранить стратегию" if self.lang == "ru" else "Save strategy")
        self.adaptive_name_error.setText(text or "")

    def show_adaptive_success(self, strategy_path: str) -> None:
        self._progress_active = False
        self._active_mode = ""
        self._adaptive_result_path = str(strategy_path or "")
        self.adaptive_result_icon.setText("✓")
        self.adaptive_result_icon.setStyleSheet("""
            QLabel {
                color:#a5f2c1; background:rgba(45,180,95,32);
                border:1px solid rgba(88,220,138,145); border-radius:36px;
                font-size:31px; font-weight:800;
            }
        """)
        self.adaptive_result_heading.setText(
            "Стратегия успешно собрана" if self.lang == "ru" else "Strategy created successfully"
        )
        self.adaptive_result_heading.setCursor(Qt.CursorShape.PointingHandCursor)
        self.adaptive_result_body.setText(
            "Новый профиль добавлен в список и готов к использованию."
            if self.lang == "ru" else
            "The new profile is in the list and ready to use."
        )
        self.adaptive_result_body.setCursor(Qt.CursorShape.PointingHandCursor)
        self.adaptive_result_card.set_result_path(strategy_path)
        self.adaptive_result_card.show()
        self.adaptive_error_browser.hide()
        self.adaptive_result_hint.setText(
            "Дважды нажмите на карточку, чтобы открыть папку"
            if self.lang == "ru" else
            "Double-click the card to open its folder"
        )
        self.adaptive_retry_btn.hide()
        self.adaptive_result_back_btn.hide()
        self.adaptive_open_btn.hide()
        self.adaptive_done_btn.show()
        self._show_page(self.adaptive_result_page)

    def show_adaptive_error(self, message: str, details: str = "") -> None:
        self._progress_active = False
        self._active_mode = ""
        self._adaptive_result_path = ""
        try:
            self.adaptive_visual.stop()
        except Exception:
            pass
        self.adaptive_result_icon.setText("!")
        self.adaptive_result_icon.setStyleSheet("""
            QLabel {
                color:#ffc1b5; background:rgba(218,78,64,34);
                border:1px solid rgba(240,112,96,155); border-radius:36px;
                font-size:30px; font-weight:800;
            }
        """)
        self.adaptive_result_heading.setText(
            "Стратегию собрать не удалось" if self.lang == "ru" else "Could not create a strategy"
        )
        self.adaptive_result_heading.unsetCursor()
        self.adaptive_result_body.setText(message or (
            "Проверка завершилась с ошибкой." if self.lang == "ru" else "The check finished with an error."
        ))
        self.adaptive_result_body.unsetCursor()
        self.adaptive_result_card.hide()
        self.adaptive_error_browser.setPlainText(details or message or "")
        self.adaptive_error_browser.moveCursor(self.adaptive_error_browser.textCursor().MoveOperation.Start)
        self.adaptive_error_browser.show()
        self.adaptive_result_hint.setText("")
        self.adaptive_retry_btn.show()
        self.adaptive_result_back_btn.show()
        self.adaptive_open_btn.hide()
        self.adaptive_done_btn.hide()
        self._show_page(self.adaptive_result_page)
