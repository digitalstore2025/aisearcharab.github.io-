from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import MutableMapping, Sequence
from urllib.parse import urlsplit, urlunsplit

_RENDER_DATABASE_ENV = "RENDER_DATABASE_URL"
_RUNTIME_DATABASE_ENV = "DATABASE_URL"


def normalize_postgres_url(raw_url: str) -> str:
    """Normalize Render's Postgres URL for SQLAlchemy's reviewed psycopg driver.

    Render exposes managed PostgreSQL as ``postgresql://...``. The application
    intentionally pins psycopg 3 and validates ``postgresql+psycopg://...`` in
    secure runtimes. This adapter changes only the SQLAlchemy dialect scheme;
    credentials, host, port, path and query parameters remain untouched.
    """

    value = raw_url.strip()
    parsed = urlsplit(value)
    if parsed.scheme == "postgresql":
        scheme = "postgresql+psycopg"
    elif parsed.scheme == "postgresql+psycopg":
        scheme = parsed.scheme
    else:
        raise RuntimeError("Render database URL must use PostgreSQL")

    if not parsed.hostname or not parsed.path.lstrip("/"):
        raise RuntimeError("Render database URL is incomplete")

    return urlunsplit((scheme, parsed.netloc, parsed.path, parsed.query, parsed.fragment))


def configure_database_url(env: MutableMapping[str, str] | None = None) -> str:
    """Populate DATABASE_URL without logging or persisting the credential."""

    runtime_env = os.environ if env is None else env
    raw_url = runtime_env.get(_RENDER_DATABASE_ENV) or runtime_env.get(_RUNTIME_DATABASE_ENV)
    if not raw_url:
        raise RuntimeError("RENDER_DATABASE_URL or DATABASE_URL is required")
    normalized = normalize_postgres_url(raw_url)
    runtime_env[_RUNTIME_DATABASE_ENV] = normalized
    return normalized


def _serve_command(env: MutableMapping[str, str]) -> list[str]:
    port = env.get("PORT", "8000").strip()
    if not port.isdigit() or not 1 <= int(port) <= 65535:
        raise RuntimeError("PORT must be an integer between 1 and 65535")
    return [
        "uvicorn",
        "aisearcharab_api.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        port,
    ]


def _migrate() -> None:
    subprocess.run(["alembic", "upgrade", "head"], check=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    modes = {"migrate", "serve", "migrate-and-serve"}
    if len(args) != 1 or args[0] not in modes:
        raise SystemExit(
            "usage: python -m aisearcharab_api.render_runtime "
            "[migrate|serve|migrate-and-serve]"
        )

    configure_database_url()
    if args[0] in {"migrate", "migrate-and-serve"}:
        _migrate()
    if args[0] == "migrate":
        return 0

    os.execvp("uvicorn", _serve_command(os.environ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
