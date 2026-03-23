"""Run the OpenInsure MCP server.

Usage:
    python -m openinsure.mcp            # stdio transport (default)
    python -m openinsure.mcp --sse      # SSE transport on port 8001
"""

from __future__ import annotations

import sys

from openinsure.mcp.server import mcp


def main() -> None:
    transport = "stdio"
    if "--sse" in sys.argv:
        transport = "sse"
    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
