"""Run the OpenInsure MCP server.

Usage:
    python -m openinsure.mcp                                    # stdio (default, localhost)
    python -m openinsure.mcp --sse                              # SSE transport on port 8001
    python -m openinsure.mcp --api-url https://my-tenant.azurecontainerapps.io

The backend URL can also be set via the OPENINSURE_API_BASE_URL env var,
which is the recommended approach for white-label / multi-tenant MCP configs.
"""

from __future__ import annotations

import sys

from openinsure.mcp.server import configure_base_url, mcp


def main() -> None:
    transport = "stdio"
    if "--sse" in sys.argv:
        transport = "sse"

    # --api-url <url> overrides the backend base URL
    if "--api-url" in sys.argv:
        idx = sys.argv.index("--api-url")
        if idx + 1 < len(sys.argv):
            configure_base_url(sys.argv[idx + 1])
        else:
            sys.stderr.write("Error: --api-url requires a URL argument\n")
            sys.exit(1)

    mcp.run(transport=transport)


if __name__ == "__main__":
    main()
