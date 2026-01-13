#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Конфигурация Telegram бота с Claude AI
"""

import os
from pathlib import Path

# =============================================================================
# API Токены
# =============================================================================

TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN и ANTHROPIC_API_KEY должны быть установлены")

# =============================================================================
# Пути к файлам
# =============================================================================

# Директория для хранения истории разговоров
CONVERSATIONS_DIR = Path("/root/telegram-bot/conversations")

# Файлы погоды
WEATHER_SUBS_FILE = Path("/root/telegram-bot/weather_subscriptions.json")
WEATHER_HISTORY_FILE = Path("/root/telegram-bot/weather_history.json")

# Файл результатов RAG сравнений
RAG_COMPARISON_FILE = Path("/root/telegram-bot/rag_comparisons.json")

# =============================================================================
# Настройки истории разговоров
# =============================================================================

MAX_HISTORY_LENGTH = 30  # Максимум сообщений в истории
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ
COMPRESSION_THRESHOLD = 10  # Порог для сжатия истории

# =============================================================================
# MCP Weather Server
# =============================================================================

MCP_WEATHER_SERVER_PATH = "/home/claude/mcp-weather-server/server.js"

# =============================================================================
# MCP News Server
# =============================================================================

MCP_NEWS_SERVER_PATH = "/home/claude/mcp-news-server/server.js"

# =============================================================================
# MCP Mobile Server (через SSH)
# =============================================================================

MCP_MOBILE_SSH_HOST = "localhost"
MCP_MOBILE_SSH_PORT = 2222
MCP_MOBILE_SSH_USER = "vkuzmin"
MCP_MOBILE_SSH_KEY = "/root/.ssh/server_to_mac"
MCP_MOBILE_NODE_PATH = "/Users/vkuzmin/.nvm/versions/node/v20.19.6/bin/node"
MCP_MOBILE_SERVER_PATH = "/Users/vkuzmin/mcp-servers/mobile-mcp/lib/index.js"
MCP_MOBILE_START_EMULATOR_SCRIPT = "/Users/vkuzmin/start-emulator.sh"

# =============================================================================
# MCP Ollama Server (через SSH) - для RAG
# =============================================================================

MCP_OLLAMA_SSH_HOST = "localhost"
MCP_OLLAMA_SSH_PORT = 2222
MCP_OLLAMA_SSH_USER = "vkuzmin"
MCP_OLLAMA_SSH_KEY = "/root/.ssh/server_to_mac"
MCP_OLLAMA_NODE_PATH = "/Users/vkuzmin/.nvm/versions/node/v20.19.6/bin/node"
MCP_OLLAMA_SERVER_PATH = "/Users/vkuzmin/mcp-servers/ollama-mcp/server.js"
MCP_OLLAMA_ENV = {
    "VECTOR_STORE_DIR": "/Users/vkuzmin/vector_stores"
}

# =============================================================================
# Системный промпт для сжатия истории
# =============================================================================

COMPRESSION_SYSTEM_PROMPT = """You are a helpful assistant that creates concise summaries of conversation history.
Your task is to create a brief summary of the conversation provided. The summary should:
1. Capture the key topics discussed
2. Preserve important facts, decisions, or conclusions
3. Be concise but informative (2-4 sentences)
4. Be written in the same language as the conversation

Respond with ONLY a valid JSON object in this format:
{"summary": "your summary text here"}

Do not include any markdown formatting, code blocks, or additional text."""

# =============================================================================
# Claude API настройки
# =============================================================================

CLAUDE_MODEL = "claude-sonnet-4-20250514"
CLAUDE_MAX_TOKENS = 4096

# =============================================================================
# RAG настройки
# =============================================================================

RAG_VECTOR_STORE_NAME = "bot_knowledge"
RAG_TOP_K_INITIAL = 10  # Количество чанков для первичного поиска (до reranking)
RAG_LLM_MODEL = "llama3.2:3b"  # Модель для генерации ответов

# Режимы reranking:
# 'light' - топ-5 документов после reranking
# 'strict' - топ-2 документа после reranking

# =============================================================================
# MCP GitHub Server - для поиска по репозиториям
# =============================================================================

MCP_GITHUB_SERVER_PATH = "/home/claude/mcp-github-server/server.js"
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_REPO_OWNER = "KuzminVik"
GITHUB_REPO_NAME = "telegram-claude-bot"
