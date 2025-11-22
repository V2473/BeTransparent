from flask import Flask, request
from flask_cors import cross_origin
# from dia import prompt_query

application = Flask(__name__)

from codemie_sdk import CodeMieClient
from codemie_sdk.models.assistant import AssistantChatRequest
import re


def prompt_query(query: str):

    client = CodeMieClient(
        auth_server_url="https://keycloak.eks-core.aws.main.edp.projects.epam.com/auth",
        username="",
        password="",
        auth_client_id="codemie-sdk",
        auth_realm_name="codemie-prod",
        codemie_api_domain="https://codemie.lab.epam.com/code-assistant-api",
    )


    # llm_models = client.llms.list()
    # print(llm_models)

    assistants = client.assistants.list(
        minimal_response=True,  # Return minimal assistant info
        scope="visible_to_user",  # or "created_by_user"
        page=0,
        per_page=12,
        filters={"key": "value"}  # Optional filters
    )

    # print(assistants)


    assistant = client.assistants.get("58998463-93a5-4c8e-a9dd-c02d4008a25d")
    # print(assistant)


    chat_request = AssistantChatRequest(
        text=query,
        stream=False,  # Set to True for streaming response
        propagate_headers=True,  # Enable propagation of X-* headers to MCP servers
    )
    # Pass X-* headers to forward to MCP servers
    response = client.assistants.chat(
        "58998463-93a5-4c8e-a9dd-c02d4008a25d",
        chat_request,
        headers={
            "X-Tenant-ID": "tenant-abc-123",
            "X-User-ID": "user-456",
            "X-Request-ID": "req-123",
        },
    )

    print('response_json.generated')


    def clean_llm_json_response(response_text):
        """
        Cleans an LLM response to extract a potential JSON string.
        Removes common markdown formatting and extracts the content within curly braces.
        """
        # Remove markdown code block delimiters (```json, ```)
        cleaned_text = response_text.replace('```json', '').replace('```', '').strip()

        # Attempt to find the first occurrence of a JSON-like structure (starts and ends with curly braces)
        # This regex is a simple heuristic and might need adjustment based on LLM output patterns.
        match = re.search(r'\{.*\}', cleaned_text, re.DOTALL)
        if match:
            return match.group(0)
        return cleaned_text

    jsonresp = clean_llm_json_response(response.generated)

    # print(jsonresp)

    chathtml_request = AssistantChatRequest(
        text=jsonresp,
        stream=False,  # Set to True for streaming response
        propagate_headers=True,  # Enable propagation of X-* headers to MCP servers
    )
    # Pass X-* headers to forward to MCP servers
    response_html = client.assistants.chat(
        "3d57d2b9-5a89-40fc-96da-cee486894f00",
        chathtml_request,
        headers={
            "X-Tenant-ID": "tenant-abc-123",
            "X-User-ID": "user-456",
            "X-Request-ID": "req-123",
        },
    )

    html_report = clean_llm_json_response(response_html.generated)

    # print(html_report)
    print(" HTML report generated")

    # with open('extracted_data.csv', 'w') as file:
    #         file.write(html_report)
    #         print(f"File 'extracted_data.csv' overwritten successfully.")

    parts = [s[7:] for s in html_report.split("~~~\n\n")]
    parts[-1] = parts[-1][:-3]
    parts = "\n\n".join(parts)
    print(parts)
    return parts

@application.route("/")
def hello_world():
    return "Welcome"

@application.route("/status")
def status():
    return "OK"

@application.route("/api/search")
@cross_origin()
def search():
    name = request.args.get('query', '112')
    if name=='112': return "Default response for query null."

    result = prompt_query(name)
    return str(result)
        
if __name__ == '__main__':
    application.run(host='0.0.0.0', port=8000)