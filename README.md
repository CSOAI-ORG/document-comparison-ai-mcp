<div align="center">

# Document Comparison Ai MCP

**MCP server for document comparison ai mcp operations**

[![PyPI](https://img.shields.io/pypi/v/meok-document-comparison-ai-mcp)](https://pypi.org/project/meok-document-comparison-ai-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![MEOK AI Labs](https://img.shields.io/badge/MEOK_AI_Labs-MCP_Server-purple)](https://meok.ai)

</div>

## Overview

Document Comparison Ai MCP provides AI-powered tools via the Model Context Protocol (MCP).

## Tools

| Tool | Description |
|------|-------------|
| `compare_documents` | Compare two documents and find differences |
| `compare_versions` | Compare two stored document versions |
| `store_document` | Store a document for future comparisons |
| `get_document` | Get a stored document |
| `list_versions` | List all versions of a document |
| `compute_similarity` | Compute similarity score between texts |
| `find_common_terms` | Find common and unique terms between documents |
| `get_comparison_history` | Get comparison history |
| `export_diff` | Export diff in specified format |

## Installation

```bash
pip install meok-document-comparison-ai-mcp
```

## Usage with Claude Desktop

Add to your Claude Desktop MCP config (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "document-comparison-ai": {
      "command": "python",
      "args": ["-m", "meok_document_comparison_ai_mcp.server"]
    }
  }
}
```

## Usage with FastMCP

```python
from mcp.server.fastmcp import FastMCP

# This server exposes 9 tool(s) via MCP
# See server.py for full implementation
```

## License

MIT © [MEOK AI Labs](https://meok.ai)
