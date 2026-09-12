from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class Check:
    name: str
    required: bool = True
    passed: bool = False
    evidence: str = ""


class DefinitionOfDone:
    def __init__(self, checks: list[Check]):
        self.checks = checks

    @property
    def complete(self) -> bool:
        return all(c.passed for c in self.checks if c.required)

    def missing(self) -> list[str]:
        return [c.name for c in self.checks if c.required and not c.passed]


def code_dod() -> DefinitionOfDone:
    return DefinitionOfDone([
        Check("implementation_exists"),
        Check("targeted_tests_pass"),
        Check("security_checks_pass"),
        Check("no_unexplained_regressions"),
    ])


def research_dod() -> DefinitionOfDone:
    return DefinitionOfDone([
        Check("claims_extracted"),
        Check("primary_sources_checked"),
        Check("contradictions_checked"),
        Check("dates_verified"),
        Check("confidence_assigned"),
    ])
