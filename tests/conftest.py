"""Shared test fixtures."""

import pytest
from unittest.mock import AsyncMock, patch


@pytest.fixture
def mock_fabric_api():
    """Mock the fabric_api module for unit tests."""
    with patch("powerbi_mcp.services.fabric_api") as mock:
        mock.get_workspaces = AsyncMock(return_value=[])
        mock.get_workspace_items = AsyncMock(return_value=[])
        mock.get_item_definition = AsyncMock(return_value={})
        mock.get_refresh_history = AsyncMock(return_value=[])
        mock.execute_dax_query = AsyncMock(return_value={})
        mock.trigger_model_refresh = AsyncMock(return_value="refresh-id")
        mock.get_deployment_pipelines = AsyncMock(return_value=[])
        mock.get_pipeline_stages = AsyncMock(return_value=[])
        mock.deploy_stage = AsyncMock(return_value={})
        mock.update_item_definition = AsyncMock()
        yield mock
