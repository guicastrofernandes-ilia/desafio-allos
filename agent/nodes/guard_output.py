"""Guardrail de saída — verificação determinística + LLM-judge leve."""
import json
import logging
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from ..config import get_settings
from ..llm import judge_llm
from ..state import AgentState
from .guard_input import _ms

logger = logging.getLogger(__name__)

PROMPT = """Avalie se a resposta está alinhada com o contexto.

Pergunta: {question}
Contexto: {context}
Resposta: {answer}

Responda APENAS JSON: {{"score": 0.0-1.0, "problems": ["..."]}}"""


def _numbers_in(text: str) -> set[str]:
    return set(re.findall(r"\d+", text))


def guard_output(state: AgentState) -> dict:
    t0 = time.perf_counter()
    s = get_settings()
    timings = dict(state.get("timings", {}))

    if state.get("intent") == "oos" or state.get("escalate") or state.get("rag_error"):
        return {"judge_score": 1.0, "timings": {**timings, "guard_output": _ms(t0)}}

    context = "\n".join(
        [d.page_content[:400] for d in state.get("docs", [])]
    )[:4000]

    answer = state.get("answer", "")
    context_nums = _numbers_in(context)
    answer_nums = _numbers_in(answer)

    score = 0.5
    if context_nums and answer_nums and answer_nums.issubset(context_nums):
        score = 0.9
    elif context_nums and answer_nums:
        overlap = answer_nums & context_nums
        if overlap and len(overlap) >= len(answer_nums) * 0.5:
            score = 0.8

    if score < 0.8:
        try:
            raw = str(judge_llm().invoke([
                SystemMessage(content="Você é um avaliador de respostas."),
                HumanMessage(content=PROMPT.format(
                    question=state.get("question", ""), context=context, answer=answer)),
            ]).content)
            m = re.search(r"\{.*\}", raw, re.DOTALL)
            parsed = json.loads(m.group(0)) if m else {}
            score = float(parsed.get("score", 0.5))
        except Exception:
            score = 0.5
        logger.info("guard_output judge=%.2f question=%s", score, state.get("question", "")[:50])

    out: dict = {"judge_score": score, "timings": {**timings, "guard_output": _ms(t0)}}
    if score < s.guard_output_threshold:
        out["answer"] = (
            "Não consegui validar a resposta com as fontes disponíveis. "
            "Para garantir informação correta, abra um ticket de suporte ou consulte o RH."
        )
        out["sources"] = []
    return out
