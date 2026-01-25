#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub RAG функции - поиск по репозиториям GitHub через Contents API
"""

import logging
import base64
from typing import List, Dict

logger = logging.getLogger(__name__)

# Глобальная ссылка на GitHub client
_github_client = None


def set_github_client(client):
    """Установить глобальный GitHub client"""
    global _github_client
    _github_client = client


async def search_in_repository(owner: str, repo: str, query: str) -> Dict:
    """
    Простой поиск по известным файлам репозитория
    """
    if not _github_client:
        return {"error": "GitHub client not initialized"}
    
    try:
        # Список основных файлов для поиска
        files_to_search = [
            "bot.py",
            "config.py",
            "handlers/basic.py",
            "handlers/with_rag.py",
            "handlers/github_search.py",
            "mcp_clients/__init__.py",
            "mcp_clients/weather_client.py",
            "mcp_clients/news_client.py",
            "mcp_clients/mobile_client.py",
            "mcp_clients/ollama_client.py",
            "utils/rag_functions.py",
            "README.md"
        ]
        
        results = []
        query_lower = query.lower()
        
        for file_path in files_to_search:
            try:
                content_result = await _github_client.get_file_contents(owner, repo, file_path)
                
                if not content_result:
                    continue
                
                # MCP GitHub возвращает JSON с метаданными
                # Извлекаем content и encoding
                file_content_encoded = content_result.get("content", "")
                encoding = content_result.get("encoding", "")
                
                if not file_content_encoded:
                    continue
                
                # Декодируем base64
                try:
                    if encoding == "base64":
                        # Убираем переносы строк и пробелы из base64
                        file_content_clean = file_content_encoded.replace('\n', '').replace('\r', '').replace(' ', '')
                        
                        # base64 должен содержать только ASCII символы
                        # Если есть unicode - значит это уже не base64, а декодированный контент
                        # Попробуем как bytes (для корректного base64)
                        try:
                            # Пытаемся декодировать как чистый base64
                            content = base64.b64decode(file_content_clean).decode('utf-8')
                        except:
                            # Если не получилось - возможно контент уже был декодирован
                            # или содержит unicode символы, пробуем latin-1
                            try:
                                content = base64.b64decode(file_content_clean.encode('latin-1')).decode('utf-8')
                            except:
                                # В крайнем случае - считаем что это уже декодированный текст
                                content = file_content_encoded
                    else:
                        content = file_content_encoded
                        
                except Exception as e:
                    logger.warning(f"Failed to decode {file_path}: {e}")
                    continue
                
                # Проверяем есть ли искомый текст
                if query_lower in content.lower():
                    # Находим строки с совпадениями
                    lines = content.split('\n')
                    matching_lines = []
                    for i, line in enumerate(lines, 1):
                        if query_lower in line.lower():
                            matching_lines.append({
                                "line_number": i,
                                "text": line.strip()[:100]
                            })
                            if len(matching_lines) >= 3:
                                break
                    
                    results.append({
                        "path": file_path,
                        "matches": matching_lines,
                        "html_url": f"https://github.com/{owner}/{repo}/blob/main/{file_path}"
                    })
                
            except Exception as e:
                logger.warning(f"Error processing {file_path}: {e}")
                continue
        
        return {
            "total_count": len(results),
            "results": results
        }
        
    except Exception as e:
        logger.error(f"Error searching repository: {e}")
        return {"error": str(e)}


async def get_file_content(owner: str, repo: str, path: str) -> Dict:
    """Получить содержимое конкретного файла"""
    if not _github_client:
        return {"error": "GitHub client not initialized"}
    
    try:
        result = await _github_client.get_file_contents(owner, repo, path)
        
        if result and "content" in result:
            content = result["content"]
            encoding = result.get("encoding", "")
            
            # Декодируем base64
            if encoding == "base64":
                try:
                    # Убираем переносы строк и пробелы
                    content_clean = content.replace('\n', '').replace('\r', '').replace(' ', '')
                    
                    # Пытаемся декодировать разными способами
                    try:
                        content = base64.b64decode(content_clean).decode('utf-8')
                    except:
                        try:
                            content = base64.b64decode(content_clean.encode('latin-1')).decode('utf-8')
                        except:
                            # Оставляем как есть
                            pass
                    
                    result["content"] = content
                except Exception as e:
                    logger.error(f"Error decoding base64: {e}")
        
        return result
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return {"error": str(e)}
