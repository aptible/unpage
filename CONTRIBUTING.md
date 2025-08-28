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

Set `UNPAGE_DEVELOPER=true` in your environment to see the python warnings that are typically suppressed.

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

## Releases

This project uses [semantic-release](https://python-semantic-release.readthedocs.io/) for automated versioning and publishing to PyPI. Releases are triggered automatically when PRs are merged to the main branch.

### PR Title Requirements

**Your PR title must follow the [Conventional Commits](https://www.conventionalcommits.org/) format** to trigger releases and generate proper changelog entries.

#### Release-Triggering Prefixes

- **`feat:`** - New features (triggers **minor** version bump: `0.1.0` → `0.2.0`)
- **`fix:`** - Bug fixes (triggers **patch** version bump: `0.1.0` → `0.1.1`)
- **`perf:`** - Performance improvements (triggers **patch** version bump: `0.1.0` → `0.1.1`)

#### Non-Release Prefixes

These prefixes are allowed but **do not trigger releases**:

- `build:` - Build system changes
- `chore:` - Maintenance tasks
- `ci:` - CI/CD changes
- `docs:` - Documentation updates
- `style:` - Code formatting changes
- `refactor:` - Code refactoring
- `test:` - Test additions or updates

#### Examples

✅ **Good PR titles:**
- `feat: add dark mode toggle to settings`
- `fix: resolve memory leak in graph builder`
- `perf: optimize database query performance`
- `docs: update installation instructions`

❌ **Bad PR titles:**
- `Update README` (missing prefix)
- `feat add new feature` (missing colon)
- `feature: add dark mode` (invalid prefix)

### Release Process

1. **Merge PR** with proper conventional commit title
2. **Automated release** runs on main branch
3. **Version bump** based on PR title prefix
4. **Changelog update** generated automatically
5. **PyPI publish** happens automatically

If your PR doesn't need a release (documentation, tests, etc.), use the non-release prefixes listed above.
