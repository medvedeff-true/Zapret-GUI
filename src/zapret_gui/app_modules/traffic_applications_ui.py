"""Nonblocking, path-based application picker (executed in app globals)."""

_TRAFFIC_CATALOG_CACHE = {}
_TRAFFIC_CATALOG_WORKERS = set()


class TrafficApplicationFileDelegate(QStyledItemDelegate):
    @staticmethod
    def remove_rect(rect):
        return QRectF(rect.right() - 27, rect.center().y() - 12, 24, 24)

    def location_rect(self, rect):
        right = rect.right() - (30 if self.parent().removable else 4)
        return QRectF(right - 104, rect.top(), 104, rect.height())

    def paint(self, painter, option, index):
        item_option = QStyleOptionViewItem(option)
        self.initStyleOption(item_option, index)
        checkable = bool(index.flags() & Qt.ItemFlag.ItemIsUserCheckable)
        # Draw the initialized option directly: the base delegate's paint()
        # initializes it again and restores the native check indicator.
        item_option.features &= ~QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        item_option.rect.setLeft(item_option.rect.left() + 28)
        location = self.location_rect(option.rect)
        item_option.rect.setRight(int(location.left()) - 70)
        widget = item_option.widget or self.parent()
        widget.style().drawControl(QStyle.ControlElement.CE_ItemViewItem, item_option, painter, widget)
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if checkable:
            indicator = QRectF(option.rect.left() + 6, option.rect.center().y() - 8.5, 17, 17)
            checked = item_option.checkState == Qt.CheckState.Checked
            painter.setPen(QPen(QColor("#58ab78" if checked else "#5f7267"), 1.1))
            painter.setBrush(QColor("#24583c" if checked else "#111716"))
            painter.drawRoundedRect(indicator, 3.5, 3.5)
            if checked:
                tick = QPainterPath(QPointF(indicator.left() + 4.0, indicator.top() + 8.5))
                tick.lineTo(indicator.left() + 7.2, indicator.top() + 11.7)
                tick.lineTo(indicator.left() + 13.0, indicator.top() + 5.5)
                painter.setPen(QPen(QColor("#eefaf1"), 1.9, Qt.PenStyle.SolidLine,
                                    Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawPath(tick)
        size_rect = QRectF(location.left() - 70, location.top(), 66, location.height())
        painter.setPen(QColor("#b4bcb7"))
        painter.drawText(size_rect, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter,
                         str(index.data(int(Qt.ItemDataRole.UserRole) + 2) or ""))
        if index.data(Qt.ItemDataRole.UserRole):
            copied = bool(index.data(int(Qt.ItemDataRole.UserRole) + 3))
            painter.setPen(QColor("#8ee6ad"))
            label = ("Скопировано" if copied else "Расположение") if self.parent().lang == "ru" else (
                "Copied" if copied else "Location")
            painter.drawText(location, Qt.AlignmentFlag.AlignCenter, label)
        if self.parent().removable:
            rect = self.remove_rect(option.rect)
            painter.setPen(QPen(QColor("#ee858b"), 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            center = rect.center()
            painter.drawLine(center + QPointF(-4, -4), center + QPointF(4, 4))
            painter.drawLine(center + QPointF(4, -4), center + QPointF(-4, 4))
        painter.restore()


class TrafficApplicationsListWidget(QListWidget):
    """Toggle a row from anywhere, not only from the native checkbox."""

    removeRequested = pyqtSignal(str)
    locationRequested = pyqtSignal(str)

    def __init__(self, parent=None, removable=False, lang="ru"):
        super().__init__(parent)
        self.removable = removable
        self.lang = lang
        self.setItemDelegate(TrafficApplicationFileDelegate(self))
        self.setMouseTracking(True)

    def viewportEvent(self, event):
        if event.type() == QEvent.Type.ToolTip:
            item = self.itemAt(event.pos())
            if item is not None:
                path = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if self.itemDelegate().location_rect(self.visualItemRect(item)).contains(QPointF(event.pos())):
                    QToolTip.showText(event.globalPos(), path, self)
                    return True
        return super().viewportEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            item = self.itemAt(event.position().toPoint())
            if item is not None and self.itemDelegate().location_rect(self.visualItemRect(item)).contains(event.position()):
                path = str(item.data(Qt.ItemDataRole.UserRole) or "")
                if path:
                    self.locationRequested.emit(path)
                event.accept()
                return
            if (
                item is not None and self.removable
                and TrafficApplicationFileDelegate.remove_rect(self.visualItemRect(item)).contains(event.position())
            ):
                self.removeRequested.emit(str(item.data(Qt.ItemDataRole.UserRole) or ""))
                event.accept()
                return
            if item is not None and item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(
                    Qt.CheckState.Unchecked
                    if item.checkState() == Qt.CheckState.Checked
                    else Qt.CheckState.Checked
                )
                event.accept()
                return
        super().mousePressEvent(event)


class TrafficApplicationsSnapshotWorker(QThread):
    snapshot = pyqtSignal(str, object, str)

    def __init__(self, kind):
        super().__init__()
        self.kind = kind

    def run(self):
        try:
            if self.kind == "installed":
                values = enumerate_installed_applications(
                    include_unresolved=True,
                    resolve_install_locations=False,
                )
            else:
                values = enumerate_processes(include_unresolved=True, resolve_unresolved=False)
            self.snapshot.emit(self.kind, values, "")
        except Exception as error:
            self.snapshot.emit(self.kind, [], str(error))


class TrafficApplicationsDialog(StyledDialog):
    def __init__(self, parent=None, settings=None):
        super().__init__(parent)
        self.settings = settings
        self.lang = settings.value("lang", "ru") if settings is not None else "ru"
        storage = os.path.join(os.path.dirname(settings.fileName()), "user", "traffic_apps.json") if settings else os.path.join(USER_DIR, "traffic_apps.json")
        self.store = TrafficAppStore(storage, auto_save=False)
        self._records = {self._key(r.path): r.to_json() for r in self.store.records()}
        if not self._records and settings is not None:
            self._records = {self._key(r["path"]): r for r in load_app_records(settings)}
        self._lists = {}
        self._rows_by_path = {}
        self._requested = set()
        self._loaded = set()
        self._workers = set()
        self._pending_rows = {}
        self._file_sizes = {}
        self._copied_path = ""
        self._copy_timer = QTimer(self)
        self._copy_timer.setSingleShot(True)
        self._copy_timer.setInterval(2000)
        self._copy_timer.timeout.connect(self._clear_copied_location)
        self._populating = False
        self._closed = False
        self._icons = ApplicationIcons(self)
        self._icons.ready.connect(self._icon_ready)
        self.setWindowTitle("Приложения для обхода" if self.lang == "ru" else "Bypass applications")
        self.setFixedSize(520, 520)
        root = _make_window_root_layout(self)
        self.install_title_bar(root, self.windowTitle())
        layout = _make_window_content_layout(root, self, margins=(10, 8, 10, 10), spacing=7)
        self._search = QLineEdit(self)
        self._search.setPlaceholderText("Поиск..." if self.lang == "ru" else "Search...")
        self._search.textChanged.connect(self._filter_current)
        layout.addWidget(self._search)
        self.tabs = QTabWidget(self)
        self.tabs.setObjectName("trafficApplicationTabs")
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(False)
        self.tabs.tabBar().setExpanding(True)
        self.tabs.tabBar().setDrawBase(False)
        self.tabs.setStyleSheet("""
            QTabWidget#trafficApplicationTabs {
                border: none; background: transparent;
            }
            QTabWidget#trafficApplicationTabs::pane {
                border: none; background: transparent;
            }
            QTabWidget#trafficApplicationTabs QTabBar {
                background: #111716; border: 1px solid #2a3831;
                border-radius: 10px; padding: 3px;
            }
            QTabWidget#trafficApplicationTabs QTabBar::tab {
                background: transparent; color: #aebbb3; border: none;
                border-radius: 7px; padding: 7px 16px; min-width: 76px;
                margin: 0 2px 0 0;
            }
            QTabWidget#trafficApplicationTabs QTabBar::tab:hover {
                color: #f2f8f4; background: rgba(93, 135, 108, 42);
            }
            QTabWidget#trafficApplicationTabs QTabBar::tab:selected {
                color: #f5fff8; background: #286345; font-weight: 650;
            }
            QTabWidget#trafficApplicationTabs QListWidget {
                border: none; border-radius: 9px; background: #292b2a;
                padding: 3px;
            }
            QTabWidget#trafficApplicationTabs QListWidget::item {
                border-radius: 6px; padding: 2px 4px;
            }
            QTabWidget#trafficApplicationTabs QListWidget::item:hover {
                background: rgba(80, 135, 100, 45);
            }
        """)
        for kind, label in (("installed", "Список"), ("processes", "Процессы"), ("file", "Из файла")):
            page = QWidget(self)
            content = QVBoxLayout(page)
            content.setContentsMargins(0, 0, 0, 0)
            if kind == "file":
                choose = QPushButton("Выбрать")
                choose.clicked.connect(self._choose_file)
                content.addWidget(choose)
            listing = TrafficApplicationsListWidget(page, removable=kind == "file", lang=self.lang)
            listing.removeRequested.connect(self._remove_saved_application)
            listing.locationRequested.connect(self._copy_location)
            listing.setUniformItemSizes(True)
            listing.setIconSize(QSize(20, 20))
            listing.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
            listing.itemChanged.connect(self._item_changed)
            listing.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
            listing.customContextMenuRequested.connect(
                lambda pos, k=kind: self._show_item_menu(k, pos)
            )
            listing.verticalScrollBar().valueChanged.connect(self._request_visible_icons)
            content.addWidget(listing)
            self._lists[kind] = listing
            self.tabs.addTab(page, label)
        self.tabs.currentChanged.connect(self._tab_changed)
        layout.addWidget(self.tabs, 1)
        self.status = QLabel()
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.refresh_btn = QPushButton("Обновить")
        self.refresh_btn.clicked.connect(self._load_processes)
        self.refresh_btn.hide()
        buttons.addWidget(self.refresh_btn)
        buttons.addStretch(1)
        apply_btn = QPushButton("Применить")
        apply_btn.clicked.connect(self.accept)
        buttons.addWidget(apply_btn)
        layout.addLayout(buttons)
        self._render_timer = QTimer(self)
        self._render_timer.setInterval(0)
        self._render_timer.timeout.connect(self._render_batch)
        # Return to Qt before registry, process or shell work starts.
        QTimer.singleShot(0, self._tab_changed)

    @staticmethod
    def _key(path):
        return os.path.normcase(os.path.normpath(path)) if path else ""

    def _tab_changed(self, *_):
        if self._closed:
            return
        kind = ("installed", "processes", "file")[self.tabs.currentIndex()]
        self.refresh_btn.setVisible(kind == "processes")
        if kind == "file":
            self._load_files()
        elif kind not in self._loaded and kind not in self._requested:
            self._request_snapshot(kind)
        self._filter_current()
        self._request_visible_icons()

    def _request_snapshot(self, kind, force=False):
        if self._closed or kind in self._requested:
            return
        cached = _TRAFFIC_CATALOG_CACHE.get(kind)
        if not force and kind == "installed" and cached and time.monotonic() - cached[0] < 60:
            self._snapshot_ready(kind, cached[1], "")
            return
        self._requested.add(kind)
        self.status.setText("Загрузка…" if self.lang == "ru" else "Loading…")
        self.refresh_btn.setEnabled(kind != "processes")
        worker = TrafficApplicationsSnapshotWorker(kind)
        self._workers.add(worker)
        _TRAFFIC_CATALOG_WORKERS.add(worker)
        worker.snapshot.connect(self._snapshot_ready)
        # Keep the thread alive when the dialog is closed mid-enumeration.
        def release():
            _TRAFFIC_CATALOG_WORKERS.discard(worker)
            worker.deleteLater()
        worker.finished.connect(release)
        worker.start()

    def _load_processes(self, *_):
        self._request_snapshot("processes", force=True)

    def _snapshot_ready(self, kind, values, error):
        self._requested.discard(kind)
        if self._closed:
            return
        self.refresh_btn.setEnabled(True)
        self.status.setText(error)
        self._loaded.add(kind)
        if not error:
            _TRAFFIC_CATALOG_CACHE[kind] = (time.monotonic(), values)
        rows = []
        seen = set()
        if kind == "installed":
            for entry in values:
                if not entry.path or not entry.path.casefold().endswith(".exe") or not os.path.isfile(entry.path):
                    continue
                rows.append((entry.path, entry.name, SOURCE_INSTALLED))
                seen.add(self._key(entry.path))
        else:
            for entry in sorted(values, key=lambda p: (p.is_service, p.name.casefold(), p.pid)):
                suffix = " · служба" if entry.is_service else ""
                rows.append((entry.path, f"{entry.name} (PID {entry.pid}){suffix}", SOURCE_PROCESS))
                seen.add(self._key(entry.path))
        # Remembered paths remain removable even while their processes are absent.
        source = SOURCE_INSTALLED if kind == "installed" else SOURCE_PROCESS
        for key, record in self._records.items():
            sources = record.get("sources", [record.get("source", SOURCE_FILE)])
            if source in sources and key not in seen:
                rows.append((record["path"], record.get("label", "") or os.path.basename(record["path"]), source))
        self._queue_rows(kind, rows)

    def _queue_rows(self, kind, rows):
        listing = self._lists[kind]
        self._populating = True
        listing.clear()
        self._populating = False
        self._rows_by_path = {
            key: [i for i in items if i.listWidget() is not listing]
            for key, items in self._rows_by_path.items()
        } if False else {}  # indexes are rebuilt for every visible snapshot
        self._pending_rows[kind] = iter(rows)
        self._render_timer.start()

    def _render_batch(self):
        if self._closed:
            self._render_timer.stop()
            return
        self._populating = True
        try:
            for kind, rows in list(self._pending_rows.items()):
                listing = self._lists[kind]
                listing.blockSignals(True)
                try:
                    for _ in range(64):
                        try:
                            path, label, source = next(rows)
                        except StopIteration:
                            self._pending_rows.pop(kind, None)
                            break
                        item = QListWidgetItem(label)
                        item.setSizeHint(QSize(0, 28))
                        item.setToolTip(path or "Исполняемый файл не найден")
                        item.setIcon(self._icons.fallback)
                        item.setData(Qt.ItemDataRole.UserRole, path)
                        item.setData(int(Qt.ItemDataRole.UserRole) + 1, source)
                        item.setData(int(Qt.ItemDataRole.UserRole) + 2, self._file_size_text(path))
                        item.setData(int(Qt.ItemDataRole.UserRole) + 3, self._key(path) == self._copied_path)
                        if path:
                            record = self._records.get(self._key(path), {})
                            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                            item.setCheckState(Qt.CheckState.Checked if record.get("enabled") else Qt.CheckState.Unchecked)
                        else:
                            item.setFlags(Qt.ItemFlag.NoItemFlags)
                        listing.addItem(item)
                        needle = self._search.text().strip().casefold()
                        item.setHidden(bool(needle and needle not in (label + " " + path).casefold()))
                finally:
                    listing.blockSignals(False)
        finally:
            self._populating = False
        if not self._pending_rows:
            self._render_timer.stop()
        self._request_visible_icons()

    def _request_visible_icons(self, *_):
        if self._closed:
            return
        listing = self._lists[("installed", "processes", "file")[self.tabs.currentIndex()]]
        top = listing.indexAt(QPoint(4, 4)).row()
        if top < 0:
            top = 0
        for row in range(top, min(listing.count(), top + listing.height() // 28 + 4)):
            item = listing.item(row)
            if item.isHidden():
                continue
            path = str(item.data(Qt.ItemDataRole.UserRole) or "")
            if path:
                self._populating = True
                item.setIcon(self._icons.icon(path))
                self._populating = False

    def _icon_ready(self, path):
        if not self._closed:
            self._request_visible_icons()

    def _load_files(self):
        rows = [
            (r["path"], r.get("label") or os.path.basename(r["path"]), SOURCE_FILE)
            for r in self._records.values()
            if SOURCE_FILE in r.get("sources", [r.get("source", SOURCE_FILE)])
        ]
        self._queue_rows("file", rows)

    def _file_size_text(self, path):
        if not path:
            return ""
        key = self._key(path)
        if key not in self._file_sizes:
            try:
                size = os.path.getsize(path)
                units = ("Б", "КБ", "МБ", "ГБ") if self.lang == "ru" else ("B", "KB", "MB", "GB")
                value = float(size)
                unit = units[0]
                for unit in units:
                    if value < 1024 or unit == units[-1]:
                        break
                    value /= 1024
                self._file_sizes[key] = f"{value:.1f} {unit}"
            except OSError:
                self._file_sizes[key] = "—"
        return self._file_sizes[key]

    def _copy_location(self, path):
        QApplication.clipboard().setText(path)
        self._copied_path = self._key(path)
        self._update_copied_locations()
        self._copy_timer.start()

    def _clear_copied_location(self):
        self._copied_path = ""
        self._update_copied_locations()

    def _update_copied_locations(self):
        self._populating = True
        try:
            for listing in self._lists.values():
                for row in range(listing.count()):
                    item = listing.item(row)
                    item.setData(int(Qt.ItemDataRole.UserRole) + 3,
                                 bool(self._copied_path and self._key(item.data(Qt.ItemDataRole.UserRole)) == self._copied_path))
        finally:
            self._populating = False

    def _filter_current(self, *_):
        needle = self._search.text().strip().casefold()
        listing = self._lists[("installed", "processes", "file")[self.tabs.currentIndex()]]
        for row in range(listing.count()):
            item = listing.item(row)
            path = str(item.data(Qt.ItemDataRole.UserRole) or "")
            item.setHidden(bool(needle and needle not in (item.text() + " " + path).casefold()))
        self._request_visible_icons()

    def _item_changed(self, item):
        if self._populating:
            return
        path = str(item.data(Qt.ItemDataRole.UserRole) or "")
        if not path:
            return
        key = self._key(path)
        source = item.data(int(Qt.ItemDataRole.UserRole) + 1) or SOURCE_FILE
        record = self._records.setdefault(key, {"path": path, "label": item.text(), "sources": []})
        record["enabled"] = item.checkState() == Qt.CheckState.Checked
        record["sources"] = sorted(set(record.get("sources", [])) | {source})
        # Synchronize check state across tabs/PIDs, without persistence or filesystem work.
        self._populating = True
        try:
            for listing in self._lists.values():
                for row in range(listing.count()):
                    other = listing.item(row)
                    if self._key(other.data(Qt.ItemDataRole.UserRole)) == key:
                        other.setCheckState(item.checkState())
        finally:
            self._populating = False

    def _choose_file(self):
        path, _ = QFileDialog.getOpenFileName(self, "Выберите исполняемый файл", "", "Исполняемые файлы (*.exe)")
        if not path:
            return
        if not os.path.isfile(path) or not path.casefold().endswith(".exe"):
            self.status.setText("Выберите существующий .exe файл.")
            return
        key = self._key(path)
        old = self._records.get(key, {})
        self._records[key] = {
            "path": path, "label": old.get("label") or os.path.basename(path),
            "enabled": True, "sources": sorted(set(old.get("sources", [])) | {SOURCE_FILE}),
        }
        self._load_files()

    def _show_item_menu(self, kind, pos):
        item = self._lists[kind].itemAt(pos)
        if item is None:
            return
        key = self._key(item.data(Qt.ItemDataRole.UserRole))
        if key not in self._records:
            return
        menu = QMenu(self)
        remove = menu.addAction("Удалить из сохранённых")
        if menu.exec(self._lists[kind].viewport().mapToGlobal(pos)) == remove:
            self._remove_saved_application(str(item.data(Qt.ItemDataRole.UserRole) or ""))

    def _remove_saved_application(self, path):
        key = self._key(path)
        if not key or key not in self._records:
            return
        # The delete icon is an immediate action, unlike staged checkboxes.
        # Load persisted records separately so deletion does not apply other
        # unsaved checkbox edits from this dialog.
        try:
            persisted = TrafficAppStore(self.store.storage_path, auto_save=False)
            if not persisted.storage_path.is_file() and self.settings is not None:
                persisted._merge_json_records(load_app_records(self.settings))
            persisted.remove(path)
            persisted.save()
            if self.settings is not None:
                save_app_records(self.settings, [r.to_json() for r in persisted.records()])
        except OSError as error:
            self.status.setText(("Не удалось удалить: " if self.lang == "ru" else "Could not remove: ") + str(error))
            return
        self._records.pop(key)
        # Other tabs may show the same executable (or several of its PIDs).
        self._populating = True
        try:
            for listing in self._lists.values():
                for row in range(listing.count()):
                    other = listing.item(row)
                    if self._key(other.data(Qt.ItemDataRole.UserRole)) == key:
                        other.setCheckState(Qt.CheckState.Unchecked)
        finally:
            self._populating = False
        self._load_files()
        parent = self.parent()
        if parent and hasattr(parent, "on_traffic_applications_changed"):
            parent.on_traffic_applications_changed()

    def accept(self):
        try:
            # Build once and atomically publish once, not twice for every listed PID.
            self.store._records.clear()
            self.store._merge_json_records(self._records.values())
            self.store.save()
            if self.settings is not None:
                save_app_records(self.settings, list(self._records.values()))
        except OSError as error:
            self.status.setText("Не удалось сохранить: " + str(error))
            return
        parent = self.parent()
        if parent and hasattr(parent, "on_traffic_applications_changed"):
            parent.on_traffic_applications_changed()
        self.done(QDialog.DialogCode.Accepted)

    def done(self, result):
        self._closed = True
        self._render_timer.stop()
        self._copy_timer.stop()
        try:
            self._icons.shutdown()
        except Exception:
            pass
        # Enumeration can finish safely after this dialog is destroyed.
        for worker in self._workers:
            try:
                worker.snapshot.disconnect(self._snapshot_ready)
            except (TypeError, RuntimeError):
                pass
        self._workers.clear()
        super().done(result)
