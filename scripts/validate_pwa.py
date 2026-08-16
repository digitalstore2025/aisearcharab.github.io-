from __future__ import annotations

import json
import re
import struct
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"


def fail(message: str) -> None:
    raise SystemExit(f"PWA validation failed: {message}")


def png_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        fail(f"{path.relative_to(ROOT)} is not a valid PNG")
    return struct.unpack(">II", data[16:24])


def require_text(path: Path, *needles: str) -> str:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            fail(f"{path.relative_to(ROOT)} missing required marker: {needle}")
    return text


def require_pattern(path: Path, pattern: str, label: str) -> None:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    text = path.read_text(encoding="utf-8")
    if re.search(pattern, text, flags=re.IGNORECASE) is None:
        fail(f"{path.relative_to(ROOT)} missing required {label}")


def require_sw_semantics(path: Path) -> None:
    if not path.is_file():
        fail(f"missing {path.relative_to(ROOT)}")
    source = path.read_text(encoding="utf-8")
    rules = {
        "install listener": r"self\.addEventListener\(\s*['\"]install['\"]",
        "fetch listener": r"self\.addEventListener\(\s*['\"]fetch['\"]",
        "non-GET bypass": r"request\.method\s*!==\s*['\"]GET['\"]",
        "cross-origin bypass": r"url\.origin\s*!==\s*self\.location\.origin",
        "scope-aware URL derivation": r"new URL\(\s*path\.replace",
        "private/no-store guard": r"no-store\|private",
        "bounded runtime cache": r"MAX_RUNTIME_ENTRIES\s*=\s*\d+",
        "cross-cache lookup": r"caches\.match\(\s*request\s*\)",
        "sensitive route guard": r"isSensitivePath\(\s*path\s*\)",
    }
    for label, pattern in rules.items():
        if re.search(pattern, source, flags=re.IGNORECASE) is None:
            fail(f"{path.relative_to(ROOT)} missing required semantic: {label}")

    for prefix in ("/api/", "/v1/", "/admin", "/health/"):
        if prefix not in source:
            fail(f"{path.relative_to(ROOT)} must bypass sensitive prefix {prefix}")
    for exact in ("/docs", "/openapi.json", "/index.json"):
        if exact not in source:
            fail(f"{path.relative_to(ROOT)} must bypass sensitive path {exact}")


def main() -> None:
    manifest_path = PUBLIC / "site.webmanifest"
    if not manifest_path.is_file():
        fail("missing generated site.webmanifest")

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        fail(f"invalid manifest JSON: {exc}")

    required = {
        "id",
        "name",
        "short_name",
        "start_url",
        "scope",
        "display",
        "background_color",
        "theme_color",
        "icons",
    }
    missing = sorted(required - manifest.keys())
    if missing:
        fail(f"manifest missing fields: {', '.join(missing)}")

    if manifest["id"] != "." or manifest["scope"] != "./":
        fail("manifest id/scope must remain base-path portable")
    if not isinstance(manifest["start_url"], str) or not manifest["start_url"].startswith("./"):
        fail("manifest start_url must be relative to the deployed base path")
    if manifest["display"] not in {"standalone", "fullscreen", "minimal-ui"}:
        fail("manifest display must be installable")

    icon_specs = {
        "icons/icon-192.png": (192, 192),
        "icons/icon-512.png": (512, 512),
    }
    declared = {icon.get("src"): icon for icon in manifest.get("icons", [])}
    for src, expected in icon_specs.items():
        if src not in declared:
            fail(f"manifest does not declare {src}")
        icon_path = PUBLIC / src
        if not icon_path.is_file():
            fail(f"missing generated icon {src}")
        actual = png_size(icon_path)
        if actual != expected:
            fail(f"{src} dimensions are {actual}, expected {expected}")

    require_sw_semantics(PUBLIC / "sw.js")
    registration = PUBLIC / "js" / "pwa-register.js"
    require_text(
        registration,
        'new URL("../", scriptUrl)',
        'new URL("sw.js", scopeUrl)',
        "scope: scopeUrl.pathname",
    )
    require_text(PUBLIC / "offline.html", "noindex,nofollow")

    index = PUBLIC / "index.html"
    require_pattern(index, r"rel=(?:\"manifest\"|'manifest'|manifest)(?:\s|>)", "manifest link")
    require_pattern(index, r"rel=(?:\"apple-touch-icon\"|'apple-touch-icon'|apple-touch-icon)(?:\s|>)", "Apple touch icon")
    require_pattern(index, r"(?:src=)?(?:\"|')?/?js/pwa-register\.js", "PWA registration script")

    print("PWA validation passed")


if __name__ == "__main__":
    main()
