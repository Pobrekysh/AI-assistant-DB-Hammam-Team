import logging
import os

os.makedirs("logs", exist_ok=True)

logger = logging.getLogger("chat")
logger.setLevel(logging.INFO)

# при повторном импорте модуля handlers дублируются
if not logger.handlers:
    # encoding обязателен: без него кириллица на Windows валится
    fh = logging.FileHandler("logs/queries.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(fh)


def log_question(q):
    logger.info(f"QUESTION: {q}")


def log_sql(sql):
    logger.info(f"SQL: {sql}")


def log_blocked(sql, reason):
    logger.warning(f"BLOCKED: {sql} | {reason}")


def log_error(err):
    logger.error(f"ERROR: {err}")


def log_result(rows, ms):
    logger.info(f"RESULT: rows={rows}, ms={ms}")