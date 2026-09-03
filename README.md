# homelab-showcase

A public, hand-curated look at the architecture and engineering behind a personal homelab. This
is a companion to the full private infrastructure repo, not a mirror of it: everything here was
deliberately written or rewritten for a public audience, with no shared git history and no
internal specifics (no real IPs, hostnames, ports, or account details).

**`content.json` and `stats.json` are the single source of truth.**
[prakash-somani.com/homelab](https://prakash-somani.com/homelab) fetches both directly and renders
them live, so editing `content.json` and pushing to `main` updates the live page on the next load.
No redeploy of the website is needed. `stats.json` is written by an unattended job on a schedule;
everything else here is written by hand.

The section below this line is generated from `content.json` and `stats.json` by
`tools/render_readme.py`, run by this repo's own GitHub Action on every push that touches either
file. Editing it directly will be overwritten on the next push; edit the source files instead.

<!-- BEGIN GENERATED -->

## Current stats

- **15** Docker Compose stacks
- **63** scheduled jobs
- **23809** job runs in the last 14 days, **99.96%** success rate
- Status: **healthy**
- Open inbound ports: **0**
- Secrets encryption: **SOPS / age**
- Last verified: **2026-09-03**

## Incidents

### A slow-booting NAS silently broke every container that depended on it

A shared power event meant the NAS came back up slower than the host. systemd's default ~90 second mount timeout gave up waiting before the NAS responded, boot continued without the network mount, and Docker started anyway. Every container bind-mounting that storage got an empty local directory instead of the real share, with no error surfaced anywhere. Some services crash-looped; others just showed empty libraries, since they don't hard-fail on missing files. Fixed by extending the mount timeout and adding a systemd drop-in that blocks Docker itself from starting until every managed mount is confirmed live, deliberately all-or-nothing, so no service starts silently broken while others start fine.

### A permission bug that looked like a missing file, not a permission error

A container running as a non-root user couldn't see files that clearly existed on a network share. The share's subfolders were owned correctly, but the share's own root directory was not, restrictive enough to block a non-root process from even traversing into it, while a root-running container sailed straight through and never noticed. It surfaced as 'path does not exist' in the app's own UI, which sent the first round of debugging in the wrong direction entirely. The fix was a single non-recursive ownership change on the share root, not the subfolders everyone assumed were the problem.

### An unbounded log file took down the whole host, not just one container

Docker's default logging driver has no size limit out of the box. One container hit a transient error, logged it, failed to log again, logged that failure too, and the loop filled the host's entire local disk with a single log file in a matter of hours. A full disk crashed the Docker daemon itself and made the whole host briefly unresponsive, not just the one misbehaving container. Fixed with a daemon-wide log rotation default, plus a scheduled disk-usage check as an early warning for any other cause of the same failure mode.

### A network card bug that looked like a bandwidth problem and wasn't

A NIC intermittently hung under load, sometimes recovering on its own, sometimes needing a manual power cycle. The obvious suspect was network saturation from scheduled bulk transfers, except the hangs kept happening during a throttled, low-bandwidth window and never during the unthrottled overnight one, the opposite of what a bandwidth theory predicts. Correlating the kernel logs against the transfer schedule ruled that out and pointed at a known hardware-driver interaction instead (TSO/offload behavior combined with a power-saving feature on that generation of chipset). Fixed by disabling the offending offloads at the network layer, not by touching bandwidth limits at all.

### A host-level fix that didn't apply to anything already running

A VPN client briefly took over the host's DNS resolution during a reboot. The host-level config was repaired by hand afterward, and the host itself looked completely healthy again, correct resolvers, working lookups. But every container that had already started was still pointed at the dead resolver, because containers capture DNS config at creation time, not continuously. Two unrelated-looking apps broke at once (one failed to fetch artwork, several others lost network access entirely), and diagnosing it meant checking DNS from inside a container, not trusting what the host itself reported. A plain container restart was the actual fix; the host-level setting only prevented a repeat.

### A job that passed its own health check 23 hours out of 24, doing nothing

A scheduled job ran hourly but only did real work during one specific hour, gating itself internally and returning success the other 23 times without an error, by design, just quietly a no-op. Every run still reported a clean exit code, so a naive health check watching for failures would have shown green all day, including on the one morning the job that actually mattered failed. The fix wasn't a smarter health check, it was removing the need for one: schedule the job to run exactly when it's supposed to do work, and let a missed run look like what it is.

<!-- END GENERATED -->

## Architecture

- A Proxmox hypervisor runs a single Debian VM ("docker-host") that hosts every service as its
  own Docker Compose stack.
- A separate NAS provides shared network storage, mounted into the Docker host over NFS.
- Inbound access runs entirely through a Cloudflare Tunnel: the host reaches out to establish the
  tunnel, so nothing needs an open inbound port on the home network.
- An operational layer sits underneath the services themselves: a scheduling layer for backups,
  bandwidth throttling, and self-healing jobs; encrypted secrets (SOPS/age) decrypted only at the
  moment a job needs them, never written to disk in plaintext; and push-notification alerting for
  anything that needs a human.

## Design rules

- Everything runs in Docker on one host, no per-service bare-metal installs.
- All user data lives on the NAS; only boot-critical config and anything that can't safely share
  a network filesystem (databases, in particular, see the NFS/database note in `content.json`'s
  incidents) stays on local disk.
- No secrets in git, anywhere, including here. Real credentials live encrypted, decrypted only at
  the point of use.
- Everything is meant to be reproducible from a repo, not from memory of what was clicked in a UI.

## Hardware

See `content.json`'s `hardware` field for the current host and NAS specs.

## What's deliberately not here

This repo does not include, and will not include: the private repo's git history, any real IP,
hostname, or port, download-automation/media-acquisition tooling, secrets-store internals, or
exact incident timestamps. See `content.json`'s `incidents` for the general engineering lessons
without any of that.
