#!/usr/bin/env bash
# Send a message to the owner: Telegram, ntfy, Discord, Slack, email, or any Apprise channel.
# Use it as a command or source it:
#   notify.sh <topic> "<text>"        topic: a number is a Telegram message_thread_id;
#                                     equal to SYSTEM_TOPIC (a number or a word) it also wakes the session
#   NOTIFY_NOQUEUE=1 notify.sh ...    on SYSTEM_TOPIC, send without waking the session
#   . notify.sh; notify <topic> "<text>"
#
# A message on SYSTEM_TOPIC is also queued for sentinel.sh, which wakes the
# Claude Code session with it as "SYSTEM ALERT (sentinel): <text>". A script
# that alerts without this file does not wake anyone. Only Telegram shows the
# topic; on the other channels it just decides the queue.
#
# NOTIFY=0 prints the message instead of sending it (dry run): a script that
# notifies sends real messages even while you test it.
#
# Settings: scripts/sentinel.env (see sentinel.env.example), or SENTINEL_ENV.
# Secrets come from *_CMD commands and reach curl on stdin, never on its
# command line: ps shows arguments to every user.

_kit_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=/dev/null
. "${SENTINEL_ENV:-$_kit_dir/scripts/sentinel.env}" || return 1 2>/dev/null || exit 1
ALERT_QUEUE=${ALERT_QUEUE:-$_kit_dir/logs/alert-queue.txt}
type log >/dev/null 2>&1 || log() { echo "$(date '+%F %T')  $*" >&2; }

# Run a *_CMD setting and print its first line.
_secret() { eval "$1" 2>/dev/null | head -n1 | tr -d '\r'; }

# A JSON string, quotes included. Other control characters are dropped.
_json() {
  local s=$1
  s=${s//\\/\\\\}; s=${s//\"/\\\"}; s=${s//$'\n'/\\n}; s=${s//$'\t'/\\t}
  printf '"%s"' "$(printf '%s' "$s" | tr -d '\000-\010\013-\037')"
}

# A value for a curl config file (curl -K), quotes included.
_cfg() { local s=${1//\\/\\\\}; printf '"%s"' "${s//\"/\\\"}"; }

# POST to a secret URL. Prints the HTTP code, 000 when there is no answer.
# Check the code, not curl's exit: a refused token still exits 0.
_post() {
  local url=$1; shift
  printf 'url = %s\n' "$(_cfg "$url")" | curl -s -m 20 -o /dev/null -w '%{http_code}' -K - "$@" || true
}

notify() {
  local LC_ALL=C.UTF-8   # ${text:0:N} counts characters, not bytes: no letter cut in half
  local -; set +u        # optional settings may be unset in a caller with set -u
  local topic=$1 text=$2 via=${NOTIFY_VIA:-telegram} secret code thread=
  # Only a number is a Telegram topic; a word (SYSTEM_TOPIC=system) only marks what wakes the session.
  [[ $topic =~ ^[0-9]+$ ]] && thread=$topic
  if [ "${NOTIFY:-1}" = 0 ]; then echo "[dry run] via=$via topic=${topic:-none}: $text"; return 0; fi
  # Queued before sending, so the session hears about it even if the send fails.
  # Why it matters: the queue line is no proof the owner got it; the send result is.
  # NOTIFY_NOQUEUE=1 sends without queueing: for the guard's own report, which
  # would otherwise come back to the session as a new alert.
  if [ -n "$SYSTEM_TOPIC" ] && [ "$topic" = "$SYSTEM_TOPIC" ] && [ "${NOTIFY_NOQUEUE:-0}" != 1 ] && [ -n "$text" ]; then
    mkdir -p "$(dirname "$ALERT_QUEUE")" &&
      { flock 9; echo "${text//$'\n'/ / }" >> "$ALERT_QUEUE"; } 9<"$(dirname "$ALERT_QUEUE")"   # lock the folder: no lock file root could own
  fi
  case $via in
    telegram) secret=$(_secret "$TELEGRAM_TOKEN_CMD") ;;
    ntfy)     secret=$(_secret "$NTFY_URL_CMD") ;;
    discord)  secret=$(_secret "$DISCORD_WEBHOOK_CMD") ;;
    slack)    secret=$(_secret "$SLACK_WEBHOOK_CMD") ;;
    email)    if [ -n "$SMTP_PASS_CMD" ]; then secret=$(_secret "$SMTP_PASS_CMD"); else secret=none; fi ;;
    apprise)  secret=$(eval "$APPRISE_URL_CMD" 2>/dev/null | tr '\n\r' '  ') ;;
    *) log "notify: not sent, unknown NOTIFY_VIA=$via"; return 1 ;;
  esac
  [ -n "${secret// }" ] || { log "notify: not sent, $via secret not readable"; return 1; }

  case $via in
    telegram)
      code=$(_post "https://api.telegram.org/bot$secret/sendMessage" \
        --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
        ${thread:+--data-urlencode "message_thread_id=$thread"} \
        --data-urlencode "text=${text:0:4096}") ;;   # Telegram takes at most 4096 characters
    ntfy)
      # NTFY_TOKEN_CMD only for a server with access control; the header comes from fd 3.
      if [ -n "$NTFY_TOKEN_CMD" ]; then
        code=$(_post "$secret" -H @/dev/fd/3 --data-raw "$text" \
          3< <(echo "Authorization: Bearer $(_secret "$NTFY_TOKEN_CMD")"))
      else
        code=$(_post "$secret" --data-raw "$text")   # --data-raw: a text starting with @ is not a file to upload
      fi ;;
    discord)
      # Discord takes at most 2000 characters.
      code=$(_post "$secret" -H 'Content-Type: application/json' \
        --data-binary "{\"content\":$(_json "${text:0:2000}")}") ;;
    slack)
      code=$(_post "$secret" -H 'Content-Type: application/json' \
        --data-binary "{\"text\":$(_json "$text")}") ;;
    email)
      local subject first=${text%%$'\n'*} tls=--ssl-reqd auth=
      subject="${NOTIFY_SUBJECT:-homelab}: ${first:0:40}"   # shortcut: one encoded word, may pass 75 chars with many accents
      # A relay on this machine may speak plain SMTP; anything else must use TLS.
      [[ $SMTP_URL =~ ^smtp://(localhost|127\.0\.0\.1)(:[0-9]+)?/?$ ]] && tls=   # not localhost.example.net
      # User and password come from fd 3.
      [ "$secret" = none ] || auth="-K /dev/fd/3"
      printf 'From: %s\nTo: %s\nSubject: =?UTF-8?B?%s?=\nDate: %s\nMIME-Version: 1.0\nContent-Type: text/plain; charset=UTF-8\nContent-Transfer-Encoding: 8bit\n\n%s\n' \
        "$MAIL_FROM" "$MAIL_TO" "$(printf '%s' "$subject" | base64 -w0)" "$(LC_ALL=C date -R)" "$text" |
        curl -s -m 30 --crlf $tls $auth --mail-from "$MAIL_FROM" --mail-rcpt "$MAIL_TO" -T - "$SMTP_URL" \
          3< <([ "$secret" = none ] || printf 'user = %s\n' "$(_cfg "$SMTP_USER:$secret")") \
        && code=200 || code="curl exit $?" ;;
    apprise)
      APPRISE_URLS=$secret timeout 60 "${APPRISE_BIN:-apprise}" -b "$text" >/dev/null 2>&1 && code=200 || code=failed ;;
  esac
  # Discord answers 204, the others 200.
  case $code in 200|204) return 0 ;; esac
  log "notify: NOT delivered ($via answered $code)"; return 1
}

# Run as a command, not sourced.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  [ $# -eq 2 ] || { echo "usage: notify.sh <topic> \"<text>\"" >&2; exit 2; }
  notify "$1" "$2"
fi
