# 🚀 Модульный Telegram бот - Инструкция по установке

## 📦 Что создано:

### Структура проекта:
```
modular_bot/
├── bot.py                          # Главный файл (140 строк)
├── config.py                       # Все константы (100 строк)
├── mcp_clients/                    # MCP клиенты
│   ├── __init__.py
│   ├── weather_client.py          # Weather (100 строк)
│   ├── news_client.py             # News (105 строк)
│   ├── mobile_client.py           # Mobile (120 строк)
│   └── ollama_client.py           # Ollama RAG (130 строк) ⭐
├── handlers/                       # Команды бота
│   ├── __init__.py
│   └── rag_compare.py             # /compare (110 строк) ⭐
└── utils/                          # Вспомогательные функции
    ├── __init__.py
    ├── helpers.py                  # send_long_message
    └── rag_functions.py            # RAG логика (150 строк) ⭐
```

**Всего: ~1000 строк чистого, модульного кода**

---

## ✅ Преимущества новой архитектуры:

1. **Чистый код** - каждый модуль отвечает за одно
2. **Легко расширять** - добавили RAG, не трогая остальное
3. **Правильная кодировка** - создано с нуля в UTF-8
4. **Легко дебажить** - ошибка в конкретном модуле
5. **Легко тестировать** - можно тестировать модули отдельно

---

## 🚀 Установка (15 минут):

### Шаг 1: Скачайте архив

Скачайте `modular_bot.tar.gz` на сервер.

### Шаг 2: Backup старого бота

```bash
cd /root/telegram-bot
sudo systemctl stop telegram-bot

# Backup старой версии
tar -czf bot_backup_$(date +%Y%m%d_%H%M).tar.gz bot.py
```

### Шаг 3: Распакуйте новый бот

```bash
cd /root/telegram-bot

# Распакуйте архив
tar -xzf modular_bot.tar.gz

# Скопируйте файлы
cp -r modular_bot/* .

# Проверьте структуру
ls -la
# Должны быть: bot.py, config.py, mcp_clients/, handlers/, utils/
```

### Шаг 4: Установите зависимости (если нужно)

```bash
source venv/bin/activate
pip install anthropic python-telegram-bot apscheduler
```

### Шаг 5: Проверьте синтаксис

```bash
python3 -m py_compile bot.py
python3 -m py_compile config.py
python3 -m py_compile mcp_clients/*.py
python3 -m py_compile handlers/*.py
python3 -m py_compile utils/*.py
```

### Шаг 6: Запустите бота

```bash
sudo systemctl start telegram-bot
sudo journalctl -u telegram-bot -f
```

**Ожидаемые логи:**

```
INFO - Bot is starting...
INFO - Initializing MCP clients...
INFO - Starting MCP Weather Client...
INFO - ✓ MCP Weather Client initialized
INFO - Starting MCP News Client...
INFO - ✓ MCP News Client initialized
INFO - Starting MCP Mobile Client...
INFO - ✓ MCP Mobile Client initialized
INFO - Starting MCP Ollama Client...        ← НОВОЕ!
INFO - ✓ MCP Ollama Client initialized      ← НОВОЕ!
INFO - All MCP clients initialized
INFO - Bot is running...
```

---

## 🧪 Тестирование:

### Тест 1: Проверка работы бота

В Telegram:
```
/compare Какие команды есть у бота?
```

**Ожидаемо:** Через 10-15 секунд получите сравнение RAG vs No-RAG.

### Тест 2: Проверка модульности

Попробуйте вызвать Python интерпретатор:

```bash
cd /root/telegram-bot
python3

>>> from mcp_clients import MCPOllamaClient
>>> print("✓ Import works!")
>>> from handlers.rag_compare import compare_rag
>>> print("✓ Handler import works!")
>>> exit()
```

---

## 📊 Что дальше?

### Следующие модули для добавления:

1. **handlers/basic.py** - команды /start, /clear, /stats, /debug
2. **handlers/weather.py** - погодные команды
3. **handlers/mobile.py** - команды для Android
4. **utils/conversation.py** - история разговоров
5. **utils/scheduler.py** - планировщик задач

### Как добавить новый handler:

1. Создайте файл `handlers/new_feature.py`
2. Добавьте импорт в `handlers/__init__.py`
3. Зарегистрируйте в `bot.py`:
   ```python
   from handlers.new_feature import new_command
   application.add_handler(CommandHandler("new", new_command))
   ```

---

## 🐛 Troubleshooting:

### Ошибка: ModuleNotFoundError

**Причина:** Python не видит модули

**Решение:**
```bash
cd /root/telegram-bot
# Убедитесь что в директории есть __init__.py
touch __init__.py
```

### Ошибка: MCP Ollama not initialized

**Причина:** Ollama клиент не запустился

**Решение:**
```bash
# Проверьте SSH туннель
ss -tulnp | grep 2222

# Проверьте логи
sudo journalctl -u telegram-bot -n 100
```

### Бот не отвечает на /compare

**Причина:** Handler не зарегистрирован

**Решение:**
Проверьте что в `bot.py` есть строка:
```python
application.add_handler(CommandHandler("compare", compare_rag))
```

---

## ✅ Готово!

Теперь у вас:
- ✅ Модульная архитектура
- ✅ Чистый, читаемый код
- ✅ Команда /compare работает
- ✅ Легко добавлять новые фичи

---

## 🎯 Следующий шаг:

После успешного запуска и теста `/compare` мы перейдём к **Шагу 3: Анализ результатов**.

Мы:
1. Соберём данные из `rag_comparisons.json`
2. Проанализируем где RAG помог, где нет
3. Сделаем выводы и рекомендации

**Протестируйте /compare и покажите результаты!** 🚀
