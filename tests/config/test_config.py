import os
from pathlib import Path
from unittest.mock import patch

import pytest
from expandvars import UnboundVariable

from unpage.config import Config, PluginConfig, manager


def test_config_merge_plugins() -> None:
    cfg = manager.get_empty_config(profile="test")
    new_cfg = cfg.merge_plugins({"testplugin": PluginConfig(enabled=True, settings={})})
    assert "testplugin" in new_cfg.plugins
    assert new_cfg.plugins["testplugin"].enabled is True
    assert new_cfg.plugins["testplugin"].settings == {}


def test_config_environment_variable_expansion() -> None:
    """Test environment variable expansion in config."""
    with patch.dict(
        os.environ,
        {
            "API_KEY": "secret",
            "HOST": "localhost",
            "ENV": "prod",
        },
    ):
        config_data: dict = {
            "plugins": {
                "service": {
                    "enabled": True,
                    "settings": {
                        "api_key": "$API_KEY",
                        "url": "https://$HOST/api",
                        "service_name": "${ENV}-service",
                        "timeout": "${TIMEOUT:-30}",
                        "connection": {"host": "$HOST", "port": "5432"},
                        "servers": ["$HOST", "backup.com"],
                        "retries": 3,
                        "enabled": True,
                    },
                }
            }
        }

        config = Config(profile="test", file_path=Path("/tmp/test"), **config_data)
        settings = config.plugins["service"].settings
        assert settings["api_key"] == "secret"
        assert settings["url"] == "https://localhost/api"
        assert settings["service_name"] == "prod-service"
        assert settings["timeout"] == "30"  # default value
        assert settings["connection"]["host"] == "localhost"  # nested
        assert settings["servers"] == ["localhost", "backup.com"]  # list
        assert settings["retries"] == 3  # non-string preserved
        assert settings["enabled"] is True


def test_config_unset_environment_variable() -> None:
    """Test that unset environment variables raise UnboundVariable exception."""
    config_data: dict = {
        "plugins": {
            "service": {
                "enabled": True,
                "settings": {
                    "missing": "$NONEXISTENT_VAR",
                },
            }
        }
    }

    with pytest.raises(UnboundVariable):
        Config(profile="test", file_path=Path("/tmp/test"), **config_data)
