import streamlit as st
import requests
import os
import pandas as pd
from dotenv import load_dotenv

from logger import log_question, log_answer

load_dotenv()

BACKEND = os.getenv("BACKEND_URL", "http://localhost:8000")
MOCK = os.getenv("MOCK_MODE", "false").lower() == "true"

st.set_page_config(page_title="AI-ассистент БД", page_icon="🎓", layout="wide")
st.title("🎓 AI-ассистент для работы с БД университета")
st.caption("Задайте вопрос — ассистент построит SQL и вернёт результат.")

if "messages" not in st.session_state:
    st.session_state.messages = []


def _mock(q: str) -> dict:
    return {
        "sql": "SELECT COUNT(*) FROM applications WHERE program_name ILIKE '%Экономика%' LIMIT 100",
        "columns": ["count"],
        "rows": [[150]],
        "error": None,
        "explanation": "MOCK-режим",
    }


def _ask(q: str) -> dict:
    try:
        r = requests.post(f"{BACKEND}/ask", json={"question": q}, timeout=30)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"sql": None, "columns": [], "rows": [], "error": None,
                "explanation": None,
                "error": f"Бэкенд недоступен ({BACKEND}). Запущен ли FastAPI?"}
    except requests.exceptions.Timeout:
        return {"sql": None, "columns": [], "rows": [], "error": None,
                "explanation": None,
                "error": "Бэкенд не ответил за 30 секунд"}
    except Exception as e:
        return {"sql": None, "columns": [], "rows": [], "error": None,
                "explanation": None,
                "error": f"Ошибка запроса: {e}"}


def ask(q: str) -> dict:
    return _mock(q) if MOCK else _ask(q)


def render(d: dict):
    if d.get("error"):
        st.error(f"❌ {d['error']}")
    if d.get("sql"):
        st.markdown("**SQL:**")
        st.code(d["sql"], language="sql")
    if d.get("rows"):
        st.markdown("**Результат:**")
        if d.get("columns"):
            st.dataframe(pd.DataFrame(d["rows"], columns=d["columns"]),
                         use_container_width=True, hide_index=True)
        else:
            st.dataframe(d["rows"], use_container_width=True, hide_index=True)
    if d.get("explanation"):
        with st.expander("💡 Как построен запрос"):
            st.text(d["explanation"])


# боковая панель
with st.sidebar:
    st.header("⚙️ Настройки")
    st.write(f"**Режим:** {'🧪 MOCK' if MOCK else '🔌 REAL'}")
    st.write(f"**Backend:** `{BACKEND}`")
    if st.button("🗑️ Очистить историю"):
        st.session_state.messages = []
        st.rerun()
    st.caption("Прототип для чемпионата Газпромбанка")


# история сообщений
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            render(msg["content"])


# поле ввода
q = st.chat_input("Введите вопрос…")

if q:
    st.session_state.messages.append({"role": "user", "content": q})
    with st.chat_message("user"):
        st.write(q)

    log_question(q)

    with st.chat_message("assistant"):
        with st.spinner("Думаю…"):
            d = ask(q)

        log_answer(q, d.get("sql", ""), len(d.get("rows", [])), d.get("error"))
        render(d)

    st.session_state.messages.append({"role": "assistant", "content": d})
