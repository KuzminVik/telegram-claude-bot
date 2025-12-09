import os
import logging
import json
import re
import time
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

# Хранилище разговоров и режимов
conversations = {}  # {user_id: [messages]}
spec_mode = {}      # {user_id: bool} - режим сбора ТЗ
models_mode = {}    # {user_id: bool} - режим сравнения моделей

# Конфигурация моделей
MODELS_CONFIG = {
    'opus': 'claude-opus-4-20250514',
    'sonnet': 'claude-sonnet-4-5-20250929',
    'haiku': 'claude-haiku-4-5-20251001'
}

# Системные промпты
NORMAL_SYSTEM_PROMPT = """You are a helpful AI assistant. You must ALWAYS respond with ONLY a valid JSON object containing exactly two fields:
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


async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user_id = update.effective_user.id
    
    welcome_message = """👋 Привет! Я бот с интеграцией Claude AI.

📋 Доступные режимы работы:

🤖 **Обычный режим** (активен по умолчанию)
Просто напиши мне сообщение, и я отвечу.

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
/debug - показать последний JSON ответ"""
    
    await update.message.reply_text(welcome_message, parse_mode='Markdown')
    logger.info(f"User {user_id} started the bot")


async def spec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /spec - вход в режим сбора ТЗ"""
    user_id = update.effective_user.id
    spec_mode[user_id] = True
    models_mode[user_id] = False  # Выключаем режим models
    
    # Очищаем историю при входе в режим spec
    conversations[user_id] = []
    
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
    conversations[user_id] = []
    
    await update.message.reply_text("🗑️ История разговора очищена!")
    logger.info(f"User {user_id} cleared conversation history")


async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /debug - показать последний JSON"""
    user_id = update.effective_user.id
    
    if user_id not in conversations or not conversations[user_id]:
        await update.message.reply_text("Нет сообщений в истории.")
        return
    
    last_message = conversations[user_id][-1]
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
    
    # Инициализация хранилища для нового пользователя
    if user_id not in conversations:
        conversations[user_id] = []
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
    
    # Добавляем сообщение пользователя в историю
    conversations[user_id].append({
        "role": "user",
        "content": user_message
    })
    
    # Ограничиваем историю последними 30 сообщениями
    if len(conversations[user_id]) > 30:
        conversations[user_id] = conversations[user_id][-30:]
    
    try:
        if is_models_mode:
            # Режим сравнения моделей - запрашиваем все три модели
            await update.message.reply_text("🔄 Генерирую ответы от трёх моделей, подождите...")
            
            results = {}
            for model_key, model_name in MODELS_CONFIG.items():
                result = await get_claude_response_single(
                    model_name=model_name,
                    messages=conversations[user_id],
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
            conversations[user_id].append({
                "role": "assistant",
                "content": json.dumps({
                    "user_message": user_message,
                    "ai_message": "Multiple model responses provided"
                })
            })
            
        else:
            # Обычный режим или режим SPEC - одна модель
            response = client.messages.create(
                model=MODELS_CONFIG['sonnet'],  # Используем Sonnet по умолчанию
                max_tokens=2048,
                temperature=0.3,
                system=system_prompt,
                messages=conversations[user_id]
            )
            
            raw_response = response.content[0].text
            logger.info(f"Raw response: {raw_response[:200]}...")
            
            # Очищаем и парсим JSON
            cleaned_json = clean_json_response(raw_response)
            
            try:
                parsed_json = json.loads(cleaned_json)
                logger.info(f"✓ Successfully parsed JSON")
                
                # Добавляем ответ ассистента в историю
                conversations[user_id].append({
                    "role": "assistant",
                    "content": cleaned_json
                })
                
                # Отправляем ответ пользователю
                ai_message = parsed_json.get('ai_message', '')
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
                logger.error(f"Cleaned JSON: {cleaned_json}")
                
                # В случае ошибки парсинга отправляем сырой ответ
                await update.message.reply_text(
                    f"⚠️ Получен некорректный формат ответа:\n\n{raw_response}"
                )
                
                # Добавляем сырой ответ в историю
                conversations[user_id].append({
                    "role": "assistant",
                    "content": raw_response
                })
    
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}", exc_info=True)
        await update.message.reply_text(
            f"Произошла ошибка при обработке сообщения: {str(e)}"
        )


def main():
    """Запуск бота"""
    logger.info("Starting bot...")
    
    # Создаём приложение
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрируем обработчики команд
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("spec", spec_command))
    application.add_handler(CommandHandler("exit_spec", exit_spec_command))
    application.add_handler(CommandHandler("models", models_command))
    application.add_handler(CommandHandler("exit_models", exit_models_command))
    application.add_handler(CommandHandler("clear", clear_command))
    application.add_handler(CommandHandler("debug", debug_command))
    
    # Регистрируем обработчик текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Запускаем бота
    logger.info("Bot is running...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == '__main__':
    main()
