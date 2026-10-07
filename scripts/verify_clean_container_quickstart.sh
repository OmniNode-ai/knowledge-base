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
#   5. Each of the six pages renders in a headless browser with its JavaScript
#      actually executed. A 200 from the server proves a file was sent; it does
#      not prove the page runs. The six are the ones the local dashboard
#      declares: /overview, /runs, /workflow, /usage, /credentials, /api-keys.
#
#   6. A flipped byte in the cached bundle is refused, and nothing is served.
#      A run that only ever sees a good bundle cannot tell a working check from
#      an absent one, so the script breaks the cache on purpose at the end.
#
# The browser is Chromium driven by Playwright's PYTHON package, installed with
# `uv`. Playwright downloads its own browser binary and needs no Node, so the
# no-Node claim survives this step -- which is the reason the browser check
# belongs in this script rather than beside it.
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

echo "== each of the six pages renders, with its JavaScript executed =="
# Chromium's own runtime libraries; the browser binary itself comes from
# Playwright, not from apt, so this list does not reintroduce Node.
apt-get install -y -qq --no-install-recommends \
  libglib2.0-0 libnss3 libnspr4 libdbus-1-3 libatk1.0-0 libatk-bridge2.0-0 \
  libcups2 libdrm2 libatspi2.0-0 libx11-6 libxcomposite1 libxdamage1 \
  libxext6 libxfixes3 libxrandr2 libgbm1 libxkbcommon0 libpango-1.0-0 \
  libcairo2 libasound2 fonts-liberation >/dev/null

uv tool install playwright >/dev/null
playwright install chromium >/dev/null 2>&1 \
  || fail "playwright could not install chromium, so the pages cannot be checked"

uv tool run --from playwright python - <<'BROWSER' || exit 1
import sys
from playwright.sync_api import sync_playwright

# The paths src/navigation/page-routes.ts declares for the local dashboard.
PAGES = ["/overview", "/runs", "/workflow", "/usage", "/credentials", "/api-keys"]
BASE = "http://127.0.0.1:8765"

failures = []
with sync_playwright() as play:
    browser = play.chromium.launch(args=["--no-sandbox"])
    for path in PAGES:
        page = browser.new_page()
        errors = []
        # A page that throws on load still returns 200 and still renders a
        # container, so the console and the page errors are the real signal.
        page.on("pageerror", lambda exc: errors.append(f"uncaught: {exc}"))
        page.on(
            "console",
            lambda msg: errors.append(f"console.error: {msg.text}")
            if msg.type == "error"
            else None,
        )
        # A request for a script or stylesheet that 404s means the bundle is
        # incomplete, which is exactly what a hand-built archive gets wrong.
        page.on(
            "response",
            lambda res: errors.append(f"{res.status} for {res.url}")
            if res.status >= 400 and res.request.resource_type in ("script", "stylesheet")
            else None,
        )
        try:
            response = page.goto(f"{BASE}{path}", wait_until="networkidle", timeout=30_000)
            if response is None or response.status != 200:
                errors.append(f"navigation returned {response and response.status}")
            # React must have mounted something: an empty root is the blank-page
            # failure a status check cannot see.
            body = page.inner_text("body").strip()
            if len(body) < 20:
                errors.append(f"rendered only {len(body)} characters of text")
        except Exception as exc:  # noqa: BLE001 - the reason is for a human
            errors.append(f"{type(exc).__name__}: {exc}")
        finally:
            page.close()
        if errors:
            failures.append((path, errors))
            print(f"  FAIL {path}")
            for line in errors:
                print(f"         {line}")
        else:
            print(f"  ok   {path}")
    browser.close()

if failures:
    sys.exit(f"FAILED: {len(failures)} of {len(PAGES)} pages did not render")
print(f"  all {len(PAGES)} pages rendered")
BROWSER

echo "== a flipped byte in the cached bundle must be refused =="
# The other half of the claim, and the one a passing run cannot show: the
# verification only matters if a bad bundle actually stops the command. The
# cache is keyed by digest, so this flips a byte in the archive the previous
# step verified and starts the command again.
kill "$DASH" 2>/dev/null || true
wait "$DASH" 2>/dev/null || true

ARCHIVE="$(find "$HOME/.omninode/dashboard/bundles" -maxdepth 1 -name '*.tar.gz' | head -1)"
[ -n "$ARCHIVE" ] || fail "no cached bundle was found, so the refusal cannot be checked"
python3 - "$ARCHIVE" <<'FLIP'
import sys, pathlib
p = pathlib.Path(sys.argv[1])
b = bytearray(p.read_bytes())
# A byte in the middle of the compressed payload: still a readable file, with
# different contents. Flipping the first byte would fail as "not a gzip file",
# which a weaker check could pass for the wrong reason.
i = len(b) // 2
b[i] ^= 0xFF
p.write_bytes(bytes(b))
print(f"  flipped one byte at offset {i} of {len(b)}")
FLIP

set +e
onex dashboard --overlay /tmp/overlay.yaml >/tmp/tampered.log 2>&1
TAMPER_EXIT=$?
set -e
if [ "$TAMPER_EXIT" -eq 0 ]; then
  cat /tmp/tampered.log >&2
  fail "the command exited 0 with a tampered bundle, so the pin is decorative"
fi
grep -qi "does not match the pin" /tmp/tampered.log || {
  echo "--- the command's output ---" >&2
  cat /tmp/tampered.log >&2
  fail "the command refused, but not for the digest: the message must name the mismatch"
}
# And it must not be serving the pages anyway. Written as an `if`, not as
# `grep -q ... && fail`: under `set -e` that form exits non-zero on the GOOD
# path, where grep correctly finds no 200.
STILL="$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 http://127.0.0.1:8765/ || true)"
if [ "$STILL" = "200" ]; then
  fail "the tampered bundle is still being served on the port"
fi
echo "  refused, naming the digest mismatch, and nothing is served"

echo
echo "PASSED: a container with no Node and no clone served the dashboard, one run,"
echo "        and all six pages in a headless browser; a flipped byte was refused."
IN_CONTAINER
