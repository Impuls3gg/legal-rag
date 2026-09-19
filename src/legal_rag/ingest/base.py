"""Интерфейс источника нормативных актов.

Любой источник данных (локальные файлы, pravo.gov.ru, будущий консультант.ру и т.д.)
реализует один метод — fetch_all() — и возвращает список RawAct. Это позволяет
не завязывать остальной пайплайн (парсинг, чанкинг, эмбеддинги) на конкретный источник.
"""
from __future__ import annotations

from typing import Iterable, Protocol

from ..models import RawAct


class ActSource(Protocol):
    def fetch_all(self) -> Iterable[RawAct]: ...
