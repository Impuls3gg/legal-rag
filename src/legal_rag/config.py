"""Настройки проекта. Переопределяются переменными окружения с префиксом LEGAL_RAG_."""
from __future__ import annotations

import os
from dataclasses import dataclass


def _env(name: str, default: str) -> str:
    return os.environ.get(f"LEGAL_RAG_{name}", default)


@dataclass(frozen=True)
class Settings:
    # Имя модели на Hugging Face Hub или путь к локальной папке с весами.
    embedding_model: str = _env("EMBEDDING_MODEL", "BAAI/bge-m3")
    llm_model: str = _env("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    device: str = _env("DEVICE", "cpu")

    data_dir: str = _env("DATA_DIR", "data")
    raw_dir: str = os.path.join(data_dir, "raw")
    processed_dir: str = os.path.join(data_dir, "processed")
    index_dir: str = os.path.join(data_dir, "index")

    chunk_max_chars: int = int(_env("CHUNK_MAX_CHARS", "1500"))
    top_k: int = int(_env("TOP_K", "6"))

    # Чанк в 1500 символов — это ~500 токенов; лимит выше нужен только как страховка.
    embedding_max_tokens: int = int(_env("EMBEDDING_MAX_TOKENS", "1024"))
    embedding_batch_size: int = int(_env("EMBEDDING_BATCH_SIZE", "8"))

    llm_max_new_tokens: int = int(_env("LLM_MAX_NEW_TOKENS", "512"))
    llm_temperature: float = float(_env("LLM_TEMPERATURE", "0"))


settings = Settings()
