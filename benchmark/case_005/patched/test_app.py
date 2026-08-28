from app import canonical_email


def test_email_is_trimmed_and_lowercased():
    assert canonical_email("  User@Example.COM  ") == "user@example.com"
