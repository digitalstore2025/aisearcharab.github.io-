#!/usr/bin/env python3
"""Score the AISearchArab blind product-validation benchmark.

This script intentionally uses only the Python standard library so that the
measurement workflow does not depend on the application runtime.
"""

from __future__ import annotations

import argparse
import csv
import statistics
from collections import Counter
from pathlib import Path

VALID_WINNERS = {"aisearcharab", "chatgpt", "perplexity", "google", "tie", "none"}


def parse_binary(value: str, field: str, row_number: int) -> int:
    value = value.strip()
    if value not in {"0", "1"}:
        raise ValueError(f"row {row_number}: {field} must be 0 or 1")
    return int(value)


def parse_optional_float(value: str, field: str, row_number: int) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric or blank") from exc
    if number < 0:
        raise ValueError(f"row {row_number}: {field} cannot be negative")
    return number


def parse_optional_rating(value: str, field: str, row_number: int) -> int | None:
    value = value.strip()
    if not value:
        return None
    if value not in {"1", "2", "3", "4", "5"}:
        raise ValueError(f"row {row_number}: {field} must be 1-5 or blank")
    return int(value)


def load_rows(path: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    seen_pairs: set[tuple[str, str]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "evaluator_id",
            "task_id",
            "persona",
            "winner",
            "ais_task_success",
            "ais_citation_usefulness",
            "ais_trust",
            "ais_completion_seconds",
            "would_return",
            "reason",
            "notes",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"missing columns: {', '.join(sorted(missing))}")

        for row_number, raw in enumerate(reader, start=2):
            evaluator_id = raw["evaluator_id"].strip()
            task_id = raw["task_id"].strip()
            persona = raw["persona"].strip()
            winner = raw["winner"].strip().lower()

            if not evaluator_id or not task_id or not persona:
                raise ValueError(f"row {row_number}: evaluator_id, task_id and persona are required")
            if winner not in VALID_WINNERS:
                raise ValueError(
                    f"row {row_number}: winner must be one of {', '.join(sorted(VALID_WINNERS))}"
                )

            pair = (evaluator_id, task_id)
            if pair in seen_pairs:
                raise ValueError(f"row {row_number}: duplicate evaluator/task pair {pair}")
            seen_pairs.add(pair)

            rows.append(
                {
                    "evaluator_id": evaluator_id,
                    "task_id": task_id,
                    "persona": persona,
                    "winner": winner,
                    "ais_task_success": parse_binary(raw["ais_task_success"], "ais_task_success", row_number),
                    "ais_citation_usefulness": parse_optional_rating(
                        raw["ais_citation_usefulness"], "ais_citation_usefulness", row_number
                    ),
                    "ais_trust": parse_optional_rating(raw["ais_trust"], "ais_trust", row_number),
                    "ais_completion_seconds": parse_optional_float(
                        raw["ais_completion_seconds"], "ais_completion_seconds", row_number
                    ),
                    "would_return": parse_binary(raw["would_return"], "would_return", row_number),
                    "reason": raw["reason"].strip(),
                    "notes": raw["notes"].strip(),
                }
            )

    if not rows:
        raise ValueError("scorecard contains no evaluated rows")
    return rows


def pct(numerator: int, denominator: int) -> float:
    return 100.0 * numerator / denominator if denominator else 0.0


def mean_optional(rows: list[dict[str, object]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row[key] is not None]
    return statistics.fmean(values) if values else None


def proposed_decision(preference_rate: float, task_success_rate: float) -> str:
    if preference_rate >= 60.0 and task_success_rate >= 80.0:
        return "PROCEED"
    if preference_rate < 40.0 or task_success_rate < 60.0:
        return "PIVOT_REVIEW"
    return "MODIFY_OR_NARROW"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scorecard",
        nargs="?",
        type=Path,
        default=Path("test_benchmarks/validation/blind_comparison_scorecard.csv"),
    )
    args = parser.parse_args()

    try:
        rows = load_rows(args.scorecard)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    total = len(rows)
    winners = Counter(str(row["winner"]) for row in rows)
    ais_wins = winners["aisearcharab"]
    task_successes = sum(int(row["ais_task_success"]) for row in rows)
    return_yes = sum(int(row["would_return"]) for row in rows)

    preference_rate = pct(ais_wins, total)
    task_success_rate = pct(task_successes, total)
    return_rate = pct(return_yes, total)

    evaluators = len({str(row["evaluator_id"]) for row in rows})
    tasks = len({str(row["task_id"]) for row in rows})

    print("AISearchArab Product Validation Score")
    print("====================================")
    print(f"evaluated comparisons : {total}")
    print(f"unique evaluators     : {evaluators}")
    print(f"unique tasks          : {tasks}")
    print(f"AIS preference        : {preference_rate:.1f}% ({ais_wins}/{total})")
    print(f"AIS task success      : {task_success_rate:.1f}% ({task_successes}/{total})")
    print(f"would return          : {return_rate:.1f}% ({return_yes}/{total})")

    citation_mean = mean_optional(rows, "ais_citation_usefulness")
    trust_mean = mean_optional(rows, "ais_trust")
    completion_mean = mean_optional(rows, "ais_completion_seconds")

    print(f"citation usefulness   : {citation_mean:.2f}/5" if citation_mean is not None else "citation usefulness   : n/a")
    print(f"trust                 : {trust_mean:.2f}/5" if trust_mean is not None else "trust                 : n/a")
    print(f"mean completion time  : {completion_mean:.1f}s" if completion_mean is not None else "mean completion time  : n/a")

    print("\nWinner distribution")
    for winner in sorted(VALID_WINNERS):
        print(f"  {winner:12} {winners[winner]:4}  {pct(winners[winner], total):5.1f}%")

    print("\nProposed gate decision")
    print(f"  {proposed_decision(preference_rate, task_success_rate)}")
    print("\nNote: this is an operating threshold, not proof of product-market fit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
