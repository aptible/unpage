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


def test_config_expand_env_vars_plugin_settings() -> None:
    """Test environment variable expansion in plugin settings."""
    with patch.dict(
        os.environ,
        {
            "AWS_REGION": "us-east-1",
            "AWS_ACCESS_KEY": "AKIA123456789",
            "DEBUG_MODE": "true",
        },
    ):
        config_data: dict = {
            "plugins": {
                "aws": {
                    "enabled": True,
                    "settings": {
                        "region": "$AWS_REGION",
                        "access_key": "$AWS_ACCESS_KEY",
                        "debug": "$DEBUG_MODE",
                        "endpoints": ["https://$AWS_REGION.amazonaws.com"],
                    },
                }
            }
        }
        config = Config(profile="test", file_path=Path("/tmp/test"), **config_data)
        aws_settings = config.plugins["aws"].settings
        assert aws_settings["region"] == "us-east-1"
        assert aws_settings["access_key"] == "AKIA123456789"
        assert aws_settings["debug"] == "true"
        assert aws_settings["endpoints"] == ["https://us-east-1.amazonaws.com"]


def test_config_expand_env_vars_nested_plugin_settings() -> None:
    """Test environment variable expansion in nested plugin settings."""
    with patch.dict(
        os.environ,
        {
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
        },
    ):
        config_data: dict = {
            "plugins": {
                "database": {
                    "enabled": True,
                    "settings": {
                        "host": "$DB_HOST",
                        "port": "$DB_PORT",
                        "nested": {
                            "connection_string": "postgresql://$DB_HOST:$DB_PORT/db",
                        },
                    },
                }
            }
        }
        config = Config(profile="test", file_path=Path("/tmp/test"), **config_data)
        db_settings = config.plugins["database"].settings
        assert db_settings["host"] == "localhost"
        assert db_settings["port"] == "5432"
        assert db_settings["nested"]["connection_string"] == "postgresql://localhost:5432/db"


def test_config_expand_env_vars_with_defaults() -> None:
    """Test environment variable expansion with default values."""
    config_data: dict = {
        "plugins": {
            "service": {
                "enabled": True,
                "settings": {
                    "timeout": "${TIMEOUT:-30}",
                    "retries": "${RETRIES:-3}",
                },
            }
        }
    }
    config = Config(profile="test", file_path=Path("/tmp/test"), **config_data)
    service_settings = config.plugins["service"].settings
    assert service_settings["timeout"] == "30"
    assert service_settings["retries"] == "3"


def test_config_expand_env_vars_nonexistent_var() -> None:
    """Test behavior with nonexistent environment variables."""
    config_data: dict = {
        "plugins": {
            "service": {
                "enabled": True,
                "settings": {
                    "missing_var": "$NONEXISTENT_VAR",
                },
            }
        }
    }
    # expandvars with nounset=True raises UnboundVariable if env var doesn't exist
    with pytest.raises(UnboundVariable):
        Config(profile="test", file_path=Path("/tmp/test"), **config_data)


def test_config_expand_env_vars_mixed_types() -> None:
    """Test that non-string types are preserved during expansion."""
    with patch.dict(
        os.environ,
        {
            "STRING_VAR": "test_value",
        },
    ):
        config_data: dict = {
            "plugins": {
                "service": {
                    "enabled": True,
                    "settings": {
                        "string_field": "$STRING_VAR",
                        "number_field": 42,
                        "boolean_field": True,
                        "float_field": 3.14,
                        "list_field": [1, 2, 3],
                    },
                }
            }
        }
        config = Config(profile="test", file_path=Path("/tmp/test"), **config_data)
        settings = config.plugins["service"].settings
        assert settings["string_field"] == "test_value"
        assert settings["number_field"] == 42
        assert settings["boolean_field"] is True
        assert settings["float_field"] == 3.14
        assert settings["list_field"] == [1, 2, 3]


def test_config_expand_env_vars_in_lists() -> None:
    """Test environment variable expansion in lists within plugin settings."""
    with patch.dict(
        os.environ,
        {
            "SERVER1": "server1.com",
            "SERVER2": "server2.com",
        },
    ):
        config_data: dict = {
            "plugins": {
                "service": {
                    "enabled": True,
                    "settings": {
                        "servers": [
                            "$SERVER1",
                            "$SERVER2",
                            "static.com",
                        ]
                    },
                }
            }
        }
        config = Config(profile="test", file_path=Path("/tmp/test"), **config_data)
        settings = config.plugins["service"].settings
        assert settings["servers"] == ["server1.com", "server2.com", "static.com"]


def test_config_expand_env_vars_complex_interpolation() -> None:
    """Test complex environment variable expansion patterns."""
    with patch.dict(
        os.environ,
        {
            "ENV": "production",
            "SERVICE_NAME": "unpage",
            "VERSION": "1.0.0",
        },
    ):
        config_data: dict = {
            "plugins": {
                "deployment": {
                    "enabled": True,
                    "settings": {
                        "service_name": "${SERVICE_NAME}-${ENV}",
                        "image": "${SERVICE_NAME}:${VERSION}",
                        "environment": "$ENV",
                    },
                }
            }
        }
        config = Config(profile="test", file_path=Path("/tmp/test"), **config_data)
        settings = config.plugins["deployment"].settings
        assert settings["service_name"] == "unpage-production"
        assert settings["image"] == "unpage:1.0.0"
        assert settings["environment"] == "production"
