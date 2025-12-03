import os
import logging
import json
import re
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import anthropic

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))
conversations = {}
spec_mode = {}
NORMAL_SYSTEM_PROMPT = """You are a JSON-only API. You must ALWAYS respond with valid JSON and nothing else.

ABSOLUTE REQUIREMENTS:
1. ONLY output a JSON object - no other text
2. NO markdown code blocks (```json or ```)
3. NO explanations, greetings, or extra text
4. Your entire response must be valid JSON that can be parsed directly

OUTPUT FORMAT (copy this structure exactly):
{"user_message": "repeat user's exact message", "ai_message": "your response"}

EXAMPLES:
Input: "Привет"
Output: {"user_message": "Привет", "ai_message": "Привет! Чем могу помочь?"}

Input: "Как дела?"
Output: {"user_message": "Как дела?", "ai_message": "Отлично! А у тебя?"}

CRITICAL: Your response must start with { and end with }. Nothing before or after."""

SPEC_SYSTEM_PROMPT = """You are a professional business analyst specializing in mobile app development. Your task is to gather requirements for a technical specification through a conversational interview.

YOUR GOAL: Collect enough information to create a brief technical specification for a mobile application.

INTERVIEW STRUCTURE (from general to specific):
1. Target platform (iOS, Android, Cross-platform)
2. App purpose and business logic (What problem does it solve? Target audience?)
3. Core features and functionality (Main screens, user flows)
4. Data storage requirements (Local storage, cloud sync, offline mode)
5. User authentication (Login system needed?)
6. Integration needs (APIs, third-party services, payment systems)
7. Design preferences (Style, UI/UX requirements)
8. Technical constraints (Performance requirements, device compatibility)

INTERVIEW RULES:
- Ask ONE question at a time
- Start with broad questions, then dive deeper based on answers
- Ask clarifying questions when needed
- Be conversational and friendly
- Analyze accumulated information continuously
- Track what information you've collected internally
- When you have enough information (typically 8-12 exchanges), generate the final specification

OUTPUT FORMAT - ALWAYS SIMPLE JSON WITH ONLY 2 FIELDS:

For questions phase:
{
  "user_message": "repeat user's message",
  "ai_message": "your question or clarification"
}

For final specification (when you have enough information):
{
  "user_message": "repeat user's message",
  "ai_message": "Спасибо! Я собрал достаточно информации.\\n\\n📋 ТЕХНИЧЕСКОЕ ЗАДАНИЕ\\n\\n🎯 Проект: [название]\\n📱 Платформа: [платформа]\\n\\n📝 Описание:\\n[описание]\\n\\n👥 Целевая аудитория:\\n[аудитория]\\n\\n⚙️ Основные функции:\\n1. [функция 1]\\n2. [функция 2]\\n3. [функция 3]\\n\\n🔧 Технические требования:\\n• Хранение данных: [требования]\\n• Аутентификация: [требования]\\n• Оффлайн режим: [да/нет]\\n• Интеграции: [список]\\n\\n🎨 UI/UX:\\n[требования]\\n\\n⚠️ Ограничения:\\n[ограничения]"
}

IMPORTANT:
- In ai_message for final spec, format the entire technical specification as readable text
- Use emojis and formatting to make it clear and structured
- Keep the JSON structure simple - ONLY user_message and ai_message fields
- No additional fields like spec_complete, collected_info, or specification
- Track collected information in your memory, not in JSON output

DECISION CRITERIA for completion:
- You have clear understanding of app purpose
- Platform is defined
- At least 3-5 core features identified
- Data storage approach clarified
- You can write a meaningful specification

Start the interview by asking about the target platform.

CRITICAL: Always output valid JSON with ONLY user_message and ai_message. Your response must start with { and end with }."""
def clean_json_response(text: str) -> str:
    """Очистка ответа от markdown и лишнего текста"""
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    return text.strip()
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    spec_mode[user_id] = False
    await update.message.reply_text(
        "Привет! Я бот на базе Claude AI. 🤖\n\n"
        "Доступные режимы:\n\n"
        "📱 /spec - Начать сбор ТЗ на мобильное приложение\n"
        "💬 Обычный режим - просто напиши мне сообщение\n\n"
        "Другие команды:\n"
        "/clear - Очистить историю\n"
        "/debug - Показать последний JSON\n"
        "/exit_spec - Выйти из режима сбора ТЗ"
    )

async def spec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    spec_mode[user_id] = True
    conversations[user_id] = []
    
    await update.message.reply_text(
        "📱 Режим сбора ТЗ активирован!\n\n"
        "Я помогу вам составить техническое задание на разработку мобильного приложения.\n"
        "Буду задавать вопросы от общего к частному.\n\n"
        "Для выхода из режима используйте /exit_spec"
    )
    
    await ask_first_question(update, user_id)

async def ask_first_question(update: Update, user_id: int):
    """Задаем первый вопрос в режиме сбора ТЗ"""
    try:
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=SPEC_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": "Начни интервью. Задай первый вопрос о платформе."
            }],
            temperature=0.3
        )
        
        raw_response = response.content[0].text.strip()
        cleaned_response = clean_json_response(raw_response)
        
        conversations[user_id] = [{
            "role": "assistant",
            "content": cleaned_response
        }]
        
        try:
            parsed = json.loads(cleaned_response)
            ai_message = parsed.get("ai_message", cleaned_response)
            await update.message.reply_text(ai_message)
        except:
            await update.message.reply_text(cleaned_response)
            
    except Exception as e:
        logger.error(f"Error in first question: {e}")
        await update.message.reply_text("Ошибка при запуске режима сбора ТЗ")

async def exit_spec_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    spec_mode[user_id] = False
    await update.message.reply_text(
        "✅ Вышли из режима сбора ТЗ.\n"
        "Теперь я работаю в обычном режиме."
    )

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []
    spec_mode[user_id] = False
    await update.message.reply_text("История очищена! ✨")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in conversations and conversations[user_id]:
        last_response = conversations[user_id][-1].get("content", "Нет данных")
        try:
            parsed = json.loads(last_response)
            formatted = json.dumps(parsed, ensure_ascii=False, indent=2)
            await update.message.reply_text(f"```json\n{formatted}\n```", parse_mode="Markdown")
        except:
            await update.message.reply_text(f"Последний JSON:\n\n{last_response}")
    else:
        await update.message.reply_text("История пуста")
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
    is_spec_mode = spec_mode.get(user_id, False)
    system_prompt = SPEC_SYSTEM_PROMPT if is_spec_mode else NORMAL_SYSTEM_PROMPT
    
    if user_id not in conversations:
        conversations[user_id] = []
    
    conversations[user_id].append({
        "role": "user",
        "content": user_message
    })
    
    try:
        await update.message.chat.send_action("typing")
        
        response = client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=2048,
            system=system_prompt,
            messages=conversations[user_id],
            temperature=0.3
        )
        
        raw_response = response.content[0].text.strip()
        logger.info(f"Mode: {'SPEC' if is_spec_mode else 'NORMAL'}")
        logger.info(f"Raw response: {raw_response[:200]}...")
        
        cleaned_response = clean_json_response(raw_response)
        
        try:
            parsed_json = json.loads(cleaned_response)
            
            await update.message.reply_text(cleaned_response)
            
            if is_spec_mode:
                ai_message = parsed_json.get("ai_message", "")
                if "ТЕХНИЧЕСКОЕ ЗАДАНИЕ" in ai_message or "📋" in ai_message:
                    spec_mode[user_id] = False
                    logger.info("Spec collection completed, switching to normal mode")
            
            logger.info(f"✓ Successfully parsed JSON")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"Cleaned response was: {cleaned_response[:500]}")
            await update.message.reply_text(f"⚠️ Ошибка форматирования:\n\n{cleaned_response}")
        
        conversations[user_id].append({
            "role": "assistant",
            "content": cleaned_response
        })
        
        if len(conversations[user_id]) > 30:
            conversations[user_id] = conversations[user_id][-30:]
        
    except anthropic.APIError as e:
        logger.error(f"Anthropic API error: {e}")
        await update.message.reply_text(
            "Извините, произошла ошибка при обращении к Claude API."
        )
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        await update.message.reply_text("Произошла непредвиденная ошибка.")

def main():
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    
    if not token:
        raise ValueError("TELEGRAM_BOT_TOKEN не найден!")
    
    app = Application.builder().token(token).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("spec", spec_command))
    app.add_handler(CommandHandler("exit_spec", exit_spec_command))
    app.add_handler(CommandHandler("clear", clear_history))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен с поддержкой режима сбора ТЗ!")
    app.run_polling()

if __name__ == "__main__":
    main()
