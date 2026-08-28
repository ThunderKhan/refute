from app import truncate


def test_truncation_respects_normal_limit():
    assert len(truncate("abcdefgh", 5)) <= 5


def test_truncation_respects_tiny_limit():
    assert len(truncate("abcdefgh", 2)) <= 2
