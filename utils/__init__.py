"""
Вспомогательные утилиты бота
"""

from .rag_functions import get_rag_answer, get_no_rag_answer, save_comparison, set_ollama_client
from .helpers import send_long_message

__all__ = [
    'get_rag_answer',
    'get_no_rag_answer', 
    'save_comparison',
    'set_ollama_client',
    'send_long_message'
]
