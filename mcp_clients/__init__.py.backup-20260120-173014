"""
MCP клиенты для различных сервисов
"""

import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from .weather_client import MCPWeatherClient
from .news_client import MCPNewsClient
from .mobile_client import MCPMobileClient
from .ollama_client import MCPOllamaClient
from .github_client import MCPGitHubClient

logger = logging.getLogger(__name__)

# Глобальные клиенты
mcp_weather_client = None
mcp_news_client = None
mcp_mobile_client = None
mcp_ollama_client = None
mcp_github_client = None
scheduler = None
bot_instance = None


async def init_ollama_local_chat_client():
    global ollama_local_chat_client
    logger.info("Starting Ollama Local Chat Client...")
    ollama_local_chat_client = OllamaLocalChatClient()
    success = await ollama_local_chat_client.start()
    if success:
        logger.info("✓ Ollama Local Chat Client initialized")
    else:
        logger.warning("⚠ Ollama Local Chat Client failed to initialize")
    return success


async def init_mcp_clients(app):
    """
    Инициализация всех MCP клиентов при старте бота
    """
    global mcp_weather_client, mcp_news_client, mcp_mobile_client, mcp_ollama_client, mcp_github_client
    global scheduler, bot_instance
    
    from config import (
        MCP_WEATHER_SERVER_PATH,
        MCP_NEWS_SERVER_PATH,
        MCP_MOBILE_SSH_HOST,
        MCP_MOBILE_SSH_PORT,
        MCP_MOBILE_SSH_USER,
        MCP_MOBILE_SSH_KEY,
        MCP_MOBILE_NODE_PATH,
        MCP_MOBILE_SERVER_PATH,
        MCP_OLLAMA_SSH_HOST,
        MCP_OLLAMA_SSH_PORT,
        MCP_OLLAMA_SSH_USER,
        MCP_OLLAMA_SSH_KEY,
        MCP_OLLAMA_NODE_PATH,
        MCP_OLLAMA_SERVER_PATH,
        MCP_GITHUB_SERVER_PATH,
        GITHUB_TOKEN,
        GITHUB_REPO_OWNER,
        GITHUB_REPO_NAME
    )
    
    # Сохраняем экземпляр бота для использования в scheduled задачах
    bot_instance = app.bot
    
    # Запускаем MCP Weather Client
    logger.info("Starting MCP Weather Client...")
    mcp_weather_client = MCPWeatherClient(MCP_WEATHER_SERVER_PATH)
    if await mcp_weather_client.start():
        logger.info("✓ MCP Weather Client initialized")
    else:
        logger.error("✗ Failed to start MCP Weather Client")
    
    # Запускаем MCP News Client
    logger.info("Starting MCP News Client...")
    mcp_news_client = MCPNewsClient(MCP_NEWS_SERVER_PATH)
    if await mcp_news_client.start():
        logger.info("✓ MCP News Client initialized")
    else:
        logger.error("✗ Failed to start MCP News Client")
    
    # Запускаем MCP Mobile Client
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
    
    # Запускаем MCP Ollama Client
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

        from utils.rag_functions import set_ollama_client
        set_ollama_client(mcp_ollama_client)
        from utils.github_rag_functions import set_github_client
        if mcp_github_client:
            set_github_client(mcp_github_client)
            logger.info("✓ GitHub RAG functions configured")
        logger.info("✓ RAG functions configured with Ollama client")
    else:
        logger.error("✗ Failed to start MCP Ollama Client")
    
    # Запускаем MCP GitHub Client
    logger.info("Starting MCP GitHub Client...")
    if GITHUB_TOKEN:
        mcp_github_client = MCPGitHubClient(
            server_path=MCP_GITHUB_SERVER_PATH,
            github_token=GITHUB_TOKEN
        )
        if await mcp_github_client.start():
            logger.info("✓ MCP GitHub Client initialized")
            from utils.github_rag_functions import set_github_client
            set_github_client(mcp_github_client)
            logger.info("✓ GitHub RAG functions configured")
        else:
            logger.error("✗ Failed to start MCP GitHub Client")
    else:
        logger.warning("⚠ GITHUB_TOKEN not set, GitHub MCP disabled")
    
    # Запускаем Task MCP Client
    await init_task_client()
    await init_ollama_local_chat_client()

    # Инициализация планировщика
    scheduler = AsyncIOScheduler()
    
    # Импортируем функцию утренней рассылки
#    from handlers.basic import send_morning_weather
    
    # Добавляем задачу утренней рассылки (каждый день в 8:00)
 #   scheduler.add_job(
  #      send_morning_weather,
   #     CronTrigger(hour=8, minute=0, timezone='Europe/Moscow'),
    #    id='morning_weather',
     #   name='Morning Weather Broadcast',
  #      replace_existing=True
   # )
   # 
   # scheduler.start()
   # logger.info("✓ Scheduler started (morning broadcast at 08:00 Moscow time)")


async def shutdown_mcp_clients(app):
    """
    Остановка всех MCP клиентов при завершении работы бота
    """
    global mcp_weather_client, mcp_news_client, mcp_mobile_client, mcp_ollama_client, mcp_github_client, scheduler
    
    if mcp_weather_client:
        await mcp_weather_client.stop()
        logger.info("✓ MCP Weather Client stopped")
    
    if mcp_news_client:
        await mcp_news_client.stop()
        logger.info("✓ MCP News Client stopped")
    
    if mcp_mobile_client:
        await mcp_mobile_client.stop()
        logger.info("✓ MCP Mobile Client stopped")
    
    if mcp_ollama_client:
        await mcp_ollama_client.stop()
        logger.info("✓ MCP Ollama Client stopped")
    
    if mcp_github_client:
        await mcp_github_client.stop()
        logger.info("✓ MCP GitHub Client stopped")

    if mcp_task_client:
        await mcp_task_client.stop()
        logger.info("✓ Task MCP Client stopped")
    
#    if scheduler:
#        scheduler.shutdown()
#        logger.info("✓ Scheduler stopped")
    if ollama_local_chat_client:
        await ollama_local_chat_client.stop()
        logger.info("✓ Ollama Local Chat Client stopped")
#

def get_weather_client():
    """Получить экземпляр Weather клиента"""
    return mcp_weather_client


def get_news_client():
    """Получить экземпляр News клиента"""
    return mcp_news_client


def get_mobile_client():
    """Получить экземпляр Mobile клиента"""
    return mcp_mobile_client


def get_ollama_client():
    """Получить экземпляр Ollama клиента"""
    return mcp_ollama_client


def get_github_client():
    """Получить экземпляр GitHub клиента"""
    return mcp_github_client


def get_bot_instance():
    """Получить экземпляр бота для scheduled задач"""
    return bot_instance


__all__ = [
    'MCPWeatherClient',
    'MCPNewsClient',
    'MCPMobileClient',
    'MCPOllamaClient',
    'MCPGitHubClient',
    'init_mcp_clients',
    'shutdown_mcp_clients',
    'get_weather_client',
    'get_news_client',
    'get_mobile_client',
    'get_ollama_client',
    'get_github_client',
    'get_bot_instance'
]

# Task MCP Client
from mcp_clients.task_client import TaskMCPClient
from mcp_clients.ollama_chat_client import OllamaLocalChatClient

mcp_task_client = None
ollama_local_chat_client = None

async def init_task_client():
    global mcp_task_client
    logger.info("Starting Task MCP Client...")
    mcp_task_client = TaskMCPClient()
    success = await mcp_task_client.start()
    if success:
        logger.info("✓ Task MCP Client initialized")
    else:
        logger.error("✗ Task MCP Client failed to initialize")
        mcp_task_client = None
    return success
