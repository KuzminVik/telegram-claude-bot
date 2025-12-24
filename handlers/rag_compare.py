#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG Compare Handler - сравнение Light vs Strict Reranking
"""

import asyncio
import logging
from telegram import Update
from telegram.ext import ContextTypes

from utils.rag_functions import get_rag_answer, save_comparison
from utils.helpers import send_long_message

logger = logging.getLogger(__name__)


async def compare_rag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Сравнить ответы с легким и жестким reranking"""
    user_id = update.effective_user.id
    
    if not context.args:
        await update.message.reply_text(
            "❌ Укажите вопрос для сравнения!\n\n"
            "Использование: /compare <вопрос>\n\n"
            "Пример: /compare Какие команды есть у бота?\n\n"
            "Сравниваются два режима фильтрации:\n"
            "🟢 Легкий (top-5 документов)\n"
            "🔴 Жесткий (top-2 документа)"
        )
        return
    
    query = ' '.join(context.args)
    
    await update.message.reply_text(
        f"⏳ Сравниваю режимы фильтрации для:\n\"{query}\"\n\n"
        "🟢 Легкий фильтр (top-5)\n"
        "🔴 Жесткий фильтр (top-2)\n\n"
        "Это займёт ~30-40 секунд..."
    )
    
    logger.info(f"User {user_id} requested reranker comparison for: {query}")
    
    # Получаем оба ответа параллельно
    light_task = asyncio.create_task(get_rag_answer(query, 'light'))
    strict_task = asyncio.create_task(get_rag_answer(query, 'strict'))
    
    light_result, strict_result = await asyncio.gather(light_task, strict_task)
    
    # Формируем сообщение
    message = "🔬 СРАВНЕНИЕ РЕЖИМОВ RERANKING\n\n"
    message += f"❓ Вопрос: {query}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Легкий фильтр
    message += "🟢 ЛЕГКИЙ ФИЛЬТР (top-5 документов):\n\n"
    message += f"{light_result['answer']}\n\n"
    
    if light_result.get('sources'):
        message += f"📚 Источники ({light_result['chunks_used']} документов):\n"
        for i, source in enumerate(light_result['sources'][:3], 1):
            similarity = source.get('similarity')
            message += f"{i}. Similarity: {similarity:.3f}\n"
            message += f"   \"{source['text'][:80]}...\"\n\n"
    
    message += f"⏱️ Время: {light_result['time']}с | "
    message += f"Модель: {light_result.get('model', 'llama3.2:3b')}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Жесткий фильтр
    message += "🔴 ЖЕСТКИЙ ФИЛЬТР (top-2 документа):\n\n"
    message += f"{strict_result['answer']}\n\n"
    
    if strict_result.get('sources'):
        message += f"📚 Источники ({strict_result['chunks_used']} документов):\n"
        for i, source in enumerate(strict_result['sources'][:3], 1):
            similarity = source.get('similarity')
            message += f"{i}. Similarity: {similarity:.3f}\n"
            message += f"   \"{source['text'][:80]}...\"\n\n"
    
    message += f"⏱️ Время: {strict_result['time']}с | "
    message += f"Модель: {strict_result.get('model', 'llama3.2:3b')}\n\n"
    message += "━━━━━━━━━━━━━━━━━━━━\n\n"
    
    # Анализ различий
    message += "📊 АНАЛИЗ РАЗЛИЧИЙ:\n\n"
    
    # Разница в количестве документов
    doc_diff = light_result['chunks_used'] - strict_result['chunks_used']
    message += f"• Документов: {light_result['chunks_used']} vs {strict_result['chunks_used']} "
    message += f"(разница: {doc_diff})\n"
    
    # Средние similarity scores
    if light_result.get('sources'):
        light_avg = sum(s.get('similarity', 0) for s in light_result['sources']) / len(light_result['sources'])
        message += f"• Средний similarity (легкий): {light_avg:.3f}\n"
    
    if strict_result.get('sources'):
        strict_avg = sum(s.get('similarity', 0) for s in strict_result['sources']) / len(strict_result['sources'])
        message += f"• Средний similarity (жесткий): {strict_avg:.3f}\n"
    
    # Длина ответов
    light_len = len(light_result['answer'])
    strict_len = len(strict_result['answer'])
    message += f"• Длина ответа: {light_len} vs {strict_len} символов\n"
    
    # Сохраняем результат
    comparison_data = {
        "user_id": user_id,
        "query": query,
        "light": light_result,
        "strict": strict_result
    }
    save_comparison(comparison_data)
    
    await send_long_message(update, message)
    logger.info(f"Reranker comparison completed for user {user_id}")
