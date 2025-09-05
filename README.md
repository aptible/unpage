<img width="830" height="180" alt="unpage-banner" src="https://github.com/user-attachments/assets/2f0d2ee7-cbef-4bbb-9189-8a992b512c81" />

## Unpage: Build SRE agents that understand _your_ infrastructure
Modern infrastructure is complex. For agents to be effective, they need **context** and **secure access** to your dev tools.

With Unpage, you can build production-ready SRE agents in minutes:
- **Define agents in YAML:** Configure how they respond to events.
- **Route intelligently:** Match alerts and requests to the right agent.
- **Give agents context:** Map your infrastructure with plugins and a knowledge graph.
- **Integrate securely:** Connect agents to logs, metrics, traces, infra providers, and external tools via MCP or shell access.

> [!NOTE]
> Unpage is **young but production-ready** and evolving quickly with community feedback.

## Unpage Agents

Unpage agents are defined in natural language in YAML files. This is an example agent that investigates SSL/TLS connection failures and provides a summary on the incident:

```yaml expandable
# SSL-connection-failure-agent.yaml

# Description: Used by the router to determine which agent to use for the alert
description: Investigate SSL/TLS connection failures

# Prompt: Instructions for the agent to follow when acting on the alert
prompt: >
  - Extract the domain/hostname from the alert about connection failures.
  - Use shell command `shell_check_cert_expiration_date` to check the certificate expiration dates
  - Parse the certificate dates to determine if the cert is expired or expiring soon
  - If certificate is expired or expiring within 24 hours:
    - Post high-priority status update to the incident explaining the root cause
    - Include the exact expiration date and affected resources

# Tools: Allows the agent to use the specified tools during its investigation
tools: >
  - "shell_check_cert_expiration_date"
  - "pagerduty_post_status_update"
```

**Description**: When Unpage is running and receives an incident payload from your alerting tool, the router uses the agent description to determine which agent should act on the incident.

Learn more about Unpage's router [here](/concepts/router).

**Prompt:** The selected agent will follow the investigation steps listed in the prompt. This will often resemble a runbook for the type of alert.

**Tools**: In order to do its investigation, the agent uses tools to understand your infrastructure and retrieve more details about the alert, as needed. You can limit the tools that the agent has access to by specifying them in this section.

> Note: You can list all available tools by running `unpage mcp tools list`

Learn more about connecting plugins and tools [here](/concepts/plugins).

**Response:** In this case, the CPU alert agent will leave a comment on the incident:

> ROOT CAUSE IDENTIFIED: SSL certificate for domain ‘[expired-rsa-dv.ssl.com](http://expired-rsa-dv.ssl.com)’ is EXPIRED. Certificate expired on August 2, 2016 GMT (over 8 years ago). This explains the SSL connection failures. IMMEDIATE ACTION REQUIRED: Certificate renewal needed for affected domain to restore SSL connectivity.

You can customize your agents to automatically respond to different types of alerts and take different actions to address them. See more examples [here](/examples/ssl_connection_failure).

To create your first agent, install Unpage and run Quickstart. You'll have a handful of example agents to start from, or you can create your own\!

```shell
# Install Unpage
curl -fsSL https://install.unpage.ai | bash
```

```shell
# Quickstart
unpage agent quickstart
```

If you need help, you can find us in the [Unpage Slack community](https://join.slack.com/t/unpage/shared_invite/zt-3a85b8rnp-Hf1OIZq8SNu5FyrFhWaGQw) or follow along with this demo: https://www.youtube.com/watch?v=z17sHig2xMk

## Installation

On macOS:

```shell
curl -fsSL https://unpage.ai/install.sh | bash
```

For other platforms, first install `uv` using the [official uv installation guide](https://github.com/astral-sh/uv), then run the command above.

## Quickstart

To get started, run:

```shell
unpage agent quickstart
```

This will get you up and running with your first agent, which will automatically investigate and add context to alerts from PagerDuty (or your preferred alerting provider). You will also have a chance to set up your infrastructure knowledge graph to provide your agent with more context.

## Learn More

- [Test and run your agents](/commands/agent)
- [Set up your knowledge graph](/commands/graph)
- [Expand your agent's knowledge with custom scripts](/plugins/shell)

Have a request for the Unpage team? Let us know on [Slack](https://join.slack.com/t/unpage/shared_invite/zt-3a85b8rnp-Hf1OIZq8SNu5FyrFhWaGQw) or [GitHub](https://github.com/aptible/unpage/issues).

## Documentation

Detailed documentation lives in [docs/](docs/), and is also published via Mintlify to [docs.unpage.ai](https://docs.unpage.ai).

## License

See [LICENSE.md](./LICENSE.md).

## Copyright

Copyright (c) 2025 Aptible. All rights reserved.
