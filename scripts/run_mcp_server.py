"""stdio JSON-RPC MCP server for Smart Event tools."""

from __future__ import annotations

import json
import sys

from mcp.server import build_default_server


def main() -> None:
    server = build_default_server()
    for raw in sys.stdin:
        line = raw.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError as exc:
            response = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(exc)}}
        else:
            response = server.handle_jsonrpc(payload)
        sys.stdout.write(json.dumps(response) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
