from app import first_nonempty


def test_whitespace_only_values_are_skipped():
    assert first_nonempty(["", "   ", "answer"]) == "answer"
