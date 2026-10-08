from mcp.client import McpClient
from mcp.server import build_default_server
from mcp.tools.tavily_search import TOOL_NAME as TAVILY_TOOL
from mcp.tools.venue_validator import TOOL_NAME as VENUE_TOOL


def test_mcp_lists_custom_tools():
    tools = {item["name"] for item in build_default_server().list_tools()}
    assert TAVILY_TOOL in tools
    assert VENUE_TOOL in tools


def test_mcp_jsonrpc_lists_tools():
    response = build_default_server().handle_jsonrpc(
        {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}
    )
    names = {item["name"] for item in response["result"]["tools"]}
    assert names == {TAVILY_TOOL, VENUE_TOOL}


def test_tavily_tool_stays_offline_without_key(app):
    result = McpClient().call_tool(
        TAVILY_TOOL,
        {"speaker_name": "Ada Lovelace", "topic": "analytical engines", "max_results": 2},
    )
    assert result["tool"] == TAVILY_TOOL
    assert result["enabled"] is False
    assert result["results"] == []


def test_venue_tool_rejects_invalid_capacity(app):
    result = McpClient().call_tool(VENUE_TOOL, {"capacity": 75})
    assert result["valid"] is False
    assert result["hall_ok"] is False
    assert "50, 100, or 300" in result["issues"][0]


def test_venue_tool_accepts_open_hall(app):
    result = McpClient().call_tool(
        VENUE_TOOL,
        {
            "capacity": 50,
            "date": "2026-12-20",
            "start_time": "09:00",
            "end_time": "10:00",
        },
    )
    assert result["valid"] is True
    assert result["hall_ok"] is True
    assert result["conflict"] is None


def test_venue_tool_detects_schedule_conflict(client, speaker_headers, event_payload):
    from conftest import approve_talk_event

    created = approve_talk_event(client, speaker_headers, event_payload)
    result = McpClient().call_tool(
        VENUE_TOOL,
        {
            "capacity": event_payload["capacity"],
            "date": event_payload["date"],
            "start_time": event_payload["start_time"],
            "end_time": event_payload["end_time"],
        },
    )
    assert result["valid"] is False
    assert result["conflict"]["title"] == created["title"]


def test_assessment_invokes_mcp_tools(client):
    client.post(
        "/register",
        json={
            "user_id": "spk-mcp",
            "password": "SecurePass1",
            "role": "speaker",
            "name": "MCP Speaker",
        },
    )
    client.post("/speaker/login", json={"user_id": "spk-mcp", "password": "SecurePass1"})
    created = client.post(
        "/api/submit",
        json={
            "title": "MCP tools for conference programming",
            "abstract": (
                "How a Deep Agent can call Tavily and a venue validator through "
                "Model Context Protocol while reviewing talk proposals."
            ),
            "category": "architecture",
            "date": "2026-12-21",
            "start_time": "11:00",
            "end_time": "12:00",
            "capacity": 100,
        },
    ).get_json()
    tools = created["ai_assessment"]["mcp_tools"]
    assert TAVILY_TOOL in tools["invoked"]
    assert VENUE_TOOL in tools["invoked"]
    assert created["ai_assessment"]["hooks"]["mcp_tavily"]["invoked"] is True
    assert created["ai_assessment"]["hooks"]["mcp_venue"]["invoked"] is True
    assert created["ai_assessment"]["venue_check"]["hall_ok"] is True
    assert created["ai_assessment"]["web_check"]["enabled"] is False
