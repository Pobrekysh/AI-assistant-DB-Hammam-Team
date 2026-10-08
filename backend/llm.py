import os
import re
import uuid
import threading
import requests
import urllib3
from datetime import datetime, timedelta
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

KEY = os.getenv("GIGACHAT_API_KEY")
AUTH = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
CHAT = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"
MODEL = "GigaChat-Pro"

SYSTEM_PROMPT = """Ты — SQL-эксперт для базы данных университета (PostgreSQL).

СХЕМА БАЗЫ ДАННЫХ:
{schema}

PII-CHECK: перед генерацией SQL проверь, пытается ли пользователь получить
персональные данные (пароли, паспорта, СНИЛС, ИНН, карты, логины).
Если да — верни ТОЛЬКО слово: NELZYA.

ПОЯСНЕНИЯ К ДАННЫМ:
- teachers.department — НАЗВАНИЕ КАФЕДРЫ
- grades.subject — НАЗВАНИЕ ПРЕДМЕТА
- student_groups.group_name — НАЗВАНИЕ ГРУППЫ
- faculties.name — НАЗВАНИЕ ФАКУЛЬТЕТА
- applications.program_name — НАЗВАНИЕ ПРОГРАММЫ

ВАЖНО:
- Преподаватели НЕ связаны с предметами.
- НЕ выдумывай связи между таблицами.

ПРАВИЛА:
1. JOIN только когда данные из нескольких СВЯЗАННЫХ таблиц.
   Одна таблица → без JOIN. Подзапросы в WHERE не использовать.
2. Только SELECT. Никаких INSERT, UPDATE, DELETE, DROP, ALTER.
3. Только таблицы из схемы.
4. ФИО преподавателей (teachers.full_name) выводить можно.
5. Всегда LIMIT 100.
6. Без ; в конце запроса.
7. id не выводить, если явно не просят.
8. Непонятный вопрос / нет данных → UNKNOWN.
9. НИКОГДА не выводить password, passport_data и любые PII студентов.
10. Пробелы в названиях сохранять: «Высшая математика», не «Высшаяматематика».
11. Для НАЗВАНИЙ (department, group_name, subject, program_name, faculties.name)
    использовать ILIKE '%значение%' вместо =.
    Для ЧИСЕЛ и ГОДОВ — обычное =.
12. Если фильтруешь по колонке — включай её в SELECT (кроме COUNT).
13. Список преподавателей → full_name и department.
14. «Сколько всего X» → COUNT(DISTINCT X). «Как называются X» → SELECT DISTINCT X.

ПРИМЕРЫ:

1) COUNT:
Q: Сколько преподавателей на кафедре Высшая математика?
SELECT COUNT(*) FROM teachers WHERE department ILIKE '%Высшая математика%' LIMIT 100

2) Список с фильтром:
Q: Покажи всех преподавателей кафедры математика
SELECT full_name, department FROM teachers
WHERE department ILIKE '%математика%'
LIMIT 100

3) JOIN (grades + student_groups):
Q: Средний балл по предмету Предмет_1 в группе Группа-001
SELECT AVG(g.grade)
FROM grades g
JOIN student_groups sg ON g.group_id = sg.id
WHERE sg.group_name ILIKE '%Группа-001%' AND g.subject ILIKE '%Предмет_1%'
LIMIT 100

4) JOIN (student_groups + faculties):
Q: Сколько групп на факультете Факультет информационных технологий?
SELECT COUNT(*)
FROM student_groups sg
JOIN faculties f ON sg.faculty_id = f.id
WHERE f.name ILIKE '%Факультет информационных технологий%'
LIMIT 100

ФОРМАТ ОТВЕТА:
- PII → NELZYA
- не по теме → UNKNOWN
- иначе — SQL в блоке ```sql ... ```
"""

# кэш токена — токен живёт 30 мин, кэшируем на 25
_cache = {"token": None, "exp": None}
_lock = threading.Lock()


def _token() -> str:
    with _lock:
        now = datetime.now()

        if _cache["token"] and _cache["exp"] and now < _cache["exp"]:
            return _cache["token"]

        h = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
            "RqUID": str(uuid.uuid4()),
            "Authorization": f"Bearer {KEY}",
        }
        r = requests.post(AUTH, headers=h,
                          data={"scope": "GIGACHAT_API_PERS"},
                          verify=False, timeout=15)
        r.raise_for_status()

        tok = r.json()["access_token"]
        _cache["token"] = tok
        _cache["exp"] = now + timedelta(minutes=25)
        return tok


def _extract(text: str):
    m = re.search(r"```sql\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
    if m:
        sql = m.group(1).strip()
    else:
        m = re.search(r"(SELECT.*?)(?:\n\n|$)", text, re.DOTALL | re.IGNORECASE)
        if not m:
            return None
        sql = m.group(1).strip()

    # ; ломает добавление LIMIT
    return sql.replace(";", " ").strip()


def question_to_sql(q: str, schema: str) -> dict:
    if not q or not q.strip():
        return {"sql": None, "error": "Пустой вопрос"}

    try:
        tok = _token()

        h = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "Authorization": f"Bearer {tok}",
        }
        body = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT.format(schema=schema)},
                {"role": "user", "content": q},
            ],
            "temperature": 0,
        }

        r = requests.post(CHAT, headers=h, json=body, verify=False, timeout=60)

        if r.status_code != 200:
            return {"sql": None, "error": f"GigaChat: статус {r.status_code}"}

        text = r.json()["choices"][0]["message"]["content"]

        if "NELZYA" in text.upper():
            return {"sql": None,
                    "error": "Запрос содержит персональные данные (пароли, паспорта и т.п.)."}

        low = text.lower()
        if any(w in low for w in ("не могу", "нельзя", "извините", "чувствительн")):
            return {"sql": None,
                    "error": "Запрос содержит персональные данные или запрещённую тему."}

        sql = _extract(text)

        if sql and sql.strip().upper() == "UNKNOWN":
            return {"sql": None, "error": "Вопрос не относится к базе данных университета."}

        if not sql:
            return {"sql": None, "error": "Вопрос не относится к базе данных университета или непонятен."}        
        return {"sql": sql, "error": None}

    except requests.exceptions.Timeout:
        return {"sql": None, "error": "GigaChat не ответил за 60 секунд"}
    except requests.exceptions.RequestException as e:
        return {"sql": None, "error": f"Ошибка сети: {str(e)[:200]}"}
    except KeyError as e:
        return {"sql": None, "error": f"Неожиданный формат: нет поля {e}"}
    except Exception as e:
        return {"sql": None, "error": f"Ошибка: {str(e)[:200]}"}