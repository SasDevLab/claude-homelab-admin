#!/bin/sh
# PreToolUse hook (Bash, Write, Edit): when a command or a script is about to
# download or run a model on ollama, it reminds the memory limit of the machine
# that runs it. It blocks nothing: it only adds a line to the context.
# Why: a model heavier than the free RAM can reboot the host that runs it, and
# everything else running there goes down with it. The name of a model does
# not say its weight: the manifest does.
# LIMIT comes from the plugin option model_limit; the fallback is the default.
LIMIT=${CLAUDE_PLUGIN_OPTION_MODEL_LIMIT:-'keep models under 60% of the free RAM of the ollama host'}

in=$(cat)   # read it all: grep -q would close the pipe early on a big Write
if printf '%s' "$in" | grep -q -i -E 'api/pull|ollama +(pull|run)'; then
  printf '{"hookSpecificOutput":{"hookEventName":"PreToolUse","additionalContext":"MODEL REMINDER: %s. Before downloading or loading a model, read its weight from the manifest (sum of the layers, projector included). A load test is announced to the owner first. On a small CPU, set num_thread in the request options: the default can be ten times slower."}}\n' "$LIMIT"
fi
exit 0
