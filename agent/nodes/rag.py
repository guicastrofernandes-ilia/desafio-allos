"""Nó RAG — retrieve + corte por distância + re-query 1x se docs ruins."""
import time

from langchain_core.documents import Document

from rag.store import retrieve
from ..state import AgentState, Source
from .guard_input import _ms

# score do Chroma (distância L2): menor = melhor. Acima disto, doc é irrelevante.
MAX_DISTANCE = 1.6


def rag_node(state: AgentState) -> dict:
    t0 = time.perf_counter()
    timings = dict(state.get("timings", {}))
    retry = state.get("retry_count", 0)

    try:
        hits = retrieve(state["question"], k=6)
    except Exception as e:  # índice ausente/corrompido
        return {
            "docs": [],
            "sources": [],
            "timings": {**timings, "rag": _ms(t0)},
            "rag_error": str(e),
        }

    good: list[Document] = _dedupe([d for d, dist in hits if dist <= MAX_DISTANCE])[:3]

    if not good and retry == 0:
        # re-query: simplifica a pergunta removendo pergunta secundária
        simplified = state["question"].split("?")[0].split(" e ")[0] + "?"
        hits = retrieve(simplified, k=6)
        good = _dedupe([d for d, dist in hits if dist <= MAX_DISTANCE])[:3]
        retry = 1

    sources: list[Source] = [
        {
            "type": "rag",
            "ref": d.metadata.get("source", "desconhecido"),
            "excerpt": d.page_content[:200].strip(),
        }
        for d in good
    ]
    return {
        "docs": good,
        "sources": sources,
        "retry_count": retry,
        "timings": {**timings, "rag": _ms(t0)},
    }


def _dedupe(docs: list[Document]) -> list[Document]:
    """Remove chunks repetidos (mesmo conteúdo) que o Chroma pode devolver no top-k."""
    seen: set[str] = set()
    out: list[Document] = []
    for d in docs:
        key = d.metadata.get("source", "") + "\x00" + d.page_content
        if key not in seen:
            seen.add(key)
            out.append(d)
    return out
