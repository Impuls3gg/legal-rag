"""Источник: тексты актов, вручную положенные в data/raw/.

Формат каталога data/raw/:
    <act_id>/
        meta.json   # {"title": ..., "act_type": ..., "number": ..., "date": ..., "source_url": ...}
        text.txt    # или text.docx

Это самый надёжный источник для MVP: не зависит от структуры внешнего сайта.
"""
from __future__ import annotations

import json
import os
from typing import Iterator

from ..models import RawAct


class LocalFilesSource:
    def __init__(self, raw_dir: str):
        self.raw_dir = raw_dir

    def fetch_all(self) -> Iterator[RawAct]:
        if not os.path.isdir(self.raw_dir):
            return
        for act_id in sorted(os.listdir(self.raw_dir)):
            act_dir = os.path.join(self.raw_dir, act_id)
            if not os.path.isdir(act_dir):
                continue
            meta_path = os.path.join(act_dir, "meta.json")
            meta = {}
            if os.path.isfile(meta_path):
                with open(meta_path, "r", encoding="utf-8") as f:
                    meta = json.load(f)

            text = self._read_text(act_dir)
            if not text:
                continue

            yield RawAct(
                act_id=act_id,
                title=meta.get("title", act_id),
                act_type=meta.get("act_type", ""),
                number=meta.get("number", ""),
                date=meta.get("date", ""),
                source_url=meta.get("source_url", ""),
                text=text,
            )

    @staticmethod
    def _read_text(act_dir: str) -> str:
        txt_path = os.path.join(act_dir, "text.txt")
        if os.path.isfile(txt_path):
            with open(txt_path, "r", encoding="utf-8") as f:
                return f.read()

        docx_path = os.path.join(act_dir, "text.docx")
        if os.path.isfile(docx_path):
            from docx import Document  # python-docx, импорт по требованию

            doc = Document(docx_path)
            return "\n".join(p.text for p in doc.paragraphs)

        return ""
