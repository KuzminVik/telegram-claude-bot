import asyncio
import sys
import os
import re

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

async def load_faq():
    """Загрузить FAQ в векторное хранилище"""
    
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
    
    print(f"📄 Загружено {len(faq_text)} символов")
    
    # Разбиваем на секции по заголовкам ###
    print("✂️ Разбиваю на секции...")
    sections = re.split(r'\n### ', faq_text)
    
    # Первая секция содержит заголовок ##, обрабатываем отдельно
    all_chunks = []
    
    for i, section in enumerate(sections):
        if not section.strip():
            continue
        
        # Восстанавливаем заголовок
        if i > 0:
            section = "### " + section
        
        # Ограничиваем размер секции до 800 символов
        if len(section) > 800:
            # Разбиваем по абзацам
            paragraphs = section.split('\n\n')
            current_chunk = ""
            
            for para in paragraphs:
                if len(current_chunk) + len(para) < 800:
                    current_chunk += para + "\n\n"
                else:
                    if current_chunk.strip():
                        all_chunks.append(current_chunk.strip())
                    current_chunk = para + "\n\n"
            
            if current_chunk.strip():
                all_chunks.append(current_chunk.strip())
        else:
            all_chunks.append(section.strip())
    
    print(f"✅ Создано {len(all_chunks)} секций вручную")
    
    # Создаём эмбеддинги для каждого чанка
    print("🧠 Создаю эмбеддинги для каждой секции...")
    embedded_chunks = []
    
    for idx, chunk_text in enumerate(all_chunks):
        print(f"  📝 Обрабатываю {idx+1}/{len(all_chunks)}...", end='\r')
        
        result = await client.call_tool("chunk_and_embed", {
            "text": chunk_text,
            "chunk_size": 2000,  # Большой размер, т.к. уже разбили
            "chunk_overlap": 0
        })
        
        if result and 'chunks' in result:
            embedded_chunks.extend(result['chunks'])
    
    print(f"\n✅ Создано {len(embedded_chunks)} эмбеддингов")
    
    # Загружаем существующее хранилище
    print("💾 Добавляю в векторное хранилище bot_knowledge...")
    load_result = await client.call_tool("vector_store_load", {
        "name": "bot_knowledge"
    })
    
    existing_chunks = load_result.get('chunks', []) if load_result else []
    print(f"📦 Существующих чанков: {len(existing_chunks)}")
    
    # Объединяем
    all_embedded = existing_chunks + embedded_chunks
    
    # Сохраняем
    save_result = await client.call_tool("vector_store_save", {
        "name": "bot_knowledge",
        "chunks": all_embedded
    })
    
    if save_result:
        print(f"✅ Сохранено {len(all_embedded)} чанков в bot_knowledge")
        print(f"📊 Добавлено новых: {len(embedded_chunks)}")
    else:
        print("❌ Ошибка сохранения")
    
    await client.stop()
    print("✅ Готово!")

if __name__ == "__main__":
    asyncio.run(load_faq())
