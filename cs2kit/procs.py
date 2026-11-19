"""Prefix-aware process selection shared by `play` and `stop`.

A name in a command line is not an executable: `tail -f /logs/steam.exe` and
`/bin/sh -c 'echo steam.exe'` must never be mistaken for the Windows client.
Wine's wow64 loader does put the Windows executable (sometimes its full Windows
path) in `comm`, so compare that basename, then read WINEPREFIX from the process
environment to establish bottle ownership. Candidates whose ownership cannot be
proved are reported, never signalled.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional

from cs2kit.util import run as _run

Runner = Callable[..., object]


@dataclass
class Selection:
    pids: List[str] = field(default_factory=list)
    ambiguous: List[str] = field(default_factory=list)
    other_prefix: List[str] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        """True when the selection is unambiguous (an empty one is safe too)."""
        return not self.ambiguous


def _out(proc: object) -> str:
    return str(getattr(proc, "out", "") or "")


def _code(proc: object) -> int:
    return int(getattr(proc, "code", 0) or 0)


def executable_pids(name: str, runner: Runner = _run) -> List[str]:
    """PIDs whose executable basename is `name`, never a command-line mention."""
    proc = runner(["ps", "-axww", "-o", "pid=,comm="], timeout=10)
    found: List[str] = []
    for line in _out(proc).splitlines():
        fields = line.strip().split(None, 1)
        if len(fields) != 2 or not fields[0].isdigit():
            continue
        executable = re.split(r"[\\/]", fields[1].strip())[-1]
        if executable.lower() == name.lower():
            found.append(fields[0])
    return found


def prefix_of(pid: str, runner: Runner = _run) -> Optional[Path]:
    """The selected bottle of a process, or None when it cannot be established.

    `ps eww` exposes inherited environment; only WINEPREFIX is read and no
    environment is logged or returned (it can contain unrelated credentials).
    """
    proc = runner(["ps", "eww", "-p", pid, "-o", "command="], timeout=10)
    if _code(proc):
        return None
    fields = re.split(r"\s+(?=[A-Za-z_]\w*=)", _out(proc).strip(), flags=re.ASCII)
    value = next((field.partition("=")[2] for field in fields
                  if field.startswith("WINEPREFIX=")), "")
    if not value or not Path(value).is_absolute():
        return None
    return Path(value).expanduser().resolve()


def select(name: str, prefix: Optional[Path] = None,
           runner: Runner = _run) -> Selection:
    """Candidates for `name`, restricted to `prefix` when one is given.

    With no prefix, executable matching alone is enough (used for read-only
    checks such as process age). With a prefix, only processes whose inherited
    WINEPREFIX resolves to it are selected. Unreadable or missing ownership is
    ambiguous, as is more than one candidate for the same bottle: callers must
    report those PIDs and leave them alone.
    """
    candidates = executable_pids(name, runner)
    if prefix is None:
        return Selection(pids=candidates)
    selected = Path(prefix).expanduser().resolve()
    owned, ambiguous, other = [], [], []
    for pid in candidates:
        owner = prefix_of(pid, runner)
        if owner is None:
            ambiguous.append(pid)
        elif owner == selected:
            owned.append(pid)
        else:
            other.append(pid)
    if len(owned) > 1:
        ambiguous.extend(owned)
        owned = []
    return Selection(pids=[] if ambiguous else owned,
                     ambiguous=ambiguous, other_prefix=other)
