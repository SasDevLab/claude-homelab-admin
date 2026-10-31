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
# Commands that run the next word as a command, and the short option letters
# (or long options) that take a value as the next word.
WRAPPERS = {"sudo": set("ugCDhprtU"), "doas": set("uC"), "timeout": {"s", "k", "--signal", "--kill-after"},
            "nice": {"n"}, "ionice": set("cnp"), "env": {"u", "C"}, "nohup": set(), "exec": {"a"},
            "time": set(), "command": set(), "setsid": set(), "stdbuf": set("ioe"),
            "watch": {"n"}, "xargs": set("nIPLdaEs")}
SHELLS = {"bash", "sh", "dash", "zsh"}  # `bash -c '<code>'`: the code is read too
# Shell keywords a command can follow: `then pkill`, `do pkill`, `{ pkill`, `! pkill`.
KEYWORDS = {"if", "then", "else", "elif", "do", "while", "until", "{", "!"}


def value_next(o, takes):
    """True if option o wants its value in the next word. A short cluster
    (-fu, -iu) stops at the first letter that takes a value: if that letter
    ends the cluster the value is the next word, otherwise it is attached
    (-uroot, -c3)."""
    if o.startswith("--"):
        return "=" not in o and o in takes
    for j, ch in enumerate(o[1:]):
        if ch in takes:
            return j == len(o) - 2
    return False


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
            while i < len(words) and words[i].startswith("-") and words[i] != "-":
                i += 2 if value_next(words[i], takes) else 1
        elif re.fullmatch(r"\w+=\S*|\d+(\.\d+)?[smhd]?", w):  # env VAR=x, timeout 5
            i += 1
        else:
            return i
    return i


def pattern(cmd):
    """The first text searched by pkill -f that can match the shell running it."""
    # Quote-aware split: a `;` inside a string does not separate commands.
    # commenters="": a `#` (in a URL, a comment) must not hide what follows.
    # A heredoc body is text written somewhere, not commands.
    code = re.sub(r"<<-?\s*(['\"]?)(\w+)\1[^\n]*\n.*?\n\s*\2\s*(?=\n|$)", "", cmd, flags=re.S)
    # Backticks and $( start a command too.
    code = code.replace("\n", " ; ").replace("`", " ; ").replace("$(", " ; ")
    lex = shlex.shlex(code, posix=True, punctuation_chars=";&|()")
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
        # "$(pkill ...)" inside double quotes stays one word: read what is in it.
        for w in words:
            if " ; " in w:
                found = pattern(w.replace(" ; ", "\n"))
                if found:
                    return found
        # pkill counts only as a command, not inside a string (commit message, echo).
        i = command_start(words)
        if i >= len(words):
            continue
        name = words[i].rsplit("/", 1)[-1]
        c = next((k for k in range(i + 1, min(i + 3, len(words)))
                  if re.fullmatch(r"-[a-z]*c[a-z]*", words[k])), None)  # -c, -lc, -ec
        if name in SHELLS and c is not None:
            inner = words[c + 1:c + 2]
            found = pattern(inner[0]) if inner else None
            if found:
                return found
            continue
        if name != "pkill":
            continue
        flags, texts = options(words[i + 1:])
        full = any("f" in f.lstrip("-") and not f.startswith("--") for f in flags) or "--full" in flags
        if full and texts and matches_itself(texts[0], cmd):
            return texts[0]
    return None


def matches_itself(p, cmd):
    """Would pkill's regex p match the shell running cmd? Its command line holds cmd."""
    if re.search(r"\$[{\w]", p):  # "$APP": the shell fills it in, we cannot know: block
        return True
    p = p.replace("\\<", "\\b").replace("\\>", "\\b")  # ERE word edges
    try:
        return re.search(p, cmd) is not None
    except re.error:  # not a Python regex: fall back to the bracket rule
        return "[" not in p


def bracketed(p):
    """p with its first letter in brackets: same matches, never itself.
    Only for a plain pattern: inside an escape or a quantifier it would change the regex."""
    if not re.fullmatch(r"[\w .:/=-]+", p):
        return None
    m = re.search(r"[A-Za-z0-9]", p)
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
    assert bracketed(".*foo") is None
    assert bracketed("\\bmyapp") is None
    assert bracketed("my app") == "[m]y app"
    assert pattern("watch -d pkill -f myapp") == "myapp"
    assert pattern("bash -c 'pkill -f myapp'") == "myapp"
    assert pattern("echo `pkill -f myapp`") == "myapp"
    assert pattern("x=$(pkill -f myapp)") == "myapp"
    assert pattern("sudo -iu root pkill -f myapp") == "myapp"
    assert pattern("exec -a x pkill -f myapp") == "myapp"
    assert pattern("setsid pkill -f myapp") == "myapp"
    assert pattern("doas pkill -f myapp") == "myapp"
    assert pattern("stdbuf -oL pkill -f myapp") == "myapp"
    assert pattern("ionice -c3 pkill -f myapp") == "myapp"
    assert pattern("pkill -f 'myapp.*[0-9]'") == "myapp.*[0-9]"
    assert pattern("pkill -f 'myap[p]'") is None
    assert pattern("sudo -uroot pkill -f myapp") == "myapp"
    assert pattern('out="$(pkill -f myapp)"') == "myapp"
    assert pattern('echo "`pkill -f myapp`"') == "myapp"
    assert pattern("bash -lc 'pkill -f myapp'") == "myapp"
    assert pattern("cat > r.sh <<'EOF'\npkill -f myapp\nEOF") is None
    assert pattern("cat > r.sh <<EOF\npkill -f myapp\nEOF\npkill -f other") == "other"
    assert pattern('APP=myapp; pkill -f "$APP"') == "$APP"
    assert pattern("pkill -f '\\<myapp\\>'") == "\\<myapp\\>"
    assert pattern("git commit -m \"stop pkill -f myapp\"") is None
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
