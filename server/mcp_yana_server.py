# server/mcp_yana_server.py
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

from mcp.server.fastmcp import FastMCP

# Ensure the project root is on sys.path so yana_tools can be imported when run as a script.
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

from yana_tools import (
    generate_screens_only,
    get_flow_bundle,
    get_step_details,
    list_ui_components,
    semantic_search_components,
    build_ui_graph_from_bundle,
)

# Create the MCP server instance
# json_response=True makes dict/list outputs come back as JSON text
mcp = FastMCP(
    name="yana-mcp",
    json_response=True,
)

@mcp.tool(
    name="yana.greet",
    description="A simple greeting tool for testing the Yana MCP server.",
)
def yana_greet(name: str) -> str:
    """
    A simple greeting tool to verify the MCP server is running.
    """
    return f"Hello, {name}! Welcome to the Yana MCP server."

@mcp.tool()
def add(a: int, b: int) -> int:
    """Adds two integer numbers together."""
    return a + b


@mcp.tool(
    name="yana.generate_screens_only",
    description=(
        "Run the Yana pipeline on a BRD and return only designer-facing data: "
        "service, UI graph, screen flows, screen definitions, and global Mermaid diagram."
    ),
)
def t_generate_screens_only(brd: str) -> Dict[str, Any]:
    """
    Generate screens & flows from a BRD using the Yana multi-agent pipeline.
    Returns the 'final' object from run_yana_pipeline_with_screens().
    """
    return generate_screens_only(brd)


@mcp.tool(
    name="yana.get_flow_bundle",
    description=(
        "Load a complete UX flow from the diia_ai.db database by flow slug, including "
        "service, flows, steps, transitions, step_components, and ui_components."
    ),
)
def t_get_flow_bundle(flow_slug: str) -> Dict[str, Any]:
    """
    Fetch a complete flow from the DB so designers or other agents can inspect or extend it.
    """
    return get_flow_bundle(flow_slug)


@mcp.tool(
    name="yana.get_step_details",
    description=(
        "Get a deep view of a single step/screen by its slug, including metadata, "
        "attached UI components (with roles), and incoming/outgoing transitions."
    ),
)
def t_get_step_details(step_slug: str) -> Dict[str, Any]:
    """
    Deep view of a single step: metadata, components, transitions.
    """
    return get_step_details(step_slug)


@mcp.tool(
    name="yana.list_ui_components",
    description=(
        "List UI design system components from the diia_ai.db database. "
        "You can optionally filter by component type and/or a search string "
        "that matches name, description, or usage notes."
    ),
)
def t_list_ui_components(
    type: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List design system components with optional filters.
    - type: filter by component type (e.g. 'button', 'input', etc.)
    - search: substring to match in name / description / usage_notes.
    """
    return list_ui_components(type_filter=type, search=search)


@mcp.tool(
    name="yana.semantic_search_components",
    description=(
        "Use vector embeddings to find the most relevant official UI components "
        "for a natural-language description (e.g. 'confirmation button', "
        "'error banner', 'document upload card')."
    ),
)
def t_semantic_search_components(
    query: str,
    top_k: int = 10,
) -> Dict[str, Any]:
    """
    Semantic search over UI components using the embeddings table.
    """
    return semantic_search_components(query=query, top_k=top_k)


@mcp.tool(
    name="yana.build_ui_graph_from_bundle",
    description=(
        "Build a UI graph (nodes, edges, Mermaid diagram, etc.) from a normalized "
        "Yana bundle object (Agent 2 schema)."
    ),
)
def t_build_ui_graph_from_bundle(
    normalized_bundle: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Wrap the existing build_ui_graph into an MCP tool.
    The normalized_bundle should match Agent 2's output schema.
    """
    return build_ui_graph_from_bundle(normalized_bundle)


if __name__ == "__main__":
    # Choose transport:
    # - "stdio" for local tools (e.g. fastmcp dev, IDEs, some MCP clients)
    # - "streamable-http" for HTTP endpoint (e.g. MCP Inspector, remote deployments)
    # transport = os.getenv("YANA_MCP_TRANSPORT", "streamable-http")
    # mcp.run(transport=transport)

    # mcp.run(transport="http", host="127.0.0.1", port=9000)
    mcp.run(transport="http", host="localhost", port=8013, path="/mcp")