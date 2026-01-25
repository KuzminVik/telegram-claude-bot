"""
Handler для команды /analyze - анализ данных через локальную LLM
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from telegram.error import BadRequest

logger = logging.getLogger(__name__)


async def analyze_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик команды /analyze <вопрос>
    
    Использует локальную LLM для генерации Python кода анализа данных
    """
    
    user_id = update.effective_user.id
    args = context.args
    
    # Проверка аргументов
    if not args:
        help_text = """📊 **Анализ данных CRM**

Используйте: `/analyze <вопрос>`

**Примеры вопросов:**
• Сколько всего тикетов?
• Какой процент тикетов успешно решён?
• Покажи распределение по статусам
• Сколько тикетов с приоритетом high?
• Какие самые частые проблемы?
• Среднее время ответа на тикет
• Построй график по статусам

**Как работает:**
1. Локальная LLM генерирует Python код
2. Код выполняется на сервере
3. Результат + график (если есть) отправляются вам

**Данные:** CRM тикеты (tickets.json)"""
        
        try:
            await update.message.reply_text(help_text, parse_mode='Markdown')
        except:
            await update.message.reply_text(help_text.replace('*', '').replace('`', ''))
        return
    
    # Получить вопрос
    question = " ".join(args)
    
    # Проверить доступность локальной LLM
    from mcp_clients import ollama_local_chat_client
    
    if ollama_local_chat_client is None:
        await update.message.reply_text(
            "❌ Локальная LLM недоступна. Анализ данных работает только в local режиме."
        )
        return
    
    # Отправить уведомление о начале анализа
    status_msg = await update.message.reply_text(
        f"🔄 Анализирую данные...\n\n**Вопрос:** {question}\n\n"
        "⏳ Генерирую код через LLM..."
    )
    
    try:
        # Импортировать функцию анализа
        from utils.data_analysis import analyze_data
        
        # Выполнить анализ
        result = await analyze_data(question, ollama_local_chat_client)
        
        if result["success"]:
            # Формат ответа (без показа кода)
            response = f"✅ **Результат:**\n\n{result['answer']}"
            
            try:
                # Удалить статусное сообщение
                try:
                    await status_msg.delete()
                except BadRequest:
                    pass  # Сообщение уже удалено или недоступно
                
                # Отправить результат
                await update.message.reply_text(response, parse_mode='Markdown')
                
                # Отправить график если есть
                if result["plot_path"]:
                    with open(result["plot_path"], 'rb') as f:
                        await update.message.reply_photo(
                            photo=f,
                            caption="📊 Визуализация данных"
                        )
            except Exception as e:
                logger.warning(f"Markdown error, sending plain text: {e}")
                try:
                    await status_msg.delete()
                except BadRequest:
                    pass
                await update.message.reply_text(response.replace('*', '').replace('_', '').replace('`', ''))
                
                if result["plot_path"]:
                    with open(result["plot_path"], 'rb') as f:
                        await update.message.reply_photo(photo=f)
        else:
            # Ошибка анализа
            error_msg = f"❌ **Ошибка анализа:**\n\n{result['error']}"
            
            # Показать код только при ошибке для отладки
            if result["code"]:
                error_msg += f"\n\n📝 _Код для отладки:_\n`{result['code'][:300]}`"
            
            try:
                try:
                    await status_msg.delete()
                except BadRequest:
                    pass
                await update.message.reply_text(error_msg, parse_mode='Markdown')
            except:
                try:
                    await status_msg.delete()
                except BadRequest:
                    pass
                await update.message.reply_text(error_msg.replace('*', '').replace('_', '').replace('`', ''))
                
    except Exception as e:
        logger.error(f"Error in analyze_command: {e}", exc_info=True)
        try:
            await status_msg.delete()
        except:
            pass
        await update.message.reply_text(f"❌ Ошибка выполнения анализа: {str(e)}")
