# 🚀 Быстрый старт - Деплой webhook сервера

## Шаг 1: Загрузка файлов на сервер

```bash
# Подключение к серверу
ssh claude_helper@45.95.232.34
# Пароль: TempPass123!

# Переход в директорию проекта
cd /root/telegram-bot
```

Скопируйте файлы:
- `webhook_server.py` → `/root/telegram-bot/`
- `handlers/pr_review.py` → `/root/telegram-bot/handlers/`
- `utils/github_api.py` → `/root/telegram-bot/utils/`

## Шаг 2: Установка зависимостей

```bash
cd /root/telegram-bot
source venv/bin/activate
pip install flask==3.0.0 aiohttp==3.9.1 gunicorn==21.2.0
```

## Шаг 3: Обновление config.py

Добавьте в конец `/root/telegram-bot/config.py`:

```python
# ===== WEBHOOK CONFIGURATION =====
WEBHOOK_PORT = int(os.getenv("WEBHOOK_PORT", 8080))
GITHUB_WEBHOOK_SECRET = os.getenv("GITHUB_WEBHOOK_SECRET", "")

# ===== CODE REVIEW CONFIGURATION =====
MAX_DIFF_SIZE = 5000
MAX_FILES_FOR_REVIEW = 10
REVIEW_TEMPERATURE = 0.3
REVIEW_MODEL = "claude-sonnet-4-20250514"
```

## Шаг 4: Генерация webhook secret

```bash
openssl rand -hex 32
```

Сохраните результат - это ваш `WEBHOOK_SECRET`.

## Шаг 5: Создание systemd service

Откройте файл `webhook-server.service` и замените:
- `YOUR_GITHUB_TOKEN` → ваш GitHub token
- `YOUR_WEBHOOK_SECRET` → сгенерированный секрет
- `YOUR_ANTHROPIC_KEY` → ваш Anthropic API key

Затем:

```bash
sudo cp webhook-server.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable webhook-server
sudo systemctl start webhook-server
sudo systemctl status webhook-server
```

## Шаг 6: Firewall

```bash
sudo ufw allow 8080/tcp
sudo ufw status
```

## Шаг 7: GitHub Webhook

1. Откройте: https://github.com/KuzminVik/telegram-claude-bot/settings/hooks
2. "Add webhook"
3. **Payload URL**: `http://45.95.232.34:8080/webhook/github`
4. **Content type**: `application/json`
5. **Secret**: [вставьте сгенерированный секрет]
6. **Events**: отметьте "Pull requests"
7. **Active**: ✅
8. "Add webhook"

## Шаг 8: Проверка

```bash
# Health check
curl http://45.95.232.34:8080/health

# Логи в реальном времени
sudo journalctl -u webhook-server -f
```

## Тестирование

Создайте тестовый PR в репозитории и проверьте:
1. Webhook получен (логи)
2. Комментарий с ревью появился в PR
3. Нет ошибок в логах

## Устранение проблем

Если не работает:

```bash
# Проверить статус
sudo systemctl status webhook-server

# Проверить логи
sudo journalctl -u webhook-server -n 100

# Проверить порт
sudo netstat -tlnp | grep 8080

# Перезапустить
sudo systemctl restart webhook-server
```

---

**Полная документация**: см. `WEBHOOK_SETUP.md`
