from pathlib import Path

from refute.benchmark import discover_cases
from refute.case import load_case


REPO_ROOT = Path(__file__).resolve().parents[1]
BENCHMARK_ROOT = REPO_ROOT / "benchmark"


def test_benchmark_catalog_has_ten_valid_cases():
    cases = discover_cases(BENCHMARK_ROOT)

    assert len(cases) == 10
    assert [path.name for path in cases] == [f"case_{index:03d}" for index in range(1, 11)]
    assert all(load_case(path).case_id == path.name for path in cases)
