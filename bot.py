#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот с Claude AI + MCP серверы - точка входа
Версия 9.1 - добавлена команда /with_rag
"""

import logging
from telegram.ext import Application, CommandHandler, MessageHandler, filters

from config import *
from mcp_clients import init_mcp_clients, shutdown_mcp_clients
from handlers.with_rag import with_rag_command, clear_rag_history_command, rag_history_command
from handlers.github_search import search_repo_command, get_file_command
from handlers.support import support_command, my_tickets_command

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


def main():
    """Запуск бота"""
    
    # Импортируем handlers.basic чтобы получить все обработчики
    from handlers import basic
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков команд из basic
    application.add_handler(CommandHandler("start", basic.start))
    application.add_handler(CommandHandler("clear", basic.clear_history))
    application.add_handler(CommandHandler("stats", basic.show_stats))
    application.add_handler(CommandHandler("debug", basic.debug_history))
    application.add_handler(CommandHandler("support", support_command))
    application.add_handler(CommandHandler("my_tickets", my_tickets_command))
    
    # Регистрация дополнительных команд если они есть
    if hasattr(basic, 'weather_subscribe'):
        application.add_handler(CommandHandler("weather_subscribe", basic.weather_subscribe))
    if hasattr(basic, 'weather_unsubscribe'):
        application.add_handler(CommandHandler("weather_unsubscribe", basic.weather_unsubscribe))
    if hasattr(basic, 'weather_list'):
        application.add_handler(CommandHandler("weather_list", basic.weather_list))
    if hasattr(basic, 'morning_digest'):
        application.add_handler(CommandHandler("morning_digest", basic.morning_digest))
    if hasattr(basic, 'mobile_devices'):
        application.add_handler(CommandHandler("mobile_devices", basic.mobile_devices))
    if hasattr(basic, 'start_emulator'):
        application.add_handler(CommandHandler("start_emulator", basic.start_emulator))
    
    # Регистрация обработчиков команд - RAG РЕЖИМ ⭐ НОВОЕ!
    application.add_handler(CommandHandler("with_rag", with_rag_command))
    application.add_handler(CommandHandler("clear_rag", clear_rag_history_command))
    application.add_handler(CommandHandler("rag_history", rag_history_command))
    application.add_handler(CommandHandler("search_repo", search_repo_command))
    application.add_handler(CommandHandler("get_file", get_file_command))
    
    # Регистрация обработчика текстовых сообщений
    if hasattr(basic, 'handle_message'):
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, basic.handle_message))
    
    # Инициализация MCP и планировщика при старте приложения
    application.post_init = init_mcp_clients
    application.post_shutdown = shutdown_mcp_clients
    
    logger.info("🤖 Bot is running (v9.1 - RAG Mode)...")
    
    # Запуск бота
    application.run_polling()


if __name__ == '__main__':
    main()
