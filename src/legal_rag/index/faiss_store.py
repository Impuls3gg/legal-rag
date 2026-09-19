"""Хранилище векторов на FAISS (IndexFlatIP + нормализованные вектора = cosine sim)
с метаданными чанков рядом, в JSON. Файл индекса и метаданные хранятся
в data/index/ и грузятся заново при каждом запуске CLI.
"""
from __future__ import annotations

import json
import os

import faiss
import numpy as np

from ..models import Chunk, SearchResult


class FaissStore:
    def __init__(self, index_dir: str):
        self.index_dir = index_dir
        self._index_path = os.path.join(index_dir, "index.faiss")
        self._meta_path = os.path.join(index_dir, "chunks.json")
        self._index: faiss.Index | None = None
        self._chunks: list[Chunk] = []

    def build(self, chunks: list[Chunk], vectors: np.ndarray) -> None:
        os.makedirs(self.index_dir, exist_ok=True)
        index = faiss.IndexFlatIP(vectors.shape[1])
        index.add(vectors)
        faiss.write_index(index, self._index_path)

        with open(self._meta_path, "w", encoding="utf-8") as f:
            json.dump([c.__dict__ for c in chunks], f, ensure_ascii=False, indent=2)

        self._index = index
        self._chunks = chunks

    def load(self) -> None:
        if not os.path.isfile(self._index_path):
            raise FileNotFoundError(
                f"Индекс не найден в {self._index_path}. Сначала запустите build-index."
            )
        self._index = faiss.read_index(self._index_path)
        with open(self._meta_path, "r", encoding="utf-8") as f:
            self._chunks = [Chunk(**d) for d in json.load(f)]

    def search(self, query_vector: np.ndarray, top_k: int) -> list[SearchResult]:
        if self._index is None:
            self.load()
        scores, ids = self._index.search(query_vector.reshape(1, -1), top_k)
        results = []
        for score, idx in zip(scores[0], ids[0]):
            if idx == -1:
                continue
            results.append(SearchResult(chunk=self._chunks[idx], score=float(score)))
        return results

    def __len__(self) -> int:
        if self._index is None:
            self.load()
        return len(self._chunks)
