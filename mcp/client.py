from __future__ import annotations

from typing import Any

from mcp.server import McpServer, build_default_server


class McpClient:
    """In-process MCP client used by the Deep Agent."""

    def __init__(self, server: McpServer | None = None) -> None:
        self._server = server or build_default_server()

    def list_tools(self) -> list[dict[str, Any]]:
        return self._server.list_tools()

    def has_tool(self, name: str) -> bool:
        return any(tool.get("name") == name for tool in self.list_tools())

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        return self._server.call_tool(name, arguments or {})

    def call_if_available(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any] | None:
        if not self.has_tool(name):
            return None
        return self.call_tool(name, arguments or {})


_default_client: McpClient | None = None


def default_mcp_client() -> McpClient:
    global _default_client
    if _default_client is None:
        _default_client = McpClient()
    return _default_client
