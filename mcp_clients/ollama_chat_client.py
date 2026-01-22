# /root/telegram-bot/mcp_clients/ollama_chat_client.py
# Optimized version with improved parameters

import asyncio
import logging
import aiohttp

logger = logging.getLogger(__name__)

class OllamaLocalChatClient:
    """Client for chatting with Ollama LLM on dedicated server"""
    
    def __init__(self):
        # Direct connection to Ollama server (no SSH tunnel)
        self.ollama_url = "http://157.22.241.102:11434"
        self.model = "llama3.2:1b"
        
    async def start(self):
        """Check Ollama server availability"""
        try:
            logger.info("Checking Ollama server at http://157.22.241.102:11434...")
        
            # Check connection to Ollama server
            async with aiohttp.ClientSession() as session:
                async with session.get(f"{self.ollama_url}/api/tags", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        models = data.get("models", [])
                        logger.info(f"✓ Ollama server available at {self.ollama_url}")
                        logger.info(f"Available models: {[m['name'] for m in models]}")
                        return True
                    else:
                        logger.error(f"Ollama connection test failed: {resp.status}")
                        return False
  
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            return False

    async def chat(self, messages, temperature=0.3, max_tokens=512):
        """
        Send chat request to Ollama with optimized parameters
        
        Args:
            messages: List of {"role": "user/assistant/system", "content": "text"}
            temperature: Sampling temperature (default: 0.3 for accuracy)
            max_tokens: Max response length
            
        Returns:
            str: Generated response
        """
        try:
            # Ollama chat API format with optimized parameters
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,      # 0.3 - более точные ответы
                    "num_predict": max_tokens,       # 512 tokens
                    "num_ctx": 768,                  # Увеличен контекст (было 512)
                    "top_p": 0.9,                    # Фокус на вероятных токенах
                    "repeat_penalty": 1.1            # Избегать повторений
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.ollama_url}/api/chat",
                    json=payload,
                    timeout=aiohttp.ClientTimeout(total=120)  # 120s timeout
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
            logger.error("Ollama request timeout (120s)")
            return None
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            return None
    
    async def stop(self):
        """Cleanup"""
        logger.info("✓ Ollama Local Chat Client stopped")
