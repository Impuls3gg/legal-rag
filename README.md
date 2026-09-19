# legal-rag

Вопросно-ответная система по законодательству РФ, работающая целиком на
локальной машине. Пользователь задаёт вопрос на
русском, система находит релевантные статьи закона и отвечает строго на их
основе, со ссылками на статьи.

## Как запустить проект у себя

Нужны Python 3.10+, [uv](https://docs.astral.sh/uv/) и ~6 ГБ свободной
оперативной памяти. GPU не нужен.

**1. Запуск**

```bash
uv sync --extra dev
```

**2. Модели**

| Роль | Модель | На диске | В памяти |
|---|---|---|---|
| эмбеддинги | `BAAI/bge-m3` | 2.3 ГБ | ~2.3 ГБ |
| генерация | `Qwen/Qwen2.5-1.5B-Instruct` | 3.1 ГБ | ~3.2 ГБ |

**3. Данные**

Быстрее всего взять кодекс с ru.wikisource.org — скрипт скачивает главы и
складывает текст с метаданными в `data/raw/`:

```bash
uv run python scripts/fetch_wikisource.py \
    --page "Гражданский кодекс РФ" --chapters 1-29 \
    --act-id gk-rf-chast-1 \
    --title "Гражданский кодекс Российской Федерации (часть первая)" \
    --number 51-ФЗ --date 1994-11-30
```

Свой текст добавляется через
`uv run python scripts/add_act.py` или вручную: `data/raw/<act_id>/text.txt`
плюс `meta.json` с полями `title`, `act_type`, `number`, `date`, `source_url`.
Оглавление в начале текста отбрасывается автоматически.

**4. Индекс**

```bash
uv run python -m legal_rag.cli build-index
```

**5. Проверка**

```bash
uv run pytest tests/ -q
```

## Как использовать

**Задать вопрос:**

```bash
uv run python -m legal_rag.cli ask "Может ли суд применить исковую давность по своей инициативе?"
```

```
Нет, суд не может применять исковую давность по своей инициативе. Согласно
статье 199 Гражданского кодекса РФ, исковая давность применяется только по
заявлению стороны в споре, сделанному до вынесения судом решения.

--- Источники ---
(0.661) Гражданский кодекс Российской Федерации (часть первая), глава 12. ИСКОВАЯ ДАВНОСТЬ, ст. 199
(0.617) Гражданский кодекс Российской Федерации (часть первая), глава 12. ИСКОВАЯ ДАВНОСТЬ, ст. 205
...
```

**Оценить качество поиска:**

```bash
uv run python scripts/evaluate.py        # eval/gk_rf_1.jsonl
uv run python scripts/evaluate.py -v     # результат по каждому вопросу
```

Набор `eval/gk_rf_1.jsonl` — 60 вопросов с эталонными статьями и 14 вопросов
вне базы. Скрипт считает Recall@k и MRR на уровне статей.

**Настройки** задаются переменными окружения с префиксом `LEGAL_RAG_`:
`TOP_K` (6), `CHUNK_MAX_CHARS` (1500), `LLM_MAX_NEW_TOKENS` (512),
`LLM_TEMPERATURE` (0), `EMBEDDING_MODEL`, `LLM_MODEL`, `DEVICE` (cpu).
Полный список — в `src/legal_rag/config.py`.

## Структура

```
src/legal_rag/
  ingest/
    parser.py        разбор текста акта на раздел / глава / статья, отсечение оглавления
    local_files.py   источник: data/raw/<act_id>/
    pravo_gov.py     источник: pravo.gov.ru (best-effort скрапер)
    base.py          протокол источника ActSource
  chunking.py        статья -> Chunk, длинные статьи режутся по абзацам
  embeddings.py      HFEmbedder: bge-m3 через transformers
  index/faiss_store.py  FAISS IndexFlatIP + chunks.json с метаданными
  retrieval.py       вопрос -> top-k чанков
  llm.py             HFLLM: Qwen2.5 через transformers, промпт «строго по контексту»
  models.py          RawAct, Chunk, SearchResult
  config.py          настройки (LEGAL_RAG_*)
  cli.py             команды build-index / ask
scripts/
  fetch_wikisource.py  загрузка кодекса с Викитеки по главам
  add_act.py           интерактивное добавление акта из буфера обмена
  evaluate.py          метрики поиска на eval-наборе
eval/gk_rf_1.jsonl   вопросы с эталонными статьями
tests/               парсер и чанкинг — самые хрупкие места пайплайна
data/
  raw/               исходные тексты актов (в .gitignore)
  index/             FAISS-индекс и метаданные (в .gitignore)
models/              локальные веса моделей, если не через Hub (в .gitignore)
```
