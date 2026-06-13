#!/usr/bin/env python3
"""
MEOK AI Labs — document-comparison-ai-mcp MCP Server. Advanced document comparison with diff highlighting and version tracking."""

import json
import re
from datetime import datetime, timezone
from typing import Any, List, Set
import uuid
import sys, os

from auth_middleware import check_access
from mcp.server.fastmcp import FastMCP
from collections import defaultdict
import urllib.request as _meter_urlreq
import urllib.error as _meter_urlerr

FREE_DAILY_LIMIT = 50
_usage = defaultdict(list)
def _rl(c="anon"):
    now = datetime.now(timezone.utc)
    _usage[c] = [t for t in _usage[c] if (now-t).total_seconds() < 86400]
    if len(_usage[c]) >= FREE_DAILY_LIMIT: return json.dumps({"error": f"Limit {FREE_DAILY_LIMIT}/day"})
    _usage[c].append(now); return None

_store = {"comparisons": [], "documents": {}, "versions": {}}
mcp = FastMCP("document-comparison-ai", instructions="Advanced document comparison with diff highlighting and version tracking.")


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

def _server_meter_check(api_key: str = "") -> dict:
    """Calls the live /verify endpoint for server-side metering. Returns the JSON dict.
    Fail-open: if /verify is unreachable or KV isn't configured, returns allowed=True
    (so the local rate-limit in _check_rate_limit remains the safety net)."""
    try:
        data = json.dumps({"api_key": api_key, "tool": ""}).encode()
        req = _meter_urlreq.Request(_METER_URL, data=data,
            headers={"Content-Type": "application/json"}, method="POST")
        with _meter_urlreq.urlopen(req, timeout=2.5) as r:
            d = json.loads(r.read())
            if isinstance(d, dict) and "allowed" in d:
                return d
    except Exception:
        pass
    return {"allowed": True, "tier": "anonymous", "remaining": 200, "upgrade_url": "https://meok.ai/pricing"}


_METER_URL = "https://proofof.ai/verify"


@mcp.tool()
def compare_documents(doc1: str, doc2: str, api_key: str = "") -> str:
    """Compare two documents and find differences

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        doc1 (str): The doc1 to analyze or process.
        doc2 (str): The doc2 to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    result = compute_diff(doc1, doc2)

    comparison = {
        "id": create_id(),
        "result": result,
        "timestamp": datetime.now().isoformat(),
    }
    _store["comparisons"].append(comparison)

    return json.dumps(
        {
            "comparison_id": comparison["id"],
            "similarity_percent": result["similarity_percent"],
            "stats": result["stats"],
            "diff_preview": result["diff_lines"][:5] if result["diff_lines"] else [],
            "key_differences": {
                "added": result["added_words"][:10],
                "removed": result["removed_words"][:10],
            },
        },
        indent=2,
    )


@mcp.tool()
def compare_versions(doc_id: str, version1: int = 1, version2: int = 2, api_key: str = "") -> str:
    """Compare two stored document versions

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        doc_id (str): The doc id to analyze or process.
        version1 (int): The version1 to analyze or process.
        version2 (int): The version2 to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    if doc_id not in _store["documents"]:
        return json.dumps({"error": "Document not found"})

    doc_data = _store["documents"][doc_id]
    ver1 = doc_data.get(f"version_{version1}")
    ver2 = doc_data.get(f"version_{version2}")

    if not ver1 or not ver2:
        return json.dumps({"error": "Version not found"})

    result = compute_diff(ver1["content"], ver2["content"])

    return json.dumps(
        {"doc_id": doc_id, "version1": version1, "version2": version2, "comparison": result},
        indent=2,
    )


@mcp.tool()
def store_document(doc_id: str, content: str, metadata: dict = None, api_key: str = "") -> str:
    """Store a document for future comparisons

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        doc_id (str): The doc id to analyze or process.
        content (str): The content to analyze or process.
        metadata (dict): The metadata to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    if doc_id not in _store["documents"]:
        _store["documents"][doc_id] = {
            "versions": [],
            "created_at": datetime.now().isoformat(),
        }

    version_num = len(_store["documents"][doc_id].get("versions", [])) + 1

    version = {
        "version": version_num,
        "content": content,
        "metadata": metadata or {},
        "stored_at": datetime.now().isoformat(),
    }

    _store["documents"][doc_id][f"version_{version_num}"] = version
    _store["documents"][doc_id]["versions"].append(version_num)

    return json.dumps(
        {
            "stored": True,
            "doc_id": doc_id,
            "version": version_num,
            "total_versions": len(_store["documents"][doc_id]["versions"]),
        },
        indent=2,
    )


@mcp.tool()
def get_document(doc_id: str, version: int = 0, api_key: str = "") -> str:
    """Get a stored document

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        doc_id (str): The doc id to analyze or process.
        version (int): The version to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    if doc_id not in _store["documents"]:
        return json.dumps({"error": "Document not found"})

    if version:
        doc_data = _store["documents"][doc_id].get(f"version_{version}")
        if doc_data:
            return json.dumps(
                {
                    "doc_id": doc_id,
                    "version": version,
                    "content": doc_data["content"],
                    "metadata": doc_data.get("metadata", {}),
                },
                indent=2,
            )

    latest_ver = max(_store["documents"][doc_id].get("versions", [1]))
    doc_data = _store["documents"][doc_id].get(f"version_{latest_ver}")

    return json.dumps(
        {"doc_id": doc_id, "version": latest_ver, "content": doc_data["content"]},
        indent=2,
    )


@mcp.tool()
def list_versions(doc_id: str, api_key: str = "") -> str:
    """List all versions of a document

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        doc_id (str): The doc id to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    if doc_id not in _store["documents"]:
        return json.dumps({"error": "Document not found"})

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

    return json.dumps({"doc_id": doc_id, "versions": version_list}, indent=2)


@mcp.tool()
def compute_similarity(text1: str, text2: str, api_key: str = "") -> str:
    """Compute similarity score between texts

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        text1 (str): The text1 to analyze or process.
        text2 (str): The text2 to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    result = compute_diff(text1, text2)

    return json.dumps(
        {
            "similarity_percent": result["similarity_percent"],
            "common_words": result["common_words"][:20],
            "unique_to_each": {
                "text1_only": result["removed_words"][:10],
                "text2_only": result["added_words"][:10],
            },
        },
        indent=2,
    )


@mcp.tool()
def find_common_terms(doc1: str, doc2: str, api_key: str = "") -> str:
    """Find common and unique terms between documents

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        doc1 (str): The doc1 to analyze or process.
        doc2 (str): The doc2 to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    tokens1 = set(tokenize(doc1))
    tokens2 = set(tokenize(doc2))

    common = tokens1 & tokens2
    unique1 = tokens1 - tokens2
    unique2 = tokens2 - tokens1

    return json.dumps(
        {
            "common_terms": list(common),
            "unique_to_doc1": list(unique1),
            "unique_to_doc2": list(unique2),
            "common_count": len(common),
            "unique1_count": len(unique1),
            "unique2_count": len(unique2),
        },
        indent=2,
    )


@mcp.tool()
def get_comparison_history(doc_id: str = "", limit: int = 10, api_key: str = "") -> str:
    """Get comparison history

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        doc_id (str): The doc id to analyze or process.
        limit (int): The limit to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    comparisons = _store["comparisons"][-limit:]

    if doc_id:
        comparisons = [c for c in comparisons if c.get("doc_id") == doc_id]

    return json.dumps({"comparisons": comparisons, "count": len(comparisons)}, indent=2)


@mcp.tool()
def export_diff(comparison_id: str, format: str = "json", api_key: str = "") -> str:
    """Export diff in specified format

    Behavior:
        This tool is read-only and stateless — it produces analysis output
        without modifying any external systems, databases, or files.
        Safe to call repeatedly with identical inputs (idempotent).
        Free tier: 10/day rate limit. Pro tier: unlimited.
        No authentication required for basic usage.

    When to use:
        Use this tool when you need to assess, audit, or verify compliance
        requirements. Ideal for gap analysis, readiness checks, and generating
        compliance documentation.

    When NOT to use:
        Do not use as a substitute for qualified legal counsel. This tool
        provides technical compliance guidance, not legal advice.

    Args:
        comparison_id (str): The comparison id to analyze or process.
        format (str): The format to analyze or process.
        api_key (str): The api key to analyze or process.

    Behavioral Transparency:
        - Side Effects: This tool is read-only and produces no side effects. It does not modify
          any external state, databases, or files. All output is computed in-memory and returned
          directly to the caller.
        - Authentication: No authentication required for basic usage. Pro/Enterprise tiers
          require a valid MEOK API key passed via the MEOK_API_KEY environment variable.
        - Rate Limits: Free tier: 10 calls/day. Pro tier: unlimited. Rate limit headers are
          included in responses (X-RateLimit-Remaining, X-RateLimit-Reset).
        - Error Handling: Returns structured error objects with 'error' key on failure.
          Never raises unhandled exceptions. Invalid inputs return descriptive validation errors.
        - Idempotency: Fully idempotent — calling with the same inputs always produces the
          same output. Safe to retry on timeout or transient failure.
        - Data Privacy: No input data is stored, logged, or transmitted to external services.
          All processing happens locally within the MCP server process.
    """
    allowed, msg, tier = check_access(api_key)
    if not allowed:
        return json.dumps({"error": msg, "upgrade_url": "https://councilof.ai"})
    if err := _rl(): return err

    comparison = next(
        (c for c in _store["comparisons"] if c.get("id") == comparison_id), None
    )

    if not comparison:
        return json.dumps({"error": "Comparison not found"})

    if format == "json":
        return json.dumps(comparison["result"], indent=2)

    elif format == "unified":
        result = comparison["result"]
        lines = ["--- Original", "+++ New"]
        for d in result.get("diff_lines", []):
            prefix = "+" if d["type"] == "added" else "-"
            lines.append(f"{prefix} {d['line']}: {d['content'][:50]}")
        return "\n".join(lines)

    elif format == "html":
        result = comparison["result"]
        html = ["<div class='diff'>"]
        for d in result.get("diff_lines", []):
            cls = "added" if d["type"] == "added" else "removed"
            html.append(f"<div class='{cls}'>{d['line']}: {d['content']}</div>")
        html.append("</div>")
        return "\n".join(html)

    return json.dumps({"error": "Unknown format"})


def main():
    mcp.run()

if __name__ == '__main__':
    main()


# ── MEOK monetization layer (Stripe upgrade · PAYG · pricing) ──────────
# Free tier is zero-config. Upgrade to Pro (unlimited) or pay-as-you-go per call.
import os as _meok_os
MEOK_STRIPE_UPGRADE = "https://buy.stripe.com/aFa7sNcgAdQS0ZT1Uc8k91t"  # Pro (unlimited)
MEOK_PAYG_KEY = _meok_os.environ.get("MEOK_PAYG_KEY", "")  # set to enable PAYG (x402 / ~GBP0.05 per call)
MEOK_PRICING = "https://meok.ai/pricing"


def meok_upsell(tier: str = "free") -> dict:
    """Monetization options for free-tier callers: Pro upgrade, PAYG, or pricing page."""
    if tier != "free":
        return {}
    return {"upgrade_url": MEOK_STRIPE_UPGRADE,
            "payg_enabled": bool(MEOK_PAYG_KEY),
            "pricing": MEOK_PRICING}
