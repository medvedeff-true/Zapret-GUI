## [Русский](#русский) | [English](#english)

## Русский
# Zapret GUI

**Zapret GUI** — это простая графическая оболочка для обхода интернет-блокировок с помощью утилиты Zapret ([Оригинальное приложение](https://github.com/bol-van/zapret)).  
Создано на Python + PyQt6.

<img width="1920" height="770" alt="press-release" src="https://github.com/user-attachments/assets/d0d91f48-87ab-48b7-92a5-30607930835d" />

<img width="616" height="568" alt="press-release2" src="https://github.com/user-attachments/assets/03ed73f7-685c-4046-bc54-a480f6c5e81b" />

---

## 🛠 Последние обновления

➕ **Изменена кнопка включения и добавлена анимация**

![Анимация](https://github.com/user-attachments/assets/bc996461-b3dc-4f43-9668-a224bf919700)

➕ **Исправлена логика индикаторов**
- 🟢 Обход включён → зелёный  
- 🔴 Обход выключен → красный  
- Добавлены разные иконки трея для состояния ON/OFF (tray-on / tray-off)

➕ **Полноценная работа в трее**
- Кнопка "Свернуть" теперь прячет приложение в трей точно также, как и кнопка <img width="31" height="31" alt="{A6289449-C895-4648-84F3-CBE5A5B09E94}" src="https://github.com/user-attachments/assets/5e9cb844-c172-4cbc-beef-0e5bdd30cde3" />
- В панели задач не остаётся лишних окон  

➕ **Автоматическое включение при выборе профиля**
- При выборе профиля обход запускается автоматически  

➕ **Обновлена версия Core**
- Текущая стратегия обновлена и работает "из коробки" на версии [Flowseal 1.9.7](https://github.com/Flowseal/zapret-discord-youtube/releases/tag/1.9.7)

➕ **Исправлена сортировка профилей**
- Реализована натуральная сортировка
- `(ALT)` отображается выше `(ALT2)`, `(ALT3)` и т.д.  

➕ **Исправлена система проверки обновлений Core**
- Текущая версия Core сохраняется в `settings.ini`  
- После обновления версия корректно обновляется и отображается  

➕ **Добавлено отображение версий**
  `Версия GUI: X.X.X, Версия Core: X.X.X`  

➕ **Исправлена кнопка "Сбросить соединения winws"**
- Скрипт `uninstall.bat` больше не зависит от перезатираемой папки `core`  

➕ **Повышена стабильность сборки**
- Исправлен краш на первом запуске (безопасная обработка `.app_version`)  

> ## ⚠️ **Если у вас возникают какие-то проблемы с запуском новой версии, удалите полностью папку **ZapretGUI** по пути **C:\Users\user** и перезапустите программу**

---

➕ **Начиная с версии 1.6.0 добавлен автоматический подбор профиля, чтобы это активировать нажмите на значок** <img width="50" height="47" alt="image" src="https://github.com/user-attachments/assets/ab1baaaa-4da1-4cc6-892f-a9d39a1c1a02" />

<img width="1005" height="732" alt="press-release3" src="https://github.com/user-attachments/assets/80a49fb5-7b67-49de-bdda-0ccf245d45f6" />

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
- OS: Windows 10 (x64) и выше (На 7/8 теоретически возможно, но не тестировалась)
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

<img width="1920" height="770" alt="press-release" src="https://github.com/user-attachments/assets/d0d91f48-87ab-48b7-92a5-30607930835d" />

<img width="616" height="568" alt="press-release2" src="https://github.com/user-attachments/assets/03ed73f7-685c-4046-bc54-a480f6c5e81b" />

---

## 🛠 Latest Updates

➕ **Indicator logic fixed**
- 🟢 Bypass enabled → green  
- 🔴 Bypass disabled → red  
- Added separate tray icons for ON/OFF state (tray-on / tray-off)

➕ **Full tray functionality**
- The "Minimize" button now hides the application to the tray, just like the button <img width="31" height="31" alt="{A6289449-C895-4648-84F3-CBE5A5B09E94}" src="https://github.com/user-attachments/assets/5e9cb844-c172-4cbc-beef-0e5bdd30cde3" />
- No extra windows remain in the taskbar  

➕ **Automatic enable on profile selection**
- Selecting a profile automatically starts the bypass  

➕ **Core version updated**
- The current strategy has been updated and works "out of the box" with [Flowseal 1.9.6](https://github.com/Flowseal/zapret-discord-youtube/releases/tag/1.9.6)

➕ **Profile sorting improved**
- Natural sorting implemented  
- `(ALT)` is displayed above `(ALT2)`, `(ALT3)`, etc.  

➕ **Core update system fixed**
- Current Core version is stored in `settings.ini`  
- After updating, the version is correctly saved and displayed  

➕ **Version display added**
  `GUI Version: X.X.X, Core Version: X.X.X`  

➕ **"Reset winws connections" button fixed**
- The `uninstall.bat` script no longer depends on the overwritten `core` directory  

➕ **Build stability improved**
- Fixed crash on first launch (safe handling of `.app_version`)  

> ## ⚠️ **If you experience any issues running the new version, completely delete the `ZapretGUI` folder located at `C:\Users\user` and restart the program**

---

➕ **Starting from version 1.6.0, automatic profile selection was added. To activate it, click the icon** <img width="50" height="47" alt="image" src="https://github.com/user-attachments/assets/ab1baaaa-4da1-4cc6-892f-a9d39a1c1a02" />

<img width="1005" height="732" alt="press-release3" src="https://github.com/user-attachments/assets/80a49fb5-7b67-49de-bdda-0ccf245d45f6" />

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

