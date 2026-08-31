"""Tests for scripts/sanitization_patterns.py — the private-repo URL exemption.

These exercise ``scan_text()``, the real gate entrypoint shared by the artifact
sanitization guard (``validate.py``) and the commit-message / PR-text gate
(``check_text_sanitization.py``), rather than matching the raw regex — the
entrypoint is what CI actually runs, so it is what the exemption is pinned to.

RED-before/GREEN-after: against the pre-fix pattern
``github\\.com/OmniNode-ai/(?!knowledge-base)`` the negative lookahead was
*prefix*-based, so every org repository whose name merely STARTS WITH the
public slug inherited the public repo's exemption. The two
``test_private_sibling_*`` cases and ``test_public_slug_prefix_is_not_exempt``
fail against that pattern and pass once the exemption is anchored to a slug
boundary.
"""

from __future__ import annotations

import sys
from pathlib import Path

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import pytest  # noqa: E402  (path setup must precede import)
from sanitization_patterns import PUBLIC_REPO_SLUGS, scan_text  # noqa: E402

_ORG = "github.com/OmniNode-ai"


def _blocks(text: str) -> bool:
    """True when the shared gate entrypoint reports a finding for ``text``."""
    return bool(scan_text(text, label="probe"))


class TestPublicRepoUrlsPass:
    """Positive direction: legitimate public references must NOT be blocked."""

    @pytest.mark.parametrize(
        "url",
        [
            f"https://{_ORG}/knowledge-base",
            f"https://{_ORG}/knowledge-base/blob/main/README.md",
            f"https://{_ORG}/knowledge-base/actions/workflows/ci.yml/badge.svg",
            f"{_ORG}/knowledge-base",
            # Clone URL — ``.git`` is a slug suffix, not a different repository.
            f"https://{_ORG}/knowledge-base.git",
            # Delimiter coverage: quote, paren, angle bracket, hash, query, EOL.
            f'"https://{_ORG}/knowledge-base"',
            f"(https://{_ORG}/knowledge-base)",
            f"<https://{_ORG}/knowledge-base>",
            f"https://{_ORG}/knowledge-base#readme",
            f"https://{_ORG}/knowledge-base?tab=readme",
        ],
    )
    def test_public_knowledge_base_url_is_exempt(self, url: str) -> None:
        assert not _blocks(url), (
            f"{url!r} is a legitimate public reference and must pass the gate; "
            "over-anchoring the exemption would break the repository's own "
            "README badge and cross-links"
        )

    def test_every_declared_public_slug_is_actually_exempt(self) -> None:
        """The allowlist constant and the compiled pattern cannot drift apart."""
        for slug in PUBLIC_REPO_SLUGS:
            assert not _blocks(f"https://{_ORG}/{slug}/blob/main/README.md"), (
                f"{slug!r} is declared public in PUBLIC_REPO_SLUGS but the "
                "compiled exemption does not actually exempt it"
            )


class TestPrivateRepoUrlsBlock:
    """Negative direction: the defect this module exists to pin."""

    def test_private_sibling_internal_is_blocked(self) -> None:
        url = f"https://{_ORG}/knowledge-base-internal/blob/main/plan.md"
        assert _blocks(url), (
            "a private sibling repository whose name merely begins with the "
            "public slug must NOT inherit the public exemption"
        )

    def test_private_sibling_personal_fork_is_blocked(self) -> None:
        url = f"https://{_ORG}/knowledge-base-jonah/blob/main/notes.md"
        assert _blocks(url), (
            "a private per-person repository whose name begins with the public "
            "slug must NOT inherit the public exemption"
        )

    def test_public_slug_prefix_is_not_exempt(self) -> None:
        """A distinct repo that happens to start with the slug, no delimiter."""
        assert _blocks(f"https://{_ORG}/knowledge-basement"), (
            "'knowledge-basement' is a different repository; a prefix match "
            "must not grant it the public repo's exemption"
        )

    @pytest.mark.parametrize(
        "slug",
        ["omnibase_core", "omnibase_infra", "omniclaude", "omniweb", "onex_change_control"],
    )
    def test_other_org_repositories_remain_blocked(self, slug: str) -> None:
        """The fix must not widen the exemption to the rest of the org."""
        assert _blocks(f"https://{_ORG}/{slug}"), f"{slug!r} is private and must stay blocked"

    def test_dot_git_suffix_does_not_smuggle_a_private_repo(self) -> None:
        """``.git`` is allowed as a suffix, not as a delimiter mid-slug."""
        assert _blocks(f"https://{_ORG}/knowledge-base.github-internal")


class TestUnderscoreSpellingVerdictsArePinned:
    """Pin the underscore candidate spellings against a silent rename.

    Workspace-plan Q1 leaves the public repository's eventual name open, with
    an underscore spelling among the candidates. These assertions record the
    CURRENT verdict for those spellings — they are private/unknown slugs and
    are blocked — so that renaming the public repo cannot quietly flip gate
    behaviour without a test failure forcing the exemption list to be updated
    deliberately. If the public repo is ever renamed to an underscore
    spelling, add it to ``PUBLIC_REPO_SLUGS`` and move that case into
    ``TestPublicRepoUrlsPass`` as an explicit decision, never as a side effect.
    """

    @pytest.mark.parametrize(
        "slug",
        ["knowledge_base", "knowledge_base_internal", "knowledge_base_jonah"],
    )
    def test_underscore_spellings_are_currently_blocked(self, slug: str) -> None:
        assert _blocks(f"https://{_ORG}/{slug}/blob/main/README.md"), (
            f"{slug!r} is not a declared public slug, so it must block; see "
            "workspace-plan Q1 — this verdict is pinned deliberately"
        )

    def test_underscore_spellings_are_not_in_the_public_allowlist(self) -> None:
        for slug in ("knowledge_base", "knowledge_base_internal", "knowledge_base_jonah"):
            assert slug not in PUBLIC_REPO_SLUGS, (
                f"{slug!r} appearing in PUBLIC_REPO_SLUGS would be a rename "
                "landing without the workspace-plan Q1 decision being made"
            )


class TestGateEntrypointReportsThePrivateRepoRule:
    """The finding must be attributed to the private-repo rule, not another."""

    def test_finding_is_labelled_private_repo_url(self) -> None:
        errors = scan_text(f"https://{_ORG}/knowledge-base-internal", label="probe")
        assert errors, "expected a finding for a private sibling repository"
        assert any("Private repo URL" in e for e in errors), f"expected the private-repo rule to fire, got: {errors}"
