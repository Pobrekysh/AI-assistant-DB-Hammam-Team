# AI-ассистент для работы с БД университета

Чат-ассистент, который превращает запросы в SQL-запросы к PostgreSQL и возвращает результаты в виде таблицы.

## Команда
**Hammam_Team**
- **Pobrekysh(кэп)** — фронтенд, интеграция, Docker, Ngrok
- **Billy-Debil** — база данных, SQL, безопасность
- **Susliqq** — бэкенд, LLM, валидация

## Стек

- PostgreSQL 15
- Python 3.11
- FastAPI (бэкенд)
- Streamlit (фронтенд)
- OpenAI / GigaChat (LLM)

## Быстрый старт

```bash
# 1. Клонировать репозиторий
git clone git@github.com:ТВОЙ_НИК/AI-assistant-DB-Hammam-Team.git
cd AI-assistant-DB-Hammam-Team

# 2. Создать .env
cp .env.example .env
# отредактировать .env, вставить API-ключ

# 3. Установить зависимости
pip install -r backend/requirements.txt
pip install -r frontend/requirements.txt

# 4. Запустить PostgreSQL (см. db/init.sql)

# 5. Запустить бэкенд
cd backend && uvicorn main:app --reload --port 8000

# 6. Запустить фронтенд (в новом терминале)
cd frontend && streamlit run app.py --server.port 8501
