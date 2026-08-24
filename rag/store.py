"""Wrapper de leitura do Chroma. Somente leitura em runtime — ingest é job separado."""
from functools import lru_cache

from langchain_chroma import Chroma

from agent.config import get_settings
from agent.llm import embeddings


@lru_cache
def get_store() -> Chroma:
    s = get_settings()
    return Chroma(
        persist_directory=s.chroma_dir,
        embedding_function=embeddings(),
        collection_name="knowledge_base",
    )


def retrieve(question: str, k: int = 6) -> list:
    """Retorna top-k chunks com score. Lança exceção se índice inexistente."""
    store = get_store()
    return store.similarity_search_with_score(question, k=k)
