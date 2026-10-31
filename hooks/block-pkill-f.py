#!/usr/bin/env python3
"""PreToolUse hook (Bash): blocks `pkill -f <text>` when the text would also
kill the command itself. The shell that runs it has that text in its own
command line, so `pkill -f myapp` also kills `bash -c '... myapp ...'` and
the tool call dies with exit code 144. The square-bracket trick,
`pkill -f '[m]yapp'`, matches the same process but never matches itself.
(`killall` matches process names, not command lines: it cannot hit the shell.)

Self-test: python3 block-pkill-f.py --test
"""
import json
import re
import shlex
import sys

# pkill options that take a value: short letters, and long names.
SHORT_VALUE = set("gGPstuUF")
LONG_VALUE = {"--signal", "--pidfile", "--ns", "--nslist", "--cgroup", "--euid", "--uid",
              "--group", "--pgroup", "--session", "--terminal", "--parent", "--user"}
# Commands that run the next word as a command, and their options that take a value.
WRAPPERS = {"sudo": {"-u", "-g", "-C", "-D", "-h", "-p", "-r", "-t", "-U"},
            "timeout": {"-s", "-k", "--signal", "--kill-after"},
            "nice": {"-n"}, "env": {"-u", "-C", "-S"}, "nohup": set(), "exec": set(),
            "time": set(), "command": set(), "watch": {"-n", "-d"},
            "xargs": {"-n", "-I", "-P", "-L", "-d", "-a", "-E", "-s"}}
# Shell keywords a command can follow: `then pkill`, `do pkill`, `{ pkill`, `! pkill`.
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "{", "!"}


def options(words):
    """Split the words after pkill into option flags and free texts.
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
            if re.fullmatch(r"[0-9]+|[A-Z][A-Z0-9]+", letters):  # a signal: -9, -TERM, -HUP (-U, -P are options)
                flags.append(r)
                continue
            kept = ""
            for j, ch in enumerate(letters):
                kept += ch
                if ch in SHORT_VALUE:
                    skip = j == len(letters) - 1  # value in the next word, or attached
                    break
            flags.append("-" + kept)
        else:
            texts.append(r)
    return flags, texts


def command_start(words):
    """Index of the real command after wrappers (sudo -u root, timeout -s KILL 5, env A=b)."""
    i = 0
    while i < len(words):
        w = words[i]
        if w in KEYWORDS:
            i += 1
        elif w in WRAPPERS:
            takes, i = WRAPPERS[w], i + 1
            while i < len(words) and words[i].startswith("-"):
                i += 2 if words[i] in takes else 1
        elif re.fullmatch(r"\w+=\S*|\d+(\.\d+)?[smhd]?", w):  # env VAR=x, timeout 5
            i += 1
        else:
            return i
    return i


def pattern(cmd):
    """The first text searched by pkill -f that can match the shell running it."""
    # Quote-aware split: a `;` inside a string does not separate commands.
    # commenters="": a `#` (in a URL, a comment) must not hide what follows.
    lex = shlex.shlex(cmd.replace("\n", " ; "), posix=True, punctuation_chars=";&|()")
    lex.whitespace_split = True
    lex.commenters = ""
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
        # pkill counts only as a command, not inside a string (commit message, echo).
        i = command_start(words)
        if i >= len(words) or words[i].rsplit("/", 1)[-1] != "pkill":
            continue
        flags, texts = options(words[i + 1:])
        full = any("f" in f.lstrip("-") and not f.startswith("--") for f in flags) or "--full" in flags
        # Brackets already there, or anchored at the start (the shell's line starts with its own name).
        if full and texts and "[" not in texts[0] and not texts[0].startswith("^"):
            return texts[0]
    return None


def bracketed(p):
    """p with its first letter or digit in brackets: same matches, never itself."""
    m = re.search(r"(?<!\\)[A-Za-z0-9]", p)
    return f"{p[:m.start()]}[{m.group()}]{p[m.end():]}" if m else None


def test():
    assert pattern("pkill -f myapp") == "myapp"
    assert pattern("sudo -n pkill -f 'node server'") == "node server"
    assert pattern("pkill -f '[m]yapp'") is None
    assert pattern("pkill myapp") is None
    assert pattern("pkill -u root -f '[m]yscript'") is None
    assert pattern("pkill -u root -f myscript") == "myscript"
    assert pattern("pkill -o -f myapp") == "myapp"
    assert pattern("pkill -fu root myapp") == "myapp"
    assert pattern("pkill -uroot -f myapp") == "myapp"
    assert pattern("pkill -STOP -f myapp") == "myapp"
    assert pattern("pkill --signal TERM -f myapp") == "myapp"
    assert pattern("pkill -fu root '[m]yapp'") is None
    assert pattern("git commit -m 'stop pkill -f myapp'") is None
    assert pattern("echo x | pkill --full myapp") == "myapp"
    assert pattern("ls #check\npkill -f myapp") == "myapp"
    assert pattern("curl http://h/#x; pkill -f myapp") == "myapp"
    assert pattern("sudo -u root pkill -f myapp") == "myapp"
    assert pattern("timeout -s KILL 5 pkill -f myapp") == "myapp"
    assert pattern("pkill -f '^python app.py'") is None
    assert pattern("killall -r 'app.*'") is None
    assert bracketed("myapp") == "[m]yapp"
    assert bracketed(".*foo") == ".*[f]oo"
    assert bracketed("\\bmyapp") == "\\b[m]yapp"
    assert pattern("pkill -U root -f myapp") == "myapp"
    assert pattern("pkill -P 1234 -f '[m]yapp'") is None
    assert pattern("pkill -F /run/x.pid -f myapp") == "myapp"
    assert pattern("if pgrep -f '[m]yapp'; then pkill -f myapp; fi") == "myapp"
    assert pattern("for p in a; do pkill -f myapp; done") == "myapp"
    assert pattern("{ pkill -f myapp; }") == "myapp"
    assert pattern("time pkill -f myapp") == "myapp"
    assert pattern("echo x | xargs -r pkill -f myapp") == "myapp"
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
        fix = bracketed(found)
        advice = f"Use square brackets: pkill -f '{fix}'." if fix else \
            "Put one letter of the pattern in square brackets, as in '[m]yapp'."
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason":
                f"pkill -f '{found}' also kills the shell that runs it (that text is in its "
                f"command line). {advice}",
        }}))
    sys.exit(0)
