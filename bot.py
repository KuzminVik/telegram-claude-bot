#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram бот с интеграцией Claude AI, погодой, новостями и RAG
Модульная архитектура
"""

import logging
from telegram import Update
from telegram.ext import Application, CommandHandler

# Импорты конфигурации
from config import (
    TELEGRAM_TOKEN,
    MCP_WEATHER_SERVER_PATH,
    MCP_NEWS_SERVER_PATH,
    MCP_MOBILE_SSH_HOST,
    MCP_MOBILE_SSH_PORT,
    MCP_MOBILE_SSH_USER,
    MCP_MOBILE_SSH_KEY,
    MCP_MOBILE_SERVER_PATH,
    MCP_OLLAMA_SSH_HOST,
    MCP_OLLAMA_SSH_PORT,
    MCP_OLLAMA_SSH_USER,
    MCP_OLLAMA_SSH_KEY,
    MCP_OLLAMA_NODE_PATH,
    MCP_OLLAMA_SERVER_PATH
)

# Импорты MCP клиентов
from mcp_clients import (
    MCPWeatherClient,
    MCPNewsClient,
    MCPMobileClient,
    MCPOllamaClient
)

# Импорты handlers
from handlers.rag_compare import compare_rag
from handlers.basic import start, clear_history, show_stats, debug_history

# Импорты utils
from utils.rag_functions import set_ollama_client

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Глобальные переменные для MCP клиентов
mcp_weather_client = None
mcp_news_client = None
mcp_mobile_client = None
mcp_ollama_client = None


async def post_init(app):
    """Инициализация после запуска приложения"""
    global mcp_weather_client, mcp_news_client, mcp_mobile_client, mcp_ollama_client
    
    logger.info("Initializing MCP clients...")
    
    # Weather Client
    logger.info("Starting MCP Weather Client...")
    mcp_weather_client = MCPWeatherClient(MCP_WEATHER_SERVER_PATH)
    if await mcp_weather_client.start():
        logger.info("✓ MCP Weather Client initialized")
    else:
        logger.error("✗ Failed to start MCP Weather Client")
    
    # News Client
    logger.info("Starting MCP News Client...")
    mcp_news_client = MCPNewsClient(MCP_NEWS_SERVER_PATH)
    if await mcp_news_client.start():
        logger.info("✓ MCP News Client initialized")
    else:
        logger.error("✗ Failed to start MCP News Client")
    
    # Mobile Client
    logger.info("Starting MCP Mobile Client...")
    mcp_mobile_client = MCPMobileClient(
        ssh_host=MCP_MOBILE_SSH_HOST,
        ssh_port=MCP_MOBILE_SSH_PORT,
        ssh_user=MCP_MOBILE_SSH_USER,
        ssh_key=MCP_MOBILE_SSH_KEY,
        server_path=MCP_MOBILE_SERVER_PATH
    )
    if await mcp_mobile_client.start():
        logger.info("✓ MCP Mobile Client initialized")
    else:
        logger.error("✗ Failed to start MCP Mobile Client")
    
    # Ollama Client (для RAG)
    logger.info("Starting MCP Ollama Client...")
    mcp_ollama_client = MCPOllamaClient(
        ssh_host=MCP_OLLAMA_SSH_HOST,
        ssh_port=MCP_OLLAMA_SSH_PORT,
        ssh_user=MCP_OLLAMA_SSH_USER,
        ssh_key=MCP_OLLAMA_SSH_KEY,
        node_path=MCP_OLLAMA_NODE_PATH,
        server_path=MCP_OLLAMA_SERVER_PATH
    )
    if await mcp_ollama_client.start():
        logger.info("✓ MCP Ollama Client initialized")
        # Устанавливаем глобальный клиент для RAG функций
        set_ollama_client(mcp_ollama_client)
    else:
        logger.error("✗ Failed to start MCP Ollama Client")
    
    logger.info("All MCP clients initialized")


async def post_shutdown(app):
    """Остановка при завершении приложения"""
    logger.info("Shutting down MCP clients...")
    
    if mcp_weather_client:
        await mcp_weather_client.stop()
    if mcp_news_client:
        await mcp_news_client.stop()
    if mcp_mobile_client:
        await mcp_mobile_client.stop()
    if mcp_ollama_client:
        await mcp_ollama_client.stop()
    
    logger.info("All MCP clients stopped")


def main():
    """Главная функция"""
    logger.info("Bot is starting...")
    
    # Создаём приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрируем handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("compare", compare_rag))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("debug", debug_history))
    
    # Устанавливаем callbacks
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    # Запускаем бота
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
