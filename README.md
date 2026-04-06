# AutoBI Power BI MCP Server

Cross-project MCP server providing Power BI and Microsoft Fabric tools for Claude Code.

## Quick Start

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env   # fill in credentials
python -m powerbi_mcp
```

## Configuration

See `.env.example` for required environment variables.

## Development

```bash
pytest                    # Run tests
ruff check --fix .        # Lint
ruff format .             # Format
```
