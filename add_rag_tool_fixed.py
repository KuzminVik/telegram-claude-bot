# Откатываемся
import shutil
shutil.copy('bot.py.backup_before_ollama', 'bot.py')

# Читаем файл
with open('bot.py', 'r') as f:
    content = f.read()

# Находим mobile_start_emulator и добавляем после него
old_text = '''            }
        }
    ]'''

new_text = '''            }
        },
        {
            "name": "search_knowledge",
            "description": "Search knowledge base using RAG",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query"},
                    "top_k": {"type": "number", "default": 3}
                },
                "required": ["query"]
            }
        }
    ]'''

content = content.replace(old_text, new_text)

# Сохраняем
with open('bot.py', 'w') as f:
    f.write(content)

print("✅ Done")
