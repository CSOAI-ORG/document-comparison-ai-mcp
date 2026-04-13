#!/usr/bin/env python3
"""MEOK AI Labs — document-comparison-ai-mcp MCP Server. Compare documents and highlight differences."""

import asyncio
import json
from datetime import datetime
from typing import Any

from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    Resource,
    Tool,
    TextContent,
)
import mcp.types as types

# In-memory store (replace with DB in production)
_store = {}

server = Server("document-comparison-ai-mcp")

@server.list_resources()
async def handle_list_resources() -> list[Resource]:
    return []

@server.list_tools()
async def handle_list_tools() -> list[Tool]:
    return [
        Tool(name="compare_documents", description="Compare two documents", inputSchema={"type":"object","properties":{"doc1":{"type":"string"},"doc2":{"type":"string"}},"required":["doc1","doc2"]}),
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Any | None) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    args = arguments or {}
    if name == "compare_documents":
            words1 = set(args["doc1"].split())
            words2 = set(args["doc2"].split())
            return [TextContent(type="text", text=json.dumps({"unique_in_doc1": len(words1 - words2), "unique_in_doc2": len(words2 - words1), "common": len(words1 & words2)}, indent=2))]
    return [TextContent(type="text", text=json.dumps({"error": "Unknown tool"}, indent=2))]

async def main():
    async with stdio_server(server._read_stream, server._write_stream) as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="document-comparison-ai-mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )

if __name__ == "__main__":
    asyncio.run(main())
