import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

URL = "http://localhost:8000/ask"

QUESTIONS = [
    "Сколько преподавателей на кафедре математика?",
    "Сколько заявлений в 2026 году?",
    "Покажи всех преподавателей",
    "Сколько групп на факультете?",
    "Средний балл по предмету Предмет_1",
]


def ask(question):
    start = time.time()
    try:
        r = requests.post(URL, json={"question": question}, timeout=60)
        data = r.json()
        elapsed = time.time() - start
        return (question, elapsed, data.get("error"))
    except Exception as e:
        return (question, time.time() - start, str(e))


print(f"Отправляю {len(QUESTIONS)} запросов одновременно...")
start = time.time()

with ThreadPoolExecutor(max_workers=5) as executor:
    results = list(executor.map(ask, QUESTIONS))

total = time.time() - start

for q, t, err in results:
    print(f"  [{t:.2f}с] {q[:50]} → {err or 'OK'}")

print(f"\nВсего времени: {total:.2f} секунд")
print(f"Среднее на запрос: {total / len(QUESTIONS):.2f} секунд")