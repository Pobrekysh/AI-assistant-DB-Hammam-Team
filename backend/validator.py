import re
from typing import Tuple

WHITELIST_TABLES = {
    "faculties",
    "teachers",
    "student_groups",
    "applications",
    "grades",
}

BLACKLIST_TABLES = {
    "users", "passwords", "auth", "sessions",
    "personal_data", "pg_shadow", "pg_user",
}

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "grant", "revoke", "copy", "vacuum", "analyze",
    "execute", "call", "do", "merge", "replace", "lock",
    "pg_sleep", "benchmark", "waitfor", "sleep",
    "--", "/*", "*/",
}


def validate_sql(sql: str) -> Tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "Пустой SQL-запрос"

    sql_lower = sql.lower().strip()

    first_word = sql_lower.split()[0] if sql_lower.split() else ""
    if first_word != "select":
        return False, f"Разрешены только SELECT-запросы. Получено: {first_word.upper()}"

    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_lower:
            return False, f"Обнаружено запрещённое выражение: {kw}"

    if sql_lower.rstrip(";").count(";") > 0:
        return False, "Множественные SQL-запросы запрещены"

    tables = extract_tables(sql_lower)
    if not tables:
        return False, "Не удалось определить таблицы в запросе"

    for t in tables:
        if t in BLACKLIST_TABLES:
            return False, f"Доступ к таблице '{t}' запрещён"
        if t not in WHITELIST_TABLES:
            return False, f"Таблица '{t}' не входит в разрешённый список"

    return True, ""


def extract_tables(sql_lower: str) -> set:
    tables = set()
    for match in re.finditer(r"\bfrom\s+([a-z_][a-z0-9_]*)", sql_lower):
        tables.add(match.group(1))
    for match in re.finditer(r"\bjoin\s+([a-z_][a-z0-9_]*)", sql_lower):
        tables.add(match.group(1))
    return tables