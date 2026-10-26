---
name: homelab-new-service
description: The pieces without which a new homelab service runs but is not finished. Use when installing a service, a container, an application, or publishing a new name.
---

# A new service, finished

**A service that starts is not a finished service.** A VPN server once ran
"healthy" while three pieces were missing, found one at a time: the DNS
rewrite (it did not open at home), the backup (its keys were not copied),
the monitor (nobody would have known it fell). It was also on the wrong
port, because a sentence was trusted instead of a test from outside.

Walk the list **before** saying "done".

## Before installing

The `scout` agent answers the first two from the web.

- **Does it speak OIDC?** If not, tell the owner **before**: two logins
  instead of one is a point against it.
- **How much RAM?** The declared figure is a hint. **If the machine is
  near its limit, test it**: compose with `mem_limit` on every container,
  port on `127.0.0.1`, then `docker stats` and `free -m` every few
  seconds, idle and **under load**. Watch the **swap**, not `available`:
  available can stay flat while swap climbs by a gigabyte. When the test
  ends, stop the containers; deleting the folder and images is asked.
- **The load test makes no users.** The first account created on many
  applications becomes their administrator, and the owner arriving later
  through the SSO is a plain member. Load the page, `/health` and public
  APIs; or throw away the test database before the first real login.
- **The credentials for the pieces below are there?** List the vault.
  Monitor and DNS need theirs. A missing one is asked **now**, not
  halfway.
- **From the internet, or only home and VPN?** It changes the proxy
  listener. When in doubt: home and VPN only.
- **Configuration keys are checked on the tag you install**, not on the
  main branch: keys move between versions, and strict parsers refuse the
  ones they do not know.

## The pieces

| # | piece | whose | how it is checked |
|---|---|---|---|
| 1 | compose in the live folder, image at a fixed version, `mem_limit`, healthcheck, port published on `127.0.0.1` only | `system` | `docker ps` says `healthy`; `docker stats` under the cap |
| 2 | OIDC client in the identity provider, secret in the vault | `infra-security` | the provider restarts without errors; a real login |
| 3 | site in the reverse proxy, on the right listener | `infra-security` | `curl --resolve <name>:<port>:<lan ip>` answers, without `-k` |
| 4 | DNS rewrite for the name | `infra-security` | `nslookup <name> <dns ip>` gives the LAN address |
| 5 | backup: database and keys in the backup script | `system` | `bash -n` on the script; the next run's log says ok |
| 6 | monitor | `infra-security` | green at its first check |
| 7 | copy of compose and configuration in the repository | whoever installs | `cmp` between live and copy |
| 8 | dashboard entry | coordinator | the dashboard shows it |
| 9 | inventory regenerated, history in the README, commit | coordinator | `git status` clean |

If it is exposed to the internet, one more:

| 10 | test from outside | coordinator | an external checker, two nodes agreeing (not `WebFetch`: it runs from this machine) |

**A systemd unit instead of a container** (a bot listener that must read
the vault on the host): pieces 2-4 do not apply, and the others become:
the unit in `/etc/systemd/system/` with `Restart=always` and its copy in
the repository; the code runs from `/opt/<service>/`, so after a change it
is copied again and restarted; it is born `disabled` and the coordinator
enables it; the monitor is a push one, beaten at every good run.

## The traps

**House names from inside a container.** A service speaking OIDC calls
the identity provider's name, and often its own public name: from the
container they resolve to the public address, where the internal port
does not answer. The compose wants `extra_hosts: ["<name>:host-gateway"]`
for each. **The test is a real login and a real write**: a service once
opened its page but did not let anyone in, and once the login was fixed it
did not upload.

**The proxy listener.** If the router forwards one port only, a site
without that port answers at home and on the VPN but not from outside.
Something that must be reached from outside (a VPN server, a webhook) uses
the internet port in **all** its addresses: server URL, OIDC return URL,
monitor. Opening a site to the internet may be refused by the session's
permission check: write the block ready to paste, the owner adds it over
SSH, and the task for `infra-security` is written without that road, or
the whole agent is refused.

**The DNS rewrite.** Without it, at home the name resolves to the public
address, which from inside answers only on the forwarded port. **Except**
the VPN server's own name: nodes must find it with the tunnel down, so it
must not go through a DNS that sits behind the tunnel.

**The SSO is not on the internet** (usually): an OIDC login can only be
tested from home or the VPN.

**A service for a few people wants a group policy**, not only two-factor:
two-factor on the client lets every family account in.

**The monitor's container resolves names too.** From inside it, a name on
the internal port goes to the public address. Probe the LAN address with
the `Host` header, or give the monitor's compose its own `extra_hosts`
(its restart is asked).

**A red monitor sends a chat message.** Create it **after** the service
answers. A service that alerts on its own writes to the owner's group and
topic, not to an old private chat.

**"It answers 200" is not "it works": the test is the owner's first
login.** A file manager once was healthy and redirected to the SSO; at the
first login the owner's SSO password was forgotten (last good login two
months earlier), the mail reset was broken, and the page came up empty (a
default left off). Before writing "try to log in", look at when they last
logged in; while they do, read the service's logs.

## The order

1. The checks before (OIDC, RAM, credentials, where it must answer).
2. `infra-security`: secret, OIDC client, proxy, DNS.
3. `system`: container, real test, backup.
4. `infra-security`: monitor.
5. Coordinator: test from outside if needed, dashboard, inventory,
   README, commit.

Step 2 comes before 3 because the container reads the secret step 2
wrote.
