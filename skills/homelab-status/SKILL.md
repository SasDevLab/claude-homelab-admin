---
name: homelab-status
description: How the homelab is doing, in one command. Use when asked "how is it going?", "all ok?", "news?", and BEFORE every intervention, to know whether something is working.
---

# How the homelab is doing

**One command answers, not ten.** Asking the system piece by piece turns a
one-screen answer into half an hour of exploring.

## Now

```bash
sudo -n bash <this skill's folder>/status.sh ${user_config.status_script}
```

Run it exactly so, with the argument: when the plugin option
`status_script` names the project's own script, `status.sh` hands over to
it, and that script sees what the built-in checks cannot.

It prints the real time, what is working, memory and swap, load,
temperature, disks, containers, and at the bottom **only what needs
attention**: containers down or unhealthy, failed systemd units, a disk
near full, memory pressure (swap half full *and* little RAM free). "Nothing needs attention." means there is
nothing else to look at.

**Without the permissions it needs, a status script lies**: a refused
`docker` call looks exactly like every container down. This one says "not
measured" instead; a script you write yourself must do the same.

## Before intervening

```bash
sudo -n bash <this skill's folder>/status.sh --busy ${user_config.status_script}
```

Exit 1 if something is working. **Something working → ask before
interrupting it. Nothing working → act, and tell the owner afterwards.**
Irreversible actions (deleting data, photos, backups) are asked
**always**, at any hour, with nobody on the system.

Out of the box it only sees systemd jobs running now (backups, copies),
**not** uploads or workflow runs: an agent trusting it could restart in the
middle of a job. Either set the plugin option `status_script` to your own
script (it must accept `--busy`; an absolute path, the script and its
folder owned by root and not writable by others), or add your applications
in the `busy()` function: uploads to the photo
library, running workflow executions, job queues. **A counter is read
twice, a few seconds apart**: one file that arrived is not an upload in
progress.
*Why root: `status.sh` runs that script with sudo, so a script your user
can edit is a way to root (SECURITY.md).*
*Why: a check that said "busy" for any upload in the last 15 minutes held
two restarts back because of a single test photo.*

Grow the script as the house grows: the monitor's Down list, the faults
your devices log today. Every check you run by hand twice belongs in it.

## How the house is made

Questions about **how it is made** (which service on which address, what
starts on its own, where the photos are) are answered by the generated
inventory documents named in `CLAUDE.md`, section "The generated
documents". Read them before going to discover things: they answer most
questions without running a command.

## When the answer is not there

Only then go down into the logs, searching rather than reading whole files:

- `logs/` in the project: every script's log;
- `docker logs <name> --since 30m`: one service;
- `journalctl -u <unit> --since -1h`: one systemd unit;
- `journalctl -k --since -1h`: the kernel (disks, USB, crashes).
