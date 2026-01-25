#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG функции - работа с Retrieval-Augmented Generation с Reranker
"""

import time
import logging
from datetime import datetime

from config import (
    RAG_COMPARISON_FILE,
    RAG_VECTOR_STORE_NAME,
    RAG_TOP_K_INITIAL,
    RAG_LLM_MODEL
)

logger = logging.getLogger(__name__)

# Глобальная ссылка на MCP Ollama client (устанавливается в bot.py)
_ollama_client = None


def set_ollama_client(client):
    """Установить глобальный Ollama client"""
    global _ollama_client
    _ollama_client = client


async def get_rag_answer(query: str, rerank_mode: str, store_name: str = None) -> dict:
    """
    Получить ответ через RAG с reranking
    
    Args:
        query: Вопрос пользователя
        rerank_mode: 'light' (top-5) или 'strict' (top-2)
        store_name: Имя векторного хранилища
    
    Returns:
        dict с ответом, источниками и метриками
    """
    if store_name is None:
        store_name = RAG_VECTOR_STORE_NAME
    
    start_time = time.time()
    
    if not _ollama_client:
        return {
            "answer": "RAG недоступен",
            "error": "MCP Ollama client not initialized",
            "time": 0,
            "sources": [],
            "rerank_mode": rerank_mode
        }
    
    try:
        result = await _ollama_client.call_tool(
            "rag_answer",
            {
                "store_name": store_name,
                "query": query,
                "top_k": RAG_TOP_K_INITIAL,  # Берем больше для reranking
                "model": RAG_LLM_MODEL,
                "rerank_mode": rerank_mode  # 'light' или 'strict'
            }
        )
        
        elapsed = time.time() - start_time
        
        if result:
            return {
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "model": result.get("model", RAG_LLM_MODEL),
                "chunks_used": result.get("chunks_used", 0),
                "time": round(elapsed, 2),
                "context_length": result.get("context_length", 0),
                "rerank_mode": rerank_mode,
                "reranked": result.get("reranked", False)
            }
        else:
            return {
                "answer": "Ошибка получения ответа через RAG",
                "error": "No result from MCP",
                "time": round(elapsed, 2),
                "sources": [],
                "rerank_mode": rerank_mode
            }
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Error in get_rag_answer: {e}")
        return {
            "answer": f"Ошибка: {str(e)}",
            "error": str(e),
            "time": round(elapsed, 2),
            "sources": [],
            "rerank_mode": rerank_mode
        }


def save_comparison(comparison_data: dict):
    """Сохранить результат сравнения в файл"""
    import json
    
    try:
        if RAG_COMPARISON_FILE.exists():
            with open(RAG_COMPARISON_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
        else:
            data = {"comparisons": []}
        
        comparison_data["timestamp"] = datetime.now().isoformat()
        data["comparisons"].append(comparison_data)
        
        # Ограничиваем до последних 100 сравнений
        if len(data["comparisons"]) > 100:
            data["comparisons"] = data["comparisons"][-100:]
        
        with open(RAG_COMPARISON_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"Saved comparison to {RAG_COMPARISON_FILE}")
    except Exception as e:
        logger.error(f"Error saving comparison: {e}")
