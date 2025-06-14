from fastapi import FastAPI, Request
from pydantic import BaseModel
import os, requests
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# Load env vars
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

# Pydantic request model
class GenerateRequest(BaseModel):
    issue_key: str
    user_story: str

# AI test case generation
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

# Jira subtask creation
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

    response = requests.post(url, json=payload, headers=JIRA_HEADERS, auth=JIRA_AUTH)
    response.raise_for_status()
    return f"{JIRA_BASE_URL}/browse/{response.json()['key']}"

# FastAPI POST endpoint
@app.post("/generate")
def generate(request: GenerateRequest):
    try:
        test_cases = generate_test_cases(request.user_story)
        links = [create_subtask(request.issue_key, tc, tc) for tc in test_cases]
        return {
            "message": f"{len(links)} test cases created as subtasks for {request.issue_key}",
            "links": links
        }
    except Exception as e:
        return {"error": str(e)}
