#!/usr/bin/env python3
"""PreToolUse hook (all tools): counts what the coordinator does without an
agent in between. Every Nth tool call it adds a delegation reminder; the
second image read is denied. Launching any agent resets both counts.
Why: a coordinator on an expensive model read a dozen images itself despite
the written rule, and the Bash-only reminder cannot see image reads.
Thresholds: plugin options delegate_calls (default 10) and delegate_images
(default 2; 0 = image block off). Any error: exit 0, silent.

Self-test: python3 delegate-counter.py --self-test
"""
import json
import os
import re
import subprocess
import sys
import tempfile

IMG = (".png", ".jpg", ".jpeg", ".gif", ".webp")
DENY = ("DELEGATION: second image read by the coordinator without an agent in "
        "between. Hand image work (photos, comparisons, camera rounds) to a cheap "
        "agent (haiku) with a written brief. Launching any agent resets this count.")


def num(name, default):
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def run(data):
    """Returns the hook output dict, or None."""
    if "agent_id" in data:
        return None
    sid = re.sub(r"[^A-Za-z0-9_-]", "", str(data.get("session_id", ""))) or "none"
    d = os.environ.get("CLAUDE_PLUGIN_DATA") or tempfile.gettempdir()
    path = os.path.join(d, "delegate-counter-%s.json" % sid)
    try:
        with open(path) as f:
            st = json.load(f)
    except (OSError, ValueError):
        st = {}
    calls, images = int(st.get("calls", 0)), int(st.get("images", 0))
    tool = data.get("tool_name", "")
    out = None
    if tool in ("Agent", "Task", "SendMessage"):
        calls = images = 0
    else:
        fp = str((data.get("tool_input") or {}).get("file_path", "")).lower()
        limit = num("CLAUDE_PLUGIN_OPTION_DELEGATE_IMAGES", 2)
        if tool == "Read" and fp.endswith(IMG) and limit > 0:
            if images + 1 >= limit:
                out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                       "permissionDecision": "deny", "permissionDecisionReason": DENY}}
            else:
                images += 1
        else:
            calls += 1
            n = max(1, num("CLAUDE_PLUGIN_OPTION_DELEGATE_CALLS", 10))
            if calls % n == 0:
                out = {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                       "additionalContext": "DELEGATION REMINDER: %d tool calls in a row by the "
                       "coordinator without an agent. If this is execution, not a decision, stop "
                       "and write a brief for an agent on a cheaper model." % calls}}
    with open(path, "w") as f:
        json.dump({"calls": calls, "images": images}, f)
    return out


def main():
    try:
        out = run(json.load(sys.stdin))
        if out:
            print(json.dumps(out))
    except Exception:
        pass  # never break the session
    sys.exit(0)


def self_test():
    me = os.path.abspath(__file__)
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, CLAUDE_PLUGIN_DATA=d)
        for k in ("CLAUDE_PLUGIN_OPTION_DELEGATE_CALLS", "CLAUDE_PLUGIN_OPTION_DELEGATE_IMAGES"):
            env.pop(k, None)

        def call(raw, **extra):
            if not isinstance(raw, str):
                raw = json.dumps(dict({"session_id": "s/1"}, **raw))
            p = subprocess.run([sys.executable, me], input=raw, capture_output=True,
                               text=True, env=env)
            assert p.returncode == 0, p
            return p.stdout.strip()
        img = {"tool_name": "Read", "tool_input": {"file_path": "/x/A.PNG"}}
        gen = {"tool_name": "Bash", "tool_input": {"command": "ls"}}
        assert call(dict(img, agent_id="a")) == "" and call(dict(gen, agent_id="a")) == ""
        assert call(img) == ""
        assert "deny" in call(img) and "deny" in call(img)
        assert call({"tool_name": "Agent"}) == "" and call(img) == ""
        outs = [call(gen) for _ in range(10)]  # +0 from image: images counted apart
        assert all(o == "" for o in outs[:9]) and "REMINDER" in outs[9], outs
        assert call("{broken") == ""
    print("self-test ok")


if __name__ == "__main__":
    self_test() if "--self-test" in sys.argv else main()
