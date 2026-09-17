# --- Site and game list management dialogs ----------------------------------

class SiteManagerTutorialDialog(StyledDialog):
    def __init__(self, parent=None, lang="ru"):
        super().__init__(parent)
        self.lang = lang

        self.setWindowTitle("Обучение: Менеджер сайтов" if lang == "ru" else "Guide: Site manager")
        self.setFixedSize(430, 530)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        self.setStyleSheet(_app_dialog_stylesheet() + """
            QLabel#Title {
                color: white;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#Subtitle {
                color: rgba(220,220,220,0.92);
                font-size: 12px;
            }
            QTextBrowser {
                border: 1px solid rgba(255,255,255,0.08);
                border-radius: 12px;
                background: rgba(255,255,255,0.03);
                padding: 6px;
            }
            QCheckBox {
                color: white;
                spacing: 8px;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 14px;
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(54,64,61,240),
                    stop:0.52 rgba(28,35,33,240),
                    stop:1 rgba(33,79,51,238));
                color: #f6fff8;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: rgba(45,180,95,0.72);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(62,74,70,242),
                    stop:0.52 rgba(34,44,40,242),
                    stop:1 rgba(42,104,63,240));
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(28,35,33,245),
                    stop:1 rgba(38,96,58,242));
            }
        """)

        frame = _make_window_root_layout(self)
        self.install_title_bar(frame, self.windowTitle())
        root = _make_window_content_layout(frame, self, margins=(14, 12, 14, 14), spacing=10)

        title = QLabel("Как пользоваться Менеджером сайтов" if lang == "ru" else "How to use Site Manager")
        title.setObjectName("Title")
        root.addWidget(title)

        subtitle = QLabel(
            "Короткое обучение по вкладкам, кнопкам и спискам."
            if lang == "ru" else
            "A quick walkthrough of tabs, buttons, and list actions."
        )
        subtitle.setObjectName("Subtitle")
        subtitle.setWordWrap(True)
        root.addWidget(subtitle)

        browser = QTextBrowser(self)
        browser.setOpenExternalLinks(False)
        browser.setHtml(self._build_html())
        root.addWidget(browser, 1)

        bottom = QHBoxLayout()
        bottom.setSpacing(10)

        self.dont_show_cb = ModernCheckBox(
            "Больше не показывать"
            if lang == "ru" else
            "Don't show again"
        )
        self.dont_show_cb.setChecked(True)
        bottom.addWidget(self.dont_show_cb, 1)

        close_btn = QPushButton("Понятно" if lang == "ru" else "Got it")
        close_btn.clicked.connect(self.close)
        bottom.addWidget(close_btn, 0)
        root.addLayout(bottom)

    def _build_html(self) -> str:
        if self.lang == "ru":
            return """
                <html><body style="font-family:Segoe UI; font-size:10.5pt; color:#efefef;">
                <div style="background:rgba(45,180,95,0.10); border:1px solid rgba(45,180,95,0.28); border-radius:12px; padding:12px; margin-bottom:10px;">
                    <b>Что делает это окно</b><br>
                    Здесь можно быстро добавлять в обход и домены, и IP, либо исключать их из обработки.
                </div>
                <div style="margin-bottom:10px;">
                    <b>1. Верхний переключатель</b><br>
                    <span style="color:#bfbfbf;">Домены</span> — работа со списками доменов и сайтов.<br>
                    <span style="color:#bfbfbf;">IP</span> — работа со списками IP-адресов и подсетей.
                </div>
                <div style="margin-bottom:10px;">
                    <b>2. Переключатель ниже</b><br>
                    <span style="color:#bfbfbf;">Добавление</span> — запись попадёт в пользовательский список обхода текущего режима.<br>
                    <span style="color:#bfbfbf;">Исключения</span> — запись попадёт в список исключений текущего режима.
                </div>
                <div style="margin-bottom:10px;">
                    <b>3. Кнопки сверху</b><br>
                    Открыть папку — открывает каталог с пользовательскими списками.<br>
                    Добавить список — импортирует текущий тип данных в список добавления.<br>
                    Исключить список — импортирует текущий тип данных в список исключений.
                </div>
                <div style="margin-bottom:10px;">
                    <b>4. Кнопки рядом с вкладками</b><br>
                    Кнопка с плюсом добавляет один домен или IP вручную в текущий режим.<br>
                    Поле поиска ниже фильтрует уже загруженный список.
                </div>
                <div style="margin-bottom:10px;">
                    <b>5. Работа со списком</b><br>
                    Нажатие по строке отмечает запись галочкой.<br>
                    Корзина удаляет отмеченные записи.<br>
                    Стрелка справа открывает домен или одиночный IP в браузере по умолчанию.
                </div>
                <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px;">
                    <b>Подсказка</b><br>
                    Если у вас сайт — используйте режим <b>Домены</b>. Если у вас IP или подсеть — переключитесь на <b>IP</b>.
                </div>
                </body></html>
            """
        return """
            <html><body style="font-family:Segoe UI; font-size:10.5pt; color:#efefef;">
            <div style="background:rgba(45,180,95,0.10); border:1px solid rgba(45,180,95,0.28); border-radius:12px; padding:12px; margin-bottom:10px;">
                <b>What this window does</b><br>
                Use it to add both domains and IPs to the bypass lists or exclude them from processing.
            </div>
            <div style="margin-bottom:10px;">
                <b>1. Top switch</b><br>
                <span style="color:#bfbfbf;">Domains</span> works with domain and site lists.<br>
                <span style="color:#bfbfbf;">IP</span> works with IP address and subnet lists.
            </div>
            <div style="margin-bottom:10px;">
                <b>2. Switch below</b><br>
                <span style="color:#bfbfbf;">Additions</span> sends the current value type into the user bypass list.<br>
                <span style="color:#bfbfbf;">Excludes</span> sends the current value type into the exclude list.
            </div>
            <div style="margin-bottom:10px;">
                <b>3. Top buttons</b><br>
                Open folder opens the folder with user lists.<br>
                Add list imports the current value type into additions.<br>
                Exclude list imports the current value type into excludes.
            </div>
            <div style="margin-bottom:10px;">
                <b>4. Buttons near tabs</b><br>
                The plus button adds a single domain or IP into the current mode.<br>
                The search field below filters the currently loaded list.
            </div>
            <div style="margin-bottom:10px;">
                <b>5. Working with the list</b><br>
                Clicking a row toggles its checkmark.<br>
                The trash button removes checked items.<br>
                The arrow on the right opens a domain or a single IP in the default browser.
            </div>
            <div style="background:rgba(255,255,255,0.04); border-radius:10px; padding:10px;">
                <b>Tip</b><br>
                Use <b>Domains</b> for websites and <b>IP</b> for direct addresses or subnets.
            </div>
            </body></html>
        """

class SiteManagerDialog(StyledDialog):
    TUTORIAL_SEEN_KEY = "site_manager_tutorial_seen"
    TUTORIAL_HIDE_KEY = "site_manager_tutorial_hide_button"

    class AttentionTabBar(QTabBar):
        def __init__(self, parent=None):
            super().__init__(parent)
            self._attention_alpha = 0

        def set_attention_state(self, alpha: int) -> None:
            self._attention_alpha = max(0, min(255, alpha))
            self.update()

        def clear_attention(self) -> None:
            self._attention_alpha = 0
            self.update()

        def paintEvent(self, event):
            super().paintEvent(event)
            if self._attention_alpha <= 0:
                return

            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            outline = QColor("#2db45f")
            outline.setAlpha(self._attention_alpha)
            pen = QPen(outline, 2)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            for index in range(self.count()):
                rect = self.tabRect(index).adjusted(2, 2, -2, -2)
                if rect.isValid():
                    painter.drawRoundedRect(QRectF(rect.adjusted(0, 0, -1, -1)), 8, 8)

            painter.end()

    class SiteListDelegate(QStyledItemDelegate):
        def __init__(self, dialog):
            super().__init__(dialog)
            self.dialog = dialog

        def paint(self, painter, option, index):
            super().paint(painter, option, index)

            item_rect = QRectF(option.rect)
            icon_rect = self.dialog._visit_icon_rect(option.rect)
            color = QColor("#2db45f") if not index.data(Qt.ItemDataRole.CheckStateRole) else QColor("#43c879")

            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
            pen = QPen(color, 2)
            pen.setCapStyle(Qt.PenCapStyle.RoundCap)
            pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
            painter.setPen(pen)

            arrow_start = QPoint(
                int(icon_rect.left() + 5),
                int(icon_rect.bottom() - 5),
            )
            arrow_end = QPoint(
                int(icon_rect.right() - 5),
                int(icon_rect.top() + 5),
            )
            painter.drawLine(arrow_start, arrow_end)
            painter.drawLine(
                arrow_end,
                QPoint(int(icon_rect.right() - 10), int(icon_rect.top() + 5)),
            )
            painter.drawLine(
                arrow_end,
                QPoint(int(icon_rect.right() - 5), int(icon_rect.top() + 10)),
            )

            underline_y = int(item_rect.bottom() - 8)
            painter.setPen(QPen(color, 1))
            painter.drawLine(
                QPoint(int(icon_rect.left() + 4), underline_y),
                QPoint(int(icon_rect.right() - 4), underline_y),
            )
            painter.restore()

    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.lang = getattr(parent, "lang", "ru") if parent else "ru"
        self.current_file = None
        self.lazy_loaded = {path: False for path in USER_LIST_FILE_MAP.values()}
        self._mode_activated = False
        self._add_button_acknowledged = False
        self._tutorial_dialog = None

        base_w = parent.width() if parent else 300
        self.setWindowTitle("Менеджер сайтов и ip" if self.lang == "ru" else "Site manager")
        self.setMinimumSize(base_w, 410)
        self.resize(base_w, 450)
        self.setFixedWidth(base_w)
        self.setModal(False)
        self.setWindowFlags(
            Qt.WindowType.Dialog |
            Qt.WindowType.WindowTitleHint |
            Qt.WindowType.WindowCloseButtonHint
        )

        frame = _make_window_root_layout(self)
        self.install_title_bar(frame, self.windowTitle())
        root = _make_window_content_layout(frame, self, margins=(10, 10, 10, 10), spacing=8)

        top_row = QHBoxLayout()
        top_row.setSpacing(6)

        tool_btn_style = """
            QToolButton {
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(44,50,50,235),
                    stop:0.36 rgba(34,40,40,238),
                    stop:0.72 rgba(24,30,29,238),
                    stop:1 rgba(26,49,36,235));
                padding: 3px 6px;
                text-align: center;
                font-size: 12px;
            }
            QToolButton:hover {
                border-color: rgba(45,180,95,0.72);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(54,64,61,240),
                    stop:0.38 rgba(40,49,46,240),
                    stop:0.74 rgba(29,39,35,240),
                    stop:1 rgba(33,79,51,238));
            }
            QToolButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(28,35,33,245),
                    stop:1 rgba(38,96,58,242));
            }
        """

        self.open_folder_btn = QToolButton()
        self.open_folder_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_btn.setToolTip(USER_DIR)
        self.open_folder_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.open_folder_btn.setText("Открыть\nпапку" if self.lang == "ru" else "Open\nfolder")
        self.open_folder_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon))
        self.open_folder_btn.setIconSize(QSize(18, 18))
        self.open_folder_btn.setFixedHeight(68)
        self.open_folder_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.open_folder_btn.setStyleSheet(tool_btn_style)
        self.open_folder_btn.clicked.connect(self.open_user_folder)

        self.import_add_btn = QToolButton()
        self.import_add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_add_btn.setToolTip(
            "Добавить домены в user/list-general-user.txt"
            if self.lang == "ru" else
            "Add domains to user/list-general-user.txt"
        )
        self.import_add_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.import_add_btn.setText("Добавить\nсписок" if self.lang == "ru" else "Add\nlist")
        self.import_add_btn.setIcon(self._build_folder_action_icon("#2db45f", True))
        self.import_add_btn.setIconSize(QSize(24, 24))
        self.import_add_btn.setFixedHeight(68)
        self.import_add_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.import_add_btn.setStyleSheet(tool_btn_style)
        self.import_add_btn.clicked.connect(self.import_add_file)

        self.import_exclude_btn = QToolButton()
        self.import_exclude_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_exclude_btn.setToolTip(
            "Добавить домены в user/list-exclude-user.txt"
            if self.lang == "ru" else
            "Add domains to user/list-exclude-user.txt"
        )
        self.import_exclude_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
        self.import_exclude_btn.setText("Исключить\nсписок" if self.lang == "ru" else "Exclude\nlist")
        self.import_exclude_btn.setIcon(self._build_folder_action_icon("#d46060", False))
        self.import_exclude_btn.setIconSize(QSize(24, 24))
        self.import_exclude_btn.setFixedHeight(68)
        self.import_exclude_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.import_exclude_btn.setStyleSheet(tool_btn_style)
        self.import_exclude_btn.clicked.connect(self.import_exclude_file)

        top_row.addWidget(self.open_folder_btn, 1)
        top_row.addWidget(self.import_add_btn, 1)
        top_row.addWidget(self.import_exclude_btn, 1)
        root.addLayout(top_row)

        self.value_tabs = SegmentedControl(self)
        self.value_tabs.addTab(QWidget(), "Домены" if self.lang == "ru" else "Domains")
        self.value_tabs.addTab(QWidget(), "IP")
        self.value_tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        root.addWidget(self.value_tabs)

        tabs_row = QHBoxLayout()
        tabs_row.setSpacing(6)

        self.tabs = SegmentedControl(self, attention_enabled=True)
        self.tabs.addTab(QWidget(), "Добавление" if self.lang == "ru" else "Additions")
        self.tabs.addTab(QWidget(), "Исключения" if self.lang == "ru" else "Excludes")
        self.tabs.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.add_btn = QToolButton()
        self.add_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.add_btn.setAutoRaise(False)
        self.add_btn.setFixedSize(34, 34)
        self.add_btn.setToolTip("Добавить сайт" if self.lang == "ru" else "Add site")
        self.add_btn.setIcon(self._build_circle_action_icon("#2db45f", True, 22))
        self.add_btn.setIconSize(QSize(22, 22))
        self.add_btn.clicked.connect(self.add_site)
        self._init_add_button_attention()
        self._apply_add_button_style()

        tabs_row.addWidget(self.tabs, 1)
        tabs_row.addWidget(self.add_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(tabs_row)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Поиск..." if self.lang == "ru" else "Search...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setFixedHeight(28)
        self.search_input.setStyleSheet("""
            QLineEdit {
                border: 1px solid rgba(120,120,120,70);
                border-radius: 8px;
                padding: 6px 10px;
                background: rgba(255,255,255,0.02);
            }
            QLineEdit:focus {
                border: 1px solid rgba(45,180,95,0.70);
            }
        """)
        self.search_input.textChanged.connect(self.filter_list)

        search_row = QHBoxLayout()
        search_row.setContentsMargins(0, 0, 0, 0)
        search_row.setSpacing(6)
        search_row.addWidget(self.search_input, 1)

        self.delete_btn = QToolButton()
        self.delete_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_TrashIcon))
        self.delete_btn.setIconSize(QSize(16, 16))
        self.delete_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_btn.setFixedSize(34, 34)
        self.delete_btn.setToolTip("Удалить отмеченные" if self.lang == "ru" else "Delete checked")
        self.delete_btn.setStyleSheet("""
            QToolButton {
                border: 1px solid rgba(200,60,60,0.45);
                border-radius: 8px;
                background: rgba(200,60,60,0.08);
            }
            QToolButton:hover { background: rgba(200,60,60,0.18); }
            QToolButton:pressed { background: rgba(200,60,60,0.28); }
        """)
        self.delete_btn.clicked.connect(self.delete_selected_multiple)
        self.delete_btn.hide()
        search_row.addWidget(self.delete_btn, 0, Qt.AlignmentFlag.AlignVCenter)
        root.addLayout(search_row)

        info_row = QHBoxLayout()
        info_row.setContentsMargins(0, 0, 0, 0)
        info_row.setSpacing(6)

        self.list_info_lbl = QLabel()
        self.list_info_lbl.setWordWrap(True)
        self.list_info_lbl.setStyleSheet("color: rgba(180,180,180,0.95);")
        info_row.addWidget(self.list_info_lbl, 1)

        self.tutorial_btn = SiteManagerTutorButton(self)
        self.tutorial_btn.setToolTip(
            "Обучение по менеджеру сайтов"
            if self.lang == "ru" else
            "Site manager guide"
        )
        self.tutorial_btn.clicked.connect(self.open_tutorial)
        info_row.addWidget(self.tutorial_btn, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)

        root.addLayout(info_row)

        self.value_tabs.currentChanged.connect(self.on_mode_changed)
        self.tabs.currentChanged.connect(self.on_mode_changed)
        self.tabs.tabBarClicked.connect(self._on_tab_clicked)

        list_wrap = QWidget(self)
        list_wrap_layout = QVBoxLayout(list_wrap)
        list_wrap_layout.setContentsMargins(0, 0, 0, 0)
        list_wrap_layout.setSpacing(0)

        self.sites_list = QListWidget()
        self.sites_list.setItemDelegate(self.SiteListDelegate(self))
        self.sites_list.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.sites_list.setMouseTracking(True)
        self.sites_list.viewport().setMouseTracking(True)
        self.sites_list.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.sites_list.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.sites_list.setStyleSheet("""
            QListWidget {
                border: 1px solid rgba(120,120,120,70);
                border-radius: 8px;
                padding: 4px;
            }
            QListWidget::item {
                padding: 6px 30px 6px 8px;
                border-radius: 6px;
            }
            QListWidget::item:selected { background: rgba(45,180,95,0.16); }
            QListWidget::item:hover { background: rgba(120,120,120,0.08); }
        """)
        self.sites_list.itemChanged.connect(self.update_delete_buttons)
        self.sites_list.viewport().installEventFilter(self)
        list_wrap_layout.addWidget(self.sites_list)

        root.addWidget(list_wrap, 1)
        self._refresh_mode_controls()
        self._update_list_info()
        self.update_delete_buttons()
        self._init_tab_attention()
        self._apply_tutorial_button_state()

    def eventFilter(self, obj, event):
        if obj is self.sites_list.viewport():
            if event.type() == QEvent.Type.MouseMove:
                item = self.sites_list.itemAt(event.pos())
                cursor = Qt.CursorShape.ArrowCursor
                if item is not None:
                    item_rect = self.sites_list.visualItemRect(item)
                    if self._visit_icon_rect(item_rect).contains(event.position()):
                        cursor = Qt.CursorShape.PointingHandCursor
                self.sites_list.viewport().setCursor(cursor)
            if event.type() in (
                QEvent.Type.Resize,
                QEvent.Type.Paint,
            ):
                QTimer.singleShot(0, self.update_delete_buttons)
            elif event.type() == QEvent.Type.MouseButtonRelease and event.button() == Qt.MouseButton.LeftButton:
                item = self.sites_list.itemAt(event.pos())
                if item is not None:
                    if bool(item.data(PLACEHOLDER_ITEM_ROLE)):
                        return True
                    item_rect = self.sites_list.visualItemRect(item)
                    if self._visit_icon_rect(item_rect).contains(event.position()):
                        self.open_site_in_browser(item)
                        return True
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        QTimer.singleShot(0, self.update_delete_buttons)

    def _build_folder_action_icon(self, badge_color: str, positive: bool, size: int = 24) -> QIcon:
        logical_size = max(18, int(size))
        dpr = 1.0
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            pass

        pm = QPixmap(int(round(logical_size * dpr)), int(round(logical_size * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = logical_size / 24.0
        tab_rect = QRectF(4.0 * scale, 5.0 * scale, 7.5 * scale, 4.2 * scale)
        back_rect = QRectF(2.8 * scale, 7.5 * scale, 17.6 * scale, 11.2 * scale)
        front_rect = QRectF(2.4 * scale, 8.8 * scale, 18.4 * scale, 10.2 * scale)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#c9962c"))
        painter.drawRoundedRect(tab_rect, 1.6 * scale, 1.6 * scale)
        painter.setBrush(QColor("#e5b64a"))
        painter.drawRoundedRect(back_rect, 2.2 * scale, 2.2 * scale)
        painter.setBrush(QColor("#f1cf6a"))
        painter.drawRoundedRect(front_rect, 2.3 * scale, 2.3 * scale)

        gloss = QColor(255, 255, 255, 55)
        painter.setBrush(gloss)
        painter.drawRoundedRect(
            QRectF(front_rect.left() + 1.8 * scale, front_rect.top() + 1.5 * scale, front_rect.width() - 5.4 * scale, 2.0 * scale),
            1.0 * scale,
            1.0 * scale,
        )

        badge_size = 9.8 * scale
        circle_rect = QRectF(
            logical_size - badge_size - 1.6 * scale,
            logical_size - badge_size - 1.6 * scale,
            badge_size,
            badge_size,
        )
        painter.setBrush(QColor(20, 20, 20, 190))
        painter.drawEllipse(circle_rect.adjusted(-0.8 * scale, -0.8 * scale, 0.8 * scale, 0.8 * scale))
        painter.setBrush(QColor(badge_color))
        painter.drawEllipse(circle_rect)

        line_pen = QPen(QColor("white"), max(1.6, 2.0 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(line_pen)

        cx = circle_rect.center().x()
        cy = circle_rect.center().y()
        arm = 2.6 * scale
        painter.drawLine(QPoint(int(round(cx - arm)), int(round(cy))), QPoint(int(round(cx + arm)), int(round(cy))))
        if positive:
            painter.drawLine(QPoint(int(round(cx)), int(round(cy - arm))), QPoint(int(round(cx)), int(round(cy + arm))))

        painter.end()
        return QIcon(pm)

    def _build_web_action_icon(self, badge_color: str, positive: bool, size: int = 22) -> QIcon:
        logical_size = max(18, int(size))
        dpr = 1.0
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            pass

        pm = QPixmap(int(round(logical_size * dpr)), int(round(logical_size * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = logical_size / 22.0
        globe_rect = QRectF(2.2 * scale, 2.2 * scale, 15.8 * scale, 15.8 * scale)
        globe = QColor("#74d6ff")
        globe_dark = QColor("#3aa8d8")
        line = QColor("#e9fbff")

        painter.setPen(QPen(globe_dark, max(1.15, 1.35 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
        painter.setBrush(QColor(116, 214, 255, 42))
        painter.drawEllipse(globe_rect)

        painter.setPen(QPen(line, max(0.85, 1.05 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        cx = globe_rect.center().x()
        cy = globe_rect.center().y()
        painter.drawLine(QPoint(int(round(globe_rect.left() + 1.9 * scale)), int(round(cy))), QPoint(int(round(globe_rect.right() - 1.9 * scale)), int(round(cy))))
        painter.drawArc(globe_rect.adjusted(4.6 * scale, 0.7 * scale, -4.6 * scale, -0.7 * scale), 90 * 16, 180 * 16)
        painter.drawArc(globe_rect.adjusted(4.6 * scale, 0.7 * scale, -4.6 * scale, -0.7 * scale), -90 * 16, 180 * 16)
        painter.drawArc(globe_rect.adjusted(1.0 * scale, 4.8 * scale, -1.0 * scale, -4.8 * scale), 0, 180 * 16)
        painter.drawArc(globe_rect.adjusted(1.0 * scale, 4.8 * scale, -1.0 * scale, -4.8 * scale), 180 * 16, 180 * 16)

        painter.setPen(Qt.PenStyle.NoPen)
        badge_size = 8.8 * scale
        badge_rect = QRectF(
            logical_size - badge_size - 1.0 * scale,
            logical_size - badge_size - 1.0 * scale,
            badge_size,
            badge_size,
        )
        painter.setBrush(QColor(20, 20, 20, 185))
        painter.drawEllipse(badge_rect.adjusted(-0.75 * scale, -0.75 * scale, 0.75 * scale, 0.75 * scale))
        painter.setBrush(QColor(badge_color))
        painter.drawEllipse(badge_rect)

        symbol_pen = QPen(QColor("white"), max(1.55, 1.85 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(symbol_pen)
        bx = badge_rect.center().x()
        by = badge_rect.center().y()
        arm = 2.35 * scale
        painter.drawLine(QPoint(int(round(bx - arm)), int(round(by))), QPoint(int(round(bx + arm)), int(round(by))))
        if positive:
            painter.drawLine(QPoint(int(round(bx)), int(round(by - arm))), QPoint(int(round(bx)), int(round(by + arm))))

        painter.end()
        return QIcon(pm)

    def _build_circle_action_icon(self, circle_color: str, positive: bool, size: int = 22) -> QIcon:
        logical_size = max(18, int(size))
        dpr = 1.0
        try:
            dpr = max(1.0, float(self.devicePixelRatioF()))
        except Exception:
            pass

        pm = QPixmap(int(round(logical_size * dpr)), int(round(logical_size * dpr)))
        pm.setDevicePixelRatio(dpr)
        pm.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pm)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)

        scale = logical_size / 22.0
        shadow_rect = QRectF(2.4 * scale, 2.4 * scale, 17.2 * scale, 17.2 * scale)
        circle_rect = QRectF(2.8 * scale, 2.0 * scale, 16.8 * scale, 16.8 * scale)

        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(0, 0, 0, 95))
        painter.drawEllipse(shadow_rect)

        painter.setBrush(QColor(circle_color))
        painter.drawEllipse(circle_rect)

        painter.setBrush(QColor(255, 255, 255, 34))
        painter.drawEllipse(circle_rect.adjusted(3.0 * scale, 2.0 * scale, -6.2 * scale, -8.8 * scale))

        symbol_pen = QPen(QColor("white"), max(2.0, 2.35 * scale), Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(symbol_pen)

        cx = circle_rect.center().x()
        cy = circle_rect.center().y()
        arm = 4.2 * scale
        painter.drawLine(QPoint(int(round(cx - arm)), int(round(cy))), QPoint(int(round(cx + arm)), int(round(cy))))
        if positive:
            painter.drawLine(QPoint(int(round(cx)), int(round(cy - arm))), QPoint(int(round(cx)), int(round(cy + arm))))

        painter.end()
        return QIcon(pm)

    def _current_value_kind(self) -> str:
        return "ip" if self.value_tabs.currentIndex() == 1 else "domain"

    def _current_action_kind(self) -> str | None:
        index = self.tabs.currentIndex()
        if index < 0:
            return None
        return "add" if index == 0 else "exclude"

    def _placeholder_lines_for_current_file(self) -> list[str]:
        if not self.current_file:
            return []
        return list(EMPTY_USER_LIST_PLACEHOLDERS.get(self.current_file, []))

    def _add_button_attention_color(self) -> tuple[int, int, int]:
        action = self._current_action_kind() or "add"
        return (212, 96, 96) if action == "exclude" else (45, 180, 95)

    def _apply_add_button_style(self, attention_alpha: int = 0) -> None:
        if not hasattr(self, "add_btn"):
            return

        r, g, b = self._add_button_attention_color()
        hover_alpha = 10 if attention_alpha <= 0 else max(18, min(110, attention_alpha // 2))
        press_alpha = 20 if attention_alpha <= 0 else max(28, min(150, int(attention_alpha * 0.7)))
        border_alpha = 60 if attention_alpha <= 0 else max(75, min(210, attention_alpha))

        self.add_btn.setStyleSheet(f"""
            QToolButton {{
                border: 1px solid rgba({r},{g},{b},{border_alpha});
                border-radius: 8px;
                background: rgba({r},{g},{b},10);
                color: rgb({r},{g},{b});
            }}
            QToolButton:hover {{ background: rgba({r},{g},{b},{hover_alpha}); }}
            QToolButton:pressed {{ background: rgba({r},{g},{b},{press_alpha}); }}
        """)

    def _init_add_button_attention(self) -> None:
        self._add_btn_attention_anim = QVariantAnimation(self)
        self._add_btn_attention_anim.setDuration(900)
        self._add_btn_attention_anim.setStartValue(30)
        self._add_btn_attention_anim.setKeyValueAt(0.5, 210)
        self._add_btn_attention_anim.setEndValue(30)
        self._add_btn_attention_anim.setLoopCount(-1)
        self._add_btn_attention_anim.valueChanged.connect(
            lambda value: self._apply_add_button_style(int(value))
            if (not self._add_button_acknowledged and self._mode_activated)
            else None
        )

    def _start_add_button_attention(self) -> None:
        if self._add_button_acknowledged:
            self._apply_add_button_style()
            return
        if hasattr(self, "_add_btn_attention_anim"):
            if self._add_btn_attention_anim.state() == QPropertyAnimation.State.Running:
                return
            self._add_btn_attention_anim.start()
            self._apply_add_button_style(int(self._add_btn_attention_anim.startValue()))

    def _stop_add_button_attention(self) -> None:
        self._add_button_acknowledged = True
        if hasattr(self, "_add_btn_attention_anim"):
            self._add_btn_attention_anim.stop()
        self._apply_add_button_style()

    def _refresh_mode_controls(self) -> None:
        is_ip = self._current_value_kind() == "ip"
        action = self._current_action_kind() or "add"

        if self.lang == "ru":
            add_btn_tip = "Добавить IP" if is_ip else "Добавить сайт"
            if action == "exclude":
                add_btn_tip = "Исключить IP" if is_ip else "Исключить сайт"

            self.import_add_btn.setToolTip(
                "Добавить IP в user/ipset-all-user.txt"
                if is_ip else
                "Добавить домены в user/list-general-user.txt"
            )
            self.import_exclude_btn.setToolTip(
                "Добавить IP в user/ipset-exclude-user.txt"
                if is_ip else
                "Добавить домены в user/list-exclude-user.txt"
            )
        else:
            add_btn_tip = "Add IP" if is_ip else "Add site"
            if action == "exclude":
                add_btn_tip = "Exclude IP" if is_ip else "Exclude site"

            self.import_add_btn.setToolTip(
                "Add IPs to user/ipset-all-user.txt"
                if is_ip else
                "Add domains to user/list-general-user.txt"
            )
            self.import_exclude_btn.setToolTip(
                "Add IPs to user/ipset-exclude-user.txt"
                if is_ip else
                "Add domains to user/list-exclude-user.txt"
            )

        self.add_btn.setToolTip(add_btn_tip)
        self.add_btn.setIcon(self._build_circle_action_icon("#d46060" if action == "exclude" else "#2db45f", action != "exclude", 22))
        self._apply_add_button_style()

    def _selected_file_path(self) -> str:
        action = self._current_action_kind()
        if action is None:
            return None
        return USER_LIST_FILE_MAP.get((self._current_value_kind(), action))

    def _update_list_info(self) -> None:
        selected_path = self._selected_file_path()
        is_ip = self._current_value_kind() == "ip"
        if selected_path is None:
            self.list_info_lbl.setText(
                "Выберите режим Добавление или Исключения, чтобы показать список."
                if self.lang == "ru" else
                "Choose Additions or Excludes to show the list."
            )
        elif selected_path in (USER_GENERAL_FILE, USER_IP_ALL_FILE):
            self.list_info_lbl.setText(
                "Добавляется к основному списку обхода доменов."
                if self.lang == "ru" and not is_ip else
                "Добавляется к основному IP-списку core."
                if self.lang == "ru" else
                "Appended to the main bypass list."
                if not is_ip else
                "Merged into the main core IP list."
            )
        else:
            self.list_info_lbl.setText(
                "Добавляется к списку исключений доменов."
                if self.lang == "ru" and not is_ip else
                "Добавляется к списку исключений IP."
                if self.lang == "ru" else
                "Appended to the exclude list."
                if not is_ip else
                "Appended to the IP exclude list."
            )

    def on_mode_changed(self, _=0):
        self._refresh_mode_controls()
        if not hasattr(self, "sites_list"):
            return
        index = self.tabs.currentIndex()
        if index < 0:
            self.current_file = None
            self.sites_list.clear()
            self._update_list_info()
            self.update_delete_buttons()
            return

        if not self._mode_activated:
            self._activate_mode_selection()

        self.current_file = self._selected_file_path()
        self.reload_current_file()
        if self.current_file:
            self.lazy_loaded[self.current_file] = True

    def reload_current_file(self):
        self.current_file = self._selected_file_path()
        self.sites_list.clear()
        self._refresh_mode_controls()
        self._update_list_info()
        if not self.current_file:
            self.update_delete_buttons()
            return

        lines = _read_lines_utf8(self.current_file)
        placeholder_mode = False
        if not lines:
            lines = self._placeholder_lines_for_current_file()
            placeholder_mode = bool(lines)

        for site in lines:
            item = QListWidgetItem(site)
            item.setData(Qt.ItemDataRole.UserRole, site)
            item.setData(PLACEHOLDER_ITEM_ROLE, placeholder_mode)
            if placeholder_mode:
                item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                item.setForeground(QColor(170, 170, 170))
                item.setToolTip("Пример записи" if self.lang == "ru" else "Example entry")
            else:
                item.setFlags(
                    item.flags() |
                    Qt.ItemFlag.ItemIsUserCheckable |
                    Qt.ItemFlag.ItemIsEnabled
                )
                item.setCheckState(Qt.CheckState.Unchecked)
            self.sites_list.addItem(item)

        self.filter_list(self.search_input.text())
        self.update_delete_buttons()

    def open_user_folder(self):
        try:
            os.startfile(USER_DIR)
        except Exception as e:
            QMessageBox.warning(self, "Ошибка" if self.lang == "ru" else "Error", str(e))

    def import_add_file(self) -> None:
        self.import_values_from_file(USER_LIST_FILE_MAP[(self._current_value_kind(), "add")])

    def import_exclude_file(self) -> None:
        self.import_values_from_file(USER_LIST_FILE_MAP[(self._current_value_kind(), "exclude")])

    def import_values_from_file(self, target_file: str) -> None:
        is_ip = _entity_kind_for_target_file(target_file) == "ip"
        title = (
            "Импорт IP" if is_ip and self.lang == "ru" else
            "Импорт доменов" if self.lang == "ru" else
            "Import IPs" if is_ip else
            "Import domains"
        )
        file_filter = (
            "Поддерживаемые файлы (*.txt *.lst *.list *.json *.csv);;"
            "Текстовые файлы (*.txt *.lst *.list);;"
            "JSON (*.json);;"
            "CSV (*.csv)"
            if self.lang == "ru" else
            "Supported files (*.txt *.lst *.list *.json *.csv);;"
            "Text files (*.txt *.lst *.list);;"
            "JSON (*.json);;"
            "CSV (*.csv)"
        )
        source_path, _ = QFileDialog.getOpenFileName(self, title, "", file_filter)
        if not source_path:
            return

        raw_text = _read_text(source_path)
        candidates = _extract_domain_candidates_from_file(source_path, raw_text)

        imported_values = []
        for value in candidates:
            normalized = _normalize_value_for_target_file(target_file, value)
            if not _is_valid_value_for_target_file(target_file, normalized):
                continue
            imported_values.append(normalized)

        if not imported_values:
            QMessageBox.warning(
                self,
                "Ошибка" if self.lang == "ru" else "Error",
                "В файле не найдено валидных IP или подсетей."
                if is_ip and self.lang == "ru" else
                "В файле не найдено валидных доменов."
                if self.lang == "ru" else
                "No valid IPs or subnets were found in the file."
                if is_ip else
                "No valid domains were found in the file."
            )
            return

        existing = _read_lines_utf8(target_file)
        before = {x.strip().casefold() for x in existing if x.strip()}
        merged = _merge_unique(existing, imported_values)
        after = {x.strip().casefold() for x in merged if x.strip()}
        added_count = len(after - before)
        _write_lines_utf8(target_file, merged)

        self.lazy_loaded[target_file] = True
        if target_file == self._selected_file_path():
            self.reload_current_file()
        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        QMessageBox.information(
            self,
            "Импорт завершён" if self.lang == "ru" else "Import completed",
            (
                f"Добавлено IP: {added_count}"
                if is_ip and self.lang == "ru" else
                f"Добавлено доменов: {added_count}"
                if self.lang == "ru" else
                f"IPs added: {added_count}"
                if is_ip else
                f"Domains added: {added_count}"
            )
        )

    def add_site(self):
        self._stop_add_button_attention()
        if self.tabs.currentIndex() < 0:
            self.tabs.setCurrentIndex(0)
        is_ip = self._current_value_kind() == "ip"
        action = self._current_action_kind() or "add"
        title = (
            "Добавить IP" if is_ip and action == "add" and self.lang == "ru" else
            "Исключить IP" if is_ip and self.lang == "ru" else
            "Добавить сайт" if action == "add" and self.lang == "ru" else
            "Исключить сайт" if self.lang == "ru" else
            "Add IP" if is_ip and action == "add" else
            "Exclude IP" if is_ip else
            "Add site" if action == "add" else
            "Exclude site"
        )
        label = (
            "Введите IP или подсеть:" if is_ip and self.lang == "ru" else
            "Введите домен или сайт:" if self.lang == "ru" else
            "Enter IP or subnet:" if is_ip else
            "Enter domain or site:"
        )

        dlg = TextInputDialog(
            title,
            label,
            ok_text="OK",
            cancel_text="Отмена" if self.lang == "ru" else "Cancel",
            parent=self,
        )
        dlg.setTextValue("")
        _center_widget_on_screen(dlg, self)

        if dlg.exec() != QDialog.DialogCode.Accepted:
            return

        value = _normalize_value_for_target_file(self.current_file, dlg.textValue())

        if not _is_valid_value_for_target_file(self.current_file, value):
            QMessageBox.warning(
                self,
                "Ошибка" if self.lang == "ru" else "Error",
                "Некорректный IP или подсеть."
                if is_ip and self.lang == "ru" else
                "Некорректный домен."
                if self.lang == "ru" else
                "Invalid IP or subnet."
                if is_ip else
                "Invalid domain."
            )
            return

        lines = _read_lines_utf8(self.current_file)
        lines = _merge_unique(lines, [value])
        _write_lines_utf8(self.current_file, lines)
        self.lazy_loaded[self.current_file] = True

        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        self.reload_current_file()

    def _confirm_delete(self, count: int) -> bool:
        title = "Удаление" if self.lang == "ru" else "Delete"
        text = (
            f"Удалить выбранные записи ({count})?"
            if count > 1 and self.lang == "ru" else
            "Удалить выбранную запись?"
            if self.lang == "ru" else
            f"Delete selected entries ({count})?"
            if count > 1 else
            "Delete selected entry?"
        )
        return QMessageBox.question(
            self,
            title,
            text,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes

    def filter_list(self, text):
        text = (text or "").strip().lower()
        for row in range(self.sites_list.count()):
            item = self.sites_list.item(row)
            item.setHidden(text not in item.text().lower())

    def _visit_icon_rect(self, item_rect) -> QRectF:
        size = 18
        margin_right = 8
        x = item_rect.right() - size - margin_right
        y = item_rect.center().y() - size / 2
        return QRectF(x, y, size, size)

    def open_site_in_browser(self, item: QListWidgetItem) -> None:
        if bool(item.data(PLACEHOLDER_ITEM_ROLE)):
            return
        site = str(item.data(Qt.ItemDataRole.UserRole) or item.text()).strip()
        if not site:
            return
        if _is_valid_ip_or_network_like(site):
            if not _is_single_ip_address_like(site):
                return
            host = _normalize_ip_candidate(site)
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            url = site if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", site) else f"http://{host}"
        else:
            url = site if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", site) else f"https://{site}"
        QDesktopServices.openUrl(QUrl(url))

    def _on_tab_clicked(self, index: int) -> None:
        if index < 0:
            return
        if not self._mode_activated and self.tabs.currentIndex() == index:
            self._activate_mode_selection()
            self.current_file = self._selected_file_path()
            self.reload_current_file()
            if self.current_file:
                self.lazy_loaded[self.current_file] = True
            return
        self.tabs.setCurrentIndex(index)

    def _activate_mode_selection(self) -> None:
        if self._mode_activated:
            return
        self._mode_activated = True
        self._stop_tab_attention()
        self._sync_tabbar_mode_state()
        self._start_add_button_attention()

    def _init_tab_attention(self) -> None:
        self.tabs.blockSignals(True)
        self.tabs.setCurrentIndex(-1)
        self.tabs.blockSignals(False)
        if hasattr(self, "sites_list"):
            self.sites_list.clear()
        self._update_list_info()
        self._sync_tabbar_mode_state()
        self._tab_attention_anim = QVariantAnimation(self)
        self._tab_attention_anim.setDuration(900)
        self._tab_attention_anim.setStartValue(30)
        self._tab_attention_anim.setKeyValueAt(0.5, 220)
        self._tab_attention_anim.setEndValue(30)
        self._tab_attention_anim.setLoopCount(-1)
        self._tab_attention_anim.valueChanged.connect(self._update_tab_attention)
        self._tab_attention_anim.start()
        self._update_tab_attention(self._tab_attention_anim.startValue())

    def _update_tab_attention(self, value) -> None:
        if self._mode_activated:
            return
        if hasattr(self.tabs, "set_attention_state"):
            self.tabs.set_attention_state(int(value))

    def _stop_tab_attention(self) -> None:
        if hasattr(self, "_tab_attention_anim") and self._tab_attention_anim is not None:
            self._tab_attention_anim.stop()
        if hasattr(self.tabs, "clear_attention"):
            self.tabs.clear_attention()

    def _sync_tabbar_mode_state(self) -> None:
        if hasattr(self.tabs, "set_mode_activated"):
            self.tabs.set_mode_activated(self._mode_activated)

    def _is_tutorial_hidden(self) -> bool:
        return bool(self.settings.value(self.TUTORIAL_HIDE_KEY, False, type=bool)) if self.settings else False

    def _is_tutorial_seen(self) -> bool:
        return bool(self.settings.value(self.TUTORIAL_SEEN_KEY, False, type=bool)) if self.settings else False

    def _apply_tutorial_button_state(self) -> None:
        if not hasattr(self, "tutorial_btn"):
            return
        if self._is_tutorial_hidden():
            self.tutorial_btn.hide()
            self.tutorial_btn.stop_pulse()
            return

        self.tutorial_btn.show()
        if self._is_tutorial_seen():
            self.tutorial_btn.stop_pulse()
        else:
            self.tutorial_btn.start_pulse()

    def _tutorial_start_pos(self, dialog: QDialog, gap: int = 8) -> QPoint:
        geom = self.frameGeometry()
        x = geom.left() - dialog.width() - 26
        y = geom.top()
        return QPoint(int(x), int(y))

    def _tutorial_target_pos(self, dialog: QDialog, gap: int = 8) -> QPoint:
        geom = self.frameGeometry()
        x = geom.left() - gap - dialog.width()
        y = geom.top()
        return QPoint(int(x), int(y))

    def open_tutorial(self) -> None:
        if self._tutorial_dialog is not None and self._tutorial_dialog.isVisible():
            self._tutorial_dialog.raise_()
            self._tutorial_dialog.activateWindow()
            return

        dialog = SiteManagerTutorialDialog(self, self.lang)
        self._tutorial_dialog = dialog

        def _after_close(_=0):
            dont_show = True
            try:
                dont_show = bool(dialog.dont_show_cb.isChecked())
            except Exception:
                pass

            if self.settings:
                self.settings.setValue(self.TUTORIAL_SEEN_KEY, True)
                self.settings.setValue(self.TUTORIAL_HIDE_KEY, dont_show)

            self._tutorial_dialog = None
            self._apply_tutorial_button_state()

        dialog.finished.connect(_after_close)
        dialog.show()

        start_pos = self._tutorial_start_pos(dialog)
        end_pos = self._tutorial_target_pos(dialog)
        dialog.move(start_pos)
        try:
            dialog.setWindowOpacity(0.0)
        except Exception:
            pass

        pos_anim = QPropertyAnimation(dialog, b"pos", dialog)
        pos_anim.setDuration(260)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(dialog, b"windowOpacity", dialog)
        op_anim.setDuration(220)
        op_anim.setStartValue(0.0)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(dialog)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)
        dialog._open_anim_grp = grp
        dialog._open_anim_pos = pos_anim
        dialog._open_anim_op = op_anim
        grp.start()

    def _checked_items(self):
        return [
            item for item in self.sites_list.findItems("", Qt.MatchFlag.MatchContains)
            if (not bool(item.data(PLACEHOLDER_ITEM_ROLE)))
            and item.checkState() == Qt.CheckState.Checked
        ]

    def _selected_items(self):
        return []

    def _marked_items(self):
        ordered = []
        seen = set()
        for item in self._checked_items():
            key = id(item)
            if key in seen:
                continue
            seen.add(key)
            ordered.append(item)
        return ordered

    def delete_selected_multiple(self):
        items = self._marked_items()
        if not items:
            return
        if not self._confirm_delete(len(items)):
            return

        selected = {str((it.data(Qt.ItemDataRole.UserRole) or it.text())).strip().casefold() for it in items}
        lines = [x for x in _read_lines_utf8(self.current_file) if x.strip().casefold() not in selected]
        _write_lines_utf8(self.current_file, lines)
        self.lazy_loaded[self.current_file] = True

        if self.parent() and hasattr(self.parent(), "refresh_runtime_lists_after_user_change"):
            self.parent().refresh_runtime_lists_after_user_change()

        self.reload_current_file()

    def update_delete_buttons(self):
        if self._marked_items():
            self.delete_btn.show()
        else:
            self.delete_btn.hide()


class GameModeSettingsDialog(StyledDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        lang = getattr(parent, "lang", "ru") if parent else "ru"
        self.parent_window = parent
        self.lang = lang
        options = _get_game_mode_options(getattr(parent, "settings", None))
        base_w = parent.width() if parent else 300

        self.setWindowTitle("Настройки игрового режима" if lang == "ru" else "Game mode settings")
        self.setWindowFlags(
            Qt.WindowType.Dialog
            | Qt.WindowType.WindowTitleHint
            | Qt.WindowType.WindowCloseButtonHint
        )
        self.setModal(False)
        self.setStyleSheet(_app_dialog_stylesheet() + """
            QLabel {
                color: #f1f1f1;
            }
            QPushButton {
                min-height: 30px;
                padding: 0 14px;
                border: 1px solid rgba(255,255,255,0.14);
                border-radius: 8px;
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(54,64,61,240),
                    stop:0.52 rgba(28,35,33,240),
                    stop:1 rgba(33,79,51,238));
                color: #f6fff8;
                font-weight: 600;
            }
            QPushButton:hover {
                border-color: rgba(45,180,95,0.72);
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(62,74,70,242),
                    stop:0.52 rgba(34,44,40,242),
                    stop:1 rgba(42,104,63,240));
            }
            QPushButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(28,35,33,245),
                    stop:1 rgba(38,96,58,242));
            }
        """)

        frame = _make_window_root_layout(self)
        self.install_title_bar(frame, self.windowTitle())
        layout = _make_window_content_layout(frame, self, margins=(14, 12, 14, 14), spacing=10)

        caption = QLabel(
            "Настройте, что добавлять к игровому режиму."
            if lang == "ru" else
            "Choose what should be added to game mode."
        )
        caption.setWordWrap(True)
        layout.addWidget(caption)

        self.main_bypass_switch = ToggleSwitch(self)
        self.main_bypass_switch.setChecked(bool(options["main_bypass_enabled"]))
        layout.addLayout(
            self._build_switch_row(
                "Основной обход" if lang == "ru" else "Main bypass",
                self.main_bypass_switch,
            )
        )

        self.user_lists_switch = ToggleSwitch(self)
        self.user_lists_switch.setChecked(bool(options["user_lists_enabled"]))
        layout.addLayout(
            self._build_switch_row(
                "Пользовательские домены и ip"
                if lang == "ru" else
                "User domains and IP",
                self.user_lists_switch,
            )
        )

        self.discord_switch = ToggleSwitch(self)
        self.discord_switch.setChecked(bool(options["discord_enabled"]))
        layout.addLayout(
            self._build_switch_row(
                "Discord отдельно" if lang == "ru" else "Discord separately",
                self.discord_switch,
            )
        )

        bottom_row = QHBoxLayout()
        bottom_row.setContentsMargins(0, 0, 0, 0)
        bottom_row.setSpacing(10)

        self.help_hint_lbl = QLabel(
            "Зачем это нужно?"
            if lang == "ru" else
            "Why is this needed?"
        )
        self.help_hint_lbl.setCursor(Qt.CursorShape.PointingHandCursor)
        self.help_hint_lbl.setMouseTracking(True)
        self.help_hint_lbl.setStyleSheet("""
            QLabel {
                color: #8ee6ad;
                font-weight: 600;
                padding: 4px 0;
                text-decoration: underline;
            }
            QLabel:hover { color: #b7f6c9; }
        """)
        self.help_hint_lbl.installEventFilter(self)
        bottom_row.addWidget(self.help_hint_lbl, 0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        bottom_row.addStretch()

        close_btn = QPushButton("Закрыть" if lang == "ru" else "Close")
        close_btn.clicked.connect(self.close)
        bottom_row.addWidget(close_btn)

        layout.addStretch()
        layout.addLayout(bottom_row)

        self._help_popup_anim = None
        self._build_help_popup()

        self.main_bypass_switch.toggled.connect(self.apply_changes)
        self.user_lists_switch.toggled.connect(self.apply_changes)
        self.discord_switch.toggled.connect(self.apply_changes)

        self.setFixedWidth(base_w)
        self.adjustSize()
        self.setFixedSize(base_w, self.sizeHint().height())

    def _help_popup_text(self) -> str:
        if self.lang == "ru":
            return (
                "Данные настройки призваны уменьшить влияние на сеть, пока вы играете. "
                "Если вам не нужен обычный обход (YouTube, Twitch и т.д.) во время игры, "
                "а нужны только Game Filters, то лишнее можно отключить, чтобы не влиять на пинг "
                "и не мониторить все сетевые пакеты. Вы также можете отдельно включить только "
                "Discord обход в дополнение к игровому режиму, чтобы общаться во время игры. "
                "Либо другие ваши пользовательские домены/ip."
            )
        return (
            "These settings reduce network impact while you play. If you do not need the regular "
            "bypass for YouTube, Twitch, and similar sites during a game, and only need Game Filters, "
            "you can disable it to avoid affecting ping or monitoring all network packets. You can also "
            "enable only Discord bypass in addition to game mode so you can talk while playing, or keep "
            "your own custom domains/IP enabled."
        )

    def _build_help_popup(self) -> None:
        popup_flags = Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint
        try:
            popup_flags |= Qt.WindowType.WindowDoesNotAcceptFocus
        except AttributeError:
            pass

        popup = QFrame(self, popup_flags)
        popup.setObjectName("gameModeHelpPopup")
        popup.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        popup.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        popup.setStyleSheet("""
            QFrame#gameModeHelpPopup {
                background: #242424;
                border: 1px solid rgba(142, 230, 173, 0.58);
                border-radius: 10px;
            }
            QFrame#gameModeHelpPopup QLabel {
                color: #f3f3f3;
            }
        """)

        popup_layout = QVBoxLayout(popup)
        popup_layout.setContentsMargins(14, 12, 14, 12)
        popup_layout.setSpacing(0)

        text_lbl = QLabel(self._help_popup_text(), popup)
        font = text_lbl.font()
        font.setPixelSize(12)
        text_lbl.setFont(font)
        text_lbl.setWordWrap(True)
        text_lbl.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
        popup_layout.addWidget(text_lbl)

        popup.hide()
        self.help_popup = popup
        self.help_popup_text_lbl = text_lbl
        self._help_popup_target_visible = False

    def _stop_help_popup_anim(self) -> None:
        if self._help_popup_anim is None:
            return
        anim = self._help_popup_anim
        self._help_popup_anim = None
        anim.stop()
        anim.deleteLater()

    def _finish_help_popup_anim(self) -> None:
        anim = self._help_popup_anim
        self._help_popup_anim = None
        if anim is not None:
            anim.deleteLater()

        if self._help_popup_target_visible:
            self.help_popup.setWindowOpacity(1.0)
        else:
            self.help_popup.hide()
            self.help_popup.setWindowOpacity(0.0)

    def _help_popup_screen_geometry(self):
        screen = QGuiApplication.screenAt(self.mapToGlobal(self.rect().center()))
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen.availableGeometry() if screen is not None else None

    def _help_popup_positions(self) -> tuple[QPoint, QPoint]:
        screen_rect = self._help_popup_screen_geometry()
        popup_w = max(320, self.width() + 100)
        if screen_rect is not None:
            popup_w = min(popup_w, max(260, screen_rect.width() - 32))

        margins = self.help_popup.layout().contentsMargins()
        inner_w = max(220, int(popup_w) - margins.left() - margins.right())
        self.help_popup_text_lbl.setFixedWidth(inner_w)
        text_h = self.help_popup_text_lbl.heightForWidth(inner_w)
        if text_h <= 0:
            text_h = self.help_popup_text_lbl.sizeHint().height()
        popup_h = int(text_h + margins.top() + margins.bottom())
        self.help_popup.setMinimumSize(0, 0)
        self.help_popup.setMaximumSize(16777215, 16777215)
        self.help_popup.setFixedSize(int(popup_w), max(80, popup_h))

        label_pos = self.help_hint_lbl.mapToGlobal(QPoint(0, 0))
        target_x = label_pos.x()
        target_y = label_pos.y() + self.help_hint_lbl.height() + 8

        if screen_rect is not None:
            if target_x + popup_w > screen_rect.right() - 8:
                target_x = screen_rect.right() - int(popup_w) - 8
            target_x = max(screen_rect.left() + 8, target_x)

            if target_y + popup_h > screen_rect.bottom() - 8:
                target_y = label_pos.y() - popup_h - 8
            target_y = max(screen_rect.top() + 8, target_y)

        target = QPoint(int(target_x), int(target_y))
        start = QPoint(target.x(), target.y() + 10)
        return start, target

    def _show_help_popup(self) -> None:
        if not hasattr(self, "help_popup"):
            return

        start_pos, target_pos = self._help_popup_positions()

        if self._help_popup_target_visible and self.help_popup.isVisible():
            self._stop_help_popup_anim()
            self.help_popup.move(target_pos)
            self.help_popup.setWindowOpacity(1.0)
            return

        self._help_popup_target_visible = True
        visible = self.help_popup.isVisible()
        current_opacity = float(self.help_popup.windowOpacity()) if visible else 0.0

        self._stop_help_popup_anim()

        if visible:
            start_pos = self.help_popup.pos()
        else:
            self.help_popup.move(start_pos)
            self.help_popup.setWindowOpacity(0.0)

        self.help_popup.show()
        self.help_popup.raise_()

        pos_anim = QPropertyAnimation(self.help_popup, b"pos", self)
        pos_anim.setDuration(180)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(target_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        op_anim = QPropertyAnimation(self.help_popup, b"windowOpacity", self)
        op_anim.setDuration(160)
        op_anim.setStartValue(current_opacity)
        op_anim.setEndValue(1.0)
        op_anim.setEasingCurve(QEasingCurve.Type.OutCubic)

        grp = QParallelAnimationGroup(self)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)
        grp.finished.connect(self._finish_help_popup_anim)
        self._help_popup_anim = grp
        grp.start()

    def _hide_help_popup(self, immediate: bool = False) -> None:
        if not hasattr(self, "help_popup"):
            return

        if not self._help_popup_target_visible and not self.help_popup.isVisible():
            return

        self._help_popup_target_visible = False
        self._stop_help_popup_anim()

        if immediate or not self.help_popup.isVisible():
            self.help_popup.hide()
            self.help_popup.setWindowOpacity(0.0)
            return

        start_pos = self.help_popup.pos()
        end_pos = QPoint(start_pos.x(), start_pos.y() + 10)

        pos_anim = QPropertyAnimation(self.help_popup, b"pos", self)
        pos_anim.setDuration(150)
        pos_anim.setStartValue(start_pos)
        pos_anim.setEndValue(end_pos)
        pos_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        op_anim = QPropertyAnimation(self.help_popup, b"windowOpacity", self)
        op_anim.setDuration(150)
        op_anim.setStartValue(float(self.help_popup.windowOpacity()))
        op_anim.setEndValue(0.0)
        op_anim.setEasingCurve(QEasingCurve.Type.InCubic)

        grp = QParallelAnimationGroup(self)
        grp.addAnimation(pos_anim)
        grp.addAnimation(op_anim)
        grp.finished.connect(self._finish_help_popup_anim)
        self._help_popup_anim = grp
        grp.start()

    def eventFilter(self, obj, event):
        if obj is getattr(self, "help_hint_lbl", None):
            if event.type() == QEvent.Type.Enter:
                self._show_help_popup()
            elif event.type() == QEvent.Type.Leave:
                self._hide_help_popup()
        return super().eventFilter(obj, event)

    def closeEvent(self, event):
        self._hide_help_popup(immediate=True)
        super().closeEvent(event)

    def _build_switch_row(self, text: str, switch: ToggleSwitch) -> QHBoxLayout:
        row = QHBoxLayout()
        row.setContentsMargins(0, 2, 0, 2)
        row.setSpacing(10)

        label = ClickableLabel(text)
        label.setWordWrap(True)
        label.clicked.connect(switch.toggle)
        row.addWidget(label, 1)
        row.addWidget(switch, 0, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return row

    def apply_changes(self) -> None:
        if self.parent_window and hasattr(self.parent_window, "apply_game_mode_preferences"):
            self.parent_window.apply_game_mode_preferences(
                main_bypass_enabled=self.main_bypass_switch.isChecked(),
                user_lists_enabled=self.user_lists_switch.isChecked(),
                discord_enabled=self.discord_switch.isChecked(),
                restart_if_running=True,
            )

