from __future__ import annotations

from .config import settings
from .embeddings import HFEmbedder
from .index.faiss_store import FaissStore
from .models import SearchResult


class Retriever:
    def __init__(self, store: FaissStore | None = None, embedder: HFEmbedder | None = None):
        self.store = store or FaissStore(settings.index_dir)
        self.embedder = embedder or HFEmbedder()

    def search(self, query: str, top_k: int | None = None) -> list[SearchResult]:
        query_vector = self.embedder.embed([query])[0]
        return self.store.search(query_vector, top_k or settings.top_k)
