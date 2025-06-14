from fastapi import FastAPI
from pydantic import BaseModel
import os, requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()
app = FastAPI()

# Load environment variables
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
JIRA_AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)

TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"

JIRA_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}

class GenerateRequest(BaseModel):
    issue_key: str
    user_story: str

def is_subtask(issue_key):
    """Check if the given Jira issue is a sub-task."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    response = requests.get(url, headers=JIRA_HEADERS, auth=JIRA_AUTH)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch issue details for {issue_key}")
    return response.json()["fields"]["issuetype"]["subtask"]

def generate_test_cases(user_story):
    payload = {
        "model": "mistralai/Mistral-7B-Instruct-v0.2",
        "messages": [
            {"role": "system", "content": "You are a QA expert generating test cases."},
            {"role": "user", "content": f"Generate 5 functional, 3 negative, and 2 edge test cases for this user story: {user_story}"}
        ],
        "temperature": 0.7,
        "max_tokens": 500,
        "top_p": 0.9
    }

    response = requests.post(
        TOGETHER_API_URL,
        headers={
            "Authorization": f"Bearer {TOGETHER_API_KEY}",
            "Content-Type": "application/json"
        },
        json=payload
    )
    response.raise_for_status()
    return [tc.strip() for tc in response.json()['choices'][0]['message']['content'].split('\n') if tc.strip()]

def create_subtask(parent_key, summary, description):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": parent_key.split('-')[0]},
            "parent": {"key": parent_key},
            "summary": summary[:50],
            "description": description,
            "issuetype": {"name": "Sub-task"}
        }
    }

    response = requests.post(
        f"{JIRA_BASE_URL}/rest/api/3/issue",
        headers=headers,
        data=json.dumps(payload),
        auth=(JIRA_EMAIL, JIRA_API_TOKEN)
    )


    if response.status_code != 201:
        print("Subtask creation failed")
        print("Status Code:", response.status_code)
        print("Response:", response.text)  # Add this to inspect the problem
        raise Exception(f"Failed to create subtask for {parent_key}")

    return f"{JIRA_BASE_URL}/browse/{response.json()['key']}"

@app.post("/generate")
def generate(request: GenerateRequest):
    try:
        if is_subtask(request.issue_key):
            return {"error": f"Cannot generate sub-tasks under {request.issue_key} because it is already a sub-task. Use a main issue like a Story or Task."}

        test_cases = generate_test_cases(request.user_story)
        links = [create_subtask(request.issue_key, tc, tc) for tc in test_cases]

        return {
            "message": f"{len(links)} test cases created under {request.issue_key}",
            "links": links
        }
    except Exception as e:
        return {"error": str(e)}
