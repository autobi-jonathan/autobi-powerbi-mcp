"""MCP tools for deployment and CI/CD operations."""

from __future__ import annotations

import json

from powerbi_mcp.server import mcp
from powerbi_mcp.services import fabric_api


@mcp.tool()
async def deploy_model(workspace_id: str, item_id: str, definition_json: str) -> str:
    """Deploy a semantic model definition to a Fabric workspace.

    Updates the model's definition with the provided JSON content.

    Args:
        workspace_id: Fabric workspace GUID.
        item_id: Semantic model item GUID.
        definition_json: JSON string of the model definition to deploy.
    """
    try:
        # Validate JSON before sending
        json.loads(definition_json)
    except json.JSONDecodeError as e:
        return f"Invalid JSON in definition_json: {e}"

    try:
        await fabric_api.update_item_definition(workspace_id, item_id, definition_json)
        return f"Model definition deployed successfully to item {item_id} in workspace {workspace_id}."
    except Exception as e:
        return f"Deployment failed: {e}"


@mcp.tool()
async def trigger_refresh(workspace_id: str, dataset_id: str, refresh_type: str = "full") -> str:
    """Trigger a semantic model refresh.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
        refresh_type: "full" for complete refresh, "automatic" for incremental if configured.
    """
    try:
        result = await fabric_api.trigger_model_refresh(workspace_id, dataset_id, refresh_type)
        return f"Refresh triggered ({refresh_type}). Tracking: {result}"
    except Exception as e:
        return f"Refresh trigger failed: {e}"


@mcp.tool()
async def get_deployment_pipeline_status(pipeline_id: str | None = None) -> str:
    """Get deployment pipeline status -- stages, workspaces, and items.

    Args:
        pipeline_id: Optional pipeline GUID. If omitted, lists all pipelines.
    """
    if not pipeline_id:
        pipelines = await fabric_api.get_deployment_pipelines()
        if not pipelines:
            return "No deployment pipelines found."
        lines = [f"Found {len(pipelines)} pipeline(s):\n"]
        for p in pipelines:
            lines.append(f"  - {p.get('displayName', 'Unknown')} ({p.get('id', '')})")
            if p.get("description"):
                lines.append(f"    {p['description']}")
        return "\n".join(lines)

    stages = await fabric_api.get_pipeline_stages(pipeline_id)
    if not stages:
        return f"No stages found for pipeline {pipeline_id}."
    lines = [f"Pipeline {pipeline_id} stages:\n"]
    for s in stages:
        ws_info = f" -> Workspace: {s.get('workspaceId', 'unassigned')}" if s.get("workspaceId") else " -> No workspace"
        lines.append(f"  Stage {s.get('order', '?')}: {s.get('displayName', 'Unknown')}{ws_info}")
    return "\n".join(lines)


@mcp.tool()
async def promote_stage(pipeline_id: str, source_stage: int, target_stage: int, items_json: str | None = None) -> str:
    """Promote items through a deployment pipeline (e.g., Dev -> Test -> Prod).

    Args:
        pipeline_id: Deployment pipeline GUID.
        source_stage: Source stage order (0=Dev, 1=Test, 2=Prod).
        target_stage: Target stage order.
        items_json: Optional JSON array of items to promote. Format: [{"itemId": "guid"}].
            If omitted, promotes all items.
    """
    items = None
    if items_json:
        try:
            items = json.loads(items_json)
        except json.JSONDecodeError as e:
            return f"Invalid items_json: {e}"

    stage_names = {0: "Dev", 1: "Test", 2: "Prod"}
    source_name = stage_names.get(source_stage, f"Stage {source_stage}")
    target_name = stage_names.get(target_stage, f"Stage {target_stage}")

    try:
        result = await fabric_api.deploy_stage(pipeline_id, source_stage, target_stage, items)
        return f"Promotion {source_name} -> {target_name} initiated.\nResult: {json.dumps(result, indent=2, default=str)}"
    except Exception as e:
        return f"Promotion failed: {e}"
