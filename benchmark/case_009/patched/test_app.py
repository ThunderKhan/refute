from app import slugify


def test_slug_is_lowercase_and_collapses_whitespace():
    assert slugify("  Hello   Brave World  ") == "hello-brave-world"
