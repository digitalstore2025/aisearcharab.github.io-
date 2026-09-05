#!/usr/bin/env python3
"""Score the AISearchArab blind product-validation benchmark.

Standard-library only. The scorer reports uncertainty and refuses to emit an
operating decision when the pilot has too little independent coverage.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

VALID_WINNERS = {"aisearcharab", "chatgpt", "perplexity", "google", "tie", "none"}
VALID_MODES = {"retrieval_only", "generated_answer"}
VALID_QUERY_SOURCES = {"participant", "seed"}
MIN_COMPARISONS = 30
MIN_EVALUATORS = 10
MIN_TASKS = 10


def parse_binary(value: str, field: str, row_number: int) -> int:
    value = value.strip()
    if value not in {"0", "1"}:
        raise ValueError(f"row {row_number}: {field} must be 0 or 1")
    return int(value)


def parse_optional_float(
    value: str,
    field: str,
    row_number: int,
    *,
    minimum: float = 0.0,
    maximum: float | None = None,
) -> float | None:
    value = value.strip()
    if not value:
        return None
    try:
        number = float(value)
    except ValueError as exc:
        raise ValueError(f"row {row_number}: {field} must be numeric or blank") from exc
    if number < minimum or (maximum is not None and number > maximum):
        limit = f"{minimum}-{maximum}" if maximum is not None else f">={minimum}"
        raise ValueError(f"row {row_number}: {field} must be {limit}")
    return number


def parse_optional_rating(value: str, field: str, row_number: int) -> int | None:
    value = value.strip()
    if not value:
        return None
    if value not in {"1", "2", "3", "4", "5"}:
        raise ValueError(f"row {row_number}: {field} must be 1-5 or blank")
    return int(value)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_keys: set[tuple[str, str, str]] = set()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {
            "evaluator_id",
            "task_id",
            "persona",
            "ais_mode",
            "query_source",
            "winner",
            "ais_task_success",
            "ais_retrieval_success",
            "ais_zero_result",
            "ais_citation_usefulness",
            "ais_citation_accuracy_pct",
            "ais_citation_completeness_pct",
            "ais_groundedness_pct",
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
            mode = raw["ais_mode"].strip().lower()
            query_source = raw["query_source"].strip().lower()
            winner = raw["winner"].strip().lower()

            if not evaluator_id or not task_id or not persona:
                raise ValueError(f"row {row_number}: evaluator_id, task_id and persona are required")
            if mode not in VALID_MODES:
                raise ValueError(f"row {row_number}: ais_mode must be one of {', '.join(sorted(VALID_MODES))}")
            if query_source not in VALID_QUERY_SOURCES:
                raise ValueError(
                    f"row {row_number}: query_source must be one of {', '.join(sorted(VALID_QUERY_SOURCES))}"
                )
            if winner not in VALID_WINNERS:
                raise ValueError(
                    f"row {row_number}: winner must be one of {', '.join(sorted(VALID_WINNERS))}"
                )

            key = (evaluator_id, task_id, mode)
            if key in seen_keys:
                raise ValueError(f"row {row_number}: duplicate evaluator/task/mode key {key}")
            seen_keys.add(key)

            rows.append(
                {
                    "evaluator_id": evaluator_id,
                    "task_id": task_id,
                    "persona": persona,
                    "ais_mode": mode,
                    "query_source": query_source,
                    "winner": winner,
                    "ais_task_success": parse_binary(raw["ais_task_success"], "ais_task_success", row_number),
                    "ais_retrieval_success": parse_binary(
                        raw["ais_retrieval_success"], "ais_retrieval_success", row_number
                    ),
                    "ais_zero_result": parse_binary(raw["ais_zero_result"], "ais_zero_result", row_number),
                    "ais_citation_usefulness": parse_optional_rating(
                        raw["ais_citation_usefulness"], "ais_citation_usefulness", row_number
                    ),
                    "ais_citation_accuracy_pct": parse_optional_float(
                        raw["ais_citation_accuracy_pct"], "ais_citation_accuracy_pct", row_number,
                        minimum=0.0, maximum=100.0
                    ),
                    "ais_citation_completeness_pct": parse_optional_float(
                        raw["ais_citation_completeness_pct"], "ais_citation_completeness_pct", row_number,
                        minimum=0.0, maximum=100.0
                    ),
                    "ais_groundedness_pct": parse_optional_float(
                        raw["ais_groundedness_pct"], "ais_groundedness_pct", row_number,
                        minimum=0.0, maximum=100.0
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


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> tuple[float, float]:
    if total <= 0:
        return 0.0, 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    lower = (centre - margin) / denominator
    upper = (centre + margin) / denominator
    return 100.0 * lower, 100.0 * upper


def mean_optional(rows: list[dict[str, Any]], key: str) -> float | None:
    values = [float(row[key]) for row in rows if row[key] is not None]
    return statistics.fmean(values) if values else None


def measurement_ready(rows: list[dict[str, Any]]) -> bool:
    return (
        len(rows) >= MIN_COMPARISONS
        and len({str(r["evaluator_id"]) for r in rows}) >= MIN_EVALUATORS
        and len({str(r["task_id"]) for r in rows}) >= MIN_TASKS
    )


def proposed_decision(
    preference_rate: float,
    task_success_rate: float,
    *,
    ready: bool,
) -> str:
    if not ready:
        return "INSUFFICIENT_EVIDENCE"
    if preference_rate >= 60.0 and task_success_rate >= 80.0:
        return "PROCEED"
    if preference_rate < 40.0 or task_success_rate < 60.0:
        return "PIVOT_REVIEW"
    return "MODIFY_OR_NARROW"


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    winners = Counter(str(row["winner"]) for row in rows)
    ais_wins = winners["aisearcharab"]
    task_successes = sum(int(row["ais_task_success"]) for row in rows)
    retrieval_successes = sum(int(row["ais_retrieval_success"]) for row in rows)
    zero_results = sum(int(row["ais_zero_result"]) for row in rows)
    return_yes = sum(int(row["would_return"]) for row in rows)

    preference_rate = pct(ais_wins, total)
    task_success_rate = pct(task_successes, total)
    ready = measurement_ready(rows)

    by_mode: dict[str, Any] = {}
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["ais_mode"])].append(row)
    for mode, mode_rows in sorted(grouped.items()):
        n = len(mode_rows)
        successes = sum(int(r["ais_task_success"]) for r in mode_rows)
        wins = sum(1 for r in mode_rows if r["winner"] == "aisearcharab")
        by_mode[mode] = {
            "comparisons": n,
            "preference_rate_pct": pct(wins, n),
            "task_success_rate_pct": pct(successes, n),
            "citation_accuracy_pct": mean_optional(mode_rows, "ais_citation_accuracy_pct"),
            "citation_completeness_pct": mean_optional(mode_rows, "ais_citation_completeness_pct"),
            "groundedness_pct": mean_optional(mode_rows, "ais_groundedness_pct"),
        }

    return {
        "comparisons": total,
        "unique_evaluators": len({str(r["evaluator_id"]) for r in rows}),
        "unique_tasks": len({str(r["task_id"]) for r in rows}),
        "participant_query_rate_pct": pct(sum(r["query_source"] == "participant" for r in rows), total),
        "preference_rate_pct": preference_rate,
        "preference_95ci_pct": wilson_interval(ais_wins, total),
        "task_success_rate_pct": task_success_rate,
        "task_success_95ci_pct": wilson_interval(task_successes, total),
        "retrieval_success_rate_pct": pct(retrieval_successes, total),
        "zero_result_rate_pct": pct(zero_results, total),
        "return_rate_pct": pct(return_yes, total),
        "citation_usefulness_mean_5": mean_optional(rows, "ais_citation_usefulness"),
        "citation_accuracy_mean_pct": mean_optional(rows, "ais_citation_accuracy_pct"),
        "citation_completeness_mean_pct": mean_optional(rows, "ais_citation_completeness_pct"),
        "groundedness_mean_pct": mean_optional(rows, "ais_groundedness_pct"),
        "trust_mean_5": mean_optional(rows, "ais_trust"),
        "completion_seconds_mean": mean_optional(rows, "ais_completion_seconds"),
        "winner_distribution": dict(sorted(winners.items())),
        "by_mode": by_mode,
        "measurement_ready": ready,
        "proposed_decision": proposed_decision(preference_rate, task_success_rate, ready=ready),
    }


def fmt_optional(value: float | None, suffix: str = "") -> str:
    return "n/a" if value is None else f"{value:.2f}{suffix}"


def print_human(summary: dict[str, Any]) -> None:
    p_lo, p_hi = summary["preference_95ci_pct"]
    s_lo, s_hi = summary["task_success_95ci_pct"]
    print("AISearchArab Product Validation Score")
    print("====================================")
    print(f"evaluated comparisons : {summary['comparisons']}")
    print(f"unique evaluators     : {summary['unique_evaluators']}")
    print(f"unique tasks          : {summary['unique_tasks']}")
    print(f"participant queries   : {summary['participant_query_rate_pct']:.1f}%")
    print(f"AIS preference        : {summary['preference_rate_pct']:.1f}% (95% CI {p_lo:.1f}-{p_hi:.1f})")
    print(f"AIS task success      : {summary['task_success_rate_pct']:.1f}% (95% CI {s_lo:.1f}-{s_hi:.1f})")
    print(f"retrieval success     : {summary['retrieval_success_rate_pct']:.1f}%")
    print(f"zero-result rate      : {summary['zero_result_rate_pct']:.1f}%")
    print(f"would return          : {summary['return_rate_pct']:.1f}%")
    print(f"citation usefulness   : {fmt_optional(summary['citation_usefulness_mean_5'], '/5')}")
    print(f"citation accuracy     : {fmt_optional(summary['citation_accuracy_mean_pct'], '%')}")
    print(f"citation completeness : {fmt_optional(summary['citation_completeness_mean_pct'], '%')}")
    print(f"groundedness          : {fmt_optional(summary['groundedness_mean_pct'], '%')}")
    print(f"trust                 : {fmt_optional(summary['trust_mean_5'], '/5')}")
    print(f"mean completion time  : {fmt_optional(summary['completion_seconds_mean'], 's')}")
    print("\nAIS mode slices")
    for mode, values in summary["by_mode"].items():
        print(
            f"  {mode:16} n={values['comparisons']:3} "
            f"preference={values['preference_rate_pct']:5.1f}% "
            f"task_success={values['task_success_rate_pct']:5.1f}%"
        )
    print("\nProposed gate decision")
    print(f"  {summary['proposed_decision']}")
    if not summary["measurement_ready"]:
        print(
            f"  Minimum evidence: {MIN_COMPARISONS} comparisons, "
            f"{MIN_EVALUATORS} evaluators, {MIN_TASKS} tasks."
        )
    print("\nCaveat: repeated tasks per evaluator are clustered observations; the Wilson intervals are descriptive, not a substitute for a clustered study analysis.")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "scorecard",
        nargs="?",
        type=Path,
        default=Path("test_benchmarks/validation/blind_comparison_scorecard.csv"),
    )
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args()

    try:
        rows = load_rows(args.scorecard)
        summary = summarize(rows)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print_human(summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
