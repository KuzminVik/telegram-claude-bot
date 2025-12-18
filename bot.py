#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import json
import logging
import asyncio
from pathlib import Path
from datetime import datetime, timedelta
import random
import re

from telegram import Update, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)

from anthropic import Anthropic
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получение токенов из переменных окружения
TELEGRAM_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
ANTHROPIC_API_KEY = os.getenv('ANTHROPIC_API_KEY')

if not TELEGRAM_TOKEN or not ANTHROPIC_API_KEY:
    raise ValueError("TELEGRAM_BOT_TOKEN и ANTHROPIC_API_KEY должны быть установлены")

# Инициализация клиента Anthropic
anthropic_client = Anthropic(api_key=ANTHROPIC_API_KEY)

# Константы для хранения истории
CONVERSATIONS_DIR = Path("/root/telegram-bot/conversations")
MAX_HISTORY_LENGTH = 30
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 МБ
COMPRESSION_THRESHOLD = 10

# Пути к файлам погоды
WEATHER_SUBS_FILE = Path("/root/telegram-bot/weather_subscriptions.json")
WEATHER_HISTORY_FILE = Path("/root/telegram-bot/weather_history.json")

# Путь к MCP Weather Server
MCP_WEATHER_SERVER_PATH = "/home/claude/mcp-weather-server/server.js"

# Глобальные переменные
user_modes = {}  # user_id -> "normal" | "spec" | "models"
mcp_weather_client = None
scheduler = None
bot_instance = None  # Для доступа к боту из scheduled задач

# Системный промпт для сжатия истории
COMPRESSION_SYSTEM_PROMPT = """You are a helpful assistant that creates concise summaries of conversation history.
Your task is to create a brief summary of the conversation provided. The summary should:
1. Capture the key topics discussed
2. Preserve important facts, decisions, or conclusions
3. Be concise but informative (2-4 sentences)
4. Be written in the same language as the conversation

Respond with ONLY a valid JSON object in this format:
{"summary": "your summary text here"}

Do not include any markdown formatting, code blocks, or additional text."""

# =============================================================================
# MCP Weather Client
# =============================================================================

class MCPWeatherClient:
    """Клиент для взаимодействия с MCP Weather Server"""
    
    def __init__(self, server_path: str):
        self.server_path = server_path
        self.process = None
        self.lock = asyncio.Lock()  # Для синхронизации запросов
        
    async def start(self):
        """Запустить MCP сервер"""
        try:
            self.process = await asyncio.create_subprocess_exec(
                'node', self.server_path,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # Читаем первую строку из stderr (приветствие сервера)
            if self.process.stderr:
                greeting = await self.process.stderr.readline()
                logger.info(f"MCP Server: {greeting.decode().strip()}")
            
            logger.info("✓ MCP Weather Server started")
            return True
        except Exception as e:
            logger.error(f"Failed to start MCP Weather Server: {e}")
            return False
    
    async def stop(self):
        """Остановить MCP сервер"""
        if self.process:
            try:
                self.process.terminate()
                await asyncio.wait_for(self.process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                self.process.kill()
                await self.process.wait()
            logger.info("✓ MCP Weather Server stopped")
    
    async def call_tool(self, tool_name: str, arguments: dict) -> dict:
        """Вызвать инструмент MCP сервера"""
        if not self.process:
            logger.error("MCP Weather Server is not running")
            return None
        
        async with self.lock:  # Только один запрос одновременно
            try:
                request = {
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": tool_name,
                        "arguments": arguments
                    },
                    "id": 1
                }
                
                request_json = json.dumps(request) + '\n'
                logger.info(f"Sending to MCP: {request_json.strip()}")
                
                # Отправляем запрос
                self.process.stdin.write(request_json.encode())
                await self.process.stdin.drain()
                
                # Читаем ответ (с таймаутом)
                response_line = await asyncio.wait_for(
                    self.process.stdout.readline(),
                    timeout=10.0
                )
                
                response_text = response_line.decode().strip()
                logger.info(f"Received from MCP: {response_text[:200]}...")
                
                response = json.loads(response_text)
                
                if 'result' in response:
                    # Извлекаем данные из result.content[0].text
                    content = response['result']['content'][0]['text']
                    return json.loads(content)
                elif 'error' in response:
                    logger.error(f"MCP tool call error: {response['error']}")
                    return None
                else:
                    logger.error(f"Unexpected MCP response format: {response}")
                    return None
                    
            except asyncio.TimeoutError:
                logger.error("MCP tool call timeout")
                return None
            except Exception as e:
                logger.error(f"Error calling MCP tool: {e}")
                return None

# =============================================================================
# Функции для работы с файлами истории разговоров
# =============================================================================

def ensure_conversations_dir():
    """Создать директорию для хранения историй если её нет"""
    CONVERSATIONS_DIR.mkdir(parents=True, exist_ok=True)
    logger.info(f"Conversations directory ensured: {CONVERSATIONS_DIR}")

def get_conversation_filepath(user_id: int) -> Path:
    """Получить путь к файлу истории для пользователя"""
    return CONVERSATIONS_DIR / f"user_{user_id}.json"

def load_conversation(user_id: int) -> list:
    """
    Загрузить историю разговора из файла
    Возвращает список сообщений или пустой список
    """
    filepath = get_conversation_filepath(user_id)
    
    if not filepath.exists():
        logger.info(f"No conversation file for user {user_id}")
        return []
    
    try:
        # Проверка размера файла
        file_size = filepath.stat().st_size
        if file_size > MAX_FILE_SIZE:
            logger.warning(f"Conversation file too large for user {user_id}: {file_size} bytes")
            # Загружаем и обрезаем до последних MAX_HISTORY_LENGTH сообщений
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                messages = data.get('messages', [])
                if len(messages) > MAX_HISTORY_LENGTH:
                    messages = messages[-MAX_HISTORY_LENGTH:]
                    # Сохраняем обрезанную версию
                    save_conversation(user_id, messages)
                return messages
        
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            messages = data.get('messages', [])
            logger.info(f"Loaded {len(messages)} messages for user {user_id}")
            return messages
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in conversation file for user {user_id}: {e}")
        # Создаём backup повреждённого файла
        backup_path = filepath.with_suffix('.json.backup')
        filepath.rename(backup_path)
        logger.info(f"Created backup: {backup_path}")
        return []
    except Exception as e:
        logger.error(f"Error loading conversation for user {user_id}: {e}")
        return []

def save_conversation(user_id: int, messages: list) -> bool:
    """
    Сохранить историю разговора в файл
    Автоматически ограничивает количество сообщений до MAX_HISTORY_LENGTH
    """
    filepath = get_conversation_filepath(user_id)
    
    try:
        # Ограничиваем количество сообщений
        if len(messages) > MAX_HISTORY_LENGTH:
            messages = messages[-MAX_HISTORY_LENGTH:]
        
        data = {
            "user_id": user_id,
            "last_updated": datetime.now().isoformat(),
            "message_count": len(messages),
            "messages": messages
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        file_size = filepath.stat().st_size
        logger.info(f"Saved {len(messages)} messages for user {user_id} ({file_size} bytes)")
        return True
        
    except Exception as e:
        logger.error(f"Error saving conversation for user {user_id}: {e}")
        return False

def delete_conversation(user_id: int) -> bool:
    """Удалить файл истории пользователя"""
    filepath = get_conversation_filepath(user_id)
    
    try:
        if filepath.exists():
            filepath.unlink()
            logger.info(f"Deleted conversation file for user {user_id}")
            return True
        return False
    except Exception as e:
        logger.error(f"Error deleting conversation for user {user_id}: {e}")
        return False

def get_conversation_stats(user_id: int) -> dict:
    """Получить статистику по файлу истории"""
    filepath = get_conversation_filepath(user_id)
    
    if not filepath.exists():
        return {
            "exists": False,
            "message_count": 0,
            "file_size": 0,
            "file_size_mb": 0
        }
    
    try:
        file_size = filepath.stat().st_size
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            message_count = data.get('message_count', 0)
        
        return {
            "exists": True,
            "message_count": message_count,
            "file_size": file_size,
            "file_size_mb": round(file_size / (1024 * 1024), 2)
        }
    except Exception as e:
        logger.error(f"Error getting stats for user {user_id}: {e}")
        return {
            "exists": True,
            "message_count": 0,
            "file_size": 0,
            "file_size_mb": 0
        }

# =============================================================================
# Функции для работы с подписками на погоду
# =============================================================================

def load_weather_subscriptions() -> dict:
    """Загрузить подписки на погоду"""
    try:
        if WEATHER_SUBS_FILE.exists():
            with open(WEATHER_SUBS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading weather subscriptions: {e}")
        return {}

def save_weather_subscriptions(subs: dict) -> bool:
    """Сохранить подписки на погоду"""
    try:
        with open(WEATHER_SUBS_FILE, 'w', encoding='utf-8') as f:
            json.dump(subs, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved {len(subs)} weather subscription(s)")
        return True
    except Exception as e:
        logger.error(f"Error saving weather subscriptions: {e}")
        return False

def load_weather_history() -> dict:
    """Загрузить историю погоды (только вчерашние данные)"""
    try:
        if WEATHER_HISTORY_FILE.exists():
            with open(WEATHER_HISTORY_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Error loading weather history: {e}")
        return {}

def save_weather_history(history: dict) -> bool:
    """Сохранить историю погоды"""
    try:
        with open(WEATHER_HISTORY_FILE, 'w', encoding='utf-8') as f:
            json.dump(history, f, ensure_ascii=False, indent=2)
        logger.info(f"Saved weather history for {len(history)} user(s)")
        return True
    except Exception as e:
        logger.error(f"Error saving weather history: {e}")
        return False

def simulate_yesterday_weather(current_weather: dict) -> dict:
    """
    Создать симулированные вчерашние данные на основе текущей погоды
    Модифицируем температуру ±2-4°C
    """
    try:
        # Парсим текущую погоду из строки
        lines = current_weather.get('weather_info', '').split('\n')
        
        # Извлекаем температуру (примерный парсинг)
        temp = None
        feels_like = None
        condition = "Неизвестно"
        humidity = 70
        wind_speed = 10
        
        for line in lines:
            if 'Температура:' in line:
                # Извлекаем число из строки типа "🌡️ Температура: -5°C"
                match = re.search(r'(-?\d+\.?\d*)°C', line)
                if match:
                    temp = float(match.group(1))
            elif 'ощущается как' in line:
                match = re.search(r'(-?\d+\.?\d*)°C', line)
                if match:
                    feels_like = float(match.group(1))
            elif 'Состояние:' in line or 'Условия:' in line:
                condition = line.split(':')[1].strip()
            elif 'Влажность:' in line:
                match = re.search(r'(\d+)%', line)
                if match:
                    humidity = int(match.group(1))
            elif 'Ветер:' in line:
                match = re.search(r'(\d+)', line)
                if match:
                    wind_speed = int(match.group(1))
        
        # Если не удалось извлечь, берём дефолтные значения
        if temp is None:
            temp = random.randint(-10, 5)
        if feels_like is None:
            feels_like = temp - 3
        
        # Модифицируем для "вчера"
        temp_delta = random.randint(2, 4) * random.choice([-1, 1])
        yesterday_temp = temp + temp_delta
        yesterday_feels = feels_like + temp_delta
        
        # Используем прогноз если есть, иначе генерируем
        if 'forecast' in current_weather:
            forecast = current_weather['forecast']
            temp_max = forecast.get('temp_max', yesterday_temp + random.randint(3, 5))
            temp_min = forecast.get('temp_min', yesterday_temp - random.randint(3, 5))
            precipitation = forecast.get('precipitation_probability', random.randint(10, 30))
        else:
            temp_max = yesterday_temp + random.randint(3, 5)
            temp_min = yesterday_temp - random.randint(3, 5)
            precipitation = random.randint(10, 30)
        
        yesterday_data = {
            "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "city": current_weather.get('city', 'Unknown'),
            "current": {
                "temp": round(yesterday_temp, 1),
                "feels_like": round(yesterday_feels, 1),
                "condition": condition,
                "humidity": max(0, min(100, humidity + random.randint(-10, 10))),
                "wind_speed": max(0, wind_speed + random.randint(-3, 3))
            },
            "forecast": {
                "temp_max": round(temp_max, 1),
                "temp_min": round(temp_min, 1),
                "precipitation_probability": max(0, min(100, precipitation + random.randint(-10, 10)))
            }
        }
        
        logger.info(f"Simulated yesterday weather: {yesterday_data}")
        return yesterday_data
        
    except Exception as e:
        logger.error(f"Error simulating yesterday weather: {e}")
        # Возвращаем дефолтные данные
        return {
            "date": (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"),
            "city": current_weather.get('city', 'Unknown'),
            "current": {
                "temp": random.randint(-10, 5),
                "feels_like": random.randint(-15, 0),
                "condition": "Облачно",
                "humidity": 70,
                "wind_speed": 10
            },
            "forecast": {
                "temp_max": random.randint(0, 5),
                "temp_min": random.randint(-15, -5),
                "precipitation_probability": 30
            }
        }

# =============================================================================
# Функции утренней рассылки погоды
# =============================================================================

async def generate_comparison_summary(yesterday_data: dict, today_data: dict, city: str) -> str:
    """
    Генерация саммари сравнения погоды через Claude
    """
    try:
        comparison_prompt = f"""Сравни погоду в городе {city} между вчера и сегодня.

ВЧЕРА ({yesterday_data['date']}):
- Текущая температура: {yesterday_data['current']['temp']}°C
- Прогноз: макс {yesterday_data['forecast']['temp_max']}°C, мин {yesterday_data['forecast']['temp_min']}°C
- Вероятность осадков: {yesterday_data['forecast']['precipitation_probability']}%

СЕГОДНЯ:
- Текущая температура: {today_data['current']['temp']}°C
- Прогноз: макс {today_data['forecast']['temp_max']}°C, мин {today_data['forecast']['temp_min']}°C
- Вероятность осадков: {today_data['forecast']['precipitation_probability']}%

Создай КРАТКОЕ (2-3 предложения) саммари изменений на русском языке. Укажи:
1. Как изменилась текущая температура
2. Как изменился прогноз (теплее/холоднее, больше/меньше осадков)

Ответь ТОЛЬКО саммари, без лишнего текста."""

        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            messages=[
                {"role": "user", "content": comparison_prompt}
            ]
        )
        
        summary = response.content[0].text.strip()
        logger.info(f"Generated comparison summary: {summary}")
        return summary
        
    except Exception as e:
        logger.error(f"Error generating comparison summary: {e}")
        # Fallback - простое сравнение
        temp_diff = round(today_data['current']['temp'] - yesterday_data['current']['temp'], 1)
        if temp_diff > 0:
            return f"Потеплело на {temp_diff}°C по сравнению со вчера."
        elif temp_diff < 0:
            return f"Похолодало на {abs(temp_diff)}°C по сравнению со вчера."
        else:
            return "Температура примерно такая же как вчера."

async def send_morning_weather():
    """
    Утренняя рассылка погоды всем подписчикам
    Вызывается по расписанию
    """
    logger.info("🌅 Starting morning weather broadcast")
    
    if not bot_instance or not mcp_weather_client:
        logger.error("Bot or MCP client not initialized")
        return
    
    # Загружаем подписки
    subs = load_weather_subscriptions()
    if not subs:
        logger.info("No weather subscriptions")
        return
    
    # Загружаем историю
    history = load_weather_history()
    
    for user_id_str, sub_data in subs.items():
        try:
            user_id = int(user_id_str)
            city = sub_data['city']
            
            logger.info(f"Sending morning weather to user {user_id} for {city}")
            
            # Получаем текущую погоду + прогноз через MCP
            result = await mcp_weather_client.call_tool(
                "get_weather",
                {"city": city, "include_forecast": True}
            )
            
            if not result or 'weather_info' not in result:
                logger.error(f"Failed to get weather for {city}")
                await bot_instance.send_message(
                    chat_id=user_id,
                    text=f"❌ Не удалось получить погоду для города {city}"
                )
                continue
            
            # Парсим текущую погоду
            weather_lines = result['weather_info'].split('\n')
            current_temp = None
            for line in weather_lines:
                if 'Температура:' in line:
                    match = re.search(r'(-?\d+\.?\d*)°C', line)
                    if match:
                        current_temp = float(match.group(1))
                        break
            
            # Формируем данные сегодняшнего дня
            today_data = {
                "date": datetime.now().strftime("%Y-%m-%d"),
                "city": city,
                "current": {
                    "temp": current_temp or 0,
                },
                "forecast": result.get('forecast', {})
            }
            
            # Формируем сообщение
            message = f"🌅 Доброе утро! Погода в городе {city}:\n\n"
            message += result['weather_info'] + "\n\n"
            
            # Добавляем прогноз на день если есть
            if 'forecast' in result:
                fc = result['forecast']
                message += f"📊 Прогноз на день:\n"
                message += f"🔺 Макс: {fc['temp_max']}°C\n"
                message += f"🔻 Мин: {fc['temp_min']}°C\n"
                message += f"💧 Осадки: {fc['precipitation_probability']}%\n"
                message += f"☀️ Восход: {fc['sunrise'][11:16]}, закат: {fc['sunset'][11:16]}\n\n"
            
            # Добавляем сравнение с вчера если есть история
            if user_id_str in history:
                yesterday_data = history[user_id_str]
                logger.info(f"Generating comparison for user {user_id}")
                
                comparison = await generate_comparison_summary(yesterday_data, today_data, city)
                message += f"📈 Изменения:\n{comparison}"
            else:
                message += "📊 Первое утреннее сообщение (нет данных за вчера для сравнения)"
            
            # Отправляем сообщение
            await bot_instance.send_message(chat_id=user_id, text=message)
            logger.info(f"✓ Sent morning weather to user {user_id}")
            
            # Обновляем историю - сегодняшние данные становятся вчерашними
            history[user_id_str] = today_data
            
        except Exception as e:
            logger.error(f"Error sending morning weather to user {user_id_str}: {e}")
    
    # Сохраняем обновлённую историю
    save_weather_history(history)
    logger.info("🌅 Morning weather broadcast completed")

# =============================================================================
# Вспомогательные функции
# =============================================================================

def serialize_message_content(content):
    """
    Сериализует содержимое сообщения для сохранения в JSON.
    Обрабатывает специальные типы из библиотеки Anthropic.
    """
    if isinstance(content, str):
        return content
    elif isinstance(content, list):
        result = []
        for item in content:
            if hasattr(item, 'model_dump'):
                result.append(item.model_dump())
            elif isinstance(item, dict):
                result.append(item)
            else:
                result.append(str(item))
        return result
    elif hasattr(content, 'model_dump'):
        return content.model_dump()
    elif isinstance(content, dict):
        return content
    else:
        return str(content)

def clean_json_response(text: str) -> str:
    """Очистить JSON ответ от markdown блоков кода"""
    text = text.strip()
    if text.startswith('```json'):
        text = text[7:]
    elif text.startswith('```'):
        text = text[3:]
    if text.endswith('```'):
        text = text[:-3]
    return text.strip()

async def compress_conversation(user_id: int) -> bool:
    """
    Сжать историю разговора, создав краткое саммари последних сообщений
    и заменив их одним сообщением
    """
    try:
        messages = load_conversation(user_id)
        
        if len(messages) < COMPRESSION_THRESHOLD:
            return False
        
        # Берём последние COMPRESSION_THRESHOLD сообщений для сжатия
        messages_to_compress = messages[-COMPRESSION_THRESHOLD:]
        
        logger.info(f"Compressing {len(messages_to_compress)} messages for user {user_id}")
        
        # Формируем контекст для сжатия
        conversation_text = ""
        for msg in messages_to_compress:
            role = msg.get('role', 'unknown')
            content = msg.get('content', '')
            
            # Если content это JSON строка, пытаемся её распарсить
            if isinstance(content, str) and content.startswith('{'):
                try:
                    parsed = json.loads(content)
                    if 'user_message' in parsed and 'ai_message' in parsed:
                        conversation_text += f"User: {parsed['user_message']}\n"
                        conversation_text += f"Assistant: {parsed['ai_message']}\n\n"
                    else:
                        conversation_text += f"{role}: {content}\n\n"
                except:
                    conversation_text += f"{role}: {content}\n\n"
            else:
                conversation_text += f"{role}: {content}\n\n"
        
        # Запрос к Claude для создания саммари
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=500,
            system=COMPRESSION_SYSTEM_PROMPT,
            messages=[
                {
                    "role": "user",
                    "content": f"Create a summary of this conversation:\n\n{conversation_text}"
                }
            ]
        )
        
        summary_text = response.content[0].text
        summary_json = json.loads(clean_json_response(summary_text))
        summary = summary_json.get('summary', 'Summary of recent conversation')
        
        # Заменяем последние COMPRESSION_THRESHOLD сообщений одним сжатым
        compressed_message = {
            "role": "user",
            "content": f"📦 Сжатая история ({COMPRESSION_THRESHOLD} сообщений): {summary}"
        }
        
        # Обновляем историю: оставляем всё до последних COMPRESSION_THRESHOLD и добавляем сжатое
        new_messages = messages[:-COMPRESSION_THRESHOLD] + [compressed_message]
        
        # Сохраняем обновлённую историю
        if save_conversation(user_id, new_messages):
            logger.info(f"✓ Successfully compressed and saved conversation for user {user_id}")
            logger.info(f"Summary: {summary}")
            return True
        else:
            logger.error(f"Failed to save compressed conversation for user {user_id}")
            return False
        
    except Exception as e:
        logger.error(f"Error compressing conversation for user {user_id}: {e}")
        return False

async def send_long_message(update: Update, text: str):
    """Отправить длинное сообщение, разбив его на части если нужно"""
    max_length = 4000
    
    if len(text) <= max_length:
        await update.message.reply_text(text)
        return
    
    # Разбиваем на части
    parts = []
    while text:
        if len(text) <= max_length:
            parts.append(text)
            break
        
        # Ищем последний перенос строки в пределах max_length
        split_pos = text.rfind('\n', 0, max_length)
        if split_pos == -1:
            split_pos = max_length
        
        parts.append(text[:split_pos])
        text = text[split_pos:].lstrip()
    
    # Отправляем части
    for i, part in enumerate(parts, 1):
        if len(parts) > 1:
            await update.message.reply_text(f"[Часть {i}/{len(parts)}]\n\n{part}")
        else:
            await update.message.reply_text(part)

# =============================================================================
# Обработчики команд
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    await update.message.reply_text(
        "👋 Привет! Я бот с интеграцией Claude AI.\n\n"
        "🎯 Доступные режимы:\n"
        "• Обычный режим - просто пишите мне вопросы\n"
        "• /spec - режим сбора технического задания\n"
        "• /models - сравнение трёх моделей Claude\n\n"
        "🌤️ Погода:\n"
        "• /weather_subscribe Город - подписаться на утреннюю погоду\n"
        "• /weather_unsubscribe - отписаться от погоды\n"
        "• /weather_list - показать подписку\n\n"
        "📊 Управление:\n"
        "• /clear - очистить историю\n"
        "• /stats - показать статистику\n"
        "• /debug - показать последнее сообщение"
    )

async def spec_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Войти в режим сбора технического задания"""
    user_id = update.effective_user.id
    user_modes[user_id] = "spec"
    
    # Очищаем историю при входе в режим spec
    delete_conversation(user_id)
    
    logger.info(f"User {user_id} entered spec mode")
    
    await update.message.reply_text(
        "📋 Режим сбора ТЗ активирован!\n\n"
        "Я задам вам несколько вопросов о вашем проекте мобильного приложения, "
        "после чего сформирую полное техническое задание.\n\n"
        "Для выхода из режима используйте /exit_spec"
    )
    
    # Отправляем первое сообщение от Claude
    try:
        messages = []
        system_prompt = (
            "Ты - опытный бизнес-аналитик, который помогает собрать требования для мобильного приложения. "
            "Твоя задача - задавать уточняющие вопросы один за другим, чтобы собрать полную информацию. "
            "После 8-12 обменов сообщениями, когда будет собрана достаточная информация, "
            "создай подробное техническое задание в формате JSON с полями: "
            "название_проекта, описание, целевая_аудитория, основные_функции, технические_требования, дизайн, сроки. "
            "Начни с приветствия и первого вопроса о проекте."
        )
        
        response = anthropic_client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1000,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": "Привет! Я хочу создать мобильное приложение."
                }
            ]
        )
        
        ai_response = response.content[0].text
        
        # Сохраняем в историю
        messages.append({
            "role": "user",
            "content": "Привет! Я хочу создать мобильное приложение."
        })
        messages.append({
            "role": "assistant",
            "content": json.dumps({
                "user_message": "Привет! Я хочу создать мобильное приложение.",
                "ai_message": ai_response
            }, ensure_ascii=False)
        })
        save_conversation(user_id, messages)
        
        await update.message.reply_text(ai_response)
        
    except Exception as e:
        logger.error(f"Error in spec_mode: {e}")
        await update.message.reply_text(f"Ошибка: {str(e)}")

async def exit_spec_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из режима сбора ТЗ"""
    user_id = update.effective_user.id
    
    if user_id in user_modes and user_modes[user_id] == "spec":
        user_modes[user_id] = "normal"
        logger.info(f"User {user_id} exited spec mode")
        await update.message.reply_text("✅ Вы вышли из режима сбора ТЗ")
    else:
        await update.message.reply_text("❌ Вы не находитесь в режиме сбора ТЗ")

async def models_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Войти в режим сравнения моделей"""
    user_id = update.effective_user.id
    user_modes[user_id] = "models"
    
    logger.info(f"User {user_id} entered models mode")
    
    await update.message.reply_text(
        "🔄 Режим сравнения моделей активирован!\n\n"
        "Отправьте вопрос, и я покажу ответы от трёх разных моделей Claude:\n"
        "• Claude Opus 4\n"
        "• Claude Sonnet 4.5\n"
        "• Claude Haiku 4.5\n\n"
        "Для выхода используйте /exit_models"
    )

async def exit_models_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Выйти из режима сравнения моделей"""
    user_id = update.effective_user.id
    
    if user_id in user_modes and user_modes[user_id] == "models":
        user_modes[user_id] = "normal"
        logger.info(f"User {user_id} exited models mode")
        await update.message.reply_text("✅ Вы вышли из режима сравнения моделей")
    else:
        await update.message.reply_text("❌ Вы не находитесь в режиме сравнения моделей")

async def clear_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очистить историю разговора"""
    user_id = update.effective_user.id
    
    if delete_conversation(user_id):
        await update.message.reply_text("✅ История очищена")
    else:
        await update.message.reply_text("✅ История уже пуста")

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать статистику истории"""
    user_id = update.effective_user.id
    stats = get_conversation_stats(user_id)
    
    if not stats['exists']:
        await update.message.reply_text("📊 У вас пока нет истории разговоров")
        return
    
    await update.message.reply_text(
        f"📊 Статистика вашей истории:\n\n"
        f"💬 Сообщений: {stats['message_count']}\n"
        f"📦 Размер файла: {stats['file_size_mb']} МБ\n"
        f"📁 Максимальный размер: {MAX_FILE_SIZE // (1024*1024)} МБ\n"
        f"📝 Максимум сообщений: {MAX_HISTORY_LENGTH}"
    )

async def debug_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать последнее сообщение из истории для отладки"""
    user_id = update.effective_user.id
    messages = load_conversation(user_id)
    
    if not messages:
        await update.message.reply_text("История пуста")
        return
    
    last_message = messages[-1]
    debug_text = f"🐛 Последнее сообщение:\n\n```json\n{json.dumps(last_message, ensure_ascii=False, indent=2)}\n```"
    
    await update.message.reply_text(debug_text, parse_mode='Markdown')

async def weather_subscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Подписаться на утреннюю погоду"""
    user_id = update.effective_user.id
    
    logger.info(f"[DEBUG 1] weather_subscribe called for user {user_id}")
    
    if not context.args:
        logger.info("[DEBUG 2] No city provided")
        await update.message.reply_text("❌ Укажите город!\n\nИспользование: /weather_subscribe Москва")
        return
    
    city = ' '.join(context.args)
    logger.info(f"[DEBUG 3] City: {city}")
    
    try:
        await update.message.reply_text(f"⏳ Получаю погоду для города {city}...")
        logger.info("[DEBUG 4] Sent 'getting weather' message")
        
        logger.info(f"[DEBUG 5] mcp_weather_client exists: {mcp_weather_client is not None}")
        
        if not mcp_weather_client:
            logger.error("[DEBUG 6] mcp_weather_client is None!")
            await update.message.reply_text("❌ MCP Weather сервер недоступен")
            return
        
        logger.info(f"[DEBUG 7] Calling MCP tool for city: {city}")
        result = await mcp_weather_client.call_tool("get_weather", {"city": city, "include_forecast": True})
        logger.info(f"[DEBUG 8] MCP result: {result}")
        
        if not result:
            logger.error("[DEBUG 9] MCP returned None")
            await update.message.reply_text(f"❌ MCP вернул None для города {city}")
            return
        
        if 'weather_info' not in result:
            logger.error(f"[DEBUG 10] No weather_info in result: {result}")
            await update.message.reply_text(f"❌ Нет weather_info в результате")
            return
        
        logger.info("[DEBUG 11] Got weather_info, creating yesterday data")
        
        # Создаём симулированные вчерашние данные
        result['city'] = city  # Добавляем город в результат
        yesterday_data = simulate_yesterday_weather(result)
        
        logger.info("[DEBUG 12] Saving to history")
        
        # Сохраняем в историю
        history = load_weather_history()
        history[str(user_id)] = yesterday_data
        save_weather_history(history)
        
        logger.info("[DEBUG 13] Saving subscription")
        
        # Сохраняем подписку
        subs = load_weather_subscriptions()
        subs[str(user_id)] = {
            "city": city,
            "time": "08:00",
            "timezone": "Europe/Moscow"
        }
        save_weather_subscriptions(subs)
        
        logger.info("[DEBUG 14] Sending success message")
        
        await update.message.reply_text(
            f"✅ Подписка на утреннюю погоду активирована!\n\n"
            f"🌍 Город: {city}\n"
            f"⏰ Время: 08:00 (Europe/Moscow)\n\n"
            f"📊 Создана симулированная история за вчера для сравнения.\n"
            f"Завтра утром вы получите первое сообщение с прогнозом!"
        )
        
        logger.info(f"User {user_id} subscribed to weather for {city}")
        
    except Exception as e:
        logger.error(f"[DEBUG ERROR] Exception in weather_subscribe: {e}", exc_info=True)
        await update.message.reply_text(f"❌ Ошибка при создании подписки: {str(e)}")

async def weather_unsubscribe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отписаться от утренней погоды"""
    user_id = update.effective_user.id
    
    try:
        subs = load_weather_subscriptions()
        
        if str(user_id) not in subs:
            await update.message.reply_text("❌ У вас нет активной подписки на погоду")
            return
        
        city = subs[str(user_id)]['city']
        del subs[str(user_id)]
        save_weather_subscriptions(subs)
        
        # Удаляем и историю
        history = load_weather_history()
        if str(user_id) in history:
            del history[str(user_id)]
            save_weather_history(history)
        
        await update.message.reply_text(
            f"✅ Подписка на погоду для города {city} отменена"
        )
        
        logger.info(f"User {user_id} unsubscribed from weather")
        
    except Exception as e:
        logger.error(f"Error in weather_unsubscribe: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

async def weather_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать текущую подписку на погоду"""
    user_id = update.effective_user.id
    
    try:
        subs = load_weather_subscriptions()
        
        if str(user_id) not in subs:
            await update.message.reply_text(
                "❌ У вас нет активной подписки на погоду\n\n"
                "Используйте: /weather_subscribe Москва"
            )
            return
        
        sub = subs[str(user_id)]
        
        await update.message.reply_text(
            f"✅ Активная подписка:\n\n"
            f"🌍 Город: {sub['city']}\n"
            f"⏰ Время: {sub['time']}\n"
            f"🌐 Часовой пояс: {sub['timezone']}"
        )
        
    except Exception as e:
        logger.error(f"Error in weather_list: {e}")
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")

# =============================================================================
# Обработчик сообщений
# =============================================================================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработать входящее сообщение"""
    user_id = update.effective_user.id
    user_message = update.message.text
    
    logger.info(f"Received message from {user_id}: {user_message[:50]}...")
    
    # Определяем режим пользователя
    mode = user_modes.get(user_id, "normal")
    
    # Загружаем историю из файла
    messages = load_conversation(user_id)
    
    try:
        if mode == "spec":
            # Режим сбора ТЗ
            await handle_spec_mode(update, user_id, user_message, messages)
        elif mode == "models":
            # Режим сравнения моделей
            await handle_models_mode(update, user_id, user_message, messages)
        else:
            # Обычный режим
            await handle_normal_mode(update, user_id, user_message, messages)
            
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        await update.message.reply_text(f"Произошла ошибка: {str(e)}")

async def handle_normal_mode(update: Update, user_id: int, user_message: str, messages: list):
    """Обработка обычного режима с поддержкой MCP Weather"""
    
    # Добавляем сообщение пользователя
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    # Описание инструмента get_weather для Claude
    tools = [
        {
            "name": "get_weather",
            "description": "Get current weather information for a city. Use this when the user asks about weather, temperature, or atmospheric conditions in a specific location.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "city": {
                        "type": "string",
                        "description": "The name of the city to get weather for (in any language)"
                    }
                },
                "required": ["city"]
            }
        }
    ]
    
    # Первый запрос к Claude
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        tools=tools,
        messages=messages
    )
    
    # Проверяем, использовал ли Claude инструмент
    tool_use_block = None
    text_response = ""
    
    for block in response.content:
        if block.type == "tool_use":
            tool_use_block = block
        elif block.type == "text":
            text_response += block.text
    
    if tool_use_block:
        # Claude хочет использовать инструмент погоды
        logger.info(f"Claude wants to use tool: {tool_use_block.name} with args: {tool_use_block.input}")
        
        # Вызываем MCP Weather
        tool_result = await mcp_weather_client.call_tool(
            tool_use_block.name,
            tool_use_block.input
        )
        
        if tool_result:
            # Добавляем ответ Claude с tool_use в историю
            messages.append({
                "role": "assistant",
                "content": serialize_message_content(response.content)
            })
            
            # Добавляем результат инструмента
            messages.append({
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_block.id,
                        "content": json.dumps(tool_result, ensure_ascii=False)
                    }
                ]
            })
            
            # Второй запрос к Claude с результатами инструмента
            response = anthropic_client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2000,
                tools=tools,
                messages=messages
            )
            
            # Извлекаем финальный текстовый ответ
            final_response = ""
            for block in response.content:
                if block.type == "text":
                    final_response += block.text
            
            # Сохраняем финальный ответ
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "user_message": user_message,
                    "ai_message": final_response
                }, ensure_ascii=False)
            })
            
            ai_response = final_response
        else:
            # Ошибка при вызове инструмента
            ai_response = "Извините, не удалось получить данные о погоде."
            messages.append({
                "role": "assistant",
                "content": json.dumps({
                    "user_message": user_message,
                    "ai_message": ai_response
                }, ensure_ascii=False)
            })
    else:
        # Обычный ответ без инструментов
        ai_response = text_response
        
        messages.append({
            "role": "assistant",
            "content": json.dumps({
                "user_message": user_message,
                "ai_message": ai_response
            }, ensure_ascii=False)
        })
    
    # Сохраняем историю
    save_conversation(user_id, messages)
    
    # Отправляем ответ пользователю
    stats_text = f"\n\n📊 Токены: вопрос {response.usage.input_tokens} | ответ {response.usage.output_tokens}"
    await send_long_message(update, ai_response + stats_text)
    
    # Проверяем необходимость сжатия
    if len(messages) >= COMPRESSION_THRESHOLD:
        compressed = await compress_conversation(user_id)
        if compressed:
            await update.message.reply_text("📦 История сжата для экономии токенов")

async def handle_spec_mode(update: Update, user_id: int, user_message: str, messages: list):
    """Обработка режима сбора ТЗ"""
    
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    system_prompt = (
        "Ты - опытный бизнес-аналитик, который помогает собрать требования для мобильного приложения. "
        "Задавай уточняющие вопросы один за другим. "
        "После 8-12 обменов, когда информации достаточно, создай подробное ТЗ в JSON формате с полями: "
        "название_проекта, описание, целевая_аудитория, основные_функции, технические_требования, дизайн, сроки. "
        "ВАЖНО: Отвечай ТОЛЬКО в JSON формате: {\"user_message\": \"сообщение пользователя\", \"ai_message\": \"твой ответ\"}"
    )
    
    response = anthropic_client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=2000,
        system=system_prompt,
        messages=messages
    )
    
    ai_response = response.content[0].text
    
    # Парсим JSON ответ
    try:
        cleaned_response = clean_json_response(ai_response)
        response_json = json.loads(cleaned_response)
        actual_response = response_json.get('ai_message', ai_response)
    except:
        actual_response = ai_response
    
    messages.append({
        "role": "assistant",
        "content": ai_response
    })
    
    # Сохраняем без сжатия в режиме spec
    save_conversation(user_id, messages)
    
    await send_long_message(update, actual_response)
    
    # Проверяем, закончил ли Claude сбор ТЗ (если в ответе есть JSON с полями ТЗ)
    if all(key in ai_response for key in ['название_проекта', 'описание', 'целевая_аудитория']):
        user_modes[user_id] = "normal"
        await update.message.reply_text(
            "\n\n✅ Сбор ТЗ завершён! Вы автоматически вернулись в обычный режим."
        )

async def handle_models_mode(update: Update, user_id: int, user_message: str, messages: list):
    """Обработка режима сравнения моделей"""
    
    await update.message.reply_text("⏳ Опрашиваю три модели, это займёт некоторое время...")
    
    models = [
        ("Claude Opus 4", "claude-opus-4-20250514"),
        ("Claude Sonnet 4.5", "claude-sonnet-4-20250514"),
        ("Claude Haiku 4.5", "claude-haiku-4-20251001")
    ]
    
    messages.append({
        "role": "user",
        "content": user_message
    })
    
    responses_text = f"🔄 Сравнение моделей для вопроса:\n\"{user_message}\"\n\n"
    
    for model_name, model_id in models:
        try:
            import time
            start_time = time.time()
            
            response = anthropic_client.messages.create(
                model=model_id,
                max_tokens=1500,
                messages=messages
            )
            
            end_time = time.time()
            duration = round(end_time - start_time, 2)
            
            ai_response = response.content[0].text
            
            responses_text += f"━━━━━━━━━━━━━━━━━━━━\n"
            responses_text += f"🤖 {model_name}\n"
            responses_text += f"⏱️ Время: {duration}s\n"
            responses_text += f"📊 Токены: in={response.usage.input_tokens} | out={response.usage.output_tokens}\n\n"
            responses_text += f"{ai_response}\n\n"
            
        except Exception as e:
            responses_text += f"━━━━━━━━━━━━━━━━━━━━\n"
            responses_text += f"🤖 {model_name}\n"
            responses_text += f"❌ Ошибка: {str(e)}\n\n"
    
    # Сохраняем последний ответ (от Sonnet) в историю
    messages.append({
        "role": "assistant",
        "content": json.dumps({
            "user_message": user_message,
            "ai_message": responses_text
        }, ensure_ascii=False)
    })
    
    save_conversation(user_id, messages)
    
    await send_long_message(update, responses_text)

# =============================================================================
# Главная функция
# =============================================================================

def main():
    """Запуск бота"""
    global mcp_weather_client, scheduler, bot_instance
    
    # Создаём директорию для историй
    ensure_conversations_dir()
    
    # Создание приложения
    application = Application.builder().token(TELEGRAM_TOKEN).build()
    
    # Регистрация обработчиков команд
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("spec", spec_mode))
    application.add_handler(CommandHandler("exit_spec", exit_spec_mode))
    application.add_handler(CommandHandler("models", models_mode))
    application.add_handler(CommandHandler("exit_models", exit_models_mode))
    application.add_handler(CommandHandler("clear", clear_history))
    application.add_handler(CommandHandler("stats", show_stats))
    application.add_handler(CommandHandler("debug", debug_history))
    application.add_handler(CommandHandler("weather_subscribe", weather_subscribe))
    application.add_handler(CommandHandler("weather_unsubscribe", weather_unsubscribe))
    application.add_handler(CommandHandler("weather_list", weather_list))

    # Временная команда для теста утренней рассылки
    async def test_morning_weather(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """ТЕСТ: Запустить утреннюю рассылку прямо сейчас"""
        await update.message.reply_text("⏳ Запускаю утреннюю рассылку...")
        await send_morning_weather()
        await update.message.reply_text("✅ Рассылка завершена!")
    
    application.add_handler(CommandHandler("test_morning", test_morning_weather))
    
    # Регистрация обработчика текстовых сообщений
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Инициализация MCP и планировщика при старте приложения
    async def post_init(app):
        global mcp_weather_client, scheduler, bot_instance
        
        # Сохраняем экземпляр бота для использования в scheduled задачах
        bot_instance = app.bot
        
        # Запускаем MCP Weather Client
        logger.info("Starting MCP Weather Client...")
        mcp_weather_client = MCPWeatherClient(MCP_WEATHER_SERVER_PATH)
        if await mcp_weather_client.start():
            logger.info("✓ MCP Weather Client initialized")
        else:
            logger.error("✗ Failed to start MCP Weather Client")
        
        # Инициализация планировщика
        scheduler = AsyncIOScheduler()
        
        # Добавляем задачу утренней рассылки (каждый день в 8:00)
        scheduler.add_job(
            send_morning_weather,
            CronTrigger(hour=8, minute=0, timezone='Europe/Moscow'),
            id='morning_weather',
            name='Morning Weather Broadcast',
            replace_existing=True
        )
        
        scheduler.start()
        logger.info("✓ Weather scheduler started (morning broadcast at 08:00 Moscow time)")
    
    # Остановка при завершении
    async def post_shutdown(app):
        if mcp_weather_client:
            await mcp_weather_client.stop()
        if scheduler:
            scheduler.shutdown()
    
    application.post_init = post_init
    application.post_shutdown = post_shutdown
    
    logger.info("Bot is running...")
    
    # Запуск бота
    application.run_polling()

if __name__ == '__main__':
    main()