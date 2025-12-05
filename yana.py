import os
import json
import math
import sqlite3
from typing import List, Optional, Literal, Tuple, Dict, Any

from functools import lru_cache
import logging
from openai import OpenAI


# ==========================
# CONFIG
# ==========================

OPENAI_MODEL_WORKFLOW = "gpt-5.1"
OPENAI_MODEL_EVAL = "gpt-5.1"
OPENAI_MODEL_EMBED = "text-embedding-3-small"
DB_PATH = "diia_ai.db"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

logger = logging.getLogger("yana_pipeline")

@lru_cache(maxsize=1)
def get_openai_client() -> OpenAI:
    """
    Lazily initialize the OpenAI client so imports don't explode when the key
    isn't configured. Callers still need OPENAI_API_KEY set before use.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Please export it before running the Yana pipeline."
        )
    return OpenAI(api_key=api_key)



# ==========================
# PROMPTS – copied from the n8n logic (inline)
# ==========================

# ---- Agent 1: AI_classify ----

CLASSIFY_SYSTEM_PROMPT = """You are an expert UX/service designer and product analyst for the Diia ecosystem.

Your job in this step:
- Receive a business requirement document (BRD) describing a NEW feature that must be integrated into the Diia app.
- Propose not less than 2–3 alternative user workflows that could implement this feature.
- For each workflow:
  - Describe it in structured JSON (see schema).
  - Generate a Mermaid flowchart of the workflow.
  - Explain screens, components, transitions, and key business rules.

Very important:
- You MUST output a single JSON object that matches the provided JSON schema exactly.
- No extra text, no explanations outside JSON.
- Use double quotes for all keys and string values.
- All Mermaid diagrams must be provided as strings and MUST start with `flowchart TD`.
- Try to re-use naming style similar to existing Diia flows: use subgraphs for steps, IDs like A0, A1, R_select etc.

JSON structure (high level, for your understanding):
- service: { slug, name, summary, tags[] }
- flows[]: { slug, name, goal, primary_actor, entry_point, notes, mermaid_diagram }
- steps[]: each row is compatible with table `steps` but uses slugs and enriched descriptions.
- ui_components[]: component catalog used in those steps.
- step_components[]: each item MUST be of the form
  { "step_slug": "<step_slug>", "component_slugs": ["<ui_component_slug>", "..."], "role": "primary" }.
- transitions[]: mapping between steps with triggers/conditions.

Behaviour rules:
- Always propose 2 or 3 workflows.
- Make flows different by entry point, path or UX strategy (but still realistic for Diia).
- Keep descriptions compact but information-dense (good for embeddings).
- Ensure every step slug appears as a node in the Mermaid diagram (via mermaid_node_id).
- If the BRD is vague, still create flows but list your assumptions explicitly in the textual fields (notes, purpose, etc.).
end
"""

CLASSIFY_USER_PROMPT_TEMPLATE = """You will now design new workflows.

1) BUSINESS REQUIREMENT (BRD)
---
{brd}
---

Task:
- Based on the BRD propose 2–3 alternative workflows implementing this feature in the Diia app.
- Follow the JSON schema from the system message.
- Return ONLY a single JSON object, no extra explanations.
"""


# ---- Agent 2: AI_Retrieve (normalization + now embedding-based retrieval) ----

RETRIEVE_SYSTEM_PROMPT = """You are a Diia service design expert whose job is to NORMALIZE proposed workflows so they follow existing Diia logic.

You receive:
- Proposed workflows for a new feature from another agent (JSON, with Mermaid diagrams) that follow a fixed schema.
- Reference context about canonical Diia flows (e.g. Warm Winter) and design patterns (provided in the user message).
- Optionally, existing Mermaid diagrams of current flows.

Your task:
- Read the proposed workflows and compare them to the patterns in the reference context.
- Adjust and normalize the workflows so they are realistic for Diia:
  - Fix entry points so they match tabs, sections and patterns used in Diia.
  - Rename step groups and screens to be consistent with existing flows.
  - Adjust conditions, eligibility, and statuses to match Warm Winter / Diia logic where relevant.
  - Reuse or align with existing flows (e.g. discovery via “Сервіси”, Diia.Card, notifications, catalog, etc.) when possible.
- Keep the SAME overall JSON structure and schema as the input (service, flows[], steps[], ui_components[], step_components[], transitions[]), but you may:
  - Add `derived_from_flow_slug` to flows.
  - Add `mapping_to_reference_flows` to flows.
  - Add `normalization_notes` to flows and steps.
- Update Mermaid diagrams to stay consistent with your changes (node IDs must still match step slugs / mermaid_node_id).

Behaviour rules:
- Output MUST be a single JSON object.
- Do NOT invent a completely different schema.
- Preserve useful information from the initial suggestion, but correct it to Diia reality.
- If a workflow is clearly impossible or redundant, you may mark that in `normalization_notes`, but still keep it in the array so later agents can see it.
end
"""

RETRIEVE_USER_PROMPT_TEMPLATE = """You will now normalize the proposed workflows to match Diia logic.

1) ORIGINAL FEATURE REQUEST (BRD)
---
{brd}
---

2) PROPOSED WORKFLOWS FROM PREVIOUS AGENT (JSON)
This object has:
- service
- flows[]
- steps[]
- ui_components[]
- step_components[]
- transitions[]
---
{candidate_flows_json}
---

3) REFERENCE CONTEXT FROM INTERNAL KNOWLEDGE BASE (retrieved via embeddings)
This contains:
- Short summaries of relevant BRDs / guidelines.
- Summaries of similar flows.
- Detailed descriptions of steps and UI components that are similar to the proposed solution.
Use this as your main reference for entry points, naming, and business logic.
---
{retrieval_context}
---

Task:
- Normalize and adjust the proposed workflows so they align with Diia patterns from the reference context.
- Keep the same JSON structure and fields, but you may add:
  - derived_from_flow_slug
  - mapping_to_reference_flows
  - normalization_notes
- Update Mermaid diagrams where needed.
- Return ONLY a single JSON object, no explanations outside the JSON.
"""


# ---- Agent 3: AI_flow_evaluation ----

EVAL_SYSTEM_PROMPT = """You are an internal evaluation assistant for the Diia design team. Reply in Ukrainian language.

Your job:
- Receive a JSON object describing a NEW feature and several alternative workflows for it.
- Optionally receive CONTEXT with:
  - Extracts from the Diia design system and canonical flows.
  - Vector similarity matches between each suggested workflow and existing Diia flows.

You must:
1) Analyse each workflow separately.
2) Estimate how good it is according to these criteria:

   A. Click / step efficiency
      - Approximate the number of user actions (taps/clicks) required along the MAIN HAPPY PATH:
        from entry screen to final confirmation/success.
      - Fewer steps (with still complete logic) is better.

   B. Unusual components
      - Identify components that look unusual vs. Diia patterns (e.g. strange checkout patterns, non-mobile UI, web-like tables).
      - Count them and list them.

   C. Correspondence to Diia design system
      - Check that:
        - Entry points match Diia patterns (e.g. “Сервіси” tab, catalog, notifications, QR, etc.).
        - Screen naming and structure look similar to existing services (like the Warm Winter flows).
        - Components combine into realistic Diia screens.
      - Use any provided vector similarity evidence to support your judgement:
        higher similarity to reference flows = better alignment.

3) Produce a structured JSON evaluation:
   - Give each workflow:
     - estimated click count along the main path;
     - count and list of unusual components;
     - a design-system alignment score (0–1);
     - an overall score (0–1) that combines the above criteria;
     - short bullet-point pros / cons.
   - Also:
     - Select ONE workflow as recommended.
     - Explain in 3–5 sentences why this workflow is preferred.
end
"""

EVAL_USER_PROMPT_TEMPLATE = """You will now evaluate alternative workflows for a new feature in the Diia app.

1) CANDIDATE WORKFLOWS (JSON)
This object has:
- service
- flows[]
- steps[]
- ui_components[]
- step_components[]
- transitions[]
---
{normalized_flows_json}
---

2) DESIGN-SYSTEM CONTEXT / VECTOR SIMILARITY EVIDENCE (OPTIONAL)
These are additional snippets and similarity scores from the internal knowledge base.
---
{vector_similarity_context}
---

TASK:
- For every workflow in flows[]:
  - Estimate the number of user clicks along the main happy path.
  - Count and list unusual components.
  - Evaluate how closely the flow matches Diia design patterns (0–1).
  - Use vector similarity evidence to support this evaluation where available.
  - Give each workflow an overall score (0–1) and short lists of pros and cons.
- Then choose ONE workflow as the recommended one and explain why.
Return ONLY a single JSON object following the schema.
"""



# ---- Agent 4: screen spec / UI workflows ----

SCREEN_SPEC_SYSTEM_PROMPT = """You are a senior product designer and UX-writer for the Diia app. Reply in Ukrainian.

You receive:
- A NORMALIZED workflow bundle for a new feature (service, flows, steps, ui_components, step_components, transitions, flows_mermaid).
- A derived UI_GRAPH object that already connects each step to a Mermaid node id and attached components (nodes, edges, mermaid).

Your goal:

1) Think in terms of real mobile screens in Diia.
   - Combine one or more steps into a single screen when that matches realistic UX.
   - Typical screen types: list/catalog, details, form, confirmation, info, settings.

2) For each screen, describe:
   - What the user can do on this screen.
   - Which steps happen here (reference step_slugs).
   - Which Mermaid node ids are shown on this screen.
   - Which components are on the screen and how they are grouped (sections).

3) For each component instance on a screen, specify:
   - component_slug (matching ui_components when possible; new ones allowed but keep them realistic).
   - label (button text, field label, chip label, etc., in Ukrainian).
   - placeholder or helper text where useful.
   - role: primary / secondary / informational.
   - Optional actions (e.g. button tap) that navigate to another screen and/or step_slug.

4) Build screen flows:
   - For every flow_slug in the normalized bundle, provide an ordered list of screen_ids that represent the main happy path for that flow.
   - Use short screen_ids like "screen_services_grid", "screen_sport_catalog", etc.

5) Output format (JSON object):
{
  "screen_flows": [
    {
      "flow_slug": "<flow_slug>",
      "name": "<human name of flow>",
      "description": "<short explanation of the flow>",
      "screens": ["<screen_id_1>", "<screen_id_2>", "..."]
    }
  ],
  "screens": [
    {
      "screen_id": "<unique screen id>",
      "step_slugs": ["<step_slug_1>", "..."],
      "mermaid_node_ids": ["<node_id_1>", "..."],
      "screen_type": "list|details|form|confirmation|info|other",
      "title": "<title text on screen>",
      "subtitle": "<optional subtitle>",
      "functional_description": "<2–4 sentences: what the user does here>",
      "sections": [
        {
          "type": "search|filters|list|details|form|summary|other",
          "title": "<optional section title>",
          "description": "<short explanation>",
          "components": [
            {
              "component_slug": "<slug from ui_components or new>",
              "label": "<UI label or button text>",
              "placeholder": "<optional placeholder>",
              "role": "primary|secondary|informational",
              "repeats": "<optional, e.g. 'for each class in catalog'>",
              "binding": "<optional data binding path>",
              "actions": [
                {
                  "label": "<button label>",
                  "navigates_to_screen_id": "<target screen id or empty>",
                  "navigates_to_step_slug": "<target step slug or empty>"
                }
              ]
            }
          ]
        }
      ],
      "primary_action": {
        "label": "<main button label>",
        "navigates_to_screen_id": "<target screen id or empty>",
        "navigates_to_step_slug": "<target step slug or empty>"
      }
    }
  ]
}

Rules:
- All user-visible text MUST be in Ukrainian.
- Use only step_slugs and Mermaid node ids that exist in the input.
- Keep microcopy short, clear and friendly, in the style of Diia.
- Return ONLY a single JSON object with those top-level keys, no explanations.
"""

SCREEN_SPEC_USER_PROMPT_TEMPLATE = """You will now prepare final app screens for a new Diia service.

1) NORMALIZED WORKFLOW BUNDLE (JSON)
This object has:
- service
- flows[]
- steps[]
- ui_components[]
- step_components[]
- transitions[]
- flows_mermaid[]
---
{normalized_json}
---

2) UI_GRAPH (derived structure: nodes, edges, global mermaid)
Each node corresponds to a step and contains step metadata and its components.
---
{ui_graph_json}
---

Task:
- Use the information above to build realistic Diia-style screens.
- Follow exactly the JSON shape described in the system message (screen_flows + screens).
- Use Ukrainian language for all labels, placeholders and descriptions.
- Return ONLY the JSON object, no extra text.
"""





# ==========================
# Embedding utilities
# ==========================

def embed_text(text: str) -> List[float]:
    text = text.replace("\n", " ")
    resp = get_openai_client().embeddings.create(
        model=OPENAI_MODEL_EMBED,
        input=text,
    )
    return resp.data[0].embedding


def cosine_similarity(a: List[float], b: List[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# ==========================
# DB helpers – embeddings & retrieval
# ==========================

def get_db_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_embeddings_for_all(conn: sqlite3.Connection) -> None:
    """
    Ensure that every document / flow / step / ui_component has at least one
    embedding row in the `embeddings` table.

    Safe to call multiple times: it only creates embeddings that are missing.
    """
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    def has_embedding(source_type: str, source_id: int, content_type: str) -> bool:
        cur.execute(
            """
            SELECT 1
            FROM embeddings
            WHERE source_type = ?
              AND source_id = ?
              AND content_type = ?
            LIMIT 1
            """,
            (source_type, source_id, content_type),
        )
        return cur.fetchone() is not None

    created = 0

    # -------------------------
    # documents -> brd/guideline summary
    # -------------------------
    logger.info("Seeding embeddings for documents...")
    for row in cur.execute(
        """
        SELECT id, service_id, flow_id, doc_type, title, body
        FROM documents
        """
    ):
        doc_id = row["id"]
        doc_type = (row["doc_type"] or "").lower()

        if doc_type.startswith("brd"):
            content_type = "brd_summary"
        else:
            content_type = "guideline_summary"

        if has_embedding("documents", doc_id, content_type):
            continue

        title = (row["title"] or "").strip()
        body = (row["body"] or "").strip()
        content = f"{title}. {body}".strip(". ").strip()

        if not content:
            continue

        vec = embed_text(content)
        cur.execute(
            """
            INSERT INTO embeddings (
                source_type, source_id,
                service_id, flow_id, step_id,
                content_type, content, tags, embedding
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "documents",
                doc_id,
                row["service_id"],
                row["flow_id"],
                None,
                content_type,
                content,
                None,
                json.dumps(vec),
            ),
        )
        created += 1

    # -------------------------
    # flows -> flow_summary
    # -------------------------
    logger.info("Seeding embeddings for flows...")
    for row in cur.execute(
        """
        SELECT id, service_id, slug, name, goal, notes
        FROM flows
        """
    ):
        flow_id = row["id"]
        if has_embedding("flows", flow_id, "flow_summary"):
            continue

        slug = row["slug"] or ""
        name = row["name"] or ""
        goal = (row["goal"] or "").strip()
        notes = (row["notes"] or "").strip()

        content_parts = [
            f"Flow {slug} ({name})",
        ]
        if goal:
            content_parts.append(f"Goal: {goal}")
        if notes:
            content_parts.append(f"Notes: {notes}")

        content = ". ".join(content_parts).strip(". ").strip()
        if not content:
            continue

        vec = embed_text(content)
        cur.execute(
            """
            INSERT INTO embeddings (
                source_type, source_id,
                service_id, flow_id, step_id,
                content_type, content, tags, embedding
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "flows",
                flow_id,
                row["service_id"],
                flow_id,
                None,
                "flow_summary",
                content,
                None,
                json.dumps(vec),
            ),
        )
        created += 1

    # -------------------------
    # steps -> step_description
    # -------------------------
    logger.info("Seeding embeddings for steps...")
    for row in cur.execute(
        """
        SELECT
            id, service_id, flow_id, slug, name,
            purpose, user_actions, data_inputs, data_outputs,
            conditions, ui_summary, notes
        FROM steps
        """
    ):
        step_id = row["id"]
        if has_embedding("steps", step_id, "step_description"):
            continue

        def t(field: str) -> str:
            return (row[field] or "").strip()

        content = (
            f"Step {t('slug')} ({t('name')}): "
            f"purpose={t('purpose')}. "
            f"User_actions={t('user_actions')}. "
            f"Inputs={t('data_inputs')}. "
            f"Outputs={t('data_outputs')}. "
            f"Conditions={t('conditions')}. "
            f"UI={t('ui_summary')}. "
            f"Notes={t('notes')}"
        ).strip()

        if not content:
            continue

        vec = embed_text(content)
        cur.execute(
            """
            INSERT INTO embeddings (
                source_type, source_id,
                service_id, flow_id, step_id,
                content_type, content, tags, embedding
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "steps",
                step_id,
                row["service_id"],
                row["flow_id"],
                step_id,
                "step_description",
                content,
                None,
                json.dumps(vec),
            ),
        )
        created += 1

    # -------------------------
    # ui_components -> component_description
    # -------------------------
    logger.info("Seeding embeddings for ui_components...")
    for row in cur.execute(
        """
        SELECT id, key, type, name, description, usage_notes, process_code
        FROM ui_components
        """
    ):
        comp_id = row["id"]
        if has_embedding("ui_components", comp_id, "component_description"):
            continue

        key = row["key"] or ""
        name = row["name"] or ""
        type_ = row["type"] or ""
        description = (row["description"] or "").strip()
        usage_notes = (row["usage_notes"] or "").strip()
        process_code = (row["process_code"] or "").strip()

        content = (
            f"Component {key} ({name}): "
            f"type={type_}. "
            f"Description={description}. "
            f"Usage={usage_notes}. "
            f"Process_code={process_code}"
        ).strip()

        if not content:
            continue

        vec = embed_text(content)
        cur.execute(
            """
            INSERT INTO embeddings (
                source_type, source_id,
                service_id, flow_id, step_id,
                content_type, content, tags, embedding
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "ui_components",
                comp_id,
                None,
                None,
                None,
                "component_description",
                content,
                None,
                json.dumps(vec),
            ),
        )
        created += 1

    conn.commit()

    total = cur.execute("SELECT COUNT(*) AS c FROM embeddings").fetchone()["c"]
    logger.info(
        "Embedding seeding complete: created %d new rows, total rows in embeddings=%d",
        created,
        total,
    )



def semantic_search_context_for_brd(
    conn: sqlite3.Connection,
    brd_text: str,
    top_k: int = 20,
) -> str:
    """
    Embedding vector search used by the 2nd agent (AI_Retrieve).

    Query: BRD text.
    Corpus: rows from `embeddings` with content_type in:
      - 'brd_summary'
      - 'guideline_summary'
      - 'flow_summary'
      - 'step_description'
      - 'component_description'

    Returns: compact, human-readable context string that is injected into the prompt.
    """
    query_vec = embed_text(brd_text)

    cur = conn.cursor()
    rows = cur.execute("""
        SELECT id, source_type, source_id, service_id, flow_id, step_id,
               content_type, content, embedding
        FROM embeddings
        WHERE content_type IN (
            'brd_summary', 'guideline_summary',
            'flow_summary', 'step_description', 'component_description'
        )
    """).fetchall()

    scored: List[Tuple[float, sqlite3.Row]] = []
    for r in rows:
        vec = json.loads(r["embedding"])
        score = cosine_similarity(query_vec, vec)
        scored.append((score, r))

    scored.sort(key=lambda x: x[0], reverse=True)
    scored = scored[:top_k]

    # Optional: enrich with slugs / names from base tables for readability
    lines: List[str] = []
    for score, r in scored:
        st = r["source_type"]
        sid = r["source_id"]
        prefix = ""
        if st == "documents":
            d = cur.execute(
                "SELECT doc_type, title FROM documents WHERE id=?", (sid,)
            ).fetchone()
            prefix = f"[DOC {d['doc_type']}:{d['title']}]"
        elif st == "flows":
            f = cur.execute(
                "SELECT slug, name FROM flows WHERE id=?", (sid,)
            ).fetchone()
            prefix = f"[FLOW {f['slug']}:{f['name']}]"
        elif st == "steps":
            s = cur.execute(
                "SELECT slug, name FROM steps WHERE id=?", (sid,)
            ).fetchone()
            prefix = f"[STEP {s['slug']}:{s['name']}]"
        elif st == "ui_components":
            c = cur.execute(
                "SELECT key, name FROM ui_components WHERE id=?", (sid,)
            ).fetchone()
            prefix = f"[COMP {c['key']}:{c['name']}]"
        else:
            prefix = f"[{st} id={sid}]"

        lines.append(f"{prefix} (similarity={score:.3f}) :: {r['content']}")

    return "\n".join(lines)


# ==========================
# OpenAI helper
# ==========================

def call_structured(
    system_prompt: str,
    user_prompt: str,
    model: str,
) -> Dict[str, Any]:
    """
    Call the LLM and parse its response as a plain JSON object (dict),
    without any Pydantic validation.
    """
    logger.info("Calling model=%s for structured JSON", model)

    resp = get_openai_client().chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.3,
        response_format={"type": "json_object"},
    )
    content = resp.choices[0].message.content or ""

    logger.debug("Raw model JSON (first 500 chars): %s", content[:500])

    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        debug_path = "debug_call_structured.json"
        with open(debug_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.error(
            "Failed to parse model output as JSON. Error: %s. Raw content saved to %s",
            e,
            debug_path,
        )
        raise RuntimeError(f"Failed to parse model output as JSON: {e}")



# ==========================
# Agents
# ==========================

def agent1_generate_bundle(brd: str) -> Dict[str, Any]:
    user_prompt = CLASSIFY_USER_PROMPT_TEMPLATE.format(brd=brd)
    return call_structured(
        system_prompt=CLASSIFY_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=OPENAI_MODEL_WORKFLOW,
    )


def agent2_normalize_with_retrieval(
    brd: str,
    candidate_bundle: Dict[str, Any],
    conn: sqlite3.Connection,
) -> Dict[str, Any]:
    """
    Agent 2: normalize flows using semantic retrieval over existing Diia data.
    """
    logger.info("Agent 2: building retrieval context for normalization")
    retrieval_context = semantic_search_context_for_brd(conn, brd_text=brd, top_k=20)
    logger.info(
        "Agent 2: retrieval context length: %d chars",
        len(retrieval_context or ""),
    )

    candidate_json = json.dumps(candidate_bundle, ensure_ascii=False, indent=2)

    user_prompt = RETRIEVE_USER_PROMPT_TEMPLATE.format(
        brd=brd,
        candidate_flows_json=candidate_json,
        retrieval_context=retrieval_context,
    )

    logger.info("Agent 2: calling model=%s for structured JSON", OPENAI_MODEL_WORKFLOW)
    result = call_structured(
        system_prompt=RETRIEVE_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=OPENAI_MODEL_WORKFLOW,
    )
    logger.info("Agent 2: normalization call finished")

    return result


def agent3_evaluate(
    normalized_bundle: Dict[str, Any],
    vector_similarity_context: str,
) -> Dict[str, Any]:
    norm_json = json.dumps(normalized_bundle, ensure_ascii=False, indent=2)

    user_prompt = EVAL_USER_PROMPT_TEMPLATE.format(
        normalized_flows_json=norm_json,
        vector_similarity_context=vector_similarity_context,
    )

    return call_structured(
        system_prompt=EVAL_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=OPENAI_MODEL_EVAL,
    )


# ==========================
# Agent 4 helpers – deterministic UI graph
# ==========================

def build_ui_graph(normalized_bundle: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build a deterministic UI graph from the normalized bundle:
      - nodes: 1 node per step (screen-level node)
      - edges: transitions between steps
      - mermaid: a single merged flowchart TD with all subgraphs
    This gives the frontend and Agent 4 a clean graph structure.
    """
    service = normalized_bundle.get("service", {})
    flows = normalized_bundle.get("flows", [])
    steps = normalized_bundle.get("steps", [])
    ui_components = normalized_bundle.get("ui_components", [])
    step_components = normalized_bundle.get("step_components", [])
    transitions = normalized_bundle.get("transitions", [])
    flows_mermaid = normalized_bundle.get("flows_mermaid", [])

    # --- indexes ---
    steps_by_slug: Dict[str, Dict[str, Any]] = {s["slug"]: s for s in steps}

    # ui_components may use "slug" (current) or "key" (older seed data)
    comps_by_key: Dict[str, Dict[str, Any]] = {}
    for c in ui_components:
        key = c.get("slug") or c.get("key")
        if not key:
            continue
        comp = dict(c)
        comp.setdefault("key", key)
        comps_by_key[key] = comp

    # map step_slug -> list of component objects with role
    step_to_components: Dict[str, List[Dict[str, Any]]] = {slug: [] for slug in steps_by_slug}

    for sc in step_components:
        step_slug = sc.get("step_slug")
        if step_slug not in steps_by_slug:
            continue

        comp_keys: List[str] = []
        if isinstance(sc.get("component_slugs"), list):
            comp_keys = sc["component_slugs"]
        elif sc.get("component_key"):
            comp_keys = [sc["component_key"]]

        for key in comp_keys:
            comp = comps_by_key.get(key, {"key": key, "name": key})
            step_to_components[step_slug].append(
                {
                    "key": comp.get("key", key),
                    "name": comp.get("name", key),
                    "description": comp.get("description", ""),
                    "role": sc.get("role", "primary"),
                }
            )

    # map step_slug -> which flows (via mermaid diagrams) reference its node
    step_to_flows: Dict[str, set] = {slug: set() for slug in steps_by_slug}

    for fm_str in flows_mermaid:
        try:
            fm = json.loads(fm_str)
            if not isinstance(fm, dict):
                continue
        except (json.JSONDecodeError, TypeError):
            continue

        flow_slug = fm.get("flow_slug")
        diagram = fm.get("mermaid_diagram") or ""
        if not flow_slug or not diagram:
            continue

        for slug, step in steps_by_slug.items():
            node_id = step.get("mermaid_node_id") or slug
            token = f"{node_id}["
            if token in diagram:
                step_to_flows[slug].add(flow_slug)

    # --- build nodes ---
    nodes: List[Dict[str, Any]] = []
    for slug, step in steps_by_slug.items():
        node_id = step.get("mermaid_node_id") or slug
        components = step_to_components.get(slug, [])
        flows_for_step = sorted(step_to_flows.get(slug, []))

        parts: List[str] = []
        if step.get("description"):
            parts.append(step["description"])

        if components:
            comp_lines = []
            for comp in components:
                line = f"- {comp.get('name')}: {comp.get('description', '').strip()}"
                comp_lines.append(line)
            parts.append("Компоненти екрану:\n" + "\n".join(comp_lines))

        if step.get("normalization_notes"):
            parts.append("Нотатки з нормалізації: " + step["normalization_notes"])

        full_description = "\n\n".join(p for p in parts if p)

        nodes.append(
            {
                "id": node_id,
                "step_slug": slug,
                "title": step.get("name", slug),
                "flows": flows_for_step,
                "description": full_description,
                "components": components,
            }
        )

    # --- build edges from transitions ---
    edges: List[Dict[str, Any]] = []
    for tr in transitions:
        from_slug = tr.get("from_step_slug")
        to_slug = tr.get("to_step_slug")
        if not from_slug or not to_slug:
            continue

        from_step = steps_by_slug.get(from_slug)
        to_step = steps_by_slug.get(to_slug)
        if not from_step or not to_step:
            continue

        edges.append(
            {
                "from": from_step.get("mermaid_node_id") or from_slug,
                "to": to_step.get("mermaid_node_id") or to_slug,
                "from_step_slug": from_slug,
                "to_step_slug": to_slug,
                "trigger": tr.get("trigger", ""),
                "condition": tr.get("condition", ""),
            }
        )

    # --- merge all Mermaid subgraphs into one global diagram ---
        # --- merge all Mermaid subgraphs into one global diagram ---
    subgraph_blocks: List[str] = []
    for fm in flows_mermaid:
        logger.info(f"[DEBUG] item in flows_mermaid: type={type(fm)}, value='{str(fm)[:100]}...'")
        diag = fm.get("mermaid_diagram") or ""
        if not diag:
            continue
        lines = diag.splitlines()
        # drop potential "flowchart ..." header lines
        lines_no_header = [ln for ln in lines if not ln.strip().startswith("flowchart ")]
        if lines_no_header:
            subgraph_blocks.append("\n".join(lines_no_header))

    if subgraph_blocks:
        # LLM already produced nice per-flow diagrams – merge them
        global_mermaid = "flowchart TD\n" + "\n".join(subgraph_blocks)
    else:
        # Fallback: deterministically build a simple diagram from nodes + edges
        lines: List[str] = ["flowchart TD"]

        # declare nodes: one per step
        for n in nodes:
            node_id = n["id"]
            title = n.get("title") or n.get("step_slug") or node_id
            safe_title = str(title).replace('"', '\\"')
            lines.append(f'{node_id}["{safe_title}"]')

        # declare edges: based on transitions
        for e in edges:
            from_id = e["from"]
            to_id = e["to"]
            label_parts: List[str] = []
            if e.get("trigger"):
                label_parts.append(str(e["trigger"]))
            if e.get("condition"):
                label_parts.append(str(e["condition"]))
            if label_parts:
                label = " | ".join(label_parts).replace('"', '\\"')
                lines.append(f"{from_id} -->|{label}| {to_id}")
            else:
                lines.append(f"{from_id} --> {to_id}")

        global_mermaid = "\n".join(lines)


    ui_graph: Dict[str, Any] = {
        "service": service,
        "flows": flows,
        "ui_components": list(comps_by_key.values()),
        "nodes": nodes,
        "edges": edges,
        "mermaid": global_mermaid,
    }
    return ui_graph


def agent4_generate_screen_spec(
    normalized_bundle: Dict[str, Any],
    ui_graph: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Agent 4: takes the normalized bundle + deterministic UI graph and
    asks the model to produce Diia-style screen specs.
    """
    normalized_json = json.dumps(normalized_bundle, ensure_ascii=False, indent=2)
    ui_graph_json = json.dumps(ui_graph, ensure_ascii=False, indent=2)

    user_prompt = SCREEN_SPEC_USER_PROMPT_TEMPLATE.format(
        normalized_json=normalized_json,
        ui_graph_json=ui_graph_json,
    )

    logger.info("Agent 4: calling model=%s for screen spec JSON", OPENAI_MODEL_WORKFLOW)
    result = call_structured(
        system_prompt=SCREEN_SPEC_SYSTEM_PROMPT,
        user_prompt=user_prompt,
        model=OPENAI_MODEL_WORKFLOW,
    )
    logger.info(
        "Agent 4: screen spec generated – screens: %d",
        len(result.get("screens", [])),
    )
    return result


# ==========================
# Public pipeline API
# ==========================
def run_yana_pipeline(brd_text: str) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    conn = get_db_connection(DB_PATH)
    conn.row_factory = sqlite3.Row

    # 0) Seed embeddings if missing
    logger.info("Ensuring base embeddings exist (documents/flows/steps/ui_components)")
    ensure_embeddings_for_all(conn)

    logger.info("Starting Yana pipeline for BRD (len=%d chars)", len(brd_text))

    # 1) Generate
    logger.info("Agent 1: generating candidate workflows")
    bundle = agent1_generate_bundle(brd_text)
    logger.info(
        "Agent 1: done – flows: %d, steps: %d",
        len(bundle.get("flows", [])),
        len(bundle.get("steps", [])),
    )

    # 2) Normalize – using semantic retrieval (inside Agent 2)
    logger.info("Agent 2: normalizing with retrieval")
    normalized_bundle = agent2_normalize_with_retrieval(brd_text, bundle, conn)
    logger.info(
        "Agent 2: done – normalized flows: %d",
        len(normalized_bundle.get("flows", [])),
    )

    # 3) Evaluation – also with retrieval context
    logger.info("Agent 3: evaluating workflows")
    vector_context = semantic_search_context_for_brd(conn, brd_text, top_k=30)
    logger.info(
        "Agent 3: vector context length: %d chars",
        len(vector_context or ""),
    )
    eval_result = agent3_evaluate(normalized_bundle, vector_context)
    logger.info(
        "Agent 3: done – workflows evaluated: %d",
        len(eval_result.get("workflows", [])),
    )

    return bundle, normalized_bundle, eval_result

def run_yana_pipeline_with_screens(
    brd_text: str,
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], Dict[str, Any]]:
    """
    Extended pipeline:
      Agent 1 -> Agent 2 -> Agent 3 -> Agent 4
    Returns:
      bundle, normalized_bundle, eval_result, final_screen_json
    """
    bundle, normalized_bundle, eval_result = run_yana_pipeline(brd_text)

    # Agent 4
    logger.info("Agent 4: building UI graph and screen spec")
    ui_graph = build_ui_graph(normalized_bundle)
    screen_spec = agent4_generate_screen_spec(normalized_bundle, ui_graph)

    final = {
        "service": normalized_bundle.get("service", {}),
        "ui_graph": ui_graph,
        "screen_flows": screen_spec.get("screen_flows", []),
        "screens": screen_spec.get("screens", []),
        "global_mermaid": ui_graph.get("mermaid", ""),
    }
    return bundle, normalized_bundle, eval_result, final


if __name__ == "__main__":
    import sys
    import json

    if sys.stdin.isatty():
        print("Paste BRD text and press Ctrl+D:")
    brd_input = sys.stdin.read().strip()
    if not brd_input:
        raise SystemExit("No BRD provided on stdin.")

    bundle, normalized, evaluation, screen_json = run_yana_pipeline_with_screens(brd_input)

    # 1) Still print everything to console (optional)
    print("\n=== Agent 1 – candidate bundle ===")
    print(json.dumps(bundle, indent=2, ensure_ascii=False))

    print("\n=== Agent 2 – normalized bundle ===")
    print(json.dumps(normalized, indent=2, ensure_ascii=False))

    print("\n=== Agent 3 – evaluation ===")
    print(json.dumps(evaluation, indent=2, ensure_ascii=False))

    print("\n=== Agent 4 – UI graph + screen spec ===")
    print(json.dumps(screen_json, indent=2, ensure_ascii=False))

    # 2) Save Agent 4 result into a txt file
    output_path = "yana_screen_spec.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(json.dumps(screen_json, indent=2, ensure_ascii=False))

    print(f"\n[INFO] Agent 4 output saved to {output_path}")
