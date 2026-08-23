"""`cs2kit launch` - the guarded way to start CS2.

This exists for one reason: T-021 requires that a modified game binary stops the
launch, and a guard nobody runs is not a guard. It refuses on a hash mismatch,
warns on anything else doctor considers fatal, then hands off to Steam. CS2Kit
never wraps Steam authentication and never injects anything into the process -
it sets environment variables and runs the Windows Steam client, exactly as a
user would.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import bottle, config, integrity, probe, recipe as recipe_mod
from cs2kit.util import (EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, FAIL, run, which,
                         wineprefix)

STEAM_EXE = Path("drive_c") / "Program Files (x86)" / "Steam" / "steam.exe"


def steam_exe(prefix: Optional[Path] = None) -> Optional[Path]:
    path = Path(prefix or wineprefix()) / STEAM_EXE
    return path if path.is_file() else None


def launch_env(rec: Optional[recipe_mod.Recipe], prefix: Path) -> Dict[str, str]:
    env = {"WINEPREFIX": str(prefix)}
    record = config.active()
    env.update({k: str(v) for k, v in (record.get("env") or {}).items()})
    if rec:
        env.update({k: str(v) for k, v in rec.env.items()})
    return env


def build_command(rec: Optional[recipe_mod.Recipe], prefix: Path,
                  extra: Optional[List[str]] = None) -> List[str]:
    wine = which("wine") or "wine"
    exe = steam_exe(prefix)
    options = list((rec.launch_options if rec else config.active().get("launch_options")) or [])
    options += list(extra or [])
    bad = sorted(set(options) & recipe_mod.FORBIDDEN_LAUNCH_OPTIONS)
    if bad:
        raise recipe_mod.RecipeError(
            f"refusing to launch with {' '.join(bad)}: on Apple Silicon CS2 falls back to DX11 "
            "silently, so the session measures something other than what it claims (docs/02)")
    args = ["-applaunch", probe.APPID] + options
    return [wine, str(exe or (prefix / STEAM_EXE)), *args]


def cmd_launch(args) -> int:
    prefix = Path(args.prefix or wineprefix())
    try:
        rec = recipe_mod.resolve(args.profile) if args.profile else None
    except recipe_mod.RecipeError as exc:
        print(f"cs2kit: {exc}")
        return EXIT_NOT_READY

    verdict = integrity.verify()
    if verdict.status == FAIL and not args.force:
        print("cs2kit: REFUSING TO LAUNCH (T-021)")
        print(f"  {verdict.message}")
        for name in (verdict.changed + verdict.missing)[:10]:
            print(f"    {name}")
        print("  Valve's VAC FAQ names modified game executables and DLLs as cheating.")
        print("  Fix: Steam > CS2 > Properties > Installed Files > Verify integrity of game files")
        return EXIT_INTEGRITY
    if verdict.status != FAIL and verdict.message:
        print(f"  [{verdict.status}] {verdict.message}")

    if not bottle.exists(prefix):
        print(f"cs2kit: {prefix} is not a Wine prefix - run `cs2kit bottle create` (T-006)")
        return EXIT_NOT_READY
    if not steam_exe(prefix):
        print(f"cs2kit: no Windows Steam client in {prefix} - install it first (T-007):")
        print(f"  WINEPREFIX={prefix} wine ~/Downloads/SteamSetup.exe")
        return EXIT_NOT_READY

    try:
        cmd = build_command(rec, prefix, args.extra)
    except recipe_mod.RecipeError as exc:
        print(f"cs2kit: {exc}")
        return EXIT_NOT_READY
    env = launch_env(rec, prefix)

    if args.json:
        print(json.dumps({"command": cmd, "env": env, "integrity": verdict.as_dict()},
                         indent=2, sort_keys=True))
        return EXIT_OK
    print("  " + " ".join(f"{k}={v}" for k, v in sorted(env.items())))
    print("  " + " ".join(cmd))
    if args.print_only:
        return EXIT_OK
    proc = run(cmd, timeout=args.timeout, env=env)
    if not proc.ok:
        print(f"cs2kit: steam.exe exited {proc.code}: {proc.err or proc.out}")
        return proc.code
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "launch", help="integrity-guarded CS2 launch (T-021)",
        description="Verifies the guarded binaries, applies the profile environment and hands "
                    "off to the in-bottle Windows Steam client. Never injects, never patches.")
    parser.add_argument("--profile", help="profile to source the environment from")
    parser.add_argument("--prefix", help="WINEPREFIX to launch in")
    parser.add_argument("--print-only", action="store_true", help="print the command, do not run it")
    parser.add_argument("--force", action="store_true",
                        help="launch despite an integrity FAIL (you are on your own)")
    parser.add_argument("--timeout", type=float, default=86400.0, help="seconds before giving up")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("extra", nargs="*", help="extra launch options passed to CS2")
    parser.set_defaults(func=cmd_launch)
