# Unpage Contribution Guide

We welcome contributions to improve the Unpage project!

We are happy to receive pull requests and issues. Issues are helpful for talking through a more time consuming change ahead of time.

Contributions to this project are released to the public under the project's open source license, which is specified in the LICENSE file.

## Setup a Dev environment

You'll need [uv](https://github.com/astral-sh/uv) to develop locally.

On macOS:

```
brew install uv
```

### UNPAGE_DEVELOPER

Set the `UNPAGE_DEVELOPER=true` to see the python warnings that are typically suppressed.

### Linting & Formatting

This project uses [pre-commit](https://pre-commit.com/) to manage linting and formatting via pre-commit hooks. To set it up:

```
uv run pre-commit install
```

Going forward, linters and formatters will run automatically before each commit.

### MCP Logs on macOS

* `~/Library/Logs/Claude/mcp.log`
* `~/Library/Logs/Claude/mcp-server-aptible.log`

## Debugging Agents

MLflow tracing is a powerful tool to figure out what the heck is happening during agent executions when you run into errors.

Start an MLflow tracking server in one terminal:

```bash
uv run unpage mlflow serve
```

Run an agent and enable tracing by setting the `MLFLOW_TRACKING_URI` environment variable:

```
npx pagerduty-cli rest get --endpoint /incidents/Q1ABCABCABCABC | \
env MLFLOW_TRACKING_URI=http://127.0.0.1:5566 uv run unpage agent run demo-quickstart
```

This also works for the Unpage Agent service:

```
MLFLOW_TRACKING_URI=http://127.0.0.1:5566 uv run unpage agent server
```

And anything that uses the `unpage.agent` package.
