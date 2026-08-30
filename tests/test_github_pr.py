from pathlib import Path

import pytest

from refute.github_pr import (
    GitHubPRIngestionError,
    _declared_test_dependencies,
    _detect_pytest,
    _is_pytest_file,
    _linked_issue_number,
    _materialize_patch_tests_on_base,
    parse_github_pr_url,
)


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


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        ("tests/test_cli.py", True),
        ("pkg/test_api.py", True),
        ("pkg/api_test.py", True),
        ("tests/helpers.py", True),
        ("src/app.py", False),
        ("docs/test_plan.md", False),
    ],
)
def test_is_pytest_file(path: str, expected: bool) -> None:
    assert _is_pytest_file(path) is expected


def test_materialize_patch_tests_on_base_copies_only_selected_files(tmp_path: Path) -> None:
    original = tmp_path / "original"
    patched = tmp_path / "patched"
    (original / "tests").mkdir(parents=True)
    (patched / "tests").mkdir(parents=True)
    (patched / "tests" / "test_fix.py").write_text("def test_fix():\n    assert True\n", encoding="utf-8")
    (patched / "src").mkdir()
    (patched / "src" / "app.py").write_text("VALUE = 2\n", encoding="utf-8")

    _materialize_patch_tests_on_base(original, patched, ("tests/test_fix.py",))

    assert (original / "tests" / "test_fix.py").read_text(encoding="utf-8") == "def test_fix():\n    assert True\n"
    assert not (original / "src" / "app.py").exists()


def test_declared_test_dependencies_collects_runtime_and_test_groups(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "sample"
version = "0.1.0"
dependencies = ["pydantic>=2"]

[project.optional-dependencies]
test = ["pytest>=8", "requests>=2"]

[dependency-groups]
dev = ["pytest-cov>=5"]
""".strip(),
        encoding="utf-8",
    )

    assert _declared_test_dependencies(tmp_path) == [
        "pydantic>=2",
        "pytest>=8",
        "requests>=2",
        "pytest-cov>=5",
    ]


def test_declared_test_dependencies_adds_pytest_when_missing(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        """
[project]
name = "sample"
version = "0.1.0"
dependencies = ["requests>=2"]
""".strip(),
        encoding="utf-8",
    )

    assert _declared_test_dependencies(tmp_path) == ["requests>=2", "pytest>=8,<9"]
