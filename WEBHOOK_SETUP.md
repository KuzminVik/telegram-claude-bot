# 🔧 Настройка GitHub Webhook для автоматического Code Review

## Шаг 1: Подготовка сервера

### 1.1 Установка зависимостей

```bash
cd /root/telegram-bot
source venv/bin/activate
pip install flask==3.0.0 aiohttp==3.9.1 gunicorn==21.2.0
```

### 1.2 Обновление config.py

Добавить в конец файла `/root/telegram-bot/config.py`:

```python
# ===== WEBHOOK CONFIGURATION =====
WEBHOOK_PORT = int(os.getenv('WEBHOOK_PORT', 8080))
GITHUB_WEBHOOK_SECRET = os.getenv('GITHUB_WEBHOOK_SECRET', '')

# ===== CODE REVIEW CONFIGURATION =====
MAX_DIFF_SIZE = 5000
MAX_FILES_FOR_REVIEW = 10
REVIEW_TEMPERATURE = 0.3
REVIEW_MODEL = "claude-sonnet-4-20250514"
```

### 1.3 Копирование файлов

```bash
# Скопировать файлы на сервер
scp webhook_server.py claude_helper@45.95.232.34:/root/telegram-bot/
scp handlers/pr_review.py claude_helper@45.95.232.34:/root/telegram-bot/handlers/
scp utils/github_api.py claude_helper@45.95.232.34:/root/telegram-bot/utils/
```

## Шаг 2: Настройка systemd service

### 2.1 Создание service файла

```bash
sudo nano /etc/systemd/system/webhook-server.service
```

Вставить содержимое из `webhook-server.service`, заменив:
- `YOUR_GITHUB_TOKEN` - на реальный токен
- `YOUR_WEBHOOK_SECRET` - на сгенерированный секрет
- `YOUR_ANTHROPIC_KEY` - на API ключ

### 2.2 Генерация webhook secret

```bash
# Генерируем случайный секрет
openssl rand -hex 32
```

Сохраните этот секрет - он понадобится при настройке webhook в GitHub.

### 2.3 Запуск сервиса

```bash
sudo systemctl daemon-reload
sudo systemctl enable webhook-server
sudo systemctl start webhook-server
sudo systemctl status webhook-server
```

### 2.4 Проверка логов

```bash
sudo journalctl -u webhook-server -f
```

## Шаг 3: Настройка firewall

### 3.1 Открыть порт 8080

```bash
sudo ufw allow 8080/tcp
sudo ufw status
```

## Шаг 4: Настройка webhook в GitHub

### 4.1 Перейти в Settings репозитория

1. Открыть https://github.com/KuzminVik/telegram-claude-bot
2. Settings → Webhooks → Add webhook

### 4.2 Заполнить параметры

**Payload URL:**
```
http://45.95.232.34:8080/webhook/github
```

**Content type:**
```
application/json
```

**Secret:**
```
[Вставить сгенерированный секрет из шага 2.2]
```

**SSL verification:**
```
Disable SSL verification (для HTTP)
```

**Events:**
Выбрать:
- ✅ Pull requests
- ✅ Pull request reviews (опционально)

**Active:**
- ✅ Включено

### 4.3 Сохранить

Нажать "Add webhook"

## Шаг 5: Тестирование

### 5.1 Health check

```bash
curl http://45.95.232.34:8080/health
```

Ожидаемый ответ:
```json
{
  "status": "healthy",
  "service": "github-webhook-server"
}
```

### 5.2 Создать тестовый PR

1. Создать новую ветку
2. Сделать небольшое изменение
3. Открыть Pull Request
4. Проверить логи webhook сервера:

```bash
sudo journalctl -u webhook-server -f
```

5. Через 30-60 секунд в PR должен появиться комментарий с ревью

## Шаг 6: Мониторинг

### Проверка статуса сервисов

```bash
# Webhook сервер
sudo systemctl status webhook-server

# Telegram бот
sudo systemctl status telegram-bot
```

### Логи

```bash
# Webhook сервер
sudo journalctl -u webhook-server -n 100

# Access log
sudo tail -f /var/log/webhook-server-access.log

# Error log
sudo tail -f /var/log/webhook-server-error.log
```

## Устранение проблем

### Webhook не получает события

1. Проверить GitHub webhook deliveries (Recent Deliveries)
2. Убедиться что порт 8080 открыт: `sudo netstat -tlnp | grep 8080`
3. Проверить firewall: `sudo ufw status`

### Ошибки при ревью

1. Проверить наличие GITHUB_TOKEN
2. Проверить права токена (должен иметь `repo` scope)
3. Проверить логи: `sudo journalctl -u webhook-server -f`

### Claude API ошибки

1. Проверить ANTHROPIC_API_KEY
2. Проверить квоты API
3. Уменьшить MAX_DIFF_SIZE если превышается context window

## Дополнительно

### Использование HTTPS (рекомендуется)

Для production настоятельно рекомендуется использовать HTTPS:

1. Установить nginx как reverse proxy
2. Настроить Let's Encrypt SSL
3. Проксировать запросы на localhost:8080

Пример nginx конфигурации:

```nginx
server {
    listen 443 ssl;
    server_name yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    location /webhook/github {
        proxy_pass http://localhost:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Автоматический перезапуск при изменениях

Добавить в systemd service:

```ini
[Service]
ExecReload=/bin/kill -HUP $MAINPID
```

Перезагрузка без downtime:
```bash
sudo systemctl reload webhook-server
```
