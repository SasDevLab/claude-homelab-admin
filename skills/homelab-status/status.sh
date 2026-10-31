#!/usr/bin/env bash
# Homelab status in one screen. Read only: it changes nothing.
#
#   status.sh          the whole picture, things needing attention last
#   status.sh --busy   only the "is something working?" check:
#                      exit 1 if something is working, 0 if nothing is
#
# Run it with sudo if Docker needs root here: without it, containers are
# reported as "not measured", never as down.

set -u
attention=()

# Something is working right now. Prints one line per job, returns the count.
busy() {
  local n=0 line
  # A timer's job running now (backups, copies, reports) is a oneshot
  # service in "activating".
  while read -r unit _ _ sub _; do
    # auto-restart is a crash loop waiting to retry, not work in progress.
    [ -n "$unit" ] && [ "$sub" != auto-restart ] && { echo "  working: $unit (systemd job running now)"; n=$((n+1)); }
  done < <(systemctl list-units --type=service --state=activating --no-legend --plain 2>/dev/null)
  # Add your own checks here: uploads to the photo library, running
  # workflow executions, job queues. For a counter, read it twice a few
  # seconds apart: a number that does not move is nothing working.
  return $(( n > 0 ))
}

if [ "${1:-}" = "--busy" ]; then
  busy; n=$?
  [ "$n" -eq 0 ] && echo "Nothing is working." && exit 0
  exit 1
fi

echo "TIME     $(date '+%a %d %b %Y %H:%M:%S %Z')   up since $(uptime -s)"

echo "BUSY"
busy; [ $? -eq 0 ] && echo "  nothing is working"

read -r _ mem_total _ _ _ _ mem_avail < <(free -m | awk '/^Mem:/')
read -r _ swap_total swap_used _ < <(free -m | awk '/^Swap:/')
echo "MEMORY   ${mem_avail} MB available of ${mem_total}, swap ${swap_used}/${swap_total} MB"
# Half-full swap with plenty of RAM free is old idle pages, not pressure.
[ "${swap_total:-0}" -gt 0 ] && [ $((swap_used * 100 / swap_total)) -ge 50 ] && \
  [ $((mem_avail * 100 / mem_total)) -lt 15 ] && \
  attention+=("memory pressure: ${mem_avail} MB available, swap ${swap_used}/${swap_total} MB")

echo "LOAD     $(cut -d' ' -f1-3 /proc/loadavg) on $(nproc) cores"
t=$(cat /sys/class/thermal/thermal_zone*/temp 2>/dev/null | sort -n | tail -1)
if [ -n "$t" ]; then
  echo "TEMP     $((t / 1000)) C (hottest sensor)"
  [ $((t / 1000)) -ge 85 ] && attention+=("temperature $((t / 1000)) C")
fi

echo "DISKS"
while read -r use mnt; do
  echo "  $use $mnt"
  [ "${use%\%}" -ge 90 ] && attention+=("disk $mnt at $use")
done < <(df -P -x tmpfs -x devtmpfs -x overlay -x squashfs -x efivarfs 2>/dev/null | awk 'NR>1 {print $5, $6}')

if command -v docker >/dev/null; then
  if out=$(docker ps -a --format '{{.Names}}|{{.Status}}' 2>/dev/null); then
    up=$(grep -c '|Up' <<<"$out")
    echo "DOCKER   $up of $(grep -c . <<<"$out") containers up"
    while IFS='|' read -r name status; do
      [ -n "$name" ] || continue   # no containers: one empty line
      case "$status" in
        Up*unhealthy*) attention+=("container $name: $status") ;;
        Up*) ;;
        *) attention+=("container $name: $status") ;;
      esac
    done <<<"$out"
  else
    echo "DOCKER   not measured (no permission: run with sudo)"
    attention+=("containers not measured: run with sudo")
  fi
fi

while read -r unit _; do
  [ -n "$unit" ] && attention+=("failed unit $unit")
done < <(systemctl --failed --no-legend --plain 2>/dev/null)

# Add your monitor here (Uptime Kuma monitors that are Down) and any
# fault your devices log today.

echo
if [ ${#attention[@]} -eq 0 ]; then
  echo "Nothing needs attention."
else
  echo "NEEDS ATTENTION"
  printf '  %s\n' "${attention[@]}"
fi
