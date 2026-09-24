"""Вопрос -> ответ целиком: поиск, проверка порога отказа, генерация.

Общая логика для CLI и веб-интерфейса. CLI загружает модели на один вопрос и
выгружает эмбеддер перед LLM; сервис держит обе в памяти через RAGPipeline.
"""
from __future__ import annotations

import threading
from dataclasses import dataclass

from .config import settings
from .index.faiss_store import FaissStore
from .llm import HFLLM
from .models import SearchResult
from .retrieval import Retriever


@dataclass
class Answer:
    question: str
    text: str                    # ответ модели; пустой, если отказались
    sources: list[SearchResult]  # при отказе — ближайшие найденные чанки
    refused: bool

    @property
    def best_score(self) -> float:
        return self.sources[0].score if self.sources else 0.0


def is_out_of_corpus(results: list[SearchResult]) -> bool:
    """Лучший чанк ниже порога — ответа в базе нет, LLM не запускаем."""
    return not results or results[0].score < settings.min_score


class RAGPipeline:
    """Обе модели загружены один раз и переиспользуются между вопросами."""

    def __init__(self, retriever: Retriever | None = None, llm: HFLLM | None = None):
        if retriever is None:
            # Индекс читаем до загрузки моделей: если его нет, падаем сразу,
            # а не после минуты ожидания весов.
            store = FaissStore(settings.index_dir)
            store.load()
            retriever = Retriever(store=store)
        self.retriever = retriever
        self.llm = llm or HFLLM()
        # Streamlit обслуживает сессии в разных потоках. Параллельные generate()
        # на одной модели не ломаются, но множат пик памяти под KV-кэш, а
        # быстрее не становятся — GPU всё равно одна. Поэтому по очереди.
        self._lock = threading.Lock()

    def ask(self, question: str) -> Answer:
        with self._lock:
            results = self.retriever.search(question)
            if is_out_of_corpus(results):
                return Answer(question, "", results[:3], refused=True)
            text = self.llm.answer(question, results)
        return Answer(question, text, results, refused=False)
