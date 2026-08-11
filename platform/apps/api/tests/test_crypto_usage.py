from __future__ import annotations

import ast
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"
ALLOWED_MODULE = "cryptography.fernet"
ALLOWED_FILE = SRC_ROOT / "aisearcharab_api" / "mfa.py"
ALLOWED_NAMES = {"Fernet", "InvalidToken"}


def test_cryptography_usage_is_fernet_only() -> None:
    findings: list[str] = []
    for path in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "cryptography" or alias.name.startswith("cryptography."):
                        findings.append(f"{path.relative_to(SRC_ROOT)}: direct import {alias.name} is not allowed")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module == "cryptography" or module.startswith("cryptography."):
                    imported = {alias.name for alias in node.names}
                    if path != ALLOWED_FILE or module != ALLOWED_MODULE or not imported.issubset(ALLOWED_NAMES):
                        findings.append(
                            f"{path.relative_to(SRC_ROOT)}: from {module} import {','.join(sorted(imported))} is outside the approved Fernet boundary"
                        )
    assert not findings, "\n".join(findings)
