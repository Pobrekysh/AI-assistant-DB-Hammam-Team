import time
import re
from datetime import datetime

from fastapi import FastAPI
from pydantic import BaseModel

from db import run_sql, get_schema
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
    t0 = time.time()
    q = req.question.strip()

    def ms():
        return int((time.time() - t0) * 1000)

    log_question(q)

    # 1. LLM -> SQL
    schema = get_schema()
    llm = question_to_sql(q, schema)
    if llm["error"]:
        log_error(f"LLM: {llm['error']}")
        return AskResponse(question=q, error=llm["error"], elapsed_ms=ms())

    sql = llm["sql"]

    # 2. валидатор
    ok, reason = validate_sql(sql)
    if not ok:
        log_blocked(sql, reason)
        return AskResponse(question=q, sql=sql,
                           error=f"Запрос отклонён: {reason}", elapsed_ms=ms())

    # 3. выполняем
    res = run_sql(sql)
    log_sql(sql)

    if res["error"]:
        log_error(res["error"])
    else:
        log_result(len(res["rows"]), ms())

    # 4. пустой результат — не показываем голый ноль
    empty = _empty_reason(res, sql)
    if empty:
        log_error(empty)
        return AskResponse(question=q, sql=sql, error=empty, elapsed_ms=ms())

    return AskResponse(
        question=q,
        sql=sql,
        columns=res["columns"],
        rows=res["rows"],
        error=res["error"],
        explanation=_explain(sql),
        elapsed_ms=ms(),
    )


def _explain(sql: str) -> str:
    low = sql.lower()
    parts = []

    tables = []
    for m in re.finditer(r"\bfrom\s+([a-z_]+)|\bjoin\s+([a-z_]+)", low):
        t = m.group(1) or m.group(2)
        if t and t not in tables:
            tables.append(t)
    parts.append(f"Таблицы: {', '.join(tables) or '—'}")

    for kw, name in [("join", "JOIN"), ("count(", "COUNT"), ("avg(", "AVG"),
                     ("sum(", "SUM"), ("group by", "GROUP BY"),
                     ("order by", "ORDER BY"), ("limit", "LIMIT")]:
        if kw in low:
            parts.append(name)

    return " | ".join(parts)


def _empty_reason(res: dict, sql: str) -> str | None:
    if res["error"]:
        return None

    rows = res["rows"]
    if not rows:
        return "По вашему запросу ничего не найдено"

    # COUNT(*) = 0 при наличии WHERE — скорее всего фильтр не нашёл
    if len(rows) == 1 and len(rows[0]) == 1 and rows[0][0] == 0:
        if "where" in sql.lower():
            return ("По вашему запросу ничего не найдено. "
                    "Возможно, такой кафедры, предмета, группы или программы нет в базе.")

    return None
