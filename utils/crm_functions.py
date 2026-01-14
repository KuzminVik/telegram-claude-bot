"""
CRM функции для работы с пользователями и тикетами
Простая JSON-based система для саппорта
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from pathlib import Path

# Пути к CRM данным
CRM_DATA_DIR = Path(__file__).parent.parent / "crm_data"
USERS_FILE = CRM_DATA_DIR / "users.json"
TICKETS_FILE = CRM_DATA_DIR / "tickets.json"

# Создаём директорию если не существует
CRM_DATA_DIR.mkdir(exist_ok=True)


def _load_json(filepath: Path) -> dict:
    """Загрузить JSON файл"""
    if not filepath.exists():
        return {}
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading {filepath}: {e}")
        return {}


def _save_json(filepath: Path, data: dict):
    """Сохранить JSON файл"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Error saving {filepath}: {e}")


# === Работа с пользователями ===

def get_user(telegram_id: int) -> Optional[Dict]:
    """Получить данные пользователя"""
    users = _load_json(USERS_FILE)
    return users.get(str(telegram_id))


def create_or_update_user(telegram_id: int, username: str = None, first_name: str = None) -> Dict:
    """Создать или обновить пользователя"""
    users = _load_json(USERS_FILE)
    user_key = str(telegram_id)
    
    if user_key not in users:
        # Новый пользователь
        users[user_key] = {
            "telegram_id": telegram_id,
            "username": username,
            "first_name": first_name,
            "registered_at": datetime.now().isoformat(),
            "total_tickets": 0,
            "open_tickets": 0,
            "last_interaction": None
        }
    else:
        # Обновляем существующего
        if username:
            users[user_key]["username"] = username
        if first_name:
            users[user_key]["first_name"] = first_name
    
    users[user_key]["last_interaction"] = datetime.now().isoformat()
    _save_json(USERS_FILE, users)
    return users[user_key]


# === Работа с тикетами ===

def get_user_tickets(telegram_id: int, status: str = None) -> List[Dict]:
    """Получить тикеты пользователя (опционально по статусу)"""
    tickets_data = _load_json(TICKETS_FILE)
    tickets = tickets_data.get("tickets", {})
    
    user_tickets = []
    for ticket_id, ticket in tickets.items():
        if ticket["user_id"] == telegram_id:
            if status is None or ticket["status"] == status:
                user_tickets.append(ticket)
    
    # Сортируем по дате создания (новые сначала)
    user_tickets.sort(key=lambda x: x["created_at"], reverse=True)
    return user_tickets


def get_ticket(ticket_id: str) -> Optional[Dict]:
    """Получить тикет по ID"""
    tickets_data = _load_json(TICKETS_FILE)
    tickets = tickets_data.get("tickets", {})
    return tickets.get(ticket_id)


def create_ticket(
    telegram_id: int,
    question: str,
    assistant_response: str = None
) -> Dict:
    """Создать новый тикет"""
    tickets_data = _load_json(TICKETS_FILE)
    
    if "tickets" not in tickets_data:
        tickets_data["tickets"] = {}
    if "_next_ticket_id" not in tickets_data:
        tickets_data["_next_ticket_id"] = 1
    
    # Генерируем ID
    ticket_id = f"ticket_{tickets_data['_next_ticket_id']:04d}"
    tickets_data["_next_ticket_id"] += 1
    
    # Создаём тикет
    now = datetime.now().isoformat()
    ticket = {
        "id": ticket_id,
        "user_id": telegram_id,
        "status": "open",
        "question": question,
        "created_at": now,
        "updated_at": now,
        "history": []
    }
    
    # Добавляем первое взаимодействие
    if assistant_response:
        ticket["history"].append({
            "timestamp": now,
            "user_message": question,
            "assistant_response": assistant_response
        })
    
    tickets_data["tickets"][ticket_id] = ticket
    _save_json(TICKETS_FILE, tickets_data)
    
    # Обновляем счётчики пользователя
    _update_user_ticket_count(telegram_id)
    
    return ticket


def update_ticket(
    ticket_id: str,
    user_message: str = None,
    assistant_response: str = None,
    status: str = None
) -> Optional[Dict]:
    """Обновить тикет (добавить сообщение или изменить статус)"""
    tickets_data = _load_json(TICKETS_FILE)
    tickets = tickets_data.get("tickets", {})
    
    if ticket_id not in tickets:
        return None
    
    ticket = tickets[ticket_id]
    now = datetime.now().isoformat()
    
    # Добавляем новое взаимодействие в историю
    if user_message or assistant_response:
        ticket["history"].append({
            "timestamp": now,
            "user_message": user_message or "",
            "assistant_response": assistant_response or ""
        })
    
    # Обновляем статус
    if status:
        ticket["status"] = status
    
    ticket["updated_at"] = now
    tickets_data["tickets"][ticket_id] = ticket
    _save_json(TICKETS_FILE, tickets_data)
    
    # Обновляем счётчики если статус изменился
    if status:
        _update_user_ticket_count(ticket["user_id"])
    
    return ticket


def _update_user_ticket_count(telegram_id: int):
    """Обновить счётчики тикетов у пользователя"""
    users = _load_json(USERS_FILE)
    user_key = str(telegram_id)
    
    if user_key not in users:
        return
    
    # Подсчитываем тикеты
    user_tickets = get_user_tickets(telegram_id)
    open_tickets = [t for t in user_tickets if t["status"] == "open"]
    
    users[user_key]["total_tickets"] = len(user_tickets)
    users[user_key]["open_tickets"] = len(open_tickets)
    
    _save_json(USERS_FILE, users)


def get_ticket_context(telegram_id: int) -> str:
    """Получить краткий контекст тикетов для промпта Claude"""
    user = get_user(telegram_id)
    open_tickets = get_user_tickets(telegram_id, status="open")
    
    if not user:
        return "Новый пользователь без истории."
    
    context_parts = [
        f"**Пользователь:** {user.get('first_name', 'Unknown')} (@{user.get('username', 'unknown')})",
        f"**Всего тикетов:** {user['total_tickets']}",
        f"**Открытых тикетов:** {user['open_tickets']}"
    ]
    
    # Добавляем последние открытые тикеты (до 3)
    if open_tickets:
        context_parts.append("\n**Последние открытые тикеты:**")
        for ticket in open_tickets[:3]:
            context_parts.append(
                f"- [{ticket['id']}] {ticket['question'][:100]}... "
                f"(создан: {ticket['created_at'][:10]})"
            )
    
    return "\n".join(context_parts)


# === Статистика ===

def get_crm_stats() -> Dict:
    """Получить общую статистику CRM"""
    users = _load_json(USERS_FILE)
    tickets_data = _load_json(TICKETS_FILE)
    tickets = tickets_data.get("tickets", {})
    
    open_count = sum(1 for t in tickets.values() if t["status"] == "open")
    closed_count = sum(1 for t in tickets.values() if t["status"] == "closed")
    
    return {
        "total_users": len(users),
        "total_tickets": len(tickets),
        "open_tickets": open_count,
        "closed_tickets": closed_count
    }


if __name__ == "__main__":
    # Тестирование
    print("=== CRM Functions Test ===")
    
    # Создаём тестового пользователя
    user = create_or_update_user(123456, "testuser", "Test User")
    print(f"\n✓ Создан пользователь: {user}")
    
    # Создаём тикет
    ticket = create_ticket(123456, "Как работает /weather?", "Используйте /weather_subscribe")
    print(f"\n✓ Создан тикет: {ticket['id']}")
    
    # Обновляем тикет
    update_ticket(ticket['id'], user_message="Спасибо!", assistant_response="Рад помочь!")
    print(f"\n✓ Обновлён тикет: {ticket['id']}")
    
    # Получаем контекст
    context = get_ticket_context(123456)
    print(f"\n✓ Контекст:\n{context}")
    
    # Статистика
    stats = get_crm_stats()
    print(f"\n✓ Статистика: {stats}")
