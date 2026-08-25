"""`cs2kit play` - what the launcher app runs.

The app used to bake absolute paths at build time, which broke the moment the
game moved libraries: it reported `cs2.exe not found` at a path that no longer
held the game. Everything here is resolved at launch instead, and every failure
ends in a sentence a player can act on.
"""
from __future__ import annotations

import json
import os
import shlex
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


def _pids(name: str) -> List[str]:
    """PIDs by exact process NAME.

    Deliberately not `pgrep -f`: that matches the whole command line, so any shell
    running a command that merely mentions `steam.exe` counts as Steam. That is
    not hypothetical - it made the launcher believe Steam was already running and
    silently skip starting it (measured 2026-08-25)."""
    return [p for p in run(["pgrep", "-ix", name], timeout=10).out.split() if p.isdigit()]


def steam_running() -> bool:
    """Is the Steam *client* up? `steamservice.exe` and `steamwebhelper.exe` are
    helpers that outlive it and must not be counted."""
    return bool(_pids("steam.exe"))


def clean_stale_steam() -> List[str]:
    """Kill helpers left behind by a previous client.

    Measured 2026-08-25: four orphaned `steamservice.exe` processes stopped a new
    client from starting at all - it logged in, then exited silently, and the app
    looked broken."""
    killed = []
    if steam_running():
        return killed
    for pattern in ("steamservice.exe", "steamwebhelper.exe"):
        pids = _pids(pattern)
        if pids:
            run(["kill", "-9", *pids], timeout=10)
            killed.extend(pids)
    return killed


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


def notify(message: str) -> None:
    """Surface a problem to someone who launched from Finder, not a terminal."""
    text = message.replace('"', "'").replace("\\", "/")
    subprocess.run(["osascript", "-e",
                    f'display dialog "{text}" with title "CS2Kit" buttons {{"OK"}} default button 1'],
                   capture_output=True, timeout=300)


def daemonize(log: Optional[Path] = None) -> None:
    """Detach from the caller so the work survives it.

    AppleScript's `do shell script` reaps whatever it started, even with
    `nohup ... &` - Steam launched that way logged in and vanished the moment the
    applet returned (measured 2026-08-25). A double fork with `setsid` reparents
    us to launchd, out of its reach."""
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    handle = open(log or (Path.home() / "CS2" / "cs2kit-app.log"), "a")
    os.dup2(handle.fileno(), 1)
    os.dup2(handle.fileno(), 2)


def cmd_play(args) -> int:
    if getattr(args, "detach", False):
        daemonize()
    prefix = Path(args.prefix) if args.prefix else wineprefix()

    verdict = integrity.verify()
    if verdict.status == FAIL and not args.force:
        # Fixing this needs Steam, so open it rather than leaving the player stuck
        # in front of a dialog telling them to use an app that is not running.
        client = steam_client(prefix)
        if client and not steam_running() and not args.print_only:
            _start_steam(prefix, client)
        message = (f"{verdict.message}. Steam is opening: right-click CS2 > Properties > "
                   "Installed Files > Verify integrity of game files.")
        if getattr(args, "gui", False):
            notify(message)
        return emit_error("play", message, EXIT_INTEGRITY, args.json)

    problem = diagnose(prefix)
    if problem and not args.start_steam_anyway:
        # Starting Steam is usually the fix, so do it before complaining about the game.
        client = steam_client(prefix)
        if client and probe.cs2_exe() is None and not steam_running():
            _start_steam(prefix, client)
        if getattr(args, "gui", False):
            notify(problem)
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
    clean_stale_steam()
    full = dict(os.environ)
    full.update(env or {"WINEPREFIX": str(prefix), "WINEMSYNC": "1", "WINEDEBUG": "-all"})
    wine_root = bottle.wine_root()
    if wine_root:
        full["PATH"] = f"{Path(wine_root) / 'bin'}:{full.get('PATH', '')}"
        full["DYLD_FALLBACK_LIBRARY_PATH"] = str(Path(wine_root) / "lib")
    wine = str(Path(wine_root) / "bin" / "wine") if wine_root else (which("wine") or "wine")
    log = Path.home() / "CS2" / "cs2kit-app.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as handle:
        handle.write(f"starting Steam with {wine}\n")
        if os.environ.get("CS2KIT_DEBUG_ENV"):
            keys = sorted(k for k in full if k.startswith(("WINE", "DYLD", "CX_", "PATH", "HOME", "TMPDIR", "USER")))
            handle.write("env: " + " ".join(f"{k}={full[k]}" for k in keys) + "\n")
    # Detach properly. Launched from a .app, this process tree dies with the app -
    # Steam would start, log in and vanish the moment the launcher exited
    # (measured 2026-08-25). `nohup ... &` inside its own session reparents Steam
    # to launchd, so it outlives us.
    quoted_wine = shlex.quote(wine)
    quoted_client = shlex.quote(str(client))
    quoted_log = shlex.quote(str(log))
    subprocess.Popen(
        ["bash", "-lc",
         f'cd {shlex.quote(str(client.parent))} && '
         # No -silent: with nothing owning Wine's system tray, a silent client
         # logs in and then exits, which looks exactly like "Steam never opened".
         f'nohup {quoted_wine} {quoted_client} -no-cef-sandbox >>{quoted_log} 2>&1 &'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        env=full, start_new_session=True)
    for _ in range(15):          # ~30 s: long enough to catch it, short enough
        time.sleep(2)               # that nothing upstream looks hung
        if steam_running():
            time.sleep(5)
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
    parser.add_argument("--detach", action="store_true",
                        help="double-fork first, so an AppleScript applet cannot reap us")
    parser.add_argument("--gui", action="store_true",
                        help="report problems in a dialog (used by the launcher app)")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("extra", nargs="*", help="extra launch options")
    parser.set_defaults(func=cmd_play)
