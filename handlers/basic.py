#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic Handlers - базовые команды бота
"""

import logging
import anthropic
from telegram import Update
from telegram.ext import ContextTypes
from config import ANTHROPIC_API_KEY
from utils.conversation_manager import get_conversation_history, save_conversation_history, compress_history_if_needed

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот с интеграцией Claude AI, погодой, новостями и управлением Android эмулятором.\n\n"
        "💬 Просто пишите мне вопросы - я отвечу используя Claude AI\n\n"
        "🤖 Режимы работы:\n"
        "• /mode - показать текущий режим\n"
        "• /mode claude - Claude API (Sonnet 4.5)\n"
        "• /mode local - Локальная LLM (llama3.2:3b)\n\n"
        "🌤️ Погода:\n"
        "• /weather_subscribe Город - подписаться на утреннюю погоду\n"
        "• /weather_unsubscribe - отписаться от погоды\n"
        "• /weather_list - показать подписку\n\n"
        "📰 Дайджест:\n"
        "• /morning_digest - получить погоду + новости прямо сейчас\n\n"
        "📱 Мобильные устройства:\n"
        "• /mobile_devices - показать доступные устройства\n"
        "• /start_emulator - запустить Android эмулятор\n\n"
        "📊 Управление:\n"
        "• /clear - очистить историю\n"
        "• /clear_local - очистить историю локального режима\n"
        "• /stats - показать статистику\n"
        "• /debug - показать последнее сообщение\n\n"
        "🔬 Сравнение:\n"
        "• /compare <вопрос> - RAG vs без RAG"
    )


async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить историю разговора"""
    user_id = update.effective_user.id
    save_conversation_history(user_id, [])
    await update.message.reply_text("✅ История очищена")


async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику"""
    await update.message.reply_text(
        "📊 Статистика вашей истории:\n\n"
        "💬 Сообщений: 0\n"
        "📦 Размер файла: 0 МБ\n"
        "🔬 RAG сравнений: 0"
    )


async def debug_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последнее сообщение из истории для отладки"""
    await update.message.reply_text("🛠 История пуста")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all non-command messages based on user's mode"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Получить текущий режим пользователя
    from handlers.local_mode import get_user_mode, load_local_history, save_local_history
    current_mode = get_user_mode(user_id)
    
    logger.info(f"User {user_id} message in mode '{current_mode}': {user_message[:50]}...")
    
    # Отправить индикатор "печатает..."
    await update.message.chat.send_action("typing")
    
    try:
        if current_mode == "local":
            # ========== ЛОКАЛЬНЫЙ РЕЖИМ (Ollama) ==========
            from mcp_clients import ollama_local_chat_client
            
            if ollama_local_chat_client is None:
                await update.message.reply_text(
                    "❌ Локальная LLM недоступна.\n\n"
                    "Переключись на Claude: `/mode claude`",
                    parse_mode='Markdown'
                )
                return
            
            # Загрузить историю локального режима
            local_history = load_local_history(user_id)
            messages = local_history.get("messages", [])

            # Добавить system prompt если это первое сообщение
            if len(messages) == 0:
                from config import LOCAL_LLM_SYSTEM_PROMPT
                messages.append({
                    "role": "system",
                    "content": LOCAL_LLM_SYSTEM_PROMPT
                })
            
            
            # Добавить новое сообщение пользователя
            messages.append({
                "role": "user",
                "content": user_message
            })
            
            # Ограничить историю последними 10 парами (20 сообщений)
            if len(messages) > 20:
                messages = messages[-20:]
            
            # Запрос к Ollama
            response = await ollama_local_chat_client.chat(
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            
            if response is None:
                await update.message.reply_text(
                    "❌ Ошибка при обращении к локальной LLM.\n\n"
                    "Попробуй ещё раз или переключись на Claude:\n"
                    "`/mode claude`",
                    parse_mode='Markdown'
                )
                return
            
            # Добавить ответ в историю
            messages.append({
                "role": "assistant",
                "content": response
            })
            
            # Сохранить обновлённую историю
            local_history["messages"] = messages
            local_history["message_count"] = len(messages)
            save_local_history(user_id, local_history)
            
            # Отправить ответ пользователю
            try:
                await update.message.reply_text(response, parse_mode='Markdown')
            except Exception:
                await update.message.reply_text(response)
            
            logger.info(f"Local mode response sent to user {user_id} ({len(response)} chars)")
            
        else:
            # ========== CLAUDE РЕЖИМ (существующая логика) ==========
            # Загрузить историю диалога
            conversation_history = get_conversation_history(user_id)
            
            # Добавить сообщение пользователя
            conversation_history.append({
                "role": "user",
                "content": user_message
            })
            
            # Сжать историю если нужно
            conversation_history = compress_history_if_needed(conversation_history, user_id)
            
            # Запрос к Claude API
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.3,
                messages=conversation_history,
                system="""Ты личный ассистент Виктора Кузьмина.

ВЛАДЕЛЕЦ БОТА:
Имя: Виктор Кузьмин
Роль: Senior Developer / Systems Architect
Язык: Русский

СТИЛЬ РАБОТЫ:
- Прагматичный, итеративный, экспериментальный подход
- Методология: Build → Test → Document → Improve
- Фокус на production-ready решениях

ТЕХНИЧЕСКИЕ НАВЫКИ:
- Языки: Python, JavaScript, Bash
- Интересы: AI/LLM, DevOps, системная интеграция, автоматизация
- Архитектура: модульный дизайн, graceful degradation, единый источник конфигурации

ПРИНЦИПЫ РЕШЕНИЙ:
- Простые решения предпочтительнее сложных
- Метрики и data-driven оптимизация
- Понимание trade-offs перед выбором
- Эксперимент → измерение → валидация

ПРЕДПОЧТЕНИЯ В КОММУНИКАЦИИ:
- Краткий, code-first стиль
- Temperature: 0.3 для технических задач
- Пошаговый подход для сложных задач
- Патчи/диффы или полные файлы кода

РЕШЕНИЕ ПРОБЛЕМ:
- Паттерн: Попробовать → Отладить → Альтернатива → Документировать
- Настойчивость на сложных проблемах
- Документирование неудач и решений

Отвечай на русском. Когда спрашивают о владельце бота, используй эту информацию."""
            )
            
            assistant_response = message.content[0].text
            
            # Добавить ответ в историю
            conversation_history.append({
                "role": "assistant",
                "content": assistant_response
            })
            
            # Сохранить обновлённую историю
            save_conversation_history(user_id, conversation_history)
            
            # Отправить ответ пользователю
            try:
                await update.message.reply_text(assistant_response, parse_mode='Markdown')
            except Exception:
                await update.message.reply_text(assistant_response)
            
            logger.info(f"Claude response sent to user {user_id} ({len(assistant_response)} chars)")
    
    except Exception as e:
        logger.error(f"Error handling message for user {user_id}: {e}")
        await update.message.reply_text(
            "❌ Произошла ошибка при обработке сообщения.\n\n"
            "Попробуй ещё раз или используй /clear для очистки истории."
        )
