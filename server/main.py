"""Endpoint HTTP do agente. Rodar: uv run uvicorn server.main:app --port 8000"""
import json

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel, Field

from agent.graph import run_agent

app = FastAPI(title="Agente RH/TI")


class ChatRequest(BaseModel):
    question: str = Field(min_length=3, max_length=2000)
    employee_id: str | None = None
    session_id: str | None = None


class SourceOut(BaseModel):
    type: str
    ref: str
    excerpt: str


class ChatResponse(BaseModel):
    answer: str
    sources: list[SourceOut]
    intent: str | None
    blocked: bool
    trace_id: str
    session_id: str
    latency_ms: float
    timings: dict[str, float]


@app.post("/chat", response_model=ChatResponse)
def chat(body: ChatRequest, response: Response):
    try:
        result = run_agent(body.question, body.employee_id, body.session_id)
    except ConnectionError as e:
        raise HTTPException(503, detail={"message": "fonte indisponível", "source": str(e)})
    if result["blocked"]:
        response.status_code = 422
    response.headers["X-Latency-Breakdown"] = json.dumps(result["timings"])
    return result


@app.get("/health")
def health():
    return {"status": "ok"}
