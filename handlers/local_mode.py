# /root/telegram-bot/handlers/local_mode.py

import logging
import json
import os
from datetime import datetime
from telegram import Update
from telegram.ext import ContextTypes
from config import CONVERSATIONS_DIR

logger = logging.getLogger(__name__)

# Файл для хранения режимов пользователей
MODES_FILE = os.path.join(CONVERSATIONS_DIR, "user_modes.json")

def load_user_modes():
    """Загрузить режимы пользователей"""
    if os.path.exists(MODES_FILE):
        try:
            with open(MODES_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load user modes: {e}")
    return {}

def save_user_modes(modes):
    """Сохранить режимы пользователей"""
    try:
        with open(MODES_FILE, 'w', encoding='utf-8') as f:
            json.dump(modes, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save user modes: {e}")

def get_user_mode(user_id):
    """Получить текущий режим пользователя"""
    modes = load_user_modes()
    return modes.get(str(user_id), "claude")  # По умолчанию Claude

def set_user_mode(user_id, mode):
    """Установить режим пользователя"""
    modes = load_user_modes()
    modes[str(user_id)] = mode
    save_user_modes(modes)

def get_local_history_path(user_id):
    """Путь к файлу истории для локального режима"""
    return os.path.join(CONVERSATIONS_DIR, f"local_{user_id}.json")

def load_local_history(user_id):
    """Загрузить историю локального режима"""
    history_path = get_local_history_path(user_id)
    if os.path.exists(history_path):
        try:
            with open(history_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load local history: {e}")
    return {
        "user_id": user_id,
        "mode": "local",
        "last_updated": datetime.now().isoformat(),
        "message_count": 0,
        "messages": []
    }

def save_local_history(user_id, history):
    """Сохранить историю локального режима"""
    history_path = get_local_history_path(user_id)
    history["last_updated"] = datetime.now().isoformat()
    try:
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Failed to save local history: {e}")

async def mode_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /mode [claude|local]
    Переключение между Claude API и локальной Ollama
    """
    user_id = update.effective_user.id
    args = context.args
    
    if not args:
        # Показать текущий режим
        current_mode = get_user_mode(user_id)
        mode_emoji = "🤖" if current_mode == "local" else "☁️"
        mode_name = "Локальная LLM (llama3.2:1b)" if current_mode == "local" else "Claude API"
        
        await update.message.reply_text(
            f"{mode_emoji} **Текущий режим:** {mode_name}\n\n"
            f"Доступные режимы:\n"
            f"• `/mode claude` - Claude API (Sonnet 4.5)\n"
            f"• `/mode local` - Локальная LLM (llama3.2:1b)\n\n"
            f"⚠️ У каждого режима отдельная история диалогов",
            parse_mode='Markdown'
        )
        return
    
    new_mode = args[0].lower()
    
    if new_mode not in ["claude", "local"]:
        await update.message.reply_text(
            "❌ Неверный режим. Используй: `/mode claude` или `/mode local`",
            parse_mode='Markdown'
        )
        return
    
    # Проверка доступности Ollama для local режима
    if new_mode == "local":
        from mcp_clients import ollama_local_chat_client
        if ollama_local_chat_client is None:
            await update.message.reply_text(
                "❌ Локальная LLM недоступна. Ollama client не инициализирован.\n\n"
                "Используй `/mode claude` для работы с Claude API.",
                parse_mode='Markdown'
            )
            return
    
    # Установить новый режим
    old_mode = get_user_mode(user_id)
    set_user_mode(user_id, new_mode)
    
    mode_emoji = "🤖" if new_mode == "local" else "☁️"
    mode_name = "Локальная LLM (llama3.2:1b)" if new_mode == "local" else "Claude API (Sonnet 4.5)"
    
    # Информация о статистике истории
    if new_mode == "local":
        local_history = load_local_history(user_id)
        msg_count = local_history.get("message_count", 0)
        stats = f"📊 История: {msg_count} сообщений"
    else:
        # Для Claude используется обычная история
        from utils.conversation_manager import get_conversation_history
        claude_history = get_conversation_history(user_id)
        msg_count = len(claude_history)
        stats = f"📊 История: {msg_count} сообщений"
    
    await update.message.reply_text(
        f"{mode_emoji} **Режим изменён:** {mode_name}\n\n"
        f"{stats}\n\n"
        f"{'🤖 Локальная LLM работает на сервере 157.22.241.102' if new_mode == 'local' else '☁️ Используется Claude Sonnet 4.5'}\n"
        f"⚠️ Истории режимов изолированы друг от друга",
        parse_mode='Markdown'
    )
    
    logger.info(f"User {user_id} switched mode: {old_mode} -> {new_mode}")

async def clear_local_history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /clear_local
    Очистить историю локального режима
    """
    user_id = update.effective_user.id
    current_mode = get_user_mode(user_id)
    
    if current_mode != "local":
        await update.message.reply_text(
            "⚠️ Вы сейчас в режиме Claude.\n\n"
            "Чтобы очистить историю локального режима, сначала переключись:\n"
            "`/mode local`",
            parse_mode='Markdown'
        )
        return
    
    # Очистить историю
    history = load_local_history(user_id)
    old_count = history.get("message_count", 0)
    
    history = {
        "user_id": user_id,
        "mode": "local",
        "last_updated": datetime.now().isoformat(),
        "message_count": 0,
        "messages": []
    }
    save_local_history(user_id, history)
    
    await update.message.reply_text(
        f"🗑️ История локального режима очищена\n\n"
        f"Удалено сообщений: {old_count}"
    )
    
    logger.info(f"User {user_id} cleared local history ({old_count} messages)")
