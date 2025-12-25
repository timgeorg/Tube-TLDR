from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import sys
from typing import Any, Optional

import yaml


def _default_config_path() -> Optional[Path]:
    # 1) explicit
    env_path = os.getenv("CONFIG_PATH")
    if env_path:
        return Path(env_path)

    # 2) current working directory (docker, scripts)
    cwd_candidate = Path.cwd() / "config.yml"
    if cwd_candidate.exists():
        return cwd_candidate

    # 3) alongside executable (PyInstaller)
    if getattr(sys, "frozen", False):
        exe_candidate = Path(sys.executable).resolve().parent / "config.yml"
        if exe_candidate.exists():
            return exe_candidate

    # 4) repo root (dev)
    repo_candidate = Path(__file__).resolve().parents[1] / "config.yml"
    if repo_candidate.exists():
        return repo_candidate

    return None


def load_config(path: Optional[str | os.PathLike[str]] = None) -> dict[str, Any]:
    cfg_path = Path(path) if path else _default_config_path()
    if not cfg_path or not cfg_path.exists():
        return {}
    data = yaml.safe_load(cfg_path.read_text(encoding="utf-8"))
    return data or {}


@dataclass(frozen=True)
class ProxySettings:
    enabled: bool
    proxies: Optional[dict[str, str]]


def get_proxy_settings(cfg: dict[str, Any]) -> ProxySettings:
    """Compute proxy settings.

    Strategy (kept intentionally simple):
    - Source of truth is config.yml
    """
    proxy_cfg = (cfg or {}).get("proxy") or {}

    enabled_cfg = bool(proxy_cfg.get("enabled", False))
    http = proxy_cfg.get("http")
    https = proxy_cfg.get("https")

    if not enabled_cfg:
        return ProxySettings(enabled=False, proxies=None)

    proxies: dict[str, str] = {}
    if http:
        proxies["http"] = str(http)
    if https:
        proxies["https"] = str(https)

    # If enabled but not configured, return None and let callers decide how to behave.
    return ProxySettings(enabled=True, proxies=proxies or None)
