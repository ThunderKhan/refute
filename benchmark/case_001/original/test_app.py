from app import clamp_percentage


def test_zero_is_valid():
    assert clamp_percentage(0) == 0


def test_hundred_is_valid():
    assert clamp_percentage(100) == 100
