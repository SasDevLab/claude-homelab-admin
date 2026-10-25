# claude-homelab-admin

A kit to run a home server with **Claude Code as its administrator**, not
as a consultant: one session always open on the machine, which does the
work and tells the owner afterwards, while the owner is mostly on the
phone.

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
| `skills/` | procedure skills: status, diagnosis, new service, end of session (in progress) |
| `scripts/` | sentinel and notifications (in progress) |
| `examples/` | `settings.json` wiring the hooks, `CLAUDE.example.md` (the template filled in for an invented house) |

## Install

From this folder, copy into your homelab project:

```sh
P=~/my-homelab                                     # your project folder
mkdir -p "$P/.claude"
cp -r agents hooks skills "$P/.claude/"
cp examples/settings.json "$P/.claude/settings.json"  # or merge it into yours
```

Then open Claude Code in `$P` and type `/homelab-init`. It measures what
it can, asks you the rest one question at a time (never a secret), and
shows the result before saving. Run it again to fill what you skipped.

Then edit the agents: the services named in them (Immich, Home Assistant,
n8n, Authelia, Caddy, Uptime Kuma) are an example stack. Drop the agents
you do not need and adapt the perimeters to yours.

Hook self-test: `python3 hooks/block-pkill-f.py --test`.

## Status

Being built in six steps: skeleton and agents (done), `CLAUDE.md` template and `/homelab-init` (done),
procedure skills, sentinel and guard, optional per-tool trap packs, final
check.
