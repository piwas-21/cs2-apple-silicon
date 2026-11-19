"""`cs2kit play` - what the launcher app runs.

The app used to bake absolute paths at build time, which broke the moment the
game moved libraries: it reported `cs2.exe not found` at a path that no longer
held the game. Everything here is resolved at launch instead, and every failure
ends in a sentence a player can act on.
"""
from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import bottle, integrity, probe, procs, recipe as recipe_mod
from cs2kit.util import (EXIT_INTEGRITY, EXIT_NOT_READY, EXIT_OK, FAIL, WARN, emit_error, run,
                         which, wineprefix)


def steam_client(prefix: Path) -> Optional[Path]:
    from cs2kit.launch import steam_exe

    return steam_exe(prefix)


def _pids(name: str, prefix: Optional[Path] = None) -> List[str]:
    """Executable PIDs, optionally restricted to one bottle.

    `pgrep -f` matches any command line that merely mentions the name, which
    once made the launcher believe Steam was already running and silently skip
    starting it (measured 2026-08-25). Wine's wow64 loader also hides the exe
    name from `pgrep -ix`, so look at `comm` instead - shared with `cs2kit stop`
    in `cs2kit.procs`, together with WINEPREFIX ownership checks."""
    if prefix is None:
        return procs.executable_pids(name, runner=run)
    return procs.select(name, prefix, runner=run).pids


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


_LOGON_RE = re.compile(r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] \[Logged On", re.M)


def _steam_started_at(prefix: Optional[Path] = None) -> Optional[float]:
    """Epoch time when the current steam.exe processes started (earliest one).

    Steam re-execs itself during bootstrap, so the client that ends up logged in
    is younger than the process a launch started; taking the earliest start is
    the honest lower bound. Locale-free on purpose: `ps -o lstart` renders month
    names per LC_TIME, so elapsed time is read and subtracted from now instead."""
    best: Optional[float] = None
    for pid in _pids("steam.exe", prefix):
        out = run(["ps", "-o", "etime=", "-p", pid], timeout=10).out.strip()
        if not out:
            continue
        days, _, rest = out.rpartition("-")
        parts = rest.split(":")
        try:
            seconds = int(days or 0) * 86400
            if len(parts) == 3:
                seconds += int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            elif len(parts) == 2:
                seconds += int(parts[0]) * 60 + int(parts[1])
            else:
                continue
        except ValueError:
            continue
        started = time.time() - seconds
        best = started if best is None else min(best, started)
    return best


def steam_ready(prefix: Path, timeout: float = 90.0) -> bool:
    """Wait until the client has finished logging in.

    `-applaunch` sent too early is silently dropped, and sent while Steam still
    believes a previous session is alive it logs `WaitingPrevProcess` and does
    nothing. The client writes `Logged On` to its connection log when it is
    actually ready.

    The connection log accumulates across sessions, so a bare tail scan finds
    yesterday's `Logged On` line instantly and fires while the fresh client is
    still handshaking - Steam then drops the `-applaunch` without a trace and
    the launcher looks like it started nothing (measured 2026-11-10, the day
    after a wedged client was cleaned up). A `Logged On` line only counts when
    its timestamp is at or after the current steam.exe processes' start.

    With no client process at all, no `Logged On` line can belong to this
    session - the log's tail is history, and `-applaunch` into a client that is
    not there is dropped without a trace. The client start time is re-read on
    every pass, because the client may still be booting when the wait begins."""
    log = (Path(prefix) / "drive_c" / "Program Files (x86)" / "Steam" / "logs" /
           "connection_log.txt")
    deadline = time.time() + timeout
    while time.time() < deadline:
        started = _steam_started_at(prefix)
        try:
            text = log.read_text(errors="ignore")[-4000:]
        except OSError:
            text = ""
        stamps = _LOGON_RE.findall(text)
        if stamps and started is not None:
            logon = datetime.strptime(stamps[-1], "%Y-%m-%d %H:%M:%S").timestamp()
            if logon >= started - 2:
                return True
        time.sleep(3)
    return False


def wineserver_running(prefix: Optional[Path] = None) -> bool:
    """Is the selected bottle's wineserver alive? Steam's Windows side needs it."""
    return bool(_pids("wineserver", prefix))


def steam_running(prefix: Optional[Path] = None) -> bool:
    """Is this bottle's Steam *client* up? Helpers do not count, and neither
    does a process in another bottle.

    A steam.exe whose wineserver has exited is debris, not a client: it cannot
    act, and counting it made every launch skip starting Steam and send
    `-applaunch` into a dead process (measured 2026-11-11). Both checks are
    scoped to the selected WINEPREFIX; an ambiguous process is not selected at
    all, so it can never suppress startup."""
    selected = Path(prefix or wineprefix()).expanduser().resolve()
    if not _pids("steam.exe", selected):
        return False
    return wineserver_running(selected)


def native_steam_running() -> bool:
    """Is the native macOS Steam client up?

    Steam ships a Mac client living in ~/Library/Application Support/Steam -
    visually identical to the one inside the bottle. It cannot start CS2 (the
    game has no macOS build) and signing into it takes over the account session
    the Wine client holds: the next `-applaunch` is then silently dropped and
    CS2Kit looks broken (measured 2026-11-10/11 - nothing opened until the
    native client was quit, and its session had quietly displaced the Wine
    client's the evening before)."""
    return bool(run(["pgrep", "-f", r"Steam\.AppBundle"], timeout=10).out.strip())


def clean_stale_steam() -> List[str]:
    """Compatibility hook: no global process-name kills from the launcher.

    A PID found by name cannot establish which bottle owns it, and this path
    issued SIGKILL without `--force` (measured 2026-11-19 in review). A stuck
    bottle is stopped explicitly with the prefix-scoped `cs2kit stop`, which
    uses that bottle's wineserver and never signals an unrelated process."""
    return []


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
    try:
        subprocess.run(["osascript", "-e",
                        f'display dialog "{text}" with title "CS2Kit" buttons {{"OK"}} '
                        f'default button 1'],
                       capture_output=True, timeout=300)
    except subprocess.TimeoutExpired:
        # Nobody clicked OK within five minutes. The dialog was still shown, and
        # the launcher must not die of it (measured 2026-11-12: an unhandled
        # TimeoutExpired ended the worker with a traceback in the log).
        pass


def notification(message: str) -> None:
    """Progress, not a question: a notification the player does not have to dismiss."""
    text = message.replace('"', "'").replace("\\", "/")
    subprocess.run(["osascript", "-e",
                    f'display notification "{text}" with title "CS2Kit"'],
                   capture_output=True, timeout=30)


_APP_STATE_RE = re.compile(
    r"^\[(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\] AppID 730 state changed : (.*)$", re.M)


def steam_update_state(prefix: Path, max_age: float = 900.0) -> Optional[str]:
    """What Steam last said about CS2's install state, e.g. `Update Required`.

    Steam downloads an update *instead of* starting the game when the installed
    build is stale: `-applaunch` becomes a download, and the game appears only
    when the download finishes - minutes later, with nothing on screen to show
    for it (measured 2026-11-12, a 1.1 GB CS2 update: the app looked dead for
    two minutes and then the game simply appeared).

    The content log is appended across sessions, so only the last line counts,
    and only if it is recent enough to belong to the launch in progress."""
    log = (Path(prefix) / "drive_c" / "Program Files (x86)" / "Steam" / "logs" /
           "content_log.txt")
    try:
        text = log.read_text(errors="ignore")[-20000:]
    except OSError:
        return None
    matches = _APP_STATE_RE.findall(text)
    if not matches:
        return None
    stamp, states = matches[-1]
    try:
        when = datetime.strptime(stamp, "%Y-%m-%d %H:%M:%S").timestamp()
    except ValueError:
        return None
    if time.time() - when > max_age:
        return None
    return states


def updating_cs2(prefix: Path) -> bool:
    """Is Steam updating CS2 right now?"""
    states = steam_update_state(prefix)
    if not states:
        return False
    return "Update Running" in states or "Update Required" in states


def daemonize(log: Optional[Path] = None) -> None:
    """Detach from the caller so the work survives it.

    AppleScript's `do shell script` reaps whatever it started, even with
    `nohup ... &` - Steam launched that way logged in and vanished the moment the
    applet returned (measured 2026-08-25). A double fork with `setsid` reparents
    us to launchd, out of its reach.

    Being out of the caller's process group is not enough: the launcher app is
    a real application bundle, and when it quits macOS tears down its whole job
    - SIGTERM to every process that is still part of it, however well it hid
    (measured 2026-11-12: the detached worker was killed a second into the
    launch, before it had even started Steam, so the app did nothing at all).
    A daemon has to outlive its parent, so the signals that mean "your parent
    is gone" are ignored here - the children get the default disposition back
    (see `_default_signals`)."""
    if os.fork() > 0:
        os._exit(0)
    os.setsid()
    if os.fork() > 0:
        os._exit(0)
    for name in ("SIGTERM", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is not None:
            try:
                signal.signal(number, signal.SIG_IGN)
            except (ValueError, OSError):     # pragma: no cover - platform specific
                pass
    handle = open(log or (Path.home() / "CS2" / "cs2kit-app.log"), "a")
    os.dup2(handle.fileno(), 1)
    os.dup2(handle.fileno(), 2)


def _default_signals() -> None:
    """Give a child back the default disposition of the daemon's signals.

    SIG_IGN survives exec, so without this the Steam client would inherit it
    and `cs2kit stop` - which shuts the bottle down with SIGTERM - would have
    to kill it the hard way."""
    for name in ("SIGTERM", "SIGHUP"):
        number = getattr(signal, name, None)
        if number is not None:
            try:
                signal.signal(number, signal.SIG_DFL)
            except (ValueError, OSError):     # pragma: no cover - platform specific
                pass


def cmd_play(args) -> int:
    if getattr(args, "detach", False):
        daemonize()
        # A marker in the log: without it, a launcher that dies before it
        # reaches Steam is indistinguishable from one that never ran (measured
        # 2026-11-12: the app was double-clicked and the log stayed completely
        # silent - nothing to look at).
        print(f"cs2kit: launch requested at {datetime.now().isoformat(timespec='seconds')}",
              flush=True)
    prefix = Path(args.prefix) if args.prefix else wineprefix()

    if not args.print_only and native_steam_running():
        message = ("Native Steam for macOS is running. It cannot start CS2 (the game has no "
                   "macOS build) and it takes over the Steam session the Windows client "
                   "needs - quit native Steam, then launch CS2Kit again.")
        if getattr(args, "gui", False):
            notify(message)
        return emit_error("play", message, EXIT_NOT_READY, args.json)

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
        if client and not steam_running(prefix) and not args.print_only:
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
        if client and probe.cs2_exe() is None and not steam_running(prefix):
            _start_steam(prefix, client)
        if getattr(args, "gui", False):
            notify(problem)
        return emit_error("play", problem, EXIT_NOT_READY, args.json)

    plan = build(prefix, args.profile, args.extra)
    client = steam_client(prefix)
    if client and not steam_running(prefix):
        if getattr(args, "gui", False):
            # Say something before the long wait: a cold start takes a minute
            # (Steam, then the login, then the game) and until the window shows
            # up, double-clicking the app looks like it did nothing.
            _report("Starting Steam. CS2 takes a minute to come up.")
        _start_steam(prefix, client, plan["env"])

    logged_on = True
    if not args.print_only and not args.steam_only and not args.direct and client:
        # A client that never finished signing in silently drops -applaunch, so
        # before sending one, give a slow login a second window. Quitting native
        # Steam mid-wait displaces the session back and forth - hence the extra
        # time instead of a hard fail at the first timeout (measured 2026-11-11:
        # a healthy cold login took ~85s to displace the native session and
        # return, seconds shy of the first window).
        logged_on = steam_ready(prefix)
        if not logged_on:
            logged_on = steam_ready(prefix, timeout=90.0)
        if not logged_on:
            # A client that is up but never signs in is a stale session: the
            # bottle still carries the half-dead client of the last run, and
            # the new one cannot take the session over - the client sits in
            # its main loop without ever logging on (measured 2026-11-12). A
            # clean bottle is the fix, so take one - once - before giving up.
            if getattr(args, "gui", False):
                _report("Steam did not sign in. Restarting the bottle.")
            restart_steam(prefix, client, plan["env"])
            logged_on = steam_ready(prefix, timeout=120.0)
        if not logged_on:
            message = ("The Steam client did not finish signing in, and it drops game "
                       "launches until it does. Quit Steam completely (cs2kit stop) and "
                       "launch again; if the Steam window asks you to log in, log in - "
                       "the game cannot start before that.")
            if getattr(args, "gui", False):
                notify(message)
            return emit_error("play", message, EXIT_NOT_READY, args.json)

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
    if getattr(args, "gui", False):
        # The app has to keep talking after the launch: CS2 needs a minute to
        # come up, and if Steam decides to update the game first it needs
        # minutes - and until the window appears, nothing at all happens on
        # screen, which is exactly what "it does not launch" looks like.
        # execve would replace this process with the game launcher and leave
        # nobody to say anything.
        _spawn_launch(cmd, env, target_dir)
        _follow_launch(prefix)
        return EXIT_OK
    os.execve(cmd[0], cmd, env)
    return EXIT_OK   # pragma: no cover - execve does not return


def _spawn_launch(cmd: List[str], env: Dict[str, str], target_dir: Path) -> None:
    """Start the game without becoming it.

    The launch has to outlive the launcher process - an applet that exits
    takes its children with it - so it gets its own session and the same log
    file the rest of the app writes to."""
    log = Path.home() / "CS2" / "cs2kit-app.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as handle:
        subprocess.Popen(cmd, env=env, cwd=str(target_dir), stdin=subprocess.DEVNULL,
                         stdout=handle, stderr=handle, start_new_session=True,
                         preexec_fn=_default_signals)


def _follow_launch(prefix: Path, timeout: float = 1800.0) -> None:
    """Tell the player what is happening while CS2 comes up.

    Three ways a launch can look like nothing happened, and each needs its own
    sentence: the game is coming up (a minute), Steam is downloading an update
    first (minutes, and the game appears when it is done), or the client died
    on the way (nothing will ever appear)."""
    deadline = time.time() + timeout
    told_update = False
    while time.time() < deadline:
        if game_running():
            _report("CS2 is starting.")
            return
        if updating_cs2(prefix):
            if not told_update:
                told_update = True
                _report("Steam is updating CS2. The game starts as soon as the update "
                        "is done - it can take a few minutes.")
            time.sleep(5)
            continue
        if not steam_running(prefix):
            _report("The Steam client closed before it could start CS2. "
                    "Run `cs2kit doctor` to see why.")
            return
        time.sleep(4)
    _report("CS2 did not start. Press Play in the Steam window.")


def _report(message: str) -> None:
    """Say it to the player, and leave a trace in the log.

    The log is the only way to tell afterwards what the launcher did - the
    notification is gone as soon as it is dismissed."""
    print(f"cs2kit: {message}", flush=True)
    notification(message)


def restart_steam(prefix: Path, client: Path, env: Optional[Dict[str, str]] = None) -> None:
    """Throw the bottle away and start the client on a clean one.

    A client that is up but never signs in is not a slow login - it is the
    leftover of an earlier session holding the account session hostage. Only a
    fresh bottle (a new wineserver, no debris) lets the new client log on."""
    from cs2kit import stop as stop_mod

    try:
        stop_mod.stop(prefix, force=True)
    except Exception:          # pragma: no cover - stopping is best effort
        pass
    time.sleep(2)
    _start_steam(prefix, client, env)


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
        env=full, start_new_session=True, preexec_fn=_default_signals)
    for _ in range(20):
        time.sleep(2)
        if steam_running(prefix):
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
