import os
import uuid
import requests
import urllib3
from dotenv import load_dotenv

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
load_dotenv()

SBER_KEY = os.getenv("GIGACHAT_API_KEY")

# ===== Ступень 1: получаем access token =====
sber_url = "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"

headers = {
    "Content-Type": "application/x-www-form-urlencoded",
    "Accept": "application/json",
    "RqUID": str(uuid.uuid4()),
    "Authorization": f"Bearer {SBER_KEY}",
}

payload = {"scope": "GIGACHAT_API_PERS"}

print("Получаю access token...")
response = requests.post(sber_url, headers=headers, data=payload, verify=False)

if response.status_code != 200:
    print(f"Ошибка OAuth: {response.status_code}")
    print(response.text)
    exit(1)

token = response.json().get("access_token")
print(f"Токен получен, длина {len(token)} символов")

# ===== Ступень 2: запрос к модели =====
chat_url = "https://gigachat.devices.sberbank.ru/api/v1/chat/completions"

headers_chat = {
    "Content-Type": "application/json",
    "Accept": "application/json",
    "Authorization": f"Bearer {token}",
}

SYSTEM_PROMPT = """Ты — SQL-эксперт для базы данных университета (PostgreSQL).

СХЕМА БАЗЫ ДАННЫХ:
- faculties: id (SERIAL, PK), name (VARCHAR)
- teachers: id (SERIAL, PK), full_name (VARCHAR), department (VARCHAR)
- student_groups: id (SERIAL, PK), group_name (VARCHAR), faculty_id (FK -> faculties.id)
- applications: id (SERIAL, PK), program_name (VARCHAR), application_year (INT), status (VARCHAR)
- grades: id (SERIAL, PK), group_id (FK -> student_groups.id), subject (VARCHAR), grade (INT), semester (INT)

ПРАВИЛА:
1. ВСЕГДА используй JOIN для связи таблиц. НЕ используй подзапросы в WHERE.
2. Только SELECT. Никогда не используй INSERT, UPDATE, DELETE, DROP, ALTER.
3. Обращайся ТОЛЬКО к таблицам из схемы выше.
4. ФИО преподавателей (teachers.full_name) выводить можно.
5. Всегда добавляй LIMIT 100.
6. Если вопрос непонятен — верни: UNKNOWN.

ПРИМЕР ПРАВИЛЬНОГО ОТВЕТА:
Вопрос: «Средний балл по дисциплине Математика в группе ПИ-101»
SQL:
SELECT AVG(g.grade)
FROM grades g
JOIN student_groups sg ON g.group_id = sg.id
WHERE sg.group_name = 'ПИ-101' AND g.subject = 'Математика'
LIMIT 100;

ФОРМАТ ОТВЕТА:
Верни ТОЛЬКО SQL-запрос в блоке ```sql ... ``` без объяснений.
"""

question = "Средний балл по дисциплине 'Математика' в группе 'ПИ-101'"

instruction = [
    {"role": "system", "content": SYSTEM_PROMPT},
    {"role": "user", "content": question},
]

payload = {
    "model": "GigaChat",
    "messages": instruction,
    "temperature": 0,
}

print(f"\nВопрос: {question}")
chat_response = requests.post(chat_url, headers=headers_chat, json=payload, verify=False)

if chat_response.status_code != 200:
    print(f"Ошибка запроса к модели: {chat_response.status_code}")
    print(chat_response.text)
    exit(1)

data = chat_response.json()
content = data["choices"][0]["message"]["content"]
print(f"\nSQL от модели:\n{content}")