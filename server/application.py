import os
import sys
import logging
import re

from flask import Flask, request, jsonify
from flask_cors import cross_origin

# Make sure Python can see yana.py which is in the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from yana import (
    run_yana_pipeline_with_screens,
    get_db_connection,
    semantic_search_context_for_brd,
)

application = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("yana_server")


@application.route("/status")
def status():
    return "OK"

VECTOR_LINE_RE = re.compile(
    r'^\[(?P<kind>[A-Z]+)\s+(?P<code>[^:\]]+):(?P<name>[^\]]+)\]\s+'
    r'\(similarity=(?P<sim>[\d.]+)\)\s+::\s+(?P<content>.*)$'
)
def parse_vector_context(raw: str):
    """
    Parse the compact text returned by semantic_search_context_for_brd()
    into structured hits for the UI.
    """
    hits = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        m = VECTOR_LINE_RE.match(line)
        if not m:
            continue
        hits.append(
            {
                "source_type": m.group("kind"),   # DOC / FLOW / STEP / COMP
                "code": m.group("code"),
                "name": m.group("name"),
                "similarity": float(m.group("sim")),
                "content": m.group("content"),
            }
        )
    return hits


@application.route("/api/search", methods=["GET", "POST"])
@cross_origin()
def search():
    """
    HTTP API to run the Yana pipeline.

    Accepts:
    - GET  /api/search?query=...
    - GET  /api/search?brd=...
    - POST /api/search with JSON: { "brd": "..." } or { "query": "..." }

    Returns:
    - JSON object with keys:
      { service, ui_graph, screen_flows, screens, global_mermaid }
    """
    if request.method == "POST":
        payload = request.get_json(silent=True) or {}
        brd = (payload.get("brd") or payload.get("query") or "").strip()
    else:
        brd = (
            request.args.get("brd")
            or request.args.get("query")
            or ""
        ).strip()

    logger.info(f"Received search request with BRD: '{brd[:50]}...'")

    if not brd:
        logger.warning("Empty BRD received.")
        return jsonify({"error": "Empty BRD"}), 400

    try:
        logger.info("Executing Yana pipeline...")
        bundle, normalized_bundle, evaluation, final = run_yana_pipeline_with_screens(brd)
        logger.info("Yana pipeline executed successfully.")
    except Exception as exc:
        logger.error(f"Error in Yana pipeline: {exc}", exc_info=True)
        return jsonify({"error": str(exc)}), 500
    
        # Build vector similarity evidence for the UI (cosine sim numbers)
    conn = get_db_connection()
    raw_vector_ctx = semantic_search_context_for_brd(conn, brd_text=brd, top_k=30)
    vector_hits = parse_vector_context(raw_vector_ctx)

    # Build richer payload combining all agents
    response = {
        # Agent 4 (screen spec) – what you already used
        **final,  # { service, ui_graph, screen_flows, screens, global_mermaid }

        # Agent 3 – evaluation of flows
        "evaluation": evaluation,

        # Embedding/evidence info used during normalization
        "retrieval": {
            "vector_context_raw": raw_vector_ctx,
            "vector_hits": vector_hits,
        },

        # Debug visibility for earlier agents
        "debug": {
            "agent1_bundle": bundle,
            "agent2_normalized": normalized_bundle,
        },
    }

    logger.info("Returning successful response with evaluation and retrieval metadata.")
    return jsonify(response)





if __name__ == "__main__":
    # Run backend locally on port 8000
    application.run(host="0.0.0.0", port=8000, debug=True)
