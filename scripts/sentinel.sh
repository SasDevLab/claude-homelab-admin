#!/usr/bin/env bash
# Sentinel: run every minute by a timer. If Uptime Kuma recorded a new Down,
# or a script queued a system alert (notify.sh), it wakes the Claude Code
# session with a throwaway `claude -p` (ListAgents + SendMessage). The session
# hands the alert to the `guard` agent. If no session answers, it tells the
# owner's chat that nobody is acting on it.
#
#   sentinel.sh                 normal run
#   sentinel.sh --dry-run       print the alerts it would send; sends nothing, saves no state
#   sentinel.sh --from <id>     start after this heartbeat id instead of the saved one
#
# Test: `sentinel.sh --dry-run --from <old id>` with an id a few thousand
# below the one in logs/sentinel-state: it prints past Downs.
#
# Runs as the user who owns the Claude Code session (its session list is per user).
# Kuma's database is only read. important=1 is a state change, status=0 is Down.
# Settings: scripts/sentinel.env (see sentinel.env.example), or SENTINEL_ENV.

kit=$(cd "$(dirname "$0")/.." && pwd)
mkdir -p "$kit/logs"
state=$kit/logs/sentinel-state
LOG=$kit/logs/sentinel.log
log() { echo "$(date '+%F %T')  $*" >> "$LOG"; }
. "$kit/scripts/notify.sh" || exit 1

dry=0; id=-1
while [ $# -gt 0 ]; do
  case "$1" in
    --dry-run) dry=1;;
    --from) shift; id=$1;;
    *) echo "unknown option: $1" >&2; exit 2;;
  esac
  shift
done
case "$id" in ''|*[!0-9-]*) echo "--from wants a number" >&2; exit 2;; esac

k() { $DOCKER exec "$KUMA_CONTAINER" sqlite3 -separator "$(printf '\t')" "$KUMA_DB" "$1"; }
save() { [ "$dry" = 1 ] || echo "$1" > "$state"; }

[ "$id" -lt 0 ] && [ -f "$state" ] && id=$(tr -dc '0-9' < "$state") && id=${id:--1}

max=$(k "select max(id) from heartbeat" 2>/dev/null)
case "$max" in ''|*[!0-9]*) log "skipped: Kuma did not answer"; exit 0;; esac
if [ "$id" -lt 0 ]; then save "$max"; exit 0; fi   # first run: start from now

rows=$(k "select h.id, m.name, replace(replace(replace(h.msg, char(13), ' '), char(10), ' '), char(9), ' '), h.time
  from heartbeat h join monitor m on m.id = h.monitor_id
  where h.important = 1 and h.status = 0 and h.id > $id order by h.id" 2>/dev/null)

# The queue is taken by renaming it, so a line is never sent twice.
# shortcut: if Kuma does not answer the run exits above and the queue waits; split them if that matters.
queue=$ALERT_QUEUE; taken=""
if [ "$dry" = 1 ]; then taken=$(cat "$queue" 2>/dev/null)
elif mv "$queue" "$queue.taken" 2>/dev/null; then taken=$(cat "$queue.taken"); fi
if [ -z "$rows" ] && [ -z "$taken" ]; then save "$max"; exit 0; fi

alerts=(); text=""
while IFS= read -r r; do
  [ -n "$r" ] || continue
  a="SYSTEM ALERT (sentinel): $r"; alerts+=("$a"); text+="$a"$'\n'
done <<< "$taken"
while IFS=$'\t' read -r _ name msg time; do
  [ -n "$name" ] || continue
  a="MONITOR ALERT (sentinel) - $name Down: $msg (at $time UTC)"; alerts+=("$a"); text+="$a"$'\n'
done <<< "$rows"
text=${text%$'\n'}; text=${text//\"/\'}
summary=$(printf '%s / ' "${alerts[@]}"); summary=${summary% / }

if [ "$dry" = 1 ]; then echo "$text"; exit 0; fi

# Throwaway Claude: run from /tmp (no project CLAUDE.md) and without the CLAUDE*
# variables of a parent session, which would make it a child of that session.
ask="Call ListAgents. Pick the LOCAL session (interactive row; not cloud, not Remote Control, not offline) whose name starts with $SESSION_PREFIX; if more than one, the most recent. Send it with SendMessage this exact text, unchanged:
$text
Answer only 'SENT <name>' if SendMessage succeeded, otherwise 'NO-SESSION'. Do nothing else."
out=$(mktemp)
( unset $(compgen -e | grep '^CLAUDE'); cd /tmp && timeout 170 "$CLAUDE_BIN" -p "$ask" --model haiku \
    --allowedTools ListAgents SendMessage ToolSearch < /dev/null > "$out" 2> "$out.err" )
[ $? = 124 ] && result=timeout
result="${result:-} $(tr -s '[:space:]' ' ' < "$out")"
# A crash of the throwaway Claude also ends as NO-SESSION: its stderr says which.
[ -s "$out.err" ] && log "claude stderr: $(head -c 300 "$out.err" | tr '\n' ' ')"
rm -f "$out" "$out.err"

case "$result" in
  *SENT*) ;;
  *)
    # Not on SYSTEM_TOPIC through notify(): that would queue it again and loop.
    if SYSTEM_TOPIC="" notify "$SYSTEM_TOPIC" "Sentinel: $summary. No Claude session reachable: nobody is acting on it."
    then result+=" [chat sent]"; else result+=" [chat FAILED]"; fi;;
esac
save "$max"
log "$summary -> $result"
