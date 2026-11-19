"""`cs2kit stop` - shut the selected bottle down cleanly.

Quitting Wine from the menu bar does not work the way people expect: it closes a
window, the Steam client is still running, and Steam puts the window straight
back. Wine's own `wineserver -k` is prefix-scoped: it stops every process that
belongs to the chosen WINEPREFIX and cannot signal an unrelated bottle, a shell
that merely mentions `steam.exe`, or a process in another prefix.

Process names are still inspected to *report* what is running and to flag
ambiguous candidates, but a name match never becomes a kill target (review of
PR #1, 2026-11-19).
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import bottle, procs
from cs2kit.util import EXIT_FAIL, EXIT_OK, run, wineprefix

#: Order matters for reporting: the game, then Steam, then its helpers.
STAGES = ["cs2.exe", "steam.exe", "steamwebhelper.exe", "steamservice.exe"]


def _wine_root(prefix: Path) -> Optional[Path]:
    """The engine this bottle was built with, not a global PATH lookup."""
    recorded = bottle.read_state(prefix).get("wine_root")
    return bottle.wine_root(str(recorded)) if recorded else bottle.wine_root()


def pids(name: str, prefix: Optional[Path] = None) -> List[str]:
    """Executable PIDs for `name` in the selected prefix, using play's rules."""
    selected = Path(prefix or wineprefix()).expanduser().resolve()
    return procs.select(name, selected, runner=run).pids


def stop(prefix: Optional[Path] = None, force: bool = False,
         log=print) -> Dict[str, Any]:
    selected = Path(prefix or wineprefix()).expanduser().resolve()
    result: Dict[str, Any] = {"stopped": {}, "wineserver_killed": False,
                              "prefix": str(selected), "ok": False}
    if not bottle.exists(selected):
        result.update(ok=True, detail="no bottle at the selected prefix")
        log("  nothing was running")
        return result

    root = _wine_root(selected)
    server = (Path(root) / "bin" / "wineserver") if root else None
    if server is None or not server.is_file():
        result["detail"] = "cannot locate this bottle's wineserver; no processes were signalled"
        return result

    found: Dict[str, List[str]] = {}
    ambiguous: Dict[str, List[str]] = {}
    for name in STAGES:
        selection = procs.select(name, selected, runner=run)
        if selection.pids:
            found[name] = selection.pids
        if selection.ambiguous:
            ambiguous[name] = selection.ambiguous
            log(f"  {name}: PIDs {', '.join(selection.ambiguous)} have unproven prefix "
                "ownership - reported, not signalled")
    result["stopped"] = {name: len(pids) for name, pids in found.items()}
    result["ambiguous"] = ambiguous

    env = {"WINEPREFIX": str(selected)}
    killed = run([str(server), "-k9" if force else "-k"], timeout=60, env=env)
    result["wineserver_killed"] = killed.code in (0, 1)
    waited = run([str(server), "-w"], timeout=60, env=env)
    result["ok"] = waited.ok
    result["detail"] = ("selected bottle is down" if waited.ok else
                        "bottle shutdown was not confirmed")
    log(f"  {result['detail']}")
    return result


def cmd_stop(args) -> int:
    print("Stopping the bottle...")
    result = stop(Path(args.prefix) if args.prefix else None, force=args.force)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif not result["stopped"]:
        print("  nothing was running")
    return EXIT_OK if result["ok"] else EXIT_FAIL


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "stop", help="shut the selected Wine bottle down cleanly",
        description="Uses the selected prefix's wineserver, never a global process-name kill. "
                    "Ambiguous processes are reported and left alone.")
    parser.add_argument("--prefix", help="WINEPREFIX to shut down")
    parser.add_argument("--force", action="store_true",
                        help="send SIGKILL to processes in the selected bottle only")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=cmd_stop)
