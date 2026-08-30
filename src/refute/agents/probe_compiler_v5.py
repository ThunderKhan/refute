from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import VerificationCase
from .challenger_v32 import extract_contract_spans
from .challenger_v4 import discover_public_targets


@dataclass(frozen=True, slots=True)
class ContractProbeV5:
    probe_id: str
    kind: str
    contract_id: str
    contract_text: str
    description: str
    test_code: str


def _pytest_equals(target: str, args: str, expected: str) -> str:
    return (
        f"from app import {target}\n\n\n"
        "def test_refute_probe():\n"
        f"    assert {target}({args}) == {expected}\n"
    )


def _pytest_len_lte(target: str, text: str, limit: int) -> str:
    return (
        f"from app import {target}\n\n\n"
        "def test_refute_probe():\n"
        f"    assert len({target}({text!r}, {limit})) <= {limit}\n"
    )


def _pytest_raises(target: str, args: str, exception: str) -> str:
    return (
        "import pytest\n"
        f"from app import {target}\n\n\n"
        "def test_refute_probe():\n"
        f"    with pytest.raises({exception}):\n"
        f"        {target}({args})\n"
    )


def compile_contract_probes_v5(case: VerificationCase) -> tuple[ContractProbeV5, ...]:
    """Compile a bounded probe pool from public issue contracts only.

    The compiler deliberately supports a small explicit contract vocabulary for the
    MVP rather than asking the language model to invent executable assertions.
    No evaluator oracle or hidden test material is read here.
    """
    targets = discover_public_targets(case)
    if not targets:
        return ()
    target = targets[0]
    spans = extract_contract_spans(case.issue_text)
    issue = " ".join(span.text for span in spans)
    lowered = issue.casefold()
    probes: list[ContractProbeV5] = []

    def add(kind: str, span_index: int, description: str, test_code: str) -> None:
        span = spans[min(max(span_index, 0), len(spans) - 1)]
        probes.append(
            ContractProbeV5(
                probe_id=f"p{len(probes) + 1}",
                kind=kind,
                contract_id=span.contract_id,
                contract_text=span.text,
                description=description,
                test_code=test_code,
            )
        )

    inclusive = re.search(r"from\s+(-?\d+)\s+through\s+(-?\d+)\s+inclusive", lowered)
    if inclusive:
        low = int(inclusive.group(1))
        high = int(inclusive.group(2))
        midpoint = low + (high - low) // 2
        add(
            "remaining_requirement",
            0,
            f"exercise the inclusive upper boundary {high}",
            _pytest_equals(target, repr(high), repr(high)),
        )
        if midpoint not in {low, high}:
            add(
                "remaining_requirement",
                0,
                f"exercise an interior value {midpoint} from the stated inclusive range",
                _pytest_equals(target, repr(midpoint), repr(midpoint)),
            )

    if "preserving meaningful internal spaces" in lowered or "preserve meaningful internal spaces" in lowered:
        add(
            "regression_guard",
            0,
            "preserve a meaningful internal space while normalizing case",
            _pytest_equals(target, repr("Mary Jane"), repr("mary jane")),
        )
        add(
            "regression_guard",
            0,
            "preserve multiple words separated by internal spaces",
            _pytest_equals(target, repr("Alice Bob"), repr("alice bob")),
        )

    if "trim surrounding whitespace" in lowered and "lowercase" in lowered:
        add(
            "regression_guard",
            0,
            "lowercase an address without relying on surrounding whitespace",
            _pytest_equals(target, repr("ADMIN@EXAMPLE.COM"), repr("admin@example.com")),
        )
        add(
            "regression_guard",
            0,
            "trim surrounding whitespace on an already-lowercase address",
            _pytest_equals(target, repr("  person@example.com  "), repr("person@example.com")),
        )

    if "collapse any run of whitespace into a single hyphen" in lowered:
        add(
            "regression_guard",
            0,
            "collapse tab whitespace to one hyphen",
            _pytest_equals(target, repr("Hello\tWorld"), repr("hello-world")),
        )
        add(
            "regression_guard",
            0,
            "collapse mixed runs of whitespace while trimming and lowercasing",
            _pytest_equals(target, repr("  Hello\nBeautiful  World  "), repr("hello-beautiful-world")),
        )

    if "must never return more than" in lowered and "very small non-negative limits" in lowered:
        add(
            "remaining_requirement",
            0,
            "enforce the stated length bound at limit 0",
            _pytest_len_lte(target, "abcdef", 0),
        )
        add(
            "remaining_requirement",
            0,
            "enforce the stated length bound at limit 1",
            _pytest_len_lte(target, "abcdef", 1),
        )

    if "invalid operand types" in lowered and "normal exceptions" in lowered:
        add(
            "regression_guard",
            0,
            "preserve the normal TypeError for an invalid string operand",
            _pytest_raises(target, repr("x") + ", 2", "TypeError"),
        )
        add(
            "regression_guard",
            0,
            "preserve the normal TypeError for a non-numeric divisor",
            _pytest_raises(target, "10, " + repr("x"), "TypeError"),
        )

    return tuple(probes)
