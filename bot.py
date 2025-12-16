import os
import logging
import json
import re
import time
import subprocess
import asyncio
from pathlib import Path
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from anthropic import Anthropic

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токены из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
    raise ValueError("Missing required environment variables: TELEGRAM_BOT_TOKEN or ANTHROPIC_API_KEY")

# Инициализация клиента Anthropic
client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Хранилище режимов (остаются в памяти, т.к. это не критичные данные)
spec_mode = {}      # {user_id: bool} - режим сбора ТЗ
models_mode = {}    # {user_id: bool} - режим сравнения моделей

# Конфигурация моделей
MODELS_CONFIG = {
    'opus': 'claude-opus-4-20250514',
    'sonnet': 'claude-sonnet-4-5-20250929',
    'haiku': 'claude-haiku-4-5-20251001'
}

# Настройки сжатия истории и хранения
COMPRESSION_THRESHOLD = 10  # Сжимать каждые 10 сообщений
MAX_HISTORY_LENGTH = 30     # Максимальная длина истории
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ в байтах
CONVERSATIONS_DIR = Path("/root/telegram-bot/conversations")

# Путь к MCP серверу погоды
MCP_WEATHER_SERVER_PATH = "/home/claude/mcp-weather-server/server.js"

# ========================================
# МОДУЛЬ MCP КЛИЕНТА
# ========================================

class MCPWeatherClient:
    """Клиент для работы с MCP Weather Server"""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.process = None
        self.request_id = 0
    
    async def start(self):
        """Запускает MCP сервер как subprocess"""
        try:
            self.process = await asyncio.create_subprocess_exec(
                'node', self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            logger.info("✓ MCP Weather Server started")
        except Exception as e:
            logger.error(f"Failed to start MCP Weather Server: {e}")
            raise
    
    async def stop(self):
        """Останавливает MCP сервер"""
        if self.process:
            self.process.terminate()
            await self.process.wait()
            logger.info("MCP Weather Server stopped")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Вызывает инструмент MCP сервера"""
        if not self.process:
            raise RuntimeError("MCP server not started")
        
        self.request_id += 1
        request = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments
            },
            "id": self.request_id
        }
        
        # Отправляем запрос
        request_json = json.dumps(request) + '\n'
        self.process.stdin.write(request_json.encode())
        await self.process.stdin.drain()
        
        # Читаем ответ
        response_line = await self.process.stdout.readline()
        response = json.loads(response_line.decode())
        
        if 'error' in response:
            raise RuntimeError(f"MCP error: {response['error']}")
        
        return response.get('result', {})

# Глобальный экземпляр MCP клиента
mcp_client = None

# ========================================
# МОДУЛЬ РАБОТЫ С JSON ФАЙЛАМИ
# ========================================

def ensure_conversations_dir():
    """Создает директорию для хранения файлов истории, если её нет"""
    try:
        CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
        logger.info(f"Conversations directory ready: {CONVERSATIONS_DIR}")
    except Exception as e:
        logger.error(f"Failed to create conversations directory: {e}")
        raise


def get_conversation_filepath(user_id: int) -> Path:
    """Возвращает путь к файлу истории конкретного пользователя"""
    return CONVERSATIONS_DIR / f"user_{user_id}.json"


def load_conversation(user_id: int) -> list:
    """
    Загружает историю разговора пользователя из JSON файла.
    Возвращает список сообщений или пустой список, если файла нет.
    """
    filepath = get_conversation_filepath(user_id)
    
    try:
        if not filepath.exists():
            logger.info(f"No conversation file for user {user_id}, returning empty history")
            return []
        
        # Проверка размера файла
        file_size = filepath.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"Conversation file for user {user_id} exceeds max size ({file_size} bytes), truncating")
            # Загружаем и обрезаем до последних MAX_HISTORY_LENGTH сообщений
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                if len(messages) > MAX_HISTORY_LENGTH:
                    messages = messages[-MAX_HISTORY_LENGTH:]
                    save_conversation(user_id, messages)  # Сохраняем обрезанную версию
                return messages
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            messages = data.get('messages', [])
            logger.info(f"Loaded {len(messages)} messages for user {user_id}")
            return messages
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in conversation file for user {user_id}: {e}")
        # Создаем backup поврежденного файла
        backup_path = filepath.with_suffix('.json.backup')
        filepath.rename(backup_path)
        logger.info(f"Corrupted file backed up to {backup_path}")
        return []
        
    except Exception as e:
        logger.error(f"Error loading conversation for user {user_id}: {e}", exc_info=True)
        return []


def save_conversation(user_id: int, messages: list) -> bool:
    """
    Сохраняет историю разговора пользователя в JSON файл.
    Возвращает True при успехе, False при ошибке.
    
    Структура файла:
    {
        "user_id": 12345,
        "last_updated": "2024-12-14T12:00:00",
        "message_count": 10,
        "messages": [
            {"role": "user", "content": "..."},
            {"role": "assistant", "content": "..."}
        ]
    }
    """
    filepath = get_conversation_filepath(user_id)
    
    try:
        # Ограничиваем историю максимальной длиной
        if len(messages) > MAX_HISTORY_LENGTH:
            messages = messages[-MAX_HISTORY_LENGTH:]
            logger.info(f"Truncated conversation for user {user_id} to {MAX_HISTORY_LENGTH} messages")
        
        data = {
            "user_id": user_id,
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "message_count": len(messages),
            "messages": messages
        }
        
        # Сохраняем с отступами для читаемости
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        # Проверяем размер сохраненного файла
        file_size = filepath.stat().st_size
        logger.info(f"Saved {len(messages)} messages for user {user_id} ({file_size} bytes)")
        
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"File size exceeds limit after save, will truncate on next load")
        
        return True
        
    except Exception as e:
        logger.error(f"Error saving conversation for user {user_id}: {e}", exc_info=True)
        return False


def delete_conversation(user_id: int) -> bool:
    """
    Удаляет файл истории пользователя.
    Возвращает True при успехе, False при ошибке.
    """
    filepath = get_conversation_filepath(user_id)
    
    try:
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted conversation file for user {user_id}")
            return True
        else:
            logger.info(f"No conversation file to delete for user {user_id}")
            return True
            
    except Exception as e:
        logger.error(f"Error deleting conversation for user {user_id}: {e}", exc_info=True)
        return False


def get_conversation_stats(user_id: int) -> dict:
    """
    Возвращает статистику по файлу истории пользователя.
    """
    filepath = get_conversation_filepath(user_id)
    
    if not filepath.exists():
        return {
            "exists": False,
            "message_count": 0,
            "file_size": 0
        }
    
    try:
        file_size = filepath.stat().st_size
        messages = load_conversation(user_id)
        
        return {
            "exists": True,
            "message_count": len(messages),
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2)
        }
        
    except Exception as e:
        logger.error(f"Error getting stats for user {user_id}: {e}")
        return {
            "exists": True,
            "message_count": 0,
            "file_size": 0,
            "error": str(e)
        }

# ========================================
# КОНЕЦ МОДУЛЯ РАБОТЫ С JSON ФАЙЛАМИ
# ========================================

# Системные промпты
NORMAL_SYSTEM_PROMPT = """You are a helpful AI assistant with access to weather information.

TOOLS AVAILABLE:
You have access to a "get_weather" tool that provides current weather data for any city.
When a user asks about weather, you MUST use this tool by including a tool_use block in your response.

RESPONSE FORMAT - CRITICAL:
You must ALWAYS respond with ONLY a valid JSON object containing exactly two fields:
- "user_message": the exact user's message
- "ai_message": your response as a string

CRITICAL RULES:
1. Your entire response must be ONLY the JSON object - nothing before, nothing after
2. Do NOT wrap the JSON in markdown code blocks (no ```json or ```)
3. Do NOT add any explanatory text outside the JSON
4. The JSON must be valid and parseable
5. Both fields must be present in every response

Example of correct response:
{"user_message": "Hello", "ai_message": "Hi! How can I help you today?"}

Example of INCORRECT response:
```json
{"user_message": "Hello", "ai_message": "Hi!"}
```

Remember: ONLY the raw JSON object, nothing else!"""

SPEC_SYSTEM_PROMPT = """You are a business analyst helping to gather requirements for a mobile application. Your task is to collect a comprehensive technical specification through a conversational interview.

RESPONSE FORMAT - CRITICAL:
You must ALWAYS respond with ONLY a valid JSON object containing exactly two fields:
- "user_message": the exact user's message
- "ai_message": your question or final specification as a string

INTERVIEW PROCESS:
1. Ask ONE question at a time, starting from general to specific:
   - Target platform (iOS/Android/Cross-platform)
   - Business logic and app purpose
   - Core features and functionality
   - Data storage requirements
   - User authentication needs
   - External service integrations
   - Design and UI/UX requirements
   - Technical constraints and limitations

2. Internally track what information you've collected

3. After 8-12 meaningful exchanges, when you have enough information, generate the final technical specification in the "ai_message" field formatted like this:

📋 ТЕХНИЧЕСКОЕ ЗАДАНИЕ

🎯 Проект: [Name]
📱 Платформа: [Platform]

📝 Описание:
[Detailed description]

⚙️ Основные функции:
1. [Feature 1]
2. [Feature 2]
...

🔧 Технические требования:
[Technical requirements]

💾 Хранение данных:
[Data storage approach]

🔐 Аутентификация:
[Auth requirements]

🎨 Дизайн:
[Design requirements]

Remember: ONLY the raw JSON object with these two fields, nothing else!"""

MODELS_SYSTEM_PROMPT = """You are a helpful AI assistant. Provide a clear, concise, and accurate response to the user's question.

RESPONSE FORMAT - CRITICAL:
You must ALWAYS respond with ONLY a valid JSON object containing exactly two fields:
- "user_message": the exact user's message
- "ai_message": your response as a string

Keep your response focused and informative, but concise since multiple models will be answering.

Remember: ONLY the raw JSON object, nothing else!"""

COMPRESSION_SYSTEM_PROMPT = """You are a helpful assistant that creates concise summaries of conversation history.

Your task is to create a brief summary of the conversation provided. The summary should:
1. Capture the key topics discussed
2. Preserve important facts, decisions, or conclusions
3. Be concise but informative (2-4 sentences)
4. Be written in the same language as the conversation

Respond with ONLY a valid JSON object:
{"summary": "your summary text here"}

Remember: ONLY the raw JSON object, nothing else!"""


def clean_json_response(text: str) -> str:
    """Извлекает JSON из ответа, удаляя markdown и лишний текст"""
    text = text.strip()
    
    # Удаляем markdown блоки кода
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Находим первый JSON объект
    match = re.search(r'\{.*\}', text, re.DOTALL)
    if match:
        return match.group(0)
    
    return text


def serialize_message_content(content):
    """
    Конвертирует содержимое сообщения Anthropic в JSON-сериализуемый формат.
    Обрабатывает ToolUseBlock, TextBlock и другие типы контента.
    """
    if isinstance(content, str):
        return content
    
    if isinstance(content, list):
        result = []
        for item in content:
            if hasattr(item, 'model_dump'):
                # Anthropic объекты имеют метод model_dump()
                result.append(item.model_dump())
            elif hasattr(item, 'dict'):
                # Старый метод для pydantic v1
                result.append(item.dict())
            elif isinstance(item, dict):
                result.append(item)
            else:
                # Если это простой тип (str, int и т.д.)
                result.append(item)
        return result
    
    # Если это один объект Anthropic
    if hasattr(content, 'model_dump'):
        return content.model_dump()
    elif hasattr(content, 'dict'):
        return content.dict()
    
    return content


async def compress_conversation(user_id: int) -> bool:
    """
    Сжимает историю разговора, создавая саммари последних N сообщений.
    Сохраняет результат в JSON файл.
    Возвращает True если сжатие выполнено успешно.
    """
    try:
        messages = load_conversation(user_id)
        
        if len(messages) < COMPRESSION_THRESHOLD:
            return False
        
        # Берем последние COMPRESSION_THRESHOLD сообщений для сжатия
        messages_to_compress = messages[-COMPRESSION_THRESHOLD:]
        
        # Формируем текст для суммаризации
        conversation_text = "\n\n".join([
            f"{'User' if msg['role'] == 'user' else 'Assistant'}: {msg['content']}"
            for msg in messages_to_compress
        ])
        
        logger.info(f"Compressing {COMPRESSION_THRESHOLD} messages for user {user_id}")
        
        # Запрашиваем саммари у Claude
        response = client.messages.create(
            model=MODELS_CONFIG['sonnet'],
            max_tokens=500,
            temperature=0.3,
            system=COMPRESSION_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": f"Create a summary of this conversation:\n\n{conversation_text}"
            }]
        )
        
        raw_response = response.content[0].text
        cleaned_json = clean_json_response(raw_response)
        parsed_json = json.loads(cleaned_json)
        summary = parsed_json.get('summary', '')
        
        if not summary:
            logger.error("Empty summary received, skipping compression")
            return False
        
        # Заменяем последние COMPRESSION_THRESHOLD сообщений на одно сжатое
        messages = messages[:-COMPRESSION_THRESHOLD]
        messages.append({
            "role": "assistant",
            "content": json.dumps({
                "user_message": "[История сжата]",
                "ai_message": f"📦 Сжатая история ({COMPRESSION_THRESHOLD} сообщений): {summary}"
            })
        })
        
        # Сохраняем обновленную историю в файл
        save_success = save_conversation(user_id, messages)
        
        if save_success:
            logger.info(f"✓ Successfully compressed and saved conversation for user {user_id}")
            logger.info(f"Summary: {summary[:100]}...")
            return True
        else:
            logger.error(f"Failed to save compressed conversation for user {user_id}")
            return False
        
    except Exception as e:
        logger.error(f"❌ Error compressing conversation for user {user_id}: {e}", exc_info=True)
        return False


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    
    welcome_message = """👋 Привет! Я бот с интеграцией Claude AI.

📋 Доступные режимы работы:

🤖 **Обычный режим** (активен по умолчанию)
Просто напиши мне сообщение, и я отвечу.
💡 История автоматически сжимается каждые 10 сообщений для экономии токенов.
🌤️ Могу рассказать о погоде - просто спроси!

📱 **Режим /spec**
Запусти командой /spec для интерактивного сбора технического задания на мобильное приложение.

🔬 **Режим /models**
Запусти командой /models для сравнения ответов трёх моделей Claude (Opus, Sonnet, Haiku) на один вопрос.

⚙️ **Команды управления:**
/start - показать это сообщение
/spec - войти в режим сбора ТЗ
/exit_spec - выйти из режима сбора ТЗ
/models - войти в режим сравнения моделей
/exit_models - выйти из режима сравнения моделей
/clear - очистить историю разговора
/stats - показать статистику истории
/debug - показать последний JSON ответ"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"User {user_id} started the bot")


async def spec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /spec - вход в режим сбора ТЗ"""
    user_id = update.effective_user.id
    spec_mode[user_id] = True
    models_mode[user_id] = False  # Выключаем режим models
    
    # Очищаем историю при входе в режим spec
    delete_conversation(user_id)
    
    await update.message.reply_text(
        "📋 Режим сбора технического задания активирован!\n\n"
        "Я помогу собрать требования для мобильного приложения. "
        "Отвечайте на мои вопросы, и я сформирую полное ТЗ.\n\n"
        "Для выхода используйте команду /exit_spec"
    )
    
    # Отправляем первый вопрос
    first_question = "Давайте начнём! Для какой платформы вы планируете создать приложение: iOS, Android или кросс-платформенное решение?"
    await update.message.reply_text(first_question)
    
    logger.info(f"User {user_id} entered SPEC mode")


async def exit_spec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /exit_spec - выход из режима сбора ТЗ"""
    user_id = update.effective_user.id
    spec_mode[user_id] = False
    
    await update.message.reply_text(
        "✅ Вы вышли из режима сбора ТЗ.\n"
        "Теперь работает обычный режим. Можете задавать любые вопросы!"
    )
    logger.info(f"User {user_id} exited SPEC mode")


async def models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /models - вход в режим сравнения моделей"""
    user_id = update.effective_user.id
    models_mode[user_id] = True
    spec_mode[user_id] = False  # Выключаем режим spec
    
    await update.message.reply_text(
        "🔬 Режим сравнения моделей активирован!\n\n"
        "Теперь на каждый ваш вопрос я буду отвечать тремя моделями:\n"
        "• Claude Opus 4\n"
        "• Claude Sonnet 4.5\n"
        "• Claude Haiku 4.5\n\n"
        "Вы увидите все три ответа с информацией о времени генерации и количестве токенов.\n\n"
        "Для выхода используйте команду /exit_models"
    )
    logger.info(f"User {user_id} entered MODELS mode")


async def exit_models_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /exit_models - выход из режима сравнения моделей"""
    user_id = update.effective_user.id
    models_mode[user_id] = False
    
    await update.message.reply_text(
        "✅ Вы вышли из режима сравнения моделей.\n"
        "Теперь работает обычный режим. Можете задавать любые вопросы!"
    )
    logger.info(f"User {user_id} exited MODELS mode")


async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /clear - очистка истории"""
    user_id = update.effective_user.id
    success = delete_conversation(user_id)
    
    if success:
        await update.message.reply_text("🗑️ История разговора очищена!")
    else:
        await update.message.reply_text("⚠️ Не удалось очистить историю. Попробуйте снова.")
    
    logger.info(f"User {user_id} cleared conversation history")


async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /stats - показать статистику истории"""
    user_id = update.effective_user.id
    stats = get_conversation_stats(user_id)
    
    if not stats['exists']:
        await update.message.reply_text("📊 У вас пока нет сохраненной истории.")
        return
    
    message = f"""📊 Статистика вашей истории:

💬 Сообщений: {stats['message_count']}
📦 Размер файла: {stats['file_size_mb']} МБ
📁 Максимальный размер: 10 МБ
📝 Максимум сообщений: {MAX_HISTORY_LENGTH}"""
    
    if stats.get('error'):
        message += f"\n\n⚠️ Ошибка: {stats['error']}"
    
    await update.message.reply_text(message)
    logger.info(f"User {user_id} requested stats")


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /debug - показать последний JSON"""
    user_id = update.effective_user.id
    
    messages = load_conversation(user_id)
    
    if not messages:
        await update.message.reply_text("Нет сообщений в истории.")
        return
    
    last_message = messages[-1]
    formatted_json = json.dumps(last_message, indent=2, ensure_ascii=False)
    
    await update.message.reply_text(f"```json\n{formatted_json}\n```", parse_mode='Markdown')
    logger.info(f"User {user_id} requested debug info")


async def get_claude_response_single(model_name: str, messages: list, system_prompt: str) -> dict:
    """Получить ответ от одной модели Claude с замером времени и токенов"""
    start_time = time.time()
    
    try:
        response = client.messages.create(
            model=model_name,
            max_tokens=2048,
            temperature=0.3,
            system=system_prompt,
            messages=messages
        )
        
        end_time = time.time()
        elapsed_time = end_time - start_time
        
        # Получаем текст ответа
        raw_response = response.content[0].text
        
        # Получаем информацию о токенах
        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens
        total_tokens = input_tokens + output_tokens
        
        return {
            'success': True,
            'raw_response': raw_response,
            'elapsed_time': elapsed_time,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
            'total_tokens': total_tokens
        }
    except Exception as e:
        end_time = time.time()
        elapsed_time = end_time - start_time
        logger.error(f"Error getting response from {model_name}: {e}")
        return {
            'success': False,
            'error': str(e),
            'elapsed_time': elapsed_time
        }


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Основной обработчик сообщений"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    # Инициализация режимов для нового пользователя
    if user_id not in spec_mode:
        spec_mode[user_id] = False
    if user_id not in models_mode:
        models_mode[user_id] = False
    
    # Определяем режим работы
    is_spec_mode = spec_mode.get(user_id, False)
    is_models_mode = models_mode.get(user_id, False)
    
    logger.info(f"User {user_id} | Mode: {'MODELS' if is_models_mode else 'SPEC' if is_spec_mode else 'NORMAL'} | Message: {user_message[:50]}...")
    
    # Выбираем системный промпт
    if is_models_mode:
        system_prompt = MODELS_SYSTEM_PROMPT
    elif is_spec_mode:
        system_prompt = SPEC_SYSTEM_PROMPT
    else:
        system_prompt = NORMAL_SYSTEM_PROMPT
    
    # Загружаем историю из файла
    messages = load_conversation(user_id)
    
    # Добавляем сообщение пользователя в историю
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    try:
        if is_models_mode:
            # Режим сравнения моделей - запрашиваем все три модели
            await update.message.reply_text("🔄 Генерирую ответы от трёх моделей, подождите...")
            
            results = {}
            for model_key, model_name in MODELS_CONFIG.items():
                result = await get_claude_response_single(
                    model_name=model_name,
                    messages=messages,
                    system_prompt=system_prompt
                )
                results[model_key] = result
            
            # Формируем итоговый ответ
            response_parts = []
            
            for model_key in ['opus', 'sonnet', 'haiku']:
                result = results[model_key]
                model_name_display = {
                    'opus': '🔷 Claude Opus 4',
                    'sonnet': '🔶 Claude Sonnet 4.5',
                    'haiku': '🔸 Claude Haiku 4.5'
                }[model_key]
                
                response_parts.append(f"\n{'='*50}\n{model_name_display}\n{'='*50}\n")
                
                if result['success']:
                    # Парсим JSON ответ
                    cleaned_json = clean_json_response(result['raw_response'])
                    try:
                        parsed_json = json.loads(cleaned_json)
                        ai_message = parsed_json.get('ai_message', result['raw_response'])
                    except json.JSONDecodeError:
                        ai_message = result['raw_response']
                    
                    response_parts.append(ai_message)
                    
                    # Добавляем резюме
                    minutes = int(result['elapsed_time'] // 60)
                    seconds = int(result['elapsed_time'] % 60)
                    time_str = f"{minutes} мин {seconds} сек" if minutes > 0 else f"{seconds} сек"
                    
                    response_parts.append(
                        f"\n\n📊 Резюме:\n"
                        f"⏱ Время: {time_str}\n"
                        f"📝 Токены: {result['total_tokens']} "
                        f"(вход: {result['input_tokens']}, выход: {result['output_tokens']})"
                    )
                else:
                    response_parts.append(f"❌ Ошибка: {result['error']}")
            
            final_response = ''.join(response_parts)
            
            # Отправляем ответ (разбиваем если слишком длинный)
            if len(final_response) > 4000:
                # Telegram ограничение ~4096 символов
                chunks = [final_response[i:i+4000] for i in range(0, len(final_response), 4000)]
                for chunk in chunks:
                    await update.message.reply_text(chunk)
            else:
                await update.message.reply_text(final_response)
            
            # Добавляем в историю комбинированный ответ (для контекста)
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "user_message": user_message,
                    "ai_message": "Multiple model responses provided"
                })
            })
            
            # Сохраняем историю в файл
            save_conversation(user_id, messages)
            
        else:
            # Обычный режим или режим SPEC - одна модель
            # В обычном режиме Claude может использовать инструменты
            tools = None
            if not is_spec_mode:
                # Добавляем описание инструмента get_weather
                tools = [{
                    "name": "get_weather",
                    "description": "Получить текущую погоду для указанного города. Использует актуальные данные о температуре, влажности, осадках и ветре.",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "city": {
                                "type": "string",
                                "description": "Название города (на русском или английском). Например: 'Москва', 'Цюрих', 'London'"
                            }
                        },
                        "required": ["city"]
                    }
                }]
            
            response = client.messages.create(
                model=MODELS_CONFIG['sonnet'],  # Используем Sonnet по умолчанию
                max_tokens=2048,
                temperature=0.3,
                system=system_prompt,
                messages=messages,
                tools=tools
            )
            
            raw_response = response.content[0].text if response.content[0].type == "text" else ""
            logger.info(f"Raw response type: {response.content[0].type}")
            
            # Получаем информацию о токенах
            input_tokens = response.usage.input_tokens
            output_tokens = response.usage.output_tokens
            
            # Проверяем есть ли tool_use в ответе
            tool_use_blocks = [block for block in response.content if block.type == "tool_use"]
            
            if tool_use_blocks and not is_spec_mode:
                # Claude хочет использовать инструмент
                for tool_use in tool_use_blocks:
                    if tool_use.name == "get_weather":
                        city = tool_use.input.get("city", "")
                        logger.info(f"Claude wants weather for: {city}")
                        
                        try:
                            # Вызываем MCP сервер
                            result = await mcp_client.call_tool("get_weather", {"city": city})
                            weather_data = result['content'][0]['text']
                            
                            # Добавляем результат инструмента в историю
                            messages.append({
                                "role": "assistant",
                                "content": serialize_message_content(response.content)
                            })
                            messages.append({
                                "role": "user",
                                "content": [{
                                    "type": "tool_result",
                                    "tool_use_id": tool_use.id,
                                    "content": weather_data
                                }]
                            })
                            
                            # Запрашиваем финальный ответ с учетом данных о погоде
                            final_response = client.messages.create(
                                model=MODELS_CONFIG['sonnet'],
                                max_tokens=2048,
                                temperature=0.3,
                                system=system_prompt,
                                messages=messages,
                                tools=tools
                            )
                            
                            raw_response = final_response.content[0].text
                            input_tokens += final_response.usage.input_tokens
                            output_tokens += final_response.usage.output_tokens
                            
                        except Exception as e:
                            logger.error(f"Error calling MCP weather tool: {e}")
                            await update.message.reply_text(f"⚠️ Ошибка при получении погоды: {str(e)}")
                            return
            
            # Очищаем и парсим JSON
            cleaned_json = clean_json_response(raw_response)
            
            try:
                parsed_json = json.loads(cleaned_json)
                logger.info(f"✓ Successfully parsed JSON")
                
                # Добавляем ответ ассистента в историю
                messages.append({
                    "role": "assistant",
                    "content": cleaned_json
                })
                
                # Проверяем необходимость сжатия истории (только в обычном режиме, после добавления ответа)
                if not is_spec_mode:
                    if len(messages) >= COMPRESSION_THRESHOLD:
                        compression_success = await compress_conversation(user_id)
                        if compression_success:
                            await update.message.reply_text("📦 История сжата для экономии токенов")
                            # Перезагружаем историю после сжатия
                            messages = load_conversation(user_id)
                
                # Сохраняем историю в файл
                save_conversation(user_id, messages)
                
                # Отправляем ответ пользователю
                ai_message = parsed_json.get('ai_message', '')
                
                # В обычном режиме добавляем статистику токенов
                if not is_spec_mode:
                    ai_message += f"\n\n📊 Токены: вопрос {input_tokens} | ответ {output_tokens}"
                
                # Разбиваем длинные сообщения (Telegram лимит ~4096 символов)
                if len(ai_message) > 4000:
                    chunks = [ai_message[i:i+4000] for i in range(0, len(ai_message), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
                else:
                    await update.message.reply_text(ai_message)
                
                # Проверяем, завершён ли сбор ТЗ в режиме spec
                if is_spec_mode:
                    if "ТЕХНИЧЕСКОЕ ЗАДАНИЕ" in ai_message or "📋" in ai_message:
                        spec_mode[user_id] = False
                        logger.info(f"User {user_id} - SPEC mode completed, switching to NORMAL")
                        await update.message.reply_text(
                            "\n✅ Сбор технического задания завершён!\n"
                            "Переключаюсь в обычный режим."
                        )
                
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse JSON: {e}")
                logger.error(f"Cleaned JSON: {cleaned_json[:500]}...")
                
                # В случае ошибки парсинга отправляем сырой ответ с разбивкой
                error_message = f"⚠️ Получен некорректный формат ответа:\n\n{raw_response}"
                
                # Разбиваем длинные сообщения
                if len(error_message) > 4000:
                    chunks = [error_message[i:i+4000] for i in range(0, len(error_message), 4000)]
                    for chunk in chunks:
                        await update.message.reply_text(chunk)
                else:
                    await update.message.reply_text(error_message)
                
                # Добавляем сырой ответ в историю
                messages.append({
                    "role": "assistant",
                    "content": raw_response
                })
                
                # Сохраняем историю даже при ошибке
                save_conversation(user_id, messages)
    
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}", exc_info=True)
        await update.message.reply_text(
            f"Произошла ошибка при обработке сообщения: {str(e)}"
        )


def main():
    """Запуск бота"""
    global mcp_client
    
    logger.info("Starting bot...")
    
    # Создаём директорию для хранения разговоров
    ensure_conversations_dir()
    
    # Инициализируем MCP клиент
    mcp_client = MCPWeatherClient(MCP_WEATHER_SERVER_PATH)
    
    # Создаём приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("spec", spec_command))
    application.add_handler(CommandHandler("exit_spec", exit_spec_command))
    application.add_handler(CommandHandler("models", models_command))
    application.add_handler(CommandHandler("exit_models", exit_models_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CommandHandler("debug", debug_command))
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем MCP сервер при старте
    async def post_init(application):
        await mcp_client.start()
        logger.info("MCP Weather Client initialized")
    
    # Останавливаем MCP сервер при выключении
    async def post_stop(application):
        await mcp_client.stop()
        logger.info("MCP Weather Client stopped")
    
    application.post_init = post_init
    application.post_shutdown = post_stop
    
    # Запускаем бота
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
