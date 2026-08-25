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
from cs2kit.util import (EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, FAIL, WARN, emit_error, run,
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


def game_running() -> bool:
    """Is CS2 up?

    Not `pgrep -ix cs2.exe`: when Steam launches the game the process carries its
    full Windows path (`C:\\Program Files (x86)\\Steam\\steamapps\\...\\cs2.exe`),
    so an exact-name match misses it entirely and CS2Kit reports "not running"
    while the game is on screen (measured 2026-08-26)."""
    listing = run(["ps", "-axo", "command="], timeout=15).out.splitlines()
    for line in listing:
        low = line.lower()
        if "cs2.exe" in low and " -lc " not in low and not low.startswith(("bash", "/bin/bash", "sh ")):
            return True
    return False


def steam_ready(prefix: Path, timeout: float = 90.0) -> bool:
    """Wait until the client has finished logging in.

    `-applaunch` sent too early is silently dropped, and sent while Steam still
    believes a previous session is alive it logs `WaitingPrevProcess` and does
    nothing. The client writes `Logged On` to its connection log when it is
    actually ready."""
    log = (Path(prefix) / "drive_c" / "Program Files (x86)" / "Steam" / "logs" /
           "connection_log.txt")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if "Logged On" in log.read_text(errors="ignore")[-4000:]:
                return True
        except OSError:
            pass
        time.sleep(3)
    return False


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
    if (verdict.status == WARN and verdict.baseline_buildid and verdict.buildid
            and verdict.baseline_buildid != verdict.buildid):
        # A new buildid means Steam updated the game - legitimate, and the only
        # honest response is to re-arm the guard against the new build. Tampering
        # *within* a build still fails, which is the case T-021 actually guards.
        try:
            new = integrity.create_baseline()
            print(f"cs2kit: CS2 updated {verdict.baseline_buildid} -> {verdict.buildid}; "
                  f"re-baselined {new.count} files")
            verdict = integrity.verify()
        except integrity.IntegrityError as exc:
            print(f"cs2kit: could not re-baseline: {exc}")
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

    if not args.steam_only and not args.direct and client:
        steam_ready(prefix)

    if args.steam_only:
        # Hand over to Steam and stop. Pressing Play in Steam is the only launch
        # path that gives the game its proper Steam context: launching cs2.exe
        # ourselves makes VAC report invalid signatures and refuse secure servers,
        # and the game starts with default settings (measured 2026-08-25).
        message = "Steam is open. Press Play on Counter-Strike 2 to start the game."
        if args.json:
            print(json.dumps({**plan, "via": "steam-ui"}, indent=2, sort_keys=True))
        elif getattr(args, "gui", False):
            notify(message)
        else:
            print(message)
        return EXIT_OK

    wine = (str(Path(plan["wine_root"]) / "bin" / "wine") if plan["wine_root"]
            else (which("wine") or "wine"))

    if args.direct:
        # Direct launch bypasses Steam's own app-launch path. VAC then reports
        # "game files have no signatures or invalid signatures" and refuses every
        # secure server, and the game starts with default settings because Steam
        # never synced the user's config (measured 2026-08-25). Offline use only.
        cmd = [wine, "cs2.exe", *plan["options"]]
        target_dir = Path(plan["cs2_exe"]).parent
    else:
        if client is None:
            return emit_error("play", "no Steam client in the bottle - run `cs2kit setup`",
                              EXIT_NOT_READY, args.json)
        cmd = [wine, str(client), "-applaunch", probe.APPID, *plan["options"]]
        target_dir = client.parent

    if args.json or args.print_only:
        print(json.dumps({**plan, "command": cmd, "via": "direct" if args.direct else "steam"},
                         indent=2, sort_keys=True))
        return EXIT_OK

    env = dict(os.environ)
    env.update(plan["env"])
    cache = env.get("DXMT_SHADER_CACHE")
    if cache:
        Path(cache).mkdir(parents=True, exist_ok=True)
    os.chdir(target_dir)
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
    subprocess.Popen(
        ["bash", "-lc",
         f'cd {shlex.quote(str(client.parent))} && '
         f'nohup {shlex.quote(wine)} {shlex.quote(str(client))} -no-cef-sandbox '
         f'>>{shlex.quote(str(log))} 2>&1 &'],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL,
        env=full, start_new_session=True)
    for _ in range(20):
        time.sleep(2)
        if steam_running():
            time.sleep(10)      # let the client finish logging in before -applaunch
            return


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "play", help="start CS2 through Steam (what the launcher app runs)",
        description="Resolves the bottle, the engine and the game at launch, verifies the guarded "
                    "binaries, starts Steam if needed, then asks Steam to launch the game.")
    parser.add_argument("--prefix", help="WINEPREFIX to use")
    parser.add_argument("--profile", help="profile whose env and launch options to use")
    parser.add_argument("--print-only", action="store_true", help="print the plan, start nothing")
    parser.add_argument("--force", action="store_true", help="start despite an integrity failure")
    parser.add_argument("--steam-only", action="store_true",
                        help="open Steam and stop - you press Play (the launcher app's default)")
    parser.add_argument("--direct", action="store_true",
                        help="start cs2.exe directly instead of through Steam. VAC then refuses "
                             "secure servers - offline testing only")
    parser.add_argument("--detach", action="store_true",
                        help="double-fork first, so an AppleScript applet cannot reap us")
    parser.add_argument("--gui", action="store_true",
                        help="report problems in a dialog (used by the launcher app)")
    parser.add_argument("--start-steam-anyway", action="store_true",
                        help="skip the readiness checks")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("extra", nargs="*", help="extra launch options")
    parser.set_defaults(func=cmd_play)
