"""
NUDGE — natural-language desktop automation.

SECURITY MODEL
--------------
v1 executed model-generated Python via exec() from an unauthenticated GET
endpoint with open CORS. That is remote code execution by design: any party
holding (or guessing) an 8-character token could run arbitrary code on the
host, and a GET meant a link preview or crawler could fire it.

v2 removes exec entirely. The model no longer emits code — it emits a list of
declarative actions drawn from a fixed vocabulary. A dispatcher validates every
action against ALLOWED_OPS and its argument schema before running it. Anything
outside the vocabulary is rejected, not executed.

Other hardening in v2:
  * execution moved from GET to POST (no preview/crawler triggering)
  * tokens carry a real expiry that is actually enforced
  * tokens are 32 bytes of secrets.token_urlsafe, not uuid4()[:8]
  * CORS restricted to an allowlist from the environment
  * every issue / execute / reject is written to an audit log
"""

from __future__ import annotations

import json
import logging
import os
import secrets
import subprocess
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import pyautogui
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from pydantic import BaseModel, Field

load_dotenv()

# ---------------------------------------------------------------- logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    handlers=[logging.FileHandler("nudge_audit.log"), logging.StreamHandler()],
)
audit = logging.getLogger("nudge.audit")

# ---------------------------------------------------------------- config
TOKEN_TTL = timedelta(minutes=int(os.getenv("NUDGE_TOKEN_TTL_MINUTES", "15")))
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv("NUDGE_ALLOWED_ORIGINS", "http://localhost:5173").split(",") if o.strip()
]
# Applications the LLM is permitted to launch. Anything else is rejected.
ALLOWED_APPS = {
    "notepad": ["notepad.exe"],
    "calculator": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "browser": ["cmd", "/c", "start", "msedge"],
}

app = FastAPI(title="NUDGE", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

client = Groq(api_key=os.getenv("GROQ_API_KEY"))
_sessions: dict[str, dict[str, Any]] = {}


# ---------------------------------------------------------------- models
class TaskRequest(BaseModel):
    task: str = Field(min_length=1, max_length=500)


class Action(BaseModel):
    op: str
    args: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- the whitelist
def _op_open_app(app_name: str) -> str:
    key = str(app_name).lower().strip()
    if key not in ALLOWED_APPS:
        raise ValueError(f"application not allowed: {app_name!r}")
    subprocess.Popen(ALLOWED_APPS[key], shell=False)
    return f"opened {key}"


def _op_type_text(text: str) -> str:
    text = str(text)
    if len(text) > 2000:
        raise ValueError("text exceeds 2000 characters")
    pyautogui.typewrite(text, interval=0.01)
    return f"typed {len(text)} characters"


def _op_press_key(key: str) -> str:
    key = str(key).lower().strip()
    if key not in {"enter", "tab", "esc", "space", "backspace", "up", "down", "left", "right"}:
        raise ValueError(f"key not allowed: {key!r}")
    pyautogui.press(key)
    return f"pressed {key}"


def _op_hotkey(keys: list[str]) -> str:
    allowed = {"ctrl", "alt", "shift", "win", "a", "c", "v", "s", "z", "n", "o", "w"}
    keys = [str(k).lower().strip() for k in keys]
    if not keys or len(keys) > 3 or any(k not in allowed for k in keys):
        raise ValueError(f"hotkey combination not allowed: {keys!r}")
    pyautogui.hotkey(*keys)
    return f"hotkey {'+'.join(keys)}"


def _op_wait(seconds: float) -> str:
    seconds = float(seconds)
    if not 0 < seconds <= 5:
        raise ValueError("wait must be between 0 and 5 seconds")
    time.sleep(seconds)
    return f"waited {seconds}s"


ALLOWED_OPS = {
    "open_app": _op_open_app,
    "type_text": _op_type_text,
    "press_key": _op_press_key,
    "hotkey": _op_hotkey,
    "wait": _op_wait,
}

SYSTEM_PROMPT = f"""You convert a plain-English Windows task into a list of actions.

Return ONLY a JSON object, no prose and no code fences:
{{"task": "<restated task>", "actions": [{{"op": "...", "args": {{...}}}}]}}

The ONLY permitted ops are:
  open_app   args: {{"app_name": one of {sorted(ALLOWED_APPS)}}}
  type_text  args: {{"text": string, max 2000 chars}}
  press_key  args: {{"key": enter|tab|esc|space|backspace|up|down|left|right}}
  hotkey     args: {{"keys": [1-3 of ctrl,alt,shift,win,a,c,v,s,z,n,o,w]}}
  wait       args: {{"seconds": 0 < n <= 5}}

Never emit code. Never emit an op outside this list. If the task cannot be
expressed with these ops, return {{"task": "...", "actions": []}}."""


# ---------------------------------------------------------------- endpoints
@app.post("/create-agent", status_code=status.HTTP_201_CREATED)
def create_agent(request: TaskRequest) -> dict[str, Any]:
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": request.task},
        ],
        response_format={"type": "json_object"},
    )

    try:
        plan = json.loads(response.choices[0].message.content)
        actions = [Action(**a) for a in plan.get("actions", [])]
    except (json.JSONDecodeError, TypeError, ValueError) as exc:
        audit.warning("plan_parse_failed task=%r error=%s", request.task, exc)
        raise HTTPException(422, "Model returned an unusable plan") from exc

    # Validate the whole plan before issuing a token. Fail closed.
    unknown = [a.op for a in actions if a.op not in ALLOWED_OPS]
    if unknown:
        audit.warning("plan_rejected task=%r disallowed_ops=%s", request.task, unknown)
        raise HTTPException(422, f"Plan contained disallowed operations: {unknown}")

    token = secrets.token_urlsafe(32)
    now = datetime.now(timezone.utc)
    _sessions[token] = {
        "task": request.task,
        "actions": [a.model_dump() for a in actions],
        "created_at": now,
        "expires_at": now + TOKEN_TTL,
        "used": False,
    }
    audit.info("token_issued token=%s… task=%r actions=%d", token[:8], request.task, len(actions))

    return {
        "token": token,
        "actions": [a.model_dump() for a in actions],
        "expires_at": (now + TOKEN_TTL).isoformat(),
    }


@app.post("/run/{token}")
def run_agent(token: str) -> dict[str, Any]:
    session = _sessions.get(token)
    if session is None:
        audit.warning("run_rejected reason=unknown_token token=%s…", token[:8])
        raise HTTPException(404, "Link is invalid or has expired")

    if session["used"]:
        audit.warning("run_rejected reason=replay token=%s…", token[:8])
        raise HTTPException(409, "This link has already been used")

    # Expiry is enforced here. v1 advertised 15 minutes and never checked.
    if datetime.now(timezone.utc) > session["expires_at"]:
        _sessions.pop(token, None)
        audit.warning("run_rejected reason=expired token=%s…", token[:8])
        raise HTTPException(410, "This link has expired")

    session["used"] = True  # burn before running, so a crash cannot be retried

    results, failed = [], None
    for action in session["actions"]:
        handler = ALLOWED_OPS.get(action["op"])
        if handler is None:  # defence in depth; create-agent already filtered
            failed = f"disallowed op {action['op']}"
            break
        try:
            results.append(handler(**action["args"]))
        except (ValueError, TypeError) as exc:
            failed = f"{action['op']}: {exc}"
            break

    audit.info(
        "run_complete token=%s… task=%r completed=%d failed=%s",
        token[:8], session["task"], len(results), failed,
    )
    return {"task": session["task"], "completed": results, "failed": failed}


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": app.version}
