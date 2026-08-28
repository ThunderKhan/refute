from app import magnitude


def test_negative_value_becomes_positive():
    assert magnitude(-7) == 7


def test_positive_value_is_unchanged():
    assert magnitude(4) == 4
