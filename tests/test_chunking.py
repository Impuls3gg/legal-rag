from legal_rag.chunking import act_to_chunks
from legal_rag.models import RawAct

SAMPLE = """
Статья 1. Короткая статья
Небольшой текст.

Статья 2. Длинная статья
""" + "\n".join(f"Пункт {i}. " + "текст " * 20 for i in range(50))


def test_short_article_is_one_chunk():
    act = RawAct(act_id="test", title="Тестовый акт", act_type="закон", text=SAMPLE)
    chunks = act_to_chunks(act, max_chars=1500)
    art1_chunks = [c for c in chunks if c.article_number == "1"]
    assert len(art1_chunks) == 1


def test_long_article_is_split_with_shared_metadata():
    act = RawAct(act_id="test", title="Тестовый акт", act_type="закон", text=SAMPLE)
    chunks = act_to_chunks(act, max_chars=500)
    art2_chunks = [c for c in chunks if c.article_number == "2"]
    assert len(art2_chunks) > 1
    assert all(c.act_title == "Тестовый акт" for c in art2_chunks)
    assert all(c.article_title == "Длинная статья" for c in art2_chunks)


def test_chunk_ids_are_unique():
    act = RawAct(act_id="test", title="Тестовый акт", act_type="закон", text=SAMPLE)
    chunks = act_to_chunks(act, max_chars=500)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_table_of_contents_does_not_duplicate_chunks():
    text = "Оглавление\nСтатья 1. Короткая статья\nСтатья 2. Длинная статья\n" + SAMPLE
    act = RawAct(act_id="test", title="Тестовый акт", act_type="закон", text=text)
    chunks = act_to_chunks(act, max_chars=500)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(c.text.strip() for c in chunks)


def test_full_text_carries_heading_into_every_part():
    act = RawAct(act_id="test", title="Тестовый акт", act_type="закон", text=SAMPLE)
    parts = [c for c in act_to_chunks(act, max_chars=500) if c.article_number == "2"]
    assert len(parts) > 1
    for chunk in parts:
        assert "Тестовый акт" in chunk.full_text()
        assert "Длинная статья" in chunk.full_text()
        assert chunk.text in chunk.full_text()
