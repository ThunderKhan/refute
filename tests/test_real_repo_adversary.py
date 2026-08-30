from refute.real_repo_adversary import (
    _candidate_relevance,
    _parse_nodeids,
    _test_name,
)


def test_parse_nodeids_filters_pytest_summary_noise() -> None:
    stdout = """
tests/test_cli.py::test_one
tests/test_cli.py::TestGroup::test_two[param]

2 tests collected in 0.01s
"""
    assert _parse_nodeids(stdout) == (
        "tests/test_cli.py::test_one",
        "tests/test_cli.py::TestGroup::test_two[param]",
    )


def test_test_name_strips_parametrization() -> None:
    assert _test_name("tests/test_cli.py::TestGroup::test_two[value]") == "test_two"


def test_candidate_relevance_prefers_changed_test_file_and_semantic_overlap() -> None:
    context = {
        "changed_tests": ["tests/test_cli.py"],
        "changed_files": ["pkg/cli.py"],
        "diff": "def fetch_fork_pr(): raise GitOperationError('PR not from fork')",
    }
    nearby = _candidate_relevance(
        "tests/test_cli.py::test_fetch_fork_pr_error",
        context,
        "report fork PR resolution errors without traceback",
    )
    unrelated = _candidate_relevance(
        "tests/test_math.py::test_addition",
        context,
        "report fork PR resolution errors without traceback",
    )
    assert nearby > unrelated
