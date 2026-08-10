# homelab-showcase

A public, hand-curated look at the architecture and engineering behind a personal homelab. This
is a companion to the full private infrastructure repo, not a mirror of it: everything here was
deliberately written or rewritten for a public audience, with no shared git history and no
internal specifics (no real IPs, hostnames, ports, or account details).

**`content.json` is the single source of truth.** [prakash-somani.com/homelab](https://prakash-somani.com/homelab)
fetches it directly and renders it live, so editing this file and pushing to `main` updates the
live page on the next load. No redeploy of the website is needed.

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
