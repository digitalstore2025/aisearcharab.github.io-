from __future__ import annotations

import hashlib
import json
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
DIST.mkdir(exist_ok=True)
_FIXED_ZIP_TIMESTAMP = (1980, 1, 1, 0, 0, 0)


def source_files() -> list[Path]:
    files: list[Path] = []
    for p in sorted(ROOT.rglob("*")):
        if not p.is_file() or DIST in p.parents or "__pycache__" in p.parts:
            continue
        files.append(p)
    return files


def _write_entry(archive: ZipFile, name: str, data: bytes) -> None:
    info = ZipInfo(name, date_time=_FIXED_ZIP_TIMESTAMP)
    info.create_system = 3
    info.external_attr = 0o100644 << 16
    info.compress_type = ZIP_DEFLATED
    archive.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)


def build_release() -> Path:
    manifest = []
    files = source_files()
    for p in files:
        rel = p.relative_to(ROOT).as_posix()
        manifest.append({"path": rel, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(), "bytes": p.stat().st_size})

    manifest_text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (DIST / "MANIFEST.json").write_text(manifest_text, encoding="utf-8")

    archive_path = DIST / "astra_agent_os_v2.zip"
    with ZipFile(archive_path, "w", compression=ZIP_DEFLATED, compresslevel=9) as archive:
        for p in files:
            _write_entry(archive, p.relative_to(ROOT).as_posix(), p.read_bytes())
        _write_entry(archive, "MANIFEST.json", manifest_text.encode("utf-8"))
    return archive_path


if __name__ == "__main__":
    archive = build_release()
    print(archive)
    print(f"files={len(source_files())}")
