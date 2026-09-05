---
type: plan
status: active
date: "2026-03-01"
title: "Gap investigation series"
topics: [integration, drift, auditing, methodology]
---

# Gap Investigation Series — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Run a four-skill gap investigation series (gap-analysis + pipeline-audit → gap-fix → golden-path-validate) to find and close integration drift across the full platform after restarting the emit daemon.

**Architecture:** Parallel discovery (1a gap-analysis + 1b pipeline-audit) feeds auto-fix (gap-fix), which must produce merged PRs and a confirmed redeploy before live validation (golden-path-validate) runs against the routing pipeline.

**Tech Stack:** Kafka/Redpanda (`${KAFKA_BOOTSTRAP_SERVERS}`), omniclaude skills, Docker Compose runtime stack, kcat, rpk

---

## Pre-flight: Load Environment

**Files:**
- Read: `~/.omnibase/.env`

**Step 1: Source the environment**

```bash
source ~/.omnibase/.env
echo "KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS:-(NOT SET — STOP)}"
echo "POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:+(SET)}${POSTGRES_PASSWORD:-(NOT SET — STOP)}"
```

Expected: Both vars printed with real values. `POSTGRES_PASSWORD` must show `(SET)` — the value itself is never printed. If either says `NOT SET — STOP`, do not continue.

**Step 2: Commit current notes**

```bash
cd $WORKSPACE_ROOT
git status
```

Expected: Working tree clean or only untracked files. No staged/unstaged changes that would be disrupted by the run.

---

## Task 0: Emit Daemon Health — Three-Level Verification

**Files:**
- Check: discover socket path dynamically (see Step 0-1)
- Log: `$(ls -t ~/.claude/plugins/cache/omninode-tools/onex/*/hooks/logs/emit-daemon.log | head -1)`

### Step 0-1: Level 1 — Socket responds

Discover the socket path dynamically before connecting. Use a 3-level glob to avoid hardcoding the macOS temp path segment:

```bash
SOCK=$(ls /var/folders/*/*/*/T/omniclaude-emit.sock 2>/dev/null | head -1)
if [ -z "$SOCK" ]; then
  echo "ERROR: emit socket not found — daemon may not be running. STOP."
  exit 1
fi
echo "Socket path: $SOCK"

# Connect with 5-second timeout via background nc + kill guard
nc -U "$SOCK" <<< '{}' &
NC_PID=$!
sleep 5
if kill -0 "$NC_PID" 2>/dev/null; then
  kill "$NC_PID"
  echo "ERROR: nc hung for 5s — daemon is unresponsive. STOP."
  exit 1
fi
wait "$NC_PID"
echo "Socket responded."
```

Expected: Socket path printed and nc exits within 5 seconds with some response. If `nc` hangs: **STOP — daemon is dead**.

### Step 0-2: Level 2 — Log shows recent "emit success"

```bash
LOG=$(ls -t ~/.claude/plugins/cache/omninode-tools/onex/*/hooks/logs/emit-daemon.log | head -1)
ls -l "$LOG"
tail -200 "$LOG" | grep "emit success\|publish success\|emitted" | tail -1
```

Expected: The `ls -l` output shows the log was modified within the last 5 minutes. The grep line shows a recent success entry. If the log mtime is stale (> 5 minutes ago) or the grep returns nothing: **STOP — daemon is stale, restart needed**.

### Step 0-3: Level 3 — Broker metadata preflight

Instead of publishing a canary message to a production topic, verify broker metadata only:

```bash
source ~/.omnibase/.env
echo "KAFKA_BOOTSTRAP_SERVERS: ${KAFKA_BOOTSTRAP_SERVERS:+(SET)}${KAFKA_BOOTSTRAP_SERVERS:-(NOT SET — STOP)}"
kcat -b "${KAFKA_BOOTSTRAP_SERVERS}" -L -t onex.cmd.omninode.routing-requested.v1 -e
```

Expected: Broker metadata printed with partition list for the topic. No errors. This is a metadata preflight check only — it does not publish any messages.

If `kcat` returns an error or cannot reach the broker: **STOP — broker is unreachable or topic not found**.

---

## Task 1: Repo Snapshot (required before Phase 1)

**Files:**
- Write: `/tmp/gap-analysis-repo-snapshot.txt`

### Step 1-1: Snapshot the repo set

```bash
ls $WORKSPACE_ROOT/ | grep -v "^docs\|^\." > /tmp/gap-analysis-repo-snapshot.txt
cat /tmp/gap-analysis-repo-snapshot.txt
```

Expected: List of repo directories (omniclaude, omnibase_core, omnibase_infra, etc.). Record this output in your run notes — it anchors what was in scope for Phase 1.

---

## Task 2: Phase 1a — gap-analysis

**Skill:** `onex:gap-analysis`

### Step 2-1: Run gap-analysis

Invoke:

```
/onex:gap-analysis --since-days 30
```

Expected: Skill runs through all closed epics in the last 30 days, produces a `.json` + `.md` report per epic under `~/.claude/gap-analysis/{epic_id}/{run_id}/`. The skill prints the epic directory path and run ID on stdout — capture these for Step 2-2.

Do **not** wait for pipeline-audit to start this — run both simultaneously (2 and 3 can be dispatched in parallel in the same session via two subagents).

### Step 2-2: Pin the latest report

After the skill completes, capture the `EPIC_ID` and `EPIC_DIR` from the skill's stdout. Do NOT infer the epic directory from the most-recently-modified directory — use the ID the skill explicitly printed.

```bash
# EPIC_ID and EPIC_DIR must be exported from gap-analysis skill stdout, e.g.:
# EPIC_ID="<epic-id>"
# EPIC_DIR="$HOME/.claude/gap-analysis/<epic-id>"
EPIC_DIR=<PASTE epic dir from skill output>
EPIC_ID=<PASTE epic ID from skill output>

# Create latest symlink pointing to the epic directory (not a file copy)
ln -sfn "$EPIC_DIR" ~/.claude/gap-analysis/latest
echo "Latest symlink created: $HOME/.claude/gap-analysis/latest -> $EPIC_DIR"
```

Expected: `~/.claude/gap-analysis/latest` is a symlink to the epic directory, not a copy of a JSON file.

```bash
REPORT=$(ls ~/.claude/gap-analysis/latest/*.json | head -1)
python3 -m json.tool "$REPORT" | head -30
```

Expected: Valid JSON with findings array. Export `$REPORT` — it is used in Tasks 4, 5, and 9.

---

## Task 3: Phase 1b — pipeline-audit

**Skill:** `onex:pipeline-audit`

### Step 3-1: Run pipeline-audit (full platform)

Invoke:

```
/onex:pipeline-audit
```

Scope: full platform, all repos. Expected phases: inventory → capability → trace → proof → gap register → fix tickets (6 phases total).

### Step 3-2: Verify created tickets have severity + owner

After the skill completes, check Linear for the created fix tickets. For each ticket:

```
/onex:linear
# or directly inspect the ticket list in Linear
```

Expected: Every created ticket has:
- A severity label set (CRITICAL / WARNING / MEDIUM / LOW)
- An assignee (owner) set

If any ticket is unowned: assign it before moving to the Phase 1 gate.

---

## Task 4: Phase 1 Gate — CRITICAL/WARNING Disposition

### Step 4-1: List all CRITICAL findings from gap-analysis

```bash
python3 - "$REPORT" <<'EOF'
import json, sys

with open(sys.argv[1]) as f:
    data = json.load(f)

findings = data.get('findings', data) if isinstance(data, dict) else data
crits = [
    fi for fi in (findings if isinstance(findings, list) else [])
    if fi.get('severity', '').upper() == 'CRITICAL'
]
for fi in crits:
    print(fi.get('id', '?'), '|', fi.get('title', '?'), '|', fi.get('status', 'open'))
print(f'Total CRITICAL: {len(crits)}')
EOF
```

Expected: Either `Total CRITICAL: 0`, or each CRITICAL finding shows a status of `fixed` or has a suppression note.

**Gate rule:**

| Finding severity | Required action |
|---|---|
| CRITICAL | Fixed OR suppressed with: written justification + owner Linear ticket |
| WARNING | Tracked in Linear with assignee + due date |
| MEDIUM / LOW | Logged; no blocker |

If any CRITICAL is unfixed with no suppression: **STOP. Fix or suppress with explicit justification before Phase 2.**

### Step 4-2: Verify pipeline-audit CRITICAL/WARNING tickets all have assignees

In Linear, confirm every CRITICAL or WARNING pipeline-audit ticket has:
- Assignee (not unassigned)
- Due date set

If any lack either field: set them now. Record the ticket IDs in your run notes.

---

## Task 5: Phase 2 — gap-fix

**Skill:** `onex:gap-fix`

**Pre-step:** Confirm `~/.claude/gap-analysis/latest` symlink exists and `$REPORT` is set (Task 2-2 must be done first).

```bash
ls -la ~/.claude/gap-analysis/latest
echo "REPORT: $REPORT"
[ -f "$REPORT" ] || { echo "ERROR: REPORT not set or file missing. STOP."; exit 1; }
```

Expected: Symlink exists; `$REPORT` points to a readable JSON file.

### Step 5-1: Run gap-fix

Invoke:

```
/onex:gap-fix --latest
```

Mode: ticket-pipeline (safe-only dispatching). The skill will only auto-dispatch findings that:
- Touch one repo
- Have explicit DoD with local verification steps
- Do NOT alter Kafka topics or contracts (unless explicitly overridden)

### Step 5-2: Capture the output path

The skill prints its output path when done. Record it by pasting directly from skill output — do NOT infer from directory listing:

```bash
RESULT_FILE="$(dirname "$REPORT")/gap-fix-result.json"
GAP_FIX_OUTPUT=$(python3 -c "import json; d=json.load(open('$RESULT_FILE')); print(d['output_path'])")
echo "gap-fix output: $GAP_FIX_OUTPUT"
python3 -m json.tool "$GAP_FIX_OUTPUT" | head -40
```

Expected: Valid JSON with `dispatched`, `blocked`, and `skipped` arrays.

### Step 5-3: Review BLOCK decisions

```bash
DECISIONS=$(dirname "$GAP_FIX_OUTPUT")/decisions.json
python3 -m json.tool "$DECISIONS" 2>/dev/null || \
  echo "No decisions.json found — check gap-fix output path"
```

`decisions.json` schema: flat dict keyed by finding fingerprint. Each entry must have:
- `action`: one of `"fix"` or `"suppress"` (required)
- `justification`: non-empty string (required — a "I'll fix it later" note is NOT acceptable)

For each BLOCK entry: either implement via `/ticket-work` or add a written suppression justification that satisfies the schema above.

---

## Task 6: Phase 2 Gate — Merge + Redeploy + Version Verify

### Step 6-1: Confirm all PRs from this run are merged (not just CI-green)

Load the list of PRs created by this gap-fix run from `$GAP_FIX_OUTPUT`, then check each one:

```bash
python3 - "$GAP_FIX_OUTPUT" <<'EOF'
import json, sys, subprocess

with open(sys.argv[1]) as f:
    d = json.load(f)

prs = d.get('prs_created', [])
if not prs:
    print("No PRs created by this run.")
    sys.exit(0)

failures = []
for pr in prs:
    repo = pr.get('repo')
    number = pr.get('number')
    result = subprocess.run(
        ['gh', 'pr', 'view', str(number), '--repo', repo,
         '--json', 'state,isDraft,mergeable,baseRefName'],
        capture_output=True, text=True
    )
    info = json.loads(result.stdout) if result.returncode == 0 else {}
    state = info.get('state', 'UNKNOWN')
    print(f"  PR #{number} ({repo}): {state}")
    if state != 'MERGED':
        failures.append(f"PR #{number} ({repo}) is {state}")

if failures:
    print("UNMERGED PRs:")
    for f in failures:
        print(f"  - {f}")
    sys.exit(1)
else:
    print("All PRs merged.")
EOF
```

Expected: All PRs from this run show `MERGED`. If any are open or unmerged: merge them now (or explain why not before proceeding).

### Step 6-2: Redeploy the runtime stack

```bash
cd $WORKSPACE_ROOT/omnibase_infra
docker compose -f docker/docker-compose.infra.yml --profile runtime up -d --build
```

Expected: All services show `Started` or `Running`. Watch for any `Error` lines.

If any service versions do not match the latest merged PRs after initial `--build`, run a no-cache rebuild:

```bash
docker compose -f docker/docker-compose.infra.yml --profile runtime build --no-cache \
  omninode-runtime omninode-runtime-effects omninode-agent-actions-consumer omnibase-intelligence-api
docker compose -f docker/docker-compose.infra.yml --profile runtime up -d
```

```bash
docker compose -f docker/docker-compose.infra.yml ps
```

Expected: `omninode-runtime`, `omninode-runtime-effects`, `omninode-agent-actions-consumer`, and `omnibase-intelligence-api` all in `running` state.

### Step 6-3: Verify package versions inside containers

```bash
docker exec omninode-runtime python -c "
import omniclaude, omnibase_infra
print('omniclaude:', omniclaude.__version__)
print('omnibase_infra:', omnibase_infra.__version__)
"

# omniintelligence lives in the intelligence-api container:
docker exec omnibase-intelligence-api python -c "
import omniintelligence
print('omniintelligence:', omniintelligence.__version__)
"
```

Expected: Versions printed match the tag/version of the latest merged PRs. Record these in your run notes.

If versions inside container are older than what was merged: **STOP — rebuild did not pick up new code. Check Docker build cache / image pinning.**

---

## Task 7: Phase 3 Pre-checks — Consumer Group + Schema

**Files:**
- Check: `omniclaude/src/omniclaude/nodes/node_agent_routing_compute/models/model_routing_request.py`

### Step 7-1: Discover and inspect the routing consumer group

```bash
docker exec omnibase-infra-redpanda rpk group list | grep -i "routing\|node_agent"
```

Expected: A group named like `local.node_agent_routing_compute` or `dev.node_agent_routing_compute`.

```bash
docker exec omnibase-infra-redpanda rpk group describe <group-name-from-above>
```

Expected:
- `lag == 0` or near-0 on all partitions
- No stuck partitions
- All partitions have an active member

If lag is high (> 1000) or any partition has no member: **investigate before running golden-path**. Check `docker logs omninode-runtime --tail=50` for errors.

### Step 7-2: Schema compatibility check

`node_agent_routing_compute` is a COMPUTE node — it has no direct Kafka I/O; topics validate the full pipeline boundary. The model uses `ModelRoutingRequest` (frozen, extra=forbid) with no `event_version` field. Version parity was verified in Task 6-3.

```bash
grep "class ModelRoutingRequest\|frozen\|extra" \
  $WORKSPACE_ROOT/omniclaude/src/omniclaude/nodes/node_agent_routing_compute/models/model_routing_request.py
```

Expected: Model class found with `frozen=True` and `extra='forbid'` (or equivalent). If missing: investigate before running golden-path.

---

## Task 8: Phase 3 — golden-path-validate

**Skill:** `onex:golden-path-validate`

### Step 8-1: Run golden-path-validate for agent routing

`node_agent_routing_compute` is a COMPUTE node — it does not consume from Kafka directly. The topics below validate the full pipeline boundary (effect nodes on both sides).

Three steps before invoking the skill:

**Step A:** Verify the fixture is schema-valid for `ModelRoutingRequest`:

```bash
python3 -c "
from omniclaude.nodes.node_agent_routing_compute.models.model_routing_request import ModelRoutingRequest
import json
fixture = {'agent_hint': 'test-agent', 'intent': 'route me', 'correlation_id': 'gp-test-001'}
m = ModelRoutingRequest(**fixture)
print('Fixture valid:', m.model_dump())
"
```

**Step B:** Write the declaration JSON to the golden-path declarations directory:

```bash
mkdir -p ~/.claude/golden-path/declarations
cat > ~/.claude/golden-path/declarations/agent_routing_pipeline.json <<'DECL'
{
  "pipeline": "agent_routing",
  "input_topic": "onex.cmd.omninode.routing-requested.v1",
  "output_topic": "onex.evt.omninode.routing-completed.v1",
  "assertions": [
    { "field": "status",      "op": "eq",  "expected": "completed" },
    { "field": "latency_ms",  "op": "lte", "expected": 2500 },
    { "field": "error_count", "op": "eq",  "expected": 0 }
  ],
  "min_sample_size": 20,
  "timeout_ms": 30000
}
DECL
echo "Declaration written."
```

**Step C:** Invoke the skill:

```
/onex:golden-path-validate ~/.claude/golden-path/declarations/agent_routing_pipeline.json
```

Expected: Skill runs validation, prints result, and writes artifact to `~/.claude/golden-path/`.

### Step 8-2: Verify run-level results

The skill prints its artifact path on stdout. Paste that path below — do not guess it:

```bash
GP_ARTIFACT="<PASTE path from skill output>"
[ -f "$GP_ARTIFACT" ] || { echo "ERROR: GP_ARTIFACT not found. STOP."; exit 1; }

python3 - "$GP_ARTIFACT" <<'EOF'
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
run = d.get('run', d)
print('run.status:', run.get('status', '?'))
print('error_count:', run.get('error_count', '?'))
print('timeout_count:', run.get('timeout_count', '?'))
samples = run.get('samples', [])
if samples:
    lats = [s['latency_ms'] for s in samples if 'latency_ms' in s]
    print(f'max latency_ms: {max(lats) if lats else "no data"}')
    print(f'sample count: {len(samples)}')
EOF
```

Expected:
- `run.status: pass`
- `error_count: 0`
- `timeout_count: 0`
- `max latency_ms <= 2500`
- `sample count >= 20`

If any assertion fails: consult the recovery table below.

---

## Task 9: End-State Verification Checklist

Run through all conditions before closing this run:

```bash
echo "=== End-State Verification ==="

# 1. gap-analysis: no unfixed CRITICALs
echo "[ ] gap-analysis: 0 unfixed CRITICAL findings"
python3 - "$REPORT" <<'EOF'
import json, sys
with open(sys.argv[1]) as f:
    d = json.load(f)
findings = d.get('findings', [])

# Load decisions.json to check resolutions
import os
decisions_path = os.path.join(os.path.dirname(sys.argv[1]), '..', 'decisions.json')
decisions = {}
if os.path.exists(decisions_path):
    with open(decisions_path) as df:
        decisions = json.load(df)

unresolved = []
for x in findings:
    if x.get('severity', '').upper() != 'CRITICAL':
        continue
    fp = x.get('fingerprint', x.get('id', ''))
    dec = decisions.get(fp, {})
    action = dec.get('action', '')
    justification = dec.get('justification', '')
    resolved = action in {'fix', 'suppress'} and len(justification) > 0
    if not resolved:
        unresolved.append(x.get('id', '?'))

print(f'  Unfixed CRITICALs: {len(unresolved)}')
if unresolved:
    for u in unresolved:
        print(f'    - {u}')
    sys.exit(1)
EOF

# 2. pipeline-audit: no unowned CRITICAL/WARNING
echo "[ ] pipeline-audit: 0 unowned CRITICAL/WARNING tickets"
echo "  (verify in Linear)"

# 3. golden-path: all pass
echo "[ ] golden-path: run.status==pass, >=20 samples, max latency<=2500, error_count==0"
echo "  (check output from Task 8-2)"
```

All three must be checked and confirmed before marking the run complete.

---

## Recovery Table

| Failure mode | Recovery action |
|---|---|
| gap-analysis errors | Read the `.md` report; fix root cause in a repo worktree (`omni_worktrees/<ticket>/<repo>`); re-run skill before proceeding to gap-fix |
| pipeline-audit GAP findings | Tickets created automatically; work via `/ticket-work`; verify assignee is set before Phase 1 gate |
| gap-fix BLOCK decision | Read `decisions.json`; implement via `/ticket-work` or suppress with explicit written justification |
| golden-path **fail** | Check consumer groups first (Task 7-1); check `docker logs omninode-runtime`; re-run after fixing root cause |
| golden-path **timeout** | Check broker connectivity; check partition health via `rpk group describe`; redeploy and retry |
| Schema mismatch after partial redeploy | Restart **all** affected services; verify model class on both producer and consumer sides; re-run golden-path after full redeploy |
| Container version mismatch | Confirm the PRs are merged, not just CI-green open; rebuild with `--no-cache` if Docker cache is stale |

---

## Commit

After all three end-state conditions are satisfied:

```bash
cd $WORKSPACE_ROOT
git add docs/plans/2026-03-01-gap-investigation-series.md
git commit -m "docs: add gap investigation series execution plan (2026-03-01)"
```
