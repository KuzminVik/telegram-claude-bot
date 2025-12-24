#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
RAG функции - работа с Retrieval-Augmented Generation
"""

import time
import logging
from datetime import datetime
from anthropic import Anthropic

from config import (
    ANTHROPIC_API_KEY,
    RAG_COMPARISON_FILE,
    RAG_VECTOR_STORE_NAME,
    RAG_TOP_K,
    CLAUDE_MODEL
)

logger = logging.getLogger(__name__)

# Глобальный клиент Anthropic
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Глобальная ссылка на MCP Ollama client (устанавливается в bot.py)
_ollama_client = None


def set_ollama_client(client):
    """Установить глобальный Ollama client"""
    global _ollama_client
    _ollama_client = client


async def get_rag_answer(query: str, store_name: str = None) -> dict:
    """Получить ответ через RAG"""
    if store_name is None:
        store_name = RAG_VECTOR_STORE_NAME
    
    start_time = time.time()
    
    if not _ollama_client:
        return {
            "answer": "RAG недоступен",
            "error": "MCP Ollama client not initialized",
            "time": 0,
            "sources": []
        }
    
    try:
        result = await _ollama_client.call_tool(
            "rag_answer",
            {
                "store_name": store_name,
                "query": query,
                "top_k": RAG_TOP_K
            }
        )
        
        elapsed = time.time() - start_time
        
        if result:
            return {
                "answer": result.get("answer", ""),
                "sources": result.get("sources", []),
                "model": result.get("model", "llama3.2:3b"),
                "chunks_used": result.get("chunks_used", 0),
                "time": round(elapsed, 2),
                "context_length": result.get("context_length", 0)
            }
        else:
            return {
                "answer": "Ошибка получения ответа через RAG",
                "error": "No result from MCP",
                "time": round(elapsed, 2),
                "sources": []
            }
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Error in get_rag_answer: {e}")
        return {
            "answer": f"Ошибка: {str(e)}",
            "error": str(e),
            "time": round(elapsed, 2),
            "sources": []
        }


async def get_no_rag_answer(query: str) -> dict:
    """Получить ответ без RAG (прямо от Claude)"""
    start_time = time.time()
    
    try:
        response = anthropic_client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1000,
            messages=[
                {"role": "user", "content": query}
            ]
        )
        
        elapsed = time.time() - start_time
        
        answer = response.content[0].text if response.content else ""
        
        return {
            "answer": answer,
            "model": "claude-sonnet-4",
            "time": round(elapsed, 2),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    except Exception as e:
        elapsed = time.time() - start_time
        logger.error(f"Error in get_no_rag_answer: {e}")
        return {
            "answer": f"Ошибка: {str(e)}",
            "error": str(e),
            "time": round(elapsed, 2)
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
