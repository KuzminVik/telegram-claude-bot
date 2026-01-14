"""
Support handler - обработка вопросов пользователей с использованием RAG и CRM
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from anthropic import AsyncAnthropic
from config import ANTHROPIC_API_KEY, CLAUDE_MODEL
from utils.crm_functions import (
    create_or_update_user,
    get_user_tickets,
    create_ticket,
    update_ticket,
    get_ticket_context
)
from utils.rag_functions import get_rag_answer

logger = logging.getLogger(__name__)
client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)


async def support_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработка команды /support <вопрос>
    
    Пример: /support Почему не работает /weather_subscribe?
    """
    user = update.effective_user
    user_id = user.id
    
    # Проверяем что есть вопрос
    if not context.args:
        await update.message.reply_text(
            "❓ **Как задать вопрос в поддержку:**\n\n"
            "Используйте: `/support <ваш вопрос>`\n\n"
            "**Примеры:**\n"
            "• `/support Как работает команда /weather_subscribe?`\n"
            "• `/support Почему бот не отвечает на мои сообщения?`\n"
            "• `/support Как очистить историю диалога?`\n\n"
            "Я найду ответ в документации бота и создам тикет для отслеживания вашего вопроса.",
            parse_mode='Markdown'
        )
        return
    
    # Получаем вопрос
    question = ' '.join(context.args)
    
    # Отправляем статус
    status_msg = await update.message.reply_text("🔍 Ищу ответ в базе знаний...")
    
    try:
        # 1. Создаём/обновляем пользователя в CRM
        logger.info(f"[Support] User {user_id} ({user.username}): {question}")
        create_or_update_user(
            telegram_id=user_id,
            username=user.username,
            first_name=user.first_name
        )
        
        # 2. Получаем контекст тикетов пользователя
        ticket_context = get_ticket_context(user_id)
        open_tickets = get_user_tickets(user_id, status="open")
        
        # 3. Ищем ответ через RAG
        await status_msg.edit_text("🧠 Анализирую документацию...")
        
        rag_result = await get_rag_answer(
            query=question,
            rerank_mode='light'
        )
        
        if not rag_result or not rag_result.get('answer'):
            # RAG недоступен - используем базовый промпт
            await status_msg.edit_text("💬 Формирую ответ...")
            rag_context = "База знаний временно недоступна. Отвечаю на основе общих знаний."
        else:
            rag_context = rag_result['answer']
            chunks_used = rag_result.get('chunks_used', 0)
            logger.info(f"[Support] RAG found answer using {chunks_used} chunks")
        
        # 4. Формируем промпт для Claude с полным контекстом
        await status_msg.edit_text("🤖 Claude анализирует...")
        
        system_prompt = f"""Ты - ассистент технической поддержки Telegram бота с Claude AI.

**Твоя задача:**
- Помочь пользователю решить проблему или ответить на вопрос
- Использовать информацию из документации (RAG контекст)
- Учитывать историю тикетов пользователя
- Давать чёткие, конкретные инструкции
- Быть дружелюбным и профессиональным

**Информация о пользователе:**
{ticket_context}

**Контекст из документации бота (RAG):**
{rag_context}

**Формат ответа:**
1. Краткий ответ на вопрос
2. Пошаговые инструкции (если нужно)
3. Дополнительные советы (опционально)

Отвечай на русском языке. Используй Markdown для форматирования."""

        user_prompt = f"**Вопрос пользователя:** {question}"
        
        # 5. Запрос к Claude
        response = await client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=2000,
            temperature=0.3,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )
        
        assistant_answer = response.content[0].text
        
        # 6. Создаём или обновляем тикет
        if not open_tickets:
            # Создаём новый тикет
            ticket = create_ticket(
                telegram_id=user_id,
                question=question,
                assistant_response=assistant_answer
            )
            ticket_info = f"\n\n📋 Создан тикет: `{ticket['id']}`"
            logger.info(f"[Support] Created ticket {ticket['id']} for user {user_id}")
        else:
            # Обновляем последний открытый тикет
            last_ticket = open_tickets[0]
            update_ticket(
                ticket_id=last_ticket['id'],
                user_message=question,
                assistant_response=assistant_answer
            )
            ticket_info = f"\n\n📋 Обновлён тикет: `{last_ticket['id']}`"
            logger.info(f"[Support] Updated ticket {last_ticket['id']} for user {user_id}")
        
        # 7. Отправляем ответ пользователю
        await status_msg.delete()
        
        full_response = f"✅ **Ответ поддержки:**\n\n{assistant_answer}{ticket_info}"
        
        # Разбиваем на части если слишком длинный
        if len(full_response) > 4000:
            parts = [full_response[i:i+4000] for i in range(0, len(full_response), 4000)]
            for part in parts:
                try:
                    await update.message.reply_text(part, parse_mode='Markdown')
                except Exception:
                    # Fallback без форматирования
                    await update.message.reply_text(part)
        else:
            try:
                await update.message.reply_text(full_response, parse_mode='Markdown')
            except Exception:
                # Fallback без форматирования
                await update.message.reply_text(full_response)
        
        logger.info(f"[Support] Successfully answered user {user_id}")
        
    except Exception as e:
        logger.error(f"[Support] Error processing support request: {e}", exc_info=True)
        try:
            await status_msg.edit_text(
                "❌ Произошла ошибка при обработке вашего вопроса.\n"
                "Попробуйте позже или обратитесь к администратору."
            )
        except Exception:
            await update.message.reply_text(
                "❌ Произошла ошибка при обработке вашего вопроса.\n"
                "Попробуйте позже или обратитесь к администратору."
            )


async def my_tickets_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Показать мои тикеты (опционально)
    """
    user_id = update.effective_user.id
    
    tickets = get_user_tickets(user_id)
    
    if not tickets:
        await update.message.reply_text(
            "📋 У вас пока нет тикетов.\n\n"
            "Используйте `/support <вопрос>` чтобы задать вопрос.",
            parse_mode='Markdown'
        )
        return
    
    open_tickets = [t for t in tickets if t['status'] == 'open']
    closed_tickets = [t for t in tickets if t['status'] == 'closed']
    
    response = f"📋 **Ваши тикеты:**\n\n"
    
    if open_tickets:
        response += f"**🟢 Открытые ({len(open_tickets)}):**\n"
        for ticket in open_tickets[:5]:  # Показываем до 5
            question_preview = ticket['question'][:60] + "..." if len(ticket['question']) > 60 else ticket['question']
            response += f"• `{ticket['id']}`: {question_preview}\n"
            response += f"  _Создан: {ticket['created_at'][:10]}_\n\n"
    
    if closed_tickets:
        response += f"\n**⚪ Закрытые ({len(closed_tickets)}):**\n"
        for ticket in closed_tickets[:3]:  # Показываем до 3
            question_preview = ticket['question'][:60] + "..." if len(ticket['question']) > 60 else ticket['question']
            response += f"• `{ticket['id']}`: {question_preview}\n"
    
    response += f"\n_Всего тикетов: {len(tickets)}_"
    
    await update.message.reply_text(response, parse_mode='Markdown')
