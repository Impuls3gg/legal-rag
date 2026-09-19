"""Превращение RawAct в список Chunk.

Единица чанка — одна статья целиком (так сохраняется юридическая цельность
нормы). Слишком длинные статьи режутся по абзацам/пунктам с сохранением
метаданных, чтобы не терять контекст при поиске.
"""
from __future__ import annotations

from .ingest.parser import parse_articles
from .models import Chunk, RawAct


def act_to_chunks(act: RawAct, max_chars: int) -> list[Chunk]:
    chunks: list[Chunk] = []
    for article in parse_articles(act.text):
        parts = _split_long_text(article.text, max_chars)
        for i, part in enumerate(parts):
            chunk_id = f"{act.act_id}:{article.article_number or 'full'}"
            if len(parts) > 1:
                chunk_id += f":{i}"

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    act_id=act.act_id,
                    act_title=act.title,
                    section=article.section,
                    chapter=article.chapter,
                    article_number=article.article_number,
                    article_title=article.article_title,
                    part_index=i,
                    text=part,
                    source_url=act.source_url,
                )
            )
    return chunks


def _split_long_text(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]

    paragraphs = [p for p in text.split("\n") if p.strip()]
    parts: list[str] = []
    current = ""
    for p in paragraphs:
        candidate = f"{current}\n{p}" if current else p
        if len(candidate) > max_chars and current:
            parts.append(current)
            current = p
        else:
            current = candidate
    if current:
        parts.append(current)
    return parts or [text]
