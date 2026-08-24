"""Configuração central via variáveis de ambiente."""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_api_key: str = ""
    model_planner: str = ""
    model_synthesizer: str = ""
    model_judge: str = ""
    model_embeddings: str = ""

    chroma_dir: str = ".chroma"
    checkpoint_db: str = ".checkpoints.sqlite"
    knowledge_base_dir: str = "knowledge_base"

    guard_output_threshold: float = 0.7
    llm_max_retries: int = 3

    # Base URL do provedor de LLM. Vazio = default do SDK (OpenAI official).
    llm_base_url: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()
