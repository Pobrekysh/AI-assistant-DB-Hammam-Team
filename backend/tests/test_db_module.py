import sys
import os

# Добавляем backend/ в путь поиска модулей,
# чтобы найти db.py (он лежит на уровень выше)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from db import execute_query, get_schema

print("=== СХЕМА БД ===")
print(get_schema())
print()

print("=== ТЕСТ 1: простой запрос ===")
result = execute_query("SELECT COUNT(*) FROM teachers")
print("Результат:", result)
print()

print("=== ТЕСТ 2: запрос с данными ===")
result = execute_query("SELECT full_name, department FROM teachers LIMIT 3")
print("Колонки:", result["columns"])
print("Строки:", result["rows"])
print()

print("=== ТЕСТ 3: ошибка ===")
result = execute_query("SELECT * FROM non_existent_table")
print("Ошибка:", result["error"])
print()