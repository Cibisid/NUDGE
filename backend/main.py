from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from groq import Groq
import uuid
import os
import json
import subprocess
import pyautogui
import time
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
client = Groq(api_key=os.getenv("GROQ_API_KEY"))

# Temporary in-memory store
agent_sessions = {}

class TaskRequest(BaseModel):
    task: str

@app.post("/create-agent")
def create_agent(request: TaskRequest):
    prompt = f"""
    A user wants to automate this task on Windows: "{request.task}"
    
    Generate a Python automation script using pyautogui that accomplishes this task.
    Return ONLY a JSON object like this, nothing else:
    {{
        "task": "{request.task}",
        "steps": ["step 1 description", "step 2 description"],
        "script": "import pyautogui\\nimport time\\n# your code here"
    }}
    Use pyautogui for mouse/keyboard automation.
    Use subprocess to open applications.
    Make the script safe and simple.
    """

    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}]
    )
    
    content = response.choices[0].message.content
    
    # Clean up response
    content = content.strip()
    if content.startswith("```json"):
        content = content[7:]
    if content.startswith("```"):
        content = content[3:]
    if content.endswith("```"):
        content = content[:-3]
    content = content.strip()
    
    agent_data = json.loads(content)
    token = str(uuid.uuid4())[:8]
    agent_sessions[token] = agent_data

    return {
        "link": f"http://localhost:8000/run/{token}",
        "token": token,
        "expires_in": "15 minutes"
    }

@app.get("/run/{token}", response_class=HTMLResponse)
def run_agent(token: str):
    if token not in agent_sessions:
        return HTMLResponse("<h1>Link expired or invalid</h1>")
    
    agent_data = agent_sessions[token]
    script = agent_data["script"]
    task = agent_data["task"]
    steps = agent_data["steps"]
    
    # Run the script
    try:
        exec(script, {"pyautogui": pyautogui, "time": time, "subprocess": subprocess, "os": os})
        status = "✅ Task completed successfully!"
    except Exception as e:
        status = f"❌ Error: {str(e)}"
    
    steps_html = "".join([f"<li>{step}</li>" for step in steps])
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>AgentLink</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 600px; margin: 40px auto; padding: 20px; background: #f5f5f5; }}
            h1 {{ color: #333; }}
            .status {{ background: white; padding: 20px; border-radius: 10px; margin: 20px 0; font-size: 20px; }}
            .steps {{ background: white; padding: 20px; border-radius: 10px; }}
            li {{ margin: 10px 0; font-size: 16px; }}
        </style>
    </head>
    <body>
        <h1>🤖 AgentLink</h1>
        <h2>Task: {task}</h2>
        <div class="status">{status}</div>
        <div class="steps">
            <h3>Steps executed:</h3>
            <ol>{steps_html}</ol>
        </div>
    </body>
    </html>
    """
    return HTMLResponse(html)