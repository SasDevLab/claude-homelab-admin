#!/usr/bin/env bash
# Send a message to the owner's chat: Telegram, or any Apprise channel. Use it as a command or source it:
#   notify.sh <topic> "<text>"        topic: a message_thread_id, or "" for none
#   . notify.sh; notify <topic> "<text>"
#
# A message on SYSTEM_TOPIC is also queued for sentinel.sh, which wakes the
# Claude Code session with it as "SYSTEM ALERT (sentinel): <text>". A script
# that alerts without this file does not wake anyone.
#
# NOTIFY=0 prints the message instead of sending it (dry run): a script that
# notifies sends real messages even while you test it.
#
# Settings: scripts/sentinel.env (see sentinel.env.example), or SENTINEL_ENV.

_kit_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
# shellcheck source=/dev/null
. "${SENTINEL_ENV:-$_kit_dir/scripts/sentinel.env}" || return 1 2>/dev/null || exit 1
ALERT_QUEUE=${ALERT_QUEUE:-$_kit_dir/logs/alert-queue.txt}
type log >/dev/null 2>&1 || log() { echo "$(date '+%F %T')  $*" >&2; }

notify() {
  local topic=$1 text=$2 token code
  if [ "${NOTIFY:-1}" = 0 ]; then echo "[dry run] topic=${topic:-none}: $text"; return 0; fi
  # Queued before sending, so the session hears about it even if Telegram fails.
  # Why it matters: the queue line is no proof the chat got it; the send result is.
  if [ -n "$SYSTEM_TOPIC" ] && [ "$topic" = "$SYSTEM_TOPIC" ]; then
    mkdir -p "$(dirname "$ALERT_QUEUE")" && echo "${text//$'\n'/ / }" >> "$ALERT_QUEUE"
  fi
  if [ -n "$NOTIFY_URL_CMD" ]; then
    # Apprise (ntfy, Slack, Discord, Matrix, email...). It has no topics: the topic only picks the queue above.
    local url
    url=$(eval "$NOTIFY_URL_CMD" 2>/dev/null | tr '\n\r' '  ')
    [ -n "${url// }" ] || { log "notify: not sent, notify URL not readable"; return 1; }
    # The URL goes in the environment, not on the command line: ps shows arguments to every user.
    APPRISE_URLS=$url timeout 60 "${APPRISE_BIN:-apprise}" -b "$text" >/dev/null 2>&1 \
      || { log "notify: NOT delivered (Apprise failed)"; return 1; }
    return 0
  fi
  token=$(eval "$TELEGRAM_TOKEN_CMD" 2>/dev/null | tr -d '\n\r')
  [ -n "$token" ] || { log "notify: not sent, token not readable"; return 1; }
  # Check the HTTP code, not curl's exit: with a revoked token Telegram answers 401 and curl exits 0.
  code=$(curl -s -m 20 -o /dev/null -w '%{http_code}' \
    --data-urlencode "chat_id=$TELEGRAM_CHAT_ID" \
    ${topic:+--data-urlencode "message_thread_id=$topic"} \
    --data-urlencode "text=$text" \
    "https://api.telegram.org/bot$token/sendMessage") || code=000
  [ "$code" = 200 ] || { log "notify: NOT delivered (Telegram answered $code)"; return 1; }
}

# Run as a command, not sourced.
if [ "${BASH_SOURCE[0]}" = "$0" ]; then
  [ $# -eq 2 ] || { echo "usage: notify.sh <topic> \"<text>\"" >&2; exit 2; }
  notify "$1" "$2"
fi
