import pytest

from app import safe_divide


def test_zero_divisor_returns_none():
    assert safe_divide(10, 0) is None


def test_invalid_operands_still_raise():
    with pytest.raises(TypeError):
        safe_divide("ten", 2)
