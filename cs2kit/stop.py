"""`cs2kit stop` - shut the bottle down cleanly.

Quitting Wine from the menu bar does not work the way people expect: it closes a
window, the Steam client is still running, and Steam puts the window straight
back. Everything in the bottle has to go down together, youngest first.
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import bottle
from cs2kit.util import EXIT_OK, run, wineprefix

#: Order matters: the game, then Steam, then its helpers, then the server.
STAGES = ["cs2.exe", "steam.exe", "steamwebhelper.exe", "steamservice.exe"]


def pids(name: str) -> List[str]:
    return [p for p in run(["pgrep", "-ix", name], timeout=10).out.split() if p.isdigit()]


def stop(prefix: Optional[Path] = None, force: bool = False,
         log=print) -> Dict[str, Any]:
    prefix = Path(prefix or wineprefix())
    stopped: Dict[str, int] = {}
    for name in STAGES:
        found = pids(name)
        if not found:
            continue
        run(["kill", "-TERM", *found], timeout=10)
        for _ in range(10):
            time.sleep(1)
            if not pids(name):
                break
        remaining = pids(name)
        if remaining and force:
            run(["kill", "-9", *remaining], timeout=10)
        stopped[name] = len(found)
        log(f"  stopped {len(found)} x {name}")

    wine_root = bottle.wine_root()
    server = str(Path(wine_root) / "bin" / "wineserver") if wine_root else "wineserver"
    result = run([server, "-k"], timeout=60, env={"WINEPREFIX": str(prefix)})
    return {"stopped": stopped, "wineserver_killed": result.code in (0, 1),
            "prefix": str(prefix)}


def cmd_stop(args) -> int:
    print("Stopping the bottle...")
    result = stop(Path(args.prefix) if args.prefix else None, force=args.force)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    if not result["stopped"]:
        print("  nothing was running")
    print("Done. Everything in the bottle is down.")
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "stop", help="shut down the game, Steam and the bottle cleanly",
        description="Quitting Wine from the menu bar only closes a window - Steam restarts it. "
                    "This stops everything in the right order.")
    parser.add_argument("--prefix", help="WINEPREFIX to shut down")
    parser.add_argument("--force", action="store_true", help="SIGKILL anything that ignores TERM")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=cmd_stop)
