"""Веб-интерфейс на Streamlit.

    uv run streamlit run src/legal_rag/web.py

Модели грузятся один раз на процесс (st.cache_resource) и общие для всех
сессий. Каждый вопрос обрабатывается независимо: история чата только
отображается, в контекст модели не попадает.
"""
from __future__ import annotations

import streamlit as st

from legal_rag.config import resolve_device, settings
from legal_rag.pipeline import Answer, RAGPipeline

st.set_page_config(page_title="legal-rag", page_icon="⚖️")


@st.cache_resource(show_spinner="Загружаю модели (первый запуск — до минуты)...")
def get_pipeline() -> RAGPipeline:
    return RAGPipeline()


def render_sources(answer: Answer) -> None:
    label = "Ближайшие статьи" if answer.refused else "Источники"
    with st.expander(f"{label} ({len(answer.sources)})"):
        for r in answer.sources:
            st.markdown(f"**({r.score:.3f}) {r.chunk.citation()}**")
            if r.chunk.article_title:
                st.caption(r.chunk.article_title)
            st.text(r.chunk.text)


def render_answer(answer: Answer) -> None:
    if answer.refused:
        st.warning(
            f"В базе нет статей по этому вопросу: лучшее совпадение "
            f"{answer.best_score:.3f} ниже порога {settings.min_score:.2f}."
        )
    else:
        st.markdown(answer.text)
    render_sources(answer)


st.title("Вопросы по законодательству РФ")
st.caption(
    "Ответ строится только по статьям из базы, со ссылками на них. "
    "Тексты кодексов взяты с Викитеки и могут отставать от действующей "
    "редакции. Это не юридическая консультация."
)

with st.sidebar:
    st.markdown(f"**Устройство:** `{resolve_device()}`")
    st.markdown(f"**Эмбеддинги:** `{settings.embedding_model}`")
    st.markdown(f"**LLM:** `{settings.llm_model}`")
    st.markdown(f"**Порог отказа:** {settings.min_score:.2f}, **top-k:** {settings.top_k}")
    if st.button("Очистить историю"):
        st.session_state.history = []

try:
    pipeline = get_pipeline()
except FileNotFoundError as e:  # индекс не построен
    st.error(str(e))
    st.stop()

st.session_state.setdefault("history", [])
for answer in st.session_state.history:
    with st.chat_message("user"):
        st.markdown(answer.question)
    with st.chat_message("assistant"):
        render_answer(answer)

if question := st.chat_input("Например: каков общий срок исковой давности?"):
    with st.chat_message("user"):
        st.markdown(question)
    with st.chat_message("assistant"):
        with st.spinner("Ищу статьи и формулирую ответ..."):
            answer = pipeline.ask(question)
        render_answer(answer)
    st.session_state.history.append(answer)
