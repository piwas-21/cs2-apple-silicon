"""T-021 - enforce "never modify game files".

Valve's VAC FAQ names *"modifications to a game's core executable files and
dynamic link libraries"* as cheating. That is the single action that turns this
project's low risk into a real one, so CS2Kit hashes the shipped Windows binary
set after a Steam *Verify integrity of game files* pass and refuses to launch
if a byte ever changes.

The legitimate surface - and it is the whole surface - is: bottle settings,
Wine's own DLL overrides, environment variables, launch options and
`autoexec.cfg`. Nothing inside `game/bin/win64/` is ours to touch.
"""
from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import probe
from cs2kit.util import (EXIT_FAIL, EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, FAIL,
                         PASS, WARN, Check, emit_error, read_json, state_dir, write_json)

#: Only files that VAC would consider "core" are guarded; a shader cache or a
#: user config changing is normal and must not raise a false alarm.
GUARDED_SUFFIXES = (".exe", ".dll", ".sys", ".so", ".dylib")
GUARDED_SUBDIR = Path("game") / "bin" / "win64"


class IntegrityError(RuntimeError):
    pass


def hash_file(path: Path, chunk: int = 1 << 20) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk), b""):
            digest.update(block)
    return digest.hexdigest()


def guarded_root(install_dir: Optional[Path] = None) -> Optional[Path]:
    install_dir = install_dir or probe.cs2_install_dir()
    if not install_dir:
        return None
    root = Path(install_dir) / GUARDED_SUBDIR
    return root if root.is_dir() else None


def scan(root: Path) -> Dict[str, str]:
    """SHA-256 every guarded binary under `root`, keyed by POSIX relative path."""
    root = Path(root)
    out: Dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file() and path.suffix.lower() in GUARDED_SUFFIXES:
            out[path.relative_to(root).as_posix()] = hash_file(path)
    return out


def baseline_path(buildid: Optional[str]) -> Path:
    return state_dir() / "integrity" / f"{buildid or 'unknown'}.json"


@dataclass
class Baseline:
    buildid: Optional[str]
    root: str
    created: str
    files: Dict[str, str] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.files)

    def as_dict(self) -> Dict[str, Any]:
        return {"buildid": self.buildid, "root": self.root, "created": self.created,
                "files": self.files, "count": self.count}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Baseline":
        return cls(buildid=data.get("buildid"), root=data.get("root", ""),
                   created=data.get("created", ""), files=data.get("files", {}))


def create_baseline(root: Optional[Path] = None, buildid: Optional[str] = None) -> Baseline:
    root = root or guarded_root()
    if not root:
        raise IntegrityError(
            "no game/bin/win64 directory found - CS2 is not installed in the bottle's library "
            "(T-008). Nothing to baseline."
        )
    buildid = buildid or probe.cs2_buildid()
    baseline = Baseline(buildid=buildid, root=str(root),
                        created=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                        files=scan(root))
    if not baseline.files:
        raise IntegrityError(f"{root} contains no guarded binaries - refusing to store an empty baseline")
    write_json(baseline_path(buildid), baseline.as_dict())
    return baseline


def load_baseline(buildid: Optional[str] = None) -> Optional[Baseline]:
    """The baseline for this buildid, else the most recent one on disk.

    Falling back matters: after a CS2 update the current buildid has no baseline
    yet, and the honest answer is "your baseline is stale" (a WARN, handled in
    `verify`), not "you have no baseline" - which would silently drop the guard
    exactly when the game's files have just changed."""
    buildid = buildid or probe.cs2_buildid()
    data = read_json(baseline_path(buildid))
    if data is None:
        candidates = sorted((state_dir() / "integrity").glob("*.json"),
                            key=lambda p: p.stat().st_mtime, reverse=True)
        for path in candidates:
            data = read_json(path)
            if data:
                break
    return Baseline.from_dict(data) if data else None


@dataclass
class Verdict:
    status: str                      # PASS / WARN / FAIL
    changed: List[str] = field(default_factory=list)
    missing: List[str] = field(default_factory=list)
    added: List[str] = field(default_factory=list)
    checked: int = 0
    buildid: Optional[str] = None
    baseline_buildid: Optional[str] = None
    message: str = ""

    @property
    def clean(self) -> bool:
        return not (self.changed or self.missing)

    def as_dict(self) -> Dict[str, Any]:
        return {"status": self.status, "changed": self.changed, "missing": self.missing,
                "added": self.added, "checked": self.checked, "buildid": self.buildid,
                "baseline_buildid": self.baseline_buildid, "message": self.message,
                "clean": self.clean}


def verify(root: Optional[Path] = None, baseline: Optional[Baseline] = None) -> Verdict:
    buildid = probe.cs2_buildid()
    root = root or guarded_root()
    if not root:
        return Verdict(status=WARN, buildid=buildid,
                       message="CS2 is not installed - nothing to verify (T-008)")
    baseline = baseline or load_baseline(buildid)
    if baseline is None:
        return Verdict(status=WARN, buildid=buildid,
                       message="no integrity baseline yet - run `cs2kit verify baseline` after "
                               "Steam's 'Verify integrity of game files' (T-008 step 5)")
    current = scan(root)
    changed = sorted(k for k, v in baseline.files.items() if k in current and current[k] != v)
    missing = sorted(k for k in baseline.files if k not in current)
    added = sorted(k for k in current if k not in baseline.files)

    if baseline.buildid and buildid and baseline.buildid != buildid:
        # A CS2 update legitimately rewrites these files. That is not tampering;
        # it is a stale baseline, and the fix is a re-baseline, not an alarm.
        return Verdict(status=WARN, changed=changed, missing=missing, added=added,
                       checked=len(current), buildid=buildid, baseline_buildid=baseline.buildid,
                       message=f"baseline is for buildid {baseline.buildid}, game is now {buildid} "
                               f"- re-run Steam verify, then `cs2kit verify baseline` (T-030)")
    if changed or missing:
        return Verdict(status=FAIL, changed=changed, missing=missing, added=added,
                       checked=len(current), buildid=buildid, baseline_buildid=baseline.buildid,
                       message=f"{len(changed)} changed, {len(missing)} missing guarded file(s) - "
                               "use Steam's 'Verify integrity of game files' before launching")
    status = WARN if added else PASS
    message = (f"{len(added)} new guarded file(s) since the baseline - expected after a CS2 update"
               if added else f"{len(current)} guarded files match the baseline")
    return Verdict(status=status, added=added, checked=len(current), buildid=buildid,
                   baseline_buildid=baseline.buildid, message=message)


def check(root: Optional[Path] = None) -> Check:
    """The doctor-facing form of `verify`."""
    verdict = verify(root)
    fix = ""
    if verdict.status == FAIL:
        fix = "Steam > CS2 > Properties > Installed Files > Verify integrity of game files"
    elif verdict.status == WARN and "baseline" in verdict.message:
        fix = "cs2kit verify baseline"
    return Check(id="game-file-integrity", label="Game file integrity", status=verdict.status,
                 detail=verdict.message, fix=fix, task="T-021")


def guard(root: Optional[Path] = None) -> Verdict:
    """Raise unless it is safe to launch. Used by `cs2kit launch`."""
    verdict = verify(root)
    if verdict.status == FAIL:
        raise IntegrityError(verdict.message)
    return verdict


# --- CLI ---------------------------------------------------------------------
def _print(verdict: Verdict) -> None:
    print(f"  [{verdict.status}] {verdict.message}")
    for label, items in (("changed", verdict.changed), ("missing", verdict.missing),
                         ("new", verdict.added)):
        for name in items[:20]:
            print(f"    {label:<8} {name}")
        if len(items) > 20:
            print(f"    {label:<8} ... and {len(items) - 20} more")


def cmd_baseline(args) -> int:
    try:
        baseline = create_baseline(Path(args.root) if args.root else None)
    except IntegrityError as exc:
        return emit_error("verify baseline", str(exc))
    print(f"Baselined {baseline.count} guarded files from {baseline.root}")
    print(f"  buildid {baseline.buildid or 'unknown'} -> {baseline_path(baseline.buildid)}")
    print("  Re-run this only after a Steam 'Verify integrity of game files' pass.")
    return EXIT_OK


def cmd_check(args) -> int:
    verdict = verify(Path(args.root) if args.root else None)
    if getattr(args, "json", False):
        import json
        print(json.dumps(verdict.as_dict(), indent=2, sort_keys=True))
    else:
        _print(verdict)
    if verdict.status == FAIL:
        return EXIT_INTEGRITY
    if verdict.status == WARN and getattr(args, "strict", False):
        return EXIT_FAIL
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "verify", help="T-021: hash-guard the shipped CS2 binaries",
        description="Record and enforce a SHA-256 baseline of game/bin/win64. CS2Kit refuses to "
                    "launch when a guarded file differs from the Steam-validated baseline.")
    sub = parser.add_subparsers(dest="verify_cmd")

    base = sub.add_parser("baseline", help="record the post-Steam-verify baseline")
    base.add_argument("--root", help="override the game/bin/win64 directory")
    base.set_defaults(func=cmd_baseline)

    chk = sub.add_parser("check", help="compare the game binaries against the baseline")
    chk.add_argument("--root", help="override the game/bin/win64 directory")
    chk.add_argument("--json", action="store_true", help="machine-readable output")
    chk.add_argument("--strict", action="store_true", help="treat WARN as failure")
    chk.set_defaults(func=cmd_check)

    parser.set_defaults(func=cmd_check, root=None, json=False, strict=False)
