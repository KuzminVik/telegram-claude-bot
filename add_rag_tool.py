import sys

# Читаем файл
with open('bot.py', 'r') as f:
    lines = f.readlines()

# Ищем строку с последним }
for i, line in enumerate(lines):
    if i > 1460 and line.strip() == '}' and 'mobile_start_emulator' in ''.join(lines[i-20:i]):
        # Нашли конец mobile_start_emulator
        # Заменяем } на },
        lines[i] = line.replace('}', '},')
        
        # Вставляем новый инструмент
        new_tool = '''        {
            "name": "search_knowledge",
            "description": "Search stored knowledge base using RAG",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string"},
                    "top_k": {"type": "number", "default": 3}
                },
                "required": ["query"]
            }
        }
'''
        lines.insert(i+1, new_tool)
        break

# Сохраняем
with open('bot.py', 'w') as f:
    f.writelines(lines)

print("✅ RAG tool added")
