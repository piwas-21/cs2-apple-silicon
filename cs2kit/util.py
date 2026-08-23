"""Shared primitives: process running, exit codes, check results, state paths.

Standard library only (Python 3.9+), so `/usr/bin/python3` on a stock Mac can run
CS2Kit with nothing installed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

# --- exit codes (docs/cs2kit-spec.md, stable contract) -----------------------
EXIT_OK = 0
EXIT_FAIL = 1          # a check FAILed / the operation did not achieve its goal
EXIT_USAGE = 2         # bad invocation
EXIT_NOT_READY = 3     # prerequisite missing (no wine, no bottle, no CS2)
EXIT_INTEGRITY = 4     # T-021: game files differ from the validated baseline
EXIT_REGRESSION = 5    # bench result outside the stored tolerance

PASS, WARN, FAIL, SKIP = "PASS", "WARN", "FAIL", "SKIP"
_RANK = {PASS: 0, SKIP: 1, WARN: 2, FAIL: 3}

_COLOR = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m", SKIP: "\033[90m"}
_RESET = "\033[0m"


def color_enabled(stream=None) -> bool:
    stream = stream or sys.stdout
    if os.environ.get("NO_COLOR") or os.environ.get("CS2KIT_NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def tag(status: str, stream=None) -> str:
    if color_enabled(stream):
        return f"{_COLOR.get(status, '')}{status:<4}{_RESET}"
    return f"{status:<4}"


@dataclass
class Check:
    """One doctor check. `fix` is a single actionable line, never a paragraph."""

    id: str
    label: str
    status: str
    detail: str = ""
    fix: str = ""
    task: str = ""  # the plan task this check enforces, e.g. "T-021"

    def line(self, stream=None) -> str:
        s = f"  [{tag(self.status, stream)}] {self.label:<32} {self.detail}"
        if self.status in (WARN, FAIL) and self.fix:
            s += f"\n         -> {self.fix}"
        return s

    def as_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class CheckSet:
    checks: List[Check] = field(default_factory=list)

    def add(self, *checks: Check) -> None:
        self.checks.extend(checks)

    def __iter__(self):
        return iter(self.checks)

    def __len__(self):
        return len(self.checks)

    def counts(self) -> Dict[str, int]:
        out = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0}
        for c in self.checks:
            out[c.status] = out.get(c.status, 0) + 1
        return out

    def worst(self) -> str:
        return max((c.status for c in self.checks), key=lambda s: _RANK.get(s, 0), default=PASS)

    def exit_code(self) -> int:
        return EXIT_FAIL if self.counts()[FAIL] else EXIT_OK

    def as_dict(self) -> Dict[str, Any]:
        return {"checks": [c.as_dict() for c in self.checks], "summary": self.counts()}


# --- process helpers ---------------------------------------------------------
@dataclass
class Proc:
    code: int
    out: str
    err: str

    @property
    def ok(self) -> bool:
        return self.code == 0


def run(cmd: Sequence[str], timeout: float = 30.0, env: Optional[Dict[str, str]] = None,
        cwd: Optional[str] = None, input_: Optional[str] = None) -> Proc:
    """Run a command, never raise. A missing binary is code 127, like a shell."""
    full_env = dict(os.environ)
    if env:
        full_env.update({k: str(v) for k, v in env.items()})
    try:
        p = subprocess.run(list(cmd), capture_output=True, text=True, timeout=timeout,
                           env=full_env, cwd=cwd, input=input_)
        return Proc(p.returncode, (p.stdout or "").strip(), (p.stderr or "").strip())
    except FileNotFoundError:
        return Proc(127, "", f"{cmd[0]}: not found")
    except subprocess.TimeoutExpired:
        return Proc(124, "", f"{' '.join(cmd)}: timed out after {timeout}s")
    except OSError as exc:  # pragma: no cover - platform specific
        return Proc(126, "", str(exc))


def which(name: str) -> Optional[str]:
    return shutil.which(name)


def sysctl(key: str) -> str:
    return run(["sysctl", "-n", key], timeout=5).out


# --- paths -------------------------------------------------------------------
def state_dir() -> Path:
    """Where CS2Kit keeps snapshots, baselines and bench results."""
    p = Path(os.environ.get("CS2KIT_HOME", Path.home() / ".cs2kit"))
    p.mkdir(parents=True, exist_ok=True)
    return p


def repo_root() -> Path:
    """The checkout that ships profiles/ and docs/ (works from a source tree)."""
    env = os.environ.get("CS2KIT_REPO")
    if env:
        return Path(env)
    return Path(__file__).resolve().parent.parent


def profiles_dir() -> Path:
    return repo_root() / "profiles"


def steam_root() -> Path:
    return Path(os.environ.get("CS2KIT_STEAM",
                               Path.home() / "Library/Application Support/Steam"))


def wineprefix() -> Path:
    return Path(os.environ.get("WINEPREFIX", Path.home() / "CS2/prefix"))


# --- io ----------------------------------------------------------------------
def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(Path(path).read_text())
    except (OSError, ValueError):
        return default


def write_json(path: Path, data: Any) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    return path


def median(values: Iterable[float]) -> float:
    vals = sorted(float(v) for v in values)
    if not vals:
        raise ValueError("median() of empty sequence")
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2.0


def percentile(values: Iterable[float], pct: float) -> float:
    """Linear-interpolation percentile; pct in [0, 100]."""
    vals = sorted(float(v) for v in values)
    if not vals:
        raise ValueError("percentile() of empty sequence")
    if len(vals) == 1:
        return vals[0]
    k = (len(vals) - 1) * (pct / 100.0)
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return vals[lo] + (vals[hi] - vals[lo]) * (k - lo)


def pct_delta(new: float, old: float) -> float:
    """Signed percentage change from `old` to `new`."""
    if old == 0:
        return 0.0 if new == 0 else float("inf")
    return (new - old) / abs(old) * 100.0
