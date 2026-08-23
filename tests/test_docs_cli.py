"""The documentation must only promise commands that exist.

A guide is the product for a user who has never used Wine (T-029), so a command
that was renamed in the code and not in the docs is a real defect, not a typo.
This test walks every `cs2kit ...` invocation printed anywhere in the repo's
markdown and checks it against the live argparse tree.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

import pytest

from cs2kit import cli

ROOT = Path(__file__).resolve().parent.parent
INVOCATION = re.compile(r"\bcs2kit\s+([a-z][a-z0-9-]*)(?:\s+([a-z][a-z0-9-]*))?")
PLACEHOLDER = re.compile(r"^<.*>$")


def markdown_files():
    return sorted([ROOT / "README.md", *(ROOT / "docs").rglob("*.md"),
                   *(p for p in (ROOT / "CONTRIBUTING.md",) if p.exists())])


def command_tree():
    parser = cli.build_parser()
    top = next(a for a in parser._actions if a.dest == "command")
    tree = {}
    for name, sub in top.choices.items():
        actions = [a for a in sub._actions if isinstance(a, argparse._SubParsersAction)]
        tree[name] = set(actions[0].choices) if actions else set()
    return tree


FENCE = re.compile(r"```.*?```", re.S)
INLINE = re.compile(r"`([^`\n]+)`")


COMMAND_LINE = re.compile(r"^\s*(?:[$#]\s+)?(?:\S*/)?(?:bin/)?cs2kit\s")


def code_spans(text: str):
    """Only executable-looking code counts. A fenced repo map that mentions
    "a cs2kit command" in prose is not a promise; a line that starts with the
    command is."""
    for block in FENCE.findall(text):
        for line in block.splitlines():
            if COMMAND_LINE.match(line):
                yield line
    for span in INLINE.findall(FENCE.sub("", text)):
        if COMMAND_LINE.match(span):
            yield span


def invocations():
    found = []
    for path in markdown_files():
        for span in code_spans(path.read_text()):
            for match in INVOCATION.finditer(span):
                found.append((path.relative_to(ROOT), match.group(1), match.group(2)))
    return found


def test_the_docs_reference_only_real_commands():
    tree = command_tree()
    bad = [(f, cmd, sub) for f, cmd, sub in invocations() if cmd not in tree]
    assert not bad, "documented commands that do not exist: " + str(bad)


def test_documented_subcommands_exist():
    tree = command_tree()
    bad = []
    for path, cmd, sub in invocations():
        if cmd not in tree or sub is None or not tree[cmd]:
            continue
        if sub not in tree[cmd] and not PLACEHOLDER.match(sub):
            bad.append((str(path), cmd, sub))
    assert not bad, "documented subcommands that do not exist: " + str(bad)


def test_the_docs_mention_every_shipped_command():
    """The reverse direction: a command nobody documented is a command nobody finds."""
    documented = {cmd for _, cmd, _ in invocations()}
    missing = sorted(set(command_tree()) - documented)
    assert not missing, f"shipped but undocumented commands: {missing}"


@pytest.mark.parametrize("profile", ["balanced-1080p", "competitive-lowest-latency",
                                     "thermal-limited"])
def test_shipped_profiles_are_named_in_the_docs(profile):
    text = "\n".join(p.read_text() for p in markdown_files())
    assert profile in text, f"{profile} ships but is never documented (T-027)"
