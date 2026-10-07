import logging
import os
from datetime import datetime

# Создаём папку для логов, если её нет
os.makedirs("logs", exist_ok=True)

# Настраиваем логгер
logger = logging.getLogger("university_chat")
logger.setLevel(logging.INFO)

# Чтобы не добавлялись дубли при повторных импортах
if not logger.handlers:
    handler = logging.FileHandler("logs/queries.log", encoding="utf-8")
    formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")
    handler.setFormatter(formatter)
    logger.addHandler(handler)


def log_question(question: str):
    """Логируем вопрос пользователя."""
    logger.info(f"QUESTION: {question}")


def log_sql(sql: str):
    """Логируем SQL, который сгенерировала LLM."""
    logger.info(f"SQL: {sql}")


def log_blocked(sql: str, reason: str):
    """Логируем заблокированный валидатором SQL."""
    logger.warning(f"BLOCKED: {sql} | {reason}")


def log_error(error: str):
    """Логируем ошибку."""
    logger.error(f"ERROR: {error}")


def log_result(rows_count: int, elapsed_ms: int):
    """Логируем успешный результат."""
    logger.info(f"RESULT: rows={rows_count}, elapsed_ms={elapsed_ms}")