# claude-homelab-admin

Agents, skills and hooks that make Claude Code the **proactive
administrator** of a home server. One session stays open on the machine:
it measures, fixes and reports, instead of suggesting. With Claude Code's
Remote Control (`claude --remote-control`) the owner calls on it from
anywhere, from a phone, a browser or another computer. And a sentinel
wakes it by itself when a service goes down.

It comes from a real homelab (an old 8 GB laptop running home automation,
family photos, documents and automations), run this way every day. Every
rule here exists because something went wrong without it. The kit keeps
the rule and its reason, and drops the house's own data.

## The idea

- **A coordinator and its agents.** The main session plans, talks with the
  owner, takes the irreversible decisions and commits. The work is done by
  sub-agents, each with its own perimeter: a cheap read-only probe to
  measure, specialists to change things.
- **When to act and when to ask.** If nothing is working, act and report
  afterwards: a service restart kills nothing. If something is working
  (an upload, a backup, a running workflow), ask first. Anything
  irreversible is always asked, with the names of what goes.
- **Measure.** A check not run is not a check. A coincidence is not a
  cause. "It's not there" is measured before it is said.
- **Hooks for the rules that a written rule did not hold.** When the same
  mistake came back despite the rule, it became a hook that speaks at the
  moment of the command.

## What is in it

| folder | what |
|---|---|
| `agents/` | 8 sub-agents: `probe`, `scout` (read-only), `system`, `guard`, `infra-security`, `n8n-agent`, `hass-agent`, `media-storage` |
| `hooks/` | 3 PreToolUse hooks: `block-pkill-f.py` (a `pkill -f` that would kill its own shell), `delegate-reminder.sh` (the coordinator doing an agent's job), `model-weight-reminder.sh` (a model too heavy for the host) |
| `skills/homelab-init/` | `/homelab-init`: writes your `CLAUDE.md` (the coordinator's rules, each with its reason) from `CLAUDE.template.md`, measuring the machine and asking you the rest |
| `skills/homelab-notify/` | `/homelab-notify`: shows or switches where alerts go (Telegram, ntfy, Discord, Slack, email, Apprise), `/homelab-notify test` sends one |
| `skills/` | procedure skills: `homelab-status` (one command for the whole picture, with `status.sh`), `homelab-diagnosis` (the order that finds the real fault), `homelab-new-service` (the pieces before "done"), `homelab-end-session` (lessons filed before `/clear`) |
| `scripts/` | `sentinel.sh` (wakes the session on a monitor Down) and `notify.sh` (messages to the owner's chat), set up in one `sentinel.env` |
| `systemd/` | `sentinel.service` and `sentinel.timer`, to edit and install |
| `packs/` | optional trap packs, one skill per tool: `homelab-n8n` (n8n 2.x workflows, Code nodes, Telegram, a local model via Ollama), `homelab-host` (systemd, Docker, sudo, reboots, the session restarting itself, MCP servers, long commands) |
| `examples/` | `settings.json` wiring the hooks, `CLAUDE.example.md` (the template filled in for an invented house) |

## Install

As a Claude Code plugin (2.1.275 or later), from your homelab project:

```
/plugin install homelab-admin --marketplace SasDevLab/claude-homelab-admin
```

This brings the agents (`homelab-admin:guard`, ...), the skills
(`/homelab-admin:homelab-init`, ...) and the hooks. To try it without
installing: `claude --plugin-dir <kit folder>`.

Or copy it into the project, if you want to edit the agents in place:

```sh
P=~/my-homelab                                     # your project folder
mkdir -p "$P/.claude"
cp -r agents hooks skills "$P/.claude/"
cp examples/settings.json "$P/.claude/settings.json"  # or merge it into yours
```

The optional packs are copied by hand either way, for the tools you run:

```sh
mkdir -p "$P/.claude/skills"
cp -r packs/homelab-n8n packs/homelab-host "$P/.claude/skills/"
```

The `n8n-agent` and `system` agents open them when they are there.

Then open Claude Code in `$P` and run `/homelab-init`
(`/homelab-admin:homelab-init` from the plugin). It measures what it can,
asks you the rest one question at a time (never a secret), and shows the
result before saving. Run it again to fill what you skipped.

Then look at the agents: the services named in them (Immich, Home
Assistant, n8n, Authelia, Caddy, Uptime Kuma) are an example stack. With
the copy, drop the agents you do not need and adapt the perimeters to
yours; with the plugin, your `CLAUDE.md` says which ones you use.

Hook self-test: `python3 hooks/block-pkill-f.py --test`.

## The sentinel

The session cannot watch anything while it waits for you. A timer can:

```
Uptime Kuma Down ──> sentinel.sh (every minute) ──> claude -p: ListAgents + SendMessage
script alert ──> notify.sh ──> queue ──┘                      │
                                                              v
        owner's chat <── notify.sh <── guard agent <── your session
```

- `sentinel.sh` reads Kuma's SQLite database (read only) for new Downs,
  and the queue that `notify.sh` fills for messages on the system topic.
  A throwaway `claude -p` (haiku, a few seconds) delivers them to the
  newest local session whose name starts with `SESSION_PREFIX`, as
  `MONITOR ALERT (sentinel) - <service> Down: <error>` or
  `SYSTEM ALERT (sentinel): <text>`. Your `CLAUDE.md` tells the session to
  hand them to `guard`.
- No session answers? It tells the chat that nobody is acting on it.
- Your own scripts alert with `notify.sh <topic> "<text>"`, or
  `. notify.sh` and `notify <topic> "<text>"`. Only the system topic wakes
  the session.

Setup (as the user who runs Claude Code):

```sh
cd "$P/.claude"
cp -r <kit>/scripts <kit>/systemd .
cp scripts/sentinel.env.example scripts/sentinel.env   # fill it in, or run /homelab-notify
NOTIFY=0 scripts/notify.sh 4 "test"           # dry run: prints, sends nothing
scripts/sentinel.sh --dry-run --from 1        # prints every past Down it would send
scripts/sentinel.sh                           # first real run: saves where it starts
# edit User= and ExecStart= in systemd/sentinel.service, then:
sudo cp systemd/sentinel.* /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now sentinel.timer
```

State, queue and log go to `logs/` next to `scripts/`. Kuma on MariaDB is
not supported: the script reads SQLite with `sqlite3` inside the container.

## License

MIT, see `LICENSE`.
