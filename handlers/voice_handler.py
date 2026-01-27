"""
Handler для голосовых сообщений - транскрипция через faster-whisper
"""

import logging
import os
import tempfile
from telegram import Update
from telegram.ext import ContextTypes
from faster_whisper import WhisperModel

logger = logging.getLogger(__name__)

# Инициализация модели
whisper_model = None

def init_whisper():
    """Инициализировать Whisper модель"""
    global whisper_model
    try:
        logger.info("Загрузка Whisper модели...")
        whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")
        logger.info("✓ Whisper модель загружена")
        return True
    except Exception as e:
        logger.error(f"Ошибка загрузки Whisper: {e}")
        return False


async def transcribe_audio(audio_path: str) -> dict:
    """Транскрибировать аудио файл"""
    global whisper_model
    
    if whisper_model is None:
        return {"success": False, "text": None, "error": "Whisper модель не загружена"}
    
    try:
        segments, info = whisper_model.transcribe(
            audio_path,
            language="ru",
            beam_size=5,
            vad_filter=True
        )
        
        text = " ".join([segment.text for segment in segments]).strip()
        
        if not text:
            return {"success": False, "text": None, "error": "Не удалось распознать речь"}
        
        return {"success": True, "text": text, "error": None}
        
    except Exception as e:
        logger.error(f"Ошибка транскрипции: {e}")
        return {"success": False, "text": None, "error": str(e)}


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик голосовых сообщений"""
    
    user_id = update.effective_user.id
    voice = update.message.voice
    
    if whisper_model is None:
        await update.message.reply_text("❌ Голосовой ввод недоступен")
        return
    
    status_msg = await update.message.reply_text("🎤 Распознаю речь...")
    
    try:
        # Скачать голосовое
        voice_file = await context.bot.get_file(voice.file_id)
        
        with tempfile.NamedTemporaryFile(suffix=".ogg", delete=False) as tmp_ogg:
            ogg_path = tmp_ogg.name
            await voice_file.download_to_drive(ogg_path)
        
        # Конвертировать OGG → WAV
        wav_path = ogg_path.replace(".ogg", ".wav")
        os.system(f"ffmpeg -i {ogg_path} -ar 16000 -ac 1 -y {wav_path} 2>/dev/null")
        
        # Транскрипция
        result = await transcribe_audio(wav_path)
        
        # Удалить временные файлы
        os.remove(ogg_path)
        os.remove(wav_path)
        
        if not result["success"]:
            await status_msg.edit_text(f"❌ {result['error']}")
            return
        
        recognized_text = result["text"]
        
        # Удалить статус
        try:
            await status_msg.delete()
        except:
            pass
        
        # Показать распознанный текст
        await update.message.reply_text(
            f"🎤 **Вы сказали:**\n_{recognized_text}_",
            parse_mode='Markdown'
        )
        
        # Теперь обработать через LLM
        from handlers.local_mode import get_user_mode
        current_mode = get_user_mode(user_id)
        
        if current_mode == "local":
            # Local LLM
            from mcp_clients import ollama_local_chat_client
            from handlers.local_mode import load_local_history, save_local_history
            
            if ollama_local_chat_client is None:
                await update.message.reply_text("❌ Локальная LLM недоступна")
                return
            
            local_history = load_local_history(user_id)
            messages = local_history.get("messages", [])
            
            # Добавить распознанное сообщение
            messages.append({"role": "user", "content": recognized_text})
            
            if len(messages) > 20:
                messages = messages[-20:]
            
            # Запрос к Ollama
            response = await ollama_local_chat_client.chat(
                messages=messages,
                temperature=0.7,
                max_tokens=1024
            )
            
            # Сохранить
            messages.append({"role": "assistant", "content": response})
            save_local_history(user_id, {"messages": messages, "message_count": len(messages)})
            
            await update.message.reply_text(response)
            
        else:
            # Claude режим
            import anthropic
            from utils.conversation_manager import get_conversation_history, save_conversation_history, compress_history_if_needed
            from config import ANTHROPIC_API_KEY
            
            conversation_history = get_conversation_history(user_id)
            conversation_history.append({"role": "user", "content": recognized_text})
            conversation_history = compress_history_if_needed(conversation_history, user_id)
            
            # Запрос к Claude
            client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=4096,
                temperature=0.3,
                messages=conversation_history
            )
            
            assistant_response = message.content[0].text
            conversation_history.append({"role": "assistant", "content": assistant_response})
            save_conversation_history(user_id, conversation_history)
            
            await update.message.reply_text(assistant_response)
        
    except Exception as e:
        logger.error(f"Ошибка обработки голоса: {e}", exc_info=True)
        try:
            await status_msg.delete()
        except:
            pass
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
