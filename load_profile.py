import asyncio
import sys
sys.path.insert(0, '/root/telegram-bot')

from mcp_clients import init_mcp_clients, mcp_ollama_rag_client, shutdown_mcp_clients
from telegram.ext import Application

async def main():
    app = Application.builder().token('dummy').build()
    await init_mcp_clients(app)
    
    profile = '''Виктор Кузьмин - Senior Developer, Systems Architect.
Стиль работы: прагматичный, итеративный, экспериментальный.
Методология: Build → Test → Document → Improve.
Языки: Python, JavaScript, Bash.
Интересы: AI/LLM, DevOps, автоматизация.
Принципы: простые решения, метрики, trade-offs.
Коммуникация: краткий code-first стиль, temperature 0.3.
Решение проблем: попробовать → отладить → альтернатива → документировать.'''
    
    print('Загрузка профиля в RAG...')
    result1 = await mcp_ollama_rag_client.call_tool('chunk_and_embed', {'text': profile, 'chunk_size': 500})
    print(f'Chunk result: {result1}')
    
    result2 = await mcp_ollama_rag_client.call_tool('vector_store_save', {'store_name': 'bot_knowledge'})
    print(f'Save result: {result2}')
    
    await shutdown_mcp_clients(app)
    print('✅ Готово!')

asyncio.run(main())
