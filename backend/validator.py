import re
from typing import Tuple

# только эти таблицы разрешены
OK_TABLES = {"faculties", "teachers", "student_groups", "applications", "grades"}

# системные и чужие — запрещены
BAD_TABLES = {"users", "passwords", "auth", "sessions", "personal_data",
              "pg_shadow", "pg_user"}

# password / passport_data не включены — это PII
OK_COLUMNS = {
    "faculties":      {"id", "name"},
    "teachers":       {"id", "full_name", "department"},
    "student_groups": {"id", "group_name", "faculty_id"},
    "applications":   {"id", "program_name", "application_year", "status"},
    "grades":         {"id", "group_id", "subject", "grade", "semester"},
}

# ищем подстрокой — ловит и "drop", и "drop_table"
BAD_WORDS = {
    "insert", "update", "delete", "drop", "alter", "create",
    "truncate", "grant", "revoke", "copy", "vacuum", "analyze",
    "execute", "call", "do", "merge", "replace", "lock",
    "pg_sleep", "benchmark", "waitfor", "sleep",
    "--", "/*", "*/",
}

# служебные слова SQL — не колонки, при проверке пропускаем
SQL_WORDS = {
    "select", "from", "where", "join", "on", "and", "or", "as", "limit",
    "group", "by", "order", "desc", "asc", "having",
    "inner", "left", "right", "outer", "full",
    "count", "avg", "sum", "min", "max", "distinct",
    "ilike", "like", "in", "not", "null", "is", "between",
    "union", "all", "case", "when", "then", "else", "end",
}


def validate_sql(sql: str) -> Tuple[bool, str]:
    if not sql or not sql.strip():
        return False, "Пустой SQL-запрос"

    low = sql.lower().strip()

    first = low.split()[0] if low.split() else ""
    if first != "select":
        return False, f"Разрешены только SELECT. Получено: {first.upper()}"

    for w in BAD_WORDS:
        if w in low:
            return False, f"Запрещённое выражение: {w}"

    if low.rstrip(";").count(";") > 0:
        return False, "Множественные SQL-запросы запрещены"

    tables = get_tables(low)
    if not tables:
        return False, "Не удалось определить таблицы"

    for t in tables:
        if t in BAD_TABLES:
            return False, f"Таблица '{t}' запрещена"
        if t not in OK_TABLES:
            return False, f"Таблица '{t}' не в whitelist"

    ok = set()
    for t in tables:
        ok |= OK_COLUMNS.get(t, set())

    aliases = get_aliases(low)
    for c in get_words(low):
        if c in SQL_WORDS or c in tables or c in aliases or len(c) == 1:
            continue
        if c not in ok:
            return False, f"Колонка '{c}' не в whitelist"

    return True, ""


def get_tables(low: str) -> set:
    t = set()
    for m in re.finditer(r"\bfrom\s+([a-z_][a-z0-9_]*)", low):
        t.add(m.group(1))
    for m in re.finditer(r"\bjoin\s+([a-z_][a-z0-9_]*)", low):
        t.add(m.group(1))
    return t


def get_aliases(low: str) -> set:
    """FROM grades g / JOIN student_groups sg → {g, sg}"""
    a = set()
    for m in re.finditer(r"\b(?:from|join)\s+[a-z_][a-z0-9_]*\s+([a-z_][a-z0-9_]*)", low):
        alias = m.group(1)
        if alias not in SQL_WORDS:
            a.add(alias)
    return a


def get_words(low: str) -> set:
    # убираем строки в кавычках — это значения, не колонки
    clean = re.sub(r"'[^']*'", "", low)
    words = re.findall(r"\b[a-z_][a-z0-9_]*\b", clean)
    tables = get_tables(clean)
    return {w for w in words if w not in tables}