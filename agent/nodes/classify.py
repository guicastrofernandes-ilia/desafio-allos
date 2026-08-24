"""Classificação de intenção — modelo do provedor, JSON mode, com tie-break determinístico."""
import json
import re
import time

from langchain_core.messages import HumanMessage, SystemMessage

from ..llm import planner_llm
from ..state import AgentState
from .guard_input import _ms

PROMPT = """Classifique a pergunta do colaborador em UMA intenção:
- policy: QUALQUER dúvida sobre regras/políticas/benefícios da empresa — férias (regras, fracionamento, venda, acúmulo, abono, prazo), home office (modelo, exceções, reembolso, equipamento, horário), equipamentos (garantia, reparo, renovação, devolução, software), benefícios (VR, VA, plano de saúde, odontológico, auxílio-creche, gympass, bônus, vale-transporte), licença (maternidade, paternidade, adoção, prorrogação, documentação), suporte de TI (SLA, acesso, senha, VPN, reset de senha, abertura de ticket)
- oos: restrito a dois casos: (1) assunto fora de RH/TI (cardápio, clima, esporte, tempo, futebol); (2) pergunta que exija dado transacional vivo de um funcionário ou ticket específico (ex.: "quantos dias de férias o E123 tem", "status do ticket T-1002", "meu saldo") — o agente não acessa sistemas transacionais.

Exemplos:
"Qual a garantia do notebook?" → policy
"Qual o valor do vale-refeição?" → policy
"Qual o SLA de prioridade alta?" → policy
"Como abro um ticket?" → policy
"Como reseto minha senha?" → policy
"De quanto em quanto tempo os notebooks são renovados?" → policy
"Em que horário posso entrar no escritório?" → policy
"Quantos dias de licença-paternidade o pai tem?" → policy
"Qual o cardápio?" → oos
"Quantos dias o E123 tem de férias?" → oos
"Status do ticket T-1002" → oos

REGRAS:
1. Toda pergunta sobre regra, política, benefício ou procedimento de RH/TI → policy, mesmo sem citar um documento específico.
2. Pergunta sobre dado específico de funcionário (E###) ou ticket (T-XXXX) → oos (dado vivo indisponível).
3. Entidades genéricas (o pai, a gestante, o colaborador, a empresa) NÃO são pessoas específicas → policy. Só um ID concreto (E123/E456) indica dado vivo.
4. Pergunta genérica sobre política de férias (direito, fracionamento, venda, prazo) → policy.
5. Na dúvida entre policy e oos, escolha policy (é melhor tentar recuperar um documento do que recusar).
Responda APENAS JSON: {"intent": "..."}"""


DOMAIN_KEYWORDS = [
    "férias", "ferias", "home office", "reembolso", "vale", "plano de saúde", "saude",
    "odontol", "auxílio", "creche", "gympass", "bônus", "bonus", "vale-transporte",
    "licença", "licenca", "maternidade", "paternidade", "adoção", "adocao",
    "garantia", "notebook", "equipamento", "renova", "software", "senha", "vpn",
    "sla", "ticket de suporte", "abrir ticket", "política", "politica", "benefício", "beneficio",
]
LIVE_ID_PATTERN = re.compile(r"\b[ETFD]\d{3,}\b|\bT-\d+\b", re.IGNORECASE)


def _tiebreak(question: str, llm_intent: str) -> str:
    """Tie-break determinístico: domínio RH/TI sem ID vivo → policy; senão mantém LLM."""
    has_live_id = bool(LIVE_ID_PATTERN.search(question))
    if has_live_id:
        return "oos"  # dado transacional vivo não acessível
    if any(kw in question.lower() for kw in DOMAIN_KEYWORDS):
        return "policy"
    return llm_intent


def classify(state: AgentState) -> dict:
    t0 = time.perf_counter()
    llm = planner_llm()
    resp = llm.invoke([
        SystemMessage(content=PROMPT),
        HumanMessage(content=state["question"]),
    ])
    try:
        intent = json.loads(resp.content)["intent"]
        if intent not in ("policy", "oos"):
            intent = "oos"  # fallback seguro: não inventar fonte
    except (json.JSONDecodeError, KeyError):
        intent = "oos"

    intent = _tiebreak(state["question"], intent)

    timings = dict(state.get("timings", {}))
    return {"intent": intent, "timings": {**timings, "classify": _ms(t0)}}
