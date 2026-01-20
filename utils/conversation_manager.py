#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conversation Manager - управление историей диалогов
"""

import os
import json
import logging
from datetime import datetime
from config import CONVERSATIONS_DIR

logger = logging.getLogger(__name__)

MAX_HISTORY_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_MESSAGES = 30


def get_conversation_file_path(user_id):
    """Получить путь к файлу истории диалога"""
    return os.path.join(CONVERSATIONS_DIR, f"user_{user_id}.json")


def get_conversation_history(user_id):
    """
    Загрузить историю диалога пользователя
    Возвращает список сообщений в формате Claude API
    """
    file_path = get_conversation_file_path(user_id)
    
    if not os.path.exists(file_path):
        logger.info(f"Creating new conversation for user {user_id}")
        return []
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        messages = data.get("messages", [])
        
        # Конвертировать старый формат в новый если нужно
        converted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                # Если это старый формат с обёрткой JSON
                if "role" in msg and "content" in msg:
                    content = msg["content"]
                    # Если content это JSON строка, попробуем распарсить
                    if isinstance(content, str) and content.startswith("{"):
                        try:
                            parsed = json.loads(content)
                            if "ai_message" in parsed:
                                # Старый формат - извлечь ai_message
                                converted_messages.append({
                                    "role": msg["role"],
                                    "content": parsed["ai_message"]
                                })
                            else:
                                converted_messages.append(msg)
                        except:
                            converted_messages.append(msg)
                    else:
                        converted_messages.append(msg)
                else:
                    converted_messages.append(msg)
        
        logger.info(f"Loaded {len(converted_messages)} messages for user {user_id}")
        return converted_messages
        
    except Exception as e:
        logger.error(f"Error loading conversation for user {user_id}: {e}")
        return []


def save_conversation_history(user_id, messages):
    """Сохранить историю диалога"""
    file_path = get_conversation_file_path(user_id)
    
    try:
        data = {
            "user_id": user_id,
            "last_updated": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": messages
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved {len(messages)} messages for user {user_id}")
        
    except Exception as e:
        logger.error(f"Error saving conversation for user {user_id}: {e}")


def compress_history_if_needed(messages, user_id):
    """
    Сжать историю если она слишком большая
    Возвращает обновлённый список сообщений
    """
    # Проверка по количеству сообщений
    if len(messages) > MAX_MESSAGES:
        logger.info(f"Compressing history for user {user_id} ({len(messages)} messages)")
        
        # Оставить последние MAX_MESSAGES сообщений
        compressed = messages[-MAX_MESSAGES:]
        
        # Добавить краткую справку о сжатии в начало
        summary = {
            "role": "user",
            "content": f"📦 История сжата. Сохранено последних {MAX_MESSAGES} сообщений из {len(messages)}."
        }
        
        return [summary] + compressed
    
    return messages


def clear_conversation_history(user_id):
    """Очистить историю диалога"""
    file_path = get_conversation_file_path(user_id)
    
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logger.info(f"Cleared conversation for user {user_id}")
            return True
    except Exception as e:
        logger.error(f"Error clearing conversation for user {user_id}: {e}")
        return False
    
    return False


def get_conversation_stats(user_id):
    """Получить статистику диалога"""
    file_path = get_conversation_file_path(user_id)
    
    if not os.path.exists(file_path):
        return {
            "messages": 0,
            "size_mb": 0,
            "last_updated": None
        }
    
    try:
        # Размер файла
        size_bytes = os.path.getsize(file_path)
        size_mb = size_bytes / (1024 * 1024)
        
        # Загрузить данные
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        return {
            "messages": data.get("message_count", 0),
            "size_mb": round(size_mb, 2),
            "last_updated": data.get("last_updated")
        }
        
    except Exception as e:
        logger.error(f"Error getting stats for user {user_id}: {e}")
        return {
            "messages": 0,
            "size_mb": 0,
            "last_updated": None
        }
