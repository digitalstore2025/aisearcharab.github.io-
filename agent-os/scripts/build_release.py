from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)


def source_files() -> list[Path]:
    files: list[Path] = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or DIST in p.parents or "__pycache__" in p.parts:
            continue
        files.append(p)
    return files


def build_release() -> Path:
    manifest = []
    files = source_files()
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        manifest.append({"path": rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size})

    manifest_text = json.dumps(manifest, indent=2)
    (DIST / "MANIFEST.json").write_text(manifest_text, encoding="utf-8")

    with tempfile.TemporaryDirectory(prefix="astra-agent-os-") as td:
        staging = Path(td) / "bundle"
        for p in files:
            rel = p.relative_to(ROOT)
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(p, target)
        (staging / "MANIFEST.json").write_text(manifest_text, encoding="utf-8")
        archive_tmp = Path(shutil.make_archive(str(Path(td) / "astra_agent_os_v2"), "zip", root_dir=staging))
        final = DIST / "astra_agent_os_v2.zip"
        shutil.copy2(archive_tmp, final)

    return final


if __name__ == "__main__":
    archive = build_release()
    print(archive)
    print(f"files={len(source_files())}")
