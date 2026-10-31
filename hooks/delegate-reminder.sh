#!/bin/sh
# PreToolUse hook (Bash): when the coordinator is about to do installation or
# configuration work itself, it reminds that the job belongs to an agent. It
# blocks nothing: it only adds a line to the context.
# Why: a written rule ("the coordinator coordinates") is not enough under
# pressure. The reminder at the moment of the command is.
# PATTERN and AGENTS come from the plugin options (delegate_pattern,
# delegate_agents: /plugin, then configure); the fallbacks are the defaults.
PATTERN=${CLAUDE_PLUGIN_OPTION_DELEGATE_PATTERN:-'systemctl +(enable|daemon-reload)|/etc/systemd/|docker compose +up|apt(-get)? +install'}
AGENTS=${CLAUDE_PLUGIN_OPTION_DELEGATE_AGENTS:-'system, infra-security'}

in=$(cat)
# A sub-agent carries the agent_id field: the reminder is only for the coordinator.
printf '%s' "$in" | grep -q '"agent_id"' && exit 0
if printf '%s' "$in" | grep -q -E "$PATTERN"; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"DELEGATION REMINDER: this is agent work (%s). If it is more than a few lines, stop and hand it over. The coordinator coordinates."}}\n' "$AGENTS"
fi
exit 0
