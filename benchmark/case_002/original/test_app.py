from app import normalize_percentage


def test_zero_is_valid():
    assert normalize_percentage(0) == 0


def test_hundred_is_valid():
    assert normalize_percentage(100) == 100
