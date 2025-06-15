from fastapi import FastAPI
from pydantic import BaseModel
import os
import requests
import json
from requests.auth import HTTPBasicAuth
from dotenv import load_dotenv
import traceback
import re

# Load environment variables
load_dotenv()

app = FastAPI()

# Environment variables
TOGETHER_API_KEY = os.getenv("TOGETHER_API_KEY")
JIRA_BASE_URL = os.getenv("JIRA_BASE_URL")
JIRA_EMAIL = os.getenv("JIRA_EMAIL")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")

# Jira auth and headers
JIRA_AUTH = HTTPBasicAuth(JIRA_EMAIL, JIRA_API_TOKEN)
JIRA_HEADERS = {
    "Accept": "application/json",
    "Content-Type": "application/json"
}
TOGETHER_API_URL = "https://api.together.xyz/v1/chat/completions"

class GenerateRequest(BaseModel):
    issue_key: str
    user_story: str

def is_subtask(issue_key):
    """Check if the Jira issue is a sub-task."""
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    response = requests.get(url, headers=JIRA_HEADERS, auth=JIRA_AUTH)
    if response.status_code != 200:
        raise Exception(f"Failed to fetch issue details for {issue_key}")
    return response.json()["fields"]["issuetype"]["subtask"]

def generate_test_cases(user_story):
    """Generate test cases from the user story using Together API."""
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
    return response.json()['choices'][0]['message']['content'].strip()

def update_jira_field(issue_key, test_cases_text):
    """Update Jira custom field with ADF-formatted test cases."""
    paragraphs = test_cases_text.strip().split('\n')
    adf_content = {
        "type": "doc",
        "version": 1,
        "content": []
    }

    for para in paragraphs:
        if para.strip():
            adf_content["content"].append({
                "type": "paragraph",
                "content": [{
                    "type": "text",
                    "text": para.strip()
                }]
            })

    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    payload = {
        "fields": {
            "customfield_10169": adf_content
        }
    }

    response = requests.put(
        url,
        headers=JIRA_HEADERS,
        auth=JIRA_AUTH,
        json=payload
    )

    if response.status_code != 204:
        raise Exception(f"Failed to update test cases in Jira: {response.status_code} - {response.text}")

def create_subtask(parent_key: str, summary: str, description: str):
    """Create a sub-task in Jira under the given parent issue."""
    payload = {
        "fields": {
            "project": {
                "key": parent_key.split("-")[0]
            },
            "parent": {
                "key": parent_key
            },
            "summary": summary,
            "description": {
                "type": "doc",
                "version": 1,
                "content": [{
                    "type": "paragraph",
                    "content": [{
                        "type": "text",
                        "text": description
                    }]
                }]
            },
            "issuetype": {
                "name": "Sub-task"
            }
        }
    }

    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    response = requests.post(url, headers=JIRA_HEADERS, auth=JIRA_AUTH, json=payload)

    if response.status_code not in (200, 201):
        print("Sub-task creation failed with:", response.status_code, response.text)  # Log for debug
        raise Exception(f"Failed to create sub-task: {response.status_code} - {response.text}")
    
    return response.json()["key"]

def split_test_cases(raw_text):
    """Split generated test case text into individual cases."""
    cases = re.split(r'\*\*Test Case \d+.*\*\*', raw_text)[1:]  # remove intro text
    titles = re.findall(r'\*\*(Test Case \d+.*?)\*\*', raw_text)

    result = []
    for title, body in zip(titles, cases):
        result.append({
            "title": title.strip(),
            "body": body.strip()
        })
    return result

@app.post("/generate")
def generate(request: GenerateRequest):
    try:
        if is_subtask(request.issue_key):
            return {
                "error": f"Cannot update test cases for {request.issue_key} because it is a sub-task. Use a parent Story or Task."
            }

        # Step 1: Generate test cases via Together API
        test_cases_text = generate_test_cases(request.user_story)

        # Step 2: Update Jira custom field
        update_jira_field(request.issue_key, test_cases_text)

        # Step 3: Split and create as sub-tasks
        test_cases = split_test_cases(test_cases_text)
        created_subtasks = []
        for case in test_cases:
            subtask_key = create_subtask(request.issue_key, case['title'], case['body'])
            created_subtasks.append(subtask_key)

        return {
            "message": f"{len(created_subtasks)} sub-tasks created under {request.issue_key}, and test cases saved to 'Generated Test Cases' field.",
            "subtasks": created_subtasks,
            "preview": test_cases_text[:300] + "..."
        }

    except Exception as e:
        print(traceback.format_exc())
        return {"error": str(e)}
