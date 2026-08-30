from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "holdout_v1"
ORACLE_ROOT = ROOT / "eval" / "holdout_v1"

# Post-freeze holdout protocol:
# - authored after Iteration 5 verifier freeze;
# - verifier/compiler/planner semantics must not be changed after observing results;
# - public cases contain no expected verdict;
# - evaluator-only verdicts are written under eval/holdout_v1/.
#
# These cases intentionally reuse the product's stated MVP contract domain while
# changing functions, constants, implementations, and combinations of requirements.

CASES: dict[str, dict[str, str]] = {
    "holdout_001": {
        "issue": """# Inclusive score range\n\n`accept_score` must return every integer from -5 through 5 inclusive unchanged. The reported bug is that the lower boundary -5 is rejected.\n""",
        "original": """def accept_score(value):\n    if -5 < value <= 5:\n        return value\n    return None\n""",
        "patched": """def accept_score(value):\n    if -5 <= value <= 5:\n        return value\n    return None\n""",
        "test": """from app import accept_score\n\n\ndef test_reported_lower_boundary():\n    assert accept_score(-5) == -5\n""",
        "oracle": "complete_fix",
    },
    "holdout_002": {
        "issue": """# Inclusive retry window\n\n`normalize_retry` must return values from 10 through 20 inclusive unchanged. The reported bug is that the lower boundary 10 is rejected.\n""",
        "original": """def normalize_retry(value):\n    if 10 < value < 20:\n        return value\n    return None\n""",
        "patched": """def normalize_retry(value):\n    if 10 <= value < 20:\n        return value\n    return None\n""",
        "test": """from app import normalize_retry\n\n\ndef test_reported_lower_boundary():\n    assert normalize_retry(10) == 10\n""",
        "oracle": "partial_fix",
    },
    "holdout_003": {
        "issue": """# Display-name normalization\n\n`format_display_name` should lowercase names and remove surrounding padding while preserving meaningful internal spaces. The reported bug is surrounding whitespace around a single name.\n""",
        "original": """def format_display_name(value):\n    return value.lower()\n""",
        "patched": """def format_display_name(value):\n    return value.strip().replace(' ', '').lower()\n""",
        "test": """from app import format_display_name\n\n\ndef test_reported_surrounding_whitespace():\n    assert format_display_name(' Alice ') == 'alice'\n""",
        "oracle": "regression_introduced",
    },
    "holdout_004": {
        "issue": """# Contact canonicalization\n\n`canonical_contact` must trim surrounding whitespace and lowercase the value. The reported failure is an uppercase address with padding.\n""",
        "original": """def canonical_contact(value):\n    return value.strip()\n""",
        "patched": """def canonical_contact(value):\n    return value.strip().lower()\n""",
        "test": """from app import canonical_contact\n\n\ndef test_reported_uppercase_address():\n    assert canonical_contact(' User@Example.COM ') == 'user@example.com'\n""",
        "oracle": "complete_fix",
    },
    "holdout_005": {
        "issue": """# Tag slug normalization\n\n`tag_slug` must trim and lowercase text and collapse any run of whitespace into a single hyphen. The reported failure is multiple spaces with surrounding padding.\n""",
        "original": """import re\n\n\ndef tag_slug(value):\n    return re.sub(r'\\s+', '-', value.lower())\n""",
        "patched": """def tag_slug(value):\n    value = value.strip().lower()\n    return value.replace('   ', '-').replace(' ', '-')\n""",
        "test": """from app import tag_slug\n\n\ndef test_reported_multiple_spaces():\n    assert tag_slug(' Hello   World ') == 'hello-world'\n""",
        "oracle": "regression_introduced",
    },
    "holdout_006": {
        "issue": """# Bounded preview text\n\n`preview` must never return more than the requested limit, including very small non-negative limits. The reported failure is a normal limit of five characters.\n""",
        "original": """def preview(text, limit):\n    return text\n""",
        "patched": """def preview(text, limit):\n    if len(text) <= limit:\n        return text\n    return text[:max(limit - 3, 0)] + '...'\n""",
        "test": """from app import preview\n\n\ndef test_reported_limit_five():\n    value = preview('abcdef', 5)\n    assert value == 'ab...'\n    assert len(value) <= 5\n""",
        "oracle": "partial_fix",
    },
    "holdout_007": {
        "issue": """# Optional division\n\n`optional_divide` should return `None` only for division by zero. Invalid operand types must keep raising their normal exceptions instead of being swallowed.\n""",
        "original": """def optional_divide(left, right):\n    return left / right\n""",
        "patched": """def optional_divide(left, right):\n    try:\n        return left / right\n    except Exception:\n        return None\n""",
        "test": """from app import optional_divide\n\n\ndef test_reported_zero_division():\n    assert optional_divide(10, 0) is None\n""",
        "oracle": "regression_introduced",
    },
    "holdout_008": {
        "issue": """# Absolute distance\n\n`distance_from_zero` should return the absolute magnitude for negative integers. The reported example is -11.\n""",
        "original": """def distance_from_zero(value):\n    return value\n""",
        "patched": """def distance_from_zero(value):\n    return value\n""",
        "test": """from app import distance_from_zero\n\n\ndef test_reported_negative_value():\n    assert distance_from_zero(-11) == 11\n""",
        "oracle": "ineffective_fix",
    },
    "holdout_009": {
        "issue": """# Stateful preference store\n\n`PreferenceStore` supports replacing an existing key. The available public example already passes on both revisions, and the issue text does not provide a mechanically checkable nearby contract beyond that example.\n""",
        "original": """class PreferenceStore:\n    def __init__(self):\n        self._values = {}\n\n    def put(self, key, value):\n        self._values[key] = value\n\n    def get(self, key):\n        return self._values.get(key)\n""",
        "patched": """class PreferenceStore:\n    def __init__(self):\n        self._values = {}\n\n    def put(self, key, value):\n        self._values[key] = value\n\n    def get(self, key):\n        return self._values.get(key)\n""",
        "test": """from app import PreferenceStore\n\n\ndef test_available_replacement():\n    store = PreferenceStore()\n    store.put('theme', 'light')\n    store.put('theme', 'dark')\n    assert store.get('theme') == 'dark'\n""",
        "oracle": "inconclusive",
    },
    "holdout_010": {
        "issue": """# Canonical label contract\n\n`canonical_label` must trim surrounding whitespace, lowercase the value, and preserve meaningful internal spaces. The reported example contains both surrounding and internal spaces.\n""",
        "original": """def canonical_label(value):\n    return value.lower()\n""",
        "patched": """def canonical_label(value):\n    value = value.strip()\n    if ' ' in value:\n        return value.lower()\n    return value\n""",
        "test": """from app import canonical_label\n\n\ndef test_reported_compound_label():\n    assert canonical_label(' Alice Bob ') == 'alice bob'\n""",
        "oracle": "partial_fix",
    },
    "holdout_011": {
        "issue": """# Account label normalization\n\n`account_label` must trim surrounding whitespace, lowercase the value, and preserve meaningful internal spaces. The reported failure is only the surrounding padding.\n""",
        "original": """def account_label(value):\n    return value.lower()\n""",
        "patched": """def account_label(value):\n    return value.strip().replace(' ', '').lower()\n""",
        "test": """from app import account_label\n\n\ndef test_reported_padding():\n    assert account_label(' Alice ') == 'alice'\n""",
        "oracle": "regression_introduced",
    },
    "holdout_012": {
        "issue": """# Normalized identifier\n\n`normalized_identifier` must trim surrounding whitespace, lowercase the value, and preserve meaningful internal spaces. The reported example is a two-word identifier with surrounding whitespace.\n""",
        "original": """def normalized_identifier(value):\n    return value.lower()\n""",
        "patched": """def normalized_identifier(value):\n    value = value.strip()\n    if ' ' in value:\n        return value.lower()\n    return value\n""",
        "test": """from app import normalized_identifier\n\n\ndef test_reported_two_word_identifier():\n    assert normalized_identifier(' Red Team ') == 'red team'\n""",
        "oracle": "partial_fix",
    },
}


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build() -> None:
    if OUTPUT.exists():
        shutil.rmtree(OUTPUT)
    OUTPUT.mkdir(parents=True)
    ORACLE_ROOT.mkdir(parents=True, exist_ok=True)

    oracles: dict[str, str] = {}
    for case_id, case in CASES.items():
        root = OUTPUT / case_id
        _write_text(root / "issue.md", case["issue"])
        _write_text(root / "original" / "app.py", case["original"])
        _write_text(root / "patched" / "app.py", case["patched"])
        _write_text(root / "original" / "test_app.py", case["test"])
        _write_text(root / "patched" / "test_app.py", case["test"])
        _write_text(
            root / "case.json",
            json.dumps(
                {
                    "case_id": case_id,
                    "test_command": ["python", "-m", "pytest", "-q"],
                    "notes": "Post-freeze Holdout v1 public case. Expected verdict is evaluator-only.",
                },
                indent=2,
            )
            + "\n",
        )
        oracles[case_id] = case["oracle"]

    _write_text(ORACLE_ROOT / "oracles.json", json.dumps(oracles, indent=2) + "\n")

    digest = hashlib.sha256()
    for path in sorted(OUTPUT.rglob("*")):
        if path.is_file():
            digest.update(path.relative_to(OUTPUT).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(path.read_bytes())
            digest.update(b"\0")

    print(f"built {len(CASES)} post-freeze public holdout cases under {OUTPUT}")
    print(f"public holdout sha256: {digest.hexdigest()}")
    print(f"evaluator oracles: {ORACLE_ROOT / 'oracles.json'}")


if __name__ == "__main__":
    build()
