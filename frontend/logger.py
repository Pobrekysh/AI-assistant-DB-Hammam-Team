import logging
import os
from datetime import datetime

LOG_DIR = "logs"
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    filename=os.path.join(LOG_DIR, "frontend.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)


def log_question(question: str):
    logging.info(f"QUESTION: {question}")


def log_answer(question: str, sql: str, rows_count: int, error: str = None):
    if error:
        logging.info(f"ANSWER_ERROR: q='{question}' | error='{error}'")
    else:
        logging.info(
            f"ANSWER_OK: q='{question}' | sql='{sql}' | rows={rows_count}")
