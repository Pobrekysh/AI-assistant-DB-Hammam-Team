import streamlit as st
import requests
import os
from dotenv import load_dotenv

from logger import log_question, log_answer

# Загружаем переменные окружения из .env
load_dotenv()

# Адрес бэкенда. Если Susliqq ещё не поднял /ask — используем MOCK_MODE
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"

# Настройка страницы
st.set_page_config(
    page_title="AI-ассистент БД университета",
    page_icon="🎓",
    layout="wide"
)

# Заголовок
st.title("🎓 AI-ассистент для работы с БД университета")
st.caption("Задайте вопрос - ассистент построит SQL-запрос и вернёт результат.")

# ===== Инициализация истории сообщений =====
if "messages" not in st.session_state:
    st.session_state.messages = []


# ===== Функция-заглушка (пока Susliqq не готов) =====
def mock_ask(question: str) -> dict:
    """Возвращает фейковый ответ, чтобы фронт можно было разрабатывать параллельно."""
    return {
        "sql": f"SELECT COUNT(*) FROM applications\nWHERE program = 'Экономика'\nAND year = 2026\nLIMIT 100;",
        "columns": ["count"],
        "rows": [[150]],
        "error": None,
        "explanation": "Использована таблица applications, фильтр по program и year, агрегат COUNT.",
        "page": 1,
        "total_pages": 1
    }


# ===== Функция реального запроса к бэкенду =====
def real_ask(question: str) -> dict:
    """Отправляет вопрос на /ask и возвращает JSON-ответ."""
    try:
        response = requests.post(
            f"{BACKEND_URL}/ask",
            json={"question": question},
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.ConnectionError:
        return {
            "sql": None,
            "columns": [],
            "rows": [],
            "error": f"Не удалось подключиться к бэкенду ({BACKEND_URL}). Проверь, запущен ли FastAPI.",
            "explanation": None,
            "page": 1,
            "total_pages": 1
        }
    except requests.exceptions.Timeout:
        return {
            "sql": None,
            "columns": [],
            "rows": [],
            "error": "Бэкенд не ответил за 30 секунд. Возможно, запрос слишком тяжёлый.",
            "explanation": None,
            "page": 1,
            "total_pages": 1
        }
    except Exception as e:
        return {
            "sql": None,
            "columns": [],
            "rows": [],
            "error": f"Ошибка запроса: {str(e)}",
            "explanation": None,
            "page": 1,
            "total_pages": 1
        }


# ===== Основная функция =====
def ask(question: str) -> dict:
    """В MOCK_MODE — заглушка, иначе — реальный запрос."""
    if MOCK_MODE:
        return mock_ask(question)
    return real_ask(question)


# ===== Боковая панель =====
with st.sidebar:
    st.header("⚙️ Настройки")
    st.write(
        f"**Режим:** {'🧪 MOCK (заглушка)' if MOCK_MODE else '🔌 REAL (бэкенд)'}")
    st.write(f"**Backend URL:** `{BACKEND_URL}`")

    if st.button("🗑️ Очистить историю"):
        st.session_state.messages = []
        st.rerun()

    st.divider()
    st.caption("Прототип для чемпионата Газпромбанка")


# ===== Отображение истории =====
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.write(msg["content"])
        else:
            # Ответ ассистента
            data = msg["content"]
            if data.get("error"):
                st.error(f"❌ {data['error']}")
            if data.get("sql"):
                st.markdown("**Сгенерированный SQL:**")
                st.code(data["sql"], language="sql")
            if data.get("rows"):
                st.markdown("**Результат:**")
                st.dataframe(data["rows"], use_container_width=True)
            if data.get("explanation"):
                with st.expander("💡 Как построен запрос"):
                    st.write(data["explanation"])


# ===== Поле ввода =====
question = st.chat_input(
    "Введите вопрос, например: Сколько заявлений на Экономику в 2026 году?")

if question:
    # 1. Добавляем сообщение пользователя
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user"):
        st.write(question)

    log_question(question)

    # 2. Показываем индикатор загрузки и получаем ответ
    with st.chat_message("assistant"):
        with st.spinner("Ассистент думает..."):
            data = ask(question)

        log_answer(
            question,
            data.get("sql", ""),
            len(data.get("rows", [])),
            data.get("error")
        )

        # 3. Отображаем ответ
        if data.get("error"):
            st.error(f"❌ {data['error']}")
        if data.get("sql"):
            st.markdown("**Сгенерированный SQL:**")
            st.code(data["sql"], language="sql")
        if data.get("rows"):
            st.markdown("**Результат:**")
            # Streamlit плохо переваривает rows без колонок — сделаем словарями
            if data.get("columns"):
                import pandas as pd
                df = pd.DataFrame(data["rows"], columns=data["columns"])
                st.dataframe(df, use_container_width=True,hide_index=True)
            else:
                st.dataframe(data["rows"], use_container_width=True,hide_index=True)
        if data.get("explanation"):
            with st.expander("💡 Как построен запрос"):
                st.write(data["explanation"])
    # 4. Сохраняем ответ в историю
    st.session_state.messages.append({"role": "assistant", "content": data})
