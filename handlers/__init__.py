#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Handlers - обработчики команд
"""

# Импортируем только то что точно есть
from . import basic

# Импортируем новый RAG handler
from .with_rag import (
    with_rag_command,
    clear_rag_history_command,
    rag_history_command
)

__all__ = [
    'basic',
    'with_rag_command',
    'clear_rag_history_command',
    'rag_history_command',
]
