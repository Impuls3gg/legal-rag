"""Скачивает акт с ru.wikisource.org в data/raw/<act_id>/ (text.txt + meta.json).

Кодексы на Викитеке разбиты на страницы по главам ("Гражданский кодекс РФ/Глава 12"),
поэтому скрипт забирает главы и склеивает их в один текст. Список глав берётся
из API Викитеки, а не из диапазона чисел: так попадают и вставные главы вроде
"Глава 9.1". Редакция на Викитеке может отставать от актуальной — для отладки
пайплайна это не важно, для реального использования сверяйтесь с официальным
источником.

Пример (ГК РФ, часть первая = главы 1-29):
    uv run python scripts/fetch_wikisource.py \\
        --page "Гражданский кодекс РФ" --chapters 1-29 \\
        --act-id gk-rf-chast-1 \\
        --title "Гражданский кодекс Российской Федерации (часть первая)" \\
        --number 51-ФЗ --date 1994-11-30

Все основные кодексы разом — scripts/fetch_codes.py.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from bs4 import BeautifulSoup

API = "https://ru.wikisource.org/w/api.php"
USER_AGENT = "legal-rag/0.1 (https://github.com/Impuls3gg/legal-rag; local student project)"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")
# Пауза между запросами: Викитека отвечает 429 уже на паре запросов в секунду.
REQUEST_DELAY = 1.0

_BLOCK_TAGS = ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dd", "dt", "blockquote", "center"]
_JUNK_SELECTORS = [
    "sup.reference", "ol.references", "div.mw-references-wrap", "table",
    "style", ".mw-editsection", ".noprint", ".navbox",
]
_BODY_START_RE = re.compile(r"^(ЧАСТЬ|Раздел|Подраздел|Глава)\b", re.MULTILINE)
_CHAPTER_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*$")
# В УК вместо пробелов стоят U+2007 (цифровой пробел) и U+202F, плюс невидимые
# метки направления текста U+200E/U+200F после каждой редакционной сноски.
_SPACE_FIXES = str.maketrans({" ": " ", " ": " ", " ": " ", "‎": None, "‏": None})


def api_get(params: dict, attempts: int = 5) -> dict:
    query = urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            break
        except (urllib.error.URLError, OSError) as e:
            if attempt == attempts:
                raise
            # На 429 Викитека говорит, сколько ждать; на прочих сбоях — растущая пауза.
            retry_after = getattr(e, "headers", None) and e.headers.get("Retry-After")
            wait = int(retry_after) if retry_after and retry_after.isdigit() else 5 * attempt
            print(f"[{e}; жду {wait} с, повтор {attempt}/{attempts - 1}]", end=" ", flush=True)
            time.sleep(wait)
    if "error" in data:
        raise RuntimeError(data["error"].get("info", data["error"]))
    return data


def fetch_page_html(title: str) -> str:
    data = api_get({"action": "parse", "page": title, "prop": "text", "disabletoc": 1})
    return data["parse"]["text"]["*"]


def list_chapters(page: str) -> list[str]:
    """Номера глав, для которых есть страница "<page>/Глава N", по порядку."""
    prefix = f"{page}/Глава "
    data = api_get({
        "action": "query", "list": "allpages", "apprefix": prefix,
        "apfilterredir": "nonredirects", "aplimit": 500,
    })
    numbers = [p["title"][len(prefix):] for p in data["query"]["allpages"]]
    # Отсекаем страницы вроде "Глава 1. ЗАДАЧИ И ПРИНЦИПЫ" — это дубли под другим именем.
    numbers = [n for n in numbers if _CHAPTER_NUMBER_RE.match(n)]
    return sorted(numbers, key=_number_key)


def select_chapters(available: list[str], spec: str) -> list[str]:
    """"all" — все главы; "30-60" — главы, чей целый номер в диапазоне (включая 47.1)."""
    if spec == "all":
        return available
    first, _, last = spec.partition("-")
    lo, hi = int(first), int(last or first)
    chosen = [n for n in available if lo <= _number_key(n)[0] <= hi]
    missing = sorted(set(range(lo, hi + 1)) - {_number_key(n)[0] for n in chosen})
    if missing:
        print(f"[предупреждение] на Викитеке нет глав: {missing}")
    return chosen


def _number_key(number: str) -> tuple[int, ...]:
    return tuple(int(part) for part in number.split("."))


def html_to_text(html: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    for selector in _JUNK_SELECTORS:
        for node in soup.select(selector):
            node.decompose()
    for br in soup.find_all("br"):
        br.replace_with("\n")
    # Переносы строк только вокруг блочных элементов: иначе каждая ссылка
    # внутри абзаца ("статьёй 200") превращается в отдельную строку.
    for node in soup.find_all(_BLOCK_TAGS):
        node.insert_before("\n")
        node.insert_after("\n")
    text = soup.get_text().translate(_SPACE_FIXES)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_page_header(text: str) -> str:
    """Убирает навигацию Викитеки перед первым структурным заголовком."""
    m = _BODY_START_RE.search(text)
    return text[m.start():] if m else text


def fetch_act(
    page: str, chapters: str, act_id: str, title: str,
    act_type: str = "кодекс", number: str = "", date: str = "", force: bool = False,
) -> bool:
    """Скачивает акт в data/raw/<act_id>/. False — если уже скачан и force не задан."""
    act_dir = os.path.join(RAW_DIR, act_id)
    if os.path.exists(act_dir) and not force:
        print(f"{act_dir} уже существует (используйте --force для перезаписи)")
        return False

    selected = select_chapters(list_chapters(page), chapters)
    if not selected:
        raise RuntimeError(f"не найдено ни одной главы «{page}/Глава N» в диапазоне {chapters}")

    parts: list[str] = []
    for n in selected:
        time.sleep(REQUEST_DELAY)
        chapter_title = f"{page}/Глава {n}"
        print(f"  {chapter_title} ...", end=" ", flush=True)
        text = strip_page_header(html_to_text(fetch_page_html(chapter_title)))
        found = len(re.findall(r"^Статья \d", text, re.MULTILINE))
        print(f"{len(text)} симв., статей: {found}")
        parts.append(text)

    os.makedirs(act_dir, exist_ok=True)
    with open(os.path.join(act_dir, "text.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts))
    meta = {
        "title": title,
        "act_type": act_type,
        "number": number,
        "date": date,
        "source_url": f"https://ru.wikisource.org/wiki/{urllib.parse.quote(page)}",
    }
    with open(os.path.join(act_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Готово: {act_dir} ({len(selected)} глав)")
    return True


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", required=True, help='базовое имя страницы, например "Гражданский кодекс РФ"')
    ap.add_argument("--chapters", default="all", help='диапазон глав, например 1-29, или "all"')
    ap.add_argument("--act-id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--act-type", default="кодекс")
    ap.add_argument("--number", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--force", action="store_true", help="перезаписать существующий data/raw/<act_id>")
    args = ap.parse_args()

    ok = fetch_act(args.page, args.chapters, args.act_id, args.title,
                   args.act_type, args.number, args.date, args.force)
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
