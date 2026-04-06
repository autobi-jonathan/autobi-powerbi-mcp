"""MCP server entry point -- registers all tools via FastMCP."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("powerbi-mcp", instructions="Power BI and Microsoft Fabric tools for workspace management, validation, and deployment.")

# Import tool modules to register their @mcp.tool() decorators
import powerbi_mcp.tools.workspace  # noqa: F401, E402
import powerbi_mcp.tools.validation  # noqa: F401, E402
import powerbi_mcp.tools.deployment  # noqa: F401, E402
