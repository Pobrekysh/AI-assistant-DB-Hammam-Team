import time
import re
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

from db import execute_query, get_schema
from llm import question_to_sql
from validator import validate_sql
from logger import log_question, log_sql, log_blocked, log_error, log_result


app = FastAPI(title="University Chat API")


class AskRequest(BaseModel):
    question: str


class AskResponse(BaseModel):
    question: str
    sql: str | None = None
    columns: list = []
    rows: list = []
    error: str | None = None
    explanation: str | None = None
    elapsed_ms: int = 0


@app.get("/health")
def health():
    return {"status": "ok", "time": datetime.now().isoformat()}


@app.post("/ask", response_model=AskResponse)
def ask(req: AskRequest):
    start = time.time()
    question = req.question.strip()

    def elapsed():
        return int((time.time() - start) * 1000)

    log_question(question)

    schema = get_schema()
    llm_result = question_to_sql(question, schema)
    if llm_result["error"]:
        log_error(f"LLM: {llm_result['error']}")
        return AskResponse(
            question=question,
            error=llm_result["error"],
            elapsed_ms=elapsed(),
        )

    sql = llm_result["sql"]

    ok, reason = validate_sql(sql)
    if not ok:
        log_blocked(sql, reason)
        return AskResponse(
            question=question,
            sql=sql,
            error=f"Запрос отклонён: {reason}",
            elapsed_ms=elapsed(),
        )

    db_result = execute_query(sql)
    log_sql(sql)

    if db_result["error"]:
        log_error(db_result["error"])
    else:
        log_result(len(db_result["rows"]), elapsed())

    empty_reason = _check_empty_result(db_result, sql, question)
    if empty_reason:
        log_error(empty_reason)
        return AskResponse(
            question=question,
            sql=sql,
            error=empty_reason,
            elapsed_ms=elapsed(),
        )

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


def _check_empty_result(db_result: dict, sql: str, question: str = "") -> str | None:
    if db_result["error"]:
        return None

    rows = db_result["rows"]

    if not rows:
        return "По вашему запросу ничего не найдено"

    if len(rows) == 1 and len(rows[0]) == 1 and rows[0][0] == 0:
        if "where" in sql.lower():
            return (
                "По вашему запросу ничего не найдено. "
                "Возможно, такой кафедры, предмета, группы или программы нет в базе."
            )

    return None