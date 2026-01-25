import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp_clients.ollama_client import MCPOllamaClient
from config import (
    MCP_OLLAMA_SSH_HOST,
    MCP_OLLAMA_SSH_PORT,
    MCP_OLLAMA_SSH_USER,
    MCP_OLLAMA_SSH_KEY,
    MCP_OLLAMA_NODE_PATH,
    MCP_OLLAMA_SERVER_PATH
)

async def rebuild():
    """Пересоздать хранилище с нуля"""
    
    print("🔌 Подключаюсь к Ollama MCP...")
    client = MCPOllamaClient(
        ssh_host=MCP_OLLAMA_SSH_HOST,
        ssh_port=MCP_OLLAMA_SSH_PORT,
        ssh_user=MCP_OLLAMA_SSH_USER,
        ssh_key=MCP_OLLAMA_SSH_KEY,
        node_path=MCP_OLLAMA_NODE_PATH,
        server_path=MCP_OLLAMA_SERVER_PATH
    )
    await client.start()
    
    print("🔄 Читаю FAQ файл...")
    with open('support_faq.txt', 'r', encoding='utf-8') as f:
        faq_text = f.read()
    
    # Разбиваем на простые вопрос-ответ блоки
    print("✂️ Разбиваю FAQ на Q&A пары...")
    
    # Простое разбиение по двойному переводу строки
    blocks = [b.strip() for b in faq_text.split('\n\n') if b.strip() and len(b.strip()) > 50]
    
    print(f"📄 Создано {len(blocks)} блоков")
    
    # Создаём один большой chunk_and_embed для всего FAQ
    # но с меньшими чанками
    print("🧠 Создаю эмбеддинги...")
    
    all_chunks_data = []
    
    # Обрабатываем по 5 блоков за раз
    for i in range(0, len(blocks), 5):
        batch = blocks[i:i+5]
        batch_text = "\n\n---\n\n".join(batch)
        
        print(f"  📝 Batch {i//5 + 1}/{(len(blocks)-1)//5 + 1}...", end='\r')
        
        # Используем rag_answer напрямую для создания эмбеддингов
        # Это более надёжный способ
        result = await client.call_tool("chunk_and_embed", {
            "text": batch_text,
            "chunk_size": 800,
            "chunk_overlap": 50
        })
        
        if result and 'chunks' in result:
            all_chunks_data.extend(result['chunks'])
    
    print(f"\n✅ Создано {len(all_chunks_data)} эмбеддингов")
    
    if not all_chunks_data:
        print("❌ Не удалось создать эмбеддинги")
        await client.stop()
        return
    
    # Сохраняем в НОВОЕ хранилище
    print("💾 Сохраняю в bot_knowledge...")
    save_result = await client.call_tool("vector_store_save", {
        "name": "bot_knowledge",
        "chunks": all_chunks_data
    })
    
    if save_result:
        print(f"✅ Сохранено {len(all_chunks_data)} чанков")
        
        # Проверяем загрузку
        print("🔍 Проверяю загрузку...")
        load_result = await client.call_tool("vector_store_load", {
            "name": "bot_knowledge"
        })
        
        if load_result and 'chunks' in load_result:
            print(f"✅ Хранилище успешно загружается: {len(load_result['chunks'])} чанков")
        else:
            print(f"⚠️ Проблема с загрузкой: {load_result}")
    else:
        print("❌ Ошибка сохранения")
    
    await client.stop()
    print("✅ Готово!")

if __name__ == "__main__":
    asyncio.run(rebuild())
