"""
Анализ данных через готовые шаблоны (без Code Generation)
"""

import json
import logging
import matplotlib
matplotlib.use('Agg')  # Без GUI
import matplotlib.pyplot as plt
from collections import Counter
from datetime import datetime

logger = logging.getLogger(__name__)

TICKETS_PATH = "/root/telegram-bot/crm_data/tickets.json"


def load_tickets():
    """Загрузить все тикеты"""
    with open(TICKETS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data['tickets']


async def analyze_data(question: str, ollama_client=None) -> dict:
    """
    Анализ данных по вопросу пользователя
    
    Использует готовые шаблоны вместо генерации кода
    """
    
    try:
        tickets = load_tickets()
        q = question.lower()
        
        # === ПРОСТЫЕ ЗАПРОСЫ ===
        
        if 'сколько' in q and 'всего' in q and 'тикет' in q:
            total = len(tickets)
            return {
                "success": True,
                "answer": f"Всего тикетов: {total}",
                "plot_path": None,
                "code": None,
                "error": None
            }
        
        if ('процент' in q or '%' in q) and ('успешн' in q or 'решён' in q or 'решен' in q):
            successful = sum(1 for t in tickets.values() if t.get('rag_success'))
            total = len(tickets)
            pct = (successful / total * 100) if total > 0 else 0
            return {
                "success": True,
                "answer": f"Успешно решено: {successful}/{total} ({pct:.1f}%)",
                "plot_path": None,
                "code": None,
                "error": None
            }
        
        if 'приоритет' in q and 'high' in q:
            high = sum(1 for t in tickets.values() if t.get('priority') == 'high')
            return {
                "success": True,
                "answer": f"Тикетов с приоритетом high: {high}",
                "plot_path": None,
                "code": None,
                "error": None
            }
        
        # === ГРАФИКИ ===
        
        if 'график' in q or 'диаграмм' in q or 'визуализ' in q or 'построй' in q or 'покажи распределение' in q:
            
            if 'статус' in q:
                # График по статусам
                counts = {}
                for t in tickets.values():
                    s = t.get('status', 'unknown')
                    counts[s] = counts.get(s, 0) + 1
                
                plt.figure(figsize=(10, 6))
                plt.bar(counts.keys(), counts.values(), color='steelblue')
                plt.title('Распределение тикетов по статусам', fontsize=14, pad=20)
                plt.xlabel('Статус', fontsize=12)
                plt.ylabel('Количество', fontsize=12)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig('/tmp/plot.png', dpi=100, bbox_inches='tight')
                plt.close()
                
                summary = "\n".join([f"{s}: {n}" for s, n in counts.items()])
                
                return {
                    "success": True,
                    "answer": f"Распределение по статусам:\n{summary}",
                    "plot_path": "/tmp/plot.png",
                    "code": None,
                    "error": None
                }
            
            elif 'приоритет' in q:
                # График по приоритетам
                counts = {}
                for t in tickets.values():
                    p = t.get('priority', 'unknown')
                    counts[p] = counts.get(p, 0) + 1
                
                plt.figure(figsize=(10, 6))
                colors = {'urgent': '#d32f2f', 'high': '#f57c00', 'medium': '#fbc02d', 'low': '#388e3c'}
                bar_colors = [colors.get(p, 'gray') for p in counts.keys()]
                plt.bar(counts.keys(), counts.values(), color=bar_colors)
                plt.title('Распределение тикетов по приоритетам', fontsize=14, pad=20)
                plt.xlabel('Приоритет', fontsize=12)
                plt.ylabel('Количество', fontsize=12)
                plt.xticks(rotation=45, ha='right')
                plt.tight_layout()
                plt.savefig('/tmp/plot.png', dpi=100, bbox_inches='tight')
                plt.close()
                
                summary = "\n".join([f"{p}: {n}" for p, n in counts.items()])
                
                return {
                    "success": True,
                    "answer": f"Распределение по приоритетам:\n{summary}",
                    "plot_path": "/tmp/plot.png",
                    "code": None,
                    "error": None
                }
        
        # === ТОПОВЫЕ ВОПРОСЫ ===
        
        if ('топ' in q or 'частые' in q or 'популярн' in q) and ('тем' in q or 'вопрос' in q or 'проблем' in q):
            questions = []
            for t in tickets.values():
                history = t.get('history', [])
                if history:
                    msg = history[0].get('user_message', '')
                    if msg:
                        questions.append(msg)
            
            counter = Counter(questions)
            top_n = 3
            if 'пять' in q or '5' in q:
                top_n = 5
            
            top_items = counter.most_common(top_n)
            
            result_lines = [f"Топ-{top_n} вопросов:"]
            for i, (question_text, count) in enumerate(top_items, 1):
                # Обрезаем длинные вопросы
                short_q = question_text[:60] + '...' if len(question_text) > 60 else question_text
                result_lines.append(f"{i}. {short_q} ({count} раз)")
            
            return {
                "success": True,
                "answer": "\n".join(result_lines),
                "plot_path": None,
                "code": None,
                "error": None
            }
        
        # === СТАТИСТИКА ПО СТАТУСАМ ===
        
        if 'распределение' in q and 'статус' in q and 'график' not in q:
            counts = {}
            for t in tickets.values():
                s = t.get('status', 'unknown')
                counts[s] = counts.get(s, 0) + 1
            
            total = len(tickets)
            lines = ["Распределение по статусам:"]
            for status, count in sorted(counts.items()):
                pct = (count / total * 100) if total > 0 else 0
                lines.append(f"• {status}: {count} ({pct:.1f}%)")
            
            return {
                "success": True,
                "answer": "\n".join(lines),
                "plot_path": None,
                "code": None,
                "error": None
            }
        
        # Если не распознали запрос
        return {
            "success": False,
            "answer": None,
            "plot_path": None,
            "code": None,
            "error": "Не удалось распознать вопрос. Попробуйте: 'Сколько всего тикетов?', 'График по статусам', 'Топ-3 вопроса'"
        }
        
    except Exception as e:
        logger.error(f"Ошибка анализа: {e}", exc_info=True)
        return {
            "success": False,
            "answer": None,
            "plot_path": None,
            "code": None,
            "error": str(e)
        }
