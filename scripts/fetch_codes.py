"""Скачивает с Викитеки основные кодексы РФ в data/raw/: ГК (все 4 части), УК, ТК, КоАП.

    uv run python scripts/fetch_codes.py            # только те, которых ещё нет
    uv run python scripts/fetch_codes.py --force    # перекачать всё
    uv run python -m legal_rag.cli build-index      # после скачивания

Редакции на Викитеке отстают от действующих на несколько лет (последние
поправки в УК — 2019 г., в ГК ч. 4 — 2022 г.). Для отладки поиска это не
важно, для реальных ответов — сверяйтесь с pravo.gov.ru.

Скачивание занимает несколько минут: ~210 страниц с паузой между запросами.
"""
from __future__ import annotations

import argparse

from fetch_wikisource import fetch_act

GK = "Гражданский кодекс РФ"
GK_TITLE = "Гражданский кодекс Российской Федерации"

CODES = [
    dict(act_id="gk-rf-chast-1", page=GK, chapters="1-29", title=f"{GK_TITLE} (часть первая)",
         number="51-ФЗ", date="1994-11-30"),
    dict(act_id="gk-rf-chast-2", page=GK, chapters="30-60", title=f"{GK_TITLE} (часть вторая)",
         number="14-ФЗ", date="1996-01-26"),
    dict(act_id="gk-rf-chast-3", page=GK, chapters="61-68", title=f"{GK_TITLE} (часть третья)",
         number="146-ФЗ", date="2001-11-26"),
    dict(act_id="gk-rf-chast-4", page=GK, chapters="69-77", title=f"{GK_TITLE} (часть четвёртая)",
         number="230-ФЗ", date="2006-12-18"),
    dict(act_id="uk-rf", page="Уголовный кодекс Российской Федерации", chapters="all",
         title="Уголовный кодекс Российской Федерации", number="63-ФЗ", date="1996-06-13"),
    dict(act_id="tk-rf", page="Трудовой кодекс РФ", chapters="all",
         title="Трудовой кодекс Российской Федерации", number="197-ФЗ", date="2001-12-30"),
    dict(act_id="koap-rf", page="Кодекс РФ об административных правонарушениях", chapters="all",
         title="Кодекс Российской Федерации об административных правонарушениях",
         number="195-ФЗ", date="2001-12-30"),
]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="перекачать уже скачанные кодексы")
    ap.add_argument("--only", nargs="+", metavar="ACT_ID", help="скачать только эти act_id")
    args = ap.parse_args()

    codes = [c for c in CODES if not args.only or c["act_id"] in args.only]
    fetched = []
    for code in codes:
        print(f"\n== {code['title']} ({code['act_id']})")
        if fetch_act(**code, force=args.force):
            fetched.append(code["act_id"])

    print(f"\nСкачано: {', '.join(fetched) or 'ничего нового'}.")
    if fetched:
        print("Пересоберите индекс: uv run python -m legal_rag.cli build-index")


if __name__ == "__main__":
    main()
