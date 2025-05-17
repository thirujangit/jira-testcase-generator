import os
from flask import Flask, request, jsonify, render_template
import requests
from requests.auth import HTTPBasicAuth

app = Flask(__name__)

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
    return response.json()['choices'][0]['message']['content']

def create_subtask(parent_key, summary, description):
    url = f"{JIRA_BASE_URL}/rest/api/3/issue"
    payload = {
        "fields": {
            "project": {"key": parent_key.split('-')[0]},
            "parent": {"key": parent_key},
            "summary": summary,
            "description": description,
            "issuetype": {"name": "Sub-task"}
        }
    }

    response = requests.post(url, json=payload, headers=JIRA_HEADERS, auth=JIRA_AUTH)
    response.raise_for_status()
    return response.json()

@app.route('/generate', methods=['POST'])
def generate():
    data = request.json
    issue_key = data.get('issue_key')
    user_story = data.get('user_story')

    if not issue_key or not user_story:
        return jsonify({"error": "Missing issue_key or user_story"}), 400

    try:
        test_cases_text = generate_test_cases(user_story)
        test_cases = [tc.strip() for tc in test_cases_text.split('\n') if tc.strip()]
        for tc in test_cases:
            create_subtask(issue_key, tc[:50], tc)

        return jsonify({"message": "Test cases added as subtasks", "count": len(test_cases)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/panel')
def panel():
    issue_key = request.args.get("issueKey")
    return render_template("panel.html", issue_key=issue_key)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port, debug=True)
