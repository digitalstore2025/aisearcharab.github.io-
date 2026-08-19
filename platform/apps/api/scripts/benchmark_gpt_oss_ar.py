from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from aisearcharab_api.evals.gpt_oss_ar import (  # noqa: E402
    DEFAULT_GATES,
    aggregate_scores,
    build_grounded_prompt,
    gate_failures,
    load_cases,
    score_answer,
)
from aisearcharab_api.geo.providers.gpt_oss import (  # noqa: E402
    GPT_OSS_20B,
    GptOssOllamaProvider,
)
from aisearcharab_api.geo.providers.ollama import OllamaProviderError  # noqa: E402

DEFAULT_DATASET = ROOT / "tests" / "fixtures" / "gpt_oss_ar_benchmark.json"


def _load_dataset(path: Path) -> tuple[bytes, dict[str, object]]:
    raw = path.read_bytes()
    payload = json.loads(raw.decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("benchmark dataset root must be a JSON object")
    return raw, payload


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the AISearchArab grounded Arabic benchmark against local gpt-oss via Ollama."
    )
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--model", default=GPT_OSS_20B)
    parser.add_argument("--base-url", default="http://localhost:11434")
    parser.add_argument("--timeout-seconds", type=float, default=120.0)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--include-answers", action="store_true")
    parser.add_argument("--enforce-gates", action="store_true")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate the benchmark schema and golden references without contacting Ollama.",
    )
    args = parser.parse_args()

    raw_dataset, payload = _load_dataset(args.dataset)
    cases = load_cases(payload)
    reference_scores = [score_answer(case, case.reference_answer) for case in cases]
    reference_metrics = aggregate_scores(cases, reference_scores)
    reference_failures = gate_failures(reference_metrics)
    if reference_failures:
        raise ValueError(
            "benchmark golden references do not satisfy their own gates: "
            + "; ".join(reference_failures)
        )

    if args.validate_only:
        print(
            json.dumps(
                {
                    "status": "valid",
                    "schema_version": payload["schema_version"],
                    "cases": len(cases),
                    "dataset_sha256": hashlib.sha256(raw_dataset).hexdigest(),
                    "reference_metrics": reference_metrics,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0

    provider = GptOssOllamaProvider(
        model=args.model,
        base_url=args.base_url,
        timeout_seconds=args.timeout_seconds,
    )

    scores = []
    try:
        for case in cases:
            result = provider.run_query(build_grounded_prompt(case), locale="ar")
            scores.append(
                score_answer(
                    case,
                    result.answer_text,
                    latency_ms=result.latency_ms,
                    raw_sha256=hashlib.sha256(result.raw_payload.encode("utf-8")).hexdigest(),
                    include_answer=args.include_answers,
                )
            )
    except OllamaProviderError as exc:
        print(f"gpt-oss benchmark failed while contacting Ollama: {exc}", file=sys.stderr)
        return 2

    metrics = aggregate_scores(cases, scores)
    failures = gate_failures(metrics)
    report = {
        "schema_version": 1,
        "benchmark": str(payload.get("name", "AISearchArab grounded Arabic gpt-oss benchmark")),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "dataset": {
            "path": str(args.dataset),
            "sha256": hashlib.sha256(raw_dataset).hexdigest(),
            "cases": len(cases),
        },
        "provider": provider.name,
        "model": provider.model,
        "metrics": metrics,
        "gates": {
            key: {"operator": operator, "threshold": threshold}
            for key, (operator, threshold) in DEFAULT_GATES.items()
        },
        "gate_failures": list(failures),
        "passed": not failures,
        "cases": [score.to_dict() for score in scores],
    }

    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(rendered, end="")
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    if args.enforce_gates and failures:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
