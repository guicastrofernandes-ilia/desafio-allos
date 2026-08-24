"""Síntese final — modelo do provedor, citações obrigatórias, pt-BR."""
import time

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import synthesizer_llm
from ..state import AgentState
from .guard_input import _ms

SYSTEM = """Você é o assistente interno de RH/TI. Regras:
1. Responda SEMPRE em português (pt-BR), tom cordial e direto.
2. Use APENAS o contexto fornecido (trechos de políticas). Não invente números, prazos ou regras.
3. Cite a fonte no formato [fonte: arquivo] ao usar um trecho de política.
4. Se o contexto não responder a pergunta, diga que não tem a informação e sugira abrir um ticket de suporte.
5. Respostas curtas: no máximo 3 parágrafos."""

USER_TEMPLATE = """Pergunta: {question}

Contexto de políticas:
{docs}
"""


def synthesize(state: AgentState) -> dict:
    t0 = time.perf_counter()
    timings = dict(state.get("timings", {}))

    docs_txt = "\n\n".join(
        f"[{d.metadata.get('source', '?')}]\n{d.page_content}" for d in state.get("docs", [])
    ) or "(nenhum trecho recuperado)"

    resp = synthesizer_llm().invoke([
        SystemMessage(content=SYSTEM),
        HumanMessage(content=USER_TEMPLATE.format(
            question=state["question"], docs=docs_txt)),
    ])
    return {"answer": resp.content, "timings": {**timings, "synthesize": _ms(t0)}}


def fallback(state: AgentState) -> dict:
    """Sem informação / OOS / fonte falhou."""
    t0 = time.perf_counter()
    timings = dict(state.get("timings", {}))
    if state.get("rag_error"):
        answer = ("A base de conhecimento está indisponível no momento. "
                  "Posso ajudar abrindo um ticket para o suporte, ou tente novamente em instantes.")
    else:
        answer = ("Não tenho informação suficiente sobre isso nas políticas internas. "
                  "Posso abrir um ticket de suporte para você, ou reformular a pergunta sobre férias, "
                  "benefícios, home office ou equipamentos.")
    return {"answer": answer, "sources": state.get("sources", []),
            "timings": {**timings, "fallback": _ms(t0)}}


def escalate(state: AgentState) -> dict:
    """Tópico sensível → humano."""
    t0 = time.perf_counter()
    timings = dict(state.get("timings", {}))
    return {
        "answer": ("Esse é um tema sensível que merece atendimento humano. "
                   "Entre em contato direto com o RH (ramal 4400 ou rh@empresa.example) — "
                   "o atendimento é confidencial."),
        "sources": [],
        "timings": {**timings, "escalate": _ms(t0)},
    }
