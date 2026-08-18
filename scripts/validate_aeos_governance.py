from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = {
    "engineering/aeos/README.md": ["Definition of Done", "Evidence"],
    "engineering/aeos/CONSTITUTION.md": ["Evidence over assertion", "No fake green", "Human control"],
    "engineering/aeos/SYSTEM_POLICY.md": ["Stop conditions", "Verification mapping", "Completion language"],
    "engineering/aeos/MEMORY_POLICY.md": ["Durable memory", "must not contain"],
    "engineering/aeos/MODEL_ROUTING.md": ["high", "balanced", "fast"],
    "engineering/aeos/TOOL_POLICY.md": ["Least privilege", "Prompt-injection resistance"],
    "engineering/aeos/THREAT_MODEL.md": ["Prompt/content injection", "Source poisoning", "Sensitive-investigation leakage"],
    "engineering/aeos/PROJECT_SPEC.md": ["Problem", "Non-goals", "acceptance criteria"],
    "docs/ADR-002-AEOS-EVIDENCE-GATED-ENGINEERING.md": ["Status: Accepted", "Decision"],
}

PROJECT_ANCHORS = [
    "AGENTS.md",
    "SECURITY.md",
    "docs/EXECUTIVE_BLUEPRINT.md",
    ".github/workflows/ci.yml",
]

CI_REQUIRED_MARKERS = [
    "scan_sensitive_data.py",
    "scan_git_history.py",
    "unittest",
    "validate_data.py",
    "hugo --minify",
]


def fail(message: str, failures: list[str]) -> None:
    failures.append(message)


def validate_files(failures: list[str]) -> None:
    for rel, phrases in REQUIRED_FILES.items():
        path = ROOT / rel
        if not path.is_file():
            fail(f"missing required file: {rel}", failures)
            continue
        text = path.read_text(encoding="utf-8")
        for phrase in phrases:
            if phrase.casefold() not in text.casefold():
                fail(f"{rel} missing required concept: {phrase}", failures)

    for rel in PROJECT_ANCHORS:
        if not (ROOT / rel).is_file():
            fail(f"missing authoritative project anchor: {rel}", failures)


def validate_ci(failures: list[str]) -> None:
    path = ROOT / ".github/workflows/ci.yml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    for marker in CI_REQUIRED_MARKERS:
        if marker not in text:
            fail(f"existing CI no longer contains required evidence gate: {marker}", failures)


def validate_evaluations(failures: list[str]) -> None:
    path = ROOT / "engineering/aeos/evaluation_cases.jsonl"
    if not path.is_file():
        fail("missing evaluation_cases.jsonl", failures)
        return

    seen: set[str] = set()
    valid_expected = {"stop", "escalate", "reject_instruction", "require_human_approval", "do_not_commit"}
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.strip():
            continue
        try:
            item = json.loads(raw)
        except json.JSONDecodeError as exc:
            fail(f"evaluation_cases.jsonl:{lineno}: invalid JSON: {exc}", failures)
            continue
        case_id = item.get("id")
        if not isinstance(case_id, str) or not case_id:
            fail(f"evaluation_cases.jsonl:{lineno}: missing id", failures)
            continue
        if case_id in seen:
            fail(f"evaluation_cases.jsonl:{lineno}: duplicate id {case_id}", failures)
        seen.add(case_id)
        if item.get("expected") not in valid_expected:
            fail(f"evaluation_cases.jsonl:{lineno}: invalid expected outcome", failures)
        if not isinstance(item.get("reason"), str) or not item["reason"].strip():
            fail(f"evaluation_cases.jsonl:{lineno}: missing reason", failures)

    if len(seen) < 5:
        fail("evaluation suite must contain at least five adversarial cases", failures)


def main() -> int:
    failures: list[str] = []
    validate_files(failures)
    validate_ci(failures)
    validate_evaluations(failures)

    if failures:
        print("AEOS GOVERNANCE VALIDATION FAIL")
        for item in failures:
            print(f"- {item}")
        return 1

    print("AEOS GOVERNANCE VALIDATION PASS")
    print("- policy files: present")
    print("- project anchors: present")
    print("- existing CI evidence gates: preserved")
    print("- adversarial evaluation cases: valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
