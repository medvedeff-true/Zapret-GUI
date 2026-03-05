## [Русский](#русский) | [English](#english)

## Русский
# Zapret GUI

**Zapret GUI** — это простая графическая оболочка для обхода интернет-блокировок с помощью утилиты Zapret ([Оригинальное приложение](https://github.com/bol-van/zapret)).  
Создано на Python + PyQt6.

![Анимация](https://github.com/user-attachments/assets/6de56a16-5ca8-4d79-a579-10d9ca5f4ca4)

<img width="616" height="568" alt="press-release2" src="https://github.com/user-attachments/assets/03ed73f7-685c-4046-bc54-a480f6c5e81b" />

---

## 🛠 Последние обновления

### ➕ Изменён внешний вид Авто-подбора профилей, добавлен стилизованный анимированный прогрессбар
![Анимация2](https://github.com/user-attachments/assets/6c376b42-47ed-4a16-bb8d-5fd917a35f7b)

### ➕ Исправлено сравнение версий Core (Flowseal)
Теперь обновление определяется не только для 1.9.7, но и для тегов с суффиксами/текстом (например 1.9.7b, 1.9.7 beta).

### ➕ Защита от редиректа в браузер при запуске профилей.
При запуске батников из GUI выставляется NO_UPDATE_CHECK=1, из-за чего service.bat check_updates не выполняется и браузер не открывается.

### ➕ Корректное определение текущей версии Core из встроенных файлов
При первом запуске/после вайпа версия Core берётся из core/service.bat (LOCAL_VERSION=...) и сохраняется в settings, чтобы не было ложного обновления core, если он уже встроен в EXE.

### ➕ То же поведение для автотеста/диагностики
В автотесте и диагностическом прогоне тоже выставляется NO_UPDATE_CHECK=1, чтобы нигде не всплывал редирект/проверка обновлений.

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

![Анимация](https://github.com/user-attachments/assets/6de56a16-5ca8-4d79-a579-10d9ca5f4ca4)

<img width="616" height="568" alt="press-release2" src="https://github.com/user-attachments/assets/03ed73f7-685c-4046-bc54-a480f6c5e81b" />

---

## 🛠 Latest Updates

### ➕ Updated the Auto Profile Selection UI, added a styled animated progress bar
![Animation2](https://github.com/user-attachments/assets/6c376b42-47ed-4a16-bb8d-5fd917a35f7b)

### ➕ Fixed Core (Flowseal) version comparison
Updates are now detected not only for 1.9.7, but also for tags with suffixes/text (e.g. 1.9.7b, 1.9.7 beta).

### ➕ Protection against browser redirects when launching profiles
When running batch files from the GUI, NO_UPDATE_CHECK=1 is set, so service.bat check_updates is skipped and the browser does not open.

### ➕ Correct detection of the current Core version from bundled files
On first launch / after a wipe, the Core version is taken from core/service.bat (LOCAL_VERSION=...) and saved to settings, preventing false Core update prompts when it’s already bundled in the EXE.

### ➕ Same behavior for autotest/diagnostics
Autotest and diagnostic runs also set NO_UPDATE_CHECK=1, so no redirects / update checks can pop up anywhere.

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

