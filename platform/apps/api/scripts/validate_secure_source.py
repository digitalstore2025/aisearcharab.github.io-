from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNTIME_PATHS = [
    ROOT / "platform" / "apps" / "api" / "src",
    ROOT / "static" / "js",
]

FORBIDDEN_TEXT = {
    ".innerHTML": "DOM HTML injection sink",
    ".outerHTML": "DOM HTML injection sink",
    "insertAdjacentHTML": "DOM HTML injection sink",
    "document.write": "DOM document injection sink",
    "eval(": "dynamic code execution",
    "new Function(": "dynamic code execution",
    "localStorage": "persistent browser token/state storage",
    "sessionStorage": "browser session storage in privileged UI",
    "@ts-ignore": "type-system bypass",
}


def iter_runtime_files():
    for base in RUNTIME_PATHS:
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix in {".py", ".js", ".html"}:
                yield path


def main() -> int:
    failures: list[str] = []
    for path in iter_runtime_files():
        text = path.read_text(encoding="utf-8")
        relative = path.relative_to(ROOT)
        for needle, reason in FORBIDDEN_TEXT.items():
            if needle in text:
                failures.append(f"{relative}: forbidden {reason}: {needle}")

    if failures:
        print("Secure source validation failed:")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("Secure source validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
