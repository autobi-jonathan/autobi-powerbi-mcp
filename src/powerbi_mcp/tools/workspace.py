"""MCP tools for querying Fabric workspaces and semantic models."""

from __future__ import annotations

import json

from powerbi_mcp.server import mcp
from powerbi_mcp.services import fabric_api


@mcp.tool()
async def list_workspaces() -> str:
    """List all accessible Microsoft Fabric workspaces.

    Returns workspace ID, name, type, and state for each workspace.
    """
    workspaces = await fabric_api.get_workspaces()
    if not workspaces:
        return "No workspaces found. Check authentication and permissions."
    lines = [f"Found {len(workspaces)} workspace(s):\n"]
    for ws in workspaces:
        lines.append(f"  - {ws.get('displayName', 'Unknown')} ({ws.get('id', '')})")
        lines.append(f"    Type: {ws.get('type', 'N/A')}, State: {ws.get('state', 'N/A')}")
    return "\n".join(lines)


@mcp.tool()
async def list_workspace_items(workspace_id: str, item_type: str | None = None) -> str:
    """List items in a Fabric workspace, optionally filtered by type.

    Args:
        workspace_id: Fabric workspace GUID.
        item_type: Optional filter -- SemanticModel, Report, DataPipeline, Lakehouse, etc.
    """
    items = await fabric_api.get_workspace_items(workspace_id, item_type)
    if not items:
        type_msg = f" of type '{item_type}'" if item_type else ""
        return f"No items{type_msg} found in workspace {workspace_id}."
    lines = [f"Found {len(items)} item(s):\n"]
    for item in items:
        lines.append(f"  - [{item.get('type', '')}] {item.get('displayName', '')} ({item.get('id', '')})")
    return "\n".join(lines)


@mcp.tool()
async def get_semantic_model_info(workspace_id: str, dataset_id: str) -> str:
    """Get metadata for a semantic model -- tables, measures, relationships.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model (dataset) GUID.
    """
    definition = await fabric_api.get_item_definition(workspace_id, dataset_id)
    return json.dumps(definition, indent=2, default=str)


@mcp.tool()
async def get_refresh_history(workspace_id: str, dataset_id: str, top: int = 5) -> str:
    """Get recent refresh history for a semantic model.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
        top: Number of recent refreshes to return (default 5).
    """
    refreshes = await fabric_api.get_refresh_history(workspace_id, dataset_id, top)
    if not refreshes:
        return f"No refresh history found for model {dataset_id}."
    lines = [f"Last {len(refreshes)} refresh(es):\n"]
    for r in refreshes:
        status = r.get("status", "Unknown")
        start = r.get("startTime", "N/A")
        end = r.get("endTime", "N/A")
        rtype = r.get("refreshType", "N/A")
        lines.append(f"  - {status} | {rtype} | {start} -> {end}")
        if r.get("serviceExceptionJson"):
            lines.append(f"    Error: {r['serviceExceptionJson'][:200]}")
    return "\n".join(lines)
