import os
import sys
import json
import logging

from flask import Flask, request
from flask_cors import cross_origin
from openai import OpenAI

# Make sure we can import yana_pipeline from the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from yana_pipeline import run_yana_pipeline  # noqa: E402

# Flask app (keeps the same WSGI entry name)
app = Flask(__name__)

logger = logging.getLogger("yana_server")
logging.basicConfig(level=logging.INFO)

# Single OpenAI client (reuses the same API key as yana_pipeline)
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ==========================
# UI Agent (hardcoded system prompt)
# ==========================

UI_SYSTEM_PROMPT = """## Instructions
You are a UI expert specializing in mobile screen development with Tailwind CSS. Generate clean, responsive HTML code for mobile screens, following the style and structure of Framelink Figma MCP Server references. Use the input JSON for data and layout. You will have multiple JSON, for each create a separate Tailwind HTML.

## Steps to Follow
1. Analyze the description, JSON specification, and MCP Figma reference provided by the user.
2. Extract required layout, UI components, and styling cues from both the JSON and the design reference.
3. Transform these requirements into pixel-perfect, mobile-first HTML using Tailwind CSS classes, maintaining fidelity to MCP Figma design.
4. Output only the completed Tailwind HTML code—no additional commentary.
5. You will have multiple JSON, for each create a separate Tailwind HTML.

## Constraints
- Only generate HTML; do not provide explanations or extra text.
- Ensure mobile responsiveness and proper use of Tailwind CSS classes.
- Accurately map JSON data and design references to UI elements.
- Assume Figma design details are provided or referenced by the user.
- frame width 360px maximum
- The language of APP is Ukrainian
- background color is #E2ECF4
- inner item background color is white
- buttons is black with white color text
- frame inner padding is 8px
- buttons rounded-2xl
- do not use img
- response only files, no additional information
- Every screen is a separate file
- Instead of min-h-screen use min-h-[680px]
"""


def clean_html_response(text: str) -> str:
    """
    Strip common markdown fences so the frontend gets plain HTML only.
    """
    if not text:
        return ""
    cleaned = text.replace("```html", "").replace("```", "").strip()
    return cleaned


def generate_ui_from_normalized_bundle(normalized_bundle: dict) -> str:
    """
    Second agent: takes normalized workflow JSON and returns Tailwind HTML screens.
    """
    json_payload = json.dumps(normalized_bundle, ensure_ascii=False, indent=2)

    resp = client.chat.completions.create(
        model="gpt-4.1",
        messages=[
            {"role": "system", "content": UI_SYSTEM_PROMPT},
            {"role": "user", "content": json_payload},
        ],
        temperature=0.2,
    )
    content = resp.choices[0].message.content or ""
    html = clean_html_response(content)
    return html


def prompt_query(query: str) -> str:
    """
    End-to-end pipeline for the API:
    1) Run Yana pipeline (replaces the original 'first agent').
    2) Feed normalized bundle JSON into the hardcoded UI agent.
    3) Return plain HTML (all screens) as string.
    """
    logger.info("Starting Yana pipeline for query='%s'", query)

    # run_yana_pipeline returns: (candidate_bundle, normalized_bundle, evaluation)
    bundle, normalized_bundle, evaluation = run_yana_pipeline(query)

    logger.info(
        "Yana pipeline finished – flows: %d (normalized: %d)",
        len(bundle.get("flows", [])),
        len(normalized_bundle.get("flows", [])),
    )

    logger.info("Calling UI agent to generate Tailwind HTML screens")
    html_output = generate_ui_from_normalized_bundle(normalized_bundle)
    logger.info("UI agent finished – HTML length=%d", len(html_output))

    return html_output


# ==========================
# Routes (kept identical)
# ==========================

@app.route("/")
def hello_world():
    return "Welcome"


@app.route("/status")
def status():
    return "OK"


@app.route("/api/search")
@cross_origin()
def search():
    # Query param stays the same as before
    name = request.args.get("query", "112")
    if name == "112":
        return "Default response for query null."

    result = prompt_query(name)
    # Frontend previously received a string, keep that behavior
    return str(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
