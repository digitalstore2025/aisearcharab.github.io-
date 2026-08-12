from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCAN_ROOTS = ("content", "data", "layouts", "static", "platform")
ROOT_FILES = ("hugo.toml", "README.md", "SECURITY.md")
FORBIDDEN = (("AIsearch" + ".study").lower(), ("aisearch" + "-study").lower())
TEXT_SUFFIXES = {".html", ".md", ".json", ".toml", ".yaml", ".yml", ".js", ".ts", ".tsx", ".css", ".py"}


def iter_targets():
    for name in ROOT_FILES:
        path = ROOT / name
        if path.is_file():
            yield path
    for root_name in SCAN_ROOTS:
        root = ROOT / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in TEXT_SUFFIXES:
                yield path


def main() -> None:
    findings: list[str] = []
    for path in iter_targets():
        try:
            text = path.read_text(encoding="utf-8").lower()
        except UnicodeDecodeError:
            continue
        if any(marker in text for marker in FORBIDDEN):
            findings.append(str(path.relative_to(ROOT)))
    if findings:
        joined = "\n".join(f"- {item}" for item in sorted(set(findings)))
        raise SystemExit(f"Cross-project identity contamination detected:\n{joined}")
    print("Project identity validation passed")


if __name__ == "__main__":
    main()
