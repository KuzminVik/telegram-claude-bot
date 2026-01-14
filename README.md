# 🤖 Telegram Claude Bot

Telegram бот с Claude AI и автоматическим code review для Pull Request через GitHub Webhooks.

## ✨ Возможности

### 💬 Диалоги и интеграции
- Диалоги с Claude AI (Sonnet 4.5)
- 🌤️ Погода с подписками
- 📰 Новости из RSS
- 📱 Управление Android эмулятором
- 🧠 RAG поиск по базе знаний (Ollama + векторные эмбеддинги)
- 🔍 Поиск по коду GitHub репозитория
- 💾 Персистентное хранилище диалогов

### 🤖 Автоматический Code Review (NEW!)
- ⚡ **Webhook интеграция** - автоматическое ревью при создании/обновлении PR
- 🧠 **RAG контекст** - использует документацию проекта для ревью
- 📊 **Детальный анализ** - архитектура, качество кода, безопасность, интеграции
- 💬 **Telegram уведомления** - мгновенные уведомления о PR и результатах ревью
- 📝 **Комментарии в GitHub** - полное ревью публикуется в PR

## 📋 Команды

### Основные
```
/start       - Старт
/clear       - Очистить историю
/stats       - Статистика
```

### Погода
```
/weather_subscribe <город>   - Подписаться на утреннюю погоду
/weather_unsubscribe        - Отписаться
/morning_digest             - Получить дайджест
```

### RAG
```
/with_rag <вопрос>   - Запрос с поиском по базе знаний
/clear_rag           - Очистить историю RAG
```

### GitHub
```
/search_repo <запрос>   - Поиск по коду репозитория
/get_file <путь>        - Получить содержимое файла
```

### Mobile
```
/mobile_devices    - Список устройств
/start_emulator    - Запустить Android эмулятор
```

## 🏗️ Архитектура

```
telegram-bot/
├── bot.py                  # Точка входа Telegram бота
├── webhook_server.py       # Webhook сервер для GitHub
├── config.py              # Централизованная конфигурация
├── requirements.txt
│
├── handlers/              # Обработчики команд
│   ├── basic.py          # Базовые команды
│   ├── with_rag.py       # RAG команды
│   ├── github_search.py  # GitHub поиск
│   └── pr_review.py      # Code review для PR
│
├── mcp_clients/          # MCP клиенты
│   ├── weather_client.py
│   ├── news_client.py
│   ├── mobile_client.py
│   ├── ollama_client.py
│   └── github_client.py
│
└── utils/                # Утилиты
    ├── rag_functions.py
    ├── github_rag_functions.py
    └── github_api.py     # GitHub REST API
```

## 🔌 MCP Серверы

**Локальные (на сервере):**
- Weather MCP - `/home/claude/mcp-weather-server/`
- News MCP - `/home/claude/mcp-news-server/`
- GitHub MCP - `/home/claude/mcp-github-server/`

**Удалённые (через SSH на Mac):**
- Mobile MCP - управление Android
- Ollama RAG MCP - векторный поиск

## 🚀 Быстрый старт

### Требования
- Python 3.12+
- Node.js (для MCP серверов)
- Ollama (для RAG, опционально)

### Установка

1. **Клонировать репозиторий:**
```bash
git clone https://github.com/KuzminVik/telegram-claude-bot.git
cd telegram-claude-bot
```

2. **Создать виртуальное окружение:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Настроить переменные окружения:**
```bash
export TELEGRAM_TOKEN="your_telegram_token"
export ANTHROPIC_API_KEY="your_anthropic_key"
export GITHUB_TOKEN="your_github_token"
export GITHUB_WEBHOOK_SECRET="your_webhook_secret"
```

4. **Установить MCP серверы:**
```bash
# Weather MCP
mkdir -p /home/claude/mcp-weather-server
cd /home/claude/mcp-weather-server
npm install @modelcontextprotocol/server-weather

# News MCP
mkdir -p /home/claude/mcp-news-server
cd /home/claude/mcp-news-server
npm install @modelcontextprotocol/server-news

# GitHub MCP
mkdir -p /home/claude/mcp-github-server
cd /home/claude/mcp-github-server
npm install @modelcontextprotocol/server-github
```

5. **Запустить бота:**
```bash
python bot.py
```

6. **Запустить webhook сервер (опционально):**
```bash
gunicorn --bind 0.0.0.0:8080 --workers 2 webhook_server:app
```

## 🔧 Настройка автоматического Code Review

### 1. Настройка Webhook сервера

См. подробную инструкцию: [WEBHOOK_SETUP.md](WEBHOOK_SETUP.md)

Краткая версия:
```bash
# Systemd service для webhook
sudo cp webhook-server.service /etc/systemd/system/
sudo systemctl enable webhook-server
sudo systemctl start webhook-server
```

### 2. Настройка GitHub Webhook

1. Перейти: `https://github.com/YOUR_USERNAME/YOUR_REPO/settings/hooks`
2. "Add webhook"
3. **Payload URL**: `http://YOUR_SERVER_IP:8080/webhook/github`
4. **Content type**: `application/json`
5. **Secret**: [ваш webhook secret]
6. **Events**: Pull requests
7. "Add webhook"

### 3. Результат

При создании PR:
1. 🔔 Telegram уведомление о начале ревью
2. 🧠 RAG поиск по документации проекта
3. 🤖 Claude анализирует код (~20-30 сек)
4. 📝 Комментарий с ревью публикуется в PR
5. ✅ Результат ревью отправляется в Telegram

## 📊 RAG Pipeline

```
Вопрос пользователя
    ↓
Создание эмбеддинга (nomic-embed-text)
    ↓
Векторный поиск (top_k=10)
    ↓
Reranking (light/strict mode)
    ↓
Генерация ответа (llama3.2:3b)
    ↓
Ответ пользователю
```

**Модели:**
- Эмбеддинги: `nomic-embed-text` (768D)
- Генерация: `llama3.2:3b`

## 🔐 Переменные окружения

**Обязательные:**
- `TELEGRAM_TOKEN` - токен Telegram бота
- `ANTHROPIC_API_KEY` - API ключ Claude

**Опциональные:**
- `GITHUB_TOKEN` - GitHub Personal Access Token
- `GITHUB_WEBHOOK_SECRET` - секрет для webhook
- `ADMIN_CHAT_ID` - Chat ID для уведомлений о PR
- `WEBHOOK_PORT` - порт webhook сервера (по умолчанию 8080)

## 🖥️ Systemd сервисы

### Telegram Bot
```bash
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
sudo journalctl -u telegram-bot -f
```

### Webhook Server
```bash
sudo systemctl start webhook-server
sudo systemctl status webhook-server
sudo journalctl -u webhook-server -f
```

## 📝 Примеры использования

### Поиск по коду
```
/search_repo async def        # найдёт все async функции
/search_repo MCP             # найдёт упоминания MCP
/get_file bot.py             # получить содержимое bot.py
```

### RAG запрос
```
/with_rag Как работает сжатие истории?
/with_rag Какие команды есть у бота?
```

### Code Review
Создайте PR → автоматически получите детальное ревью через 30 секунд

## 🎯 Что проверяет Code Review

1. **Архитектура и дизайн**
   - Модульная структура
   - Separation of Concerns
   - Соответствие принципам проекта

2. **Качество кода**
   - PEP 8
   - Type hints
   - Обработка ошибок
   - Логирование
   - Документация

3. **Функциональность**
   - Корректность логики
   - Edge cases
   - Async/await паттерны

4. **Безопасность**
   - Валидация входных данных
   - Управление секретами
   - SQL/Command injection

5. **Интеграция**
   - Работа с MCP
   - Совместимость с кодом

## 📚 Документация

- [Полный контекст проекта](PROJECT_MASTER_CONTEXT.md)
- [Настройка webhook](WEBHOOK_SETUP.md)
- [Быстрый старт webhook](QUICKSTART.md)

## 🔗 Версии

- **v10.0** (14.01.2026) - Автоматический Code Review с Telegram уведомлениями
- **v9.2** (13.01.2026) - GitHub MCP интеграция
- **v9.1** (23.12.2024) - RAG команды
- **v7.0** (24.12.2024) - Модульная архитектура
- **v6.0** (21.12.2024) - Ollama RAG
- **v5.0** (18.12.2024) - Mobile MCP
- **v4.0** (16.12.2024) - News MCP
- **v3.0** (15.12.2024) - Weather MCP
- **v2.0** (14.12.2024) - JSON хранилище
- **v1.0** (Декабрь 2024) - Базовая версия

## 🤝 Контрибьютинг

Создавайте PR - автоматический code review поможет с ревью! 🤖

## 📄 Лицензия

MIT

## 👤 Автор

Виктор Кузьмин - [@KuzminVik](https://github.com/KuzminVik)

---

**Telegram бот:** @viksimurg_claude_bot
