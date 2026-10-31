#!/usr/bin/env python3
"""PreToolUse hook (Bash): blocks `pkill -f <text>` (and `kill` with
`pgrep -f <text>`) when the text would also kill the command itself. The
shell that runs it has the whole command in its own command line, so
`pkill -f myapp` also kills `bash -c '... myapp ...'` and the tool call dies
with exit code 144. The square-bracket trick, `pkill -f '[m]yapp'`, matches
the same process but never matches itself.

One rule, no shell parser: every `pkill`/`pgrep` word in the command, also
inside quotes (bash -c, eval, su -c, sudo, heredocs), is checked by asking
whether its pattern matches the command text. Text that only mentions it (a
commit message) is blocked too: write `[m]yapp` there as well.
(`killall` matches process names, not command lines: it cannot hit the shell.)

Self-test: python3 block-pkill-f.py --test
"""
import json
import re
import shlex
import sys

# Option letters (and long options) that take a value as the next word.
VALUE = set("gGPstuUFOqrd") | {"--signal", "--pidfile", "--ns", "--nslist", "--cgroup",
                               "--euid", "--uid", "--group", "--pgroup", "--session",
                               "--terminal", "--parent", "--user", "--older", "--queue",
                               "--runstates", "--env", "--delimiter"}
SIGNAL = re.compile(r"-([0-9]+|[A-Z][A-Z0-9]+)")  # -9, -TERM, -HUP (-U, -P are options)


def options(words):
    """Option letters and free texts of the words after pkill/pgrep. A short
    cluster stops at the first letter that takes a value (-fu root, -uroot)."""
    letters, texts, skip = set(), [], False
    for w in words:
        if skip:
            skip = False
        elif w.startswith("--"):
            letters.add(w.split("=")[0])
            skip = "=" not in w and w in VALUE
        elif w.startswith("-") and len(w) > 1 and not SIGNAL.fullmatch(w):
            for j, ch in enumerate(w[1:]):
                letters.add(ch)
                if ch in VALUE:
                    skip = j == len(w) - 2  # value in the next word, or attached
                    break
        elif not w.startswith("-"):
            texts.append(w)
    return letters, texts


def matches_itself(p, cmd):
    """Would the regex p match the shell running cmd? Its command line holds cmd."""
    if re.search(r"\$[{\w(]", p):  # "$APP": the shell fills it in, we cannot know
        return True
    p = p.replace("\\<", "\\b").replace("\\>", "\\b")  # ERE word edges
    try:
        return re.search(p, cmd) is not None
    except re.error:  # not a Python regex: fall back to the bracket rule
        return "[" not in p


def pattern(cmd):
    """The first pkill/pgrep -f pattern that would match the command itself."""
    for m in re.finditer(r"(?<![\w.-])(pkill|pgrep)(?![\w.-])", cmd):
        if m.group(1) == "pgrep" and not re.search(r"(?<![\w.-])kill(?![\w.-])", cmd):
            continue  # pgrep only lists; it hurts only when its output is killed
        rest = re.split(r"[;&|)`\n]", cmd[m.end():], maxsplit=1)[0]
        try:
            words = shlex.split(rest)
        except ValueError:  # an open quote: it belongs to a string around us
            words = rest.split()
        letters, texts = options(words)
        full = "f" in letters or "--full" in letters
        safe = "A" in letters or "--ignore-ancestors" in letters
        if full and not safe and texts and matches_itself(texts[0], cmd):
            return texts[0]
    return None


def bracketed(p):
    """p with its first letter in brackets: same matches, never itself.
    Only for a plain pattern: inside an escape or a quantifier it would change the regex."""
    if not re.fullmatch(r"[\w .:/=-]+", p):
        return None
    m = re.search(r"[A-Za-z0-9]", p)
    return f"{p[:m.start()]}[{m.group()}]{p[m.end():]}" if m else None


def test():
    blocked = ["pkill -f myapp", "sudo -n pkill -f 'node server'", "pkill -u root -f myscript",
               "pkill -o -f myapp", "pkill -fu root myapp", "pkill -uroot -f myapp",
               "pkill -STOP -f myapp", "pkill -ALRM -f myapp", "pkill --signal TERM -f myapp",
               "echo x | pkill --full myapp", "ls #check\npkill -f myapp",
               "curl http://h/#x; pkill -f myapp", "sudo -u root pkill -f myapp",
               "timeout -s KILL 5 pkill -f myapp", "if pgrep -f '[m]yapp'; then pkill -f myapp; fi",
               "bash -c 'pkill -f myapp'", "bash -lc 'pkill -f myapp'", "echo `pkill -f myapp`",
               'out="$(pkill -f myapp)"', "sudo bash <<'EOF'\npkill -f myapp\nEOF",
               "eval \"pkill -f myapp\"", "su -c 'pkill -f myapp'", 'FOO="a b" pkill -f myapp',
               "kill $(pgrep -f myapp)", "sudo kill $(pgrep -f myapp)",
               "pgrep -f myapp | xargs -n 1 kill", "kill $(pgrep -u root -f myapp)",
               'APP=myapp; pkill -f "$APP"', "pkill -f 'myapp.*[0-9]'", "pkill -f '\\<myapp\\>'",
               "git commit -m 'stop pkill -f myapp'"]
    allowed = ["pkill -f '[m]yapp'", "pkill myapp", "pkill -u root -f '[m]yscript'",
               "pkill -fu root '[m]yapp'", "pkill -P 1234 -f '[m]yapp'", "pkill -O 60 -f '[m]yapp'",
               "pkill -A -f myapp", "kill $(pgrep -A -f myapp)", "pkill -f '^python app.py'",
               "kill $(pgrep -f '[m]yapp')", "pgrep -d ' ' -f '[m]yapp' | xargs kill",
               "pgrep -f myapp", "killall -r 'app.*'", "ls ~/pkill-notes.txt",
               "git commit -m 'block pkill -f [m]yapp'"]
    for c in blocked:
        assert pattern(c), c
    for c in allowed:
        assert pattern(c) is None, c
    assert bracketed("myapp") == "[m]yapp" and bracketed(".*foo") is None
    print(f"ok ({len(blocked)} blocked, {len(allowed)} allowed)")


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
        advice = f"Use square brackets: '{fix}'" if fix else \
            "Put one plain letter of the pattern in square brackets, as in '[m]yapp'"
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason":
                f"pkill/pgrep -f '{found}' also matches the shell that runs this command "
                f"(the text is in its command line), so it would kill itself. {advice}, "
                f"also when the command only mentions it (a commit message).",
        }}))
    sys.exit(0)
