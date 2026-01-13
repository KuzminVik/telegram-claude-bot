#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Search Handler - поиск по репозиторию
"""

import logging
from telegram import Update
from telegram.ext import ContextTypes

from mcp_clients import get_github_client
from utils.github_rag_functions import search_in_repository, get_file_content
from config import GITHUB_REPO_OWNER, GITHUB_REPO_NAME

logger = logging.getLogger(__name__)


async def search_repo_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /search_repo <запрос> - поиск по коду репозитория
    """
    if not context.args:
        await update.message.reply_text(
            "Использование: /search_repo <поисковый запрос>\n"
            f"Пример: /search_repo def handle_message\n\n"
            f"Поиск выполняется в репозитории: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
        )
        return
    
    query = " ".join(context.args)
    await update.message.reply_text(f"🔍 Ищу '{query}' в репозитории...")
    
    try:
        result = await search_in_repository(GITHUB_REPO_OWNER, GITHUB_REPO_NAME, query)
        
        if "error" in result:
            await update.message.reply_text(f"❌ Ошибка: {result['error']}")
            return
        
        total = result.get("total_count", 0)
        results = result.get("results", [])
        
	# Проверяем что результаты вообще вернулись
        if "error" in result:
            await update.message.reply_text(f"❌ Ошибка: {result['error']}")
            return
            
        if total == 0:
            await update.message.reply_text(
                f"🔍 Ничего не найдено по запросу '{query}'\n\n"
                f"Попробуйте:\n"
                f"• Более короткий запрос (1-2 слова)\n"
                f"• Конкретные имена функций или переменных\n"
                f"Например: /search_repo handler"
            )
            return
        
	# Формируем ответ
        response = f"📊 Найдено совпадений: {total}\n\n"
        
        for i, item in enumerate(results[:5], 1):
            response += f"{i}. **{item['path']}**\n"
            
            # Показываем совпадения
            for match in item.get('matches', [])[:2]:
                response += f"   Строка {match['line_number']}: `{match['text']}`\n"
            
            response += f"   [Открыть файл]({item['html_url']})\n\n"
        
        if total > 5:
            response += f"... и ещё {total - 5} файлов"
        
        await update.message.reply_text(response, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error in search_repo_command: {e}")
        await update.message.reply_text(f"❌ Ошибка при поиске: {str(e)}")


async def get_file_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Команда /get_file <путь> - получить содержимое файла
    """
    if not context.args:
        await update.message.reply_text(
            "Использование: /get_file <путь к файлу>\n"
            f"Пример: /get_file bot.py\n\n"
            f"Репозиторий: {GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
        )
        return
    
    file_path = " ".join(context.args)
    await update.message.reply_text(f"📄 Получаю файл '{file_path}'...")
    
    try:
        result = await get_file_content(GITHUB_REPO_OWNER, GITHUB_REPO_NAME, file_path)
        
        if "error" in result:
            await update.message.reply_text(f"❌ Ошибка: {result['error']}")
            return
        
        content = result.get("content", "")
        
        # Отправляем содержимое (ограничиваем длину)
        if len(content) > 4000:
            await update.message.reply_text(
                f"📄 **{file_path}**\n\n"
                f"Файл слишком большой ({len(content)} символов).\n"
                f"Первые 4000 символов:\n\n"
                f"```\n{content[:4000]}\n```",
                parse_mode='Markdown'
            )
        else:
            await update.message.reply_text(
                f"📄 **{file_path}**\n\n"
                f"```\n{content}\n```",
                parse_mode='Markdown'
            )
        
    except Exception as e:
        logger.error(f"Error in get_file_command: {e}")
        await update.message.reply_text(f"❌ Ошибка при получении файла: {str(e)}")
