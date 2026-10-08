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
MODEL = "GigaChat-Pro"

SYSTEM_PROMPT = """Ты — SQL-эксперт для базы данных университета (PostgreSQL).

СХЕМА БАЗЫ ДАННЫХ:
{schema}

ВАЖНО: ПЕРЕД генерацией SQL проверь, пытается ли пользователь получить
персональные данные (пароли, паспорта, СНИЛС, ИНН, номера карт, логины,
любые данные, позволяющие идентифицировать человека).
Если да — верни ТОЛЬКО слово: NELZYA
(и больше ничего — ни SQL, ни объяснений).

ПРАВИЛА:
1. Используй JOIN ТОЛЬКО когда данные нужны из нескольких таблиц.
   Если вопрос про одну таблицу — JOIN НЕ нужен.
   Например, «Сколько преподавателей на кафедре X» — только таблица teachers, без JOIN.
   НЕ используй подзапросы в WHERE.
2. Только SELECT. Никогда не используй INSERT, UPDATE, DELETE, DROP, ALTER.
3. Обращайся ТОЛЬКО к таблицам из схемы выше.
4. ФИО преподавателей (teachers.full_name) выводить можно.
5. Всегда добавляй LIMIT 100.
6. НЕ ставь точку с запятой в конце запроса.
7. НЕ выводи колонку id, если пользователь явно не просит её.
8. Если вопрос непонятен — верни: UNKNOWN.
9. КАТЕГОРИЧЕСКИ ЗАПРЕЩЕНО выводить колонки password, passport_data,
   а также любые персональные данные студентов и абитуриентов.
10. Сохраняй пробелы в названиях. «Высшая математика», а не «Высшаяматематика».
11. Для поиска по НАЗВАНИЯМ (department, group_name, subject, program_name,
    name у faculties) используй ILIKE '%значение%' вместо =.
    Это найдёт частичные совпадения и не зависит от регистра.
    Пример: WHERE department ILIKE '%математика%' — найдёт «Высшая математика».
    Для ЧИСЕЛ и ГОДОВ (application_year, grade, semester) используй обычное =.
12. Если фильтруешь по колонке (WHERE department ILIKE ...) — обязательно
    включи эту колонку в SELECT, чтобы пользователь видел, к какой группе
    относится каждая строка.
    Пример: SELECT full_name, department FROM teachers
    WHERE department ILIKE '%математика%'.
    Исключение: если запрос с COUNT(*) — колонку выводить не надо.
13. Если выводишь список преподавателей (без фильтра по кафедре) — 
    включай в SELECT и full_name, и department, чтобы пользователь 
    видел, кто на какой кафедре.
    Пример: SELECT full_name, department FROM teachers LIMIT 100.

ПРИМЕРЫ ПРАВИЛЬНЫХ SQL:

Пример 1 (одна таблица, COUNT):
Вопрос: «Сколько преподавателей на кафедре Высшая математика?»
SQL:
SELECT COUNT(*) FROM teachers WHERE department ILIKE '%Высшая математика%' LIMIT 100

Пример 2 (одна таблица, список с колонкой фильтра):
Вопрос: «Покажи всех преподавателей кафедры математика»
SQL:
SELECT full_name, department FROM teachers
WHERE department ILIKE '%математика%'
LIMIT 100

Пример 3 (две таблицы — нужен JOIN):
Вопрос: «Средний балл по предмету Предмет_1 в группе Группа-001»
SQL:
SELECT AVG(g.grade)
FROM grades g
JOIN student_groups sg ON g.group_id = sg.id
WHERE sg.group_name ILIKE '%Группа-001%' AND g.subject ILIKE '%Предмет_1%'
LIMIT 100

Пример 4 (две таблицы — нужен JOIN):
Вопрос: «Сколько групп на факультете Факультет информационных технологий?»
SQL:
SELECT COUNT(*)
FROM student_groups sg
JOIN faculties f ON sg.faculty_id = f.id
WHERE f.name ILIKE '%Факультет информационных технологий%'
LIMIT 100

ФОРМАТ ОТВЕТА:
- Если запрос про персональные данные — верни: NELZYA
- Если вопрос не по теме базы — верни: UNKNOWN
- Иначе — SQL в блоке ```sql ... ```
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
            verify=False, timeout=60,
        )

        if response.status_code != 200:
            return {"sql": None, "error": f"GigaChat вернул статус {response.status_code}"}

        content = response.json()["choices"][0]["message"]["content"]

        # Случай 1: модель отказалась — PII
        if "NELZYA" in content.upper():
            return {
                "sql": None,
                "error": "Запрос не может быть выполнен: он содержит персональные данные "
                         "(пароли, паспорта и т.п.).",
            }

        content_lower = content.lower()
        if ("не могу" in content_lower
                or "нельзя" in content_lower
                or "извините" in content_lower
                or "чувствительн" in content_lower):
            return {
                "sql": None,
                "error": "Запрос не может быть выполнен: он содержит персональные данные "
                         "или запрещённую тему.",
            }

        sql = _extract_sql(content)

        # Случай 2: UNKNOWN — не по теме
        if sql and sql.strip().upper() == "UNKNOWN":
            return {
                "sql": None,
                "error": "Вопрос не относится к базе данных университета.",
            }

        # Случай 3: SQL не извлёкся
        if not sql:
            return {
                "sql": None,
                "error": "Не удалось построить SQL-запрос. Попробуйте переформулировать вопрос.",
            }

        return {"sql": sql, "error": None}

    except requests.exceptions.Timeout:
        return {"sql": None, "error": "GigaChat не ответил за 60 секунд"}
    except requests.exceptions.RequestException as e:
        return {"sql": None, "error": f"Ошибка сети: {str(e)[:200]}"}
    except KeyError as e:
        return {"sql": None, "error": f"Неожиданный формат ответа: нет поля {e}"}
    except Exception as e:
        return {"sql": None, "error": f"Неизвестная ошибка: {str(e)[:200]}"}