from __future__ import annotations

import re
from dataclasses import dataclass


_PATTERNS = [
    ("override", re.compile(r"\b(ignore|disregard|override)\b.{0,40}\b(system|developer|previous|instructions?)\b", re.I | re.S)),
    ("secrets", re.compile(r"\b(reveal|print|send|exfiltrate|show)\b.{0,60}\b(secret|password|api[_ -]?key|token|credential)\b", re.I | re.S)),
    ("privilege", re.compile(r"\b(disable|bypass|remove)\b.{0,40}\b(safety|guardrail|approval|policy|permission)\b", re.I | re.S)),
    ("tool_escalation", re.compile(r"\b(use|call|invoke)\b.{0,30}\b(tool|shell|terminal|browser)\b.{0,60}\b(unrelated|without approval|secret|credential)\b", re.I | re.S)),
    ("override_ar", re.compile(r"(تجاهل|تجاوز|اهمل|أهمل|تخط(?:ى|ي)).{0,50}(تعليمات|توجيهات|سياسة).{0,30}(النظام|المطور|السابقة|الأمان|الامان)", re.S)),
    ("secrets_ar", re.compile(r"(اعرض|اكشف|اطبع|ارسل|أرسل|سر[ّ]?ب).{0,70}(كلمة\s*(?:المرور|السر)|مفتاح\s*(?:API|واجهة)|رمز\s*وصول|توكن|بيانات\s*اعتماد|سر)", re.I | re.S)),
    ("privilege_ar", re.compile(r"(عطل|عط[ّ]?ل|تجاوز|ازل|أزل).{0,50}(الحماية|الأمان|الامان|السياسة|الموافقة|الصلاحيات|القيود)", re.S)),
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
