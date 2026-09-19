"""Источник: pravo.gov.ru.

ВАЖНО (ограничение, о котором нужно знать заранее): поиск на pravo.gov.ru построен
на JS и сессионных параметрах, поэтому надёжно программно искать акты по номеру/
названию без ручной проверки — нельзя. Рабочий вариант для MVP: вы вручную находите
на сайте нужный кодекс/закон, копируете прямую ссылку на страницу с текстом и
добавляете её в data/sources.json. Дальше этот модуль сам скачивает и чистит HTML.

Формат data/sources.json:
[
  {
    "act_id": "gk-rf-chast-1",
    "title": "Гражданский кодекс Российской Федерации (часть первая)",
    "act_type": "кодекс",
    "number": "51-ФЗ",
    "date": "1994-11-30",
    "url": "http://pravo.gov.ru/..."
  }
]

Селектор извлечения текста (`_TEXT_SELECTOR`) — эвристика по типовой разметке
портала и почти наверняка потребует подстройки под конкретную страницу: если
после скачивания текст выглядит "грязным" (меню, футер и т.п.) — поправьте
селектор или замените на CSS-класс, который видно в devtools на нужной странице.
"""
from __future__ import annotations

import json
import os
from typing import Iterator

import requests
from bs4 import BeautifulSoup

from ..models import RawAct

_TEXT_SELECTOR = "div.text"  # см. предупреждение в docstring модуля
_TIMEOUT = 30


class PravoGovSource:
    def __init__(self, sources_file: str):
        self.sources_file = sources_file

    def fetch_all(self) -> Iterator[RawAct]:
        if not os.path.isfile(self.sources_file):
            return
        with open(self.sources_file, "r", encoding="utf-8") as f:
            entries = json.load(f)

        for entry in entries:
            text = self._fetch_text(entry["url"])
            if not text:
                continue
            yield RawAct(
                act_id=entry["act_id"],
                title=entry.get("title", entry["act_id"]),
                act_type=entry.get("act_type", ""),
                number=entry.get("number", ""),
                date=entry.get("date", ""),
                source_url=entry["url"],
                text=text,
            )

    @staticmethod
    def _fetch_text(url: str) -> str:
        resp = requests.get(url, timeout=_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        resp.encoding = resp.apparent_encoding
        soup = BeautifulSoup(resp.text, "lxml")

        node = soup.select_one(_TEXT_SELECTOR)
        if node is None:
            # Резервный вариант: берём весь <body>, чтобы ничего не потерять,
            # но потом придётся подчистить вручную через meta.json/локальный файл.
            node = soup.body or soup

        return node.get_text("\n", strip=True)
