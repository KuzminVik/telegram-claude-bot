#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Вспомогательные функции для бота
"""

from telegram import Update


async def send_long_message(update: Update, message: str, max_length: int = 4096):
    """
    Отправить длинное сообщение, разбив на части если необходимо
    """
    if len(message) <= max_length:
        await update.message.reply_text(message)
    else:
        # Разбиваем на части
        parts = []
        while message:
            if len(message) <= max_length:
                parts.append(message)
                break
            
            # Ищем перенос строки ближе к концу
            split_pos = message.rfind('\n', 0, max_length)
            if split_pos == -1:
                split_pos = max_length
            
            parts.append(message[:split_pos])
            message = message[split_pos:].lstrip()
        
        # Отправляем части
        for part in parts:
            await update.message.reply_text(part)
