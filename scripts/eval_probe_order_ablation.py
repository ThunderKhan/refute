from __future__ import annotations

import argparse
from pathlib import Path

from refute.benchmark.probe_order_ablation import evaluate_probe_order_ablation


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate Iteration 5 without the LLM probe planner. The deterministic contract compiler, "
            "probe budget, execution, and verdict semantics remain unchanged; probes are taken in compiler order."
        )
    )
    parser.add_argument("benchmark_dir", type=Path)
    parser.add_argument("--oracle-root", type=Path, required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--probe-budget", type=int, default=2)
    args = parser.parse_args()

    summary = evaluate_probe_order_ablation(
        args.benchmark_dir,
        oracle_root=args.oracle_root,
        artifacts_root=args.artifacts,
        timeout_seconds=args.timeout,
        probe_budget=args.probe_budget,
        progress=True,
    )

    print("\nmode: Iteration 5 probe-order ablation")
    print("agent probe prioritization: no")
    print(f"cases: {summary['cases']}")
    print(f"probe budget: {summary['probe_budget']}")
    print(f"verdict accuracy: {summary['verdict_accuracy']:.1%}")
    print(f"false acceptance rate: {summary['false_acceptance_rate']:.1%}")
    print(f"challenge counterexamples: {summary['challenge_counterexamples']}")
    print(f"average runtime: {summary['average_runtime_seconds']:.3f}s")
    print(f"aggregate evidence: {summary['artifacts_root']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
