"""Tests for proxy configuration resolution (src.config_loader.get_proxy_settings).

Pure config logic — no network, no youtube_video import. The function under test
maps the ``proxy:`` block of config.yml to a ``ProxySettings`` dataclass:

    enabled=false          -> ProxySettings(enabled=False, proxies=None)
    enabled=true + urls    -> ProxySettings(enabled=True, proxies={...})
    enabled=true, no urls  -> ProxySettings(enabled=True, proxies=None)

The last case is *not* an error at this layer: ``get_proxy_settings`` is a pure
mapper. The "enabled but unconfigured" failure is raised one layer up in
``src/cli.py`` as ``_ConfigError`` (exit code 1) — see
``tests/test_cli.py::test_proxy_enabled_but_unset_exits_1``.
"""
from __future__ import annotations

import os
import sys

# Let Python locate the source code (matches the other test modules).
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import yaml

from src.config_loader import ProxySettings, get_proxy_settings, load_config


def test_disabled_returns_no_proxies():
    cfg = {
        "proxy": {
            "enabled": False,
            "http": "socks5h://127.0.0.1:9050",
            "https": "socks5h://127.0.0.1:9050",
        }
    }
    settings = get_proxy_settings(cfg)
    assert settings.enabled is False
    assert settings.proxies is None


def test_missing_proxy_block_defaults_to_disabled():
    assert get_proxy_settings({}) == ProxySettings(enabled=False, proxies=None)
    assert get_proxy_settings({"llm": {"provider": "ollama"}}) == ProxySettings(
        enabled=False, proxies=None
    )


def test_enabled_with_http_and_https_returns_dict():
    cfg = {
        "proxy": {
            "enabled": True,
            "http": "socks5h://user:pass@host:1080",
            "https": "socks5h://user:pass@host:1080",
        }
    }
    settings = get_proxy_settings(cfg)
    assert settings.enabled is True
    assert settings.proxies == {
        "http": "socks5h://user:pass@host:1080",
        "https": "socks5h://user:pass@host:1080",
    }


def test_enabled_with_only_http_returns_partial_dict():
    settings = get_proxy_settings(
        {"proxy": {"enabled": True, "http": "http://127.0.0.1:8080"}}
    )
    assert settings.enabled is True
    assert settings.proxies == {"http": "http://127.0.0.1:8080"}


def test_enabled_without_urls_returns_none_proxies():
    # Not an error here — src/cli.py turns this into exit code 1.
    settings = get_proxy_settings({"proxy": {"enabled": True}})
    assert settings.enabled is True
    assert settings.proxies is None


def test_enabled_with_blank_urls_returns_none_proxies():
    settings = get_proxy_settings(
        {"proxy": {"enabled": True, "http": "", "https": None}}
    )
    assert settings.enabled is True
    assert settings.proxies is None


def test_values_are_coerced_to_str():
    settings = get_proxy_settings({"proxy": {"enabled": True, "http": 1234}})
    assert settings.enabled is True
    assert settings.proxies == {"http": "1234"}


def test_load_config_roundtrip_from_yaml(tmp_path):
    cfg_path = tmp_path / "config.yml"
    cfg_path.write_text(
        yaml.safe_dump(
            {
                "proxy": {
                    "enabled": True,
                    "http": "socks5h://127.0.0.1:9050",
                    "https": "socks5h://127.0.0.1:9050",
                }
            }
        ),
        encoding="utf-8",
    )
    settings = get_proxy_settings(load_config(cfg_path))
    assert settings.enabled is True
    assert settings.proxies == {
        "http": "socks5h://127.0.0.1:9050",
        "https": "socks5h://127.0.0.1:9050",
    }


def test_load_config_missing_file_returns_empty_dict(tmp_path):
    missing = tmp_path / "does-not-exist.yml"
    assert load_config(missing) == {}
    assert get_proxy_settings(load_config(missing)) == ProxySettings(
        enabled=False, proxies=None
    )