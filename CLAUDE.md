# AutoBI Power BI MCP Server

## Purpose
Cross-project MCP (Model Context Protocol) server providing Power BI and Microsoft Fabric tools for Claude Code. Usable from any AutoBI project -- SemanticLayer, sytner-bi, datasetmigration, etc.

## Status
In Development

## Quick Start
```bash
cd C:\git\projects\autobi-powerbi-mcp
python -m venv .venv
.venv\Scripts\activate
pip install -e ".[dev]"
copy .env.example .env   # then fill in credentials

# Run MCP server
python -m powerbi_mcp

# Run tests
pytest
```

## Key Architecture
- `src/powerbi_mcp/server.py` -- MCP server entry point (FastMCP)
- `src/powerbi_mcp/config/settings.py` -- Fabric API credentials from .env
- `src/powerbi_mcp/services/fabric_api.py` -- Shared Fabric REST API client
- `src/powerbi_mcp/tools/workspace.py` -- Workspace & model query tools
- `src/powerbi_mcp/tools/validation.py` -- DAX & schema validation tools
- `src/powerbi_mcp/tools/deployment.py` -- Deployment & CI/CD tools

## MCP Tools
| Tool | Category | Description |
|------|----------|-------------|
| `list_workspaces` | Workspace | List accessible Fabric workspaces |
| `list_workspace_items` | Workspace | List items in a workspace |
| `get_semantic_model_info` | Workspace | Get model metadata |
| `get_refresh_history` | Workspace | Check refresh status and timing |
| `validate_dax` | Validation | Validate a DAX expression |
| `compare_model_schema` | Validation | Compare model vs source columns |
| `check_model_health` | Validation | Best-practice checks on a model |
| `deploy_model` | Deployment | Deploy model definition to workspace |
| `trigger_refresh` | Deployment | Trigger semantic model refresh |
| `get_deployment_pipeline_status` | Deployment | Check pipeline stage status |
| `promote_stage` | Deployment | Promote through deployment pipeline |

## Authentication
Two authentication methods supported:
1. **Service Principal** (recommended): Set `FABRIC_TENANT_ID`, `FABRIC_CLIENT_ID`, `FABRIC_CLIENT_SECRET` in `.env`
2. **Azure CLI**: Run `az login`, leave service principal vars blank

## Integration with Other Projects
Add to Claude Code settings as an MCP server:
```json
{
  "mcpServers": {
    "powerbi": {
      "command": "python",
      "args": ["-m", "powerbi_mcp"],
      "cwd": "C:\\git\\projects\\autobi-powerbi-mcp"
    }
  }
}
```
