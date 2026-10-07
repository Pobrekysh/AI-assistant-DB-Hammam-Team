import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB_CONFIG = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "connect_timeout": 5,
    "client_encoding": "utf8",
}

STATEMENT_TIMEOUT_MS = 5000  # 5 секунд
DEFAULT_LIMIT = 100


def execute_query(sql: str, limit: int = DEFAULT_LIMIT) -> dict:
    """
    Выполняет SELECT-запрос.
    Возвращает: {"columns": [...], "rows": [...], "error": None}
    или:        {"columns": [], "rows": [], "error": "..."}
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('UTF8')
        conn.set_session(readonly=True, autocommit=False)

        cursor = conn.cursor(cursor_factory=RealDictCursor)
        cursor.execute(f"SET statement_timeout = {STATEMENT_TIMEOUT_MS}")

        # Добавляем LIMIT, если его нет
        sql_clean = sql.strip().rstrip(";")
        if "limit" not in sql_clean.lower():
            sql_clean += f" LIMIT {limit}"

        cursor.execute(sql_clean)

        rows = cursor.fetchall()
        columns = [desc[0] for desc in cursor.description] if cursor.description else []
        rows_as_lists = [[row[col] for col in columns] for row in rows]

        # Приводим несериализуемые типы к строкам
        from decimal import Decimal
        rows_serializable = []
        for row in rows_as_lists:
            new_row = []
            for v in row:
                if v is None:
                    new_row.append(v)
                elif isinstance(v, Decimal):
                    new_row.append(round(float(v), 2))
                elif not isinstance(v, (int, float, str, bool)):
                    new_row.append(str(v))
                else:
                    new_row.append(v)
            rows_serializable.append(new_row)

        conn.rollback()  # ничего не меняли
        return {"columns": columns, "rows": rows_serializable, "error": None}

    except psycopg2.errors.QueryCanceled:
        return {"columns": [], "rows": [], "error": "Запрос выполнялся слишком долго и был отменён"}
    except psycopg2.Error as e:
        return {"columns": [], "rows": [], "error": f"Ошибка БД: {str(e).strip()}"}
    except Exception as e:
        return {"columns": [], "rows": [], "error": f"Неизвестная ошибка: {str(e)}"}
    finally:
        if conn:
            conn.close()


def get_schema() -> str:
    """
    Возвращает схему БД в виде текста для промпта LLM.
    Читает таблицы и колонки из information_schema.
    """
    conn = None
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        conn.set_client_encoding('UTF8')
        cursor = conn.cursor()
        cursor.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
            ORDER BY table_name, ordinal_position
        """)
        rows = cursor.fetchall()

        schema = {}
        for table, column, dtype in rows:
            schema.setdefault(table, []).append(f"{column} ({dtype})")

        lines = []
        for table, cols in schema.items():
            lines.append(f"- {table}: {', '.join(cols)}")
        return "\n".join(lines)

    except Exception as e:
        return f"Ошибка получения схемы: {e}"
    finally:
        if conn:
            conn.close()