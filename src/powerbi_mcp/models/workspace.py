"""Pydantic models for Fabric API responses."""

from __future__ import annotations

from pydantic import BaseModel


class WorkspaceInfo(BaseModel):
    """Fabric workspace summary."""

    id: str
    display_name: str
    type: str = ""
    state: str = ""


class WorkspaceItem(BaseModel):
    """Item within a Fabric workspace."""

    id: str
    display_name: str
    type: str
    description: str = ""


class RefreshEntry(BaseModel):
    """Semantic model refresh history entry."""

    request_id: str = ""
    status: str = ""
    start_time: str = ""
    end_time: str = ""
    refresh_type: str = ""
    service_exception_json: str = ""


class DeploymentPipeline(BaseModel):
    """Deployment pipeline summary."""

    id: str
    display_name: str
    description: str = ""


class PipelineStage(BaseModel):
    """Stage within a deployment pipeline."""

    order: int
    display_name: str
    workspace_id: str = ""
    workspace_name: str = ""
