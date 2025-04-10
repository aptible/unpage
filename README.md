# Unpage

> [!WARNING]
> **ALPHA SOFTWARE**
> Unpage is experimental, under heavy development, and may be unstable. Use at your own risk!

Unpage is an infrastructure knowledge graph builder, and an MCP server to enable your LLM-powered application to understand and query your infrastructure.

## Installation

### Prerequisites

- Python 3.12 or higher
- `uv` package manager

### Install uv

On macOS:
```bash
brew install uv
```

For other platforms, follow the [official uv installation guide](https://github.com/astral-sh/uv).

### Install Unpage

Unpage is designed to be run using `uvx`, which comes with `uv`:

```bash
uvx unpage
```

That will automatically install unpage from PyPI in a virtualenv and then run it!

### Setup Unpage

```bash
uvx unpage configure
```

## Usage

### Building the Graph

Before using Unpage, build your knowledge graph:

```bash
uvx unpage build-graph
```

To use a specific profile:
```bash
uvx unpage build-graph --profile your-graph-name
# Or set UNPAGE_PROFILE=your-graph-name
```

### Configure your client to use the MCP Server

#### Claude Desktop

On macOS:
```bash
uvx unpage configure
```

That will, among many other things, create or update the `~/Library/Application Support/Claude/claude_desktop_config.json` file.

## How Unpage Works

Unpage builds a knowledge graph of your infrastructure using a fairly simple inference strategy:

1. Unpage queries the APIs of your integrated tools and retrieves all supported resources, and adds each one as a node in the knowledge graph.
2. Unpage extracts unique identifiers and aliases for each retrieved resource, and adds them to a mapping.
3. Unpage extracts potential references from each retrieved resource, and attempts to match them to identifiers and aliases in the mapping to create edges between nodes.

Once the graph is built, the MCP server provides a set of tools for traversing the graph and interacting with nodes.


## Configuration

### Authentication

Unpage uses your local credentials to access various platforms and tools. Make sure you have the necessary credentials configured:

1. **AWS Credentials**: Configure using standard AWS credential methods (profiles, `aws configure` CLI, EC2 )
2. **Aptible Credentials**: Run `aptible login` to set up your Aptible credentials
3. **Datadog Credentials**: Add your Datadog API key and application key to your `config.yaml` (see below)

### config.yaml

Unpage can be configured using a `config.yaml` file in the `~/.unpage` folder:

```yaml
# Default configuration file location: ~/.unpage/profiles/default/config.yaml
plugins:
  aptible:
    enabled: true
  aws:
    enabled: true
    # These are optional settings for AWS that enable you to specify an existing AWS profile on your system
    # Unpage will use the credentials from that AWS profile to build the infrastructure graph and
    # access CloudWatch metrics about resourse in the MCP server.
    settings:
      accounts:
        dev-account:
          profile: dev-engineering-readonly
  core:
    enabled: true
  datadog:
    enabled: true
    settings:
      api_key: <your datadog API key>
      application_key: <your datadog application key>
  graph:
    enabled: true
  logs:
    enabled: false
  metrics:
    enabled: true
  networking:
    enabled: true
```

## Plugins

Unpage supports various plugins to integrate with different platforms:

### AWS Plugin
- Supports querying AWS resources across multiple regions
- Uses standard AWS credential resolution and profiles in config.yaml
- Supported resources: EC2, RDS, ALBs, ELBs, target groups
- Infers knowledge graph edges between services like ALBs, target groups, and EC2 instances

### Aptible Plugin
- Integrates with Aptible platform
- Uses credentials from `~/.aptible/tokens.json`, which is created by `aptible login`
- Supports apps, databases, and environments
- Infers knowledge graph edges between Aptible and AWS resources

### Datadog Plugin
- Integrates with your Datadog organization
- Uses the API key and application key configured in your `config.yaml`
- Supports importing your Datadog teams, services, systems, and other entities from your software catalog into your knowledge graph

### Adding New Plugins
Plugins are managed in the [`src/unpage/plugins`](src/unpage/plugins) folder. The Aptible and AWS plugins are good examples for adding new resources to the graph and querying metrics.

## Client Setup

We recommend using `uvx unpage configure` to configure clients like Claude Desktop or Amazon Q. This section has examples of configuring those manually...

### Claude Desktop

1. Create or edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
    "mcpServers": {
        "unpage": {
            "command": "/opt/homebrew/bin/uvx",
            "args": ["unpage", "start"],
            "env": {
                "HOME": "/Users/YOUR_USER"
            }
        }
    }
}
```

### Amazon Q

1. Create or edit `~/.aws/amazonq/mcp.json`:
```json
{
    "mcpServers": {
        "unpage": {
            "command": "/opt/homebrew/bin/uvx",
            "args": ["unpage", "start"],
            "env": {
                "HOME": "/Users/YOUR_USER"
            }
        }
    }
}
```

### AWS Vault Integration

If you prefer to use `aws-vault` (or another similar tool) instead of unpage's configuration directly, you can use a configuration like this:
```json
{
    "mcpServers": {
        "unpage": {
            "command": "aws-vault",
            "args": ["exec", "YOUR_AWS_PROFILE", "--", "/opt/homebrew/bin/uvx", "unpage", "start", "--disable-sse"]
        }
    }
}
```
