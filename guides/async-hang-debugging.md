---
type: guide
status: current
date: "2026-08-25"
title: "Async Hang Debugging Guide"
topics: [python, asyncio, pytest, debugging, ci]
refs: []
---

# Async Hang Debugging Guide

**Issue**: a test suite hangs with a timeout in CI, typically with pytest-asyncio strict mode

**Source**: omnibase_core `docs/troubleshooting/ASYNC_HANG_DEBUGGING.md`

> **2026-08-25 migration correction.** The original document was built around a specific
> historical incident, citing exact line numbers in
> `src/omnibase_core/mixins/mixin_workflow_support.py`. Verified live: that file does not
> exist in omnibase_core@dev — it has since been removed or renamed, and the specific
> incident record (line numbers, a dated "Historical Incidents" entry, a correlation ID) can
> no longer be verified against any live artifact. Rather than republish a dated incident
> against a file that no longer exists, this migrated copy keeps the **general, still-valid**
> debugging technique — an unawaited coroutine called from synchronous code is a real and
> recurring class of Python/asyncio bug, and this codebase still exposes async methods (e.g.
> `publish_async` on its event-bus protocols) that synchronous callers can misuse the same
> way — and drops the file-specific claims and the incident record that can no longer be
> verified.

---

## Symptoms

- **Test Progress**: hangs at a specific completion percentage
- **CI Behavior**: times out after the configured timeout
- **Last Test**: shows as PASSED but the next test never starts
- **Error Message**: "Error: The operation was canceled"
- **Environment**: typically seen in pytest with `pytest-asyncio` strict mode

## Root Cause

Synchronous code calling an async method without awaiting or scheduling the resulting
coroutine:

1. An async method (e.g. `publish_async()`) is called from sync code.
2. The call returns a coroutine object — it has not executed anything yet.
3. The coroutine is **never awaited or scheduled**.
4. Event-loop cleanup tries to handle the uncompleted coroutine.
5. `pytest-asyncio` strict mode **blocks** waiting for coroutines to complete.
6. **The test suite hangs** until timeout.

## Detection Steps

1. **Identify the last passing test** from CI output or a local run — note the test that
   passed just before the hang.
2. **Find the next test in collection order**:
   ```bash
   uv run pytest tests/ --collect-only -q | grep -A 5 "<last_passing_test_name>"
   ```
3. **Search for unawaited async calls** — look for `*_async` method calls not preceded by
   `await`:
   ```bash
   grep -n "\.publish_async\|\.send_async\|async def" src/<package>/mixins/*.py
   ```
4. **Check for sync methods calling async** — find methods that call `*_async` but are not
   themselves `async def`:
   ```bash
   rg "def\s+\w+\(" -A 20 src/<package>/mixins/ | grep "publish_async\|send_async"
   ```

## Anti-Pattern: Unawaited Async Call

```python
def emit_dag_completion_event(self, result, status):
    """Synchronous method."""
    # WRONG: async method called without await
    self._event_bus.publish_async(envelope)
```

`emit_dag_completion_event` is synchronous (no `async def`); `publish_async()` returns a
coroutine that is never awaited; it is garbage-collected without running, and the event loop
can get stuck waiting on it during cleanup.

## Solution Pattern: Helper Method with Coroutine Detection

```python
def emit_dag_completion_event(self, result, status):
    """Synchronous method."""
    self._publish_event(envelope)

def _publish_event(self, envelope) -> None:
    """Publish event, handling both sync and async event buses."""
    import asyncio
    import inspect

    result = self._event_bus.publish_async(envelope)

    if inspect.iscoroutine(result):
        try:
            loop = asyncio.get_running_loop()
            _ = loop.create_task(result)  # fire-and-forget, scheduled on the running loop
        except RuntimeError:
            # No running event loop — fallback for non-async contexts
            try:
                asyncio.run(result)
            except RuntimeError:
                # Test context with mocks — ignore
                pass
```

This works because it detects async via `inspect.iscoroutine()`, schedules the coroutine
properly (fire-and-forget task on the running loop, or `asyncio.run()` as a fallback outside
one), and handles the sync-context and mocked-test-context edge cases without hanging.

## Verification Steps

1. Run the affected tests: `uv run pytest tests/unit/<affected_module>/ -xvs`
2. Check type safety: `uv run mypy src/<package>/<affected_module>.py`
3. Smoke-test related modules: `uv run pytest tests/unit/<affected_area>/ -x --tb=short`
4. Full suite if time permits: `uv run pytest tests/ -x`

## Prevention Checklist

- [ ] Check the method signature — is it `async def`?
- [ ] Check the return type — does it return a coroutine?
- [ ] Check the caller context — is your method synchronous?
- [ ] Sync → async: use a helper method with coroutine detection (above).
- [ ] Async → async: use `await`.
- [ ] Test in strict mode: run with `pytest-asyncio` strict mode.
- [ ] CI verification: ensure tests don't time out in CI.

## Quick Reference

| Symptom | Likely Cause |
|---------|-------------|
| Test hangs at a specific % | Unawaited coroutine in the recently-run test |
| "Operation canceled" in CI | Timeout from an event-loop hang |
| Works locally, hangs in CI | Stricter async mode in the CI environment |
| Passes sometimes, hangs others | Race condition with event-loop cleanup |

```bash
# Find potential async issues
rg "\.publish_async\(" --type py
rg "\.send_async\(" --type py
rg "async def.*\(" -A 10 --type py | grep -v "await"

# Find sync methods calling async
rg "def\s+(?!async)" -A 20 --type py | grep "publish_async\|send_async"
```

---

**Remember**: in Python, calling an async method from sync code without proper handling will
**always** cause issues. Use the helper pattern above to ensure safe async/sync interop.

---

**Migration note**: originally authored 2025-11-15 against a specific incident in
`mixin_workflow_support.py` (file no longer present in omnibase_core@dev as of 2026-08-25).
Migrated to the knowledge base with the file-specific incident details removed and the
general technique — still directly applicable, since this codebase's event-bus protocols
still expose `publish_async` — preserved.
