"""Разбор сырого текста акта на структуру раздел -> глава -> статья.

Рассчитан на типовую разметку российских кодексов и федеральных законов
("Раздел I. ...", "Глава 5. ...", "Статья 123. Название"). Если верстка
источника отличается, статьи не найдутся вообще — тогда весь текст акта
возвращается одной "псевдостатьёй", чтобы пайплайн не падал, а деградация
была видна (в CLI выводится предупреждение с числом найденных статей).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_SECTION_RE = re.compile(r"^Раздел\s+([IVXLCDM\d]+)\.?\s*(.*)$", re.MULTILINE)
_CHAPTER_RE = re.compile(r"^Глава\s+(\d+)\.?\s*(.*)$", re.MULTILINE)
# Номера вида "12", "66.1", "123.20-1" (последний — реальная нумерация ГК РФ).
_ARTICLE_RE = re.compile(r"^Статья\s+(\d+(?:[.\-]\d+)*)\.?\s*(.*)$", re.MULTILINE)

# В оглавлении между заголовками статей текста нет — только перевод строки
# и иногда заголовок раздела/главы.
_MIN_TOC_BODY = 80


@dataclass
class ParsedArticle:
    section: str
    chapter: str
    article_number: str
    article_title: str
    text: str


def parse_articles(raw_text: str) -> list[ParsedArticle]:
    text = raw_text.replace("\r\n", "\n")

    article_matches = list(_ARTICLE_RE.finditer(text))
    if not article_matches:
        return [_whole_text(text)]

    section_matches = list(_SECTION_RE.finditer(text))
    chapter_matches = list(_CHAPTER_RE.finditer(text))

    articles: list[ParsedArticle] = []
    for i, m in enumerate(article_matches):
        start = m.end()
        end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(text)
        body = text[start:end].strip()

        section = _label_before(section_matches, m.start())
        chapter = _label_before(chapter_matches, m.start())

        articles.append(
            ParsedArticle(
                section=section,
                chapter=chapter,
                article_number=m.group(1),
                article_title=m.group(2).strip(),
                text=body,
            )
        )

    articles = [a for a in _drop_table_of_contents(articles) if a.text]
    return articles or [_whole_text(text)]


def _whole_text(text: str) -> ParsedArticle:
    return ParsedArticle(section="", chapter="", article_number="", article_title="", text=text.strip())


def _drop_table_of_contents(articles: list[ParsedArticle]) -> list[ParsedArticle]:
    """Отбрасывает оглавление в начале акта.

    Скопированный из браузера кодекс начинается с оглавления: те же заголовки
    "Статья N. Название", но без текста. Без этого каждая статья попадает в
    индекс дважды, причём пустым дублем, который матчится на произвольный запрос.

    Признак конца оглавления — нумерация, пошедшая заново. Проверка на длину
    страхует от актов, где нумерация честно перезапускается (например, в
    приложении): тогда перед перезапуском стоят статьи с настоящим текстом.
    """
    for i in range(1, len(articles)):
        if _number_key(articles[i].article_number) > _number_key(articles[i - 1].article_number):
            continue
        # Последняя запись оглавления втягивает в себя заголовки разделов и глав,
        # идущие до первой настоящей статьи, поэтому её длину не проверяем.
        head = articles[: i - 1] or articles[:1]
        if all(len(a.text) < _MIN_TOC_BODY for a in head):
            return articles[i:]
    return articles


def _number_key(number: str) -> tuple[int, ...]:
    """"123.20-1" -> (123, 20, 1), чтобы сравнивать номера статей по порядку, а не строками."""
    try:
        return tuple(int(part) for part in re.split(r"[.\-]", number))
    except ValueError:
        return ()


def _label_before(matches: list[re.Match], pos: int) -> str:
    label = ""
    for m in matches:
        if m.start() > pos:
            break
        num, title = m.group(1), m.group(2).strip()
        label = f"{num}. {title}" if title else num
    return label
