# Telegram Bot с Claude AI

Telegram-бот, использующий Claude API от Anthropic для генерации ответов в формате JSON.

## 🚀 Возможности

- Интеграция с Claude Sonnet 4.5
- Ответы в структурированном JSON формате
- Хранение истории разговоров
- Автоматический перезапуск через systemd
- Логирование всех операций

## 📋 Требования

- Python 3.12+
- Telegram Bot Token (получить у [@BotFather](https://t.me/botfather))
- Anthropic API Key (получить на [console.anthropic.com](https://console.anthropic.com))

## 🛠️ Установка

### 1. Клонируйте репозиторий
```bash
git clone https://github.com/ваш-username/telegram-claude-bot.git
cd telegram-claude-bot
```

### 2. Создайте виртуальное окружение
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Установите зависимости
```bash
pip install -r requirements.txt
```

### 4. Настройте переменные окружения

Создайте файл `.env`:
```bash
TELEGRAM_BOT_TOKEN=ваш_токен_от_botfather
ANTHROPIC_API_KEY=ваш_claude_api_ключ
```

Или добавьте в `~/.bashrc`:
```bash
export TELEGRAM_BOT_TOKEN="ваш_токен"
export ANTHROPIC_API_KEY="ваш_ключ"
source ~/.bashrc
```

### 5. Запустите бота
```bash
python bot.py
```

## 🔧 Настройка systemd (для production)

### 1. Создайте systemd сервис
```bash
sudo nano /etc/systemd/system/telegram-bot.service
```

Добавьте:
```ini
[Unit]
Description=Telegram Claude Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/telegram-bot
Environment="TELEGRAM_BOT_TOKEN=ваш_токен"
Environment="ANTHROPIC_API_KEY=ваш_ключ"
ExecStart=/path/to/telegram-bot/venv/bin/python /path/to/telegram-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 2. Активируйте сервис
```bash
sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot
```

### 3. Проверьте статус
```bash
sudo systemctl status telegram-bot
sudo journalctl -u telegram-bot -f
```

## 📚 Команды бота

- `/start` - Начать работу с ботом
- `/clear` - Очистить историю разговора
- `/debug` - Показать последний JSON ответ

## 🔍 Формат ответов

Бот возвращает ответы в JSON формате:
```json
{
  "user_message": "Привет",
  "ai_message": "Привет! Чем могу помочь?"
}
```

## 🛡️ Безопасность

⚠️ **ВАЖНО:** Никогда не коммитьте токены и API ключи в Git!

- Используйте `.env` файлы (добавлены в `.gitignore`)
- Или храните секреты в переменных окружения
- Для production используйте секреты в CI/CD

## 📊 Мониторинг

### Просмотр логов
```bash
# В реальном времени
sudo journalctl -u telegram-bot -f

# Последние 50 строк
sudo journalctl -u telegram-bot -n 50

# За последний час
sudo journalctl -u telegram-bot --since "1 hour ago"
```

### Управление сервисом
```bash
sudo systemctl start telegram-bot    # Запустить
sudo systemctl stop telegram-bot     # Остановить
sudo systemctl restart telegram-bot  # Перезапустить
sudo systemctl status telegram-bot   # Статус
```

## 🤝 Вклад в проект

Pull requests приветствуются! Для серьезных изменений сначала откройте issue.

## 📄 Лицензия

MIT

## 👤 Автор

Ваше Имя - [@your_telegram](https://t.me/your_telegram)

Проект создан с помощью Claude AI
