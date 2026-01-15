import logging
from telegram import Update
from telegram.ext import ContextTypes
import anthropic
from config import ANTHROPIC_API_KEY

logger = logging.getLogger(__name__)

async def handle_tasks_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать задачи с опциональными фильтрами"""
    logger.info("[TASKS] Entering handle_tasks_command")
    
    try:
        # Динамический импорт для получения актуального клиента
        import mcp_clients
        from mcp_clients import mcp_task_client
        
        logger.info(f"[TASKS] mcp_task_client type: {type(mcp_task_client)}")
        
        if mcp_task_client is None:
            await update.message.reply_text("❌ Task MCP не инициализирован. Попробуйте позже.")
            return
        
        # Получаем аргументы фильтра
        args = context.args
        filter_type = args[0] if args else None
        
        logger.info(f"[TASKS] Filter: {filter_type}")
        
        # Вызываем MCP
        if filter_type in ["high", "medium", "low", "urgent"]:
            result = await mcp_task_client.get_tasks(priority=filter_type)
        elif filter_type in ["open", "in_progress", "completed", "blocked"]:
            result = await mcp_task_client.get_tasks(status=filter_type)
        elif filter_type:
            result = await mcp_task_client.get_tasks(assignee=filter_type)
        else:
            result = await mcp_task_client.get_tasks()
        
        logger.info(f"[TASKS] Got result: {result.get('count', 0)} tasks")
        
        # Форматируем ответ
        tasks = result.get("tasks", [])
        if not tasks:
            await update.message.reply_text("📋 Задач не найдено")
            return
        
        response = f"📋 *Задачи ({len(tasks)})*\n\n"
        
        for task in tasks:
            priority_emoji = {
                "urgent": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢"
            }.get(task["priority"], "⚪")
            
            status_emoji = {
                "open": "📂",
                "in_progress": "🔄",
                "completed": "✅",
                "blocked": "🚫"
            }.get(task["status"], "📄")
            
            response += f"{priority_emoji} {status_emoji} *{task['id']}*: {task['title']}\n"
            response += f"   Приоритет: {task['priority']} | Статус: {task['status']}\n"
            if task.get("assignee"):
                response += f"   Исполнитель: {task['assignee']}\n"
            response += "\n"
        
        # Статистика
        stats = result.get("stats")
        if not stats:
            stats_result = await mcp_task_client.get_stats()
            stats = stats_result.get("stats", {})
        
        if stats:
            response += "\n📊 *Статистика:*\n"
            response += f"Всего: {stats['total']}\n"
            response += f"Открыто: {stats['by_status']['open']} | "
            response += f"В работе: {stats['by_status']['in_progress']}\n"
        
        try:
            await update.message.reply_text(response, parse_mode='Markdown')
        except:
            await update.message.reply_text(response)
        
        logger.info("[TASKS] Command completed successfully")
        
    except Exception as e:
        logger.error(f"[TASKS] Error: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_task_create_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Создать новую задачу"""
    try:
        import mcp_clients
        from mcp_clients import mcp_task_client
        
        if mcp_task_client is None:
            await update.message.reply_text("❌ Task MCP не инициализирован")
            return
        
        # Простой интерфейс создания
        await update.message.reply_text(
            "📝 *Создание задачи*\n\n"
            "Формат: `/task_create <приоритет> <название>`\n"
            "Приоритет: low, medium, high, urgent\n\n"
            "Пример:\n"
            "`/task_create high Исправить критический баг`",
            parse_mode='Markdown'
        )
        
        args = context.args
        if len(args) < 2:
            return
        
        priority = args[0].lower()
        title = " ".join(args[1:])
        
        if priority not in ["low", "medium", "high", "urgent"]:
            await update.message.reply_text("❌ Неверный приоритет. Используйте: low, medium, high, urgent")
            return
        
        # Создаём задачу
        result = await mcp_task_client.create_task(
            title=title,
            priority=priority
        )
        
        if result.get("success"):
            task = result["task"]
            await update.message.reply_text(
                f"✅ Задача создана!\n\n"
                f"ID: {task['id']}\n"
                f"Название: {task['title']}\n"
                f"Приоритет: {task['priority']}\n"
                f"Статус: {task['status']}"
            )
        else:
            await update.message.reply_text(f"❌ Ошибка создания задачи")
        
    except Exception as e:
        logger.error(f"Error in task_create: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_task_update_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обновить задачу"""
    try:
        import mcp_clients
        from mcp_clients import mcp_task_client
        
        if mcp_task_client is None:
            await update.message.reply_text("❌ Task MCP не инициализирован")
            return
        
        args = context.args
        if len(args) < 3:
            await update.message.reply_text(
                "📝 *Обновление задачи*\n\n"
                "Формат: `/task_update <id> <поле> <значение>`\n\n"
                "Поля:\n"
                "• status: open, in_progress, completed, blocked\n"
                "• priority: low, medium, high, urgent\n"
                "• assignee: имя исполнителя\n\n"
                "Пример:\n"
                "`/task_update task_0001 status in_progress`",
                parse_mode='Markdown'
            )
            return
        
        task_id = args[0]
        field = args[1].lower()
        value = " ".join(args[2:])
        
        # Обновляем задачу
        update_args = {field: value}
        result = await mcp_task_client.update_task(task_id, **update_args)
        
        if result.get("success"):
            task = result["task"]
            await update.message.reply_text(
                f"✅ Задача обновлена!\n\n"
                f"ID: {task['id']}\n"
                f"Название: {task['title']}\n"
                f"Статус: {task['status']}\n"
                f"Приоритет: {task['priority']}"
            )
        else:
            await update.message.reply_text(f"❌ {result.get('error', 'Ошибка обновления')}")
        
    except Exception as e:
        logger.error(f"Error in task_update: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")


async def handle_ask_team_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Умный ассистент с RAG + Tasks + Claude"""
    try:
        import mcp_clients
        from mcp_clients import mcp_task_client
        
        if not context.args:
            await update.message.reply_text(
                "🤖 *Командный ассистент*\n\n"
                "Задайте вопрос о проекте или задачах.\n\n"
                "Примеры:\n"
                "• `/ask_team Покажи задачи high приоритета и предложи что делать первым`\n"
                "• `/ask_team Какие задачи в работе?`\n"
                "• `/ask_team Что нужно сделать для миграции на PostgreSQL?`",
                parse_mode='Markdown'
            )
            return
        
        question = " ".join(context.args)
        
        # Получаем контекст задач
        tasks_context = ""
        if mcp_task_client:
            try:
                result = await mcp_task_client.get_tasks()
                tasks = result.get("tasks", [])
                if tasks:
                    tasks_context = "\n\n**Текущие задачи:**\n"
                    for task in tasks[:10]:  # Топ-10
                        tasks_context += f"- [{task['priority']}] {task['id']}: {task['title']} ({task['status']})\n"
            except Exception as e:
                logger.error(f"Failed to get tasks context: {e}")
        
        # Получаем RAG контекст
        rag_context = ""
        try:
            from utils.rag_functions import get_rag_answer
            rag_result = await get_rag_answer(question, top_k=5, rerank_mode="light")
            if rag_result and rag_result.get("answer"):
                rag_context = f"\n\n**Контекст из документации:**\n{rag_result['answer']}"
        except Exception as e:
            logger.error(f"Failed to get RAG context: {e}")
        
        # Формируем промпт для Claude
        prompt = f"""Ты - командный ассистент проекта Telegram бота с Claude AI.

**Вопрос пользователя:**
{question}
{tasks_context}
{rag_context}

**Твоя задача:**
1. Проанализируй текущие задачи
2. Используй контекст из документации
3. Дай конкретные рекомендации
4. Предложи приоритеты если нужно

Ответь кратко и по делу."""

        # Запрос к Claude
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            temperature=0.3,
            messages=[{"role": "user", "content": prompt}]
        )
        
        response = message.content[0].text
        
        try:
            await update.message.reply_text(response, parse_mode='Markdown')
        except:
            await update.message.reply_text(response)
        
    except Exception as e:
        logger.error(f"Error in ask_team: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
