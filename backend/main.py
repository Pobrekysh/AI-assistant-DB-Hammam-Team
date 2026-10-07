from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()

class AskRequest (BaseModel):
    question :str


@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ask")
def ask(req:AskRequest):
    return {  "question": req.question,
        "sql": "SELECT 1;",
        "rows": [[1]],
        "error": None}