#!/usr/bin/env python3
"""
Скрипт для тестирования влияния параметра temperature на ответы Claude AI
Сравнивает ответы с temperature = 0, 0.7 и 1.2 на одинаковые запросы
"""

import os
import json
import time
from anthropic import Anthropic
from datetime import datetime

# Инициализация Claude API
client = Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))

# Модель Claude
MODEL = "claude-sonnet-4-20250514"

# Системный промпт
SYSTEM_PROMPT = """Ты полезный AI-ассистент. Отвечай на вопросы пользователя четко и по существу.
Всегда отвечай ТОЛЬКО валидным JSON в формате:
{"user_message": "повтор вопроса пользователя", "ai_message": "твой ответ"}

Никаких markdown блоков, никаких пояснений до или после JSON. Только чистый JSON."""

# Тестовые запросы разных типов
TEST_QUERIES = [
    {
        "type": "factual",
        "query": "Что такое фотосинтез?",
        "description": "Фактический вопрос - требует точного ответа"
    },
    {
        "type": "creative",
        "query": "Придумай короткую историю о роботе, который научился чувствовать эмоции",
        "description": "Творческая задача - требует креативности"
    },
    {
        "type": "analytical",
        "query": "Сравни преимущества и недостатки iOS и Android для разработки мобильных приложений",
        "description": "Аналитическая задача - требует структурированного анализа"
    },
    {
        "type": "code",
        "query": "Напиши функцию на Python для сортировки списка чисел пузырьком",
        "description": "Программирование - требует точности"
    },
    {
        "type": "open_ended",
        "query": "Какие технологии будут популярны в 2030 году?",
        "description": "Открытый вопрос - требует рассуждений и прогнозов"
    }
]

# Температуры для тестирования
TEMPERATURES = [0, 0.7, 1.0]


def clean_json_response(response_text):
    """Очистка ответа от markdown и извлечение JSON"""
    import re
    
    # Удаляем блоки ```json и ```
    cleaned = re.sub(r'```json\s*', '', response_text)
    cleaned = re.sub(r'```\s*', '', cleaned)
    cleaned = cleaned.strip()
    
    # Пытаемся найти JSON объект
    json_match = re.search(r'\{.*\}', cleaned, re.DOTALL)
    if json_match:
        return json_match.group(0)
    
    return cleaned


def get_claude_response(user_message, temperature):
    """Получить ответ от Claude с заданной температурой"""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            temperature=temperature,
            system=SYSTEM_PROMPT,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        # Извлекаем текстовый ответ
        raw_response = response.content[0].text
        
        # Очищаем и парсим JSON
        clean_response = clean_json_response(raw_response)
        parsed_response = json.loads(clean_response)
        
        return {
            "success": True,
            "ai_message": parsed_response.get("ai_message", ""),
            "raw_response": raw_response,
            "tokens_used": response.usage.input_tokens + response.usage.output_tokens
        }
    
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "ai_message": None
        }


def run_temperature_experiment():
    """Запустить эксперимент с разными температурами"""
    print("=" * 80)
    print("ЭКСПЕРИМЕНТ: Влияние параметра TEMPERATURE на ответы Claude AI")
    print("=" * 80)
    print(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Модель: {MODEL}")
    print(f"Температуры: {TEMPERATURES}")
    print(f"Количество тестов: {len(TEST_QUERIES)}")
    print("=" * 80)
    print()
    
    results = []
    
    for query_data in TEST_QUERIES:
        query = query_data["query"]
        query_type = query_data["type"]
        description = query_data["description"]
        
        print(f"\n{'=' * 80}")
        print(f"ТЕСТ: {query_type.upper()}")
        print(f"Описание: {description}")
        print(f"Запрос: {query}")
        print(f"{'=' * 80}\n")
        
        query_results = {
            "query": query,
            "type": query_type,
            "description": description,
            "responses": {}
        }
        
        for temp in TEMPERATURES:
            print(f"\n--- Temperature = {temp} ---")
            
            response = get_claude_response(query, temp)
            
            if response["success"]:
                ai_message = response["ai_message"]
                tokens = response["tokens_used"]
                
                print(f"✓ Успешно получен ответ ({tokens} токенов)")
                print(f"\nОтвет:\n{ai_message[:500]}{'...' if len(ai_message) > 500 else ''}\n")
                
                query_results["responses"][str(temp)] = {
                    "ai_message": ai_message,
                    "tokens_used": tokens,
                    "length": len(ai_message)
                }
            else:
                print(f"✗ Ошибка: {response['error']}")
                query_results["responses"][str(temp)] = {
                    "error": response["error"]
                }
            
            # Пауза между запросами
            time.sleep(1)
        
        results.append(query_results)
    
    return results


def analyze_results(results):
    """Анализ результатов эксперимента"""
    print("\n\n" + "=" * 80)
    print("АНАЛИЗ РЕЗУЛЬТАТОВ")
    print("=" * 80)
    
    analysis = {
        "summary": {},
        "observations": [],
        "recommendations": {}
    }
    
    for result in results:
        query_type = result["type"]
        print(f"\n\n## {query_type.upper()}")
        print(f"Запрос: {result['query']}\n")
        
        responses = result["responses"]
        
        # Сравнение длины ответов
        print("### Длина ответов:")
        for temp in TEMPERATURES:
            if str(temp) in responses and "length" in responses[str(temp)]:
                length = responses[str(temp)]["length"]
                print(f"  T={temp}: {length} символов")
        
        # Сравнение количества токенов
        print("\n### Использовано токенов:")
        for temp in TEMPERATURES:
            if str(temp) in responses and "tokens_used" in responses[str(temp)]:
                tokens = responses[str(temp)]["tokens_used"]
                print(f"  T={temp}: {tokens} токенов")
        
        # Качественная оценка
        print("\n### Наблюдения:")
        if str(0) in responses and str(1.2) in responses:
            resp_0 = responses[str(0)].get("ai_message", "")
            resp_12 = responses[str(1.2)].get("ai_message", "")
            
            if query_type == "factual":
                print(f"  • Temperature=0: Более структурированный и точный ответ")
                print(f"  • Temperature=1.2: Более разнообразная формулировка")
            elif query_type == "creative":
                print(f"  • Temperature=0: Более предсказуемый сюжет")
                print(f"  • Temperature=1.2: Более оригинальные идеи")
            elif query_type == "code":
                print(f"  • Temperature=0: Классическая реализация")
                print(f"  • Temperature=1.2: Возможны вариации в реализации")
    
    return analysis


def save_results(results, analysis):
    """Сохранить результаты в файл"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"temperature_experiment_{timestamp}.json"
    
    output = {
        "experiment_date": datetime.now().isoformat(),
        "model": MODEL,
        "temperatures_tested": TEMPERATURES,
        "results": results,
        "analysis": analysis
    }
    
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n\n✓ Результаты сохранены в файл: {filename}")
    return filename


def generate_markdown_report(results):
    """Генерация отчета в формате Markdown"""
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"temperature_report_{timestamp}.md"
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write("# Эксперимент: Влияние параметра Temperature на ответы Claude AI\n\n")
        f.write(f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  \n")
        f.write(f"**Модель:** {MODEL}  \n")
        f.write(f"**Температуры:** {', '.join(map(str, TEMPERATURES))}  \n\n")
        
        f.write("## Что такое Temperature?\n\n")
        f.write("Temperature (температура) - это параметр, контролирующий случайность/креативность ответов AI:\n")
        f.write("- **T=0**: Детерминированные, предсказуемые ответы (всегда выбирается самый вероятный токен)\n")
        f.write("- **T=0.7**: Баланс между точностью и креативностью (рекомендуемое значение)\n")
        f.write("- **T=1.2**: Высокая креативность и разнообразие (более рискованные выборы)\n\n")
        
        f.write("---\n\n")
        
        for result in results:
            f.write(f"## Тест: {result['type'].upper()}\n\n")
            f.write(f"**Описание:** {result['description']}  \n")
            f.write(f"**Запрос:** _{result['query']}_\n\n")
            
            responses = result["responses"]
            
            for temp in TEMPERATURES:
                if str(temp) in responses and "ai_message" in responses[str(temp)]:
                    f.write(f"### Temperature = {temp}\n\n")
                    ai_msg = responses[str(temp)]["ai_message"]
                    tokens = responses[str(temp)]["tokens_used"]
                    length = responses[str(temp)]["length"]
                    
                    f.write(f"**Статистика:** {length} символов, {tokens} токенов\n\n")
                    f.write(f"**Ответ:**\n```\n{ai_msg}\n```\n\n")
            
            f.write("---\n\n")
        
        # Выводы
        f.write("## Выводы и рекомендации\n\n")
        f.write("### Temperature = 0 (Детерминированность)\n")
        f.write("**Лучше всего подходит для:**\n")
        f.write("- Фактических вопросов, требующих точных ответов\n")
        f.write("- Написания кода (максимальная консистентность)\n")
        f.write("- Технической документации\n")
        f.write("- Задач классификации и анализа данных\n")
        f.write("- Когда важна воспроизводимость результатов\n\n")
        
        f.write("### Temperature = 0.7 (Баланс)\n")
        f.write("**Лучше всего подходит для:**\n")
        f.write("- Общения с пользователями (чат-боты)\n")
        f.write("- Аналитических задач с элементами творчества\n")
        f.write("- Генерации контента среднего уровня креативности\n")
        f.write("- Большинства повседневных задач\n")
        f.write("- Когда нужен баланс точности и естественности\n\n")
        
        f.write("### Temperature = 1.2 (Креативность)\n")
        f.write("**Лучше всего подходит для:**\n")
        f.write("- Творческого письма (истории, стихи, сценарии)\n")
        f.write("- Брейнсторминга и генерации идей\n")
        f.write("- Создания оригинального контента\n")
        f.write("- Задач, требующих нестандартных решений\n")
        f.write("- Когда важно разнообразие и избежание шаблонов\n\n")
        
        f.write("### Общие наблюдения\n\n")
        f.write("1. **Длина ответов:** При высокой температуре ответы могут быть длиннее и более развернутыми\n")
        f.write("2. **Консистентность:** T=0 даст практически одинаковые ответы при повторных запросах\n")
        f.write("3. **Риск галлюцинаций:** При T>1.0 увеличивается вероятность неточностей в фактах\n")
        f.write("4. **Структура:** Низкая температура даёт более структурированные ответы\n")
        f.write("5. **Оригинальность:** Высокая температура генерирует более неожиданные формулировки\n\n")
    
    print(f"✓ Markdown отчет сохранен в файл: {filename}")
    return filename


def main():
    """Главная функция"""
    print("\n🚀 Запуск эксперимента...\n")
    
    # Проверка API ключа
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Ошибка: Не установлена переменная окружения ANTHROPIC_API_KEY")
        return
    
    # Запуск эксперимента
    results = run_temperature_experiment()
    
    # Анализ результатов
    analysis = analyze_results(results)
    
    # Сохранение результатов
    json_file = save_results(results, analysis)
    md_file = generate_markdown_report(results)
    
    print("\n\n" + "=" * 80)
    print("✓ ЭКСПЕРИМЕНТ ЗАВЕРШЕН")
    print("=" * 80)
    print(f"Результаты сохранены в:")
    print(f"  • JSON: {json_file}")
    print(f"  • Markdown: {md_file}")
    print("\nОткройте Markdown файл для детального отчета с выводами.")
    print("=" * 80)


if __name__ == "__main__":
    main()
