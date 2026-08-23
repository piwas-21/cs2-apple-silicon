"""Documentation invariants (T-029).

The install guide is only useful if its cross-references resolve, and the repo's
own rule is that "every claim in docs/ traces to a research/ or docs/ file".  A
dead relative link silently breaks that chain, so the same check that CI runs
(`.github/workflows/ci.yml`, docs-link job) is enforced locally here: a broken
link fails `uv run pytest` on the developer's machine, not three commits later.

Only *relative* links are checked. External URLs are deliberately not fetched -
tests must stay offline, deterministic and stdlib-only.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import List, Tuple

ROOT = Path(__file__).resolve().parent.parent

# [label](target) - target captured up to the first whitespace or closing paren,
# so `[x](path "title")` is handled too.
LINK_RE = re.compile(r"\[[^\]]*\]\(\s*(<[^>]+>|[^)\s]+)[^)]*\)")
# Fenced code blocks hold shell transcripts, not links.
FENCE_RE = re.compile(r"^\s*```")


def markdown_files() -> List[Path]:
    files = sorted(p for p in (ROOT / "docs").rglob("*.md"))
    for name in ("README.md", "CONTRIBUTING.md"):
        p = ROOT / name
        if p.is_file():
            files.append(p)
    return files


def strip_code_fences(text: str) -> str:
    out, in_fence = [], False
    for line in text.splitlines():
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        out.append("" if in_fence else line)
    return "\n".join(out)


def relative_links(path: Path) -> List[str]:
    targets = []
    for raw in LINK_RE.findall(strip_code_fences(path.read_text())):
        target = raw.strip("<>")
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):  # http:, https:, mailto:
            continue
        if target.startswith("#") or not target:            # in-page anchor
            continue
        targets.append(target)
    return targets


def broken_links() -> List[Tuple[str, str]]:
    bad = []
    for path in markdown_files():
        for target in relative_links(path):
            fragmentless = target.split("#", 1)[0]
            if not fragmentless:
                continue
            resolved = (path.parent / fragmentless).resolve()
            if not resolved.exists():
                bad.append((str(path.relative_to(ROOT)), target))
    return bad


def test_every_relative_markdown_link_resolves():
    bad = broken_links()
    assert not bad, "broken relative links:\n" + "\n".join(f"  {f} -> {t}" for f, t in bad)


def test_markdown_corpus_is_not_empty():
    """Guards the guard: a glob typo would otherwise make the check vacuous."""
    assert len(markdown_files()) >= 10
