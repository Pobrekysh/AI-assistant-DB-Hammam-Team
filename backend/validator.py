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

# Whitelist КОЛОНОК по каждой таблице.
# password и passport_data НЕ включены — это персональные данные.
ALLOWED_COLUMNS = {
    "faculties": {"id", "name"},
    "teachers": {"id", "full_name", "department"},
    "student_groups": {"id", "group_name", "faculty_id"},
    "applications": {"id", "program_name", "application_year", "status"},
    "grades": {"id", "group_id", "subject", "grade", "semester"},
}

FORBIDDEN_KEYWORDS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "grant", "revoke", "copy", "vacuum", "analyze",
    "execute", "call", "do", "merge", "replace", "lock",
    "pg_sleep", "benchmark", "waitfor", "sleep",
    "--", "/*", "*/",
}

SQL_KEYWORDS = {
    "select", "from", "where", "join", "on", "and", "or",
    "as", "limit", "group", "by", "order", "desc", "asc",
    "having", "inner", "left", "right", "outer", "full",
    "count", "avg", "sum", "min", "max", "distinct",
    "ilike", "like", "in", "not", "null", "is", "between",
    "union", "all", "case", "when", "then", "else", "end",
}


def validate_sql(sql: str) -> Tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "Пустой SQL-запрос"

    sql_lower = sql.lower().strip()

    # 1. Только SELECT
    first_word = sql_lower.split()[0] if sql_lower.split() else ""
    if first_word != "select":
        return False, f"Разрешены только SELECT-запросы. Получено: {first_word.upper()}"

    # 2. Нет запрещённых ключевых слов
    for kw in FORBIDDEN_KEYWORDS:
        if kw in sql_lower:
            return False, f"Обнаружено запрещённое выражение: {kw}"

    # 3. Нет множественных запросов
    if sql_lower.rstrip(";").count(";") > 0:
        return False, "Множественные SQL-запросы запрещены"

    # 4. Проверка таблиц
    tables = extract_tables(sql_lower)
    if not tables:
        return False, "Не удалось определить таблицы в запросе"

    for t in tables:
        if t in BLACKLIST_TABLES:
            return False, f"Доступ к таблице '{t}' запрещён"
        if t not in WHITELIST_TABLES:
            return False, f"Таблица '{t}' не входит в разрешённый список"

    # 5. Проверка колонок
    allowed = set()
    for t in tables:
        allowed |= ALLOWED_COLUMNS.get(t, set())

    aliases = extract_aliases(sql_lower)
    columns = extract_columns(sql_lower)

    for col in columns:
        if col in SQL_KEYWORDS:
            continue
        if col in tables:
            continue
        if col in aliases:
            continue
        if len(col) == 1:
            continue
        if col not in allowed:
            return False, f"Колонка '{col}' не входит в разрешённый список"

    return True, ""


def extract_tables(sql_lower: str) -> set:
    tables = set()
    for m in re.finditer(r"\bfrom\s+([a-z_][a-z0-9_]*)", sql_lower):
        tables.add(m.group(1))
    for m in re.finditer(r"\bjoin\s+([a-z_][a-z0-9_]*)", sql_lower):
        tables.add(m.group(1))
    return tables


def extract_aliases(sql_lower: str) -> set:
    """Извлекает алиасы: FROM table alias / JOIN table alias."""
    aliases = set()
    for m in re.finditer(r"\b(?:from|join)\s+[a-z_][a-z0-9_]*\s+([a-z_][a-z0-9_]*)", sql_lower):
        alias = m.group(1)
        if alias not in SQL_KEYWORDS:
            aliases.add(alias)
    return aliases


def extract_columns(sql_lower: str) -> set:
    """Извлекает идентификаторы, исключая строковые литералы."""
    sql_clean = re.sub(r"'[^']*'", "", sql_lower)
    words = re.findall(r"\b[a-z_][a-z0-9_]*\b", sql_clean)
    tables = extract_tables(sql_clean)
    result = set()
    for w in words:
        if w in tables:
            continue
        result.add(w)
    return result