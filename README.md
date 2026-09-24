# legal-rag

Вопросно-ответная система по законодательству РФ, которая работает целиком на
своём сервере. Пользователь задаёт вопрос на русском, система находит
релевантные статьи закона и отвечает строго на их основе, со ссылками на статьи.

## Требования

- NVIDIA GPU от 6 ГБ VRAM, поколение Turing (GTX 16xx / RTX 20xx) и новее
- драйвер NVIDIA ≥ 560
- Docker с Compose и [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/latest/install-guide.html)

Проверка, что контейнеры видят GPU:

```bash
docker run --rm --gpus all ubuntu nvidia-smi
```

Модели:

| Роль | Модель | На диске | VRAM (fp16) |
|---|---|---|---|
| эмбеддинги | `BAAI/bge-m3` | 2.3 ГБ | ~1.1 ГБ |
| генерация | `Qwen/Qwen2.5-1.5B-Instruct` | 3.1 ГБ | ~3.1 ГБ |

Веса моделей и индекс в образ не входят: они монтируются из `models/` и `data/`.
Если в `models/` нет весов, модели скачаются с Hugging Face Hub в том `hf-cache`
при первом запуске.

## Запуск

**1. Сборка образа**

```bash
docker compose build
```

**2. Данные**

Быстрее всего взять кодекс с ru.wikisource.org: скрипт скачивает главы и
складывает текст с метаданными в `data/raw/`.

```bash
docker compose run --rm web python scripts/fetch_wikisource.py \
    --page "Гражданский кодекс РФ" --chapters 1-29 \
    --act-id gk-rf-chast-1 \
    --title "Гражданский кодекс Российской Федерации (часть первая)" \
    --number 51-ФЗ --date 1994-11-30
```

Свой текст добавляется через
`docker compose run --rm web python scripts/add_act.py` или вручную:
`data/raw/<act_id>/text.txt` плюс `meta.json` с полями `title`, `act_type`,
`number`, `date`, `source_url`. Оглавление в начале текста отбрасывается
автоматически.

**3. Индексация**

```bash
docker compose run --rm web python -m legal_rag.cli build-index
```

Индекс пересобирается после каждого изменения `data/raw/`.

**4. Запуск веб-интерфейса**

```bash
docker compose up -d
```

Интерфейс откроется на `http://<сервер>:8501`. Первый вопрос после старта
ждёт загрузки моделей, около минуты. Логи смотрите через `docker compose logs -f web`.

В Streamlit нет авторизации. Если сервер доступен из интернета, закройте порт
8501 и поставьте перед ним reverse proxy с паролем (nginx + basic auth, Caddy)
либо ходите через SSH-туннель: `ssh -L 8501:localhost:8501 <сервер>`.

## Как использовать

Основной способ — веб-интерфейс. Под каждым ответом есть список статей, на
которых он построен, с их текстом.

Если ответа в базе нет, система отказывается отвечать, а не выдумывает. LLM
при этом не запускается.

**Вопрос из командной строки:**

```bash
docker compose run --rm web python -m legal_rag.cli ask "Может ли суд применить исковую давность по своей инициативе?"
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
docker compose run --rm web python scripts/evaluate.py        # eval/gk_rf_1.jsonl
docker compose run --rm web python scripts/evaluate.py -v     # результат по каждому вопросу
```

Набор `eval/gk_rf_1.jsonl` — 60 вопросов с эталонными статьями и 14 вопросов
вне базы. Скрипт считает Recall@k и MRR на уровне статей и строит таблицу
порогов отказа. Текущий результат на ГК РФ ч. 1: Recall@1 95%, Recall@5 98%,
MRR 0.968; порог 0.55 оставляет 97% вопросов с ответом в базе и отсекает 75%
вопросов вне её (оставшиеся 25% — смежные темы из части второй ГК: аренда,
заём, купля-продажа).

## Настройки

Задаются переменными окружения с префиксом `LEGAL_RAG_` в секции `environment:`
файла `docker-compose.yml`, после изменения — `docker compose up -d`:
`TOP_K` (6), `MIN_SCORE` (0.55, порог отказа; 0 — отключить),
`CHUNK_MAX_CHARS` (1500), `LLM_MAX_NEW_TOKENS` (512), `LLM_TEMPERATURE` (0),
`EMBEDDING_MODEL`, `LLM_MODEL`.
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
tests/               тесты парсера и чанкинга
Dockerfile           образ на torch cu126 со Streamlit
docker-compose.yml   сервис web: GPU, порт 8501, тома models/, data/, hf-cache
data/
  raw/               исходные тексты актов (в .gitignore)
  index/             FAISS-индекс и метаданные (в .gitignore)
models/              локальные веса моделей, если не через Hub (в .gitignore)
```
