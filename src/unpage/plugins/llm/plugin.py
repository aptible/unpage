import os
from typing import Any

import litellm
import questionary
import rich
from litellm import acompletion

from unpage.config.manager import PluginSettings
from unpage.plugins.base import Plugin
from unpage.utils import Choice, classproperty, select


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
        if (
            self.model.startswith("bedrock/")
            and not os.environ.get("AWS_REGION")
            and not os.environ.get("AWS_DEFAULT_REGION")
        ):
            os.environ["AWS_REGION"] = "us-east-1"

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
        recommended_models = {
            "openai": {
                "title": "OpenAI (recommended)",
                "description": "Models from OpenAI https://platform.openai.com/docs/models",
                "models": {
                    "gpt-4o": {
                        "title": "gpt-4o (recommended)",
                        "description": "Fast, intelligent, flexible GPT model https://platform.openai.com/docs/models/gpt-4o",
                    },
                    "gpt-4o-mini": {
                        "description": "Fast, affordable small model for focused tasks https://platform.openai.com/docs/models/gpt-4o-mini",
                    },
                },
            },
            "anthropic": {
                "title": "Anthropic",
                "description": "Models from Anthropic https://www.anthropic.com/claude",
                "models": {
                    "claude-4-sonnet-20250514": {
                        "title": "claude-4-sonnet-20250514 (recommended)",
                        "description": "High intelligence and balanced performance https://docs.anthropic.com/en/docs/about-claude/models/overview#model-comparison-table",
                    },
                    "claude-4-opus-20250514": {
                        "description": "Highest level of intelligence and capability https://docs.anthropic.com/en/docs/about-claude/models/overview#model-comparison-table",
                    },
                },
            },
            "bedrock": {
                "title": "Amazon Bedrock",
                "description": "Models from the Amazon Bedrock marketplace https://aws.amazon.com/bedrock/",
                "models": {
                    "us.anthropic.claude-sonnet-4-20250514-v1:0": {
                        "title": "us.anthropic.claude-sonnet-4-20250514-v1:0 (recommended)",
                        "description": "High intelligence and balanced performance, billed and run through your AWS account",
                    },
                    "us.anthropic.claude-opus-4-20250514-v1:0": {
                        "description": "Highest level of intelligence and capability, billed and run through your AWS account",
                    },
                    "eu.anthropic.claude-sonnet-4-20250514-v1:0": {
                        "description": "High intelligence and balanced performance, billed and run through your AWS account",
                    },
                    "eu.anthropic.claude-opus-4-20250514-v1:0": {
                        "description": "Highest level of intelligence and capability, billed and run through your AWS account",
                    },
                },
            },
        }
        rich.print("Unpage uses LiteLLM and supports all models that LiteLLM supports.")
        rich.print(
            "To configure a model not referenced in this quickstart, you can directly edit Unpage's config.yaml."
        )
        rich.print("More information here: https://docs.aptible.ai/plugins/llm")
        rich.print("")
        provider = await select(
            "Which LLM provider would you like to use?",
            choices=[
                Choice(
                    title=d.get("title", provider),
                    value=provider,
                    description=d["description"],
                )
                for provider, d in recommended_models.items()
            ],
        )
        model = await select(
            f"Which {provider} LLM model would you like to use?",
            choices=[
                Choice(
                    title=d.get("title", model),
                    value=model,
                    description=d["description"],
                )
                for model, d in recommended_models[provider]["models"].items()
            ],
        )
        max_tokens_for_model = litellm.model_cost[model]["max_tokens"]
        return {
            "model": f"{provider}/{model}",
            "api_key": await questionary.password(
                "API key",
                default=self.api_key or defaults["api_key"],
            ).unsafe_ask_async(),
            "temperature": defaults["temperature"],
            "max_tokens": max_tokens_for_model,
            "cache": defaults["cache"],
        }

    async def validate_plugin_config(self) -> None:
        params = {
            "model": self.model,
            "api_key": self.api_key,
            **({"temperature": self.temperature} if not self.model.startswith("bedrock/") else {}),
            "max_tokens": self.max_tokens,
            "cache": self.cache,
        }
        await acompletion(
            **params,
            messages=[
                {
                    "role": "user",
                    "content": "hiiiii",
                }
            ],
        )
