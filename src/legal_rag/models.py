"""Общие структуры данных, используемые на всех этапах пайплайна."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RawAct:
    """Сырой нормативный акт целиком, до разбиения на статьи."""

    act_id: str          # уникальный слаг, например "gk-rf-chast-1"
    title: str           # "Гражданский кодекс Российской Федерации (часть первая)"
    act_type: str        # "кодекс" | "федеральный закон" | ...
    number: str = ""     # официальный номер акта
    date: str = ""       # дата принятия/подписания, ISO-строка или как в источнике
    source_url: str = ""
    text: str = ""       # полный текст акта


@dataclass
class Chunk:
    """Единица индексации — как правило, одна статья (или её часть, если статья большая)."""

    chunk_id: str
    act_id: str
    act_title: str
    section: str = ""       # раздел
    chapter: str = ""       # глава
    article_number: str = ""
    article_title: str = ""
    part_index: int = 0     # >0, если статья была разрезана на несколько частей
    text: str = ""
    source_url: str = ""

    def citation(self) -> str:
        loc = f"ст. {self.article_number}" if self.article_number else ""
        chapter = f"глава {self.chapter}" if self.chapter else ""
        pieces = [p for p in [self.act_title, chapter, loc] if p]
        return ", ".join(pieces)

    def full_text(self) -> str:
        """Заголовок + тело: то, что уходит в эмбеддинг и в контекст модели.

        Парсер оставляет в `text` только тело статьи, поэтому её название
        (часто единственное место, где встречается ключевая формулировка —
        "срок исковой давности", "крайняя необходимость") иначе не попало бы
        ни в вектор, ни к модели. Для разрезанных статей заголовок повторяется
        в каждой части, чтобы та была самодостаточной.
        """
        header = self.citation()
        if self.article_title:
            header = f"{header}. {self.article_title}" if header else self.article_title
        return f"{header}\n{self.text}" if header else self.text


@dataclass
class SearchResult:
    chunk: Chunk
    score: float
