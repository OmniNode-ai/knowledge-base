---
type: runbook
status: current
date: "2026-08-19"
title: "Runner-fleet local DNS cache rollout — <ticket>"
topics: [omnibase-infra, runner, dns, cache, rollout]
refs: []
---

# Runner-fleet local DNS cache rollout — <ticket>

**Status:** SHOVEL-READY / execution operator-gated. Do **not** run these steps
until an explicit operator go, exactly like the <ticket> pypi-cache canary
pattern. This runbook is the `APPLY.md` companion to the staged cache; keeping
it in-repo means the rollout is reviewable before it runs.

## What this is

All 64+ self-hosted runner containers resolve DNS through `systemd-resolved`
pointed at a single LAN-router upstream (`<lan-gateway>`, with `8.8.8.8` as
fallback) — there is no local caching layer. Under a 64+ concurrent job-start
burst (all runners cold-starting `uv sync` / `actions/checkout` near
simultaneously), every container fires its own upstream query for the same
handful of CI hostnames. A single router-grade upstream is not built for that
query concurrency; this is the plausible chokepoint behind
[<ticket>](https://linear.app/omninode/issue/<ticket>) — deterministic
`files.pythonhosted.org` `Temporary failure in name resolution` failures,
reproduced on 3 distinct OCC PRs, one at `run_attempt=14`.

A local unbound caching resolver absorbs repeat lookups for the same
hostnames and caps how long a retry storm can amplify a transient upstream
hiccup, without replacing the existing router/fallback resolution path — it
is purely additive. See `docker/dns-cache/Dockerfile` for why unbound was
picked over dnsmasq (fine-grained negative-caching TTL control + a built-in
stats interface for the hit-rate metric this rollout needs).

## Artifacts in this repo (already landed by this design/canary PR)

| Artifact | Role | State |
|---|---|---|
| `docker/dns-cache/Dockerfile` + `unbound.conf` + `entrypoint.sh` | unbound caching-resolver image (build-at-rollout) | inert |
| `docker/docker-compose.dns-cache.yml` | standalone cache service (NOT in the runner fleet) | inert |
| `docker/docker-compose.dns-canary.yml` | canary `dns:` override for 2-4 runners | inert / non-default |
| `config/runner_fleet.yaml` → `dns_cache:` | endpoint source-of-truth | `active: false` |

Relationship to the other three runner-scaling preconditions (per the
`[mergesweep-0808-capacity]` ledger row): this ticket is precondition #1 of
four — [<ticket>](https://linear.app/omninode/issue/<ticket>) (pypi-cache,
canary live), [<ticket>](https://linear.app/omninode/issue/<ticket>) (git
mirror / shallow-checkout policy, Backlog), and a not-yet-filed busy-window
measurement precondition. Do not use a green canary here as license to scale
runner count — the other three preconditions are independent gates.

## Rollout (gated — run only after explicit operator go)

Run on the runner host (`<onex-host>` / `<onex-host>`). This is a NEW service; it
does not mutate any prod daemon or the runner containers on its own.

### 1. Freeze the pins

- Pin the `alpine:3.20` base image to a `@sha256:` digest in
  `docker/dns-cache/Dockerfile` (match the runner-image and pypi-cache
  reproducibility discipline).

### 2. Stand up the cache

```bash
docker compose -f docker/docker-compose.dns-cache.yml up -d --build
# wait for healthy:
docker inspect --format '{{.State.Health.Status}}' omninode-dns-cache
# prove it actually resolves through itself:
dig +time=3 +tries=1 @<onex-host> files.pythonhosted.org
```

### 3. Wire 2-4 canary runners (leave the rest on direct router DNS)

Layer the non-default override on top of the base fleet compose file and
recreate only the canary containers — this does **not** touch the other 60+
runners.

```bash
docker compose \
  -f docker/docker-compose.runners.yml \
  -f docker/docker-compose.dns-canary.yml \
  up -d --no-deps omninode-runner-1 omninode-runner-2
```

Default is 2 canary runners (`omninode-runner-1`, `omninode-runner-2`); extend
to 3-4 by uncommenting `omninode-runner-3`/`omninode-runner-4` in
`docker-compose.dns-canary.yml` and adding them to the command above. The
router (`<lan-gateway>`) stays as the 2nd `dns:` entry on every canary
container, so a cache miss/outage degrades (falls through to the router), not
fails-closed.

### 4. Measure on the canary (busy-window soak — AC1-AC3)

- **Cache hit rate** (AC1): `docker exec omninode-dns-cache unbound-control
  stats_noreset | grep -E 'total.num.(queries|cachehits|cachemiss)'`, or read
  the periodic `[dns-cache-stats]` lines in `docker logs omninode-dns-cache`.
  Target ≥ 0.80 steady-state (`config/runner_fleet.yaml`
  `dns_cache.target_hit_rate`) — lower than the pypi-cache's 0.90 target
  because DNS answers are far fewer distinct records than PyPI wheels, but
  each canary runner still needs enough job volume to have queried the same
  hostnames more than once before this number is meaningful.
- **Routing verification** (AC2): confirm via `docker exec
  omninode-runner-1 cat /etc/resolv.conf` (or container logs) that DNS
  queries route through `<onex-host>`, not the router directly.
- **Zero DNS-class failures** (AC3): zero occurrences of the
  `files.pythonhosted.org`-style `Temporary failure in name resolution`
  signature on canary-runner job logs over a stated busy-window observation
  period (`config/runner_fleet.yaml` `dns_cache.target_dns_failure_count: 0`).
  A "busy window" here means concurrent `merge_group`/full-suite load
  comparable to the conditions that produced <ticket>, not idle overnight
  traffic — an idle-window green does not satisfy this AC.

### 5. Fleet rollout (only if the canary is green — separate operator go)

- Set `dns_cache.active: true` in `config/runner_fleet.yaml`.
- Extend the canary `dns:` wiring to the full 64+ fleet, either by widening
  `docker-compose.dns-canary.yml` to cover every runner service or by
  promoting the `dns:` block into the `x-runner-base` anchor in
  `docker-compose.runners.yml` directly (operator's call at that point).
- Roll the change fleet-wide via the same idle-only, rolling-recreate
  discipline used for fleet-heal / image rebuilds — never a blanket
  `--force-recreate` across all 64+ containers at once.

## Rollback (non-disruptive)

The cache is additive; removing the canary wiring returns those containers to
direct router resolution.

1. Recreate the canary runners without the override file:
   ```bash
   docker compose -f docker/docker-compose.runners.yml \
     up -d --no-deps omninode-runner-1 omninode-runner-2
   ```
2. Tear down the cache service (its own project — not a runtime lane, so the
   no-bare-compose-teardown gate does not apply):
   ```bash
   docker compose -f docker/docker-compose.dns-cache.yml down
   ```

unbound's cache is in-memory only (no named volume), so there is nothing to
discard beyond the container itself.

## References

- <ticket> (this work)
- <ticket> — the DNS failure class this cache targets
- `[mergesweep-0808-capacity]` — capacity-probe ledger row identifying the
  single-upstream-no-cache topology as the plausible chokepoint
- <ticket> / `docs/runbooks/pypi-cache-egress-rollout.md` — sibling cache
  rollout this runbook is modeled on (wheels vs DNS; same host, same
  non-disruptive rollback discipline, same operator-gate posture)
