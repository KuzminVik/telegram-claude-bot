"""
Утилиты для работы с GitHub API
Постинг комментариев, получение diff и т.д.
"""

import os
import logging
import aiohttp
from typing import Optional

logger = logging.getLogger(__name__)

GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_API_BASE = "https://api.github.com"

async def post_pr_comment(
    owner: str, 
    repo: str, 
    pr_number: int, 
    comment_body: str
) -> bool:
    """
    Постинг комментария в Pull Request
    
    Args:
        owner: Владелец репозитория
        repo: Название репозитория
        pr_number: Номер PR
        comment_body: Текст комментария (Markdown)
    
    Returns:
        bool: True если успешно
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN не установлен")
        return False
    
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/issues/{pr_number}/comments"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    # Добавляем префикс для автоматических ревью
    full_comment = f"""🤖 **Автоматическое Code Review**

{comment_body}

---
*Это автоматическое ревью от бота. При необходимости запросите ревью у человека.*
"""
    
    payload = {
        "body": full_comment
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url, 
                headers=headers, 
                json=payload
            ) as response:
                
                if response.status == 201:
                    logger.info(
                        f"Комментарий успешно опубликован в PR #{pr_number}"
                    )
                    return True
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Ошибка при публикации комментария: "
                        f"{response.status} - {error_text}"
                    )
                    return False
                    
    except Exception as e:
        logger.error(f"Исключение при публикации комментария: {e}")
        return False

async def get_pr_diff(
    owner: str, 
    repo: str, 
    pr_number: int
) -> Optional[str]:
    """
    Получение diff Pull Request
    
    Args:
        owner: Владелец репозитория
        repo: Название репозитория
        pr_number: Номер PR
    
    Returns:
        str: Содержимое diff или None
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN не установлен")
        return None
    
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3.diff",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                
                if response.status == 200:
                    diff_content = await response.text()
                    logger.info(
                        f"Получен diff для PR #{pr_number}, "
                        f"размер: {len(diff_content)} символов"
                    )
                    return diff_content
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Ошибка при получении diff: "
                        f"{response.status} - {error_text}"
                    )
                    return None
                    
    except Exception as e:
        logger.error(f"Исключение при получении diff: {e}")
        return None

async def get_pr_files(
    owner: str, 
    repo: str, 
    pr_number: int
) -> list:
    """
    Получение списка изменённых файлов в PR
    
    Args:
        owner: Владелец репозитория
        repo: Название репозитория
        pr_number: Номер PR
    
    Returns:
        list: Список словарей с информацией о файлах
    """
    if not GITHUB_TOKEN:
        logger.error("GITHUB_TOKEN не установлен")
        return []
    
    url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/pulls/{pr_number}/files"
    
    headers = {
        "Authorization": f"Bearer {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
        "X-GitHub-Api-Version": "2022-11-28"
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                
                if response.status == 200:
                    files_data = await response.json()
                    logger.info(
                        f"Получено {len(files_data)} файлов для PR #{pr_number}"
                    )
                    return files_data
                else:
                    error_text = await response.text()
                    logger.error(
                        f"Ошибка при получении файлов: "
                        f"{response.status} - {error_text}"
                    )
                    return []
                    
    except Exception as e:
        logger.error(f"Исключение при получении файлов: {e}")
        return []
