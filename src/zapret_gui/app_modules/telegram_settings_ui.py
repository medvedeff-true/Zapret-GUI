# --- Telegram Desktop proxy settings ---------------------------------------

class TelegramModeSettingsDialog(StyledDialog):
    def __init__(self, parent):
        super().__init__(parent)
        self.owner = parent
        self.ru = parent.lang == "ru"
        title = self._text("Настройки Telegram Mode", "Telegram Mode settings")
        self.setWindowTitle(title)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setMinimumSize(450, 360)
        self.setStyleSheet(_app_dialog_stylesheet() + """
            QScrollArea, QWidget#TelegramSettingsForm { background: transparent; border: none; }
            QGroupBox {
                color: #f2f2f2; border: 1px solid #343d39; border-radius: 9px;
                margin-top: 12px; padding: 10px 8px 6px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 4px; }
            QLineEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox {
                background: #202523; color: #f1f1f1; border: 1px solid #49534d;
                border-radius: 6px; padding: 4px 6px; min-height: 20px;
            }
            QCheckBox:disabled, QLineEdit:disabled { color: #9a9a9a; }
        """)
        frame = _make_window_root_layout(self)
        self.install_title_bar(frame, title)
        layout = _make_window_content_layout(frame, self, margins=(14, 10, 14, 12), spacing=9)

        actions = QHBoxLayout()
        self.restart_btn = self._button("Перезапустить прокси", "Restart proxy", lambda: self._apply("restart"))
        self.open_btn = self._button("Открыть в Telegram", "Open in Telegram", lambda: self._apply("open"))
        actions.addWidget(self.restart_btn, 1)
        actions.addWidget(self.open_btn, 1)
        layout.addLayout(actions)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        form = QWidget()
        form.setObjectName("TelegramSettingsForm")
        scroll.setWidget(form)
        body = QVBoxLayout(form)
        body.setContentsMargins(0, 0, 6, 0)
        body.setSpacing(10)
        layout.addWidget(scroll, 1)

        connection = self._group(body, "Подключение MTProto", "MTProto connection")
        self.host = QLineEdit()
        self.host.setMaxLength(46)
        self.port = self._number(1, 65535)
        connection.addRow(self._text("IP-адрес", "IP address"), self.host)
        connection.addRow(self._text("Порт", "Port"), self.port)
        self.secret = QLineEdit()
        self.secret.setMaxLength(34)
        secret_row = QHBoxLayout()
        secret_row.addWidget(self.secret, 1)
        secret_row.addWidget(self._button("Новый ключ", "New key", lambda: self.secret.setText(os.urandom(16).hex())))
        connection.addRow(self._text("Ключ", "Secret"), secret_row)
        self._hint(
            connection,
            "Для Telegram на этом ПК оставьте 127.0.0.1. Адрес 0.0.0.0 открывает прокси и для других устройств сети.",
            "Keep 127.0.0.1 for Telegram on this PC. 0.0.0.0 also exposes the proxy to other devices on the network.",
        )

        dc = self._group(body, "Дата-центры Telegram (DC → IP)", "Telegram data centers (DC → IP)")
        self.dc_rules = QPlainTextEdit()
        self.dc_rules.setFixedHeight(82)
        dc.addRow(self.dc_rules)
        self._hint(
            dc, "По одному правилу номер:IPv4 на строку. Пустое поле отключает прямые WebSocket-маршруты.",
            "One number:IPv4 rule per line. Leave blank to disable direct WebSocket routes.",
        )

        cf = self._group(body, "Cloudflare Proxy", "Cloudflare Proxy")
        self.cf_enabled = self._check(cf, "Включить CF-прокси", "Enable CF proxy")
        self.h2_media = self._check(cf, "Мультиплексирование медиа (HTTP/2)", "HTTP/2 media multiplexing")
        self.custom_cf = self._check(cf, "Использовать свои домены", "Use custom domains")
        self.cf_domains = QLineEdit()
        cf.addRow(self.cf_domains)
        self._hint(
            cf, "Без своих доменов используется автоматический список Flowseal. Домены вводятся через запятую.",
            "Uses Flowseal's automatic list unless custom domains are enabled. Separate domains with commas.",
        )

        worker = self._group(body, "Cloudflare Worker", "Cloudflare Worker")
        self.custom_worker = self._check(worker, "Использовать свои Worker-домены", "Use custom Worker domains")
        self.worker_domains = QLineEdit()
        worker.addRow(self.worker_domains)
        self._hint(worker, "Укажите домены уже настроенных Worker через запятую.",
                   "Enter the domains of your configured Workers, separated by commas.")

        tuning = self._group(body, "Логи и производительность", "Logging and performance")
        self.verbose = self._check(tuning, "Подробное логирование", "Verbose logging")
        self.disable_tls = self._check(tuning, "Выключить TLS для CF-прокси и Worker", "Disable TLS for CF proxy and Workers")
        self.buffer_kib = self._number(32, 4096)
        self.pool_size = self._number(0, 32)
        self.log_max_mb = QDoubleSpinBox()
        self.log_max_mb.setRange(0.1, 100.0)
        self.log_max_mb.setSingleStep(0.5)
        self.log_max_mb.setDecimals(1)
        tuning.addRow(self._text("Размер буфера, КБ", "Buffer size, KiB"), self.buffer_kib)
        tuning.addRow(self._text("Пул WebSocket-сессий", "WebSocket pool size"), self.pool_size)
        tuning.addRow(self._text("Макс. размер лога, МБ", "Max log size, MB"), self.log_max_mb)
        self._hint(
            tuning, "Пул 0 отключает предварительные соединения. Без TLS HTTP/2 не используется. Лог: logs/telegram-proxy.log.",
            "Pool size 0 disables preconnections. HTTP/2 is unavailable without TLS. Log: logs/telegram-proxy.log.",
        )

        self.manual_btn = self._button("Как подключить вручную?", "How to connect manually?", self.show_manual)
        self.reset_btn = self._button("Сбросить настройки", "Reset settings", self.reset_settings)
        body.addWidget(self.manual_btn)
        body.addWidget(self.reset_btn)

        self.status = QLabel()
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.hide()
        layout.addWidget(self.status)
        buttons = QHBoxLayout()
        self.save_btn = self._button("Сохранить", "Save", lambda: self._apply("save"))
        buttons.addWidget(self.save_btn, 1)
        buttons.addWidget(self._button("Закрыть", "Close", self.close), 1)
        layout.addLayout(buttons)
        for box in (self.cf_enabled, self.custom_cf, self.custom_worker, self.disable_tls):
            box.toggled.connect(self._update_fields)
        self._load_fields(_get_telegram_proxy_options(parent.settings))
        self.resize(530, 650)

    def _text(self, ru, en):
        return ru if self.ru else en

    def _button(self, ru, en, callback):
        button = QPushButton(self._text(ru, en))
        button.setAutoDefault(False)
        button.clicked.connect(callback)
        return button

    def _group(self, layout, ru, en):
        group = QGroupBox(self._text(ru, en))
        form = QFormLayout(group)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        layout.addWidget(group)
        return form

    def _check(self, form, ru, en):
        check = QCheckBox(self._text(ru, en))
        form.addRow(check)
        return check

    def _hint(self, form, ru, en):
        label = QLabel(self._text(ru, en))
        label.setWordWrap(True)
        label.setStyleSheet("color: #b8c4bd;")
        form.addRow(label)

    @staticmethod
    def _number(minimum, maximum):
        field = QSpinBox()
        field.setRange(minimum, maximum)
        return field

    def _update_fields(self):
        cf = self.cf_enabled.isChecked()
        self.custom_cf.setEnabled(cf)
        self.cf_domains.setEnabled(cf and self.custom_cf.isChecked())
        self.h2_media.setEnabled(cf and not self.disable_tls.isChecked())
        self.worker_domains.setEnabled(self.custom_worker.isChecked())

    def _load_fields(self, options):
        self.host.setText(options.host)
        self.port.setValue(options.port)
        self.secret.setText(options.secret)
        self.dc_rules.setPlainText("\n".join(options.dc_rules))
        self.cf_domains.setText(", ".join(options.cf_domains))
        self.worker_domains.setText(", ".join(options.worker_domains))
        for name in ("cf_enabled", "h2_media", "custom_cf", "custom_worker", "verbose", "disable_tls"):
            getattr(self, name).setChecked(getattr(options, name))
        for name in ("buffer_kib", "pool_size", "log_max_mb"):
            getattr(self, name).setValue(getattr(options, name))
        self._update_fields()

    def _options(self):
        if not self.secret.text().strip():
            raise ValueError(self._text("Введите ключ MTProto или нажмите «Новый ключ».",
                                        "Enter an MTProto secret or click New key."))
        return TelegramProxyOptions(
            host=self.host.text(), port=self.port.value(), secret=self.secret.text(),
            dc_rules=tuple(self.dc_rules.toPlainText().splitlines()),
            cf_enabled=self.cf_enabled.isChecked(), h2_media=self.h2_media.isChecked(),
            custom_cf=self.custom_cf.isChecked(), cf_domains=self.cf_domains.text(),
            custom_worker=self.custom_worker.isChecked(), worker_domains=self.worker_domains.text(),
            verbose=self.verbose.isChecked(), disable_tls=self.disable_tls.isChecked(),
            buffer_kib=self.buffer_kib.value(), pool_size=self.pool_size.value(),
            log_max_mb=self.log_max_mb.value(),
        )

    def _set_status(self, message, *, error=False):
        self.status.setStyleSheet("color: #ffad9e;" if error else "color: #a3e8b4;")
        self.status.setText(message)
        self.status.setVisible(bool(message))

    def show_error(self, message):
        self._set_status(message, error=True)

    def show_open_error(self):
        self.show_error(self._text("Не удалось открыть ссылку в Telegram. Подключитесь вручную.",
                                   "Could not open Telegram. Connect manually instead."))

    def reset_settings(self):
        # Restore the original per-installation secret as well as routing
        # defaults, so an existing Telegram entry can be used again.
        secret = str(self.owner.settings.value(TELEGRAM_MODE_PROXY_SECRET_KEY, "") or "")
        if not re.fullmatch(r"(?:dd)?[0-9a-f]{32}", secret, re.IGNORECASE):
            secret = _get_telegram_proxy_options(self.owner.settings).secret
        self._load_fields(TelegramProxyOptions(secret=secret))
        self._apply("save")

    def _apply(self, action):
        try:
            options = self._options()
            self._set_status("")
            if self.owner.apply_telegram_proxy_settings(options, action):
                self._set_status(self._text("Запускаем прокси…", "Starting proxy…"))
            elif not self.status.text():
                self._set_status(self._text("Настройки сохранены.", "Settings saved."))
        except (ValueError, RuntimeError) as error:
            self.show_error(str(error))

    def proxy_restarted(self):
        self._set_status(self._text("Прокси запущен, настройки применены.", "Proxy started with the new settings."))

    def show_manual(self):
        try:
            options = self._options()
        except (ValueError, RuntimeError) as error:
            self.show_error(str(error))
            return
        heading = self._text(
            "Сначала примените настройки и включите Telegram Mode.\n\n"
            "Telegram Desktop → Настройки → Тип соединения → Использовать собственный прокси → MTProto.",
            "Apply the settings and enable Telegram Mode first.\n\n"
            "Telegram Desktop → Settings → Connection type → Use custom proxy → MTProto.",
        )
        values = self._text(
            f"Сервер: {options.client_host}\nПорт: {options.port}\nКлюч: dd{options.secret}",
            f"Server: {options.client_host}\nPort: {options.port}\nSecret: dd{options.secret}",
        )
        message = QMessageBox(self)
        message.setWindowTitle(self._text("Как подключить вручную?", "How to connect manually?"))
        message.setTextFormat(Qt.TextFormat.PlainText)
        message.setText(f"{heading}\n\n{values}")
        message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse | Qt.TextInteractionFlag.TextSelectableByKeyboard)
        message.addButton(QMessageBox.StandardButton.Ok)
        message.exec()
