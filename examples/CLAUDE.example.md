# Example: the template filled in

This is how the placeholder parts of `CLAUDE.md` look once filled in, for an
invented house. Only the sections with placeholders are shown; the rest of
the template stays as it is.

---

## The project

A small server at home at **close to zero cost**: home automation and
family services (photos, documents, automations). An old laptop, 8 GB of
RAM, Debian 13 since March. A mini PC with more RAM is being considered.

- Machine: ThinkPad T440, 8 GB, Debian 13, since 2026-03-01.
- **Memory threshold for heavy jobs: 1500 MB free** (`free -m`). Below it,
  an agent does not start a heavy job: it reports the number.
- Owner: Anna. Other people in the house: Marco (photos, the alarm
  buttons), the kids (nothing).

## When to act and when to ask

2. **Whether something is working**: uploads to Immich in the last 15
   minutes, running n8n executions, Immich job queues, the nightly backup
   (the `homelab-status` skill).

**What tends to be refused, and the road that passes** (from this house):

- Reading the GitHub token from the old Windows disk → `gh auth login` with
  the code from `github.com/login/device`, typed by Anna on the phone.
- A new site on `:8443` in Caddy → Anna pastes `printf '...' | sudo tee -a
  /srv/caddy/Caddyfile` and `docker compose restart` over SSH.

**There are two lock-out risks**: the machine losing its way out to the
internet and the machine rebooting. After a reboot the session comes back
by itself (`assistant.service`, a user unit with lingering, in tmux):
tested once, back in two minutes; the MCP servers need `/mcp reconnect
all`.

## Sentinel alerts

A monitor (Uptime Kuma) is watched by `sentinel.timer` every minute. ...
The `guard` agent reports in the Telegram group "Home admin", topic
"System".

## The owner's rules

- **Automations live in n8n**, not in scattered scripts.
- **Telegram is the channel for everything** said to Anna, in the group
  "Home admin" (topics: System, Photos, Reminders). Things for Marco go to
  the group "Home". One bot has **one reader** (`telegram-listener`): never
  a second one.
- **The shutters never go below 20%** (the cat sleeps on the sill).
- **Downloaded models are not deleted** until Anna says so.

## Sub-agents

- **Before handing over, check the agent has what it needs**: the
  credential in the vault (`sudo -n vault-read --list`).
- Secrets are read into a variable and never appear in your answer:
  `TOKEN=$(sudo -n vault-read "Immich - API key")` (8 seconds).

**Prefer an MCP server to the raw API when there is one**: `n8n` and
`homeassistant`. After a reboot they can stay disconnected: Anna writes
`/mcp reconnect all`, which works remotely.

## Where things are

- **The compose files that run are in `/srv/<service>/`**, and `docker
  compose` is launched from there. `homelab/services/` is a copy.

## The generated documents

`INVENTORY.md` and `AUTOMATIONS.md`, regenerated with `sudo -n systemctl
start snapshot-inventory.service`, and every morning at 07:30 anyway.
