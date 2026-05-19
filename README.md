<div align="center">
   
[![Boosty](https://img.shields.io/badge/Поддержать-Boosty-orange?style=for-the-badge)](https://boosty.to/medvedeff)
## [Ru](#rus) | [En](#eng)

<a name="rus"></a>
<img width="443,5" height="86" alt="logoreadme" src="https://github.com/user-attachments/assets/76dc2441-f9e0-4357-b2da-1a0408688079" />

**Zapret GUI** — это простая графическая оболочка для обхода интернет-блокировок с помощью утилиты [Zapret](https://github.com/bol-van/zapret)  
Создано на Python + PyQt6.

</div>

> [!Caution]
> #### У меня нет youtube каналов, я не заливаю ZapretGUI на форумы или файлообменники. Программа распространятеся **только на [GitHub](https://github.com/medvedeff-true/Zapret-GUI/releases) и в моём [Boosty](https://boosty.to/medvedeff)**. Не качайте ZapretGUI с других сайтов, это могут быть вирусные сборки.

<img width="1065" height="484" alt="Анимация228" src="https://github.com/user-attachments/assets/966f47d1-259d-426d-a7d7-460e1f0ee627" />

<div align="center">
   
<img width="358" height="390" alt="tray" src="https://github.com/user-attachments/assets/be193b84-adb9-4fad-860b-9a34edf20205" />

</div>

---

<details>
<summary><strong>🛠 Последние обновления <img width="19" height="20" alt="277031mbmmfoabln" src="https://github.com/user-attachments/assets/6161bda3-fa90-40be-8e71-c077bf96af9d" /> тык чтобы развернуть</strong></summary>

# 2.1.1

## ✨ Что нового

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

# 2.0

# Добавлено:

- Игровой режим. <img width="73" height="55" alt="{3A9FE377-5CEE-4091-8277-AB895BFA087C}" src="https://github.com/user-attachments/assets/c355c1e2-0006-4b14-aa15-d60ea5362c73" />

Теперь можно подключать Zapret Game Filters по TCP и UDP, а также настраивать что конкретно будет в обходе при игровом режиме. Настроить игровой режим можно через кнопке рядом в виде шестерёнки.

#

- Менеджер IP.
<img width="303" height="454" alt="{0194100F-A606-48AC-AA8C-573C282AC45C}" src="https://github.com/user-attachments/assets/f90765b1-d2b4-4ad3-9bc1-f41c28b8cb3a" />

#

- DNS для доступа к нейросетям без VPN. <img width="40" height="39" alt="{6DD1220B-00D6-4D4E-AE89-88C1114E2E95}" src="https://github.com/user-attachments/assets/1c1be104-b4a2-4d43-ad6c-c5e6f9aa82dc" />

Если активировано, Вам станут доступны нейросети без VPN. (Например ChatGPT, Claude и подобные, которые блокируют доступ из России). 
#### На данную функцию может ругаться антивирус, так как данный обход взаимодействует с файлом hosts (ваш hosts хранится в backup и восстанавливается когда вы выключаете функцию), поэтому во избежание проблем с антивирусом, просто добавьте Zapret GUI.exe и папку Users/user/ZapretGUI целиком в исключения антивируса.

#

- Автоматическое обновление игровых списков.

Собрал из Issues разных репозиториев домены и ip заблокированных игровых сервисов и добавил их дополнительно в игровой режим. Просмотреть их отдельно можно здесь: [Игровые списки](https://github.com/medvedeff-true/ru-gaming-blocklist) (`Буду благодарен за звёзды ⭐`)

# Улучшено:

- Запуск обхода ждёт завершения важных фоновых операций.
- Обновления списков выполняются аккуратнее и тише.
- Главное окно и трей лучше синхронизируют состояние обхода.
- Улучшена работа с пользовательскими списками.
- Улучшены иконки и подсказки в интерфейсе.

# Исправлено:

- Исправлены зависания при проверке обновлений.
- Исправлены зависания при включении/отключении Ai DNS.
- Исправлены ошибки доступа к hosts при Ai DNS.
- Исправлены проблемы с иконками на экранах с масштабированием.

</details>

---

## 🧩 Возможности

- ✅ Запуск и остановка в один клик
- 🌐 Предустановленные профили (Flowseal Core) для разных методов обхода
- 🎮 Игровой режим с настройкой TCP/UDP-фильтров и обхода игровых сервисов
- 📡 Менеджер доменов и IP для удобного управления заблокированными сайтами и подсетями
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

1. Скачайте последний релиз `Zapret_GUI.zip` из раздела [Releases](https://github.com/medvedeff-true/Zapret-GUI/releases/tag/v1.7.0) и разархивируйте в любое удобное место
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

# 2.0

# Added:

- Gaming Mode. <img width="73" height="55" alt="{3A9FE377-5CEE-4091-8277-AB895BFA087C}" src="https://github.com/user-attachments/assets/c355c1e2-0006-4b14-aa15-d60ea5362c73" />

You can now enable Zapret Game Filters over TCP and UDP, and also configure exactly what will be bypassed in Gaming Mode. You can configure Gaming Mode using the gear button next to it.

#

- IP Manager.
<img width="303" height="454" alt="{0194100F-A606-48AC-AA8C-573C282AC45C}" src="https://github.com/user-attachments/assets/f90765b1-d2b4-4ad3-9bc1-f41c28b8cb3a" />

#

- DNS for access to AI services without a VPN. <img width="40" height="39" alt="{6DD1220B-00D6-4D4E-AE89-88C1114E2E95}" src="https://github.com/user-attachments/assets/1c1be104-b4a2-4d43-ad6c-c5e6f9aa82dc" />

When enabled, AI services will be available without a VPN. (For example ChatGPT, Claude, and similar services that block access from Russia.)
#### Your antivirus may warn about this feature because it interacts with the `hosts` file (your `hosts` file is stored in backup and restored when you disable the feature). To avoid antivirus issues, simply add `Zapret GUI.exe` and the entire `Users/user/ZapretGUI` folder to your antivirus exclusions.

#

- Automatic updates for gaming lists.

I collected domains and IPs of blocked gaming services from Issues across various repositories and additionally added them to Gaming Mode. You can view them separately here: [Gaming Lists](https://github.com/medvedeff-true/ru-gaming-blocklist) (`I'd appreciate a star ⭐`)

# Improved:

- Bypass startup now waits for important background operations to finish.
- List updates now run more cleanly and quietly.
- The main window and tray now stay better synchronized with the bypass state.
- Improved handling of user-managed lists.
- Improved interface icons and tooltips.

# Fixed:

- Fixed freezes during update checks.
- Fixed freezes when enabling/disabling AI DNS.
- Fixed `hosts` access errors when using AI DNS.
- Fixed icon issues on displays with scaling enabled.

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

---

## 📦 Installation

No installation required. Just:

1. Download the latest `Zapret_GUI.zip` file from [Releases](https://github.com/medvedeff-true/Zapret-GUI/releases/tag/v1.7.0) and extract
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

