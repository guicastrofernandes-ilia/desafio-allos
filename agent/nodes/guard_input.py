"""Guardrail de entrada — determinístico, sem LLM (~0ms)."""
import re
import time

from ..state import AgentState

INJECTION_PATTERNS = [
    r"ignore\s+(as\s+)?(instru[çc][õo]es|previous|all)",
    r"system\s*:",
    r"</?instructions>",
    r"mostre?\s+(o\s+)?(seu\s+)?prompt",
    r"(você|voce)\s+[ée]\s+agora",
    r"reveal\s+(your\s+)?(prompt|instructions)",
    r"dan\s+mode|jailbreak",
]
SENSITIVE_TOPICS = [
    "demissão", "demissao", "demitido", "demitida", "demitir", "assédio", "assedio",
    "sindicato", "processo trabalhista", "justa causa", "rescisão", "rescisao",
    "quem vai ser demitido", "corte de pessoal", "layoff",
]
PII_PATTERNS = [
    (re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b"), "[CPF]"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "[CARTAO]"),
]
PT_MARKERS = {
    "o", "a", "de", "que", "e", "do", "da", "em", "um", "para", "é", "com",
    "não", "uma", "os", "no", "se", "na", "por", "mais", "as", "dos", "como",
    "meu", "minha", "férias", "você", "qual", "quanto", "quantos", "posso",
    "quem", "vai", "ser", "tem", "pode", "sobre", "sua", "seu",
    "eu", "vou", "amanhã", "demitido", "hoje", "ontem", "estou", "tenho", "me",
    "abrir", "abre", "ticket", "saldo", "política", "política",
    "existem", "existe", "aberto", "abertos", "aberta", "abertas", "abri",
    "está", "estão", "são", "faço", "fazer", "qual", "qualquer", "algum",
    "alguma", "alguns", "algumas", "preciso", "gostaria", "quero", "pedir",
}


def _mask_pii(text: str) -> str:
    for pat, repl in PII_PATTERNS:
        text = pat.sub(repl, text)
    return text


def _looks_portuguese(text: str) -> bool:
    words = set(re.findall(r"[a-záéíóúâêôãõç]+", text.lower()))
    hits = words & PT_MARKERS
    return len(hits) >= 2


def guard_input(state: AgentState) -> dict:
    t0 = time.perf_counter()
    q = state["question"].strip()
    timings = dict(state.get("timings", {}))

    if not (3 <= len(q) <= 2000):
        return {"blocked": True, "block_reason": "pergunta fora do tamanho permitido (3-2000 caracteres)",
                "timings": {**timings, "guard_input": _ms(t0)}}

    if not _looks_portuguese(q):
        return {"blocked": True,
                "block_reason": "Respondo apenas em português. Por favor, reformule sua pergunta.",
                "timings": {**timings, "guard_input": _ms(t0)}}

    low = q.lower()
    for pat in INJECTION_PATTERNS:
        if re.search(pat, low):
            return {"blocked": True,
                    "block_reason": "Não posso atender a esse tipo de pedido.",
                    "timings": {**timings, "guard_input": _ms(t0)}}

    escalate = any(topic in low for topic in SENSITIVE_TOPICS)
    masked = _mask_pii(q)
    return {
        "question": masked,
        "escalate": escalate,
        "blocked": False,
        "timings": {**timings, "guard_input": _ms(t0)},
    }


def _ms(t0: float) -> float:
    return round((time.perf_counter() - t0) * 1000, 1)
