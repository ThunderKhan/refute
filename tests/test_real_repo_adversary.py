from refute.real_repo_adversary import _parse_nodeids, _test_name


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
