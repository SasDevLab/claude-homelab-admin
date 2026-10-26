---
name: homelab-diagnosis
description: Finding the real fault in the homelab without chasing false alarms. Use when something does not work, an alert arrives, or an automation "did not fire".
---

# Finding a fault

## 1. Is the fault real?

Many alerts are false. Before digging, confirm the fault exists: the real
time (`date`, never guessed) and the status script (`homelab-status`).

- **A Down that recovered on its own** is reported as such, with the
  times, and the cause is still looked for: it will come back.
- **Push monitors** (the service sends a heartbeat): the window must cover
  the interval **plus** the longest run, because a job beats at the end of
  its run. A slow run makes a Down with nothing broken.
- **Daylight saving change**: in the repeated hour some monitors record no
  heartbeat and go Down, then come back on their own an hour later.
- **Each Down is measured on its own.** Four Downs in a week do not have
  to share a cause: put each heartbeat time next to the run that should
  have sent it.

## 2. The order

1. **Does the service answer?** Not "the process runs": it *answers*, on
   its published port, with real content.
2. **Since when?** `docker ps` shows uptime. If it did not restart, it is
   probably not the one that broke.
3. **What is under it?** Disk, network, memory, the device it talks to.

## 3. Several things at once

- **Same minute → first, did the machine sleep?**
  `journalctl -t systemd-logind -t systemd-sleep` answers in one line (a
  laptop lid). Read **every** kernel line of that second, not only the
  device you were looking at.
- **"The machine was dead"**: look at how the previous boot's log ends
  (`journalctl --list-boots`, then `journalctl -b -1 -n 60`). Cut off in
  the middle of a minute, with no shutdown lines, nobody turned it off.
  Then, in order: the kernel trace saved at reboot
  (`/var/lib/systemd/pstore/`, `grep -nE "Oops|RIP|Comm:"`), the power
  (a smart plug's history, the battery), sleep, the load just before.
  A kernel that freezes on an Oops stays frozen until someone walks to
  it: `kernel.panic=10` and a hardware watchdog make it reboot itself.
- **A clean reboot was ordered by someone**: look for who
  (`journalctl -b -1 | grep -E "sudo.*COMMAND=.*reboot"`), then memory,
  before writing "unknown".
- **After a crash, alerts arrive that are its tail**, not new faults: the
  execution running at crash time stays failed, a dependent service fails
  its first check. Compare their time with the crash time, and check the
  runs after the reboot. One reading is enough.

## 4. "It answers" is not "it works"

- **`healthy` looks at the internal port.** A service behind the SSO that
  spins forever, or returns 500 after exactly 30 seconds, while healthy:
  `docker logs <c> | grep -i 'dial tcp'`. The container is looking for a
  house name at the public address, where from inside nothing answers.
  The cure is `extra_hosts: ["<name>:host-gateway"]` in its compose.
- **A bridge that answers `ok` with an empty payload is down.** Count what
  it has to say, not whether it replies.
- **MQTT availability is retained**: the last "online" stays published
  after the service died. A fresh `null` value is a dead bridge, not a
  live one.
- **A workflow execution marked `success` proves nothing**: workflows have
  error branches and end green on a broken query. Open the execution and
  look at which nodes ran, and how long they took.
- **After an application update**, the first suspects are the automations
  that read its database: the schema changes without notice. Before
  saying "it updated itself", read the git log: it may have been done on
  purpose the day before.
- **A failing systemd timer warns nobody**: `systemctl --failed`.
  **"Job X has not run since <time>"** at the time of its scheduled run:
  first check whether it ran (`systemctl list-timers --all`,
  `systemctl show X.service -p Result -p ExecMainExitTimestamp`). A
  checker ported from another system is believed only after it has seen
  one run of every cadence.
- **"The machine is slow"**: measure over ten seconds, not an instant
  (`top -b -d 10 -n 2`, `ps -eo rss,comm --sort=-rss | head`). The
  measuring itself makes the CPU jump.

## 5. Home automation

- **"The automation did not fire."** First, did it trigger: the
  `automation_triggered` events in the database, read only. Then rebuild
  each condition from the state history at the time of the fault: the
  false one is the cause.
- **Did the trigger's entity ever have a value?** A permanent
  `unavailable` next to a live twin named `_2` is an entity reborn in a
  migration: the automation points at the dead one, and stays blind for
  weeks with nothing down.
- **"That entity does not exist" is not decided by a name search**: read
  the entity registry filtered by integration, and look at `disabled_by`.
  Names deceive (`wi_fi`, not `wifi`). An entity with zero changes in 24
  hours may be a placeholder the device does not really have.
- **When something came back is read from the state history** in time
  order, not from `last_changed` of the API (some sensors change it at
  every new value). Attributes of an `unavailable` device say nothing.
- **The database keeps a few days**: "unchanged since <date>" means "since
  the first record". Before dating the start of a problem, read git and
  the README.
- **Presence**: a GPS `home` is not "inside": the zone radius plus the
  reported accuracy reaches the street. The home Wi-Fi is the closer
  signal.
- **"I see it in the app" does not mean reachable at home**: the app goes
  through the cloud. Measure with ping and the ports; a device that only
  answers ARP is on but not talking. Before the plug: ask whether someone
  touched the app, try the soft reboot, wait.

## 6. Network and VPN

- **The VPN drops on the phone**: do not guess, read three places: the
  server's session durations, what the other client sees about that peer,
  and whether the tunnel carries traffic (`tailscale ping`, `tailscale
  status --json`).
- **A name the VPN nodes need with the tunnel down** must not resolve
  through a DNS that sits behind the tunnel: the node can no longer find
  its way back.
- **A "not in sync" warning in a VPN app can be false.** A one-minute
  decisive test: rename the node on the server and have the owner look at
  the device list. The new name showing up means it is in sync.
- **"The internet freezes in the whole house when you work"**: sample
  router, internet and DNS every second while redoing the suspect
  operation. First check whether the house's traffic even passes through
  this machine. A DNS query log on disk can lag by an hour: a silent hour
  can be a memory buffer.
- **Testing "from the internet" from this machine proves nothing**: it
  sees the rewritten names. Use an external checker with two nodes that
  agree.

## 7. Method

- **Do not stop at the first plausible suspect.** "It was memory" was
  false: the same freezes happened with the machine idle. The proof came
  measuring from inside while the outside test failed.
- **One outcome must tell two hypotheses apart.** Before asking the owner
  for a test, write what you would see in one case and in the other: if
  the two coincide, the test is useless.
- **Fix the cause, not the symptom.** If the check is wrong, fix the
  check.
- **Write the result at once**, in the commit and in memory: what was
  measured, and **which hypothesis was discarded**, so nobody goes back
  to it.
