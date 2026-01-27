#!/usr/bin/env python3
"""Load developer profile into RAG system"""
import asyncio
import sys

sys.path.insert(0, "/root/telegram-bot")

from mcp_clients import init_mcp_clients, mcp_ollama_rag_client, shutdown_mcp_clients
from telegram.ext import Application

async def load_profile():
    print("Initializing MCP clients...")
    app = Application.builder().token("dummy").build()
    await init_mcp_clients(app)
    
    if mcp_ollama_rag_client is None:
        print("❌ Ollama RAG client not available")
        return
    
    print("✓ Ollama RAG client initialized")
    
    profile_text = """# Профиль разработчика: Виктор Кузьмин

## Личная информация
Имя: Виктор Кузьмин
Роль: Senior Developer / Systems Architect
Язык: Русский

## Стиль работы
Подход: прагматичный, итеративный, экспериментальный
Методология: Build → Test → Document → Improve
Фокус: Production-ready решения с правильной архитектурой

## Технические компетенции
Основные языки: Python, JavaScript, Bash
Интересы: AI/LLM, DevOps, системные интеграции, автоматизация

Принципы архитектуры:
- Модульный дизайн с разделением ответственности
- Graceful degradation и обработка ошибок
- Single source of truth для конфигурации

## Принятие решений
- Простые решения вместо сложных
- Метрики и data-driven оптимизация
- Понимание trade-offs перед выбором
- Эксперимент, измерение, валидация

## Предпочтения в коммуникации
Стиль: Краткий, code-first ответы
Temperature: 0.3
Обработка задач: Пошагово для многошаговых задач

## Решение проблем
Паттерн: Попробовать решение → Отладить → Альтернатива → Документировать
Настойчивость: Не сдаваться на сложных проблемах"""
    
    print(f"\nПрофиль: {len(profile_text)} символов")
    
    print("\n📦 Создание эмбеддингов...")
    result = await mcp_ollama_rag_client.call_tool("chunk_and_embed", {
        "text": profile_text,
        "chunk_size": 800,
        "chunk_overlap": 100
    })
    print(f"✓ {result}")
    
    print("\n💾 Сохранение в bot_knowledge...")
    result = await mcp_ollama_rag_client.call_tool("vector_store_save", {
        "store_name": "bot_knowledge"
    })
    print(f"✓ {result}")
    
    await shutdown_mcp_clients(app)
    print("\n✅ Профиль загружен!")

if __name__ == "__main__":
    asyncio.run(load_profile())
