---
type: runbook
status: current
date: "2026-07-21"
title: "Managed-staging one-tenant canary — Postgres surface provisioning (bring-up)"
topics: [omnibase-infra, managed, staging, canary, postgres]
refs: []
---

# Managed-staging one-tenant canary — Postgres surface provisioning (bring-up)

This runbook provisions the **Postgres landing surface** for the backend-only,
one-gateway, one-synthetic-tenant MSK canary: a dedicated **canary logical DB**, the
**delivery/replay landing table**, and a **scoped runtime credential**, ending in a
**psql readback that proves the landing table exists**. Without this surface, B11's
correlation-linked readback has nowhere to land.

Ticket: **<ticket>** (Lane B / task **B12**).
It is the Postgres **bring-up** counterpart to the teardown spec
`docs/runbooks/managed-staging-canary-teardown-rollback.md`
(B13, whose step **T-5** reverses everything below).

The plan docs cited below live in the **`OmniNode-ai/omni_home` registry** (not in this
repo), under its `docs/plans/` tree; paths are given as plain code, not repo-relative
links.

- Plan of record: `omni_home:docs/plans/2026-07-17-managed-staging-verified-state-and-task-split.md`
  — task **B12** (this surface), **B6** (the projection contract the table shape is
  derived from), **B7** (canary topic/group epoch `mstg1`), **B11** (the canary run that
  writes here).
- Ownership/authority model: `omni_home:docs/plans/2026-07-17-managed-staging-agent-driven-execution-plan.md`.

> **This document is a spec. It executes nothing.** Every numbered step in §3 is a
> **live mutation or a live connection** and is **HELD FOR OPERATOR**. Per the
> agent-driven execution plan, the agent presents one reviewed step at a time (exact
> command, expected output, rollback), and **Jonah issues GO and executes by default**.
> Authoring or reading this runbook authorizes **no** DB/table/role/credential creation
> and **no** AWS/RDS mutation. There is no autonomous provisioning.

> **Plane scope.** This targets the single `dev`-tagged managed plane (account
> `272493677981`, `us-east-1`, RDS instance **`omninode-dev-postgres`**, postgres 16.13,
> single-AZ, private). It is **not** the `<onex-host>` runtime lanes and **not** prod. The
> prod-promotion grant gate (CLAUDE.md §2a/§12) does **not** apply here because no prod
> resource is touched — but the "each live mutation needs an explicit operator GO" rule
> still governs every step below.

---

## 0. What gets created (and the naming contract)

| Object | Default name | Notes |
|---|---|---|
| Canary logical DB | `omninode_canary_mstg1` | Epoch-scoped to the B7 `mstg1` canary epoch. A re-run bumps the epoch (`omninode_canary_mstg2`, …) for a provably disjoint surface. |
| Landing table | `delivery_replay_canary_projection` | Columns derived field-by-field from B6's `ModelReplayProjection` (<ticket>). DDL: `docker/migrations/canary/forward/001_create_delivery_replay_canary_projection.sql`. |
| Scoped runtime role | `role_canary_mstg1` | `LOGIN`, scoped to the canary DB only; can `SELECT`/`INSERT`/`UPDATE` the landing table. No access to any other logical DB. |

**Tenant-scoping is out of scope** (decision #5, pending Adil). The one-tenant canary
has exactly one synthetic tenant; the landing table carries **no** `tenant_id` column
and **no** multi-tenant partitioning. Do not add either here.

---

## 1. Prerequisites (read-only — safe to run to prepare a step)

These commands **read** state to assemble the parameters; they mutate nothing. Even so,
run them only when preparing the corresponding GO step.

```bash
# --- Parameters (adjust epoch for a re-run; nothing is created by setting these) ---
CANARY_EPOCH="mstg1"
CANARY_DB="omninode_canary_${CANARY_EPOCH}"
CANARY_ROLE="role_canary_${CANARY_EPOCH}"

# --- Resolve the RDS endpoint from SSM (per plan §1: the only params stored are
#     /omninode/dev/postgres/rds_endpoint and .../rds_port). Do NOT hardcode it. ---
CANARY_PGHOST="$(aws ssm get-parameter --region us-east-1 \
  --name /omninode/dev/postgres/rds_endpoint --query 'Parameter.Value' --output text)"
CANARY_PGPORT="$(aws ssm get-parameter --region us-east-1 \
  --name /omninode/dev/postgres/rds_port --query 'Parameter.Value' --output text)"

# --- Superuser for the admin steps (§3.1–§3.3). The RDS master user + password are
#     held by the operator / secret store; never inline the password on the CLI. ---
CANARY_ADMIN_USER="postgres"        # RDS master user
export PGSSLMODE="verify-full"      # transport TLS + hostname verification (plan A4/B4)
# PGPASSWORD is exported interactively by the operator at GO time; never committed.
```

> **TLS.** `omninode-dev-postgres` enforces `rds.force_ssl=1`, but that guarantees
> transport TLS only. Connect with `PGSSLMODE=verify-full` and the RDS CA bundle
> (`rds-ca-rsa2048-g1`, `PGSSLROOTCERT=<ca-bundle>`), per plan tasks **A4/B4**. If the CA
> bundle is not yet mounted, use `require` for this provisioning step and record the gap
> — but the canary runtime path must reach `verify-full` before B11.

---

## 2. Ordering

Run §3 in order. Each step is **HELD FOR OPERATOR**; the agent presents the exact
command + expected readback + rollback, and Jonah issues GO.

1. §3.1 Create the canary logical DB.
2. §3.2 Apply the landing-table migration into that DB.
3. §3.3 Create + scope the runtime role/credential.
4. §3.4 **Readback** — prove the landing table exists (the acceptance gate).

---

## 3. Provisioning steps (each HELD FOR OPERATOR)

### 3.1 Create the canary logical DB — HELD

RDS `DBName=null`, so the logical DB is hand-created. Idempotent guard first.

```bash
# GUARD (read-only): does the canary DB already exist?
psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ADMIN_USER" -d postgres -tAc \
  "SELECT 1 FROM pg_database WHERE datname = '${CANARY_DB}';"
# -> empty = does not exist (proceed); '1' = already exists (skip CREATE).

# GO (mutation): create the DB (CREATE DATABASE cannot run inside a txn / with IF NOT EXISTS).
psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ADMIN_USER" -d postgres -v ON_ERROR_STOP=1 -c \
  "CREATE DATABASE ${CANARY_DB};"
```

Expected readback: `CREATE DATABASE`. Rollback: `DROP DATABASE ${CANARY_DB};` (B13 T-5).

### 3.2 Apply the landing-table migration into the canary DB — HELD

Apply the committed, DB-agnostic forward migration **into the canary DB** (`-d "$CANARY_DB"`).
Run from the repo root so the relative path resolves. Idempotent (`IF NOT EXISTS`).

```bash
# GO (mutation): apply the landing-table DDL into the canary DB.
psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ADMIN_USER" \
  -d "$CANARY_DB" -v ON_ERROR_STOP=1 \
  -f docker/migrations/canary/forward/001_create_delivery_replay_canary_projection.sql
```

Expected readback: `CREATE TABLE`, two `CREATE INDEX`, `CREATE FUNCTION`, `CREATE TRIGGER`
(and `DROP TRIGGER` on a clean first apply). Rollback:
`-f docker/migrations/canary/rollback/rollback_001_delivery_replay_canary_projection.sql`.

### 3.3 Create and scope the runtime credential — HELD

A dedicated role that can reach **only** the canary DB and only the landing table.
Generate the password with `openssl rand -hex 32`; it goes into the k8s Secret / the secrets manager
for the canary runtime — **never** committed and never inlined in a shell history file.

```bash
# Operator generates the secret out-of-band (example; capture into the secret store):
#   CANARY_ROLE_PW="$(openssl rand -hex 32)"

# GO (mutation, run against the CANARY DB): create the login role and scope it.
psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ADMIN_USER" \
  -d "$CANARY_DB" -v ON_ERROR_STOP=1 -v role="$CANARY_ROLE" <<'SQL'
-- Create the login role if absent (password set separately — see below).
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = :'role') THEN
    EXECUTE format('CREATE ROLE %I LOGIN', :'role');
  END IF;
END
$$;

-- Fence the DB: only the scoped role (and admins) may connect.
REVOKE CONNECT ON DATABASE current_database() FROM PUBLIC;
GRANT  CONNECT ON DATABASE current_database() TO :"role";

-- Minimal table privileges for the readback landing (upsert = INSERT + UPDATE).
GRANT USAGE ON SCHEMA public TO :"role";
GRANT SELECT, INSERT, UPDATE ON delivery_replay_canary_projection TO :"role";
SQL

# GO (mutation): set the role password from the secret store (kept off the CLI/history).
#   psql ... -d "$CANARY_DB" -c "ALTER ROLE ${CANARY_ROLE} WITH PASSWORD '<from-secret-store>';"
```

Expected readback: `CREATE ROLE`/`DO`, `REVOKE`, `GRANT` ×3, then `ALTER ROLE`.
Rollback: `DROP ROLE ${CANARY_ROLE};` after revoking its grants (B13 T-5 cred rotation).

### 3.4 Readback — prove the landing table exists (ACCEPTANCE GATE) — HELD

Read-only, but a live connection — still HELD. This is the proof B11 depends on.

```bash
# (a) Existence proof: to_regclass returns the table's OID name, or NULL if absent.
psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ADMIN_USER" \
  -d "$CANARY_DB" -tAc "SELECT to_regclass('public.delivery_replay_canary_projection');"
# EXPECTED: delivery_replay_canary_projection   (NULL/empty => FAIL, table missing)

# (b) Column contract: assert every derived column is present with the right type.
psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ADMIN_USER" \
  -d "$CANARY_DB" -c "\d public.delivery_replay_canary_projection"
# EXPECTED columns: correlation_id (uuid, PK, not null), projection_checksum (text,
# not null), cursor_token (text, not null), cursor_positions (jsonb), cursor_event_count
# (bigint), event_count (bigint), compared (bool), diverged (bool), divergence_reasons
# (jsonb), created_at (timestamptz), updated_at (timestamptz); trigger
# trg_delivery_replay_canary_projection_updated_at present.

# (c) Machine-checkable column set (11 rows).
psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ADMIN_USER" \
  -d "$CANARY_DB" -tAc \
  "SELECT column_name, data_type FROM information_schema.columns
     WHERE table_name = 'delivery_replay_canary_projection' ORDER BY ordinal_position;"

# (d) Scoped-role reachability (optional, from the runtime cred): the role can read
#     the empty table (0 rows) and cannot reach any other logical DB.
#   PGPASSWORD=<role-pw> psql -h "$CANARY_PGHOST" -p "$CANARY_PGPORT" -U "$CANARY_ROLE" \
#     -d "$CANARY_DB" -tAc "SELECT count(*) FROM delivery_replay_canary_projection;"  # -> 0
```

**Acceptance:** step (a) returns `delivery_replay_canary_projection` (not NULL) and (c)
lists all 11 columns. Record this readback into the B11 evidence packet + OCC receipt.

---

## 4. Idempotency & re-run

- §3.1 is guarded (skip if the DB exists); §3.2 uses `IF NOT EXISTS` / `OR REPLACE`
  throughout; §3.3 guards the role with `IF NOT EXISTS`. The full sequence is safe to
  re-run against a partially-provisioned DB.
- **Fresh epoch:** to mint a disjoint surface for a canary re-run, set
  `CANARY_EPOCH=mstg2` in §1 and re-run §3 — the DDL is DB-agnostic; only the DB name and
  role change. Align the epoch with the B7 topic/group epoch bump.

---

## 5. Held-for-operator status of the live steps

Every step in §3 is **HELD FOR OPERATOR** and is **not** authorized by this runbook:

- §3.1 `CREATE DATABASE` (logical DB),
- §3.2 applying the landing-table migration,
- §3.3 `CREATE ROLE` / grants / `ALTER ROLE ... PASSWORD`,
- §3.4 the live readback connection.

The agent presents each step with its exact command, expected readback, and rollback —
**one reviewed step at a time**; Jonah issues GO and executes by default. This document
adds the spec only; it performs no live mutation and grants no standing authority to
execute one.

---

## Related

- Landing DDL + rollback: `docker/migrations/canary/`
- Teardown / abort / rollback (reverses this): `managed-staging-canary-teardown-rollback.md`
- B6 projection contract the table shape derives from: omnimarket
  `node_delivery_replay_projection_compute` (<ticket>) — output model
  `ModelReplayProjection`.
