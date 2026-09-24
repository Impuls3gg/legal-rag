# Образ веб-интерфейса на GPU (torch cu126). Веса моделей и индекс в образ не
# входят — они монтируются томами (см. docker-compose.yml), так что образ
# пересобирается только при изменении кода или зависимостей.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH=/opt/venv/bin:$PATH \
    # В образе нет C-компилятора, а torch >= 2.14 без этого флага компилирует
    # Triton-ядра при первом generate() и падает. config.py тоже его ставит,
    # но только если импортирован раньше torch — здесь надёжнее.
    TORCH_DISABLE_NATIVE_JIT=1 \
    HF_HOME=/cache/huggingface \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Сначала только зависимости: этот слой (~3 ГБ с torch) кэшируется и не
# пересобирается при правке кода.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-install-project --extra cu126 --extra web

COPY src ./src
COPY scripts ./scripts
COPY eval ./eval
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --extra cu126 --extra web

EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8501/_stcore/health')"

# fileWatcherType=none: наблюдатель Streamlit обходит атрибуты модулей и
# спотыкается о torch.classes; в проде перезагрузка по изменению файлов не нужна.
CMD ["streamlit", "run", "src/legal_rag/web.py", \
     "--server.address=0.0.0.0", "--server.port=8501", "--server.headless=true", \
     "--server.fileWatcherType=none", "--browser.gatherUsageStats=false"]
