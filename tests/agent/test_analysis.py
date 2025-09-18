import os
from unittest.mock import patch

import pytest
from expandvars import UnboundVariable

from unpage.agent.analysis import Agent


def test_agent_config_environment_variable_expansion() -> None:
    """Test environment variable expansion in agent config."""
    with patch.dict(os.environ, {"API_KEY": "secret", "HOST": "localhost", "ENV": "prod"}):
        agent_data = {
            "name": "test",
            "description": "Test agent",
            "prompt": "Analyze",
            "tools": ["*"],
            "config": {
                "plugins": {
                    "service": {
                        "enabled": True,
                        "settings": {
                            "api_key": "$API_KEY",
                            "url": "https://$HOST/api",
                            "service_name": "${ENV}-service",
                            "timeout": "${TIMEOUT:-30}",
                            "retries": 3,
                            "enabled": True,
                        },
                    }
                }
            },
        }

        agent = Agent(**agent_data)
        settings = agent.config.plugins["service"].settings
        assert settings["api_key"] == "secret"
        assert settings["url"] == "https://localhost/api"
        assert settings["service_name"] == "prod-service"
        assert settings["timeout"] == "30"  # default value
        assert settings["retries"] == 3  # non-string preserved
        assert settings["enabled"] is True


def test_agent_config_unset_environment_variable() -> None:
    """Test that unset environment variables raise UnboundVariable exception."""
    agent_data = {
        "name": "test",
        "description": "Test",
        "prompt": "Analyze",
        "tools": ["*"],
        "config": {
            "plugins": {
                "service": {
                    "enabled": True,
                    "settings": {
                        "missing": "$NONEXISTENT_VAR",
                    },
                }
            }
        },
    }

    with pytest.raises(UnboundVariable):
        Agent(**agent_data)
