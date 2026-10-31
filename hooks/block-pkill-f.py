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


# Options that take a value: short letters per command (for pkill -o is
# "oldest" and takes none), long names for both.
SHORT_VALUE = {"pkill": set("gGPstuUF"), "killall": set("suoyn")}
LONG_VALUE = {"--signal", "--pidfile", "--ns", "--nslist", "--cgroup", "--euid", "--uid",
              "--group", "--pgroup", "--session", "--terminal", "--parent", "--user",
              "--older-than", "--younger-than"}


def options(cmd, words):
    """Split the words after pkill/killall into option flags and free texts.
    The value of an option (`-u root`, `-fu root`, `-uroot`) is neither."""
    flags, texts, skip = [], [], False
    for r in words:
        if skip:
            skip = False
        elif r.startswith("--"):
            flags.append(r)
            skip = "=" not in r and r in LONG_VALUE
        elif r.startswith("-") and len(r) > 1:
            letters = r[1:]
            if re.fullmatch(r"[A-Z0-9]+", letters):  # a signal: -9, -TERM, -HUP
                flags.append(r)
                continue
            kept = ""
            for j, ch in enumerate(letters):
                kept += ch
                if ch in SHORT_VALUE[cmd]:
                    skip = j == len(letters) - 1  # value in the next word, or attached
                    break
            flags.append("-" + kept)
        else:
            texts.append(r)
    return flags, texts


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
        flags, texts = options("killall" if p.endswith("killall") else "pkill", words[i + 1:])
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
    assert pattern("pkill -u root -f '[m]yscript'") is None
    assert pattern("pkill -u root -f myscript") == "myscript"
    assert pattern("killall -u bob -r 'app.*'") == "app.*"
    assert pattern("pkill -o -f myapp") == "myapp"
    assert pattern("pkill -fu root myapp") == "myapp"
    assert pattern("pkill -uroot -f myapp") == "myapp"
    assert pattern("pkill -STOP -f myapp") == "myapp"
    assert pattern("pkill --signal TERM -f myapp") == "myapp"
    assert pattern("pkill -fu root '[m]yapp'") is None
    assert pattern("killall -o 1h -r 'app.*'") == "app.*"
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
