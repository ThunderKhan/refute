from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEGACY = ROOT / "benchmark"
OUTPUT = ROOT / "benchmark_v2"

PUBLIC_TESTS: dict[str, str] = {
    "case_001": '''from app import clamp_percentage\n\n\ndef test_reported_zero_boundary():\n    assert clamp_percentage(0) == 0\n''',
    "case_002": '''from app import normalize_percentage\n\n\ndef test_reported_lower_boundary():\n    assert normalize_percentage(0) == 0\n''',
    "case_003": '''from app import format_username\n\n\ndef test_reported_surrounding_whitespace():\n    assert format_username(" Alice ") == "alice"\n''',
    "case_004": '''from app import magnitude\n\n\ndef test_reported_negative_value():\n    assert magnitude(-7) == 7\n''',
    "case_005": '''from app import canonical_email\n\n\ndef test_reported_uppercase_email():\n    assert canonical_email(" User@Example.COM ") == "user@example.com"\n''',
    "case_006": '''from app import truncate\n\n\ndef test_reported_length_bound():\n    value = truncate("abcdef", 5)\n    assert value == "ab..."\n    assert len(value) <= 5\n''',
    "case_007": '''from app import safe_divide\n\n\ndef test_reported_zero_division():\n    assert safe_divide(10, 0) is None\n''',
    "case_008": '''from app import first_nonempty\n\n\ndef test_reported_whitespace_only_value():\n    assert first_nonempty(["", "   ", "ready"]) == "ready"\n''',
    "case_009": '''from app import slugify\n\n\ndef test_reported_slug_normalization():\n    assert slugify(" Hello   World ") == "hello-world"\n''',
    "case_010": '''from app import Cache\n\n\ndef test_available_sequential_update():\n    cache = Cache()\n    cache.update("x", 1)\n    cache.update("x", 2)\n    assert cache.get("x") == 2\n''',
}


def build() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)

    for case_id, public_test in PUBLIC_TESTS.items():
        source = LEGACY / case_id
        target = OUTPUT / case_id
        (target / "original").mkdir(parents=True)
        (target / "patched").mkdir(parents=True)

        shutil.copy2(source / "issue.md", target / "issue.md")
        shutil.copy2(source / "original" / "app.py", target / "original" / "app.py")
        shutil.copy2(source / "patched" / "app.py", target / "patched" / "app.py")
        (target / "original" / "test_app.py").write_text(public_test, encoding="utf-8")
        (target / "patched" / "test_app.py").write_text(public_test, encoding="utf-8")

        metadata = {
            "case_id": case_id,
            "test_command": ["python", "-m", "pytest", "-q"],
            "notes": "Benchmark v2 public case. Expected verdict and hidden tests are evaluator-only.",
        }
        (target / "case.json").write_text(
            json.dumps(metadata, indent=2) + "\n", encoding="utf-8"
        )

    (OUTPUT / "README.md").write_text(
        "# Benchmark v2\n\n"
        "Public verification cases only. `case.json` intentionally contains no expected verdict. "
        "Evaluator-only oracles and hidden tests live under `eval/benchmark_v2/` and are never passed "
        "to refute agents. Regenerate this directory with `python scripts/build_benchmark_v2.py`.\n",
        encoding="utf-8",
    )
    print(f"built {len(PUBLIC_TESTS)} public cases under {OUTPUT}")


if __name__ == "__main__":
    build()
