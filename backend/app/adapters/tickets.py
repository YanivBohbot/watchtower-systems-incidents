import json
import sys

from langchain_mcp_adapters.client import MultiServerMCPClient


class McpTickets:
    def __init__(self, server_path, database_path):
        self.client = MultiServerMCPClient(
            {
                "tickets": {
                    "transport": "stdio",
                    "command": sys.executable,
                    "args": [str(server_path.resolve())],
                    "env": {"TICKET_DB_PATH": str(database_path.resolve())},
                }
            }
        )

    async def read_tools(self):
        tools = await self.client.get_tools()
        return [t for t in tools if t.name in ("search_tickets", "get_ticket")]

    async def publish(self, investigation_id: str, report: dict) -> dict:
        async with self.client.session("tickets") as session:
            result = await session.call_tool(
                "create_ticket",
                arguments={
                    "idempotency_key": investigation_id,
                    "title": report["summary"][:200],
                    "body": json.dumps(report, ensure_ascii=False),
                },
            )
            if result.isError:
                raise RuntimeError("MCP ticket creation failed")
            if result.structuredContent:
                return result.structuredContent
            return json.loads(next(block.text for block in result.content if block.type == "text"))
