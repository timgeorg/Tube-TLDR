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


# Default base URLs per provider
_DEFAULT_BASE_URLS = {
    "openai": "https://api.openai.com/v1",
    "ollama": "https://ollama.com",  # Ollama Cloud; use http://localhost:11434 for local
}


@dataclass(frozen=True)
class LLMSettings:
    """Resolved LLM connection settings.

    `api_key` is resolved from the environment here so callers get a ready-to-use value.
    For `openai` we check API_KEY then OPENAI_API_KEY.
    For `ollama` we check OLLAMA_API_KEY then API_KEY.
    """
    provider: str  # "openai" | "ollama"
    base_url: str
    model: str
    model_heavy: str
    api_key: Optional[str]
    # Ollama thinking/reasoning mode. None = auto (resolves to False for ollama).
    # Reasoning models can burn the num_predict budget on internal reasoning
    # before emitting visible content, yielding empty responses.
    think: Optional[bool] = None

    @property
    def is_configured(self) -> bool:
        # Ollama running locally without an API key is valid (key may be empty).
        if self.provider == "ollama" and "localhost" in self.base_url:
            return True
        return bool(self.api_key)


def get_llm_settings(cfg: dict[str, Any]) -> LLMSettings:
    """Build LLMSettings from config + environment.

    Config keys (all optional, under `llm:`):
      provider (str): "openai" | "ollama"  -> default "openai"
      base_url (str): override endpoint
      model (str): default model
      model_heavy (str): model for heavy tasks (falls back to model)
      think (bool): Ollama thinking mode; absent -> False for ollama, None otherwise
    """
    llm_cfg = (cfg or {}).get("llm") or {}

    provider = str(llm_cfg.get("provider") or "openai").lower()
    if provider not in _DEFAULT_BASE_URLS:
        provider = "openai"

    base_url = (llm_cfg.get("base_url") or "").strip() or _DEFAULT_BASE_URLS[provider]
    model = str(llm_cfg.get("model") or "gpt-4o-mini")
    model_heavy = str(llm_cfg.get("model_heavy") or "").strip() or model

    # Thinking mode: explicit config wins; absent -> False for ollama (thinking
    # models otherwise risk empty responses), None for openai (no such concept).
    think_raw = llm_cfg.get("think")
    if think_raw is None:
        think: Optional[bool] = False if provider == "ollama" else None
    else:
        think = bool(think_raw)

    # Resolve API key from environment based on provider
    if provider == "ollama":
        api_key = os.getenv("OLLAMA_API_KEY") or os.getenv("API_KEY")
    else:
        api_key = os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")

    return LLMSettings(
        provider=provider,
        base_url=base_url,
        model=model,
        model_heavy=model_heavy,
        api_key=api_key,
        think=think,
    )


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
