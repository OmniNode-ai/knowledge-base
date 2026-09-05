---
type: plan
status: active
date: "2026-03-31"
title: "Delegation pipeline end-to-end fix"
topics: [delegation, routing, llm-backends, classification]
---

# Delegation Pipeline E2E Fix — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan phase-by-phase.

**Goal:** Fix the broken delegation pipeline so prompts actually route to local LLMs, Gemini CLI, and Codex CLI for delegatable tasks (pr-polish, test writing, documentation, research) — verified by live delegation events on the dashboard.

**Architecture:** Three tracks executed sequentially in one worktree. Track A fixes the broken classifier (threshold, formula, allow-list). Track B adds Gemini/Codex CLI as delegation backends by generalizing the proven `aggregate_reviews.py` subprocess pattern. Track C adds GLM as an OpenAI-compatible LLM endpoint.

**Tech Stack:** Python 3.12, Pydantic, subprocess (Gemini/Codex CLI), httpx/urllib (OpenAI-compat API), pytest

---

## Known Types Inventory

> Types discovered in the repository that are relevant to this plan.
> Any new type introduced by a task below MUST reference this inventory
> and state why an existing type does not suffice.

- `TaskIntent` — `src/omniclaude/lib/task_classifier.py:18` — Enum: DEBUG, IMPLEMENT, DATABASE, REFACTOR, RESEARCH, TEST, DOCUMENT, UNKNOWN
- `ModelDelegationScore` — `src/omniclaude/lib/task_classifier.py:44` — dataclass: delegatable, delegate_to_model, confidence, estimated_savings_usd, reasons
- `TaskClassifier` — `src/omniclaude/lib/task_classifier.py:56` — Main classifier class, keyword-based
- `LlmEndpointPurpose` — `src/omniclaude/config/model_local_llm_config.py:66` — Enum: ROUTING, CODE_ANALYSIS, EMBEDDING, GENERAL, VISION, FUNCTION_CALLING, REASONING
- `LlmEndpointConfig` — `src/omniclaude/config/model_local_llm_config.py:92` — Pydantic model for endpoint config
- `ModelAggregateResult` — `plugins/onex/skills/hostile_reviewer/_lib/aggregate_reviews.py:107` — Multi-model review result
- `run_gemini()` — `aggregate_reviews.py:240` — Subprocess dispatch to `gemini` CLI
- `run_codex()` — `aggregate_reviews.py:312` — Subprocess dispatch to `codex review` CLI
- `run_http_model()` — `aggregate_reviews.py:357` — OpenAI-compat HTTP call to vLLM endpoints
- `_HANDLER_ROUTING` — `delegation_orchestrator.py:260` — Maps intent → (endpoint_purpose, system_prompt, handler_name, min_response_length)

---

## Task 1: Fix classification confidence threshold and formula

**Files:**
- Modify: `src/omniclaude/lib/task_classifier.py:321` (threshold), `:420-467` (formula)
- Test: `tests/unit/lib/test_task_classifier.py`

**Step 1: Write failing test — realistic prompts should be delegatable**

```python
def test_research_prompt_is_delegatable():
    """A normal research prompt should be classified as delegatable."""
    classifier = TaskClassifier()
    score = classifier.is_delegatable("explain how the delegation pipeline works in this codebase")
    assert score.delegatable is True
    assert score.confidence >= 0.4

def test_document_prompt_is_delegatable():
    classifier = TaskClassifier()
    score = classifier.is_delegatable("write documentation for the task classifier module")
    assert score.delegatable is True

def test_test_prompt_is_delegatable():
    classifier = TaskClassifier()
    score = classifier.is_delegatable("write unit tests for the delegation orchestrator")
    assert score.delegatable is True
```

**Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/lib/test_task_classifier.py -v -k "delegatable"`
Expected: FAIL — confidence too low to pass 0.9 threshold

**Step 3: Fix the threshold and formula**

In `task_classifier.py`:

1. Line 321: Change `DELEGATION_CONFIDENCE_THRESHOLD: float = 0.9` → `0.4`
2. Lines 420-467: Change confidence formula from `matched / total_keywords` to:
   ```python
   # Any 2+ keyword matches = base confidence 0.5
   # Each additional match adds 0.1 (capped at 0.95)
   if intent_keywords_matched >= 2:
       confidence = min(0.5 + (intent_keywords_matched - 2) * 0.1, 0.95)
   elif intent_keywords_matched == 1:
       confidence = 0.3
   else:
       confidence = 0.0
   ```

**Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/lib/test_task_classifier.py -v -k "delegatable"`
Expected: PASS

**Step 5: Commit**

```bash
git add src/omniclaude/lib/task_classifier.py tests/unit/lib/test_task_classifier.py
git commit -m "fix: lower delegation threshold to 0.4, fix confidence formula for sparse prompts"
```

---

## Task 2: Expand DELEGATABLE_INTENTS to include IMPLEMENT

**Files:**
- Modify: `src/omniclaude/lib/task_classifier.py:311-316`
- Test: `tests/unit/lib/test_task_classifier.py`

**Step 1: Write failing test**

```python
def test_implement_prompt_is_delegatable():
    """Implementation tasks (like PR polish) should be delegatable."""
    classifier = TaskClassifier()
    score = classifier.is_delegatable("fix the merge conflict in this PR and rebase on main")
    assert score.delegatable is True
    assert score.primary_intent == TaskIntent.IMPLEMENT
```

**Step 2: Run test — verify FAIL**

**Step 3: Add IMPLEMENT to DELEGATABLE_INTENTS**

```python
DELEGATABLE_INTENTS: frozenset[TaskIntent] = frozenset(
    {
        TaskIntent.DOCUMENT,
        TaskIntent.TEST,
        TaskIntent.RESEARCH,
        TaskIntent.IMPLEMENT,  # PR polish, code fixes
    }
)
```

Also add IMPLEMENT to `_HANDLER_ROUTING` in `delegation_orchestrator.py`:
```python
"implement": ("code_analysis", _SYSTEM_PROMPT_IMPLEMENT, "code_fix", 50),
```

Add `_SYSTEM_PROMPT_IMPLEMENT`:
```python
_SYSTEM_PROMPT_IMPLEMENT = (
    "You are a senior software engineer. Fix the described issue precisely. "
    "Output only the corrected code with brief explanation."
)
```

**Step 4: Run test — verify PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add IMPLEMENT to delegatable intents for PR polish delegation"
```

---

## Task 3: Add Gemini CLI as delegation backend

**Files:**
- Create: `plugins/onex/hooks/lib/cli_delegation_backends.py`
- Modify: `plugins/onex/hooks/lib/delegation_orchestrator.py`
- Test: `tests/unit/hooks/test_cli_delegation_backends.py`

**Not reusing `run_gemini()` from `aggregate_reviews.py` because:** That function is hostile-review-specific (hardcoded review prompt, returns findings JSON). We need a general-purpose dispatch that accepts any prompt and returns text.

**Step 1: Write failing test**

```python
def test_gemini_backend_returns_response(monkeypatch):
    """Gemini CLI backend should return text response."""
    import subprocess
    def mock_run(*args, **kwargs):
        result = subprocess.CompletedProcess(args=args[0], returncode=0, stdout="Here is the documentation...", stderr="")
        return result
    monkeypatch.setattr(subprocess, "run", mock_run)

    from plugins.onex.hooks.lib.cli_delegation_backends import run_gemini_delegation
    result = run_gemini_delegation("write docs for this module", timeout=30)
    assert result is not None
    assert "documentation" in result.lower()

def test_codex_backend_returns_response(monkeypatch):
    """Codex CLI backend should return text response."""
    import subprocess
    def mock_run(*args, **kwargs):
        result = subprocess.CompletedProcess(args=args[0], returncode=0, stdout="def test_example():\n    assert True", stderr="")
        return result
    monkeypatch.setattr(subprocess, "run", mock_run)

    from plugins.onex.hooks.lib.cli_delegation_backends import run_codex_delegation
    result = run_codex_delegation("write tests for the classifier", timeout=60)
    assert result is not None
```

**Step 2: Run tests — verify FAIL**

**Step 3: Create `cli_delegation_backends.py`**

```python
"""CLI delegation backends for Gemini and Codex.

Generalizes the subprocess dispatch pattern from aggregate_reviews.py
for general-purpose prompt delegation (not just hostile review).
"""
from __future__ import annotations

import shutil
import subprocess
import sys


def run_gemini_delegation(prompt: str, *, timeout: int = 60) -> str | None:
    """Dispatch prompt to Gemini CLI. Returns response text or None on failure."""
    if not shutil.which("gemini"):
        print("[gemini] CLI not found", file=sys.stderr)
        return None
    try:
        result = subprocess.run(
            ["gemini", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        response = result.stdout.strip()
        if not response:
            print(f"[gemini] empty response (rc={result.returncode})", file=sys.stderr)
            return None
        return response
    except subprocess.TimeoutExpired:
        print(f"[gemini] timed out after {timeout}s", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[gemini] failed: {e}", file=sys.stderr)
        return None


def run_codex_delegation(prompt: str, *, timeout: int = 120) -> str | None:
    """Dispatch prompt to Codex CLI. Returns response text or None on failure."""
    if not shutil.which("codex"):
        print("[codex] CLI not found", file=sys.stderr)
        return None
    try:
        result = subprocess.run(
            ["codex", "-p", prompt],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        response = result.stdout.strip()
        if not response:
            print(f"[codex] empty response (rc={result.returncode})", file=sys.stderr)
            return None
        return response
    except subprocess.TimeoutExpired:
        print(f"[codex] timed out after {timeout}s", file=sys.stderr)
        return None
    except Exception as e:
        print(f"[codex] failed: {e}", file=sys.stderr)
        return None
```

**Step 4: Run tests — verify PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add Gemini and Codex CLI delegation backends"
```

---

## Task 4: Wire CLI backends into delegation orchestrator as fallback

**Files:**
- Modify: `plugins/onex/hooks/lib/delegation_orchestrator.py`
- Test: `tests/unit/hooks/test_delegation_orchestrator.py`

**Step 1: Write failing test**

```python
def test_orchestrator_falls_back_to_gemini_when_local_llm_down(monkeypatch):
    """When local LLM endpoint is unreachable, fallback to Gemini CLI."""
    # Mock local LLM to fail
    monkeypatch.setenv("LLM_CODER_URL", "http://localhost:99999")  # unreachable
    monkeypatch.setenv("ENABLE_LOCAL_DELEGATION", "true")
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")

    # Mock Gemini CLI to succeed
    import subprocess
    original_run = subprocess.run
    def mock_run(*args, **kwargs):
        if args[0][0] == "gemini":
            return subprocess.CompletedProcess(args=args[0], returncode=0, stdout="Generated documentation here", stderr="")
        return original_run(*args, **kwargs)
    monkeypatch.setattr(subprocess, "run", mock_run)

    result = orchestrate_delegation(
        prompt="write documentation for this module",
        correlation_id="test-123",
    )
    assert result["delegated"] is True
    assert result["handler"] == "gemini-cli"
```

**Step 2: Run test — verify FAIL**

**Step 3: Add fallback chain to `orchestrate_delegation()`**

After the existing local LLM call fails (returns None or times out), add:

```python
# Fallback 1: Gemini CLI (if GEMINI_API_KEY set)
if response is None and os.environ.get("GEMINI_API_KEY"):
    from cli_delegation_backends import run_gemini_delegation
    response = run_gemini_delegation(truncated_prompt, timeout=60)
    if response:
        handler_name = "gemini-cli"
        model_name = "gemini-cli"

# Fallback 2: Codex CLI (if available)
if response is None and shutil.which("codex"):
    from cli_delegation_backends import run_codex_delegation
    response = run_codex_delegation(truncated_prompt, timeout=120)
    if response:
        handler_name = "codex-cli"
        model_name = "codex-cli"
```

**Step 4: Run tests — verify PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add Gemini/Codex CLI fallback chain in delegation orchestrator"
```

---

## Task 5: Add `api_key` field to LlmEndpointConfig

**Files:**
- Modify: `src/omniclaude/config/model_local_llm_config.py`
- Test: `tests/unit/config/test_local_llm_config.py`

**Step 1: Write failing test**

```python
def test_endpoint_config_accepts_api_key():
    config = LlmEndpointConfig(
        name="glm", url="http://api.example.com", model_name="glm-4",
        purpose=LlmEndpointPurpose.GENERAL, priority=5, api_key="sk-test"
    )
    assert config.api_key == "sk-test"

def test_endpoint_config_api_key_defaults_empty():
    config = LlmEndpointConfig(
        name="local", url="http://localhost:8000", model_name="qwen",
        purpose=LlmEndpointPurpose.CODE_ANALYSIS, priority=5
    )
    assert config.api_key == ""
```

**Step 2: Run test — verify FAIL**

**Step 3: Add field**

```python
class LlmEndpointConfig(BaseModel):
    # ... existing fields ...
    api_key: str = Field(default="", description="API key for authenticated endpoints (GLM, cloud APIs)")
```

**Step 4: Run test — verify PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add api_key field to LlmEndpointConfig for cloud LLM endpoints"
```

---

## Task 6: Add GLM (ChatGLM) as OpenAI-compatible LLM endpoint

**Files:**
- Modify: `src/omniclaude/config/model_local_llm_config.py`
- Modify: `plugins/onex/hooks/lib/delegation_orchestrator.py`
- Test: `tests/unit/config/test_local_llm_config.py`

**Not creating a new endpoint class because:** `LlmEndpointConfig` already supports any OpenAI-compatible API. GLM just needs a new env var entry.

**Step 1: Write failing test**

```python
def test_glm_endpoint_registered_when_env_set(monkeypatch):
    """GLM endpoint should appear in registry when GLM_API_URL is set."""
    monkeypatch.setenv("LLM_GLM_URL", "http://api.example.com/v1")
    monkeypatch.setenv("LLM_GLM_MODEL_NAME", "glm-4-plus")
    monkeypatch.setenv("LLM_GLM_API_KEY", "test-key")
    registry = LocalLlmEndpointRegistry()
    endpoint = registry.get_by_purpose(LlmEndpointPurpose.GENERAL)
    assert endpoint is not None
```

**Step 2: Run test — verify FAIL**

**Step 3: Add GLM to endpoint registry**

In `model_local_llm_config.py`, add to the endpoint initialization:

```python
# GLM (ChatGLM) — OpenAI-compatible API
glm_url = os.environ.get("LLM_GLM_URL", "")
if glm_url:
    self._endpoints.append(LlmEndpointConfig(
        name="glm",
        url=glm_url,
        model_name=os.environ.get("LLM_GLM_MODEL_NAME", "glm-4-plus"),
        purpose=LlmEndpointPurpose.GENERAL,
        priority=7,
        api_key=os.environ.get("LLM_GLM_API_KEY", ""),
    ))
```

In `delegation_orchestrator.py`, update `_call_llm_with_system_prompt()` to pass `api_key` header when the endpoint has one:

```python
headers = {"Content-Type": "application/json"}
if endpoint.api_key:
    headers["Authorization"] = f"Bearer {endpoint.api_key}"
```

**Step 4: Run test — verify PASS**

**Step 5: Commit**

```bash
git commit -m "feat: add GLM (ChatGLM) as OpenAI-compatible LLM endpoint"
```

---

## Task 7: Fix tiktoken dependency in plugin venv

**Files:**
- Modify: `pyproject.toml` (add tiktoken to dependencies if missing)
- Verify: Plugin venv after deploy

**Step 1: Check if tiktoken is in dependencies**

```bash
grep tiktoken pyproject.toml
```

**Step 2: If missing, add it**

```bash
uv add tiktoken
```

**Step 3: Rebuild and verify**

```bash
uv sync
uv run python -c "import tiktoken; print(tiktoken.__version__)"
```

**Step 4: Deploy plugin and verify hooks don't crash**

```bash
deploy_local_plugin --execute
```

**Step 5: Commit**

```bash
git commit -m "fix: add tiktoken dependency to fix plugin hook crashes"
```

---

## Task 8: Kill stale daemon processes and verify live delegation

**Files:**
- No code changes — operational verification

**Step 1: Kill stale daemons**

```bash
# Find all delegation daemon processes
ps aux | grep delegation_daemon | grep -v grep
# Kill old ones (keep only the newest)
kill <stale_pids>
```

**Step 2: Restart delegation daemon**

```bash
python plugins/onex/hooks/lib/delegation_daemon.py --stop
python plugins/onex/hooks/lib/delegation_daemon.py --start
```

**Step 3: Verify delegation fires on a real prompt**

```bash
# Send test prompt via daemon socket
echo '{"prompt": "write documentation for the task classifier", "correlation_id": "test-e2e", "session_id": "test"}' | socat - UNIX-CONNECT:/tmp/omniclaude-delegation.sock
```

Expected: `{"delegated": true, "response": "...", "model": "...", "handler": "..."}`

**Step 4: Verify Kafka event emitted**

```bash
docker exec omnibase-infra-redpanda rpk topic consume onex.evt.omniclaude.task-delegated.v1 --num 1 --offset end
```

Expected: Event with `delegation_success: true`

**Step 5: Commit verification receipt**

```bash
git commit -m "chore: verify delegation pipeline e2e — events flowing"
```

---

## Task 9: Add env vars for GLM to ~/.omnibase/.env

**Files:**
- Modify: `~/.omnibase/.env` (via `editenv`)

**Step 1: Add GLM configuration**

```bash
editenv
```

Add:
```
LLM_GLM_URL=https://open.bigmodel.cn/api/paas/v4
LLM_GLM_MODEL_NAME=glm-4-plus
LLM_GLM_API_KEY=<user's GLM API key>
```

**Step 2: Source and verify**

```bash
source ~/.omnibase/.env
echo "GLM: $LLM_GLM_URL / $LLM_GLM_MODEL_NAME"
```

**Step 3: Test GLM endpoint**

```bash
curl -sf "$LLM_GLM_URL/chat/completions" \
  -H "Authorization: Bearer $LLM_GLM_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"model": "glm-4-plus", "messages": [{"role": "user", "content": "hello"}], "max_tokens": 50}'
```

---

## Task 10: Deploy plugin and run full e2e verification

**Files:**
- No new code — integration verification

**Step 1: Deploy plugin**

```bash
cd "$WORKSPACE_ROOT/omniclaude"
deploy_local_plugin --execute
```

**Step 2: Restart delegation daemon**

```bash
python plugins/onex/hooks/lib/delegation_daemon.py --stop
python plugins/onex/hooks/lib/delegation_daemon.py --start
```

**Step 3: Verify each delegation surface**

Test prompts that should delegate:
1. "explain how the delegation pipeline works" → should delegate to local LLM or Gemini
2. "write documentation for the task classifier" → should delegate (DOCUMENT intent)
3. "write unit tests for the orchestrator" → should delegate (TEST intent)
4. "fix the merge conflict in this file" → should delegate (IMPLEMENT intent)

For each, verify:
- Classification returns `delegatable: true` with confidence > 0.4
- Response comes from delegated model (not Claude)
- Kafka event `onex.evt.omniclaude.task-delegated.v1` emitted
- Dashboard shows delegation event

**Step 4: Verify fallback chain**

1. Stop local LLM servers (or set URL to unreachable)
2. Send delegatable prompt
3. Verify Gemini CLI picks it up as fallback
4. Restart local LLMs, verify they take priority again

---

routing: ticket-pipeline
