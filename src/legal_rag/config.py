"""Настройки проекта. Переопределяются переменными окружения с префиксом LEGAL_RAG_."""
from __future__ import annotations

import os
from dataclasses import dataclass

# torch >= 2.14 в eager-режиме маршрутизирует часть матричных операций через
# Triton-ядра, которые компилируются при первом вызове и требуют C-компилятор.
# В свежем WSL/контейнере его нет, и generate() падает на RoPE в Qwen с
# "Failed to find C compiler". Штатные CUDA-ядра ничем не хуже для наших
# размеров, поэтому отключаем. Переменная читается torch при каждом вызове,
# так что setdefault здесь успевает, а явное значение из окружения — приоритетнее.
os.environ.setdefault("TORCH_DISABLE_NATIVE_JIT", "1")


def _env(name: str, default: str) -> str:
    return os.environ.get(f"LEGAL_RAG_{name}", default)


def _model(name: str, default: str) -> str:
    """Имя модели на Hub или путь к папке. Если веса скачаны вручную в
    models/<имя без организации>, берём их — Hub не понадобится."""
    model = _env(name, default)
    local = os.path.join("models", model.rsplit("/", 1)[-1])
    return local if os.path.isdir(local) else model


@dataclass(frozen=True)
class Settings:
    embedding_model: str = _model("EMBEDDING_MODEL", "BAAI/bge-m3")
    llm_model: str = _model("LLM_MODEL", "Qwen/Qwen2.5-1.5B-Instruct")
    # Только GPU: "cuda" или конкретная карта, например "cuda:1".
    device: str = _env("DEVICE", "cuda")

    data_dir: str = _env("DATA_DIR", "data")
    raw_dir: str = os.path.join(data_dir, "raw")
    processed_dir: str = os.path.join(data_dir, "processed")
    index_dir: str = os.path.join(data_dir, "index")

    chunk_max_chars: int = int(_env("CHUNK_MAX_CHARS", "1500"))
    top_k: int = int(_env("TOP_K", "6"))
    # Порог отказа: если лучший чанк ниже — в базе нет ответа, LLM не запускаем.
    # Подобран по scripts/evaluate.py на ГК РФ ч.1: 0.55 оставляет ~97% вопросов
    # с ответом в базе и отсекает ~75% вопросов вне её. Полностью не разделить:
    # вопросы по смежным темам (аренда, заём — часть вторая ГК) набирают до 0.61.
    # 0 отключает проверку.
    min_score: float = float(_env("MIN_SCORE", "0.55"))

    # Чанк в 1500 символов — это ~500 токенов; лимит выше нужен только как страховка.
    embedding_max_tokens: int = int(_env("EMBEDDING_MAX_TOKENS", "1024"))
    embedding_batch_size: int = int(_env("EMBEDDING_BATCH_SIZE", "8"))

    llm_max_new_tokens: int = int(_env("LLM_MAX_NEW_TOKENS", "512"))
    llm_temperature: float = float(_env("LLM_TEMPERATURE", "0"))


settings = Settings()


def resolve_device() -> str:
    """Проверяет, что GPU доступна, и возвращает устройство из настроек.
    torch импортируется здесь, а не наверху модуля, чтобы config оставался
    лёгким для тестов парсера."""
    import torch

    if not torch.cuda.is_available():
        raise RuntimeError(
            "CUDA недоступна: проект работает только на GPU. Проверьте драйвер "
            "NVIDIA (>= 560) и, в Docker, NVIDIA Container Toolkit."
        )
    return settings.device
