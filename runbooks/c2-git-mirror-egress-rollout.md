---
type: runbook
status: current
date: "2026-08-19"
title: "Git-transport + Actions egress: local mirrors and tool-cache durability — <ticket> C2"
topics: [omnibase-infra, c2, git, mirror, egress]
refs: []
---

# Git-transport + Actions egress: local mirrors and tool-cache durability — <ticket> C2

**Status:** ACTIVE on the runner host (`<onex-host>`) as of
2026-08-14. Sibling of `pypi-cache-egress-rollout.md` (C1, wheels) and the §3.19
Docker Hub mirror (images). This one covers **git transport and the Actions tool
cache** — the class the C1 design explicitly listed as "not covered by C1, not
implemented."

Unlike C1, this component is **not soak-gated**, because it cannot fail a job
closed: every runner-side step is fail-open and `actions/checkout` still resolves
the requested SHA against `github.com` over its own authenticated remote. See
"Why this cannot fail a job" below before changing that property.

---

## 1. The failure this removes

72 self-hosted runners NAT through one home uplink. `runner-job-started.sh`
destroys the workspace before every job — correct, and load-bearing: it is what
stops stale sparse-checkout state leaking between jobs on a stateful runner. The
side effect is that `actions/checkout` can **never** reuse an object store, so
every job cold-clones the entire repository. Under wave load that is 72
simultaneous full clones of the same five repos across one uplink.

Measured before-state, `onex_change_control` run `31775568785` (2026-08-14):

| Job | Runner | `fetch-depth` | Symptom |
|---|---|---|---|
| `94690271817` Pre-commit | omninode-runner-37 | 0 | `RPC failed; curl 56 GnuTLS recv error (-54)` + `fatal: early EOF` **3x** (06:23:07Z, 06:27:21Z, 06:36:09Z); job died after 16m43s |
| `94690271858` Context Integrity | omninode-runner-2 | 1 | `Failed to download action 'https://codeload.github.com/actions/checkout/tar.gz/3d3c42e5…'` — `HttpClient.Timeout of 100 seconds` — then GnuTLS `-9`/`-54` + early EOF **3x** |
| `94690197950` CI Summary | omninode-runner-36 | 1 | GnuTLS `-9` then `-54`, both with early EOF |
| `94690198031` OCC Append-Only Gate | omninode-runner-10 | 0 | GnuTLS `-54` + early EOF |

Two distinct failures are visible there and they need different fixes:

- **git transport** (`GnuTLS recv error` / `early EOF`) — fixed by §2, the local
  mirror.
- **runner-native action tarball** (`codeload.github.com` + `HttpClient.Timeout`)
  — **not** fixed here, and not fixable by the tool cache either: the runner
  downloads action tarballs itself, before any hook or action runs. See §5.

---

## 2. Architecture (what is running)

```
                 upstream github.com
                          |
                          |  ONE fetch per repo per 2 min (serialized)
                          v
  omninode-git-mirror-refresh.timer -> .service -> git-mirror-refresh.sh
                          |
                          v
   ~/.omnibase/runners/git-mirror/<repo>.git   (bare mirrors)
                          |
                          |  git-daemon, bound to <docker-bridge-gateway>:9418 (bridge only)
                          v
  omninode-git-mirror-daemon.service
                          |
                          |  git://<docker-bridge-gateway>:9418/<repo>.git
                          v
   runner-job-started.sh  ->  seeds $GITHUB_WORKSPACE, detached HEAD
                          |
                          v
   actions/checkout       ->  authenticated github.com fetch = DELTA ONLY
```

### Host units and paths

| Path / unit | Role |
|---|---|
| `~/.omnibase/runners/git-mirror/<repo>.git` | bare mirrors (351 MiB total for the five repos) |
| `/etc/systemd/system/omninode-git-mirror-daemon.service` | `git-daemon`, `--listen=<docker-bridge-gateway> --port=9418 --export-all`, read-only (no receive-pack) |
| `/etc/systemd/system/omninode-git-mirror-refresh.{service,timer}` | 2-minute refresh, `Type=oneshot` |
| `~/.omnibase/runners/docker/runners/git-mirror-refresh.sh` | deployed refresh script (`ExecStart` target) |
| `~/.omnibase/runners/docker/runners/runner-job-started.sh` | deployed job hook containing the pre-seed |
| `~/.omnibase/runners/toolcache-seed/` | canonical tool-cache snapshot (4.8 GiB) |

In-repo sources: `docker/runners/{git-mirror-refresh.sh,toolcache-seed.sh,runner-job-started.sh}`,
`docker/runners/systemd/*`, `config/runner_fleet.yaml` (`git_mirror:` / `tool_cache:`).

### Serialization is the point

"N jobs, 1 upstream transfer" is enforced twice and both layers are deliberate:
`Type=oneshot` means systemd will not start a second refresh while one is
active, and the script additionally takes an `flock` on
`${MIRROR_ROOT}/.refresh.lock`. Do not convert the unit to `Type=simple` or add
`RemainAfterExit`.

### Why git:// on the bridge and not a bind-mounted `file://` path

A bind mount of the mirror root into the runners would require recreating all 72
containers, which kills every in-flight job and — see §4 — would also destroy the
fleet-wide tool cache. The daemon is reachable from the **existing** containers,
so this component rolls out mid-wave with zero recreate. The cost is that each
job copies the object pack over the bridge (~33 MiB, ~4 s, ~97 MiB/s) instead of
hardlinking it; removing that copy is the `--reference`/alternates upgrade noted
in §5.

Binding to `<docker-bridge-gateway>` (the `docker_default` gateway, the network all 72 runners
sit on) rather than the Tailscale hostname is a security requirement, not a
detail: `git://` is unauthenticated, so the mirrors of private repos must not be
reachable from the LAN or the tailnet.

---

## 3. Why this cannot fail a job

Read this before touching `seed_workspace_from_mirror`.

1. **The mirror is never a source of truth.** `actions/checkout` still fetches
   the exact requested SHA from `github.com` over its own authenticated remote.
   The pre-seed only changes how much of the object graph that fetch has to
   transfer — a mirror that is minutes behind costs a slightly larger delta, and
   can never cause a "SHA not found" failure.
2. **Every step is guarded.** The probe, the fetch, and the checkout are wrapped
   in `timeout` and a subshell that always exits 0; a missing, unreachable, or
   corrupt mirror leaves the workspace exactly as the hook left it before C2.
   This was exercised in the field on the first canary job (omnibase_infra job
   `94696085047`, 06:48:00Z): the probe missed, the hook logged the fail-open
   line, and the job proceeded normally.
3. **The kill switch cannot break the thing it protects.** The disable check is
   written as an `if`, not `[[ … ]] && return 0`. The hook runs under `set -e`,
   where a bare AND-list whose left side is false returns non-zero and would kill
   the hook — i.e. fail every job — precisely when the kill switch was *not* set.
4. **The detached checkout is load-bearing.** `actions/checkout`'s
   `prepareExistingDirectory` runs `git checkout --detach` and deletes the
   directory if that fails, which it would on an unborn HEAD. The detached HEAD
   is also the "have" that git's fetch negotiation offers upstream — it is what
   turns the fetch into a delta.
5. **`remote.origin.url` must match byte-for-byte.** `actions/checkout` computes
   `${GITHUB_SERVER_URL}/${owner}/${repo}` with **no** `.git` suffix and does an
   exact string comparison; any mismatch makes it delete the seeded directory
   (wasted work, not a failure, but the benefit is lost).

---

## 4. Recreating runner containers — read before `--force-recreate`

Two traps, both found the hard way on 2026-08-14.

### 4a. The tool cache is destroyed by a recreate

`RUNNER_TOOL_CACHE` is `/home/runner/actions-runner/_work/_tool`, which lives in
the **container filesystem** — only `/home/runner/.runner-creds` is a named
volume. Measured steady state on 2026-08-14 was **72/72 runners warm** (CPython
3.12.13 or 3.12.14 plus 3.13.15; uv 0.6.14 / 0.8.3 / 0.12.3 / 0.12.4; CodeQL
2.26.x). A naive `docker compose up --force-recreate` takes that to 0/72 and
hands the next wave 72 simultaneous cold CPython + uv downloads from
`objects.githubusercontent.com` — manufacturing the exact stampede this ticket
exists to remove.

Bracket every fleet recreate:

```bash
D=~/.omnibase/runners/docker/runners
$D/toolcache-seed.sh report     # capture the before-state
$D/toolcache-seed.sh snapshot   # union of all runners -> host snapshot
# ... recreate ...
$D/toolcache-seed.sh restore    # host snapshot -> every container missing an entry
$D/toolcache-seed.sh report     # prove the restore
```

`restore` never overwrites an existing entry, so it is safe to re-run and cannot
corrupt a live cache. It is also the way to normalise version drift (runners
created at different times hold different CPython patch releases; `3.12` is
satisfied by either, but an exact pin or `check-latest: true` would turn that
drift into a 63-way cold download).

### 4b. Editing a bind-mounted hook: write in place, never rename

The runner compose bind-mounts individual **files**
(`./runners/runner-job-started.sh` → `/usr/local/bin/runner-job-started.sh`). A
Linux file bind mount pins the **inode**, not the path. `mv`/`install` replace the
inode, so the containers keep executing the old (now unlinked) file and the
update silently does nothing — verified live: host inode `165414643`, container
inode `165412929` with `nlink=0`.

Use an in-place write (`cp src dest`, which opens the destination `O_TRUNC` and
keeps the inode):

```bash
cp /path/to/new/runner-job-started.sh \
   ~/.omnibase/runners/docker/runners/runner-job-started.sh
```

If the inode has already been orphaned, it can be recovered **without** a
recreate by remounting the bind mount read-write inside one container's mount
namespace and writing through `/proc/<pid>/root` — all 72 mounts reference the
same inode, so one write propagates to the whole fleet:

```bash
PID=$(docker inspect -f '{{.State.Pid}}' omninode-runner-1)
sudo nsenter -t $PID -m -- mount -o remount,bind,rw /usr/local/bin/runner-job-started.sh
sudo cp <new-file> /proc/$PID/root/usr/local/bin/runner-job-started.sh
sudo nsenter -t $PID -m -- mount -o remount,bind,ro /usr/local/bin/runner-job-started.sh
# verify on an UNRELATED container:
docker exec omninode-runner-55 bash -c 'bash -n /usr/local/bin/runner-job-started.sh'
```

Note `remount,bind,rw` — plain `remount,rw` fails with `mount point is busy`.
Always re-verify with `bash -n` inside a container before walking away: a
truncated hook fails every job on the fleet.

---

## 5. What this does NOT cover

- **Runner-native action tarballs** (`codeload.github.com`, the 100 s
  `HttpClient.Timeout` in job `94690271858`). The runner downloads and extracts
  action tarballs into `_work/_actions` during job initialisation, *before* the
  `ACTIONS_RUNNER_HOOK_JOB_STARTED` hook runs, and it wipes `_actions` per job —
  so neither the hook nor a pre-populated directory can help. The upstream lever
  is `ACTIONS_RUNNER_ACTION_ARCHIVE_CACHE`, and **this runner build does not
  support it** (the string is absent from every DLL under
  `/home/runner/actions-runner/bin`). The remaining option is the C2(a) HTTP
  caching forward proxy from the design doc, which needs a new service plus
  proxy env on the runners, i.e. a fleet recreate.
- **The per-job 33 MiB bridge copy.** Bind-mounting the mirror root and using
  `--reference`/`objects/info/alternates` would take that to near zero, at the
  cost of a fleet recreate.
- **ghcr / container image pulls** — separate lever (§3.19 Docker Hub mirror).
- **PyPI wheels** — C1, `pypi-cache-egress-rollout.md`.

---

## 6. Verification

```bash
# units healthy
systemctl is-active omninode-git-mirror-daemon.service
systemctl list-timers omninode-git-mirror-refresh.timer --no-pager
sudo journalctl -u omninode-git-mirror-refresh --no-pager -n 20

# every mirror answers over the bridge
for r in onex_change_control omnibase_infra omnibase_core omnimarket omniclaude; do
  printf '%s heads=' "$r"
  timeout 10 git ls-remote --heads git://<docker-bridge-gateway>:9418/$r.git | wc -l
done

# a runner container can reach the daemon
docker exec -u runner omninode-runner-1 \
  bash -c 'timeout 10 git ls-remote --heads git://<docker-bridge-gateway>:9418/onex_change_control.git | wc -l'
```

Job-log evidence: a seeded job prints

```
[c2-mirror] pre-seeded <repo> from git://<docker-bridge-gateway>:9418/<repo>.git at <sha> in <n>s -- checkout will fetch a delta, not a full clone.
```

and the subsequent `actions/checkout` "Fetching the repository" group shows no
`Receiving objects` line (nothing transferred) or a small one.

---

## 7. Rollback (non-disruptive, no recreate)

The pre-seed is additive; removing it returns the fleet to direct egress.

1. **Per-job:** set `OMNI_GIT_MIRROR_DISABLE=1` in the workflow env.
2. **Fleet, immediate:** narrow the allowlist on the deployed hook — edit
   `_C2_MIRROR_RUNNERS` in place (per §4b: `cp`, never `mv`) to a smaller set, or
   restore `runner-job-started.sh.pre-c2.bak`. Takes effect on the next job start;
   no container restart, no recreate.
3. **Stop serving:** `sudo systemctl disable --now omninode-git-mirror-daemon
   omninode-git-mirror-refresh.timer`. The pre-seed's probe then fails and every
   job takes the fail-open path — i.e. exactly the pre-C2 behaviour.
4. **Reclaim disk:** `rm -rf ~/.omnibase/runners/git-mirror` (351 MiB)
   and `~/.omnibase/runners/toolcache-seed` (4.8 GiB). Keep the
   tool-cache snapshot unless you are certain no recreate is pending — §4a.

## 8. References

- `docs/plans/2026-07-06-runner-fleet-layer-b-egress-caching-design.md` — <ticket> design (C1/C2/C3)
- `docs/runbooks/pypi-cache-egress-rollout.md` — C1 sibling (wheels)
- `config/runner_fleet.yaml` — `git_mirror:` / `tool_cache:` source of truth
