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

SYSTEM_PROMPT = """You are a JSON-only API. You must ALWAYS respond with valid JSON and nothing else.

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

Input: "Расскажи о погоде"
Output: {"user_message": "Расскажи о погоде", "ai_message": "К сожалению, у меня нет доступа к актуальной информации о погоде. Попробуйте проверить прогноз на специализированных сайтах."}

CRITICAL: Your response must start with { and end with }. Nothing before or after."""

def clean_json_response(text: str) -> str:
    """Очистка ответа от markdown и лишнего текста"""
    # Удаляем markdown блоки кода
    text = re.sub(r'```json\s*', '', text)
    text = re.sub(r'```\s*', '', text)
    
    # Ищем JSON объект в тексте
    json_match = re.search(r'\{.*\}', text, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    return text.strip()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Привет! Я бот на базе Claude AI. 🤖\n\n"
        "Просто напиши мне сообщение, и я отвечу!\n\n"
        "Команды:\n"
        "/start - Начать заново\n"
        "/clear - Очистить историю\n"
        "/debug - Показать последний JSON ответ"
    )

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    conversations[user_id] = []
    await update.message.reply_text("История очищена! ✨")

async def debug_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in conversations and conversations[user_id]:
        last_response = conversations[user_id][-1].get("content", "Нет данных")
        await update.message.reply_text(f"Последний JSON:\n\n{last_response}")
    else:
        await update.message.reply_text("История пуста")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_message = update.message.text
    
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
            system=SYSTEM_PROMPT,
            messages=conversations[user_id],
            temperature=0.3  # Более строгое следование инструкциям
        )
        
        raw_response = response.content[0].text.strip()
        logger.info(f"Raw response: {raw_response}")
        
        # Очищаем от markdown и лишнего текста
        cleaned_response = clean_json_response(raw_response)
        logger.info(f"Cleaned response: {cleaned_response}")
        
        # Попытка распарсить JSON
        try:
            parsed_json = json.loads(cleaned_response)
            user_msg = parsed_json.get("user_message", "")
            ai_message = parsed_json.get("ai_message", "")
            
            if not ai_message:
                raise ValueError("ai_message is empty")
            
            logger.info(f"✓ Successfully parsed JSON")
            logger.info(f"  user_message: {user_msg}")
            logger.info(f"  ai_message: {ai_message}")
                
        except (json.JSONDecodeError, ValueError) as e:
            logger.error(f"❌ Failed to parse JSON: {e}")
            logger.error(f"Cleaned response was: {cleaned_response}")
            
            # Fallback: используем сырой ответ как ai_message
            ai_message = f"⚠️ Ошибка форматирования:\n\n{raw_response}"
        
        # Добавляем очищенный JSON ответ в историю
        conversations[user_id].append({
            "role": "assistant",
            "content": cleaned_response
        })
        
        if len(conversations[user_id]) > 20:
            conversations[user_id] = conversations[user_id][-20:]
        
        await update.message.reply_text(cleaned_response)
        
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
    app.add_handler(CommandHandler("clear", clear_history))
    app.add_handler(CommandHandler("debug", debug_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    logger.info("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
