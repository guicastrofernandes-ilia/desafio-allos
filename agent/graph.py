"""Grafo LangGraph — montagem e compilação com checkpointer SQLite."""
import sqlite3
import time
import uuid

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from .config import get_settings
from .nodes.classify import classify
from .nodes.guard_input import guard_input
from .nodes.guard_output import guard_output
from .nodes.rag import rag_node
from .nodes.synthesize import escalate, fallback, synthesize
from .state import AgentState


def _route_after_guard(state: AgentState) -> str:
    if state.get("blocked"):
        return "respond_blocked"
    if state.get("escalate"):
        return "escalate"
    return "classify"


def _route_after_classify(state: AgentState) -> str:
    intent = state.get("intent", "oos")
    return {"policy": "rag", "oos": "fallback"}[intent]


def _route_after_rag(state: AgentState) -> str:
    if not state.get("docs") and not state.get("rag_error"):
        return "fallback"
    return "synthesize"


def build_graph(checkpointer: SqliteSaver | None = None):
    g = StateGraph(AgentState)
    g.add_node("guard_input", guard_input)
    g.add_node("classify", classify)
    g.add_node("rag", rag_node)
    g.add_node("synthesize", synthesize)
    g.add_node("guard_output", guard_output)
    g.add_node("fallback", fallback)
    g.add_node("escalate", escalate)
    g.add_node("respond_blocked", lambda s: {
        "answer": s.get("block_reason", "Pergunta bloqueada."),
        "sources": [],
    })

    g.add_edge(START, "guard_input")
    g.add_conditional_edges("guard_input", _route_after_guard,
                            {"respond_blocked": "respond_blocked", "escalate": "escalate", "classify": "classify"})
    g.add_conditional_edges("classify", _route_after_classify,
                            {"rag": "rag", "fallback": "fallback"})
    g.add_conditional_edges("rag", _route_after_rag,
                            {"fallback": "fallback", "synthesize": "synthesize"})
    g.add_edge("synthesize", "guard_output")
    g.add_edge("guard_output", END)
    g.add_edge("fallback", END)
    g.add_edge("escalate", END)
    g.add_edge("respond_blocked", END)
    return g.compile(checkpointer=checkpointer)


_graph = None


def get_graph():
    global _graph
    if _graph is None:
        s = get_settings()
        conn = sqlite3.connect(s.checkpoint_db, check_same_thread=False)
        _graph = build_graph(SqliteSaver(conn))
    return _graph


def run_agent(question: str, employee_id: str | None = None, session_id: str | None = None) -> dict:
    """Executa o agente ponta a ponta. Retorna answer, sources, timings, latency_ms."""
    t0 = time.perf_counter()
    session_id = session_id or str(uuid.uuid4())
    graph = get_graph()
    result = graph.invoke(
        {
            "question": question,
            "employee_id": employee_id,
            "session_id": session_id,
            "trace_id": str(uuid.uuid4()),
            "timings": {},
            "sources": [],
            "docs": [],
            "retry_count": 0,
        },
        config={"configurable": {"thread_id": session_id}},
    )
    total_ms = round((time.perf_counter() - t0) * 1000, 1)
    return {
        "answer": result.get("answer", ""),
        "sources": result.get("sources", []),
        "intent": result.get("intent"),
        "blocked": result.get("blocked", False),
        "trace_id": result.get("trace_id"),
        "session_id": session_id,
        "timings": result.get("timings", {}),
        "latency_ms": total_ms,
    }
