"""Shared Fabric REST API client."""

from __future__ import annotations

import base64
import json
import logging
from typing import Any

import httpx

from powerbi_mcp.config.settings import Settings

logger = logging.getLogger(__name__)

BASE_URL = "https://api.fabric.microsoft.com/v1"


def _headers() -> dict[str, str]:
    """Build authorization headers with a fresh token."""
    token = Settings.get_access_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def get_workspaces() -> list[dict[str, Any]]:
    """List all accessible Fabric workspaces.

    Returns:
        List of workspace dicts with id, displayName, type, state.
    """
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"{BASE_URL}/workspaces", headers=_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])


async def get_workspace_items(workspace_id: str, item_type: str | None = None) -> list[dict[str, Any]]:
    """List items in a workspace, optionally filtered by type.

    Args:
        workspace_id: Fabric workspace GUID.
        item_type: Optional filter (SemanticModel, Report, DataPipeline, etc.).

    Returns:
        List of item dicts with id, displayName, type.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/items"
    params = {"type": item_type} if item_type else {}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])


async def get_item_definition(workspace_id: str, item_id: str) -> dict[str, Any]:
    """Fetch the full definition of a Fabric item.

    Args:
        workspace_id: Fabric workspace GUID.
        item_id: Item GUID.

    Returns:
        Decoded definition dict.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{item_id}/getDefinition"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=_headers(), timeout=60)
        resp.raise_for_status()
        data = resp.json()
        result: dict[str, Any] = {}
        for part in data.get("definition", {}).get("parts", []):
            payload = part.get("payload", "")
            decoded = base64.b64decode(payload).decode("utf-8")
            try:
                result[part["path"]] = json.loads(decoded)
            except json.JSONDecodeError:
                result[part["path"]] = decoded
        return result


async def trigger_model_refresh(workspace_id: str, dataset_id: str, refresh_type: str = "full") -> str:
    """Trigger a semantic model refresh.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model (dataset) GUID.
        refresh_type: "full" or "automatic".

    Returns:
        Refresh request ID from Location header.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/semanticModels/{dataset_id}/refresh"
    body = {"type": refresh_type}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=_headers(), json=body, timeout=30)
        resp.raise_for_status()
        return resp.headers.get("Location", "refresh-triggered")


async def get_refresh_history(workspace_id: str, dataset_id: str, top: int = 5) -> list[dict[str, Any]]:
    """Get recent refresh history for a semantic model.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
        top: Number of recent refreshes to return.

    Returns:
        List of refresh history entries.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/semanticModels/{dataset_id}/refreshes"
    params = {"$top": top}
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_headers(), params=params, timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])


async def execute_dax_query(workspace_id: str, dataset_id: str, dax_query: str) -> dict[str, Any]:
    """Execute a DAX query against a semantic model.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
        dax_query: DAX query string.

    Returns:
        Query result dict.
    """
    url = f"{BASE_URL}/workspaces/{workspace_id}/semanticModels/{dataset_id}/executeQueries"
    body = {"queries": [{"query": dax_query}], "serializerSettings": {"includeNulls": True}}
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=_headers(), json=body, timeout=60)
        resp.raise_for_status()
        return resp.json()


async def update_item_definition(workspace_id: str, item_id: str, definition_content: str) -> None:
    """Update a Fabric item's definition.

    Args:
        workspace_id: Fabric workspace GUID.
        item_id: Item GUID.
        definition_content: JSON string of the definition payload.
    """
    encoded = base64.b64encode(definition_content.encode()).decode()
    payload = {
        "definition": {
            "parts": [{"path": "definition.json", "payload": encoded, "payloadType": "InlineBase64"}]
        }
    }
    url = f"{BASE_URL}/workspaces/{workspace_id}/items/{item_id}/updateDefinition"
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=_headers(), json=payload, timeout=60)
        resp.raise_for_status()


async def get_deployment_pipelines() -> list[dict[str, Any]]:
    """List all deployment pipelines accessible to the user.

    Returns:
        List of pipeline dicts.
    """
    url = f"{BASE_URL}/deploymentPipelines"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])


async def get_pipeline_stages(pipeline_id: str) -> list[dict[str, Any]]:
    """Get stages for a deployment pipeline.

    Args:
        pipeline_id: Deployment pipeline GUID.

    Returns:
        List of stage dicts with order, displayName, workspaceId.
    """
    url = f"{BASE_URL}/deploymentPipelines/{pipeline_id}/stages"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, headers=_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])


async def deploy_stage(pipeline_id: str, source_stage_order: int, target_stage_order: int, items: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Deploy (promote) items from one pipeline stage to the next.

    Args:
        pipeline_id: Deployment pipeline GUID.
        source_stage_order: Source stage order (0=Dev, 1=Test, 2=Prod).
        target_stage_order: Target stage order.
        items: Optional list of specific items to deploy. If None, deploys all.

    Returns:
        Deployment operation result.
    """
    url = f"{BASE_URL}/deploymentPipelines/{pipeline_id}/deploy"
    body: dict[str, Any] = {
        "sourceStageOrder": source_stage_order,
        "targetStageOrder": target_stage_order,
        "isBackwardDeployment": target_stage_order < source_stage_order,
    }
    if items:
        body["items"] = items
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=_headers(), json=body, timeout=120)
        resp.raise_for_status()
        return resp.json()
