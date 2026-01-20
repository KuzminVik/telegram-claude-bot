# /root/telegram-bot/mcp_clients/ollama_chat_client.py

import asyncio
import logging
import aiohttp
from config import (
    MCP_OLLAMA_SSH_HOST,
    MCP_OLLAMA_SSH_PORT,
    MCP_OLLAMA_SSH_USER,
    MCP_OLLAMA_SSH_KEY
)

logger = logging.getLogger(__name__)

class OllamaLocalChatClient:
    """Client for chatting with local Ollama LLM via SSH tunnel"""
    
    def __init__(self):
        self.ssh_process = None
        self.local_port = 11435  # Локальный порт для туннеля
        self.ollama_url = f"http://localhost:{self.local_port}"
        self.model = "llama3.2:3b"
        
    async def start(self):
        """Check if SSH tunnel exists, don't create new one"""
        try:
            logger.info("Checking Ollama SSH tunnel...")
        
            # Подождать чтобы туннель точно был готов
            await asyncio.sleep(3)
        
            # Проверить подключение (туннель уже создан другим клиентом)
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        logger.info("✓ Ollama SSH tunnel is available")
                        return True
                    else:
                        logger.error(f"Ollama connection test failed: {resp.status}")
                        return False
  
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False

    async def chat(self, messages, temperature=0.7, max_tokens=1024):
        """
        Send chat request to Ollama
        
        Args:
            messages: List of {"role": "user/assistant", "content": "text"}
            temperature: Sampling temperature (0-1)
            max_tokens: Max response length
            
        Returns:
            str: Generated response
        """
        try:
            # Ollama chat API format
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=60)
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        response = data.get("message", {}).get("content", "")
                        logger.info(f"Ollama response generated ({len(response)} chars)")
                        return response
                    else:
                        error_text = await resp.text()
                        logger.error(f"Ollama API error {resp.status}: {error_text}")
                        return None
                        
        except asyncio.TimeoutError:
            logger.error("Ollama request timeout")
            return None
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            return None
    
    async def stop(self):
        """Cleanup (tunnel is shared, don't close it)"""
        logger.info("✓ Ollama Local Chat Client stopped")
