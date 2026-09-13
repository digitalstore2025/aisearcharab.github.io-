from __future__ import annotations

import os
import stat
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


def _secure_open_dir(path: Path) -> int:
    """Open an absolute directory path component-by-component without symlinks."""
    if not path.is_absolute():
        raise ValueError("secure directory open requires an absolute path")
    if not hasattr(os, "O_NOFOLLOW") or os.open not in os.supports_dir_fd:
        raise RuntimeError("secure repo.read is unavailable on this platform")

    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    current_fd = os.open(path.anchor or os.sep, dir_flags)
    try:
        for component in path.parts[1:]:
            next_fd = os.open(component, dir_flags, dir_fd=current_fd)
            os.close(current_fd)
            current_fd = next_fd
        return current_fd
    except Exception:
        os.close(current_fd)
        raise


def _secure_read_relative(root: Path, requested: Path) -> str:
    """Read a regular file through directory FDs, rejecting symlinks and TOCTOU escapes."""
    if requested.is_absolute() or not requested.parts:
        raise PermissionError("repo.read requires a workspace-relative path")
    if any(part in {"", ".", ".."} for part in requested.parts):
        raise PermissionError("repo.read path traversal is prohibited")
    if _is_sensitive_path(requested):
        raise PermissionError("repo.read blocks sensitive repository paths")

    dir_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    file_flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0) | getattr(os, "O_NONBLOCK", 0)
    root_fd = _secure_open_dir(root)
    current_fd = root_fd
    file_fd: int | None = None
    try:
        for component in requested.parts[:-1]:
            next_fd = os.open(component, dir_flags, dir_fd=current_fd)
            if current_fd != root_fd:
                os.close(current_fd)
            current_fd = next_fd

        file_fd = os.open(requested.parts[-1], file_flags, dir_fd=current_fd)
        metadata = os.fstat(file_fd)
        if not stat.S_ISREG(metadata.st_mode):
            raise FileNotFoundError("repo.read target is not a regular file")
        if metadata.st_size > _MAX_REPO_READ_BYTES:
            raise ValueError("repo.read target exceeds the 256 KiB limit")

        chunks: list[bytes] = []
        remaining = _MAX_REPO_READ_BYTES + 1
        while remaining > 0:
            chunk = os.read(file_fd, min(64 * 1024, remaining))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        data = b"".join(chunks)
        if len(data) > _MAX_REPO_READ_BYTES:
            raise ValueError("repo.read target exceeds the 256 KiB limit")
        return data.decode("utf-8", errors="replace")
    finally:
        if file_fd is not None:
            os.close(file_fd)
        if current_fd != root_fd:
            os.close(current_fd)
        os.close(root_fd)


def _repo_reader(workspace_root: str | Path):
    root = Path(workspace_root).expanduser().resolve()
    if not root.is_dir():
        raise ValueError(f"workspace root is not a directory: {root}")
    if _is_sensitive_path(root):
        raise PermissionError("repo.read refuses a sensitive workspace root")

    # Validate the resolved root can itself be opened without following a symlink
    # through any component. Each read reopens it the same way to avoid stale path checks.
    root_fd = _secure_open_dir(root)
    os.close(root_fd)

    def read(arguments: dict[str, Any]) -> str:
        raw_path = arguments.get("path")
        if not isinstance(raw_path, str) or not raw_path.strip():
            raise ValueError("repo.read requires a non-empty path")
        if "\x00" in raw_path:
            raise ValueError("repo.read path contains a null byte")
        return _secure_read_relative(root, Path(raw_path))

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
    symlink-safe on supported platforms, and refuse sensitive roots/targets.
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
                        "minLength": 1,
                    }
                },
                "required": ["path"],
                "additionalProperties": False,
            },
            strict=True,
            production_read=True,
            handler=_repo_reader(workspace_root),
        )

    return PolicyBoundToolRuntime(
        MCPGateway(policy),
        executor,
        tracer=tracer,
        profile_allowed_tools=profile_allowed_tools,
        production_mutations=production_mutations,
    )
