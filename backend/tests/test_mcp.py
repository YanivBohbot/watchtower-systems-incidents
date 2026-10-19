import asyncio
from pathlib import Path

from app.adapters.tickets import McpTickets


def test_real_mcp_stdio_round_trip_and_idempotency(tmp_path):
    async def scenario():
        server = Path(__file__).resolve().parents[2] / "mcp_server/server.py"
        tickets = McpTickets(server, tmp_path / "tickets.db")
        tools = await tickets.read_tools()
        assert {tool.name for tool in tools} == {"search_tickets", "get_ticket"}
        report = {"summary": "Zone A presence"}
        first = await tickets.publish("investigation-1", report)
        second = await tickets.publish("investigation-1", report)
        assert first["id"] == second["id"]
        search = next(tool for tool in tools if tool.name == "search_tickets")
        result = await search.ainvoke({"query": "Zone A"})
        assert first["id"] in str(result)

    asyncio.run(scenario())
