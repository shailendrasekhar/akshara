from akshara.tts_engine import split_into_sentences


def test_split_into_sentences():
    assert split_into_sentences("One. Two! Three? Four") == ["One.", "Two!", "Three?", "Four"]


def test_split_ignores_blank():
    assert split_into_sentences("   ") == []
