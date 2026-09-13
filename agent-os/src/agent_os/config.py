from __future__ import annotations

import json
import os
import re
import sysconfig
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_PROFILE_NAME = re.compile(r"^[A-Za-z0-9_-]+$")
_RISK_LEVELS = {"low", "medium", "high", "critical"}


@dataclass(frozen=True, slots=True)
class Profile:
    name: str
    mode: str
    allowed_tools: tuple[str, ...]
    default_risk: str
    default_complexity: str
    preferred_skills: tuple[str, ...] = ()
    production_mutations: bool = False


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def package_root() -> Path:
    return Path(__file__).resolve().parents[2]


def config_root() -> Path:
    override = os.environ.get("ASTRA_AGENT_OS_CONFIG_DIR")
    if override:
        path = Path(override).expanduser().resolve()
        if path.is_dir():
            return path
        raise FileNotFoundError(f"ASTRA_AGENT_OS_CONFIG_DIR does not exist: {path}")

    source = package_root() / "config"
    if source.is_dir():
        return source

    installed = Path(sysconfig.get_path("data")) / "share" / "astra-agent-os" / "config"
    if installed.is_dir():
        return installed
    raise FileNotFoundError("Astra Agent OS configuration resources are unavailable")


def load_profile(name: str, root: str | Path | None = None) -> Profile:
    if not _PROFILE_NAME.fullmatch(name):
        raise ValueError(f"Invalid profile name: {name}")
    cfg_root = Path(root) if root is not None else config_root()
    data = load_json(cfg_root / "profiles" / f"{name}.json")
    if data.get("name") != name:
        raise ValueError("Profile name does not match its filename")
    risk = data.get("default_risk", "medium")
    complexity = data.get("default_complexity", "medium")
    if risk not in _RISK_LEVELS or complexity not in _RISK_LEVELS:
        raise ValueError("Profile contains an unsupported risk/complexity level")
    allowed_tools = data.get("allowed_tools", [])
    preferred_skills = data.get("preferred_skills", [])
    if not isinstance(allowed_tools, list) or not all(isinstance(x, str) and x for x in allowed_tools):
        raise ValueError("Profile allowed_tools must be a list of non-empty strings")
    if not isinstance(preferred_skills, list) or not all(isinstance(x, str) and x for x in preferred_skills):
        raise ValueError("Profile preferred_skills must be a list of non-empty strings")
    return Profile(
        name=name,
        mode=str(data.get("mode", "standard")),
        allowed_tools=tuple(allowed_tools),
        default_risk=risk,
        default_complexity=complexity,
        preferred_skills=tuple(preferred_skills),
        production_mutations=bool(data.get("production_mutations", False)),
    )
