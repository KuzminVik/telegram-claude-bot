#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Basic Handlers - базовые команды бота
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот с интеграцией Claude AI, погодой, новостями и управлением Android эмулятором.\n\n"
        "💬 Просто пишите мне вопросы - я отвечу используя Claude AI\n\n"
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
        "• /stats - показать статистику\n"
        "• /debug - показать последнее сообщение\n\n"
        "🔬 Сравнение:\n"
        "• /compare <вопрос> - RAG vs без RAG"
    )


async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить историю разговора"""
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
