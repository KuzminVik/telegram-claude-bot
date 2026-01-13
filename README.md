# 🤖 Telegram Claude Bot

Telegram бот с Claude AI и множественными MCP интеграциями для погоды, новостей, управления Android, RAG поиска и работы с GitHub репозиториями.

## Возможности

- 💬 Диалоги с Claude AI (Sonnet 4.5)
- 🌤️ Погода с подписками
- 📰 Новости из RSS
- 📱 Управление Android эмулятором
- 🧠 RAG поиск по базе знаний (Ollama + векторные эмбеддинги)
- 🔍 Поиск по коду GitHub репозитория
- 💾 Персистентное хранилище диалогов

## Команды

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

## Архитектура

```
bot.py                  # Точка входа
config.py               # Конфигурация
handlers/               # Обработчики команд
  ├── basic.py
  ├── with_rag.py
  └── github_search.py
mcp_clients/           # MCP клиенты
  ├── weather_client.py
  ├── news_client.py
  ├── mobile_client.py
  ├── ollama_client.py
  └── github_client.py
utils/                 # Утилиты
  ├── rag_functions.py
  └── github_rag_functions.py
```

## MCP Серверы

**Локальные (на сервере):**
- Weather MCP - `/home/claude/mcp-weather-server/`
- News MCP - `/home/claude/mcp-news-server/`
- GitHub MCP - `/home/claude/mcp-github-server/`

**Удалённые (через SSH на Mac):**
- Mobile MCP - управление Android
- Ollama RAG MCP - векторный поиск

## Установка

### Требования
- Python 3.12+
- Node.js (для MCP серверов)
- Ollama (для RAG, опционально)

### Зависимости
```bash
python-telegram-bot==21.0
anthropic==0.75.0
apscheduler
```

### Настройка

1. **Клонировать:**
```bash
git clone https://github.com/KuzminVik/telegram-claude-bot.git
cd telegram-claude-bot
```

2. **Создать venv:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Настроить переменные окружения:**
```bash
export TELEGRAM_BOT_TOKEN="your_token"
export ANTHROPIC_API_KEY="your_key"
export GITHUB_TOKEN="your_github_token"
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

5. **Запустить:**
```bash
python bot.py
```

## Systemd сервис

```ini
[Unit]
Description=Telegram Claude Bot
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/telegram-bot
Environment="TELEGRAM_BOT_TOKEN=..."
Environment="ANTHROPIC_API_KEY=..."
Environment="GITHUB_TOKEN=..."
ExecStart=/root/telegram-bot/venv/bin/python /root/telegram-bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Управление:
```bash
sudo systemctl start telegram-bot
sudo systemctl status telegram-bot
sudo journalctl -u telegram-bot -f
```

## Структура данных

### История диалогов
```
/root/telegram-bot/conversations/user_{user_id}.json
```

Формат:
```json
{
  "user_id": 12345,
  "last_updated": "2026-01-13T12:00:00",
  "message_count": 25,
  "messages": [...]
}
```

### Векторные хранилища (Ollama)
```
/Users/vkuzmin/vector_stores/bot_knowledge.json
```

## RAG Pipeline

```
Запрос → Эмбеддинг → Векторный поиск → Reranking → LLM → Ответ
```

**Модели:**
- Эмбеддинги: `nomic-embed-text` (768D)
- Генерация: `llama3.2:3b`

## Конфигурация

Основные настройки в `config.py`:

```python
# MCP серверы
MCP_WEATHER_SERVER_PATH = "..."
MCP_NEWS_SERVER_PATH = "..."
MCP_GITHUB_SERVER_PATH = "..."

# GitHub
GITHUB_REPO_OWNER = "KuzminVik"
GITHUB_REPO_NAME = "telegram-claude-bot"

# RAG
RAG_VECTOR_STORE_NAME = "bot_knowledge"
RAG_TOP_K_INITIAL = 10
RAG_LLM_MODEL = "llama3.2:3b"
```

## Примеры использования

**Поиск по коду:**
```
/search_repo async def
/search_repo MCP client
/search_repo vector search
```

**RAG запрос:**
```
/with_rag Как работает сжатие истории?
/with_rag Какие команды есть у бота?
```

**Погода:**
```
/weather_subscribe Moscow
/morning_digest
```

## Документация

Полная документация: [PROJECT_MASTER_CONTEXT.md](PROJECT_MASTER_CONTEXT.md)

## Версии

- **v9.2** (13.01.2026) - GitHub MCP интеграция
- **v9.1** (23.12.2024) - RAG команды
- **v7.0** (24.12.2024) - Модульная архитектура
- **v6.0** (21.12.2024) - Ollama RAG
- **v5.0** (18.12.2024) - Mobile MCP
- **v4.0** (16.12.2024) - News MCP
- **v3.0** (15.12.2024) - Weather MCP
- **v2.0** (14.12.2024) - JSON хранилище
- **v1.0** (Декабрь 2024) - Базовая версия

## Лицензия

MIT

## Контакты

Виктор Кузьмин - [@KuzminVik](https://github.com/KuzminVik)
