"""
MCP клиенты для различных сервисов
"""

from .weather_client import MCPWeatherClient
from .news_client import MCPNewsClient
from .mobile_client import MCPMobileClient
from .ollama_client import MCPOllamaClient

__all__ = [
    'MCPWeatherClient',
    'MCPNewsClient',
    'MCPMobileClient',
    'MCPOllamaClient'
]
