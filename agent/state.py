"""Estado do grafo."""
from typing import Literal, TypedDict

from langchain_core.documents import Document


class Source(TypedDict):
    type: Literal["rag"]
    ref: str  # ex.: "politicas/ferias.md#abono"
    excerpt: str  # trecho usado no RAG


class AgentState(TypedDict, total=False):
    question: str
    employee_id: str | None
    session_id: str

    intent: Literal["policy", "oos"]
    blocked: bool
    block_reason: str
    escalate: bool

    docs: list[Document]

    answer: str
    sources: list[Source]
    retry_count: int
    judge_score: float

    # instrumentação de latência por etapa (ms)
    timings: dict[str, float]
    trace_id: str
