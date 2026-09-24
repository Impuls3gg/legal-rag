"""CLI: build-index и ask.

    python -m legal_rag.cli build-index
    python -m legal_rag.cli ask "Каков срок исковой давности по общему правилу?"
"""
from __future__ import annotations

import sys

import numpy as np
from tqdm import tqdm

from .chunking import act_to_chunks
from .config import resolve_device, settings
from .embeddings import HFEmbedder
from .index.faiss_store import FaissStore
from .ingest.local_files import LocalFilesSource
from .ingest.pravo_gov import PravoGovSource
from .llm import HFLLM
from .pipeline import is_out_of_corpus
from .retrieval import Retriever


def build_index() -> None:
    acts = list(LocalFilesSource(settings.raw_dir).fetch_all())
    acts += list(PravoGovSource("data/sources.json").fetch_all())

    if not acts:
        print(
            "Не найдено ни одного акта. Положите тексты в data/raw/<act_id>/text.txt "
            "или заполните data/sources.json (см. legal_rag/ingest/pravo_gov.py)."
        )
        return

    chunks = []
    for act in acts:
        act_chunks = act_to_chunks(act, settings.chunk_max_chars)
        found_articles = sum(1 for c in act_chunks if c.article_number)
        if found_articles == 0:
            print(f"[предупреждение] в «{act.title}» не распознано ни одной статьи — "
                  f"проверьте формат текста/парсер.")
        chunks.extend(act_chunks)

    print(f"Актов: {len(acts)}, чанков: {len(chunks)}. "
          f"Загружаю {settings.embedding_model} ({resolve_device()})...")
    embedder = HFEmbedder()
    step = settings.embedding_batch_size
    vectors = [
        embedder.embed([c.full_text() for c in chunks[i : i + step]])
        for i in tqdm(range(0, len(chunks), step), desc="эмбеддинги", unit="batch")
    ]

    store = FaissStore(settings.index_dir)
    store.build(chunks, np.concatenate(vectors))
    print(f"Индекс сохранён в {settings.index_dir}")


def ask(question: str) -> None:
    retriever = Retriever()
    results = retriever.search(question)
    if not results:
        print("Ничего не найдено. Индекс построен? (build-index)")
        return

    if is_out_of_corpus(results):
        print(
            f"В базе нет статей по этому вопросу: лучшее совпадение {results[0].score:.3f} "
            f"ниже порога {settings.min_score:.2f} (LEGAL_RAG_MIN_SCORE). "
            f"Ближайшее, что нашлось:"
        )
        _print_sources(results[:3])
        return

    # Эмбеддер больше не нужен — отдаём его память (на 6-ГБ карте это ~1 ГБ
    # запаса под KV-кэш LLM) до того, как грузить генеративную модель.
    device = retriever.embedder.device
    del retriever
    import torch

    torch.cuda.empty_cache()

    print(f"Загружаю {settings.llm_model} ({device})...", file=sys.stderr)
    llm = HFLLM()
    answer = llm.answer(question, results)

    print(answer)
    print("\n--- Источники ---")
    _print_sources(results)


def _print_sources(results) -> None:
    for r in results:
        print(f"({r.score:.3f}) {r.chunk.citation()}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return

    command = sys.argv[1]
    if command == "build-index":
        build_index()
    elif command == "ask":
        if len(sys.argv) < 3:
            print("Использование: python -m legal_rag.cli ask \"вопрос\"")
            return
        ask(sys.argv[2])
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
