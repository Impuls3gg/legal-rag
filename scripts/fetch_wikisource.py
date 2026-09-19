"""Скачивает акт с ru.wikisource.org в data/raw/<act_id>/ (text.txt + meta.json).

Кодексы на Викитеке разбиты на страницы по главам ("Гражданский кодекс РФ/Глава 12"),
поэтому скрипт забирает диапазон глав и склеивает их в один текст. Редакция на
Викитеке может отставать от актуальной — для отладки пайплайна это не важно,
для реального использования сверяйтесь с официальным источником.

Пример (ГК РФ, часть первая = главы 1-29):
    uv run python scripts/fetch_wikisource.py \\
        --page "Гражданский кодекс РФ" --chapters 1-29 \\
        --act-id gk-rf-chast-1 \\
        --title "Гражданский кодекс Российской Федерации (часть первая)" \\
        --number 51-ФЗ --date 1994-11-30
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
USER_AGENT = "legal-rag/0.1 (https://github.com/; local student project)"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")

_BLOCK_TAGS = ["p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "li", "dd", "dt", "blockquote", "center"]
_JUNK_SELECTORS = [
    "sup.reference", "ol.references", "div.mw-references-wrap", "table",
    "style", ".mw-editsection", ".noprint", ".navbox",
]
_BODY_START_RE = re.compile(r"^(ЧАСТЬ|Раздел|Подраздел|Глава)\b", re.MULTILINE)


def fetch_page_html(title: str, attempts: int = 4) -> str:
    query = urllib.parse.urlencode(
        {"action": "parse", "page": title, "prop": "text", "format": "json", "disabletoc": 1}
    )
    req = urllib.request.Request(f"{API}?{query}", headers={"User-Agent": USER_AGENT})
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.load(resp)
            break
        except (urllib.error.URLError, OSError) as e:
            if attempt == attempts:
                raise
            print(f"[{e}; повтор {attempt}/{attempts - 1}]", end=" ", flush=True)
            time.sleep(2 * attempt)
    if "error" in data:
        raise RuntimeError(f"{title}: {data['error'].get('info', data['error'])}")
    return data["parse"]["text"]["*"]


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
    text = soup.get_text()
    text = re.sub(r"[ \t ]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def strip_page_header(text: str) -> str:
    """Убирает навигацию Викитеки перед первым структурным заголовком."""
    m = _BODY_START_RE.search(text)
    return text[m.start():] if m else text


def parse_range(spec: str) -> list[int]:
    first, _, last = spec.partition("-")
    return list(range(int(first), int(last or first) + 1))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page", required=True, help='базовое имя страницы, например "Гражданский кодекс РФ"')
    ap.add_argument("--chapters", required=True, help="диапазон глав, например 1-29")
    ap.add_argument("--act-id", required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--act-type", default="кодекс")
    ap.add_argument("--number", default="")
    ap.add_argument("--date", default="")
    ap.add_argument("--force", action="store_true", help="перезаписать существующий data/raw/<act_id>")
    args = ap.parse_args()

    act_dir = os.path.join(RAW_DIR, args.act_id)
    if os.path.exists(act_dir) and not args.force:
        print(f"{act_dir} уже существует (используйте --force для перезаписи)")
        sys.exit(1)

    parts: list[str] = []
    for n in parse_range(args.chapters):
        title = f"{args.page}/Глава {n}"
        print(f"  {title} ...", end=" ", flush=True)
        text = strip_page_header(html_to_text(fetch_page_html(title)))
        found = len(re.findall(r"^Статья \d", text, re.MULTILINE))
        print(f"{len(text)} симв., статей: {found}")
        parts.append(text)
        time.sleep(0.5)

    os.makedirs(act_dir, exist_ok=True)
    with open(os.path.join(act_dir, "text.txt"), "w", encoding="utf-8") as f:
        f.write("\n\n".join(parts))
    meta = {
        "title": args.title,
        "act_type": args.act_type,
        "number": args.number,
        "date": args.date,
        "source_url": f"https://ru.wikisource.org/wiki/{urllib.parse.quote(args.page)}",
    }
    with open(os.path.join(act_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    print(f"Готово: {act_dir}")


if __name__ == "__main__":
    main()
