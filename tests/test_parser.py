from legal_rag.ingest.parser import parse_articles

SAMPLE = """
Раздел I. Общие положения

Глава 1. Гражданское законодательство

Статья 1. Основные начала гражданского законодательства
1. Гражданское законодательство основывается на признании равенства участников.
2. Граждане приобретают и осуществляют свои гражданские права своей волей.

Статья 2. Отношения, регулируемые гражданским законодательством
Гражданское законодательство определяет правовое положение участников оборота.

Глава 2. Возникновение гражданских прав

Статья 8. Основания возникновения гражданских прав и обязанностей
Гражданские права и обязанности возникают из оснований, предусмотренных законом.
"""


def test_finds_all_articles():
    articles = parse_articles(SAMPLE)
    assert [a.article_number for a in articles] == ["1", "2", "8"]


def test_tracks_section_and_chapter():
    articles = parse_articles(SAMPLE)
    art1, art2, art8 = articles
    assert art1.section.startswith("I")
    assert art1.chapter.startswith("1")
    assert art8.chapter.startswith("2")


def test_article_title_and_body():
    articles = parse_articles(SAMPLE)
    art1 = articles[0]
    assert art1.article_title == "Основные начала гражданского законодательства"
    assert "равенства участников" in art1.text


TOC_SAMPLE = """Гражданский кодекс Российской Федерации

Оглавление
Статья 1. Основные начала гражданского законодательства
Статья 2. Отношения, регулируемые гражданским законодательством
Статья 8. Основания возникновения гражданских прав и обязанностей
""" + SAMPLE


def test_table_of_contents_is_dropped():
    articles = parse_articles(TOC_SAMPLE)
    assert [a.article_number for a in articles] == ["1", "2", "8"]
    assert "равенства участников" in articles[0].text


def test_articles_without_body_are_dropped():
    articles = parse_articles(
        "Статья 1. Заголовок без текста\n\nСтатья 2. Вторая\nТело второй статьи.\n"
    )
    assert [a.article_number for a in articles] == ["2"]


def test_restart_after_real_articles_is_not_treated_as_toc():
    text = SAMPLE + "\nПриложение\n\nСтатья 1. Статья приложения\n" + "Текст приложения. " * 10
    numbers = [a.article_number for a in parse_articles(text)]
    assert numbers == ["1", "2", "8", "1"]


def test_dashed_article_numbers():
    text = (
        "Статья 123.20. Основные положения\nТело.\n\n"
        "Статья 123.20-1. Личный фонд\nТело личного фонда.\n\n"
        "Статья 123.21. Учреждения\nТело учреждений.\n"
    )
    articles = parse_articles(text)
    assert [a.article_number for a in articles] == ["123.20", "123.20-1", "123.21"]
    assert articles[1].article_title == "Личный фонд"


def test_superscript_article_numbers_become_dotted():
    text = (
        "Статья 124. Неоказание помощи больному\nТело.\n\n"
        "Статья 124¹. Воспрепятствование оказанию медицинской помощи\nТело.\n"
    )
    articles = parse_articles(text)
    assert [a.article_number for a in articles] == ["124", "124.1"]
    assert articles[1].article_title == "Воспрепятствование оказанию медицинской помощи"


def test_fractional_chapter_numbers():
    text = (
        "Глава 36. Обеспечение прав работников\n\nСтатья 225. Обучение\nТело.\n\n"
        "Глава 36.1. Расследование несчастных случаев\n\nСтатья 226. Микротравмы\nТело.\n"
    )
    articles = parse_articles(text)
    assert articles[0].chapter == "36. Обеспечение прав работников"
    assert articles[1].chapter == "36.1. Расследование несчастных случаев"


def test_no_articles_falls_back_to_full_text():
    articles = parse_articles("Просто текст без статей.")
    assert len(articles) == 1
    assert articles[0].article_number == ""
    assert "Просто текст" in articles[0].text
