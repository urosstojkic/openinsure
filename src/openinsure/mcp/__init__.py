"""OpenInsure MCP Server — Model Context Protocol interface.

Usage:
    python -m openinsure.mcp          # stdio transport (for Copilot CLI, Claude Desktop)
    python -m openinsure.mcp --sse    # SSE transport (for web clients)
"""

from openinsure.mcp.server import OpenInsureMCPServer, mcp

__all__ = ["OpenInsureMCPServer", "mcp"]
