from __future__ import annotations

import re
from dataclasses import dataclass


_PATTERNS = [
    ("override", re.compile(r"\b(ignore|disregard|override)\b.{0,40}\b(system|developer|previous|instructions?)\b", re.I | re.S)),
    ("secrets", re.compile(r"\b(reveal|print|send|exfiltrate|show)\b.{0,60}\b(secret|password|api[_ -]?key|token|credential)\b", re.I | re.S)),
    ("privilege", re.compile(r"\b(disable|bypass|remove)\b.{0,40}\b(safety|guardrail|approval|policy|permission)\b", re.I | re.S)),
    ("tool_escalation", re.compile(r"\b(use|call|invoke)\b.{0,30}\b(tool|shell|terminal|browser)\b.{0,60}\b(unrelated|without approval|secret|credential)\b", re.I | re.S)),
]


@dataclass(slots=True)
class InjectionAssessment:
    suspicious: bool
    signals: list[str]


def assess_untrusted_text(text: str) -> InjectionAssessment:
    signals = [name for name, pattern in _PATTERNS if pattern.search(text)]
    return InjectionAssessment(bool(signals), signals)


def isolate_untrusted(text: str) -> str:
    """Wrap retrieved content so downstream prompts cannot confuse it with policy."""
    return f"<UNTRUSTED_DATA>\n{text}\n</UNTRUSTED_DATA>"
