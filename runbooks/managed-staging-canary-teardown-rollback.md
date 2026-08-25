---
type: runbook
status: current
date: "2026-07-21"
title: "Managed-staging one-tenant canary — teardown / abort / rollback"
topics: [omnibase-infra, managed, staging, canary, teardown]
refs: []
---

# Managed-staging one-tenant canary — teardown / abort / rollback

This runbook defines how to **unwind** the backend-only, one-gateway,
one-synthetic-tenant MSK canary described in the managed-staging task split. It is
the **exact reverse of the bring-up**, plus two failure-mode entry points (abort,
rollback) that are made **explicit and owned**, not implicit.

Ticket: **<ticket>** (Lane B / task **B13**).
The plan docs cited below live in the **`OmniNode-ai/omni_home` registry** (not in this
repo), under its `docs/plans/` tree; paths are given as plain code, not repo-relative
links.

- Plan of record: `omni_home:docs/plans/2026-07-17-managed-staging-verified-state-and-task-split.md`
  — tasks **B2** (worker/data ASG scale), **B7** (canary topic/group catalog), **B10**
  (monitoring signals wired to numeric thresholds), **B11** (run the canary + abort),
  and **B13** (this teardown/rollback spec).
- Ownership/authority model: `omni_home:docs/plans/2026-07-17-managed-staging-agent-driven-execution-plan.md`.
- Epoch-aware rollback contract (superset, governs any authoritative-write case):
  `omni_home:docs/plans/2026-07-16-managed-staging-cloud-cutover-plan.md` § "Rollback Contract".

> **This document is a spec. It executes nothing.** Every step below is a *live
> mutation* that is **HELD FOR OPERATOR**. Per the agent-driven execution plan, the
> agent presents one reviewed step at a time (exact command, expected output,
> rollback), and **Jonah issues GO and executes by default**. No AWS, IAM, MSK topic,
> consumer-group, RDS, secret, or ASG mutation is authorized by authoring or reading
> this runbook. There is no autonomous teardown.

> **Plane scope.** This targets the single `dev`-tagged managed plane (account
> `272493677981`, `us-east-1`, cluster `omninode-dev-msk`, instance
> `omninode-dev-postgres`). It is **not** the `<onex-host>` runtime lanes and **not** prod.
> The prod-promotion grant gate (CLAUDE.md §2a/§12) does **not** apply here because no
> prod resource is touched — but the "each live mutation needs an explicit operator
> GO" rule from the agent-driven plan still governs every step.

---

## 0. Ownership — who owns each path (read first)

Three distinct unwind paths, three distinct trigger conditions, one shared executor
for the live steps. "Owns" below means *accountable for the decision*; the **live
execution of every mutation is Jonah's by default**, and the **agent** presents +
validates each step and captures evidence.

| Path | When it fires | Trigger owner (decides to start) | Live-execution owner | Prepare / validate / evidence owner |
|---|---|---|---|---|
| **Teardown** (§2) | Canary **succeeded** (or a clean, non-failure stop) — planned unwind | Jonah (planned) | Jonah | Agent |
| **Abort** (§3) | **B10 numeric threshold breach** mid-run (auth / TLS / broker / lag / RDS) | Staffed operator (Jonah) on the agent's breach signal | Jonah | Agent (owns B10 detection + presents the halt) |
| **Rollback** (§4) | Authoritative state was written and must be reverted, or the candidate image/config must revert while MSK/RDS stay authoritative | Jonah | Jonah | Agent (owns the rollback tuple + reconciliation readback); Contractor consulted for any AWS-side revert |

Supporting identities (referenced, **not invoked** by this runbook):

- **A3 create/delete-capable operator identity** — the operator/admin IAM identity
  that carries `CreateTopic`/`DeleteTopic` and consumer-group admin on the cluster,
  scoped to `arn:aws:kafka:us-east-1:272493677981:cluster/omninode-dev-msk/*` and the
  `onex.*` / `omninode.*` topic and group patterns (per plan A1/A3). **All canary
  topic/group deletion uses this operator identity, never the runtime identity** — A1
  strips `DeleteTopic` from the runtime node-role path, so the runtime identity cannot
  (and must not) delete topics. Owned by the contractor's team.
- **Runtime workload identity (A1)** — used by the canary pods only; carries no
  topic-admin after A1. Not used for teardown.

---

## 1. What the bring-up did (so teardown can reverse it exactly)

The canary bring-up, in order (B11 run sequence and its Lane-A/Lane-B prerequisites):

| # | Bring-up step | Task | Canary-specific? |
|---|---|---|---|
| 1 | Build + push fresh `main-lineage` runtime image; record ECR digest | B1 | No — durable plane state |
| 2 | Scale worker + data ASGs **off** `desired=0` | B2 | Yes (capacity for the canary) |
| 3 | Admit the canary node group's SG to MSK SG `sg-0183e3c660adf6ef1` on 9098 | A2 | No — durable plane state |
| 4 | Prove pod→IMDS identity + MSK connect from the scheduled node group | A1 | No — durable plane state |
| 5 | Create canary **topics + consumer groups** on the fresh prefix (create-capable A3 identity) | B7 / A3 | **Yes** |
| 6 | Provision canary Postgres **logical DB** + migrations/projection (landing) tables + runtime DB creds | B12 | **Yes** |
| 7 | Wire monitoring signals to numeric thresholds (from A6) | B10 | Config (canary window) |
| 8 | **Activate consumers → start the single producer → send one synthetic command →** correlation-linked readback → replay-determinism check → **soak ≥30 min or 2 token-refresh cycles** | B11 | **Yes** |

**Key invariant that makes teardown safe (from B7):** the canary uses its own topic
**prefix**, and B7's acceptance readback proves the prefix matches **zero of the 1089
existing topics AND zero existing consumer groups**. The canary namespace is therefore
**non-authoritative by construction** — deleting it cannot fork or destroy any
authoritative event log. This is what distinguishes canary teardown from the
epoch-aware Rollback Contract (§4).

---

## 2. Teardown — planned unwind (exact reverse of §1)

Run this when the canary **succeeded** or is being stopped cleanly (no threshold
breach). Execute in the order below — it reverses the bring-up **last-step-first**, so
producers are fenced before consumers, and topics are removed only after nothing is
attached to them.

**Owner:** trigger = Jonah (planned); execution = Jonah; prepare/validate/evidence =
agent. Every step is HELD FOR OPERATOR.

### T-0. Freeze evidence FIRST (never deleted)

Before any destructive step, confirm the B11 evidence surface is captured and durable:
the `docs/evidence/…` packet + the OCC receipt for the correlation-linked readback and
the replay comparison (named in B11). **Teardown, abort, and rollback never delete
evidence, topics-of-record, or databases-of-record.** If evidence is not yet durable,
STOP — do not tear down an un-evidenced canary.

### T-1. Stop the single producer (write fence) — reverses B11 step 8 (producer)

Halt the one synthetic producer / gateway so no new authoritative writes enter the
canary topics. This is the write fence. Expected readback: producer offset stops
advancing; no new records on the canary prefix.

### T-2. Halt the consumers (drain + commit) — reverses B11 step 8 (consumers)

Stop the canary consumer group members **after** the producer is fenced. Let in-flight
messages drain, then commit final offsets so positions are captured (do **not** leave
uncommitted in-flight work). Expected readback: consumer group has no active members;
lag is final/static. Capturing final positions here is what lets §4 reason about
whether any authoritative projection was written.

### T-3. Capture final soak/readback evidence — reverses B11 readback/soak

Record the terminal state into the evidence packet (final lag, final projection-table
row(s), soak duration met, replay-determinism result). This is additive to T-0; it is
the last read before deletion.

### T-4. Delete canary consumer groups, then canary topics — reverses B7 (via A3)

Using the **A3 create/delete-capable operator identity** (referenced in §0; **not**
invoked by this runbook), delete in this order:

1. the canary **consumer groups** (delete groups first, or a still-attached consumer
   re-creates them — hence T-2 must complete first);
2. the canary **topics** on the fresh prefix.

Use the **same admin path B7 used to create them** (exact reverse). **Delete strictly
by the canary prefix** — the prefix B7 declared, which by B7's acceptance readback
overlaps **zero** existing topics/groups. Never issue a wildcard delete; never touch
any of the 1089 pre-existing inert topics.

**Acceptance readback (required):** re-list topics and groups and assert the canary
prefix now matches **zero** topics and **zero** groups, and that the pre-existing
topic/group count is **unchanged** from the pre-canary baseline.

### T-5. Tear down the canary Postgres surface — reverses B12 *(operator call)*

The canary logical DB + landing/projection tables + runtime DB creds created by B12.
**Default:** retain the DB read-only as forensic evidence for the evidence packet, then
drop it once the receipt is durable. If dropping: drop the canary **logical DB** (and
revoke/rotate its runtime creds) — scoped to the canary DB only, never
`omninode-dev-postgres`'s other logical DBs. **Acceptance readback:** the canary
logical DB is absent (or intentionally retained-and-noted); no other DB affected.
*This step is jointly owned with B12; if B12 chose to retain the DB for evidence,
record that decision here instead of dropping.*

### T-6. Scale worker + data ASGs back to `desired=0` — reverses B2

Scale the dev/staging worker + data ASGs back to `desired=0` (their pre-canary
verified state — plan §1: "ALL worker + data ASGs = desired 0"). Expected readback:
each ASG `DesiredCapacity=0`, instances draining to zero. Do this **after** the topics
are gone so no pod re-creates a consumer group during scale-down.

### T-7. What teardown deliberately does NOT reverse

Leave the **durable plane state** in place — it is not a canary artifact:

- **B1** ECR image (durable; the plane's runtime image).
- **A2** MSK SG 9098 allow-list entry for the node group (durable network posture).
- **A1** node-role / pod-identity wiring and its tightening (durable identity posture).
- **A4** RDS TLS pinning, if landed (durable).

Reverting these is a **separate, explicitly-scoped decision**, not part of canary
teardown. Needlessly reverting them re-opens the exact gaps A1/A2/A4 closed.

### T-8. Declare the post-canary steady state (the exit assertion)

Teardown is **complete** only when all of the following are read back as true (logs
alone are insufficient — assert the surfaces):

- Worker + data ASGs at `DesiredCapacity=0` (readback).
- Canary prefix matches **zero** topics and **zero** consumer groups; the 1089
  pre-existing inert topics are **unchanged** (count + spot-check readback).
- Canary Postgres logical DB dropped **or** intentionally retained-and-noted; no other
  logical DB touched.
- Durable plane state (B1/A2/A1/A4) **preserved**.
- Evidence packet + OCC receipt **retained** and durable.

Record this steady-state assertion in the evidence packet as the teardown receipt.

---

## 3. Abort — B10 threshold breach mid-run (explicit, owned)

**Abort is a distinct, owned action, not a synonym for "the canary failed."** It fires
**during** the canary run when a **B10 numeric threshold** (fed by A6) is breached:
authentication failure rate, TLS posture, broker health, consumer position/lag, or RDS
signal. A threshold without an action is advisory (B11) — this section is that action.

**Owner:** the **staffed operator (Jonah)** owns the abort **call** and executes the
live halt; the **agent** owns **detection** (B10 wiring surfaces the breach against the
numeric threshold) and **presents the exact halt commands + validates the halt took
effect**. This split is deliberate: detection is mechanical (agent), the go/no-go and
the live mutation are the operator's.

**False-abort guard (from A6):** an RDS signal must distinguish **single-AZ
unavailability** — a maintenance event on the no-HA `omninode-dev-postgres` instance —
from a genuine canary failure. Do **not** abort on an RDS blip that matches a scheduled
maintenance window; A6's thresholds encode that distinction. Verify the breach is real
and not a maintenance artifact before pulling the trigger (but do not stall a genuine
auth/TLS/broker breach waiting for certainty — those are unambiguous).

### Abort sequence

1. **STOP the producer immediately** (write fence) — same as T-1. This is the first and
   most time-critical action: stop new authoritative writes.
2. **HALT the consumers** — same as T-2, but capture positions **before** committing so
   the breach state is forensically preserved; then commit to avoid re-delivery
   ambiguity.
3. **Snapshot the breach evidence FIRST** — capture the signal sample that tripped the
   threshold (the metric value, timestamp, and which B10 threshold), plus final lag and
   the last projection row, into the evidence packet. Evidence precedes destruction.
4. **Then run the teardown** — proceed into §2 from **T-4** (topics/groups → Postgres →
   ASGs → steady-state assertion). Steps T-1/T-2 are already done as abort steps 1–2.

**Abort is complete** when the §2 T-8 steady state holds **and** the breach snapshot is
durable in the evidence packet. An abort that stops the producer but leaves topics,
groups, or scaled-up workers behind is **not** complete.

---

## 4. Rollback — authoritative-state revert (distinct from abort)

**Abort stops-and-tears-down a running canary that never became authoritative.
Rollback reverts state after an authoritative write, or reverts the candidate
image/config while the managed broker/DB stay authoritative.** For the backend-only,
one-synthetic-tenant canary, the B7 prefix is non-authoritative by construction (§1
invariant), so a clean unwind is §2 teardown — **not** a rollback. Rollback becomes the
governing path only if the canary is promoted to carry authoritative traffic, or if a
config/image must be reverted mid-flight. This section defers to the **epoch-aware
Rollback Contract** in the cutover plan; the rules below are its load-bearing subset.

**Owner:** trigger + live execution = Jonah; the **agent prepares the rollback tuple
and owns the reconciliation readback**; the **contractor** is consulted for any AWS-side
revert (SG/identity), which normally persists.

### 4.1 Prepare the rollback tuple FIRST (B13 / plan T28)

Before any canary write, the agent assembles and Jonah accepts the **rollback tuple**:

- exact **previous ECR image digest + config** to revert to;
- named **rollback owner** (Jonah, live);
- the exact **rollback commands**;
- the **reconciliation/readback queries** that prove recovery;
- the **abort thresholds** (B10) that would trigger it.

A rollback without a pre-staged tuple is not a rollback — it is improvisation under
pressure. (This mirrors the `<onex-host>` discipline: the rollback target must be pinned/tagged
*before* the mutation, never discovered afterward.)

### 4.2 Epoch-aware rules (never violate)

- **Rollback never deletes topics-of-record, databases-of-record, or evidence.** (This
  is why §2 T-4/T-5 can delete the canary prefix/DB: they are non-authoritative by
  construction — rollback of *authoritative* state does not.)
- **Never blindly flip endpoints back to Redpanda.** Redpanda is retained only as
  evidence of the closed prior epoch. After the first MSK write, returning authority to
  Redpanda requires a **separately approved reconciliation** — never a blind endpoint
  restore.
- **After MSK/RDS became authoritative:** prefer **image/config rollback** while MSK and
  RDS stay authoritative. A broker/database *authority* rollback requires quiescing every
  in-scope producer/outbox/retry/scheduler/emitter, capturing both sides, running the
  approved forward-repair/reverse-sync, and proving deterministic parity **before**
  changing authority.
- **Rollback is complete only when authoritative state — not logs — proves recovery**
  (reconciliation readback from 4.1 passes).

### 4.3 Relationship to teardown

If, after an authoritative rollback, the canary itself is also being retired, the
**non-authoritative** canary artifacts (its prefix topics/groups, its logical DB) are
removed via §2 teardown, and the durable plane state (§2 T-7) is preserved. Rollback and
teardown compose; they are not alternatives.

---

## 5. Quick decision table

| Situation | Path | Entry point |
|---|---|---|
| Canary soak passed, retire it | Teardown | §2 from T-0 |
| Canary stopped cleanly, no breach | Teardown | §2 from T-0 |
| B10 threshold breached mid-run | Abort | §3 (then §2 from T-4) |
| Authoritative write must be reverted | Rollback | §4 (then §2 if also retiring) |
| Candidate image/config revert, broker/DB stay authoritative | Rollback | §4.2 (image/config) |
| RDS blip during a known single-AZ maintenance window | **Not an abort** | §3 false-abort guard — verify first |

---

## 6. Held-for-operator status of the live steps

Every mutating step in §2–§4 is **HELD FOR OPERATOR** and is **not** authorized by this
runbook:

- producer stop / consumer halt (canary workload),
- consumer-group + topic deletion (via the A3 operator identity — referenced, not
  invoked here),
- canary Postgres logical-DB drop / cred rotation,
- ASG scale-to-zero,
- any image/config or AWS-side revert (§4).

The agent's role is to present each step with its exact command, expected readback, and
rollback, **one reviewed step at a time**; Jonah issues GO and executes by default. This
document adds the spec only — it performs no live mutation and grants no standing
authority to execute one.

---

## Related runbooks

- `docs/runbooks/cold-lane-full-bringup.md` — the `<onex-host>`
  cold-lane bring-up/teardown analog (different plane; same "exact reverse, readback
  every surface" discipline).
- `docs/runbooks/emergency-runtime-refresh.md` —
  surgical warm refresh that must not touch core infra.
