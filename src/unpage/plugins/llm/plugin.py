from typing import Any

import litellm
import questionary
from litellm import acompletion

from unpage.config.utils import PluginSettings
from unpage.plugins.base import Plugin
from unpage.utils import classproperty, select


class LlmPlugin(Plugin):
    """A plugin for configuring LLM models."""

    def __init__(
        self,
        *args: Any,
        model: str,
        api_key: str,
        temperature: float,
        max_tokens: int,
        cache: bool,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.model = model
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.cache = cache

    @classproperty
    def default_plugin_settings(cls) -> PluginSettings:
        return {
            "model": "openai/gpt-4o-mini",
            "api_key": "",
            "temperature": 0,
            "max_tokens": 8192,
            "cache": True,
        }

    async def interactive_configure(self) -> PluginSettings:
        """Interactive wizard for configuring the settings of this plugin."""
        defaults = self.default_plugin_settings
        model_list = [
            model if model.startswith(f"{provider}/") else f"{provider}/{model}"
            for provider, models in litellm.models_by_provider.items()
            for model in models
        ]
        return {
            "model": await select(
                "Model",
                choices=model_list,
                default=self.model or defaults["model"],
                use_jk_keys=False,
                use_search_filter=True,
            ),
            "api_key": await questionary.password(
                "API key",
                default=self.api_key or defaults["api_key"],
            ).unsafe_ask_async(),
            "temperature": self.temperature or defaults["temperature"],
            "max_tokens": self.max_tokens or defaults["max_tokens"],
            "cache": self.cache or defaults["cache"],
        }

    async def validate_plugin_config(self) -> None:
        await acompletion(
            model=self.model,
            api_key=self.api_key,
            temperature=self.temperature,
            max_tokens=self.max_tokens,
            messages=[
                {
                    "role": "user",
                    "content": "hiiiii",
                }
            ],
        )
