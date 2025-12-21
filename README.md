# 🤖 Telegram бот с Claude AI + Weather + News + Mobile Emulator

Умный Telegram бот с интеграцией Claude AI, погодой, новостями и **управлением Android эмулятором** через MCP серверы.

[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Telegram Bot API](https://img.shields.io/badge/Telegram%20Bot%20API-21.0-blue.svg)](https://python-telegram-bot.org/)
[![Claude AI](https://img.shields.io/badge/Claude-Sonnet%204-purple.svg)](https://www.anthropic.com/)
[![Node.js](https://img.shields.io/badge/Node.js-20.x-green.svg)](https://nodejs.org/)
[![Android](https://img.shields.io/badge/Android-API%2034-green.svg)](https://developer.android.com/)

---

## 🎯 Возможности

### 💬 Разговор с Claude AI
- Поддержка истории диалога (до 30 сообщений)
- Автоматическое сжатие истории через Claude
- Персистентное хранение в JSON (сохраняется при перезапуске)
- Показ статистики токенов

### 🌤️ Погода (через MCP Weather Server)
- **Текущая погода** для любого города
- **Прогноз на день:** макс/мин температура, осадки, восход/закат
- **Сравнение с вчера:** Claude анализирует изменения
- **Утренняя рассылка** в 08:00 MSK с дайджестом

### 📰 Новости (через MCP News Server)
- **RSS новости** из российских источников
- **3 категории:** общие, технологии, бизнес
- **Топ новости** в утренней рассылке
- **Команда /morning_digest** - погода + новости

### 📱 Android Эмулятор (через MCP Mobile Server) ⭐ **НОВОЕ!**
- **Список устройств** - просмотр доступных эмуляторов
- **Запуск эмулятора** - автоматический старт если выключен
- **Статус проверка** - готов ли эмулятор к работе
- **Удалённое управление** - через SSH tunnel с Mac на сервер
- **Поддержка Appium** - готовность для UI автоматизации

### 🔧 Инструменты Claude
- `get_weather(city)` - получить погоду
- `get_news(category, limit)` - получить новости
- `mobile_list_available_devices()` - список Android устройств
- `mobile_start_emulator()` - запустить эмулятор

---

## 🏗️ Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                  Telegram Bot (Python) - Сервер                 │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │   Commands   │  │ APScheduler  │  │   3x MCP Clients     │  │
│  │              │  │              │  │                      │  │
│  │ /morning_    │  │  08:00 daily │  │ Weather+News+Mobile  │  │
│  │  digest      │  │  broadcast   │  │                      │  │
│  │ /start_      │  │              │  │                      │  │
│  │  emulator    │  │              │  │                      │  │
│  └──────────────┘  └──────────────┘  └──────────────────────┘  │
│                                              │                  │
└──────────────────────────────────────────────┼──────────────────┘
        │                   │                  │
        ↓                   ↓                  ↓ SSH Tunnel
┌───────────────┐  ┌───────────────┐  ┌──────────────────────────┐
│ MCP Weather   │  │  MCP News     │  │                          │
│  Server       │  │   Server      │  │  Mac (локальный)         │
│  (Node.js)    │  │  (Node.js)    │  │                          │
│               │  │               │  │  ┌───────────────────┐   │
│  Open-Meteo   │  │  RSS Feeds    │  │  │ MCP Mobile Server │   │
│      API      │  │               │  │  │    (Node.js)      │   │
└───────────────┘  └───────────────┘  │  └────────┬──────────┘   │
                                      │           │              │
                                      │  ┌────────▼──────────┐   │
                                      │  │ Appium Server     │   │
                                      │  └────────┬──────────┘   │
                                      │           │              │
                                      │  ┌────────▼──────────┐   │
                                      │  │ Android Emulator  │   │
                                      │  │  Pixel 8 API 34   │   │
                                      │  └───────────────────┘   │
                                      └──────────────────────────┘
```

### Reverse SSH Tunnel
- Mac автоматически создаёт туннель при загрузке (LaunchAgent)
- Сервер подключается к Mac через `localhost:2222`
- mobile-mcp запускается через SSH с установкой переменных окружения
- ANDROID_HOME и PATH передаются в SSH сессию

---

## 📱 Команды бота

### Основные команды:
- `/start` - Приветствие и список команд
- `/clear` - Очистить историю диалога
- `/stats` - Показать статистику (сообщения, размер файла)
- `/debug` - Показать последнее сообщение

### Погода:
- `/weather_subscribe Город` - Подписаться на утреннюю погоду
- `/weather_unsubscribe` - Отписаться от погоды
- `/weather_list` - Показать текущую подписку

### Новости:
- `/morning_digest` - Получить дайджест (погода + новости) прямо сейчас

### Мобильные устройства: ⭐ **НОВОЕ!**
- `/mobile_devices` - Показать доступные Android устройства
- `/start_emulator` - Запустить Android эмулятор

### Служебные:
- `/test_morning` - Протестировать утреннюю рассылку

---

## 📦 Установка

### Часть 1: Сервер (Python Bot + MCP Weather/News)

#### 1. Клонирование репозитория

```bash
git clone https://github.com/KuzminVik/telegram-claude-bot.git
cd telegram-claude-bot
```

#### 2. Установка Python зависимостей

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

**requirements.txt:**
```
python-telegram-bot==21.0
anthropic==0.75.0
apscheduler==3.10.4
```

#### 3. Установка MCP Weather Server

```bash
cd /home/claude/mcp-weather-server
npm install
npm test  # Проверка работы
```

#### 4. Установка MCP News Server

```bash
cd /home/claude/mcp-news-server
npm install
npm test  # Проверка работы
```

#### 5. Настройка переменных окружения

```bash
export TELEGRAM_BOT_TOKEN="your_telegram_bot_token"
export ANTHROPIC_API_KEY="your_anthropic_api_key"
```

---

### Часть 2: Mac (MCP Mobile Server + Appium + Emulator) ⭐ **НОВОЕ!**

#### 1. Установка Java JDK

```bash
# Проверка установки
java -version
```

Если нет - установите OpenJDK 17+

#### 2. Установка Android Studio + SDK

1. Скачайте [Android Studio](https://developer.android.com/studio)
2. Установите Android SDK
3. Создайте AVD (Android Virtual Device):
   - Tools → Device Manager → Create Device
   - Выберите Pixel 8
   - Скачайте API 34 system image
   - Создайте эмулятор

#### 3. Настройка переменных окружения

Добавьте в `~/.zshrc`:

```bash
export ANDROID_HOME=/Users/YOUR_USER/Library/android/sdk
export PATH=$ANDROID_HOME/platform-tools:$ANDROID_HOME/emulator:$PATH
```

```bash
source ~/.zshrc
```

#### 4. Установка Appium

```bash
# Установка Appium
npm install -g appium

# Установка UiAutomator2 драйвера
appium driver install uiautomator2

# Проверка
appium -v
```

#### 5. Установка mobile-mcp

```bash
# Клонирование
cd ~/mcp-servers
git clone https://github.com/mobile-next/mobile-mcp.git
cd mobile-mcp

# Установка зависимостей
npm install

# Сборка
npm run build
```

#### 6. Создание скрипта запуска эмулятора

```bash
nano ~/start-emulator.sh
```

Вставьте:

```bash
#!/bin/bash

EMULATOR_NAME="Pixel_8_API_34_3"  # Замените на имя вашего AVD
ANDROID_SDK="/Users/YOUR_USER/Library/android/sdk"

# Проверяем запущен ли эмулятор
RUNNING=$(${ANDROID_SDK}/platform-tools/adb devices | grep "emulator-" | grep "device$")

if [ -n "$RUNNING" ]; then
    DEVICE_ID=$(echo "$RUNNING" | awk '{print $1}')
    echo "{\"status\":\"already_running\",\"device_id\":\"$DEVICE_ID\",\"message\":\"Эмулятор уже запущен и готов к работе\"}"
else
    # Запускаем эмулятор
    nohup ${ANDROID_SDK}/emulator/emulator -avd ${EMULATOR_NAME} > /tmp/emulator.log 2>&1 &
    sleep 10
    
    DEVICE_ID=$(${ANDROID_SDK}/platform-tools/adb devices | grep "emulator-" | grep "device$" | awk '{print $1}')
    
    if [ -n "$DEVICE_ID" ]; then
        echo "{\"status\":\"started\",\"device_id\":\"$DEVICE_ID\",\"message\":\"Эмулятор успешно запущен\"}"
    else
        echo "{\"status\":\"error\",\"message\":\"Не удалось запустить эмулятор\"}"
    fi
fi
```

```bash
chmod +x ~/start-emulator.sh
```

#### 7. Настройка Reverse SSH Tunnel

На Mac генерируем SSH ключ:

```bash
ssh-keygen -t ed25519 -C "mac-to-server" -f ~/.ssh/mac_to_server
# Нажимайте Enter (без passphrase!)
```

Копируем ключ на сервер:

```bash
ssh-copy-id -i ~/.ssh/mac_to_server.pub root@YOUR_SERVER_IP
```

Создаём скрипт туннеля:

```bash
nano ~/ssh-tunnel.sh
```

```bash
#!/bin/bash
export PATH=/usr/bin:/bin:/usr/sbin:/sbin
export HOME=/Users/YOUR_USER

/usr/bin/ssh \
    -i "$HOME/.ssh/mac_to_server" \
    -R 2222:localhost:22 \
    -N \
    -o StrictHostKeyChecking=no \
    -o UserKnownHostsFile=/dev/null \
    -o ServerAliveInterval=60 \
    -o ServerAliveCountMax=3 \
    -o ExitOnForwardFailure=yes \
    root@YOUR_SERVER_IP
```

```bash
chmod +x ~/ssh-tunnel.sh
```

Создаём LaunchAgent для автозапуска:

```bash
mkdir -p ~/Library/LaunchAgents
nano ~/Library/LaunchAgents/com.user.ssh-reverse-tunnel.plist
```

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.user.ssh-reverse-tunnel</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/YOUR_USER/ssh-tunnel.sh</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardErrorPath</key>
    <string>/tmp/ssh-tunnel-error.log</string>
    <key>StandardOutPath</key>
    <string>/tmp/ssh-tunnel-out.log</string>
</dict>
</plist>
```

Загрузка LaunchAgent:

```bash
launchctl load ~/Library/LaunchAgents/com.user.ssh-reverse-tunnel.plist
launchctl list | grep ssh-reverse-tunnel
```

#### 8. Настройка SSH ключа на сервере для подключения к Mac

На сервере:

```bash
ssh-keygen -t ed25519 -C "server-to-mac" -f ~/.ssh/server_to_mac
```

Копируем публичный ключ:

```bash
cat ~/.ssh/server_to_mac.pub
```

На Mac добавляем в `~/.ssh/authorized_keys`:

```bash
nano ~/.ssh/authorized_keys
# Вставьте публичный ключ с сервера
chmod 600 ~/.ssh/authorized_keys
```

Тест с сервера:

```bash
ssh -i ~/.ssh/server_to_mac -p 2222 YOUR_MAC_USER@localhost "hostname"
```

---

### Часть 3: Запуск бота на сервере

#### 1. Обновление bot.py

Убедитесь что в `bot.py` правильно указаны пути:

```python
# SSH конфигурация для mobile-mcp
MCP_MOBILE_SSH_HOST = "localhost"
MCP_MOBILE_SSH_PORT = 2222
MCP_MOBILE_SSH_USER = "YOUR_MAC_USER"
MCP_MOBILE_SSH_KEY = "/root/.ssh/server_to_mac"
MCP_MOBILE_NODE_PATH = "/Users/YOUR_MAC_USER/.nvm/versions/node/v20.19.6/bin/node"
MCP_MOBILE_SERVER_PATH = "/Users/YOUR_MAC_USER/mcp-servers/mobile-mcp/lib/index.js"
MCP_MOBILE_START_EMULATOR_SCRIPT = "/Users/YOUR_MAC_USER/start-emulator.sh"
```

#### 2. Создание systemd сервиса

```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

```ini
[Unit]
Description=Telegram Claude Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/telegram-bot
Environment="TELEGRAM_BOT_TOKEN=your_token"
Environment="ANTHROPIC_API_KEY=your_key"
ExecStart=/root/telegram-bot/venv/bin/python /root/telegram-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. Запуск

```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
```

---

## 🧪 Тестирование

### 1. Тест Appium на Mac

```bash
# Запустите Appium в одном терминале
appium

# В другом терминале запустите эмулятор
~/Library/android/sdk/emulator/emulator -avd Pixel_8_API_34_3 &

# Проверьте что эмулятор виден
~/Library/android/sdk/platform-tools/adb devices
```

### 2. Тест mobile-mcp на Mac

```bash
cd ~/mcp-servers/mobile-mcp

# Тест через stdio
echo '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"mobile_list_available_devices","arguments":{"noParams":{}}},"id":1}' | node lib/index.js
```

Должно вернуть список устройств в JSON.

### 3. Тест SSH туннеля

С сервера:

```bash
ssh -i ~/.ssh/server_to_mac -p 2222 YOUR_MAC_USER@localhost "hostname"
```

Должно вывести имя Mac.

### 4. Тест скрипта запуска эмулятора

С сервера через SSH:

```bash
ssh -i ~/.ssh/server_to_mac -p 2222 YOUR_MAC_USER@localhost "/Users/YOUR_MAC_USER/start-emulator.sh"
```

Должно вернуть JSON со статусом.

### 5. Тест бота в Telegram

1. `/start` - проверить список команд
2. `/mobile_devices` - должен показать Pixel 8
3. `/start_emulator` - должен запустить или сообщить что уже работает
4. "Покажи доступные Android устройства" - Claude использует инструмент
5. "Запусти эмулятор" - Claude использует инструмент

---

## 📊 Примеры использования

### Пример 1: Список устройств

**Пользователь:** `/mobile_devices`

**Бот:**
```
📱 Доступные устройства:

1. Pixel 8 API 34 3
   ID: emulator-5554
   Платформа: android
   Тип: emulator
   Версия: 14
   Статус: 🟢 online
```

### Пример 2: Запуск эмулятора

**Пользователь:** `/start_emulator`

**Бот (если уже запущен):**
```
✅ Эмулятор уже запущен и готов к работе

📱 ID устройства: emulator-5554
```

**Бот (если был выключен):**
```
🚀 Эмулятор успешно запущен

📱 ID устройства: emulator-5554

Эмулятор готов к работе!
```

### Пример 3: Через Claude

**Пользователь:** "Эмулятор готов к работе?"

**Бот:** (Claude вызывает `mobile_start_emulator` и отвечает на основе статуса)

---

## 🔐 Безопасность

### SSH Туннели
- ✅ Reverse SSH tunnel с автоматическим переподключением
- ✅ SSH ключи без passphrase для автоматизации
- ✅ ServerAliveInterval для поддержания соединения
- ✅ LaunchAgent для автозапуска при загрузке Mac

### Изоляция процессов
- ✅ Каждый MCP - отдельный процесс
- ✅ Appium изолирован на Mac
- ✅ Эмулятор в sandbox Android
- ✅ Timeout для всех SSH команд

### Переменные окружения
- ✅ ANDROID_HOME передаётся через SSH
- ✅ PATH настроен для non-interactive сессий
- ✅ Полные пути к node и другим бинарникам

---

## 📈 Статус проекта

**Текущая версия:** 6.0.0 (Mobile Emulator Integration)

**Последние изменения (21.12.2024):**
- ✅ Добавлен MCP Mobile Server с интеграцией Appium
- ✅ Реализован Reverse SSH tunnel Mac ↔ Сервер
- ✅ Добавлены команды `/mobile_devices` и `/start_emulator`
- ✅ Claude может управлять эмулятором через инструменты
- ✅ Автоматический запуск эмулятора при запросе
- ✅ Проверка статуса эмулятора

**В разработке:**
- [ ] Снятие скриншотов с эмулятора
- [ ] Запуск приложений на эмуляторе
- [ ] UI автоматизация (клики, свайпы)
- [ ] Поддержка нескольких эмуляторов
- [ ] iOS симуляторы (требует физический Mac)

---

## 🔧 Устранение неполадок

### Проблема: Туннель не работает

**Решение:**
```bash
# На Mac проверьте LaunchAgent
launchctl list | grep ssh-reverse-tunnel

# Проверьте логи
tail /tmp/ssh-tunnel-error.log

# Перезапустите туннель
launchctl unload ~/Library/LaunchAgents/com.user.ssh-reverse-tunnel.plist
launchctl load ~/Library/LaunchAgents/com.user.ssh-reverse-tunnel.plist
```

### Проблема: Бот не видит устройства

**Решение:**
```bash
# На Mac проверьте Appium
ps aux | grep appium

# Проверьте эмулятор
adb devices

# Проверьте ANDROID_HOME через SSH
ssh -i ~/.ssh/server_to_mac -p 2222 user@localhost "echo \$ANDROID_HOME"
```

### Проблема: node: command not found через SSH

**Решение:**
Используйте полный путь к node в bot.py:
```python
MCP_MOBILE_NODE_PATH = "/Users/YOUR_USER/.nvm/versions/node/v20.19.6/bin/node"
```

---

## 🤝 Вклад

Проект открыт для улучшений! Если у вас есть идеи или нашли баг:

1. Создайте Issue
2. Форкните репозиторий
3. Создайте ветку для фичи
4. Отправьте Pull Request

---

## 📝 Лицензия

MIT License

---

## 👨‍💻 Автор

**Виктор Кузьмин**
- GitHub: [@KuzminVik](https://github.com/KuzminVik)
- Telegram бот: создан с помощью Claude AI (Anthropic)

---

## 🙏 Благодарности

- [Anthropic](https://www.anthropic.com/) - за Claude AI
- [python-telegram-bot](https://python-telegram-bot.org/) - за библиотеку Telegram Bot
- [Open-Meteo](https://open-meteo.com/) - за бесплатный Weather API
- [MCP](https://modelcontextprotocol.io/) - за Model Context Protocol
- [mobile-mcp](https://github.com/mobile-next/mobile-mcp) - за MCP Mobile Server
- [Appium](https://appium.io/) - за мобильную автоматизацию

---

## 📚 Документация

Подробная документация проекта:
- [NEWS_MCP_INTEGRATION_SUMMARY.md](./NEWS_MCP_INTEGRATION_SUMMARY.md) - Саммари интеграции новостей
- [PROJECT_CONTEXT_UPDATED.md](./PROJECT_CONTEXT_UPDATED.md) - Полный контекст проекта
- [MCP_Setup_Summary.md](./MCP_Setup_Summary.md) - Настройка MCP серверов

---

**Последнее обновление:** 21 декабря 2024  
**Версия README:** 6.0.0
