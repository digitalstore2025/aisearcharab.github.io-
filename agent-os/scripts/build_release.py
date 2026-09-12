from __future__ import annotations
import hashlib, json, shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)

manifest = []
for p in sorted(ROOT.rglob("*")):
    if not p.is_file() or "/dist/" in p.as_posix() or "__pycache__" in p.parts:
        continue
    rel = p.relative_to(ROOT).as_posix()
    manifest.append({"path": rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size})
(DIST / "MANIFEST.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
archive = shutil.make_archive(str(DIST / "astra_agent_os_v2"), "zip", root_dir=ROOT, base_dir=".")
print(archive)
print(f"files={len(manifest)}")
