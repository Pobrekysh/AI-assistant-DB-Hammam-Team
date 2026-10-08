from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class AskRequest (BaseModel):
    question: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    start = time.time()
    question = req.question.strip()

    def elapsed():
        return int((time.time() - start) * 1000)

    # 1. Логируем вопрос
    log_question(question)

    # 2. Получаем схему БД
    schema = get_schema()

    # 3. LLM → SQL
    llm_result = question_to_sql(question, schema)
    if llm_result["error"]:
        log_error(f"LLM: {llm_result['error']}")
        return AskResponse(
            question=question,
            error=llm_result["error"],
            elapsed_ms=elapsed(),
        )

    sql = llm_result["sql"]

    # 4. Валидация SQL
    ok, reason = validate_sql(sql)
    if not ok:
        log_blocked(sql, reason)
        return AskResponse(
            question=question,
            sql=sql,
            error=f"Запрос отклонён: {reason}",
            elapsed_ms=elapsed(),
        )

    # 5. Выполняем в БД
    db_result = execute_query(sql)
    log_sql(sql)

    if db_result["error"]:
        log_error(db_result["error"])
    else:
        log_result(len(db_result["rows"]), elapsed())

    # 6. Проверяем на "ничего не найдено"
    empty_reason = _check_empty_result(db_result, sql)
    if empty_reason:
        log_error(empty_reason)
        return AskResponse(
            question=question,
            sql=sql,
            error=empty_reason,
            elapsed_ms=elapsed(),
        )

    # 7. Строим объяснение
    explanation = _build_explanation(sql)

    return AskResponse(
        question=question,
        sql=sql,
        columns=db_result["columns"],
        rows=db_result["rows"],
        error=db_result["error"],
        explanation=explanation,
        elapsed_ms=elapsed(),
    )


def _build_explanation(sql: str) -> str:
    """Простое объяснение SQL: таблицы, JOIN, агрегаты."""
    sql_lower = sql.lower()
    parts = []

    tables = []
    for m in re.finditer(r"\bfrom\s+([a-z_]+)|\bjoin\s+([a-z_]+)", sql_lower):
        t = m.group(1) or m.group(2)
        if t and t not in tables:
            tables.append(t)
    parts.append(f"Таблицы: {', '.join(tables) if tables else '—'}")

    if "join" in sql_lower:
        parts.append("JOIN")
    if "count(" in sql_lower:
        parts.append("COUNT")
    if "avg(" in sql_lower:
        parts.append("AVG")
    if "sum(" in sql_lower:
        parts.append("SUM")
    if "group by" in sql_lower:
        parts.append("GROUP BY")
    if "order by" in sql_lower:
        parts.append("ORDER BY")
    if "limit" in sql_lower:
        parts.append("LIMIT")

    return " | ".join(parts)


def _check_empty_result(db_result: dict, sql: str) -> str | None:
    """
    Возвращает текст ошибки, если результат пустой.
    Иначе None.
    """
    if db_result["error"]:
        return None  # уже ошибка, обработаем отдельно

    rows = db_result["rows"]

    # Случай 1: пустой список строк
    if not rows:
        return "По вашему запросу ничего не найдено"

    # Случай 2: единственное значение 0 (COUNT) при наличии WHERE
    if len(rows) == 1 and len(rows[0]) == 1 and rows[0][0] == 0:
        if "where" in sql.lower():
            return (
                "По вашему запросу ничего не найдено. "
                "Возможно, такой кафедры, предмета, группы или программы нет в базе."
            )

    return None
