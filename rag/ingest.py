"""Ingest: carrega knowledge_base/, chunkeia por seção markdown, indexa no Chroma.

Uso: uv run python -m rag.ingest
"""
import re
from pathlib import Path

from langchain_chroma import Chroma
from langchain_core.documents import Document

from agent.config import get_settings
from agent.llm import embeddings


def split_markdown_sections(text: str) -> list[str]:
    """Quebra em seções por headers ##, mantendo header no chunk."""
    parts = re.split(r"(?m)(?=^## )", text)
    return [p.strip() for p in parts if p.strip()]


def build_store() -> Chroma:
    s = get_settings()
    kb = Path(s.knowledge_base_dir)
    docs: list[Document] = []
    for md in sorted(kb.rglob("*.md")):
        text = md.read_text(encoding="utf-8")
        title = text.splitlines()[0].lstrip("# ").strip()
        rel = str(md.relative_to(kb))
        for section in split_markdown_sections(text):
            docs.append(Document(
                page_content=section,
                metadata={"source": rel, "doc": title},
            ))

    store = Chroma.from_documents(
        docs,
        embeddings(),
        persist_directory=s.chroma_dir,
        collection_name="knowledge_base",
    )
    print(f"Indexados {len(docs)} chunks de {len(list(kb.rglob('*.md')))} documentos em {s.chroma_dir}")
    return store


if __name__ == "__main__":
    build_store()
