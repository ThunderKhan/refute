from app import format_username


def test_trims_surrounding_whitespace():
    assert format_username("  Alice  ") == "alice"


def test_preserves_internal_spaces():
    assert format_username("Mary Jane") == "mary jane"
