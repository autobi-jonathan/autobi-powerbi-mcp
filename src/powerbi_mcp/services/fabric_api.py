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
PBI_ADMIN_URL = "https://api.powerbi.com/v1.0/myorg/admin"
PBI_URL = "https://api.powerbi.com/v1.0/myorg"


def _headers() -> dict[str, str]:
    """Build authorization headers with a fresh token."""
    token = Settings.get_access_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


async def get_workspaces() -> list[dict[str, Any]]:
    """List all Fabric workspaces using admin API with user API fallback.

    Returns:
        List of workspace dicts with id, displayName/name, type, state.
    """
    async with httpx.AsyncClient() as client:
        # Try admin API first (tenant-level SP access)
        resp = await client.get(f"{PBI_ADMIN_URL}/groups?$top=5000", headers=_headers(), timeout=30)
        if resp.status_code == 200:
            workspaces = resp.json().get("value", [])
            # Normalize field names (admin API uses 'name', Fabric uses 'displayName')
            for ws in workspaces:
                if "name" in ws and "displayName" not in ws:
                    ws["displayName"] = ws["name"]
            return workspaces
        # Fall back to Fabric user API
        resp = await client.get(f"{BASE_URL}/workspaces", headers=_headers(), timeout=30)
        resp.raise_for_status()
        return resp.json().get("value", [])


async def get_workspace_items(workspace_id: str, item_type: str | None = None) -> list[dict[str, Any]]:
    """List items in a workspace, optionally filtered by type.

    Uses Fabric API with Power BI admin API fallback for tenant-level SP access.

    Args:
        workspace_id: Fabric workspace GUID.
        item_type: Optional filter (SemanticModel, Report, DataPipeline, etc.).

    Returns:
        List of item dicts with id, displayName, type.
    """
    async with httpx.AsyncClient() as client:
        # Try Fabric API first
        url = f"{BASE_URL}/workspaces/{workspace_id}/items"
        params = {"type": item_type} if item_type else {}
        resp = await client.get(url, headers=_headers(), params=params, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("value", [])
        # Fall back to Power BI admin API (returns datasets, reports, etc. separately)
        items: list[dict[str, Any]] = []
        type_endpoints = {
            "SemanticModel": "datasets",
            "Report": "reports",
            "Dashboard": "dashboards",
            "Dataflow": "dataflows",
        }
        endpoints = {item_type: type_endpoints[item_type]} if item_type and item_type in type_endpoints else type_endpoints
        for itype, endpoint in endpoints.items():
            r = await client.get(f"{PBI_ADMIN_URL}/groups/{workspace_id}/{endpoint}", headers=_headers(), timeout=30)
            if r.status_code == 200:
                for item in r.json().get("value", []):
                    items.append({"id": item.get("id", ""), "displayName": item.get("name", ""), "type": itype, **{k: v for k, v in item.items() if k not in ("id", "name")}})
        return items


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
    async with httpx.AsyncClient() as client:
        # User API (works if SP has workspace membership)
        url = f"{PBI_URL}/groups/{workspace_id}/datasets/{dataset_id}/refreshes?$top={top}"
        resp = await client.get(url, headers=_headers(), timeout=30)
        if resp.status_code == 200:
            return resp.json().get("value", [])
        # Fabric API
        url = f"{BASE_URL}/workspaces/{workspace_id}/semanticModels/{dataset_id}/refreshes"
        resp = await client.get(url, headers=_headers(), params={"$top": top}, timeout=30)
        if resp.status_code == 200:
            return resp.json().get("value", [])
        # Admin API doesn't expose per-dataset refresh history directly.
        # Fall back to refresh schedule as partial info.
        url = f"{PBI_ADMIN_URL}/datasets/{dataset_id}/refreshSchedule"
        resp = await client.get(url, headers=_headers(), timeout=30)
        if resp.status_code == 200:
            schedule = resp.json()
            return [{"status": "Scheduled", "refreshType": "Scheduled", "schedule": schedule}]
        return []


async def execute_dax_query(workspace_id: str, dataset_id: str, dax_query: str) -> dict[str, Any]:
    """Execute a DAX query against a semantic model.

    Uses PBI API (supports SP auth) with Fabric API fallback.
    Note: RLS-enabled models do not support SP DAX queries.

    Args:
        workspace_id: Fabric workspace GUID.
        dataset_id: Semantic model GUID.
        dax_query: DAX query string.

    Returns:
        Query result dict.
    """
    body = {"queries": [{"query": dax_query}], "serializerSettings": {"includeNulls": True}}
    async with httpx.AsyncClient() as client:
        # PBI API (works with SP auth for non-RLS models)
        url = f"{PBI_URL}/groups/{workspace_id}/datasets/{dataset_id}/executeQueries"
        resp = await client.post(url, headers=_headers(), json=body, timeout=60)
        if resp.status_code == 200:
            return resp.json()
        if resp.status_code == 400:
            # DAX syntax/semantic error -- return the error, don't fall through
            return resp.json()
        if resp.status_code == 401:
            # RLS-enabled model or permission issue -- include helpful message
            raise httpx.HTTPStatusError(
                f"Unauthorized (401). If this model has RLS enabled, SP DAX queries are not supported.",
                request=resp.request,
                response=resp,
            )
        # Other errors -- try Fabric API fallback
        url = f"{BASE_URL}/workspaces/{workspace_id}/semanticModels/{dataset_id}/executeQueries"
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
