"""Fábrica de LLMs apontando para um provedor OpenAI-compatible."""
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from .config import get_settings


def _chat(model: str, temperature: float, max_tokens: int | None = None) -> ChatOpenAI:
    s = get_settings()
    kwargs: dict = {
        "model": model,
        "api_key": s.llm_api_key,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "max_retries": s.llm_max_retries,
        "default_headers": {"X-Title": "desafio-agente-rh"},
    }
    if s.llm_base_url:
        kwargs["base_url"] = s.llm_base_url
    return ChatOpenAI(**kwargs)


def planner_llm() -> ChatOpenAI:
    """Classificação, re-query — barato e rápido."""
    return _chat(get_settings().model_planner, temperature=0, max_tokens=150)


def synthesizer_llm() -> ChatOpenAI:
    """Síntese final — qualidade máxima."""
    return _chat(get_settings().model_synthesizer, temperature=0.2, max_tokens=600)


def judge_llm() -> ChatOpenAI:
    """Guardrail de saída — determinístico."""
    return _chat(get_settings().model_judge, temperature=0, max_tokens=200)


def embeddings() -> OpenAIEmbeddings:
    s = get_settings()
    kwargs: dict = {
        "model": s.model_embeddings,
        "api_key": s.llm_api_key,
    }
    if s.llm_base_url:
        kwargs["base_url"] = s.llm_base_url
    return OpenAIEmbeddings(**kwargs)
