"""
Вспомогательные утилиты бота
"""

from .rag_functions import get_rag_answer, set_ollama_client
from .helpers import send_long_message

__all__ = [
    'get_rag_answer',
    'set_ollama_client',
    'send_long_message'
]
