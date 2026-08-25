"""`cs2kit play` - what the launcher app runs.

The app used to bake absolute paths at build time, which broke the moment the
game moved libraries: it reported `cs2.exe not found` at a path that no longer
held the game. Everything here is resolved at launch instead, and every failure
ends in a sentence a player can act on.
"""
from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import bottle, integrity, probe, recipe as recipe_mod
from cs2kit.util import (EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, FAIL, emit_error, run,
                         which, wineprefix)


def steam_client(prefix: Path) -> Optional[Path]:
    from cs2kit.launch import steam_exe

    return steam_exe(prefix)


def steam_running() -> bool:
    return run(["pgrep", "-f", "Steam.exe"], timeout=10).ok


def diagnose(prefix: Path) -> Optional[str]:
    """The first blocking problem, phrased for someone who just wants to play."""
    if not bottle.exists(prefix):
        return ("No Wine bottle yet. Run `cs2kit setup` in the project folder "
                "(about 10 minutes).")
    if steam_client(prefix) is None:
        return ("The Windows Steam client is not installed in the bottle. "
                "Run `cs2kit setup` to add it.")
    if probe.cs2_exe() is None:
        install = probe.cs2_install_dir()
        where = f" Found game files at {install} but no cs2.exe." if install else ""
        return ("Counter-Strike 2 is not installed in the bottle's Steam library." + where +
                " Open Steam (this app starts it), then install CS2 from your library.")
    return None


def build(prefix: Optional[Path] = None, profile: Optional[str] = None,
          extra: Optional[List[str]] = None) -> Dict[str, Any]:
    """Resolve everything needed to start the game, now, from disk."""
    prefix = Path(prefix or wineprefix())
    wine_root = bottle.wine_root()
    rec = None
    try:
        rec = recipe_mod.resolve(profile) if profile else recipe_mod.load_default()
    except recipe_mod.RecipeError:
        rec = None
    env = {"WINEPREFIX": str(prefix), "WINEDEBUG": "-all", "WINEMSYNC": "1"}
    if rec:
        env.update({k: os.path.expandvars(str(v)) for k, v in rec.env.items()})
    if wine_root:
        env["PATH"] = f"{Path(wine_root) / 'bin'}:{os.environ.get('PATH', '')}"
        env["DYLD_FALLBACK_LIBRARY_PATH"] = str(Path(wine_root) / "lib")
        env["CX_ROOT"] = str(wine_root)
    options = list((rec.launch_options if rec else []) or ["-novid", "-nojoy", "-console"])
    options += list(extra or [])
    bad = sorted(set(options) & recipe_mod.FORBIDDEN_LAUNCH_OPTIONS)
    if bad:
        raise recipe_mod.RecipeError(f"refusing to launch with {' '.join(bad)} (docs/architecture.md)")
    exe = probe.cs2_exe()
    return {"prefix": str(prefix), "wine_root": str(wine_root) if wine_root else None,
            "cs2_exe": str(exe) if exe else None, "env": env, "options": options,
            "profile": rec.name if rec else None}


def cmd_play(args) -> int:
    prefix = Path(args.prefix) if args.prefix else wineprefix()

    verdict = integrity.verify()
    if verdict.status == FAIL and not args.force:
        # Fixing this needs Steam, so open it rather than leaving the player stuck
        # in front of a dialog telling them to use an app that is not running.
        client = steam_client(prefix)
        if client and not steam_running() and not args.print_only:
            _start_steam(prefix, client)
        return emit_error("play", f"{verdict.message}. Steam is opening: right-click CS2 > "
                                  "Properties > Installed Files > Verify integrity of game files.",
                          EXIT_INTEGRITY, args.json)

    problem = diagnose(prefix)
    if problem and not args.start_steam_anyway:
        # Starting Steam is usually the fix, so do it before complaining about the game.
        client = steam_client(prefix)
        if client and probe.cs2_exe() is None and not steam_running():
            _start_steam(prefix, client)
        return emit_error("play", problem, EXIT_NOT_READY, args.json)

    plan = build(prefix, args.profile, args.extra)
    client = steam_client(prefix)
    if client and not steam_running():
        _start_steam(prefix, client, plan["env"])

    cmd = [str(Path(plan["wine_root"] or "") / "bin" / "wine") if plan["wine_root"] else (which("wine") or "wine"),
           "cs2.exe", *plan["options"]]
    if args.json or args.print_only:
        print(json.dumps({**plan, "command": cmd}, indent=2, sort_keys=True))
        return EXIT_OK
    env = dict(os.environ)
    env.update(plan["env"])
    cache = env.get("DXMT_SHADER_CACHE")
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
    game_dir = Path(plan["cs2_exe"]).parent
    os.chdir(game_dir)
    os.execve(cmd[0], cmd, env)
    return EXIT_OK   # pragma: no cover - execve does not return


def _start_steam(prefix: Path, client: Path, env: Optional[Dict[str, str]] = None) -> None:
    full = dict(os.environ)
    full.update(env or {"WINEPREFIX": str(prefix), "WINEMSYNC": "1", "WINEDEBUG": "-all"})
    wine_root = bottle.wine_root()
    if wine_root:
        full["PATH"] = f"{Path(wine_root) / 'bin'}:{full.get('PATH', '')}"
        full["DYLD_FALLBACK_LIBRARY_PATH"] = str(Path(wine_root) / "lib")
    subprocess.Popen(["bash", "-lc", f'cd "{client.parent}" && exec wine "{client.name}" -no-cef-sandbox -silent'],
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     stdin=subprocess.DEVNULL, env=full, start_new_session=True)
    for _ in range(30):
        time.sleep(2)
        if steam_running():
            time.sleep(8)
            return


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "play", help="start CS2 (what the launcher app runs)",
        description="Resolves the bottle, the engine and the game at launch time, verifies the "
                    "guarded binaries, starts Steam if needed, then starts the game.")
    parser.add_argument("--prefix", help="WINEPREFIX to use")
    parser.add_argument("--profile", help="profile whose env and launch options to use")
    parser.add_argument("--print-only", action="store_true", help="print the plan, start nothing")
    parser.add_argument("--force", action="store_true", help="start despite an integrity failure")
    parser.add_argument("--start-steam-anyway", action="store_true",
                        help="skip the readiness checks")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("extra", nargs="*", help="extra launch options")
    parser.set_defaults(func=cmd_play)
