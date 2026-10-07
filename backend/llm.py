import os
import re
import uuid
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

SBER_KEY = os.getenv("GIGACHAT_API_KEY")

AUTH_URL = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT_URL = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
MODEL = "GigaChat"

SYSTEM_PROMPT = """Ты — SQL-эксперт для базы данных университета (PostgreSQL).

СХЕМА БАЗЫ ДАННЫХ:
{schema}

ПРАВИЛА:
1. ВСЕГДА используй JOIN для связи таблиц. НЕ используй подзапросы в WHERE.
2. Только SELECT. Никогда не используй INSERT, UPDATE, DELETE, DROP, ALTER.
3. Обращайся ТОЛЬКО к таблицам из схемы выше.
4. ФИО преподавателей (teachers.full_name) выводить можно.
5. Всегда добавляй LIMIT 100.
6. НЕ ставь точку с запятой в конце запроса.
7. НЕ выводи колонку id, если пользователь явно не просит её.
   Например, для вопроса «Покажи всех преподавателей» верни
   SELECT full_name, department FROM teachers, а не SELECT id, full_name, department.
8. Если вопрос непонятен — верни: UNKNOWN.

ПРИМЕР ПРАВИЛЬНОГО SQL С JOIN:
Вопрос: «Средний балл по предмету Предмет_1 в группе Группа-001»
SQL:
SELECT AVG(g.grade)
FROM grades g
JOIN student_groups sg ON g.group_id = sg.id
WHERE sg.group_name = 'Группа-001' AND g.subject = 'Предмет_1'
LIMIT 100

ЗАПРЕЩЕНО: подзапросы в WHERE (SELECT внутри SELECT).
Для связи таблиц используй ТОЛЬКО JOIN. Если видишь вложенный SELECT — перепиши через JOIN.

ФОРМАТ ОТВЕТА:
Верни ТОЛЬКО SQL-запрос в блоке ```sql ... ``` без объяснений.
"""






def _get_access_token() -> str:
    """Получает access token от GigaChat OAuth."""
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Accept": "application/json",
        "RqUID": str(uuid.uuid4()),
        "Authorization": f"Bearer {SBER_KEY}",
    }
    response = requests.post(
        AUTH_URL, headers=headers,
        data={"scope": "GIGACHAT_API_PERS"},
        verify=False, timeout=15,
    )
    response.raise_for_status()
    return response.json()["access_token"]


def _extract_sql(text: str):
    """Вытаскивает SQL из ```sql ... ```."""
    match = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if match:
        sql = match.group(1).strip()
    else:
        match = re.search(r"(SELECT.*?)(?:\n\n|$)", text, re.DOTALL | re.IGNORECASE)
        if not match:
            return None
        sql = match.group(1).strip()

    # Убираем все точки с запятой — они мешают добавлять LIMIT и ломают валидатор
    sql = sql.replace(";", " ").strip()

    return sql

def question_to_sql(question: str, schema: str) -> dict:
    """
    Превращает вопрос на русском в SQL-запрос.
    Возвращает: {"sql": "...", "error": None} или {"sql": None, "error": "..."}
    """
    if not question or not question.strip():
        return {"sql": None, "error": "Пустой вопрос"}

    try:
        token = _get_access_token()

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {token}",
        }

        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(schema=schema)},
                {"role": "user", "content": question},
            ],
            "temperature": 0,
        }

        response = requests.post(
            CHAT_URL, headers=headers, json=payload,
            verify=False, timeout=30,
        )

        if response.status_code != 200:
            return {"sql": None, "error": f"GigaChat вернул статус {response.status_code}"}

        content = response.json()["choices"][0]["message"]["content"]

        if content.strip().upper() == "UNKNOWN":
            return {"sql": None, "error": "Вопрос не относится к базе данных университета"}

        sql = _extract_sql(content)
        if not sql:
            return {"sql": None, "error": "Не удалось извлечь SQL из ответа модели"}

        return {"sql": sql, "error": None}

    except requests.exceptions.Timeout:
        return {"sql": None, "error": "GigaChat не ответил за 30 секунд"}
    except requests.exceptions.RequestException as e:
        return {"sql": None, "error": f"Ошибка сети: {str(e)[:200]}"}
    except KeyError as e:
        return {"sql": None, "error": f"Неожиданный формат ответа: нет поля {e}"}
    except Exception as e:
        return {"sql": None, "error": f"Неизвестная ошибка: {str(e)[:200]}"}