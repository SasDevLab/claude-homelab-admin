---
name: homelab-notify
description: Shows or changes where the homelab's alerts go (Telegram, ntfy, Discord, Slack, email, or any Apprise channel), and sends a test. `/homelab-notify` shows the channel, `/homelab-notify <channel>` switches to it, `/homelab-notify test` sends one real message.
disable-model-invocation: true
argument-hint: "[telegram|ntfy|discord|slack|email|apprise|test]"
---

# homelab-notify

Argument: `$ARGUMENTS` (empty, a channel name, or `test`).

Alerts go out through `notify.sh`, set up in `sentinel.env`. Both sit in
the project's `.claude/scripts/`, next to `sentinel.sh`: a copy, so a
plugin update leaves the settings alone. The channel is `NOTIFY_VIA`.

Rules for the whole run:

- **Never ask for a secret, never print one, never run a `*_CMD`.** A
  setting ending in `_CMD` is a command that prints a secret: ask *where*
  the secret is (a file path, a vault entry name) and write the command.
  Only `notify.sh` runs it. The commands themselves are not secret: you
  may show them.
- **One question per message**, in plain words. The owner may be on a phone.
- **Nothing written before the owner says yes** to the lines you show.
- **A real message is announced first, with its exact text**, and sent
  only when the owner asks for it.

## 1. Find the settings

`ls .claude/scripts/notify.sh .claude/scripts/sentinel.env` from the
project root (one `ls` per file if one is missing).

- `notify.sh` missing → the scripts are not copied yet. The kit root is
  two levels above this skill's base directory. Propose
  `mkdir -p .claude && cp -r <kit>/scripts .claude/` and wait for yes.
- `sentinel.env` missing → propose copying `sentinel.env.example` to it,
  and wait for yes.

Read the channel and which of its settings are filled:
`grep -E '^[A-Z_]+=' .claude/scripts/sentinel.env`. No `NOTIFY_VIA`
means `telegram`.

## 2. No argument: show

One line: the channel, and the settings it needs that are empty. Then ask
whether to switch, listing the six channels with one line each:

| channel | what the owner needs |
|---|---|
| `telegram` | a bot (BotFather) and the chat id; topics work |
| `ntfy` | the ntfy app and a long random topic; no account |
| `discord` | a channel webhook (Channel settings > Integrations > Webhooks) |
| `slack` | an app with Incoming Webhooks |
| `email` | an SMTP server, user and password (Gmail: an app password) |
| `apprise` | any other channel; Apprise installed in a venv |

Stop there. Switching is step 3.

## 3. A channel: switch

Measure before asking: a container named like `ntfy`, `apprise`, a mail
relay (`ss -ltn` on 25 or 587), a Telegram bot already in the chat app.
Then ask, one per message, only what is empty for that channel. The
settings, as `sentinel.env.example` names them:

- `telegram`: `TELEGRAM_CHAT_ID`, `SYSTEM_TOPIC` (empty without topics), `TELEGRAM_TOKEN_CMD`
- `ntfy`: `NTFY_URL_CMD`, and `NTFY_TOKEN_CMD` only for a server with access control.
  On `ntfy.sh` anyone who knows the topic reads it: say so.
- `discord`: `DISCORD_WEBHOOK_CMD`
- `slack`: `SLACK_WEBHOOK_CMD`
- `email`: `SMTP_URL`, `SMTP_USER`, `SMTP_PASS_CMD`, `MAIL_FROM`, `MAIL_TO`.
  `smtps://host:465` or `smtp://host:587`; plain SMTP only to localhost.
- `apprise`: `APPRISE_URL_CMD`, `APPRISE_BIN`. If Apprise is missing,
  propose `python3 -m venv ~/.local/share/apprise-venv` and
  `~/.local/share/apprise-venv/bin/pip install apprise`, and wait for yes.

`SYSTEM_TOPIC` stays set on every channel: it decides which messages wake
the session. The old channel's lines stay in the file, so switching back
is one line.

Show the lines you will change, as `KEY=value`, and wait for yes. Write
them in place (a commented `# KEY=` line becomes `KEY=`). Claude Code asks
permission for every file under `.claude/`: tell the owner to expect that
prompt, and if it is refused, give them the two lines to paste. Then check:
`bash -n .claude/scripts/sentinel.env`, and
`NOTIFY=0 .claude/scripts/notify.sh "" "test"` prints `[dry run] via=<channel>`.

End by offering the test of step 4.

## 4. `test`: one real message

Announce: "I will send `homelab-notify test <time>` to <channel>." Send
it when the owner says yes:

`.claude/scripts/notify.sh "" "homelab-notify test $(date '+%H:%M')"`

Topic `""`, so it does not wake the session. Exit 0 means the channel
accepted it, not that the owner saw it: ask whether it arrived. On
`NOT delivered (<channel> answered <code>)`, say the code in plain words:
401/403 a refused token or webhook, 404 a wrong address, `curl exit 67` a
refused login, `curl exit 6` a host that does not resolve,
`secret not readable` a `*_CMD` that printed nothing.
