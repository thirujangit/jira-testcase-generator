function generate(issueKey) {
    document.getElementById("status").innerText = "Generating test cases...";
    fetch("https://jira-testcase-generator.onrender.com/generate", {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            issue_key: issueKey,
            user_story: "Placeholder, to be replaced with dynamic value or fetched via API"
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.message) {
            document.getElementById("status").innerText = data.message;
        } else {
            document.getElementById("status").innerText = "Error: " + (data.error || "Unknown error");
        }
    })
    .catch(err => {
        document.getElementById("status").innerText = "Failed to call API";
        console.error(err);
    });
}
