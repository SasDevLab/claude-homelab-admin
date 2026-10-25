#!/usr/bin/env python3
"""PreToolUse hook (Bash): blocks `pkill -f <text>` (and `killall -r`) when the
text would also kill the command itself. The shell that runs it has that text
in its own command line, so `pkill -f myapp` also kills `bash -c '... myapp ...'`
and the tool call dies with exit code 144. The square-bracket trick,
`pkill -f '[m]yapp'`, matches the same process but never matches itself.

Self-test: python3 block-pkill-f.py --test
"""
import json
import re
import shlex
import sys


def pattern(cmd):
    """The first text searched by pkill -f / killall -r without square brackets."""
    # Quote-aware split: a `;` inside a string does not separate commands.
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    try:
        tokens = list(lex)
    except ValueError:
        return None
    pieces, cur = [], []
    for t in tokens:
        if t and set(t) <= set(";&|()"):
            pieces.append(cur)
            cur = []
        else:
            cur.append(t)
    pieces.append(cur)
    for words in pieces:
        # pkill counts only as a command: first word, or after sudo/env/timeout.
        # Inside a string (commit message, echo) it is not a command.
        i = 0
        while i < len(words) and (words[i] in ("sudo", "-n", "env", "timeout", "nice")
                                  or re.fullmatch(r"\w+=\S*|\d+[smh]?", words[i])):
            i += 1
        if i >= len(words):
            continue
        p = words[i]
        if p.rsplit("/", 1)[-1] not in ("pkill", "killall"):
            continue
        rest = words[i + 1:]
        flags = [r for r in rest if r.startswith("-")]
        texts = [r for r in rest if not r.startswith("-")]
        full = any("f" in f.lstrip("-") and not f.startswith("--") for f in flags) or "--full" in flags
        regex = p.endswith("killall") and any(f in ("-r", "--regexp") for f in flags)
        if (full or regex) and texts and "[" not in texts[0]:
            return texts[0]
    return None


def test():
    assert pattern("pkill -f myapp") == "myapp"
    assert pattern("sudo -n pkill -f 'node server'") == "node server"
    assert pattern("ls; killall -r 'app.*'") == "app.*"
    assert pattern("pkill -f '[m]yapp'") is None
    assert pattern("pkill myapp") is None
    assert pattern("git commit -m 'stop pkill -f myapp'") is None
    assert pattern("echo x | pkill --full myapp") == "myapp"
    print("ok")


if __name__ == "__main__":
    if sys.argv[1:] == ["--test"]:
        test()
        sys.exit(0)
    try:
        cmd = json.load(sys.stdin).get("tool_input", {}).get("command", "")
    except Exception:
        sys.exit(0)
    found = pattern(cmd)
    if found:
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason":
                f"pkill -f '{found}' also kills the shell that runs it (that text is in its "
                f"command line). Use square brackets: pkill -f '[{found[0]}]{found[1:]}'.",
        }}))
