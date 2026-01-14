#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub RAG функции - индексация и поиск по GitHub репозиториям
"""

import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# Глобальная ссылка на GitHub client
_github_client = None


def set_github_client(client):
    """Установить глобальный GitHub client"""
    global _github_client
    _github_client = client


async def index_repository(owner: str, repo: str, extensions: List[str] = None) -> Dict:
    """
    Индексировать репозиторий GitHub для RAG
    
    Args:
        owner: Владелец репозитория
        repo: Название репозитория
        extensions: Список расширений файлов для индексации (например, ['.py', '.js'])
    
    Returns:
        dict с результатами индексации
    """
    if not _github_client:
        return {"error": "GitHub client not initialized"}
    
    if extensions is None:
        extensions = ['.py', '.js', '.md', '.json', '.yml', '.yaml']
    
    try:
        # Получаем дерево файлов репозитория
        tree_result = await _github_client.call_tool(
            "get_file_tree",
            {
                "owner": owner,
                "repo": repo,
                "recursive": True
            }
        )
        
        if not tree_result:
            return {"error": "Failed to get repository tree"}
        
        # Фильтруем файлы по расширениям
        files_to_index = []
        for item in tree_result.get("tree", []):
            if item["type"] == "blob":  # Это файл
                path = item["path"]
                if any(path.endswith(ext) for ext in extensions):
                    files_to_index.append({
                        "path": path,
                        "sha": item["sha"]
                    })
        
        logger.info(f"Found {len(files_to_index)} files to index in {owner}/{repo}")
        
        # Собираем содержимое файлов
        indexed_files = []
        for file_info in files_to_index[:50]:  # Ограничим первыми 50 файлами
            try:
                content_result = await _github_client.get_file_contents(
                    owner, repo, file_info["path"]
                )
                
                if content_result and "content" in content_result:
                    indexed_files.append({
                        "path": file_info["path"],
                        "content": content_result["content"],
                        "size": content_result.get("size", 0)
                    })
            except Exception as e:
                logger.warning(f"Failed to get content for {file_info['path']}: {e}")
        
        return {
            "total_files": len(files_to_index),
            "indexed_files": len(indexed_files),
            "files": indexed_files
        }
        
    except Exception as e:
        logger.error(f"Error indexing repository: {e}")
        return {"error": str(e)}


async def search_in_repository(owner: str, repo: str, query: str) -> Dict:
    """
    Поиск по содержимому репозитория через GitHub Code Search API
    
    Args:
        owner: Владелец репозитория
        repo: Название репозитория
        query: Поисковый запрос
    
    Returns:
        dict с результатами поиска
    """
    if not _github_client:
        return {"error": "GitHub client not initialized"}
    
    try:
        result = await _github_client.search_code(owner, repo, query)
        
        if not result:
            return {"error": "Search failed"}
        
        # Форматируем результаты для удобного использования
        items = result.get("items", [])
        formatted_results = []
        
        for item in items:
            formatted_results.append({
                "path": item.get("path"),
                "repository": item.get("repository", {}).get("full_name"),
                "html_url": item.get("html_url"),
                "score": item.get("score"),
                "text_matches": item.get("text_matches", [])
            })
        
        return {
            "total_count": result.get("total_count", 0),
            "results": formatted_results
        }
        
    except Exception as e:
        logger.error(f"Error searching repository: {e}")
        return {"error": str(e)}


async def get_file_content(owner: str, repo: str, path: str) -> Dict:
    """
    Получить содержимое конкретного файла
    
    Args:
        owner: Владелец репозитория
        repo: Название репозитория
        path: Путь к файлу
    
    Returns:
        dict с содержимым файла
    """
    if not _github_client:
        return {"error": "GitHub client not initialized"}
    
    try:
        result = await _github_client.get_file_contents(owner, repo, path)
        return result
    except Exception as e:
        logger.error(f"Error getting file content: {e}")
        return {"error": str(e)}
