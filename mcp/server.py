from __future__ import annotations

from typing import Any

from mcp.protocol import ToolSpec, jsonrpc_error, jsonrpc_result


class McpServer:
    """In-process MCP server: tools/list and tools/call."""

    def __init__(self, name: str = "smart-events-mcp") -> None:
        self.name = name
        self._tools: dict[str, ToolSpec] = {}

    def register(self, spec: ToolSpec) -> None:
        self._tools[spec.name] = spec

    def list_tools(self) -> list[dict[str, Any]]:
        return [spec.to_mcp() for spec in self._tools.values()]

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
        spec = self._tools.get(name)
        if spec is None:
            raise KeyError(f"Unknown MCP tool: {name}")
        return spec.handler(arguments or {})

    def handle_jsonrpc(self, payload: dict[str, Any]) -> dict[str, Any]:
        request_id = payload.get("id")
        method = str(payload.get("method") or "")
        params = payload.get("params") if isinstance(payload.get("params"), dict) else {}
        try:
            if method in {"initialize", "mcp/initialize"}:
                return jsonrpc_result(
                    request_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "serverInfo": {"name": self.name, "version": "1.0.0"},
                        "capabilities": {"tools": {}},
                    },
                )
            if method in {"tools/list", "list_tools"}:
                return jsonrpc_result(request_id, {"tools": self.list_tools()})
            if method in {"tools/call", "call_tool"}:
                name = str(params.get("name") or "")
                arguments = params.get("arguments") if isinstance(params.get("arguments"), dict) else {}
                return jsonrpc_result(
                    request_id,
                    {"content": [{"type": "json", "data": self.call_tool(name, arguments)}]},
                )
            return jsonrpc_error(request_id, -32601, f"Method not found: {method}")
        except KeyError as exc:
            return jsonrpc_error(request_id, -32601, str(exc))
        except Exception as exc:
            return jsonrpc_error(request_id, -32000, str(exc))


def build_default_server() -> McpServer:
    from mcp.tools.tavily_search import tavily_web_speaker_search_tool
    from mcp.tools.venue_validator import venue_capacity_validator_tool

    server = McpServer()
    server.register(tavily_web_speaker_search_tool())
    server.register(venue_capacity_validator_tool())
    return server
