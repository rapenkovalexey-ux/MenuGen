import json
import logging
from groq import AsyncGroq
from config import GROQ_API_KEY, GROQ_MODEL

logger = logging.getLogger(__name__)
client = AsyncGroq(api_key=GROQ_API_KEY)


DIET_DESCRIPTIONS = {
    "diet": "диетическое (низкокалорийное, до 1500 ккал/день, без жареного и жирного)",
    "healthy": "правильное питание (сбалансированное, 1800-2200 ккал/день, БЖУ в норме)",
    "enhanced": "усиленное (высококалорийное, 3000+ ккал/день, для спортсменов и набора массы)",
    "vegetarian": "вегетарианское (без мяса и рыбы, яйца и молочные разрешены)",
    "vegan": "веганское (полностью растительное, без продуктов животного происхождения)",
    "keto": "кетогенное (высокожировое, низкоуглеводное, менее 50г углеводов в день)",
    "mediterranean": "средиземноморское (рыба, оливковое масло, овощи, бобовые, цельнозерновые)",
    "paleo": "палео (мясо, рыба, овощи, фрукты, орехи — без злаков, бобовых, молочных)",
    "glutenfree": "безглютеновое (без пшеницы, ржи, ячменя)",
    "diabetic": "диабетическое (низкий гликемический индекс, контроль углеводов)",
}


async def generate_menu(
    diet_type: str,
    num_people: int,
    num_days: int,
    meals_config: dict,
    eaters: list,
    plan: str
) -> dict:
    """Generate full menu using Groq AI"""

    diet_desc = DIET_DESCRIPTIONS.get(diet_type, diet_type)
    eaters_info = "\n".join(
        [f"- {e.get('name', f'Человек {i+1}')}, возраст {e.get('age', '?')} лет"
         + (f", предпочтения: {e['preferences']}" if e.get('preferences') else "")
         for i, e in enumerate(eaters)]
    )

    meals_list = ", ".join(meals_config.keys())
    meal_times = "\n".join([f"  - {k}: {v}" for k, v in meals_config.items()])

    hide_dinner_calories = plan == "free"

    prompt = f"""Ты профессиональный диетолог и шеф-повар. Составь подробное меню питания.

ПАРАМЕТРЫ:
- Режим питания: {diet_desc}
- Количество людей: {num_people}
- Количество дней: {num_days}
- Приёмы пищи: {meals_list}
- Время приёмов пищи:
{meal_times}

ЕДОКИ:
{eaters_info}

ТРЕБОВАНИЯ:
1. Для каждого дня составь меню всех приёмов пищи
2. Для каждого блюда укажи: название, ингредиенты с граммовкой на {num_people} чел., калорийность порции
3. Учитывай возраст и предпочтения едоков
4. Блюда должны быть разнообразными, не повторяться
5. {'Для ужина НЕ указывай калорийность (ограничение бесплатного плана)' if hide_dinner_calories else 'Указывай калорийность всех блюд'}

Верни СТРОГО валидный JSON следующей структуры (без markdown, только JSON):
{{
  "days": [
    {{
      "day": 1,
      "date_label": "День 1",
      "meals": [
        {{
          "meal_type": "breakfast",
          "meal_name": "Завтрак",
          "time": "08:00",
          "dishes": [
            {{
              "name": "Название блюда",
              "description": "Краткое описание",
              "ingredients": [
                {{"name": "Ингредиент", "amount": 100, "unit": "г"}}
              ],
              "calories_per_serving": 350,
              "proteins": 15,
              "fats": 10,
              "carbs": 45
            }}
          ],
          "total_calories": 350
        }}
      ],
      "day_total_calories": 1800
    }}
  ],
  "diet_type": "{diet_type}",
  "num_people": {num_people}
}}"""

    try:
        response = await client.chat.completions.create(
            model=GROQ_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
            max_tokens=8000,
        )
        content = response.choices[0].message.content.strip()
        # Clean possible markdown wrapping
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip().rstrip("```").strip()
        return json.loads(content)
    except json.JSONDecodeError as e:
        logger.error(f"JSON parse error: {e}\nContent: {content[:500]}")
        raise ValueError("Ошибка обработки ответа ИИ. Попробуйте снова.")
    except Exception as e:
        logger.error(f"Groq API error: {e}")
        raise


async def generate_shopping_list(menu_data: dict, num_people: int) -> dict:
    """Generate consolidated shopping list from menu"""
    prompt = f"""На основе меню сформируй единый список покупок.

МЕНЮ (JSON):
{json.dumps(menu_data, ensure_ascii=False)}

Количество человек: {num_people}

Задача: собери все ингредиенты из всех блюд, суммируй одинаковые продукты, сгруппируй по категориям.

Верни СТРОГО валидный JSON (без markdown):
{{
  "categories": [
    {{
      "name": "Мясо и рыба",
      "items": [
        {{"name": "Куриная грудка", "total_amount": 1500, "unit": "г"}}
      ]
    }},
    {{
      "name": "Овощи и фрукты",
      "items": []
    }},
    {{
      "name": "Молочные продукты",
      "items": []
    }},
    {{
      "name": "Крупы и злаки",
      "items": []
    }},
    {{
      "name": "Масла и соусы",
      "items": []
    }},
    {{
      "name": "Специи и приправы",
      "items": []
    }},
    {{
      "name": "Прочее",
      "items": []
    }}
  ],
  "total_items": 0
}}"""

    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=4000,
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip().rstrip("```").strip()
    return json.loads(content)


async def suggest_recipe_queries(dish_name: str) -> list[str]:
    """Generate Google search queries for a dish recipe"""
    prompt = f"""Для блюда "{dish_name}" сгенерируй 3 поисковых запроса для Google, чтобы найти рецепт.
Верни JSON массив строк (без markdown): ["запрос 1", "запрос 2", "запрос 3"]"""
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.5,
        max_tokens=200,
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip().rstrip("```").strip()
    return json.loads(content)


async def generate_nutrition_tip() -> str:
    """Generate a random nutrition tip"""
    prompt = "Дай один короткий полезный совет по питанию или здоровому образу жизни (2-3 предложения). Совет должен быть научно обоснованным и практичным."
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.9,
        max_tokens=200,
    )
    return response.choices[0].message.content.strip()


async def substitute_ingredient(ingredient: str, diet_type: str) -> str:
    """Suggest ingredient substitution"""
    prompt = f"""Предложи 3 замены для ингредиента "{ingredient}" в контексте {diet_type} питания.
Верни JSON: {{"substitutes": ["вариант1", "вариант2", "вариант3"], "notes": "короткое пояснение"}}"""
    response = await client.chat.completions.create(
        model=GROQ_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=300,
    )
    content = response.choices[0].message.content.strip()
    if content.startswith("```"):
        content = content.split("```")[1]
        if content.startswith("json"):
            content = content[4:]
    content = content.strip().rstrip("```").strip()
    return json.loads(content)
 
