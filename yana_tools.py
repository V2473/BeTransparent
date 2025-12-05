# yana_tools.py
import sqlite3
from typing import Dict, Any, List, Optional
import json

from yana import (
    run_yana_pipeline_with_screens,
    get_db_connection,
    semantic_search_context_for_brd,
    build_ui_graph,
    agent4_generate_screen_spec,
)

# -----------------------------
# 1) generate_screens_only
# -----------------------------

def generate_screens_only(brd: str) -> Dict[str, Any]:
    """
    Run full Yana pipeline but return only what designers care about:
    { service, ui_graph, screen_flows, screens, global_mermaid }.
    """
    bundle, normalized, evaluation, final = run_yana_pipeline_with_screens(brd)
    # final already has the keys we need
    return final


# -----------------------------
# 2) get_flow_bundle
# -----------------------------

def get_flow_bundle(flow_slug: str) -> Dict[str, Any]:
    """
    Load a complete flow from the DB so designers (or another LLM)
    can inspect it or extend it.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Find the flow
    flow = cur.execute(
        """
        SELECT *
        FROM flows
        WHERE slug = ?
        """,
        (flow_slug,),
    ).fetchone()

    if not flow:
        raise ValueError(f"Flow with slug '{flow_slug}' not found")

    # Get service
    service = cur.execute(
        "SELECT * FROM services WHERE id = ?",
        (flow["service_id"],),
    ).fetchone()

    # Get steps for this flow
    steps = cur.execute(
        """
        SELECT *
        FROM steps
        WHERE flow_id = ?
        ORDER BY id
        """,
        (flow["id"],),
    ).fetchall()

    # Step ids
    step_ids = [row["id"] for row in steps] or [-1]

    # Get transitions
    transitions = cur.execute(
        """
        SELECT *
        FROM transitions
        WHERE flow_id = ?
          AND from_step_id IN ({ids})
        """.format(ids=",".join("?" * len(step_ids))),
        [flow["id"], *step_ids],
    ).fetchall()

    # Get step_components and related ui_components
    step_components = cur.execute(
        """
        SELECT *
        FROM step_components
        WHERE step_id IN ({ids})
        """.format(ids=",".join("?" * len(step_ids))),
        step_ids,
    ).fetchall()

    comp_ids = list({row["component_id"] for row in step_components}) or [-1]

    ui_components = cur.execute(
        """
        SELECT *
        FROM ui_components
        WHERE id IN ({ids})
        """.format(ids=",".join("?" * len(comp_ids))),
        comp_ids,
    ).fetchall()

    # Convert rows to dicts
    def row_to_dict(row):
        return {k: row[k] for k in row.keys()}

    return {
        "service": row_to_dict(service) if service else None,
        "flows": [row_to_dict(flow)],
        "steps": [row_to_dict(s) for s in steps],
        "transitions": [row_to_dict(t) for t in transitions],
        "step_components": [row_to_dict(sc) for sc in step_components],
        "ui_components": [row_to_dict(c) for c in ui_components],
    }


# -----------------------------
# 3) get_step_details
# -----------------------------

def get_step_details(step_slug: str) -> Dict[str, Any]:
    """
    Deep view of a single step: metadata, components, transitions.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    step = cur.execute(
        "SELECT * FROM steps WHERE slug = ?",
        (step_slug,),
    ).fetchone()

    if not step:
        raise ValueError(f"Step with slug '{step_slug}' not found")

    # Components
    step_components = cur.execute(
        "SELECT * FROM step_components WHERE step_id = ?",
        (step["id"],),
    ).fetchall()

    comp_ids = [sc["component_id"] for sc in step_components] or [-1]

    ui_components = cur.execute(
        """
        SELECT *
        FROM ui_components
        WHERE id IN ({ids})
        """.format(ids=",".join("?" * len(comp_ids))),
        comp_ids,
    ).fetchall()

    # Transitions (incoming/outgoing)
    outgoing = cur.execute(
        "SELECT * FROM transitions WHERE from_step_id = ?",
        (step["id"],),
    ).fetchall()

    incoming = cur.execute(
        "SELECT * FROM transitions WHERE to_step_id = ?",
        (step["id"],),
    ).fetchall()

    def row_to_dict(row):
        return {k: row[k] for k in row.keys()}

    return {
        "step": row_to_dict(step),
        "components": [
            {
                **row_to_dict(comp),
                "role": sc["role"],
            }
            for sc in step_components
            for comp in ui_components
            if comp["id"] == sc["component_id"]
        ],
        "outgoing_transitions": [row_to_dict(t) for t in outgoing],
        "incoming_transitions": [row_to_dict(t) for t in incoming],
    }


# -----------------------------
# 4) list_ui_components
# -----------------------------

def list_ui_components(
    type_filter: Optional[str] = None,
    search: Optional[str] = None,
) -> Dict[str, Any]:
    """
    List components from the design system with optional filters.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    query = "SELECT * FROM ui_components WHERE 1=1"
    params: List[Any] = []

    if type_filter:
        query += " AND type = ?"
        params.append(type_filter)

    if search:
        # Very simple search across name/description/usage_notes
        like = f"%{search}%"
        query += """
            AND (
                name LIKE ?
                OR description LIKE ?
                OR usage_notes LIKE ?
            )
        """
        params.extend([like, like, like])

    rows = cur.execute(query, params).fetchall()

    return {
        "components": [{k: row[k] for k in row.keys()} for row in rows]
    }


# -----------------------------
# 5) semantic_search_components
# -----------------------------

def semantic_search_components(query: str, top_k: int = 10) -> Dict[str, Any]:
    """
    Use embeddings table to find closest UI components for a textual query.
    Assumes that:
      - source_type = 'ui_components'
      - content_type = 'component_description'
    exist in the 'embeddings' table.
    """
    conn = get_db_connection()
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # We reuse the same embedding function as Agent 2
    from yana import embed_text, cosine_similarity

    query_vec = embed_text(query)

    rows = cur.execute(
        """
        SELECT e.*, c.key, c.name, c.description, c.usage_notes
        FROM embeddings e
        JOIN ui_components c ON c.id = e.source_id
        WHERE e.source_type = 'ui_components'
          AND e.content_type = 'component_description'
        """
    ).fetchall()

    hits = []
    for row in rows:
        emb = json.loads(row["embedding"]) if isinstance(row["embedding"], str) else None
        if emb is None:
            continue
        sim = cosine_similarity(query_vec, emb)
        hits.append(
            {
                "component_key": row["key"],
                "component_name": row["name"],
                "description": row["description"],
                "usage_notes": row["usage_notes"],
                "similarity": float(sim),
            }
        )

    hits.sort(key=lambda h: h["similarity"], reverse=True)
    return {"components": hits[:top_k]}


# -----------------------------
# 6) build_ui_graph_from_bundle
# -----------------------------

def build_ui_graph_from_bundle(normalized_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Wrap existing build_ui_graph into a simple tool-friendly function.
    """
    return build_ui_graph(normalized_bundle)
