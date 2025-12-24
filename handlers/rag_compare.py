#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Compare Handler - команда сравнения RAG vs No-RAG
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from utils.rag_functions import get_rag_answer, get_no_rag_answer, save_comparison
from utils.helpers import send_long_message

logger = logging.getLogger(__name__)


async def compare_rag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сравнить ответы с RAG и без RAG"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите вопрос для сравнения!\n\n"
            "Использование: /compare <вопрос>\n\n"
            "Пример: /compare Какие команды есть у бота?"
        )
        return
    
    query = ' '.join(context.args)
    
    await update.message.reply_text(
        f"⏳ Получаю ответы на вопрос:\n\"{query}\"\n\n"
        "Это займёт ~10-15 секунд..."
    )
    
    logger.info(f"User {user_id} requested comparison for: {query}")
    
    # Получаем оба ответа параллельно
    rag_task = asyncio.create_task(get_rag_answer(query))
    no_rag_task = asyncio.create_task(get_no_rag_answer(query))
    
    rag_result, no_rag_result = await asyncio.gather(rag_task, no_rag_task)
    
    # Формируем сообщение
    message = "🔬 СРАВНЕНИЕ RAG vs БЕЗ RAG\n\n"
    message += f"❓ Вопрос: {query}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # С RAG
    message += "🧠 С RAG (Retrieval-Augmented Generation):\n\n"
    message += f"{rag_result['answer']}\n\n"
    
    if rag_result.get('sources'):
        message += f"📚 Источники ({rag_result['chunks_used']} чанков):\n"
        for i, source in enumerate(rag_result['sources'][:2], 1):
            message += f"{i}. Релевантность: {source['similarity']}\n"
            message += f"   \"{source['text'][:100]}...\"\n\n"
    
    message += f"⏱️ Время: {rag_result['time']}с | "
    message += f"Модель: {rag_result.get('model', 'llama3.2:3b')}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Без RAG
    message += "🤖 БЕЗ RAG (чистый Claude):\n\n"
    message += f"{no_rag_result['answer']}\n\n"
    message += f"⏱️ Время: {no_rag_result['time']}с | "
    message += f"Модель: {no_rag_result.get('model', 'claude-sonnet-4')}\n"
    message += f"📊 Токены: {no_rag_result.get('input_tokens', 0)} вход / "
    message += f"{no_rag_result.get('output_tokens', 0)} выход\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Выводы
    message += "📊 МЕТРИКИ:\n"
    time_diff = abs(rag_result['time'] - no_rag_result['time'])
    faster = "RAG" if rag_result['time'] < no_rag_result['time'] else "Claude"
    message += f"• Скорость: {faster} быстрее на {time_diff:.1f}с\n"
    
    if rag_result.get('sources'):
        avg_similarity = sum(s['similarity'] for s in rag_result['sources']) / len(rag_result['sources'])
        message += f"• Релевантность источников: {avg_similarity:.2f}\n"
    
    # Сохраняем результат
    comparison_data = {
        "user_id": user_id,
        "query": query,
        "rag": rag_result,
        "no_rag": no_rag_result
    }
    save_comparison(comparison_data)
    
    await send_long_message(update, message)
    logger.info(f"Comparison completed for user {user_id}")
