from pathlib import Path

import pytest

from refute.github_pr import GitHubPRIngestionError, _detect_pytest, _linked_issue_number, parse_github_pr_url


def test_parse_github_pr_url() -> None:
    assert parse_github_pr_url("https://github.com/example/project/pull/42") == ("example", "project", 42)


@pytest.mark.parametrize(
    "value",
    [
        "http://github.com/example/project/pull/42",
        "https://gitlab.com/example/project/pull/42",
        "https://github.com/example/project/issues/42",
        "https://github.com/example/project/pull/nope",
    ],
)
def test_parse_github_pr_url_rejects_unsupported_shapes(value: str) -> None:
    with pytest.raises(GitHubPRIngestionError):
        parse_github_pr_url(value)


def test_linked_issue_number_recognizes_common_closing_keywords() -> None:
    assert _linked_issue_number("Fixes #123") == 123
    assert _linked_issue_number("This resolves #77 when merged") == 77
    assert _linked_issue_number("Closes #9") == 9
    assert _linked_issue_number("Related to #4") is None


def test_detect_pytest_from_tests_directory(tmp_path: Path) -> None:
    (tmp_path / "tests").mkdir()
    command = _detect_pytest(tmp_path)
    assert command is not None
    assert command[-3:] == ("-m", "pytest", "-q")


def test_detect_pytest_rejects_unknown_project(tmp_path: Path) -> None:
    assert _detect_pytest(tmp_path) is None
