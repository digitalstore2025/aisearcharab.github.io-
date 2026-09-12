from __future__ import annotations

from dataclasses import dataclass, asdict
from statistics import mean
from typing import Iterable


@dataclass(slots=True)
class RunMetric:
    variant: str
    case_id: str
    success: bool
    latency_s: float
    tool_calls: int
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    security_violations: int = 0


@dataclass(slots=True)
class VariantSummary:
    variant: str
    cases: int
    success_rate: float
    avg_latency_s: float
    avg_tool_calls: float
    avg_tokens: float
    avg_cost_usd: float
    security_violations: int

    def to_dict(self) -> dict:
        return asdict(self)


def summarize(metrics: Iterable[RunMetric]) -> list[VariantSummary]:
    groups: dict[str, list[RunMetric]] = {}
    for m in metrics:
        groups.setdefault(m.variant, []).append(m)
    out = []
    for variant, rows in sorted(groups.items()):
        out.append(VariantSummary(
            variant=variant,
            cases=len(rows),
            success_rate=mean(1.0 if r.success else 0.0 for r in rows),
            avg_latency_s=mean(r.latency_s for r in rows),
            avg_tool_calls=mean(r.tool_calls for r in rows),
            avg_tokens=mean(r.input_tokens + r.output_tokens for r in rows),
            avg_cost_usd=mean(r.cost_usd for r in rows),
            security_violations=sum(r.security_violations for r in rows),
        ))
    return out


def recommend(a: VariantSummary, b: VariantSummary, *, max_success_regression: float = 0.0) -> str:
    if b.security_violations > a.security_violations:
        return f"reject:{b.variant}:security_regression"
    if b.success_rate + max_success_regression < a.success_rate:
        return f"reject:{b.variant}:success_regression"
    if b.success_rate > a.success_rate:
        return f"promote:{b.variant}:higher_success"
    if b.avg_cost_usd < a.avg_cost_usd and b.avg_latency_s <= a.avg_latency_s:
        return f"promote:{b.variant}:same_quality_lower_cost_latency"
    return "hold:insufficient_evidence"
