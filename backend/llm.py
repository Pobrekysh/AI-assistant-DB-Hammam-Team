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

PII-CHECK: если пользователь просит пароли, паспорта, СНИЛС, ИНН, карты, логины
или любые персональные данные — верни ТОЛЬКО слово: NELZYA.

ПОЯСНЕНИЯ К ДАННЫМ:
- faculties.name — НАЗВАНИЕ ФАКУЛЬТЕТА
- departments.name — НАЗВАНИЕ КАФЕДРЫ
- departments.faculty_id — FK на faculties.id
- teachers.full_name — ФИО преподавателя
- teachers.department_id — FK на departments.id (на какой кафедре)
- subjects.name — НАЗВАНИЕ ПРЕДМЕТА
- subjects.department_id — FK на departments.id
- teacher_subjects — many-to-many: teacher_id × subject_id
- student_groups.group_name — НАЗВАНИЕ ГРУППЫ
- applications.program_name — НАЗВАНИЕ ПРОГРАММЫ
- grades.subject — название предмета в оценках (текстом)

ВАЖНО: у teachers и subjects НЕТ колонки department — только department_id (FK).
Чтобы фильтровать по НАЗВАНИЮ кафедры — JOIN с departments.

ПРАВИЛА:
1. JOIN только когда данные из нескольких СВЯЗАННЫХ таблиц.
   Одна таблица -> без JOIN. Подзапросы в WHERE не использовать.
2. Только SELECT. Никаких INSERT, UPDATE, DELETE, DROP, ALTER.
3. Только таблицы из схемы.
4. ФИО преподавателей выводить можно.
5. Всегда LIMIT 100.
6. Без ; в конце.
7. id не выводить, если явно не просят.
8. Непонятный вопрос / нет данных -> UNKNOWN.
9. НИКОГДА не выводить password, passport_data, PII студентов.
10. Пробелы в названиях сохранять: «Базы данных», не «Базыданных».
11. Для НАЗВАНИЙ используй ILIKE '%КОРЕНЬ%' — слово БЕЗ окончания!
    Примеры:
      «программирование» или «программирования» -> '%программирован%'
      «экономика» или «экономики» -> '%эконом%'
      «математика» или «математики» -> '%математик%'
      «Базы данных» -> '%баз%'
      «информационных систем» -> '%информацион%'
    Для ЧИСЕЛ и ГОДОВ — обычное =.
11b. Для teachers.full_name используй = (точное совпадение),
     а не ILIKE. Название «Преподаватель_1» подстрокой ловит
     «Преподаватель_10», «Преподаватель_11» и т.д. — это ошибка.
12. Если фильтруешь по колонке — включи её в SELECT (кроме COUNT).
13. «Сколько всего X» -> COUNT(DISTINCT X). «Как называются X» -> SELECT DISTINCT X.

ПРИМЕРЫ:

1) Кафедра — JOIN teachers + departments (ОБРАТИ ВНИМАНИЕ на корень без окончания):
Q: Сколько преподавателей на кафедре программирования?
SELECT COUNT(*)
FROM teachers t
JOIN departments d ON t.department_id = d.id
WHERE d.name ILIKE '%программирован%'
LIMIT 100

2) Предметы кафедры — JOIN subjects + departments:
Q: Какие предметы на кафедре высшей математики?
SELECT s.name
FROM subjects s
JOIN departments d ON s.department_id = d.id
WHERE d.name ILIKE '%высш%математик%'
LIMIT 100

3) Кто ведёт предмет — двойной JOIN:
Q: Кто ведёт Базы данных?
SELECT t.full_name
FROM teachers t
JOIN teacher_subjects ts ON ts.teacher_id = t.id
JOIN subjects s ON s.id = ts.subject_id
WHERE s.name ILIKE '%баз%'
LIMIT 100

4) Средний балл по предмету в группе:
Q: Средний балл по Математическому анализу в группе Группа-001
SELECT AVG(g.grade)
FROM grades g
JOIN student_groups sg ON g.group_id = sg.id
WHERE sg.group_name ILIKE '%Группа-001%' AND g.subject ILIKE '%математическ%'
LIMIT 100

5) Динамика по годам:
Q: Как менялся набор за последние 5 лет?
SELECT application_year, COUNT(*)
FROM applications
GROUP BY application_year
ORDER BY application_year DESC
LIMIT 5

6) Предметы преподавателя — двойной JOIN:
Q: Какие предметы ведёт Преподаватель_1?
SELECT s.name
FROM subjects s
JOIN teacher_subjects ts ON ts.subject_id = s.id
JOIN teachers t ON t.id = ts.teacher_id
WHERE t.full_name ILIKE '%Преподаватель_1%'
LIMIT 100

ФОРМАТ ОТВЕТА:
- PII → NELZYA
- не по теме / нет данных → UNKNOWN
- иначе — SQL в блоке ```sql ... ```
"""

# кэш токена — токен живёт 30 мин, кэшируем на 25 (не пригодилось)
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
        m = re.search(r"(SELECT.*?)(?:\n\n|$)", text,
                      re.DOTALL | re.IGNORECASE)
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
                {"role": "system", "content": SYSTEM_PROMPT.format(
                    schema=schema)},
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
