import os
import psycopg2
from psycopg2.extras import RealDictCursor
from dotenv import load_dotenv

load_dotenv()

DB = {
    "host": os.getenv("DB_HOST"),
    "port": os.getenv("DB_PORT"),
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "connect_timeout": 5,
}

TIMEOUT = 5000   # ms
LIMIT = 100


def run_sql(sql: str, limit: int = LIMIT) -> dict:
    conn = None
    try:
        conn = psycopg2.connect(**DB)
        # без этого кириллица на Windows приходит фигней
        conn.set_client_encoding("UTF8")
        conn.set_session(readonly=True, autocommit=False)

        cur = conn.cursor(cursor_factory=RealDictCursor)
        cur.execute(f"SET statement_timeout = {TIMEOUT}")

        # ; в конце мешает добавить LIMIT
        sql = sql.strip().rstrip(";")
        if "limit" not in sql.lower():
            sql += f" LIMIT {limit}"

        cur.execute(sql)
        rows = cur.fetchall()
        cols = [d[0] for d in cur.description] if cur.description else []
        data = [[row[c] for c in cols] for row in rows]

        # Decimal ломает JSON и даёт 3.4580000000000000
        from decimal import Decimal
        out = []
        for row in data:
            new = []
            for v in row:
                if v is None:
                    new.append(v)
                elif isinstance(v, Decimal):
                    new.append(round(float(v), 2))
                elif not isinstance(v, (int, float, str, bool)):
                    new.append(str(v))
                else:
                    new.append(v)
            out.append(new)

        conn.rollback()
        return {"columns": cols, "rows": out, "error": None}

    except psycopg2.errors.QueryCanceled:
        return {"columns": [], "rows": [], "error": "Запрос выполнялся слишком долго"}
    except psycopg2.Error as e:
        return {"columns": [], "rows": [], "error": f"Ошибка БД: {str(e).strip()}"}
    except Exception as e:
        return {"columns": [], "rows": [], "error": f"Неизвестная ошибка: {str(e)}"}
    finally:
        if conn:
            conn.close()


def get_schema() -> str:
    conn = None
    try:
        conn = psycopg2.connect(**DB)
        conn.set_client_encoding("UTF8")
        cur = conn.cursor()

        # password/passport_data не отдаём модели
        cur.execute("""
            SELECT table_name, column_name, data_type
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND column_name NOT IN ('password', 'passport_data', 'passport', 'pwd', 'secret')
            ORDER BY table_name, ordinal_position
        """)
        rows = cur.fetchall()

        tables = {}
        for t, c, d in rows:
            tables.setdefault(t, []).append(f"{c} ({d})")

        lines = [f"- {t}: {', '.join(cs)}" for t, cs in tables.items()]

        # без FK модель выдумывает связи
        cur.execute("""
            SELECT tc.table_name, kcu.column_name, ccu.table_name, ccu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
            JOIN information_schema.constraint_column_usage ccu
              ON ccu.constraint_name = tc.constraint_name
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = 'public'
        """)
        fks = cur.fetchall()

        if fks:
            lines.append("")
            lines.append("СВЯЗИ:")
            for ft, fc, tt, tc in fks:
                lines.append(f"- {ft}.{fc} → {tt}.{tc}")

        return "\n".join(lines)

    except Exception as e:
        return f"Ошибка получения схемы: {e}"
    finally:
        if conn:
            conn.close()