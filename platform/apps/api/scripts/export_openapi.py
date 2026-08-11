from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT / "src"))

from aisearcharab_api.config import Settings
from aisearcharab_api.main import create_app

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_OUTPUT = ROOT / "contracts" / "openapi.generated.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate the canonical OpenAPI document from the application factory.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings = Settings(
        environment="test",
        database_url="sqlite+pysqlite:///:memory:",
        allowed_origins=("http://localhost:3000",),
        api_prefix="/v1",
        max_search_limit=20,
        log_queries=False,
    )
    schema = create_app(settings).openapi()
    output = args.output.resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
