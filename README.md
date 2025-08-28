# Unpage
<img width="830" height="180" alt="unpage-banner" src="https://github.com/user-attachments/assets/2f0d2ee7-cbef-4bbb-9189-8a992b512c81" />

> [!WARNING]
> **ALPHA SOFTWARE**
> Unpage is experimental, under heavy development, and may be unstable. Use at your own risk!

Unpage is an infrastructure knowledge graph builder, and an MCP server to enable your LLM-powered application to understand and query your infrastructure.


## Installation

### Prerequisites

- Python 3.12 or higher
- `uv` package manager
- API keys for your LLM and alerting, infrastructure, and observability tools. Learn more in [Plugins](https://docs.unpage.ai/concepts/plugins).

### Install uv

On macOS:
```shell
brew install uv
```

For other platforms, follow the [official uv installation guide](https://github.com/astral-sh/uv).

### Install Unpage

Unpage is designed to be run using `uvx`, which comes with `uv`:

```shell
uvx unpage -h
```

## Quickstart

To get started, run:

```shell
uvx unpage agent quickstart
```

This will get you up and running with your first agent, which will automatically investigate and add context to alerts from [PagerDuty](https://docs.unpage.ai/plugins/pagerduty) (or your preferred alerting provider). You will also have a chance to set up your infrastructure knowledge graph to provide your agent with more context.

The quickstart flow will walk you through:

- Configuring your LLM, [PagerDuty plugin](https://docs.unpage.ai/plugins/pagerduty), and logs and metrics plugins
- Creating your first [agent](https://docs.unpage.ai/concepts/agents) and prompt
- Testing your agent with an existing incident ticket
- Building your [knowledge graph](https://docs.unpage.ai/concepts/knowledge-graph)

### Running the Agent

Once you're happy with the results of your agent, you can automate the agent's actions for new incidents by running `unpage agent serve` and configuring [PagerDuty to send webhooks](https://docs.unpage.ai/plugins/pagerduty#webhooks) to the Unpage server:

```shell
uvx unpage agent serve -h
```

The `agent serve` command supports running the server over an ngrok tunnel, so that you can test your agents end-to-end locally, without deploying. For more information on `agent serve` options, see [its documentation](https://docs.unpage.ai/commands/agent#subcommand%3A-serve).

## Documentation

Detailed documentation lives in [docs/](docs/), and is also published via Mintlify to [docs.unpage.ai](https://docs.unpage.ai).

## License

See [LICENSE.md](./LICENSE.md).

## Copyright

Copyright (c) 2025 Aptible. All rights reserved.
