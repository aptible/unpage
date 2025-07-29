# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Environment Setup

```bash
# Install uv package manager (if needed)
brew install uv  # On macOS

# Install development dependencies
uv pip install --dev
```

### Building and Running

```bash
# Run the application
uv run unpage

# Start the MCP server
uv run unpage start

# Build the infrastructure knowledge graph
uv run unpage graph build

# Configure the application
uv run unpage configure
```

### Testing

```bash
# Run all tests
uv run pytest

# Run tests with verbosity
uv run pytest -v

# Run tests with coverage
uv run pytest --cov=unpage
```

### Code Quality

```bash
# Install pre-commit hooks (one-time setup)
uv run pre-commit install

# Run pre-commit manually on all files
uv run pre-commit run --all-files

# Run linter
uv run ruff check .

# Run formatter
uv run ruff format .

# Run type checker
uv run pyright
```

### Debugging

```bash
# Start MLflow tracking server for debugging agents
uv run unpage mlflow serve

# Run an agent with tracing enabled
env MLFLOW_TRACKING_URI=http://127.0.0.1:5566 uv run unpage agent run [agent-name]
```

## Architecture Overview

### Knowledge Graph System

Unpage builds a directed graph of infrastructure resources where:
- **Nodes**: Represent infrastructure resources (EC2 instances, databases, load balancers, etc.)
- **Edges**: Represent relationships between resources

The graph is implemented using NetworkX and follows these steps:
1. Resources are retrieved from infrastructure providers via plugins
2. Resources are converted to nodes with their properties and metadata
3. Relationships between resources are inferred and added as edges
4. The graph is persisted to disk as JSON for later use

### Plugin Architecture

Unpage is built around a plugin system where each plugin:
- Extends the system with new data sources or capabilities
- Authenticates with external systems (AWS, Aptible, Datadog, etc.)
- Queries resources from those systems
- Creates nodes in the knowledge graph
- Registers tools for LLM interaction

Plugins implement mixins for different capabilities:
- `KnowledgeGraphMixin`: For adding nodes to the graph
- `McpServerMixin`: For exposing tools to LLMs
- `HasLogs`/`HasMetrics`: For nodes that provide logs/metrics

### MCP Server

The MCP (Model Coupling Protocol) server enables LLM-powered applications to interact with your infrastructure:
- Implements the FastMCP protocol for LLM communication
- Exposes tools provided by plugins for LLMs to use
- Enables graph traversal, resource querying, and infrastructure operations
- Supports both stdio and HTTP transport protocols

### Key Workflows

1. **Building the Graph**:
   - User configures plugins with `unpage configure`
   - User runs `unpage graph build` to build the knowledge graph
   - Graph is saved for later use

2. **Using the MCP Server**:
   - User runs `unpage start` to start the MCP server
   - LLM clients connect to the server
   - LLMs use tools to query and interact with the infrastructure

3. **Agent System**:
   - External systems send alerts to the webhook interface
   - Agents analyze and respond to the alerts using LLM reasoning

## Documentation

Changelog entries live in CHANGELOG.md. This file should not be edited, as it is automatically updated by CI.

User-facing documentation lives under docs/ and is built and published using Mintlify.

### Working relationship
- You can push back on ideas-this can lead to better documentation. Cite sources and explain your reasoning when you do so
- ALWAYS ask for clarification rather than making assumptions
- NEVER lie, guess, or make up information

### Project context
- Format: MDX files with YAML frontmatter
- Config: docs.json for navigation, theme, settings
- Components: Mintlify components

### Content strategy
- Document just enough for user success - not too much, not too little
- Prioritize accuracy and usability of information
- Make content evergreen when possible
- Search for existing information before adding new content. Avoid duplication unless it is done for a strategic reason
- Check existing patterns for consistency
- Start by making the smallest reasonable changes

### docs.json

- Refer to the [docs.json schema](https://mintlify.com/docs.json) when building the docs.json file and site navigation

### Frontmatter requirements for pages
- title: Clear, descriptive page title
- description: Concise summary for SEO/navigation

### Writing standards
- Second-person voice ("you")
- Prerequisites at start of procedural content
- Test all code examples before publishing
- Match style and formatting of existing pages
- Include both basic and advanced use cases
- Language tags on all code blocks
- Alt text on all images
- Relative paths for internal links

### Do not...
- Skip frontmatter on any MDX file
- Use absolute URLs for internal links
- Include untested code examples
- Make assumptions - always ask for clarification