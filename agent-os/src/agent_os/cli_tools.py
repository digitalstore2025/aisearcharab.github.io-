from __future__ import annotations

from pathlib import Path
from typing import Any

from .mcp_gateway import MCPGateway
from .policy import PolicyEngine
from .tool_runtime import PolicyBoundToolRuntime, RegisteredToolExecutor
from .tracing import JsonlTracer


_MAX_REPO_READ_BYTES = 256 * 1024
_SENSITIVE_PARTS = frozenset({".git", ".ssh", "secrets", "credentials"})
_SENSITIVE_SUFFIXES = frozenset({".pem", ".key", ".p12", ".pfx"})


def _is_sensitive_path(path: Path) -> bool:
    lowered = [part.lower() for part in path.parts]
    if any(part in _SENSITIVE_PARTS for part in lowered):
        return True
    name = path.name.lower()
    if name == ".env" or name.startswith(".env."):
        return True
    return path.suffix.lower() in _SENSITIVE_SUFFIXES


def _repo_reader(workspace_root: str | Path):
    root = Path(workspace_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"workspace root is not a directory: {root}")
    if _is_sensitive_path(root):
        raise PermissionError("repo.read refuses a sensitive workspace root")

    def read(arguments: dict[str, Any]) -> str:
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("repo.read requires a non-empty path")
        if "\x00" in raw_path:
            raise ValueError("repo.read path contains a null byte")

        requested = Path(raw_path)
        if requested.is_absolute():
            raise PermissionError("repo.read requires a workspace-relative path")
        candidate = (root / requested).resolve()
        try:
            candidate.relative_to(root)
        except ValueError as exc:
            raise PermissionError("repo.read path escapes the workspace root") from exc
        relative = candidate.relative_to(root)
        if _is_sensitive_path(relative) or _is_sensitive_path(candidate):
            raise PermissionError("repo.read blocks sensitive repository paths")
        if not candidate.is_file():
            raise FileNotFoundError("repo.read target is not a regular file")
        if candidate.stat().st_size > _MAX_REPO_READ_BYTES:
            raise ValueError("repo.read target exceeds the 256 KiB limit")
        return candidate.read_text(encoding="utf-8", errors="replace")

    return read


def build_cli_tool_runtime(
    policy: PolicyEngine,
    *,
    profile_allowed_tools: tuple[str, ...],
    production_mutations: bool,
    tracer: JsonlTracer | None,
    workspace_root: str | Path,
    enable_repo_read: bool,
) -> PolicyBoundToolRuntime:
    """Build the CLI's explicit default-deny tool runtime.

    The CLI ships no mutation handlers. Repository reads are opt-in, root-confined,
    and refuse sensitive workspace roots as well as sensitive target paths.
    """

    executor = RegisteredToolExecutor()
    if enable_repo_read:
        executor.register(
            tool="repo",
            action="repo.read",
            name="repo_read",
            description="Read one non-sensitive UTF-8 text file inside the configured workspace root.",
            parameters={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Workspace-relative file path to read.",
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            strict=True,
            handler=_repo_reader(workspace_root),
        )

    return PolicyBoundToolRuntime(
        MCPGateway(policy),
        executor,
        tracer=tracer,
        profile_allowed_tools=profile_allowed_tools,
        production_mutations=production_mutations,
    )
