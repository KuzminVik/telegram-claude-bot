"""
Handler для автоматического code review Pull Request
Использует Claude AI + RAG + GitHub MCP для анализа кода
Отправляет уведомления в Telegram
"""

import logging
import asyncio
from anthropic import Anthropic
from telegram import Bot
from config import (
    ANTHROPIC_API_KEY, 
    GITHUB_REPO_OWNER, 
    GITHUB_REPO_NAME, 
    RAG_VECTOR_STORE_NAME,
    ADMIN_CHAT_ID,
    TELEGRAM_TOKEN
)
from utils.github_api import post_pr_comment, get_pr_diff
from utils.rag_functions import get_rag_answer
# from mcp_clients.github_client import mcp_github_client  # TODO: добавить позже

logger = logging.getLogger(__name__)

# Инициализация Claude
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Инициализация Telegram Bot для уведомлений
telegram_bot = Bot(token=TELEGRAM_TOKEN)

def process_pr_review(webhook_payload):
    """
    Основная функция обработки PR для ревью
    
    Args:
        webhook_payload: JSON payload от GitHub webhook
    """
    try:
        pr_data = webhook_payload.get('pull_request', {})
        pr_number = pr_data.get('number')
        pr_title = pr_data.get('title')
        pr_description = pr_data.get('body', '')
        pr_author = pr_data.get('user', {}).get('login', 'unknown')
        pr_url = pr_data.get('html_url', '')
        
        repo_data = webhook_payload.get('repository', {})
        repo_owner = repo_data.get('owner', {}).get('login', GITHUB_REPO_OWNER)
        repo_name = repo_data.get('name', GITHUB_REPO_NAME)
        
        logger.info(f"Начинаю ревью PR #{pr_number}: {pr_title}")
        
        # Запускаем асинхронную обработку
        asyncio.run(
            review_pull_request(
                repo_owner, repo_name, pr_number,
                pr_title, pr_description, pr_author, pr_url
            )
        )
        
    except Exception as e:
        logger.error(f"Ошибка в process_pr_review: {e}", exc_info=True)
        raise

async def review_pull_request(
    owner, repo, pr_number, 
    pr_title, pr_description, pr_author, pr_url
):
    """
    Асинхронное выполнение code review
    
    Args:
        owner: Владелец репозитория
        repo: Название репозитория
        pr_number: Номер PR
        pr_title: Заголовок PR
        pr_description: Описание PR
        pr_author: Автор PR
        pr_url: URL Pull Request
    """
    try:
        # 0. Отправляем уведомление о начале ревью
        await notify_telegram_start(pr_number, pr_title, pr_author, pr_url)
        
        # 1. Получаем diff через GitHub API
        logger.info(f"Получаю diff для PR #{pr_number}")
        diff_content = await get_pr_diff(owner, repo, pr_number)
        
        if not diff_content:
            logger.warning(f"Не удалось получить diff для PR #{pr_number}")
            return
        
        # 2. Получаем список изменённых файлов через MCP
        logger.info("Получаю список изменённых файлов через MCP")
        changed_files = await get_changed_files_mcp(owner, repo, pr_number)
        
        # 3. RAG поиск по документации проекта
        logger.info("Выполняю RAG поиск по документации")
        rag_context = await get_rag_context(pr_title, diff_content)
        
        # 4. Формируем промпт для Claude
        review_prompt = build_review_prompt(
            pr_title, pr_description, pr_author,
            diff_content, changed_files, rag_context
        )
        
        # 5. Получаем ревью от Claude
        logger.info("Отправляю запрос Claude для ревью")
        review_text = await get_claude_review(review_prompt)
        
        # 6. Постим комментарий в PR
        logger.info(f"Публикую ревью в PR #{pr_number}")
        await post_pr_comment(owner, repo, pr_number, review_text)
        
        # 7. Отправляем результат ревью в Telegram
        await notify_telegram_result(pr_number, pr_title, pr_url, review_text)
        
        logger.info(f"Ревью PR #{pr_number} завершено успешно")
        
    except Exception as e:
        logger.error(f"Ошибка при ревью PR #{pr_number}: {e}", exc_info=True)
        # Постим комментарий об ошибке
        error_comment = (
            f"❌ **Автоматическое ревью не удалось**\n\n"
            f"Произошла ошибка при анализе PR: {str(e)}\n\n"
            f"Пожалуйста, проверьте логи бота."
        )
        try:
            await post_pr_comment(owner, repo, pr_number, error_comment)
            await notify_telegram_error(pr_number, pr_title, pr_url, str(e))
        except:
            pass

async def notify_telegram_start(pr_number, pr_title, pr_author, pr_url):
    """
    Отправка уведомления в Telegram о начале ревью
    
    Args:
        pr_number: Номер PR
        pr_title: Заголовок PR
        pr_author: Автор PR
        pr_url: URL PR
    """
    try:
        message = f"""🔔 **Новый Pull Request**

📝 **PR #{pr_number}:** {pr_title}
👤 **Автор:** @{pr_author}

🔄 Начинаю автоматическое ревью...

🔗 [Открыть PR]({pr_url})
"""
        
        await telegram_bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        logger.info(f"Уведомление о начале ревью PR #{pr_number} отправлено в Telegram")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления в Telegram: {e}")

async def notify_telegram_result(pr_number, pr_title, pr_url, review_text):
    """
    Отправка результата ревью в Telegram
    
    Args:
        pr_number: Номер PR
        pr_title: Заголовок PR
        pr_url: URL PR
        review_text: Текст ревью от Claude
    """
    try:
        # Telegram ограничение на длину сообщения - 4096 символов
        MAX_MESSAGE_LENGTH = 4000
        
        # Формируем заголовок
        header = f"""✅ **Ревью завершено**

📝 **PR #{pr_number}:** {pr_title}
🔗 [Открыть PR]({pr_url})

---

"""
        
        # Если ревью слишком длинное, обрезаем и добавляем ссылку
        if len(header + review_text) > MAX_MESSAGE_LENGTH:
            truncated_review = review_text[:MAX_MESSAGE_LENGTH - len(header) - 200]
            message = header + truncated_review + f"\n\n...\n\n_(Полное ревью см. в комментарии к PR)_\n\n🔗 [Открыть PR]({pr_url})"
        else:
            message = header + review_text
        
        await telegram_bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        logger.info(f"Результат ревью PR #{pr_number} отправлен в Telegram")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке результата ревью в Telegram: {e}")
        # Пытаемся отправить без форматирования если Markdown не сработал
        try:
            simple_message = f"✅ Ревью PR #{pr_number} завершено\n\n{pr_url}\n\nСм. комментарий в GitHub"
            await telegram_bot.send_message(
                chat_id=ADMIN_CHAT_ID,
                text=simple_message
            )
        except:
            pass

async def notify_telegram_error(pr_number, pr_title, pr_url, error_message):
    """
    Отправка уведомления об ошибке в Telegram
    
    Args:
        pr_number: Номер PR
        pr_title: Заголовок PR
        pr_url: URL PR
        error_message: Сообщение об ошибке
    """
    try:
        message = f"""❌ **Ошибка при ревью**

📝 **PR #{pr_number}:** {pr_title}

⚠️ **Ошибка:** {error_message}

🔗 [Открыть PR]({pr_url})
"""
        
        await telegram_bot.send_message(
            chat_id=ADMIN_CHAT_ID,
            text=message,
            parse_mode='Markdown',
            disable_web_page_preview=True
        )
        logger.info(f"Уведомление об ошибке для PR #{pr_number} отправлено в Telegram")
        
    except Exception as e:
        logger.error(f"Ошибка при отправке уведомления об ошибке в Telegram: {e}")

async def get_changed_files_mcp(owner, repo, pr_number):
    """
    Получение списка изменённых файлов через GitHub MCP
    
    Returns:
        list: Список путей изменённых файлов
    """
    try:
        # Используем GitHub MCP для получения информации о PR
        # TODO: Добавить метод в mcp_clients/github_client.py
        # Пока возвращаем пустой список
        return []
    except Exception as e:
        logger.error(f"Ошибка при получении файлов через MCP: {e}")
        return []

async def get_rag_context(pr_title, diff_content):
    """
    Получение контекста из документации через RAG
    
    Args:
        pr_title: Заголовок PR
        diff_content: Содержимое diff
    
    Returns:
        str: Релевантный контекст из документации
    """
    try:
        # Формируем запрос для RAG из заголовка и ключевых изменений
        # Берём первые 500 символов diff для контекста
        query_parts = [pr_title]
        
        # Добавляем ключевые слова из diff
        if diff_content:
            # Извлекаем изменённые файлы из diff
            files = []
            for line in diff_content.split('\n')[:20]:  # Первые 20 строк
                if line.startswith('diff --git'):
                    # Пример: diff --git a/config.py b/config.py
                    parts = line.split()
                    if len(parts) >= 4:
                        file_path = parts[2].replace('a/', '')
                        files.append(file_path)
            
            if files:
                query_parts.append(f"Изменённые файлы: {', '.join(files)}")
            
            # Добавляем краткое содержимое изменений
            diff_preview = diff_content[:500].replace('\n', ' ')
            query_parts.append(f"Изменения: {diff_preview}")
        
        query = "\n".join(query_parts)
        
        logger.info(f"RAG запрос: {query[:200]}...")
        
        # Выполняем RAG поиск с режимом 'light' (топ-5 документов)
        rag_result = await get_rag_answer(
            query=query,
            rerank_mode='light',
            store_name=RAG_VECTOR_STORE_NAME
        )
        
        if rag_result and 'answer' in rag_result:
            logger.info(
                f"RAG контекст получен: {rag_result.get('chunks_used', 0)} чанков, "
                f"{rag_result.get('time', 0)}с"
            )
            return rag_result['answer']
        else:
            logger.warning("RAG не вернул результат")
            return ""
        
    except Exception as e:
        logger.error(f"Ошибка при RAG поиске: {e}", exc_info=True)
        return ""

def build_review_prompt(
    pr_title, pr_description, pr_author,
    diff_content, changed_files, rag_context
):
    """
    Формирование промпта для Claude
    
    Returns:
        str: Промпт для ревью
    """
    # Определяем есть ли контекст из RAG
    context_section = ""
    if rag_context:
        context_section = f"""
**Контекст из документации проекта:**
{rag_context}

---
"""
    else:
        context_section = """
**Контекст из документации проекта:**
⚠️ RAG контекст недоступен. Проводи ревью на основе общих best practices.

---
"""
    
    prompt = f"""Ты — senior code reviewer для Telegram бота с Claude AI.

**Pull Request:** {pr_title}
**Автор:** {pr_author}
**Описание:** {pr_description or 'Нет описания'}

{context_section}

**Изменённые файлы:**
{', '.join(changed_files) if changed_files else 'Список файлов недоступен'}

**Diff изменений:**
```diff
{diff_content[:3000]}  # Ограничение 3000 символов
```

**Задача:**
Проведи детальное code review, проверь:

1. **Архитектура и дизайн:**
   - Соответствие модульной архитектуре проекта
   - Separation of Concerns
   - Не нарушает ли изменение принципы проекта

2. **Качество кода:**
   - Python best practices (PEP 8)
   - Обработка ошибок (try/except)
   - Типизация (type hints)
   - Логирование
   - Документация (docstrings)

3. **Функциональность:**
   - Корректность логики
   - Обработка edge cases
   - Асинхронность (async/await)

4. **Безопасность:**
   - Валидация входных данных
   - Управление секретами
   - SQL injection / command injection

5. **Интеграция:**
   - Работа с MCP клиентами
   - Работа с GitHub API
   - Совместимость с существующим кодом

**Формат ответа:**
Дай структурированное ревью в формате Markdown:

## 🔍 Code Review Summary

**Общая оценка:** ✅ Approve / ⚠️ Request Changes / ❌ Reject

### ✨ Что хорошо:
- ...

### ⚠️ Замечания:
- ...

### 🐛 Потенциальные проблемы:
- ...

### 💡 Рекомендации:
- ...

### 📝 Итог:
Краткое заключение и рекомендация (approve/changes requested).
"""
    return prompt

async def get_claude_review(prompt):
    """
    Получение ревью от Claude
    
    Args:
        prompt: Промпт для анализа
    
    Returns:
        str: Текст ревью
    """
    try:
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            temperature=0.3,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )
        
        review_text = response.content[0].text
        return review_text
        
    except Exception as e:
        logger.error(f"Ошибка при получении ревью от Claude: {e}")
        raise
