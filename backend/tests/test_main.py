"""Tests for the NUDGE action whitelist and token lifecycle.

These cover the things v1 got wrong: unbounded execution, unenforced expiry,
and replayable tokens.
"""

from datetime import datetime, timedelta, timezone

import pytest

from backend import main


@pytest.fixture(autouse=True)
def clear_sessions():
    main._sessions.clear()
    yield
    main._sessions.clear()


def _issue(actions, ttl_minutes=15):
    """Insert a session directly so tests don't call the LLM."""
    now = datetime.now(timezone.utc)
    token = "test-token"
    main._sessions[token] = {
        "task": "test task",
        "actions": actions,
        "created_at": now,
        "expires_at": now + timedelta(minutes=ttl_minutes),
        "used": False,
    }
    return token


# ---------------------------------------------------------------- whitelist
def test_disallowed_op_is_not_executed():
    token = _issue([{"op": "run_shell", "args": {"cmd": "rm -rf /"}}])
    result = main.run_agent(token)
    assert result["completed"] == []
    assert "disallowed op" in result["failed"]


def test_open_app_rejects_unlisted_application():
    with pytest.raises(ValueError, match="not allowed"):
        main._op_open_app("powershell")


def test_press_key_rejects_arbitrary_keys():
    with pytest.raises(ValueError, match="not allowed"):
        main._op_press_key("f4")


def test_hotkey_rejects_long_combinations():
    with pytest.raises(ValueError, match="not allowed"):
        main._op_hotkey(["ctrl", "alt", "shift", "delete"])


def test_type_text_rejects_oversized_input():
    with pytest.raises(ValueError, match="2000"):
        main._op_type_text("x" * 2001)


def test_wait_is_bounded():
    with pytest.raises(ValueError, match="between 0 and 5"):
        main._op_wait(3600)


# ---------------------------------------------------------------- tokens
def test_unknown_token_is_rejected():
    with pytest.raises(main.HTTPException) as exc:
        main.run_agent("nope")
    assert exc.value.status_code == 404


def test_token_cannot_be_replayed():
    token = _issue([{"op": "wait", "args": {"seconds": 0.01}}])
    main.run_agent(token)
    with pytest.raises(main.HTTPException) as exc:
        main.run_agent(token)
    assert exc.value.status_code == 409


def test_expired_token_is_rejected():
    token = _issue([{"op": "wait", "args": {"seconds": 0.01}}], ttl_minutes=-1)
    with pytest.raises(main.HTTPException) as exc:
        main.run_agent(token)
    assert exc.value.status_code == 410


def test_token_is_burned_before_execution():
    token = _issue([{"op": "wait", "args": {"seconds": 0.01}}])
    main.run_agent(token)
    assert main._sessions[token]["used"] is True


# ---------------------------------------------------------------- source audit
def test_source_contains_no_dynamic_execution():
    import ast
    import pathlib

    tree = ast.parse(pathlib.Path(main.__file__).read_text())
    calls = [
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id in {"exec", "eval", "compile", "__import__"}
    ]
    assert calls == []
