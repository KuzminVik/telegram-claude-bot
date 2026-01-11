#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Handler - обработчик команды /with_rag с историей
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes
from utils import get_rag_answer
from utils.helpers import send_long_message

logger = logging.getLogger(__name__)

# Хранилище истории RAG диалогов: {user_id: [messages]}
rag_histories = {}
MAX_RAG_HISTORY = 20


async def with_rag_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /with_rag <вопрос> - ответ через RAG с историей диалога
    
    - Ищет контекст в базе документов
    - Сохраняет историю последних 20 сообщений
    - Всегда показывает источники
    """
    user_id = update.effective_user.id
    
    # Проверяем что есть вопрос
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите вопрос после команды.\n\n"
            "Пример: /with_rag Какие команды есть у бота?"
        )
        return
    
    query = ' '.join(context.args)
    logger.info(f"User {user_id} asked (RAG mode): {query}")
    
    # Инициализируем историю для пользователя если её нет
    if user_id not in rag_histories:
        rag_histories[user_id] = []
    
    # Отправляем уведомление о поиске
    status_message = await update.message.reply_text("🔍 Ищу информацию в базе знаний...")
    
    try:
        # Получаем ответ через RAG (light фильтр)
        result = await get_rag_answer(
            query=query,
            rerank_mode='light',
            store_name='bot_knowledge'
        )

        logger.info(f"get_rag_answer returned: {result}")
        logger.info(f"result type: {type(result)}")
        if result:
            logger.info(f"result keys: {result.keys()}")
        
        if not result:
            await status_message.edit_text("❌ Не удалось получить ответ. Попробуйте позже.")
            return
        
        # Сохраняем в историю RAG
        rag_histories[user_id].append({
            'role': 'user',
            'content': query
        })
        rag_histories[user_id].append({
            'role': 'assistant',
            'content': result['answer']
        })
        
        # Обрезаем историю до MAX_RAG_HISTORY сообщений
        if len(rag_histories[user_id]) > MAX_RAG_HISTORY:
            rag_histories[user_id] = rag_histories[user_id][-MAX_RAG_HISTORY:]
        
        # Формируем ответ
        message = "🤖 RAG РЕЖИМ\n\n"
        message += f"❓ Вопрос: {query}\n\n"
        message += "━━━━━━━━━━━━━━━━━━━━\n\n"
        
        # Ответ
        message += result['answer']
        message += "\n\n"
        
        # ОБЯЗАТЕЛЬНО: Источники
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += f"📚 ИСТОЧНИКИ ({result['chunks_used']} документов):\n\n"
        
        if result.get('sources'):
            for i, source in enumerate(result['sources'], 1):
                similarity = source.get('similarity', 0)
                message += f"{i}. Similarity: {similarity:.3f}\n"
                # Показываем первые 150 символов источника
                source_text = source['text'][:150]
                if len(source['text']) > 150:
                    source_text += "..."
                message += f"   \"{source_text}\"\n\n"
        else:
            message += "⚠️ Источники не найдены\n\n"
        
        # Метаинформация
        message += "━━━━━━━━━━━━━━━━━━━━\n"
        message += f"⏱️ Время: {result.get('time', 0):.2f}с | "
        message += f"📊 История: {len(rag_histories[user_id])}/{MAX_RAG_HISTORY} сообщений\n"
        message += f"🔧 Модель: {result.get('model', 'llama3.2:3b')}"
        
        # Удаляем статусное сообщение
        await status_message.delete()
        
        # Отправляем ответ
        await send_long_message(update, message)
        
        logger.info(f"RAG answer sent to user {user_id}, history size: {len(rag_histories[user_id])}")
        
    except Exception as e:
        logger.error(f"Error in with_rag_command: {e}", exc_info=True)
        await status_message.edit_text(f"❌ Ошибка при обработке запроса: {str(e)}")


async def clear_rag_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /clear_rag - очистить историю RAG диалога
    """
    user_id = update.effective_user.id
    
    if user_id in rag_histories:
        history_size = len(rag_histories[user_id])
        rag_histories[user_id] = []
        await update.message.reply_text(
            f"✅ История RAG диалога очищена ({history_size} сообщений удалено)"
        )
        logger.info(f"RAG history cleared for user {user_id}")
    else:
        await update.message.reply_text("ℹ️ История RAG диалога пуста")


async def rag_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /rag_history - показать историю RAG диалога
    """
    user_id = update.effective_user.id
    
    if user_id not in rag_histories or not rag_histories[user_id]:
        await update.message.reply_text("ℹ️ История RAG диалога пуста")
        return
    
    history = rag_histories[user_id]
    
    message = f"📚 ИСТОРИЯ RAG ДИАЛОГА ({len(history)} сообщений)\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    for i, msg in enumerate(history, 1):
        role_icon = "👤" if msg['role'] == 'user' else "🤖"
        role_name = "Вы" if msg['role'] == 'user' else "RAG"
        
        # Обрезаем длинные сообщения
        content = msg['content'][:200]
        if len(msg['content']) > 200:
            content += "..."
        
        message += f"{i}. {role_icon} {role_name}:\n{content}\n\n"
    
    message += f"━━━━━━━━━━━━━━━━━━━━\n"
    message += f"Всего: {len(history)}/{MAX_RAG_HISTORY} сообщений"
    
    await send_long_message(update, message)
