import logging
import os

os.makedirs("logs", exist_ok=True)

# без encoding='utf-8' кириллица на Windows ломается
logging.basicConfig(
    filename=os.path.join("logs", "frontend.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8",
)


def log_question(q):
    logging.info(f"QUESTION: {q}")


def log_answer(q, sql, rows, err=None):
    if err:
        logging.info(f"ANSWER_ERR: q='{q}' | err='{err}'")
    else:
        logging.info(f"ANSWER_OK: q='{q}' | sql='{sql}' | rows={rows}")