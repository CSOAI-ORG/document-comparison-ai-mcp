#!/usr/bin/env python3
"""MEOK AI Labs — document-comparison-ai-mcp MCP Server. Advanced document comparison with diff highlighting and version tracking."""

import asyncio
import json
import re
from datetime import datetime, timezone
from typing import Any, List, Set
import uuid
import sys, os

sys.path.insert(0, os.path.expanduser("~/clawd/meok-labs-engine/shared"))
from auth_middleware import check_access
from collections import defaultdict

FREE_DAILY_LIMIT = 15
_usage = defaultdict(list)
def _rl(c="anon"):
    now = datetime.now(timezone.utc)
    _usage[c] = [t for t in _usage[c] if (now-t).total_seconds() < 86400]
    if len(_usage[c]) >= FREE_DAILY_LIMIT: return json.dumps({"error": f"Limit {FREE_DAILY_LIMIT}/day"})
    _usage[c].append(now); return None
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.types import Resource, Tool, TextContent
import mcp.types as types

_store = {"comparisons": [], "documents": {}, "versions": {}}
server = Server("document-comparison-ai")


def create_id():
    return str(uuid.uuid4())[:8]


def tokenize(text: str) -> List[str]:
    return re.findall(r"\b\w+\b", text.lower())


def compute_diff(text1: str, text2: str) -> dict:
    tokens1 = tokenize(text1)
    tokens2 = tokenize(text2)

    set1, set2 = set(tokens1), set(tokens2)

    added = set2 - set1
    removed = set1 - set2
    common = set1 & set2

    similarity = len(common) / max(len(set1 | set2), 1) * 100

    diff_lines = []
    lines1 = text1.split("\n")
    lines2 = text2.split("\n")

    max_lines = max(len(lines1), len(lines2))
    for i in range(max_lines):
        l1 = lines1[i] if i < len(lines1) else ""
        l2 = lines2[i] if i < len(lines2) else ""

        if l1 != l2:
            if l1:
                diff_lines.append({"type": "removed", "line": i + 1, "content": l1})
            if l2:
                diff_lines.append({"type": "added", "line": i + 1, "content": l2})

    return {
        "added_words": list(added),
        "removed_words": list(removed),
        "common_words": list(common),
        "similarity_percent": round(similarity, 2),
        "diff_lines": diff_lines[:20],
        "stats": {
            "total_unique_1": len(set1 - set2),
            "total_unique_2": len(set2 - set1),
            "common_count": len(common),
        },
    }


@server.list_resources()
async def handle_list_resources():
    return [
        Resource(
            uri="doc://comparisons",
            name="Document Comparisons",
            mimeType="application/json",
        ),
        Resource(
            uri="doc://documents", name="Stored Documents", mimeType="application/json"
        ),
    ]


@server.list_tools()
async def handle_list_tools():
    return [
        Tool(
            name="compare_documents",
            description="Compare two documents and find differences",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc1": {"type": "string"},
                    "doc2": {"type": "string"},
                    "api_key": {"type": "string"},
                },
                "required": ["doc1", "doc2"],
            },
        ),
        Tool(
            name="compare_versions",
            description="Compare two stored document versions",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "version1": {"type": "number"},
                    "version2": {"type": "number"},
                },
            },
        ),
        Tool(
            name="store_document",
            description="Store a document for future comparisons",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "content": {"type": "string"},
                    "metadata": {"type": "object"},
                },
                "required": ["doc_id", "content"],
            },
        ),
        Tool(
            name="get_document",
            description="Get a stored document",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "version": {"type": "number"},
                },
            },
        ),
        Tool(
            name="list_versions",
            description="List all versions of a document",
            inputSchema={
                "type": "object",
                "properties": {"doc_id": {"type": "string"}},
            },
        ),
        Tool(
            name="compute_similarity",
            description="Compute similarity score between texts",
            inputSchema={
                "type": "object",
                "properties": {
                    "text1": {"type": "string"},
                    "text2": {"type": "string"},
                },
            },
        ),
        Tool(
            name="find_common_terms",
            description="Find common and unique terms between documents",
            inputSchema={
                "type": "object",
                "properties": {"doc1": {"type": "string"}, "doc2": {"type": "string"}},
            },
        ),
        Tool(
            name="get_comparison_history",
            description="Get comparison history",
            inputSchema={
                "type": "object",
                "properties": {
                    "doc_id": {"type": "string"},
                    "limit": {"type": "number"},
                },
            },
        ),
        Tool(
            name="export_diff",
            description="Export diff in specified format",
            inputSchema={
                "type": "object",
                "properties": {
                    "comparison_id": {"type": "string"},
                    "format": {"type": "string", "enum": ["json", "unified", "html"]},
                },
            },
        ),
    ]


@server.call_tool()
async def handle_call_tool(name: str, arguments: Any = None) -> list[types.TextContent]:
    args = arguments or {}
    api_key = args.get("api_key", "")
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"error": msg, "upgrade_url": "https://meok.ai/pricing"}
                ),
            )
        ]
    if err := _rl(): return [TextContent(type="text", text=err)]

    if name == "compare_documents":
        doc1 = args.get("doc1", "")
        doc2 = args.get("doc2", "")

        result = compute_diff(doc1, doc2)

        comparison = {
            "id": create_id(),
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
        _store["comparisons"].append(comparison)

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "comparison_id": comparison["id"],
                        "similarity_percent": result["similarity_percent"],
                        "stats": result["stats"],
                        "diff_preview": result["diff_lines"][:5]
                        if result["diff_lines"]
                        else [],
                        "key_differences": {
                            "added": result["added_words"][:10],
                            "removed": result["removed_words"][:10],
                        },
                    },
                    indent=2,
                ),
            )
        ]

    elif name == "compare_versions":
        doc_id = args.get("doc_id")
        v1 = args.get("version1", 1)
        v2 = args.get("version2", 2)

        if doc_id not in _store["documents"]:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": "Document not found"})
                )
            ]

        doc_data = _store["documents"][doc_id]
        ver1 = doc_data.get(f"version_{v1}")
        ver2 = doc_data.get(f"version_{v2}")

        if not ver1 or not ver2:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": "Version not found"})
                )
            ]

        result = compute_diff(ver1["content"], ver2["content"])

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "doc_id": doc_id,
                        "version1": v1,
                        "version2": v2,
                        "comparison": result,
                    },
                    indent=2,
                ),
            )
        ]

    elif name == "store_document":
        doc_id = args.get("doc_id", create_id())
        content = args.get("content", "")
        metadata = args.get("metadata", {})

        if doc_id not in _store["documents"]:
            _store["documents"][doc_id] = {
                "versions": [],
                "created_at": datetime.now().isoformat(),
            }

        version_num = len(_store["documents"][doc_id].get("versions", [])) + 1

        version = {
            "version": version_num,
            "content": content,
            "metadata": metadata,
            "stored_at": datetime.now().isoformat(),
        }

        _store["documents"][doc_id][f"version_{version_num}"] = version
        _store["documents"][doc_id]["versions"].append(version_num)

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "stored": True,
                        "doc_id": doc_id,
                        "version": version_num,
                        "total_versions": len(_store["documents"][doc_id]["versions"]),
                    },
                    indent=2,
                ),
            )
        ]

    elif name == "get_document":
        doc_id = args.get("doc_id")
        version = args.get("version")

        if doc_id not in _store["documents"]:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": "Document not found"})
                )
            ]

        if version:
            doc_data = _store["documents"][doc_id].get(f"version_{version}")
            if doc_data:
                return [
                    TextContent(
                        type="text",
                        text=json.dumps(
                            {
                                "doc_id": doc_id,
                                "version": version,
                                "content": doc_data["content"],
                                "metadata": doc_data.get("metadata", {}),
                            },
                            indent=2,
                        ),
                    )
                ]

        latest_ver = max(_store["documents"][doc_id].get("versions", [1]))
        doc_data = _store["documents"][doc_id].get(f"version_{latest_ver}")

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "doc_id": doc_id,
                        "version": latest_ver,
                        "content": doc_data["content"],
                    },
                    indent=2,
                ),
            )
        ]

    elif name == "list_versions":
        doc_id = args.get("doc_id")

        if doc_id not in _store["documents"]:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": "Document not found"})
                )
            ]

        versions = _store["documents"][doc_id].get("versions", [])

        version_list = []
        for v in versions:
            ver_data = _store["documents"][doc_id].get(f"version_{v}")
            version_list.append(
                {
                    "version": v,
                    "stored_at": ver_data.get("stored_at"),
                    "metadata": ver_data.get("metadata", {}),
                }
            )

        return [
            TextContent(
                type="text",
                text=json.dumps({"doc_id": doc_id, "versions": version_list}, indent=2),
            )
        ]

    elif name == "compute_similarity":
        text1 = args.get("text1", "")
        text2 = args.get("text2", "")

        result = compute_diff(text1, text2)

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "similarity_percent": result["similarity_percent"],
                        "common_words": result["common_words"][:20],
                        "unique_to_each": {
                            "text1_only": result["removed_words"][:10],
                            "text2_only": result["added_words"][:10],
                        },
                    },
                    indent=2,
                ),
            )
        ]

    elif name == "find_common_terms":
        doc1 = args.get("doc1", "")
        doc2 = args.get("doc2", "")

        tokens1 = set(tokenize(doc1))
        tokens2 = set(tokenize(doc2))

        common = tokens1 & tokens2
        unique1 = tokens1 - tokens2
        unique2 = tokens2 - tokens1

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {
                        "common_terms": list(common),
                        "unique_to_doc1": list(unique1),
                        "unique_to_doc2": list(unique2),
                        "common_count": len(common),
                        "unique1_count": len(unique1),
                        "unique2_count": len(unique2),
                    },
                    indent=2,
                ),
            )
        ]

    elif name == "get_comparison_history":
        doc_id = args.get("doc_id")
        limit = args.get("limit", 10)

        comparisons = _store["comparisons"][-limit:]

        if doc_id:
            comparisons = [c for c in comparisons if c.get("doc_id") == doc_id]

        return [
            TextContent(
                type="text",
                text=json.dumps(
                    {"comparisons": comparisons, "count": len(comparisons)}, indent=2
                ),
            )
        ]

    elif name == "export_diff":
        comparison_id = args.get("comparison_id")
        fmt = args.get("format", "json")

        comparison = next(
            (c for c in _store["comparisons"] if c.get("id") == comparison_id), None
        )

        if not comparison:
            return [
                TextContent(
                    type="text", text=json.dumps({"error": "Comparison not found"})
                )
            ]

        if fmt == "json":
            return [
                TextContent(
                    type="text", text=json.dumps(comparison["result"], indent=2)
                )
            ]

        elif fmt == "unified":
            result = comparison["result"]
            lines = ["--- Original", "+++ New"]
            for d in result.get("diff_lines", []):
                prefix = "+" if d["type"] == "added" else "-"
                lines.append(f"{prefix} {d['line']}: {d['content'][:50]}")
            return [TextContent(type="text", text="\n".join(lines))]

        elif fmt == "html":
            result = comparison["result"]
            html = ["<div class='diff'>"]
            for d in result.get("diff_lines", []):
                cls = "added" if d["type"] == "added" else "removed"
                html.append(f"<div class='{cls}'>{d['line']}: {d['content']}</div>")
            html.append("</div>")
            return [TextContent(type="text", text="\n".join(html))]

        return [TextContent(type="text", text=json.dumps({"error": "Unknown format"}))]

    return [TextContent(type="text", text=json.dumps({"error": "Unknown tool"}))]


async def main():
    async with stdio_server(server._read_stream, server._write_stream) as (
        read_stream,
        write_stream,
    ):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="document-comparison-ai",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
