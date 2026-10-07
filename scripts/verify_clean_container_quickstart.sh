#!/usr/bin/env bash
# Prove the quickstart's dashboard step works on a machine that has nothing.
#
# The claim the dashboard step makes is that a reader needs only `uv`: no
# Node, no clone of any OmniNode repository, and no environment this project
# set up for them. A developer machine cannot check that claim, because it
# already has all three. This script checks it in a container that has none.
#
# WHAT IT PROVES, AND WHY IN THIS ORDER
#   1. `onex` installs from the published package alone.
#   2. One delegation runs and is recorded, so the dashboard has something
#      true to show. A dashboard that serves an empty page proves only that
#      a web server started.
#   3. `onex dashboard` answers `/` with the page itself within 120 seconds
#      of the command being given -- the first run downloads and verifies the
#      prebuilt pages, so the budget covers a download, not just a start.
#   4. The page's data route serves that run. This is the step that separates
#      "a page loaded" from "the reader can see their own work".
#
# The container is deliberately hostile to the claim: `OMNI_HOME` is unset,
# `node` and `git` are absent from the install path, and nothing is mounted
# from the host. If the step needs any of them, this script fails rather than
# passing on the host's leftovers.
#
# Checking that all six pages render their JavaScript needs a browser, and is
# a separate artifact; this script checks the server side, which is what the
# quickstart's own text promises.
#
# Usage: scripts/verify_clean_container_quickstart.sh [--image python:3.12-slim]
# Needs: docker (or podman via DOCKER=podman) and a provider key in
#        OPENROUTER_API_KEY, which is what the quickstart's step 3 sets up.

set -euo pipefail

IMAGE="python:3.12-slim"
DOCKER="${DOCKER:-docker}"
BUDGET_SECONDS=120

while [ $# -gt 0 ]; do
  case "$1" in
    --image) IMAGE="$2"; shift 2 ;;
    --budget) BUDGET_SECONDS="$2"; shift 2 ;;
    -h|--help) sed -n '2,31p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "REFUSED: unknown argument '$1'" >&2; exit 2 ;;
  esac
done

if ! command -v "$DOCKER" >/dev/null 2>&1; then
  echo "REFUSED: '$DOCKER' is not on PATH. This check needs a container runtime," >&2
  echo "         because its whole purpose is to run where the host's tools are not." >&2
  exit 2
fi

if [ -z "${OPENROUTER_API_KEY:-}" ]; then
  echo "REFUSED: OPENROUTER_API_KEY is unset, so step 2 below could not run a real" >&2
  echo "         delegation and the dashboard would be checked against no data." >&2
  echo "         Set the key the quickstart's step 3 describes and run this again." >&2
  exit 2
fi

echo "IMAGE          : $IMAGE"
echo "BUDGET         : ${BUDGET_SECONDS}s for / to answer 200"
echo

# `--network host` is not used: the dashboard is checked from inside the
# container, over its own loopback, which is the binding the command makes.
"$DOCKER" run --rm \
  --env "OPENROUTER_API_KEY=${OPENROUTER_API_KEY}" \
  --env "BUDGET_SECONDS=${BUDGET_SECONDS}" \
  --env OMNI_HOME= \
  --entrypoint /bin/bash \
  "$IMAGE" -s <<'IN_CONTAINER'
set -euo pipefail

fail() { echo; echo "FAILED: $*" >&2; exit 1; }

echo "== the container has nothing =="
# Proving the premise before relying on it: a check that silently ran with
# Node present would prove the opposite of what it claims.
command -v node >/dev/null 2>&1 && fail "this image ships node, so it cannot prove the no-Node claim"
command -v git  >/dev/null 2>&1 && echo "note: git is present but nothing below clones anything"
[ -z "${OMNI_HOME:-}" ] || fail "OMNI_HOME is set to '${OMNI_HOME}'"
echo "  no node, OMNI_HOME unset"

echo "== curl, for the checks themselves =="
apt-get update -qq >/dev/null
apt-get install -y -qq --no-install-recommends curl ca-certificates >/dev/null
echo "  installed"

echo "== uv, and onex from the published package alone =="
curl -fsSL https://astral.sh/uv/install.sh | sh >/dev/null
export PATH="$HOME/.local/bin:$PATH"
uv tool install omnimarket >/dev/null
onex --version || fail "onex did not install from the published package"

echo "== this machine's identity =="
onex local init || fail "onex local init failed on a clean machine"

echo "== one delegation, so the dashboard has something true to show =="
onex delegate --task-type code_generation \
  "reply with the single word ok" >/dev/null \
  || fail "the delegation failed, so there is no row for the dashboard to serve"
echo "  one run recorded"

echo "== onex dashboard: / must answer 200 within ${BUDGET_SECONDS}s =="
# The bind is an overlay key, not a flag: left to itself the command takes a
# free port, which a script cannot then poll. A fixed loopback port is the
# only thing this overlay changes.
cat >/tmp/overlay.yaml <<'OVERLAY'
dashboard:
  bind: "127.0.0.1:8765"
OVERLAY
onex dashboard --overlay /tmp/overlay.yaml >/tmp/dashboard.log 2>&1 &
DASH=$!
trap 'kill "$DASH" 2>/dev/null || true' EXIT

STARTED="$(date +%s)"
CODE=""
while [ "$(( $(date +%s) - STARTED ))" -lt "$BUDGET_SECONDS" ]; do
  kill -0 "$DASH" 2>/dev/null || {
    echo "--- the command exited; its output ---" >&2
    cat /tmp/dashboard.log >&2
    fail "onex dashboard exited before serving anything"
  }
  CODE="$(curl -s -o /tmp/root.html -w '%{http_code}' http://127.0.0.1:8765/ || true)"
  [ "$CODE" = "200" ] && break
  sleep 2
done
ELAPSED="$(( $(date +%s) - STARTED ))"
[ "$CODE" = "200" ] || {
  echo "--- the command's output ---" >&2
  cat /tmp/dashboard.log >&2
  fail "/ answered '${CODE:-nothing}' after ${ELAPSED}s, not 200"
}
# A 200 carrying no page is the failure a naive check passes: the pinned
# bundle is what makes this an HTML document rather than an empty body.
grep -qi '<script' /tmp/root.html \
  || fail "/ answered 200 but the body loads no JavaScript, so the page is a shell"
echo "  200 in ${ELAPSED}s, and the body loads its JavaScript"

echo "== the page's data route serves that run =="
curl -fsS http://127.0.0.1:8765/projections >/tmp/projections.json \
  || fail "/projections did not answer, so the page would render empty"
python3 - <<'PY' || exit 1
import json, sys, urllib.request

catalogue = json.load(open("/tmp/projections.json"))
topics = [row["topic"] for row in catalogue.get("topics", [])]
if not topics:
    sys.exit("FAILED: the catalogue is empty, so the dashboard has nothing to read")

served = 0
for topic in topics:
    with urllib.request.urlopen(
        f"http://127.0.0.1:8765/projection/{topic}", timeout=10
    ) as response:
        served += len(json.load(response).get("rows", []))
if served < 1:
    sys.exit(
        "FAILED: every exposure served zero rows, so the delegation above is "
        "not reaching the store the dashboard reads"
    )
print(f"  {served} row(s) served across {len(topics)} exposure(s)")
PY

echo
echo "PASSED: a container with no Node and no clone served the dashboard and one run."
IN_CONTAINER
