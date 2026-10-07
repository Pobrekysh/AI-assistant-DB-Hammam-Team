import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from llm import question_to_sql
from db import get_schema

schema = get_schema()
print("Схема загружена:")
print(schema)
print()

questions = [
    "Сколько заявлений подано на программу 'Экономика' в 2026 году?",
    "Сколько преподавателей на кафедре 'Математика'?",
    "Средний балл по дисциплине 'Предмет_1'",
    "Привет, как дела?",  # не по теме — должно вернуть UNKNOWN или ошибку
]

for q in questions:
    result = question_to_sql(q, schema)
    print(f"❓ {q}")
    print(f"   SQL: {result['sql']}")
    print(f"   Ошибка: {result['error']}")
    print()