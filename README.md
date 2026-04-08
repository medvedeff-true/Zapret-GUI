## [Русский](#русский) | [English](#english)

## Русский
# Zapret GUI

**Zapret GUI** — это простая графическая оболочка для обхода интернет-блокировок с помощью утилиты Zapret ([Оригинальное приложение](https://github.com/bol-van/zapret)).  
Создано на Python + PyQt6.

![Анимация](https://github.com/user-attachments/assets/6de56a16-5ca8-4d79-a579-10d9ca5f4ca4)

<img width="616" height="568" alt="press-release2" src="https://github.com/user-attachments/assets/03ed73f7-685c-4046-bc54-a480f6c5e81b" />

---

## 🛠 Последние обновления

- **Отдельный слой пользовательских списков**: Добавлен выделенный слой для пользовательских списков сайтов, который сохраняется при обновлениях ядра, чтобы ваши домены не терялись.
- **Система слияния списков**: Реализована бесшовная система слияния списков ядра и пользователя для избежания дубликатов и поддержания порядка.
- **Валидация доменов**: Улучшена обработка доменов и сайтов с лучшей валидацией, нормализацией и поддержкой различных форматов, таких как URL, JSON и CSV.
- **Синхронизация списков Flowseal**: Добавлена эффективная синхронизация списков Flowseal с проверкой хешей, обновляющая только при наличии изменений.
- **Улучшенный процесс обновления**: Переработан процесс обновления файлов доменов для определения локальных версий, синхронизации списков даже при актуальности, сохранения пользовательских данных и предоставления более ясных сообщений о статусе.
- **Защита пользовательских данных**: Пользовательские директории теперь исключаются из очистки директории приложения, защищая ваши настройки.
- **Сохранение результатов автотеста**: Добавлено сохранение результатов автотеста профилей для удобства справки и устранения неисправностей.
- **Расширенная диагностика автотеста**: Увеличено логирование и анализ ошибок для лучшей отладки проблем с профилями.
- **Модуль UI Менеджера сайтов**: Новый инструмент в приложении для просмотра и редактирования пользовательских списков сайтов прямо в GUI.
- **Обновленные инструкции**: Расширены инструкции в приложении, включая использование нового Менеджера сайтов.
- **Быстрые действия в трее**: Добавлены ярлыки в системном трее для открытия Менеджера сайтов и быстрого добавления доменов в списки.
- **Обновленные зависимости**: Обновлены импорты и модули для поддержки новых функций.

> ## ⚠️ **Если у вас возникают какие-то проблемы с запуском новой версии, удалите полностью папку **ZapretGUI** по пути **C:\Users\user** и перезапустите программу**

---

➕ **Начиная с версии 1.6.0 добавлен автоматический подбор профиля, чтобы это активировать нажмите на значок** <img width="50" height="47" alt="image" src="https://github.com/user-attachments/assets/ab1baaaa-4da1-4cc6-892f-a9d39a1c1a02" />

![Анимация2](https://github.com/user-attachments/assets/bd1a677e-ba71-4666-8c25-daeb005bbd8b)
<img width="387" height="552" alt="{76777BE7-4C31-4FFE-8774-A06166E97935}" src="https://github.com/user-attachments/assets/4ca91776-0c79-4809-97ad-46f9eb9cb9a4" />

> ⚠️ **Автоподбор не панацея!** Функция была написана на скорую руку, без глубокого тестирования, поэтому на некоторых провайдерах могут быть баги и неверный результат. Если у вас в итоге не выдаёт ни одного рабочего профиля, всё равно попробуйте сами вручную поискать рабочий.

➕ **Изменена логика проверки обновления, теперь она проверяет только релизы из репозитория [Flowseal]([https://github.com/Flowseal/zapret-discord-youtube](https://github.com/Flowseal/zapret-discord-youtube)). Теперь если у Flowseal вышла новая версия, вы просто можете нажать на кнопку "Проверить обновления" в настройках программы и она скачается с заменой профилей**

---

## 🧩 Возможности

- ✅ Запуск и остановка в один клик
- 🌐 Предустановленные профили (Flowseal Core) для разных методов обхода
- 🧠 Автоматический запуск обхода при выборе/переключении профиля
- 🛠 Полноценная работа в трее: сворачивание обычной кнопкой окна, управление профилями и состоянием из трея
- 🔄 Сброс соединений winws и остановка служб прямо из GUI (через `uninstall.bat`)
- 🔁 Проверка обновлений и обновление Core (Flowseal) прямо из настроек + отображение версий GUI/Core
- 🌍 Выбор языка: русский и английский
- 🖥 Автозапуск и запуск в свернутом виде

---

## 📦 Установка

Установка не требуется. Просто:

1. Скачайте последний релиз `Zapret_GUI.exe` из раздела [Releases](https://github.com/medvedeff-true/Zapret-GUI/releases/tag/v1.7.0)
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
6. Чтобы проверить обновления Core (Flowseal) — откройте настройки и нажмите **Проверить обновления**
7. Если нужно полностью оборвать соединения winws/остановить службы — нажмите **Сбросить соединения winws** (откроется консоль, дойдёт до `Success`, подождёт 5 секунд и закроется)

> Всё подробно описано в инструкции внутри программы. Если что-то непонятно — откройте инструкцию и следуйте шагам.

---

## 🖥️Системные требования
- OS: Windows 10 (x64) и выше (На 7/8 смотреть [Issue](https://github.com/medvedeff-true/Zapret-GUI/issues/10))
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

## English
# Zapret GUI

**Zapret GUI** is a simple graphical interface for bypassing internet restrictions using pre-configured profiles (like `General`, `Discord`, etc.).  
Built on Python + PyQt6. One-click launch, multi-language support, no installation required.

![Анимация](https://github.com/user-attachments/assets/6de56a16-5ca8-4d79-a579-10d9ca5f4ca4)

<img width="616" height="568" alt="press-release2" src="https://github.com/user-attachments/assets/03ed73f7-685c-4046-bc54-a480f6c5e81b" />

---

## 🛠 Latest Updates

- **Separate User Lists Layer**: Added a dedicated user layer for site lists that survives core updates, ensuring your custom domains aren't lost.
- **List Merging System**: Implemented seamless merging of core and user lists to avoid duplicates and keep everything organized.
- **Domain Validation**: Enhanced handling of domains and sites with better validation, normalization, and support for various formats like URLs, JSON, and CSV.
- **Flowseal Lists Synchronization**: Added efficient syncing of Flowseal lists with hash-based checks, updating only when changes occur.
- **Improved Update Process**: Redesigned domain file updates to detect local versions, sync lists even when up-to-date, preserve user data during updates, and provide clearer status messages.
- **User Data Protection**: User directories are now excluded from app directory wipes, protecting your custom settings.
- **Autotest Results Saving**: Introduced saving of autoprofile test results for easier reference and troubleshooting.
- **Enhanced Autotest Diagnostics**: Expanded logging and error analysis for better debugging of profile issues.
- **Site Manager UI Module**: New in-app tool for viewing and editing user site lists directly through the GUI.
- **Updated Instructions**: Expanded in-app guidance to include how to use the new Site Manager.
- **Tray Quick Actions**: Added shortcuts in the system tray to open the Site Manager and quickly add domains to lists.
- **Updated Dependencies**: Added necessary imports and modules to support the new features.

> ## ⚠️ **If you experience any issues running the new version, completely delete the `ZapretGUI` folder located at `C:\Users\user` and restart the program**

---

➕ **Starting from version 1.6.0, automatic profile selection was added. To activate it, click the icon** <img width="50" height="47" alt="image" src="https://github.com/user-attachments/assets/ab1baaaa-4da1-4cc6-892f-a9d39a1c1a02" />

![Анимация2](https://github.com/user-attachments/assets/bd1a677e-ba71-4666-8c25-daeb005bbd8b)
<img width="387" height="552" alt="{76777BE7-4C31-4FFE-8774-A06166E97935}" src="https://github.com/user-attachments/assets/4ca91776-0c79-4809-97ad-46f9eb9cb9a4" />

> ⚠️ **Auto-selection is not a silver bullet!** The feature was implemented quickly without deep testing, so there may be bugs or incorrect results on some providers. If no working profile is found, try selecting one manually.

➕ **Update check logic has been changed. It now checks only releases from the [Flowseal](https://github.com/Flowseal/zapret-discord-youtube) repository. If a new version of Flowseal is available, simply click "Check for updates" in the program settings and it will download and replace the profiles automatically.**

---

## 🧩 Features

- ✅ One-click start/stop
- 🌐 Prebuilt bypass profiles (Flowseal Core) for different strategies
- 🧠 Auto-start bypass when selecting/switching a profile
- 🛠 Full tray support: minimize-to-tray using the standard window minimize button, tray controls for status and profiles
- 🔄 Reset winws connections and stop services прямо from GUI (via `uninstall.bat`)
- 🔁 Core (Flowseal) update check & update from Settings + GUI/Core version display
- 🌍 Language switch: Russian and English
- 🖥 Autostart support and start minimized

---

## 📦 Installation

No installation required. Just:

1. Download the latest `Zapret_GUI.exe` file from [Releases](https://github.com/medvedeff-true/Zapret-GUI/releases/tag/v1.7.0)
2. Run it (optionally as administrator)

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

