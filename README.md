<div align="center">
   
[![Boosty](https://img.shields.io/badge/Поддержать-Boosty-orange?style=for-the-badge)](https://boosty.to/medvedeff)
## [Ru](#rus) | [En](#eng)

<a name="rus"></a>
<img width="443,5" height="86" alt="logoreadme" src="https://github.com/user-attachments/assets/76dc2441-f9e0-4357-b2da-1a0408688079" />

**Zapret GUI** — это простая графическая оболочка для обхода интернет-блокировок с помощью утилиты [Zapret](https://github.com/bol-van/zapret)  
Создано на Python + PyQt6.

</div>

> [!Caution]
>
> #### У меня нет youtube каналов, я не заливаю ZapretGUI на форумы или файлообменники. Программа распространяется **только на [GitHub](https://github.com/medvedeff-true/Zapret-GUI/releases) и в моём [Boosty](https://boosty.to/medvedeff)**. Не качайте ZapretGUI с других сайтов, это могут быть вирусные сборки.

<img width="1065" height="484" alt="Анимация228" src="https://github.com/user-attachments/assets/966f47d1-259d-426d-a7d7-460e1f0ee627" />

<div align="center">
   
<img width="358" height="390" alt="tray" src="https://github.com/user-attachments/assets/be193b84-adb9-4fad-860b-9a34edf20205" />

</div>

---

<details>
<summary><strong>🛠 Последние обновления <img width="19" height="20" alt="277031mbmmfoabln" src="https://github.com/user-attachments/assets/6161bda3-fa90-40be-8e71-c077bf96af9d" /> тык чтобы развернуть</strong></summary>

# 3.0.0

## ✨ Что нового

## Полный рефакторинг и новая архитектура

Версия 3.0.0 — это не просто обновление интерфейса. Внутренняя часть приложения полностью переработана: большая legacy-логика перенесена из монолитного файла в отдельные модули и новую структуру.

> Подробное описание новой структуры можно посмотреть в разделе [Структура проекта](#struct)

### Автоподбор профиля нового поколения

- Добавлен режим создания **новой адаптивной стратегии** под конкретное подключение.
- Адаптивный поиск проверяет доступность YouTube и Discord по отдельной матрице HTTPS/HTTP3-проб и формирует bat файл только с необходимыми методами обхода.
- Готовый профиль сохраняется в пользовательский каталог и сразу готов к использованию.

### Что ещё добавлено

- Добавлена полноценная работа с пользовательскими bat конфигурациями, их загрузка и использование, а также автоматическая сборка собственного профиля с нуля (описано выше).
- Добавлена собственная служба Background service `ZapretGUI.Service.exe` для операций, требующих повышенных прав. (В перспективе это должно исправлять все проблемы с повисающими окнаи cmd, скрывать их).
- Обновлены lifecycle single-instance, запуск из трея, автозапуск, остановка обхода и повторное подключение к helper-службе.
- Runtime-обновление переведено на staging/backup/rollback с сохранением.
- Повторный запуск программы через exe или значок на панели задач, когда Zapret GUI уже запущен и свёрнут в трей, больше не кричит ошибкой, а просто разворачивает прогу из трея.
- Поиск обновлений теперь сам останавливает обход и делает сброс соединений winws, если возникают проблемы. В некоторых редких случаях всё же могут оставаться проблемы, поэтому кнопка сброса winws не удалена (да и в целом она полезна, когда возникают любые проблемы с обходом, просто жмите её, перезапускайтесь и будет вам счастье).
- Все вторичные функции (Telegram proxy, Ai DNS, Game mode) обновлены до последних версий.
- Добавлены различные regression-тесты для сетевых проверок, генератора BAT и атомарной публикации, background service и прочих.

## Исправлено

- Гонки и зависания при остановке `winws` и background service.
- Повторный запуск обхода без orphan-процессов.
- Синхронизация состояний главного окна, профиля и трея.
- Выпадание списка профилей за экран, при просмотре через трей.
- Ошибка при завершении работы Windows с запущенным обходом.
- Ошибка когда окно обхода могло появиться при его выключении и остаться работать.
- различные мелкие проблемы.

# 2.1.1

### Добавлен отдельный режим для Telegram.

<img width="69" height="44" alt="{A8A7F8AB-0144-4001-BA1E-DE7431F9D748}" src="https://github.com/user-attachments/assets/404ea57a-e504-4105-988f-317dfb00a94c" />

Теперь Telegram Desktop можно разблокировать вместе с web версией.  
Для этого нажмите на кнопку в виде логотипа Telegram.

<img width="1146" height="640" alt="telegram" src="https://github.com/user-attachments/assets/10efe408-a8b4-43d8-ab05-6a9cf06235f3" />

За метод спасибо [Flowseal](https://github.com/Flowseal/tg-ws-proxy)

---

### Добавлен новый дизайн для всего приложения

<img width="1065" height="484" alt="Анимация228" src="https://github.com/user-attachments/assets/cf0dad01-7aa3-4087-8768-f48d6ae19ba8" />

Обновлена визуальная составляющая всех окон.

---

⚠️Если возникают проблемы с запуском, удалите полностью папку **ZapretGUI** по пути **C:\Users\user** и перезапустите программу. И внесите в исключения антивируса ZapretGUI.exe и всю папку **ZapretGUI** по пути **C:\Users\user**

</details>

---

## 🧩 Возможности

- ✅ Запуск и остановка в один клик
- 🌐 Предустановленные профили (Flowseal Core) для разных методов обхода
- 🎮 Игровой режим с настройкой TCP/UDP-фильтров и обхода игровых сервисов
- 📡 Менеджер доменов и IP для удобного управления заблокированными сайтами и подсетями
- 🧩 Адаптивное создание профиля с учётом особенностей вашего подключения
- 📄 Полная поддержка пользовательских `.bat`-конфигураций и создания собственных профилей с нуля
- 🛡 Фоновая служба для операций, требующих повышенных прав
- ♻️ Безопасное обновление runtime с поддержкой staging, резервного копирования и rollback
- 🤖 AI DNS для доступа к нейросетям без VPN
- 💥 Разблокировка Telegram Desktop и Web
- 🔄 Автоматическое обновление игровых списков
- 🧠 Автоматический запуск обхода при выборе/переключении профиля
- 🗂 Улучшенная работа с пользовательскими списками
- 🛠 Полноценная работа в трее: сворачивание обычной кнопкой окна, управление профилями, функциями и состоянием из трея
- 🔄 Сброс соединений winws и остановка служб прямо из GUI
- 🔁 Проверка обновлений и обновление Core (Flowseal) / Gui прямо из настроек + отображение версий GUI/Core
- 🌍 Выбор языка: русский и английский
- 🖥 Автозапуск и запуск в свернутом виде

---

## 📦 Установка

Установка не требуется. Просто:

1. Скачайте последний релиз `Zapret_GUI.zip` из раздела [Releases](https://github.com/medvedeff-true/Zapret-GUI/releases) и разархивируйте в любое удобное место
2. Запустите файл `Zapret_GUI.exe` (при необходимости — от имени администратора)

> ⚠️ Если Windows выдаёт предупреждение, нажмите **Подробнее → Всё равно запустить**

---

## 🚀 Как пользоваться

1. Выберите профиль из выпадающего списка
2. Нажмите круглую кнопку:
   - 🔴 Красная — обход выключен (нажатие включает)
   - 🟢 Зелёная — обход включён (нажатие выключает)
3. При переключении профиля обход включится автоматически (или перезапустится на новом профиле)
4. Чтобы свернуть приложение в трей — нажмите обычную кнопку **Свернуть (—)**, окно исчезнет из панели задач и останется только значок в трее
5. Чтобы открыть окно обратно — нажмите на значок в трее
6. Чтобы проверить обновления — откройте настройки и нажмите **Проверить обновления**
7. Если нужно полностью оборвать соединения winws/остановить службы — нажмите **Сбросить соединения winws** (откроется консоль, дойдёт до `Success`, подождёт 5 секунд и закроется)

> Всё подробно описано в инструкции внутри программы. Если что-то непонятно — откройте инструкцию и следуйте шагам.

### Краткая обучалка как добавить свой сайт в обход:

<img width="1146" height="640" alt="add" src="https://github.com/user-attachments/assets/f194234c-0467-44f5-bd68-b3186505f194" />

### Краткий показ как включить обход Telegram

<img width="1146" height="640" alt="telegram" src="https://github.com/user-attachments/assets/810c3ea4-2dbf-41bc-93db-40d24fb25bdb" />

---

## 💡Структура проекта

<a name="struct"></a>

<details>
<summary><strong>Полное описание структуры <img width="19" height="20" alt="277031mbmmfoabln" src="https://github.com/user-attachments/assets/6161bda3-fa90-40be-8e71-c077bf96af9d" /> нажми на меня</strong></summary>

#### `EzUnBlock.py`

**Назначение:** основной совместимый launcher приложения.

**Содержимое:** добавляет каталог `src` в Python path, импортирует `zapret_gui.app` и вызывает `main()` при обычном запуске. При импорте под именем `EzUnBlock` предоставляет namespace приложения, который используется существующими интеграциями и тестами.

### Пакет `src/zapret_gui`

#### `src/__init__.py`

**Назначение:** package marker корневого каталога исходников.

**Содержимое:** позволяет инструментам Python и тестам однозначно воспринимать `src` как пакетное пространство проекта.

#### `src/zapret_gui/__init__.py`

**Назначение:** объявление пакета ZapretGUI.

**Содержимое:** минимальная инициализация package namespace без запуска интерфейса и побочных операций.

#### `src/zapret_gui/__main__.py`

**Назначение:** запуск приложения командой `python -m zapret_gui`.

**Содержимое:** импортирует `main` из `app.py` и передаёт ему управление.

#### `src/zapret_gui/app.py`

**Назначение:** центральная точка сборки Python-приложения.

**Содержимое:** импортирует системные и Qt-зависимости, adaptive strategy API, Telegram controller и IPC-клиент службы. Затем в установленном порядке загружает файлы из `app_modules` в единый namespace. Для PyInstaller определяет путь к встроенным модулям через `_MEIPASS`, а для запуска из исходников использует каталог рядом с `app.py`.

#### `src/zapret_gui/telegram_proxy.py`

**Назначение:** управление локальным MTProto-прокси для Telegram Mode.

**Содержимое:** класс `TelegramProxyController`, запуск proxy event loop в отдельном потоке, настройка порта и secret, ожидание готовности, корректная остановка, генерация Telegram proxy-ссылки и получение статистики подключений. Ошибки запуска преобразуются в `TelegramProxyError` и передаются интерфейсу.

### Модули `src/zapret_gui/app_modules`

#### `app_config.py`

**Назначение:** единая конфигурация приложения.

**Содержимое:** версия ZapretGUI, пути к runtime и пользовательским данным, URL репозиториев и обновлений, ключи QSettings, интервалы фоновых проверок, параметры игрового и Telegram-режимов, имена пользовательских и runtime-списков, настройки AI DNS и фиксированные адреса Telegram Web.

#### `runtime_setup.py`

**Назначение:** установка и миграция portable runtime.

**Содержимое:** выбор каталога `%USERPROFILE%\ZapretGUI` или пути из CLI, копирование встроенных ресурсов, проверка доступности файлов, расчёт SHA-256, резервное копирование пользовательских стратегий, staged-обновление управляемых каталогов и rollback при ошибке. Также создаёт и обновляет маркер версии runtime.

#### `ui_base.py`

**Назначение:** базовые функции и классы интерфейса.

**Содержимое:** единый Qt-стиль, цвета, геометрия окон, центрирование, скруглённые маски, отрисовка фона, custom title bar, базовый `StyledDialog`, текстовый диалог и вспомогательные функции для запуска, автозагрузки и подготовки BAT-файлов.

#### `runtime_data.py`

**Назначение:** работа с локальными данными приложения.

**Содержимое:** чтение и запись результатов стандартного и adaptive-автоподбора, атомарная запись файлов, нормализация пользовательских списков, подготовка runtime-данных, сохранение информации о последней стратегии и вспомогательные операции с настройками режимов.

#### `dns_service.py`

**Назначение:** реализация AI DNS и безопасной работы с системным `hosts`.

**Содержимое:** загрузка и объединение DNS-источников, фильтрация записей, резервное копирование `hosts`, добавление управляемых секций, восстановление исходного состояния, определение текущего статуса, обработка прав доступа и исправление сетевой доступности приложения после изменения DNS-записей.

#### `list_management.py`

**Назначение:** управление доменными и IP-списками для `winws`.

**Содержимое:** синхронизация Flowseal и игровых списков, проверка доменов/IP/подсетей, импорт значений из текста и файлов, устранение дублей, сборка итоговых runtime-списков, применение параметров игрового режима, разбор BAT-профилей и формирование команд запуска `winws`.

#### `updates.py`

**Назначение:** обновление GUI, Core и связанных компонентов.

**Содержимое:** проверка версий GitHub releases, валидация скачанных архивов и SHA-256, staged-замена Core, сохранение пользовательских стратегий, portable-обновление EXE, запуск update helper, восстановление после ошибки, обновление инструкций интерфейса и обработка пропущенной версии.

#### `dialogs_and_workers.py`

**Назначение:** диалоги настроек и фоновые задачи.

**Содержимое:** `SettingsDialog`, а также QThread workers для стандартного и adaptive-автоподбора, обновления списков, AI DNS, первичной настройки runtime, запуска и остановки обхода, обновления release, перезапуска игрового режима и переключения Telegram Mode. Workers передают результат в GUI через Qt signals и не блокируют основной поток.

#### `adaptive_ui.py`

**Назначение:** интерфейс двух режимов автоподбора.

**Содержимое:** анимированная визуализация поиска, выбор режима, экран перебора стандартных стратегий, экран adaptive-поиска, прогресс и ETA, отмена операции, ввод имени BAT-профиля, карточка результата, обработка ошибок и переходы между страницами диалога.

#### `ui_controls.py`

**Назначение:** переиспользуемые элементы интерфейса.

**Содержимое:** анимированная кнопка включения обхода, переключатели, checkbox, стабильный popup для combo box, переключатель стандартных и пользовательских профилей, delegate пользовательского списка, кнопки действий, segmented control, clickable label и элементы менеджера сайтов.

#### `site_manager.py`

**Назначение:** управление пользовательскими доменами, IP и игровыми фильтрами.

**Содержимое:** окно менеджера сайтов, добавление и исключение доменов/IP, проверка введённых значений, импорт списков, tutorial-диалог и настройки игрового режима с выбором TCP/UDP-фильтров и состава обхода.

#### `main_window.py`

**Назначение:** главное окно и координация пользовательских действий.

**Содержимое:** создание главного интерфейса, загрузка профилей, переключение стандартного и пользовательского источника, запуск/остановка обхода, меню трея, прокручиваемый список профилей, AI DNS, Telegram Mode, игровой режим, автоподбор, импорт/переименование/удаление профилей, синхронизация индикаторов и обработка результатов workers.

#### `application_lifecycle.py`

**Назначение:** жизненный цикл процесса ZapretGUI.

**Содержимое:** single-instance mutex, сигнал восстановления уже запущенного окна, обработка CLI-действий с повышенными правами, запуск после обновления, автозагрузка, восстановление окна из трея, системное завершение Windows, очистка ресурсов и функция `main()`, создающая QApplication и MainWindow.

#### `app_modules/__init__.py`

**Назначение:** объявление набора модулей интерфейса.

**Содержимое:** документация о загрузке файлов в совместимый namespace и об их включении в one-file сборку как PyInstaller data.

#### `app_modules/README.md`

**Назначение:** техническая памятка о порядке загрузки модулей.

**Содержимое:** точная последовательность исполнения файлов `app_modules`, причины сохранения общего namespace и особенности упаковки этих файлов в PyInstaller.

### Пакет `src/adaptive_strategy`

#### `adaptive_strategy/__init__.py`

**Назначение:** публичный API adaptive-подсистемы.

**Содержимое:** экспортирует `SearchEngine`, `SearchOutcome`, `RuntimePaths`, генератор BAT, функции разбора целей и валидации имени стратегии.

#### `models.py`

**Назначение:** модели данных adaptive-поиска.

**Содержимое:** перечисление протоколов, описания целей и стратегий, результаты отдельных проб и кандидатов, итог `SearchOutcome`, параметры обязательности целей и функции проверки прохождения probe matrix.

#### `catalog.py`

**Назначение:** каталог доступных методов обхода.

**Содержимое:** набор HTTPS и HTTP3-стратегий, группы методов, уровни риска и приоритета, аргументы `winws`, ссылки на fake payload-файлы и выбор кандидатов для конкретного протокола и сервиса.

#### `hostlist.py`

**Назначение:** подготовка hostlist для adaptive-кандидатов.

**Содержимое:** расширение целевых доменов, определение сервиса по hostname, группировка целей по профилям, формирование списков хостов для запуска `winws` и подготовка DNS/hosts overrides.

#### `probe.py`

**Назначение:** выполнение сетевых проверок.

**Содержимое:** разбор списка целей, DNS с ограничением времени, HTTPS-проверки с идентификацией URL и validator, HTTP3/QUIC-проверки через встроенные helpers, Telegram WebSocket-пробы, повтор transient failures, отмена и формирование `ProbeResult`.

#### `runtime.py`

**Назначение:** управление процессами adaptive runtime.

**Содержимое:** класс `RuntimePaths`, проверка требуемых файлов, формирование аргументов `winws`, запуск процесса без лишнего окна, остановка дерева процессов, поиск конфликтующих средств обхода и проверка работоспособности bundled helpers.

#### `engine.py`

**Назначение:** основной алгоритм создания адаптивной стратегии.

**Содержимое:** preflight DNS, baseline-проверки, перебор кандидатов по группам сервисов, повтор обязательных неудачных проб, выбор лучших методов, объединение профилей, несколько раундов финальной валидации, расчёт confidence, прогресс операции и корректная отмена.

#### `generator.py`

**Назначение:** создание готового пользовательского BAT-профиля.

**Содержимое:** нормализация имени, проверка запрещённых символов и Windows device names, защита от коллизий без учёта регистра, генерация аргументов `winws`, добавление служебных маркеров ZapretGUI, атомарная запись и проверка BAT через реальный Windows command parser.

#### `resources.py`

**Назначение:** установка adaptive runtime в пользовательский каталог.

**Содержимое:** чтение manifest, проверка размеров и SHA-256, повторное использование исправных файлов, восстановление повреждённых компонентов, удаление устаревших generated-файлов и проверка полного состава runtime.

### Фоновая служба

#### `src/bypass_service.py`

**Назначение:** непривилегированный клиент `ZapretGUI.Service.exe`.

**Содержимое:** формирование безопасного profile request, чтение локальных файлов профиля от имени пользователя, length-framed JSON IPC, аутентификация процесса службы, установка helper через UAC, подключение к named pipe, запуск/остановка `winws`, snapshot состояния и восстановление соединения после ошибки.

#### `tools/background_service/Service.cs`

**Назначение:** Windows-служба, запускающая `winws` с повышенными правами.

**Содержимое:** named pipe server с ACL пользователя, проверка протокола и fingerprint движка, whitelist параметров, создание временных файлов из IPC payload, запуск процесса в Job Object, сбор stdout/stderr, остановка дерева процессов и встроенные операции для управляемых Telegram hosts.

#### `tools/background_service/build.py`

**Назначение:** сборка helper-службы.

**Содержимое:** поиск системного C# compiler, извлечение доверенного Telegram hosts mapping из конфигурации, добавление его как embedded resource и компиляция `Service.cs` в `resources/background_service/ZapretGUI.Service.exe`.

### Встроенный Telegram proxy

#### `src/tg_ws_proxy_vendor/__init__.py`

**Назначение:** объявление vendored-пакета Flowseal tg-ws-proxy.

**Содержимое:** package marker для включения proxy-модулей в приложение.

#### `src/tg_ws_proxy_vendor/LICENSE`

**Назначение:** лицензия встроенного Flowseal tg-ws-proxy.

**Содержимое:** условия распространения и использования vendored-кода Telegram proxy.

#### `proxy/__init__.py`

**Назначение:** публичные данные proxy-пакета.

**Содержимое:** версия vendored proxy и экспорт конфигурации, разбора DC-адресов и служебных функций.

#### `proxy/tg_ws_proxy.py`

**Назначение:** основной сервер локального MTProto-прокси.

**Содержимое:** чтение MTProto handshake, определение Telegram DC, управление WebSocket connection pool, маршрутизация клиентов, fallback-сценарии, async server lifecycle и запуск proxy loop.

#### `proxy/bridge.py`

**Назначение:** передача трафика между Telegram-клиентом и удалённым transport.

**Содержимое:** контексты шифрования, разбиение сообщений, WebSocket/TCP bridge, fallback через Cloudflare proxy или прямой TCP, учёт переданных данных и обработка закрытия соединений.

#### `proxy/config.py`

**Назначение:** конфигурация Telegram proxy.

**Содержимое:** адрес, порт, secret, список DC, Cloudflare proxy domains, загрузка актуального списка доменов и периодическое обновление балансировщика.

#### `proxy/raw_websocket.py`

**Назначение:** низкоуровневый WebSocket transport.

**Содержимое:** HTTP upgrade handshake, кодирование и декодирование WebSocket frames, masking, socket options, чтение/запись binary payload и обработка redirect/error статусов.

#### `proxy/fake_tls.py`

**Назначение:** Fake TLS transport для маскировки MTProto-соединения.

**Содержимое:** проверка ClientHello, формирование ServerHello, TLS records, потоковое чтение/запись за TLS-обёрткой и перенаправление неподходящего соединения на masking domain.

#### `proxy/balancer.py`

**Назначение:** распределение Telegram DC по доступным proxy-доменам.

**Содержимое:** хранение списка доменов, выбор домена для каждого DC и смена маршрута при ошибках соединения.

#### `proxy/stats.py`

**Назначение:** статистика Telegram proxy.

**Содержимое:** счётчики активных и завершённых соединений, WebSocket/TCP fallback, ошибок, объёма трафика и попаданий в connection pool.

#### `proxy/utils.py`

**Назначение:** общие MTProto-константы и функции.

**Содержимое:** размеры ключей и handshake, protocol tags, запрещённые сигнатуры, форматирование объёма данных и разбор link host.

### Сборка и упаковка

#### `tools/build_release.py`

**Назначение:** официальный release-builder ZapretGUI.

**Содержимое:** сборка background service, preflight ресурсов, проверка версии, manifest и adaptive runtime, контроль запущенного EXE, вызов PyInstaller one-file/noconsole, создание `ZapretGUI-3.0.0.zip`, проверка архива и запись SHA-256.

#### `packaging/ZapretGUI.spec`

**Назначение:** поддерживаемая конфигурация PyInstaller.

**Содержимое:** entry point, data-файлы, hidden imports, ресурсы Core, adaptive runtime, helper-служба, Qt-зависимости, иконка и version resource.

### Тесты

#### `tests/__init__.py`

**Назначение:** package marker набора тестов.

**Содержимое:** обеспечивает импорт тестовых модулей через `python -m unittest` и прямой запуск отдельных test cases.

#### `tests/test_adaptive_gui.py`

Проверяет страницы автоподбора, ETA, заголовки, ввод имени, success/error UI, мини-игру, пользовательские профили и прокручиваемое меню трея.

#### `tests/test_adaptive_engine_hardening.py`

Проверяет retry policy, обязательность результатов, HTTPS/HTTP3 identity, Telegram alternatives, DNS preflight и финальную многократную валидацию.

#### `tests/test_adaptive_generator.py`

Проверяет имена BAT, Windows device names, коллизии, атомарную публикацию, содержимое профиля и прохождение аргументов через Windows command parser.

#### `tests/test_adaptive_resources_engine.py`

Проверяет установку adaptive runtime, восстановление повреждённых файлов, helpers, специализированные baseline-пробы и отмену во время retry.

#### `tests/test_adaptive_targets_catalog.py`

Проверяет состав целей, отсутствие дублей, probe matrix, каталоги ALT-кандидатов и подстановку payload-файлов.

#### `tests/test_bypass_service.py`

Проверяет JSON IPC, безопасность аргументов и файлов, повторный запуск, остановку дерева процессов, падение helper и dry-run стандартных профилей.

#### `tests/test_ezunblock_lifecycle.py`

Проверяет runtime migration и rollback, обновление GUI/Core, single-instance, autostart, shutdown, синхронизацию списков и восстановление service pipe.

#### `tests/manual_service_smoke.py`

Выполняет ручную opt-in проверку установленной Windows-службы и WinDivert с несколькими циклами запуска и остановки.

### Документация

#### `docs/background-service.md`

**Назначение:** техническое описание фоновой службы.

**Содержимое:** расположение исходников и готового helper, порядок его сборки, модель JSON IPC, правила проверки запросов и связь службы с Python-клиентом.

### Пользовательские и runtime-данные

Пользовательские данные находятся в `%USERPROFILE%\ZapretGUI\user`:

- `adaptive-strategies` — созданные и импортированные BAT-профили;
- `strategy-backups` — резервные копии пользовательских стратегий;
- `adaptive-runtime` — локальный runtime автоподбора;
- `adaptive-search-last.json` — подробный отчёт последнего поиска;
- пользовательские доменные и IP-списки.

Управляемые папки `core`, `flags` и `background_service` валидируются и обновляются отдельно. Миграция сначала готовит новую версию во временном каталоге, проверяет критические файлы, сохраняет пользовательские стратегии и только потом заменяет runtime. При ошибке выполняется rollback.

Фоновая служба принимает ограниченные JSON-команды через IPC, самостоятельно проверяет исполняемый файл и аргументы, запускает `winws` без консольного окна и завершает всё дерево процесса при остановке или потере клиента.

### Сборка 3.0 из исходников

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\build_release.py --preflight
.\.venv\Scripts\python.exe tools\build_release.py
```

</details>

---

## ❤️ Поддержать проект

Поддержать автора и развитие Zapret-GUI: [Boosty](https://boosty.to/medvedeff)

Tron(TRC20) - TQJTGJjN5kNF6ZWoRvyFb1mBnDge6PLELg

BTC - 12v3ZMUk9XiAUT6DTBuBrGArEbUAeFhCwr

ETH - 0x5467629d742aee0161f59d67f32cf4cbd7d68bc2

TON - UQA5vNFPw88m1y7yO2VuIO_CVvOu1845wHZ3msuuGGlb2rUn

---

## 🖥️Системные требования

- OS: Windows 10 (x64) и выше
- CPU: 2 ядра (любые современные Intel/AMD)
- RAM: 2 GB
- Место на диске: ~150 MB

---

## 🌐 Оригинальные репозитории

### 1. [Zapret](https://github.com/bol-van/zapret)

### 2. [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube)

### 3. [Winsw](https://github.com/winsw/winsw)

---

### ⚠️В случае введения юридических или технических ограничений со стороны провайдеров или государственных органов, автор не несёт ответственности за последствия использования этой утилиты. Скачивая приложение, Вы соглашаетесь с этим.

---

<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>
<br>

<div align="center">

[![Boosty](https://img.shields.io/badge/Support-Boosty-orange?style=for-the-badge)](https://boosty.to/medvedeff)

<a name="eng"></a>
<img width="443,5" height="86" alt="logoreadme" src="https://github.com/user-attachments/assets/76dc2441-f9e0-4357-b2da-1a0408688079" />

**Zapret GUI** is a simple graphical interface for bypassing internet restrictions using pre-configured profiles (like `General`, `Discord`, etc.).  
Built on Python + PyQt6. One-click launch, multi-language support, no installation required.

</div>

<img width="1065" height="484" alt="Анимация228" src="https://github.com/user-attachments/assets/966f47d1-259d-426d-a7d7-460e1f0ee627" />

<div align="center">
   
<img width="358" height="390" alt="tray" src="https://github.com/user-attachments/assets/be193b84-adb9-4fad-860b-9a34edf20205" />

</div>

---

<details>
<summary><strong>🛠 Latest Updates</strong></summary>

# 3.0.0

## ✨ What's New

## Complete Refactoring and New Architecture

Version 3.0.0 is more than just an interface update. The application's internal structure has been completely reworked: much of the legacy logic has been moved from a monolithic file into separate modules and a new project structure.

> A detailed overview of the new structure is available in the [Project Structure](#structen) section.

### Next-Generation Adaptive Profile Selection

- Added a mode for creating a **new adaptive strategy** tailored to a specific connection.
- The adaptive search checks YouTube and Discord availability using a separate HTTPS/HTTP3 test matrix, then generates a `.bat` file containing only the required bypass methods.
- The finished profile is saved to the custom profiles directory and is ready to use immediately.

### Other Additions

- Added full support for custom `.bat` configurations: loading and using them, as well as automatically building a custom profile from scratch (described above).
- Added a dedicated `ZapretGUI.Service.exe` background service for operations requiring elevated privileges. In the future, this should resolve issues with hanging CMD windows and keep them hidden.
- Updated the single-instance lifecycle, tray startup, autostart, bypass stopping, and reconnection to the helper service.
- Runtime updates now use a staging/backup/rollback system with preservation of existing data.
- Launching the program again via the `.exe` file or taskbar icon while Zapret GUI is already running in the tray no longer shows an error—it simply restores the application window.
- Update checks now automatically stop the bypass and reset winws connections if issues occur. In some rare cases, problems may still persist, so the winws reset button has been kept. It is also generally useful whenever bypass-related issues occur: click it, restart the application, and everything should work properly.
- All secondary features (Telegram Proxy, AI DNS, and Game Mode) have been updated to their latest versions.
- Added various regression tests for network checks, the BAT generator, atomic publishing, the background service, and more.

## Fixed

- Race conditions and freezes when stopping `winws` and the background service.
- Restarting the bypass without leaving orphan processes behind.
- Synchronization issues between the main window, selected profile, and tray state.
- The profile list appearing outside the screen when viewed from the tray.
- An error that occurred when Windows was shut down while the bypass was running.
- An issue where the bypass window could appear while stopping it and remain running.
- Various minor issues.

# 2.1.1

## ✨ Whats new

### Add special function for unblock Telegram with mtproto proxy.

<img width="69" height="44" alt="{A8A7F8AB-0144-4001-BA1E-DE7431F9D748}" src="https://github.com/user-attachments/assets/404ea57a-e504-4105-988f-317dfb00a94c" />

<img width="1146" height="640" alt="telegram" src="https://github.com/user-attachments/assets/10efe408-a8b4-43d8-ab05-6a9cf06235f3" />

Special thanks [Flowseal](https://github.com/Flowseal/tg-ws-proxy)

---

### New design of app

<img width="1065" height="484" alt="Анимация228" src="https://github.com/user-attachments/assets/cf0dad01-7aa3-4087-8768-f48d6ae19ba8" />

---

⚠️If there are problems with the startup, delete the entire **ZapretGUI** folder along the way **C:\Users\user ** and restart the program. And add antivirus exceptions. ZapretGUI.exe and the entire **ZapretGUI** folder along the way**C:\Users\user**

</details>

---

## 🧩 Features

- ✅ One-click start/stop
- 🌐 Prebuilt bypass profiles (Flowseal Core) for different strategies
- 🎮 Gaming mode with configurable TCP/UDP filters and bypass options for gaming services
- 📡 IP Manager for convenient IP and subnet management
- 🤖 AI DNS for accessing AI services without a VPN
- 💥 Unblock Telegram Desktop and Web
- 🔄 Automatic updates for gaming blocklists
- 🧠 Auto-start bypass when selecting/switching a profile
- 🗂 Improved support for user-managed lists
- 🛠 Full tray support: minimize-to-tray using the standard window minimize button, tray controls for status and profiles
- 🔄 Reset winws connections and stop services directly from the GUI (via `uninstall.bat`)
- 🔁 Core (Flowseal) update check & update from Settings + GUI/Core version display
- 🌍 Language switch: Russian and English
- 🖥 Autostart support and start minimized
- 🧩 Adaptive profile generation tailored to your connection
- 📄 Full support for custom `.bat` configurations and creating custom profiles from scratch
- 🛡 Background service for operations requiring elevated privileges
- ♻️ Safe runtime updates with staging, backup, and rollback support

---

## 📦 Installation

No installation required. Just:

1. Download the latest `Zapret_GUI.zip` file from [Releases](https://github.com/medvedeff-true/Zapret-GUI/releases) and extract
2. Run `Zapret_GUI.exe` (optionally as administrator)

> ⚠️ If Windows warns you, click **More info → Run anyway**

---

## 🚀 How to use

1. Pick a profile from the dropdown
2. Click the round button:
   - 🔴 Red — bypass is OFF (click to turn ON)
   - 🟢 Green — bypass is ON (click to turn OFF)
3. Switching a profile will auto-enable bypass (or restart it on the new profile)
4. To minimize to tray — use the standard **Minimize (—)** button; the app will disappear from the taskbar and stay in the tray only
5. To restore the window — click the tray icon
6. To check/update Core (Flowseal) — open Settings and click **Check updates**
7. To fully reset winws connections / stop services — click **Reset winws connections** (a console window will show progress, reach `Success`, wait 5 seconds, then close)

> Detailed instructions are available inside the app. If something is unclear — open the in-app guide and follow the steps.

---

## 💡 Project Structure

<a name="structen"></a>

<details>
<summary><strong>Full structure description <img width="19" height="20" alt="277031mbmmfoabln" src="https://github.com/user-attachments/assets/6161bda3-fa90-40be-8e71-c077bf96af9d" /> click me</strong></summary>

#### `EzUnBlock.py`

**Purpose:** the main compatible application launcher.

**Contents:** adds the `src` directory to the Python path, imports `zapret_gui.app`, and calls `main()` during normal startup. When imported as `EzUnBlock`, it exposes the application namespace used by existing integrations and tests.

### `src/zapret_gui` package

#### `src/__init__.py`

**Purpose:** package marker for the root source directory.

**Contents:** allows Python tools and tests to unambiguously treat `src` as the project's package namespace.

#### `src/zapret_gui/__init__.py`

**Purpose:** declares the ZapretGUI package.

**Contents:** minimal package namespace initialization without launching the interface or performing side effects.

#### `src/zapret_gui/__main__.py`

**Purpose:** launches the application via `python -m zapret_gui`.

**Contents:** imports `main` from `app.py` and transfers control to it.

#### `src/zapret_gui/app.py`

**Purpose:** the central assembly point of the Python application.

**Contents:** imports system and Qt dependencies, the adaptive strategy API, the Telegram controller, and the service IPC client. It then loads files from `app_modules` into a shared namespace in a defined order. For PyInstaller, it determines the path to bundled modules via `_MEIPASS`; when running from source, it uses the directory next to `app.py`.

#### `src/zapret_gui/telegram_proxy.py`

**Purpose:** manages the local MTProto proxy for Telegram Mode.

**Contents:** the `TelegramProxyController` class, proxy event-loop startup in a separate thread, port and secret configuration, readiness waiting, graceful shutdown, Telegram proxy-link generation, and connection statistics retrieval. Startup errors are converted into `TelegramProxyError` and passed to the interface.

### `src/zapret_gui/app_modules` modules

#### `app_config.py`

**Purpose:** centralized application configuration.

**Contents:** ZapretGUI version, runtime and user-data paths, repository and update URLs, QSettings keys, background-check intervals, Game Mode and Telegram Mode parameters, custom and runtime list names, AI DNS settings, and fixed Telegram Web addresses.

#### `runtime_setup.py`

**Purpose:** installation and migration of the portable runtime.

**Contents:** selects the `%USERPROFILE%\ZapretGUI` directory or a CLI-provided path, copies bundled resources, checks file availability, calculates SHA-256 hashes, backs up user strategies, performs staged updates of managed directories, and rolls back on failure. It also creates and updates the runtime version marker.

#### `ui_base.py`

**Purpose:** base interface classes and functions.

**Contents:** unified Qt styling, colors, window geometry, centering, rounded masks, background rendering, a custom title bar, the base `StyledDialog`, text dialog, and helper functions for startup, autostart, and BAT-file preparation.

#### `runtime_data.py`

**Purpose:** manages local application data.

**Contents:** reads and writes standard and adaptive profile-selection results, performs atomic file writes, normalizes custom lists, prepares runtime data, stores information about the last strategy, and provides helper operations for mode settings.

#### `dns_service.py`

**Purpose:** implements AI DNS and safe handling of the system `hosts` file.

**Contents:** downloads and merges DNS sources, filters entries, backs up `hosts`, adds managed sections, restores the original state, determines the current status, handles permission issues, and restores application network access after changing DNS records.

#### `list_management.py`

**Purpose:** manages domain and IP lists for `winws`.

**Contents:** synchronizes Flowseal and game lists, validates domains, IPs, and subnets, imports values from text and files, removes duplicates, builds final runtime lists, applies Game Mode settings, parses BAT profiles, and generates `winws` launch commands.

#### `updates.py`

**Purpose:** updates the GUI, Core, and related components.

**Contents:** checks GitHub Releases versions, validates downloaded archives and SHA-256 hashes, performs staged Core replacement, preserves user strategies, updates the portable EXE, launches the update helper, restores the previous state after errors, updates interface instructions, and handles skipped versions.

#### `dialogs_and_workers.py`

**Purpose:** settings dialogs and background tasks.

**Contents:** `SettingsDialog`, along with QThread workers for standard and adaptive profile selection, list updates, AI DNS, initial runtime setup, bypass startup and shutdown, release updates, Game Mode restarts, and Telegram Mode switching. Workers send results to the GUI via Qt signals and do not block the main thread.

#### `adaptive_ui.py`

**Purpose:** interface for the two profile-selection modes.

**Contents:** animated search visualization, mode selection, standard strategy iteration screen, adaptive search screen, progress and ETA, operation cancellation, BAT-profile name input, result card, error handling, and transitions between dialog pages.

#### `ui_controls.py`

**Purpose:** reusable interface components.

**Contents:** animated bypass toggle button, switches, checkbox, stable combo-box popup, standard/custom profile switcher, custom list delegate, action buttons, segmented control, clickable label, and site-manager controls.

#### `site_manager.py`

**Purpose:** manages custom domains, IPs, and game filters.

**Contents:** site manager window, adding and excluding domains/IPs, input validation, list import, tutorial dialog, and Game Mode settings with TCP/UDP filter and bypass composition selection.

#### `main_window.py`

**Purpose:** the main window and coordination of user actions.

**Contents:** creates the main interface, loads profiles, switches between standard and custom sources, starts/stops the bypass, manages the tray menu, provides a scrollable profile list, AI DNS, Telegram Mode, Game Mode, profile selection, profile import/rename/delete, indicator synchronization, and worker-result handling.

#### `application_lifecycle.py`

**Purpose:** ZapretGUI process lifecycle.

**Contents:** single-instance mutex, signal for restoring an already running window, handling elevated CLI actions, post-update startup, autostart, restoring the window from the tray, Windows shutdown handling, resource cleanup, and the `main()` function that creates `QApplication` and `MainWindow`.

#### `app_modules/__init__.py`

**Purpose:** declares the interface module set.

**Contents:** documentation on loading files into a compatible namespace and including them in a one-file build as PyInstaller data.

#### `app_modules/README.md`

**Purpose:** technical reference for the module loading order.

**Contents:** the exact execution sequence of `app_modules` files, reasons for preserving a shared namespace, and details of packaging these files with PyInstaller.

### `src/adaptive_strategy` package

#### `adaptive_strategy/__init__.py`

**Purpose:** public API of the adaptive subsystem.

**Contents:** exports `SearchEngine`, `SearchOutcome`, `RuntimePaths`, the BAT generator, target parsing functions, and strategy-name validation.

#### `models.py`

**Purpose:** data models for adaptive search.

**Contents:** protocol enumeration, target and strategy definitions, individual probe and candidate results, final `SearchOutcome`, target requirement parameters, and functions for checking probe-matrix success.

#### `catalog.py`

**Purpose:** catalog of available bypass methods.

**Contents:** HTTPS and HTTP3 strategies, method groups, risk and priority levels, `winws` arguments, links to fake payload files, and candidate selection for a particular protocol and service.

#### `hostlist.py`

**Purpose:** prepares hostlists for adaptive candidates.

**Contents:** expands target domains, identifies a service by hostname, groups targets by profiles, generates host lists for launching `winws`, and prepares DNS/hosts overrides.

#### `probe.py`

**Purpose:** performs network checks.

**Contents:** parses the target list, performs time-limited DNS resolution, HTTPS checks with URL and validator identification, HTTP3/QUIC checks through built-in helpers, Telegram WebSocket probes, retries transient failures, handles cancellation, and produces `ProbeResult`.

#### `runtime.py`

**Purpose:** manages adaptive runtime processes.

**Contents:** the `RuntimePaths` class, required-file checks, `winws` argument generation, process startup without an extra window, process-tree termination, detection of conflicting bypass tools, and checks for bundled helper availability.

#### `engine.py`

**Purpose:** the core algorithm for creating an adaptive strategy.

**Contents:** DNS preflight, baseline checks, candidate iteration by service groups, retries for failed mandatory probes, selection of the best methods, profile merging, multiple final-validation rounds, confidence calculation, operation progress, and graceful cancellation.

#### `generator.py`

**Purpose:** creates a finished custom BAT profile.

**Contents:** name normalization, validation of forbidden characters and Windows device names, case-insensitive collision protection, `winws` argument generation, ZapretGUI service marker insertion, atomic writing, and BAT validation through the real Windows command parser.

#### `resources.py`

**Purpose:** installs the adaptive runtime into the user directory.

**Contents:** reads the manifest, checks file sizes and SHA-256 hashes, reuses valid files, restores damaged components, removes obsolete generated files, and verifies the complete runtime contents.

### Background Service

#### `src/bypass_service.py`

**Purpose:** unprivileged client for `ZapretGUI.Service.exe`.

**Contents:** generates safe profile requests, reads local profile files as the current user, implements length-framed JSON IPC, authenticates the service process, installs the helper through UAC, connects to the named pipe, starts/stops `winws`, retrieves state snapshots, and restores the connection after an error.

#### `tools/background_service/Service.cs`

**Purpose:** Windows service that launches `winws` with elevated privileges.

**Contents:** named-pipe server with user ACLs, protocol and engine-fingerprint validation, parameter whitelist, temporary-file creation from IPC payloads, process launch in a Job Object, stdout/stderr collection, process-tree termination, and built-in operations for managed Telegram hosts.

#### `tools/background_service/build.py`

**Purpose:** builds the helper service.

**Contents:** locates the system C# compiler, extracts the trusted Telegram hosts mapping from configuration, adds it as an embedded resource, and compiles `Service.cs` into `resources/background_service/ZapretGUI.Service.exe`.

### Bundled Telegram Proxy

#### `src/tg_ws_proxy_vendor/__init__.py`

**Purpose:** declares the vendored Flowseal tg-ws-proxy package.

**Contents:** package marker for including proxy modules in the application.

#### `src/tg_ws_proxy_vendor/LICENSE`

**Purpose:** license for the bundled Flowseal tg-ws-proxy.

**Contents:** distribution and usage terms for the vendored Telegram proxy code.

#### `proxy/__init__.py`

**Purpose:** public proxy package metadata.

**Contents:** bundled proxy version and exports for configuration, DC-address parsing, and helper functions.

#### `proxy/tg_ws_proxy.py`

**Purpose:** main local MTProto proxy server.

**Contents:** reads the MTProto handshake, detects the Telegram DC, manages the WebSocket connection pool, routes clients, handles fallback scenarios, manages the async server lifecycle, and runs the proxy loop.

#### `proxy/bridge.py`

**Purpose:** transfers traffic between the Telegram client and remote transport.

**Contents:** encryption contexts, message splitting, WebSocket/TCP bridge, fallback through a Cloudflare proxy or direct TCP, transferred-data accounting, and connection-close handling.

#### `proxy/config.py`

**Purpose:** Telegram proxy configuration.

**Contents:** address, port, secret, DC list, Cloudflare proxy domains, loading the current domain list, and periodic balancer updates.

#### `proxy/raw_websocket.py`

**Purpose:** low-level WebSocket transport.

**Contents:** HTTP upgrade handshake, WebSocket frame encoding and decoding, masking, socket options, binary payload reading/writing, and redirect/error status handling.

#### `proxy/fake_tls.py`

**Purpose:** Fake TLS transport for disguising the MTProto connection.

**Contents:** ClientHello validation, ServerHello generation, TLS records, streaming reads/writes through the TLS wrapper, and redirecting unsuitable connections to a masking domain.

#### `proxy/balancer.py`

**Purpose:** distributes Telegram DCs across available proxy domains.

**Contents:** stores the domain list, selects a domain for each DC, and changes routes when connection errors occur.

#### `proxy/stats.py`

**Purpose:** Telegram proxy statistics.

**Contents:** counters for active and completed connections, WebSocket/TCP fallback usage, errors, traffic volume, and connection-pool hits.

#### `proxy/utils.py`

**Purpose:** shared MTProto constants and functions.

**Contents:** key and handshake sizes, protocol tags, forbidden signatures, data-volume formatting, and link-host parsing.

### Build and Packaging

#### `tools/build_release.py`

**Purpose:** official ZapretGUI release builder.

**Contents:** builds the background service, performs resource preflight checks, verifies the version, manifest, and adaptive runtime, checks for a running EXE, invokes PyInstaller one-file/noconsole mode, creates `ZapretGUI-3.0.0.zip`, verifies the archive, and writes its SHA-256 hash.

#### `packaging/ZapretGUI.spec`

**Purpose:** maintained PyInstaller configuration.

**Contents:** entry point, data files, hidden imports, Core resources, adaptive runtime, helper service, Qt dependencies, icon, and version resource.

### Tests

#### `tests/__init__.py`

**Purpose:** test-suite package marker.

**Contents:** enables importing test modules through `python -m unittest` and direct execution of individual test cases.

#### `tests/test_adaptive_gui.py`

Tests profile-selection pages, ETA, headings, name input, success/error UI, the mini-game, custom profiles, and the scrollable tray menu.

#### `tests/test_adaptive_engine_hardening.py`

Tests retry policy, mandatory-result requirements, HTTPS/HTTP3 identity, Telegram alternatives, DNS preflight, and final repeated validation.

#### `tests/test_adaptive_generator.py`

Tests BAT names, Windows device names, collisions, atomic publishing, profile contents, and argument parsing through the Windows command parser.

#### `tests/test_adaptive_resources_engine.py`

Tests adaptive-runtime installation, damaged-file restoration, helpers, specialized baseline probes, and cancellation during retries.

#### `tests/test_adaptive_targets_catalog.py`

Tests target composition, duplicate prevention, the probe matrix, ALT candidate catalogs, and payload-file substitution.

#### `tests/test_bypass_service.py`

Tests JSON IPC, argument and file security, repeated startup, process-tree termination, helper failure, and dry-run execution of standard profiles.

#### `tests/test_ezunblock_lifecycle.py`

Tests runtime migration and rollback, GUI/Core updates, single-instance behavior, autostart, shutdown, list synchronization, and service-pipe restoration.

#### `tests/manual_service_smoke.py`

Performs an opt-in manual check of the installed Windows service and WinDivert using several start/stop cycles.

### Documentation

#### `docs/background-service.md`

**Purpose:** technical documentation for the background service.

**Contents:** source and built-helper locations, build procedure, JSON IPC model, request-validation rules, and the service's integration with the Python client.

### User and Runtime Data

User data is stored in `%USERPROFILE%\ZapretGUI\user`:

- `adaptive-strategies` — created and imported BAT profiles;
- `strategy-backups` — backups of custom strategies;
- `adaptive-runtime` — local runtime for adaptive profile selection;
- `adaptive-search-last.json` — detailed report of the latest search;
- custom domain and IP lists.

The managed `core`, `flags`, and `background_service` directories are validated and updated separately. Migration first prepares the new version in a temporary directory, verifies critical files, preserves custom strategies, and only then replaces the runtime. If an error occurs, rollback is performed.

The background service accepts restricted JSON commands through IPC, independently validates the executable and arguments, starts `winws` without a console window, and terminates the entire process tree when stopped or when the client connection is lost.

### Building Version 3.0 from Source

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-build.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools\build_release.py --preflight
.\.venv\Scripts\python.exe tools\build_release.py
```

</details>

---

## ❤️ Support project

You can support the author and Zapret-GUI: [Boosty](https://boosty.to/medvedeff)

Tron(TRC20) - TQJTGJjN5kNF6ZWoRvyFb1mBnDge6PLELg

BTC - 12v3ZMUk9XiAUT6DTBuBrGArEbUAeFhCwr

ETH - 0x5467629d742aee0161f59d67f32cf4cbd7d68bc2

TON - UQA5vNFPw88m1y7yO2VuIO_CVvOu1845wHZ3msuuGGlb2rUn

---

## 🖥️System Requirements

- OS: Windows 10 (x64) and higher
- CPU: 2 cores (any modern Intel/AMD)
- RAM: 2 GB
- Disk space: ~150 MB

---

## 🌐 Original repositories

### 1. [Zapret](https://github.com/bol-van/zapret)

### 2. [zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube)

### 3. [Winsw](https://github.com/winsw/winsw)

---

### ⚠️In case of legal or technical restrictions imposed by providers or governmental authorities, the author is not responsible for the consequences of using this utility. By downloading the application, you agree to this.
