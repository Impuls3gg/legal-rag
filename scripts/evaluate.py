"""Оценка качества поиска на наборе вопросов с эталонными статьями.

    uv run python scripts/evaluate.py                       # eval/gk_rf_1.jsonl
    uv run python scripts/evaluate.py eval/other.jsonl -v   # показать каждый вопрос

Формат строки набора: {"question": "...", "articles": ["196"]}.
Пустой список статей означает «ответа в базе нет» — по таким вопросам считается
не recall, а насколько уверенно (score лучшего чанка) система выдаёт
нерелевантное. Это нужно, чтобы подобрать порог, ниже которого лучше отказаться
отвечать, чем отдавать модели мусор.

Метрики считаются на уровне статей, а не чанков: длинная статья лежит в индексе
несколькими частями, и попадание любой из них — это попадание статьи.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass

from legal_rag.retrieval import Retriever

KS = (1, 3, 5, 10)
CHUNKS_TO_FETCH = 20


@dataclass
class Outcome:
    question: str
    expected: list[str]
    found: list[str]        # номера статей в порядке убывания релевантности, без дублей
    top_score: float
    rank: int | None        # позиция первой эталонной статьи, с 1


def evaluate(cases: list[dict], retriever: Retriever) -> list[Outcome]:
    outcomes = []
    for case in cases:
        results = retriever.search(case["question"], top_k=CHUNKS_TO_FETCH)
        found: list[str] = []
        for r in results:
            if r.chunk.article_number not in found:
                found.append(r.chunk.article_number)
        expected = case["articles"]
        ranks = [found.index(a) + 1 for a in expected if a in found]
        outcomes.append(
            Outcome(
                question=case["question"],
                expected=expected,
                found=found,
                top_score=results[0].score if results else 0.0,
                rank=min(ranks) if ranks else None,
            )
        )
    return outcomes


def article_title(retriever: Retriever, number: str) -> str:
    for chunk in retriever.store.chunks:
        if chunk.article_number == number:
            return chunk.article_title
    return "(нет в индексе!)"


def report(outcomes: list[Outcome], retriever: Retriever, verbose: bool) -> None:
    in_corpus = [o for o in outcomes if o.expected]
    out_corpus = [o for o in outcomes if not o.expected]

    print(f"Вопросов: {len(in_corpus)} в базе, {len(out_corpus)} вне базы\n")

    print("== Поиск по вопросам, ответ на которые есть в базе ==")
    for k in KS:
        hits = sum(1 for o in in_corpus if o.rank is not None and o.rank <= k)
        print(f"  Recall@{k:<2} {hits / len(in_corpus):6.1%}   ({hits}/{len(in_corpus)})")
    mrr = sum(1 / o.rank for o in in_corpus if o.rank) / len(in_corpus)
    print(f"  MRR       {mrr:6.3f}")

    misses = [o for o in in_corpus if o.rank is None or o.rank > 5]
    if misses:
        print(f"\n  Промахи (эталон не в топ-5): {len(misses)}")
        for o in misses:
            where = f"место {o.rank}" if o.rank else "не найдена в топ-20 чанков"
            exp = ", ".join(f"ст. {a} «{article_title(retriever, a)}»" for a in o.expected)
            print(f"   - {o.question}")
            print(f"       ждали {exp} -> {where}; нашли {o.found[:5]}")

    if verbose:
        print("\n  Все вопросы:")
        for o in in_corpus:
            mark = f"#{o.rank}" if o.rank else "--"
            print(f"   {mark:>4} {o.top_score:.3f}  {o.question}  -> {o.found[:3]}")

    if not out_corpus:
        return

    print("\n== Вопросы вне базы: насколько уверенно система ошибается ==")
    for o in sorted(out_corpus, key=lambda o: -o.top_score):
        print(f"   {o.top_score:.3f}  {o.question}  -> {o.found[:3]}")

    print("\n== Порог отсечения по score лучшего чанка ==")
    print("   порог   оставляем «своих»   отсекаем «чужих»")
    lo = min(o.top_score for o in outcomes)
    hi = max(o.top_score for o in outcomes)
    t = round(lo, 2)
    while t <= hi:
        kept = sum(1 for o in in_corpus if o.top_score >= t) / len(in_corpus)
        rejected = sum(1 for o in out_corpus if o.top_score < t) / len(out_corpus)
        print(f"   {t:.2f}    {kept:6.1%}              {rejected:6.1%}")
        t = round(t + 0.02, 2)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("dataset", nargs="?", default="eval/gk_rf_1.jsonl")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args()

    with open(args.dataset, encoding="utf-8") as f:
        cases = [json.loads(line) for line in f if line.strip()]

    retriever = Retriever()
    missing = {a for c in cases for a in c["articles"]} - {ch.article_number for ch in retriever.store.chunks}
    if missing:
        print(f"[предупреждение] эталонных статей нет в индексе: {sorted(missing)}", file=sys.stderr)

    report(evaluate(cases, retriever), retriever, args.verbose)


if __name__ == "__main__":
    main()
