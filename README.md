# legal-rag

Вопросно-ответная система по законодательству РФ, работающая целиком на
локальной машине. Пользователь задаёт вопрос на
русском, система находит релевантные статьи закона и отвечает строго на их
основе, со ссылками на статьи.

## Как запустить проект у себя

Нужны Python 3.10+ и [uv](https://docs.astral.sh/uv/). GPU не обязателен.

**1. Запуск**

Torch нужен в любом случае, но сборок две — выберите одну. Без `--extra`
torch не установится вовсе: так `uv sync` не подменит выбранную сборку
дефолтной с PyPI.

Запуск на CPU (~6 ГБ свободной RAM, скачивание ~200 МБ):

```bash
uv sync --extra cpu --extra dev
```

Запуск на GPU (NVIDIA от 6 ГБ VRAM, скачивание ~2.5 ГБ):

```bash
uv sync --extra cu126 --extra dev
```

Проверить, что карта видна:

```bash
uv run python -c "import torch; print(torch.cuda.is_available())"
```

Устройство выбирается автоматически: CUDA, если стоит GPU-сборка и карта
доступна, иначе CPU. Принудительно — `LEGAL_RAG_DEVICE=cpu`.

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

**4. Индексация**

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

Если ответа в базе нет, система отказывается отвечать, а не выдумывает — LLM
при этом даже не загружается:

```bash
uv run python -m legal_rag.cli ask "Что такое необходимая оборона?"
```

```
В базе нет статей по этому вопросу: лучшее совпадение 0.423 ниже порога 0.55
(LEGAL_RAG_MIN_SCORE). Ближайшее, что нашлось:
(0.423) Гражданский кодекс Российской Федерации (часть первая), глава 23. ОБЕСПЕЧЕНИЕ ИСПОЛНЕНИЯ ОБЯЗАТЕЛЬСТВ, ст. 329
...
```

**Оценить качество поиска:**

```bash
uv run python scripts/evaluate.py        # eval/gk_rf_1.jsonl
uv run python scripts/evaluate.py -v     # результат по каждому вопросу
```

Набор `eval/gk_rf_1.jsonl` — 60 вопросов с эталонными статьями и 14 вопросов
вне базы. Скрипт считает Recall@k и MRR на уровне статей и строит таблицу
порогов отказа. Текущий результат на ГК РФ ч. 1: Recall@1 95%, Recall@5 98%,
MRR 0.968; порог 0.55 оставляет 97% вопросов с ответом в базе и отсекает 75%
вопросов вне её (оставшиеся 25% — смежные темы из части второй ГК: аренда,
заём, купля-продажа).

**Веб-интерфейс** (Streamlit, модели загружаются один раз и остаются в памяти):

```bash
uv sync --extra cu126 --extra web
uv run streamlit run src/legal_rag/web.py
```

## Деплой на сервер (Docker Compose, GPU)

На сервере нужны драйвер NVIDIA ≥ 560, Docker и
[NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html).
Проверка, что контейнеры видят GPU:

```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

Веса моделей и индекс в образ не входят, они монтируются из `models/` и `data/`.
Есть два варианта:

- скопировать с машины разработчика готовые `data/raw/`, `data/index/` и
  (по желанию) `models/`, например через `rsync`;
- собрать на сервере: модели скачаются с Hub в том `hf-cache` при первом запуске.

```bash
docker compose build
# индекс, если он не скопирован:
docker compose run --rm web python scripts/fetch_wikisource.py --page "Гражданский кодекс РФ" \
    --chapters 1-29 --act-id gk-rf-chast-1 \
    --title "Гражданский кодекс Российской Федерации (часть первая)" --number 51-ФЗ --date 1994-11-30
docker compose run --rm web python -m legal_rag.cli build-index
docker compose up -d
```

Интерфейс откроется на `http://<сервер>:8501`. Первый вопрос после старта
ждёт загрузки моделей, около минуты. Логи смотрите через `docker compose logs -f web`.

В Streamlit нет авторизации. Если сервер доступен из интернета, закройте порт
8501 и поставьте перед ним reverse proxy с паролем (nginx + basic auth, Caddy)
либо ходите через SSH-туннель: `ssh -L 8501:localhost:8501 <сервер>`.

**Настройки** задаются переменными окружения с префиксом `LEGAL_RAG_`:
`TOP_K` (6), `MIN_SCORE` (0.55, порог отказа; 0 — отключить),
`CHUNK_MAX_CHARS` (1500), `LLM_MAX_NEW_TOKENS` (512), `LLM_TEMPERATURE` (0),
`EMBEDDING_MODEL`, `LLM_MODEL`, `DEVICE` (auto).
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
  pipeline.py        вопрос -> ответ: поиск, порог отказа, генерация (общее для CLI и веба)
  web.py             веб-интерфейс на Streamlit
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
