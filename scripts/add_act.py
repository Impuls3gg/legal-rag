"""Интерактивно добавляет акт в data/raw/<act_id>/ (meta.json + text.txt).

Тексты законов и других официальных документов не являются объектом
авторского права (ст. 1259 ГК РФ) — их можно свободно копировать для
локального использования. Автоматический скрапинг pravo.gov.ru/
docs.cntd.ru ненадёжен (SSO-редиректы, непубличные ID документов),
поэтому текст удобнее скопировать руками из браузера и вставить сюда.

Использование:
    uv run python scripts/add_act.py
"""
from __future__ import annotations

import json
import os
import sys

RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def ask(prompt: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    value = input(f"{prompt}{suffix}: ").strip()
    return value or default


def read_multiline_text() -> str:
    print("Вставьте текст акта, затем на новой строке введите EOF и Enter:")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "EOF":
            break
        lines.append(line)
    return "\n".join(lines)


def main() -> None:
    act_id = ask("act_id (слаг, например gk-rf-chast-1)")
    if not act_id:
        print("act_id обязателен")
        sys.exit(1)

    act_dir = os.path.join(RAW_DIR, act_id)
    if os.path.exists(act_dir):
        print(f"{act_dir} уже существует — прервано, чтобы не затереть данные.")
        sys.exit(1)

    meta = {
        "title": ask("Полное название акта"),
        "act_type": ask("Тип акта (кодекс/федеральный закон/...)"),
        "number": ask("Номер акта", ""),
        "date": ask("Дата принятия (YYYY-MM-DD)", ""),
        "source_url": ask("Ссылка на источник", ""),
    }
    text = read_multiline_text()
    if not text.strip():
        print("Пустой текст — прервано.")
        sys.exit(1)

    os.makedirs(act_dir)
    with open(os.path.join(act_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
    with open(os.path.join(act_dir, "text.txt"), "w", encoding="utf-8") as f:
        f.write(text)

    print(f"Готово: {act_dir}")


if __name__ == "__main__":
    main()
