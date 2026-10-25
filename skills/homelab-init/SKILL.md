---
name: homelab-init
description: Writes the homelab's CLAUDE.md from the kit's template - measures what can be measured on the machine, asks the owner the rest one question at a time, shows the result before saving. Run it once after installing the kit, and again to fill what was left open.
disable-model-invocation: true
---

# homelab-init

You are writing the `CLAUDE.md` of this homelab project from the template
`CLAUDE.template.md`, which sits in this skill's base directory. Its blanks
are written `{{like this}}`; the text inside says what goes there.

Rules for the whole run:

- **Read only, until the owner says "save".** No installs, no restarts,
  no file written before step 5.
- **Measure before asking.** A question comes with what you measured as
  the proposed answer: "I see 7.6 GB of RAM and Debian 13. Right?"
- **One question per message**, in plain words. The owner is probably on a
  phone.
- **Never ask for a secret** and never print one. For the vault, ask for
  the *command* that lists entries and the one that prints one entry. You
  may run the listing (names only); you never run the one that prints.
- **No guessing.** A blank the owner skips stays `{{...}}`, as it is.

## 1. Where you start

- `CLAUDE.md` absent in the project root → start from the template.
- `CLAUDE.md` present with `{{` in it → it is a run left halfway: fill
  only the blanks still there.
- `CLAUDE.md` present without `{{` → it is someone's own file. Do not
  overwrite it: ask whether to write `CLAUDE.homelab.md` beside it, and
  stop if the answer is no.

Say in one line how many blanks there are (`grep -o '{{' <file> | wc -l`;
if the command is refused, say "not counted" rather than counting by eye)
and that you will measure first.

## 2. Measure

Each in its own command, so a failure stays readable:

| blank | measure |
|---|---|
| machine | `hostnamectl`, `free -m`, `nproc`, `df -h /` |
| memory threshold | proposal: about 20% of total RAM, rounded to 100 MB |
| what can be "working" | `docker ps --format '{{.Names}}'` (photo library, workflow engine, backup containers) and `systemctl list-timers` |
| monitor | a container named like `uptime-kuma` |
| compose path | `docker compose ls -a` (the CONFIG FILES column) |
| MCP servers | `claude mcp list` |
| workflow engine, chat app | containers and timers above (n8n, Node-RED; a Telegram or Matrix bot) |
| session after reboot | `systemctl --user list-unit-files`, `loginctl show-user $USER -p Linger` |

`docker` may need `sudo -n`; if it is refused, say so and ask instead.
Write what you measured in a scratch list: you will need it in step 3.

## 3. Ask

In this order, skipping what step 2 already settled beyond doubt:

1. What the server is for, in one sentence, and since when.
2. The owner's name, and who else in the house uses what.
3. The memory threshold: your proposal, yes or a number.
4. Which chat, group and topic get the system messages.
5. The vault: the command that lists entries, the one that prints one.
   Run the listing once and report only how many entries it showed.
6. How the session comes back after a reboot, and whether it was tested.
   "Not set up" is a fine answer: write it as it is.
7. The owner's own rules (the template has the kind). Read the template's
   list and ask, for each, keep / drop / change. Then: "any rule of
   yours I should add, with its reason?"
8. The names of the two generated documents and the command that
   regenerates them. If there is none yet, propose `INVENTORY.md` and
   `AUTOMATIONS.md` and leave the command as a blank.

## 4. Fill

Copy the template and replace each blank with its answer, in the
template's voice: short sentences, the reason after the rule. Keep every
"Why" line. Delete the HTML comment at the top only when no `{{` is left.
Rules the owner dropped are deleted, not commented out.

## 5. Show, then save

Send the owner the filled sections only (not the whole file), and the
count of blanks still open. Save when they say so. Then check:

- `grep -o '{{' CLAUDE.md | wc -l`: the number you announced;
- the five section titles the agents cite are there, once each:
  `grep -c -E '^## (The roles|When to act and when to ask|Sentinel alerts|Sub-agents|How to work)$' CLAUDE.md`
  gives 5.

End with one line: saved, how many blanks are left, and that running
`/homelab-init` again fills only those.
