"""Stop only the selected bottle, using Wine's own prefix-scoped control API."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Optional

from cs2kit import bottle
from cs2kit.util import EXIT_FAIL, EXIT_OK, run, wineprefix


def stop(prefix: Optional[Path] = None, force: bool = False, log=print) -> Dict[str, Any]:
    prefix = Path(prefix or wineprefix()).expanduser().resolve()
    result: Dict[str, Any] = {"stopped": {}, "wineserver_killed": False,
                              "prefix": str(prefix), "ok": False}
    if not bottle.exists(prefix):
        result.update(ok=True, detail="no bottle at the selected prefix")
        return result
    wine_root = bottle.wine_root(prefix=prefix)
    server = Path(wine_root) / "bin" / "wineserver" if wine_root else None
    if server is None or not server.is_file():
        result["detail"] = "cannot locate this bottle's wineserver; no processes were signalled"
        return result
    env = {"WINEPREFIX": str(prefix)}
    # Wine selects its server by the prefix directory's device/inode. It does
    # not search command-line arguments or terminate other bottles.
    killed = run([str(server), "-k9" if force else "-k"], timeout=30, env=env)
    if killed.code not in (0, 1):
        result["detail"] = killed.err or "wineserver shutdown failed"
        return result
    waited = run([str(server), "-w"], timeout=30, env=env)
    result.update(ok=waited.ok, wineserver_killed=waited.ok,
                  detail="selected bottle is down" if waited.ok else "bottle shutdown was not confirmed")
    log(result["detail"])
    return result


def cmd_stop(args) -> int:
    result = stop(Path(args.prefix) if args.prefix else None, force=args.force,
                  log=(lambda message: None))
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(result["detail"])
    return EXIT_OK if result["ok"] else EXIT_FAIL


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "stop", help="shut down only the selected Wine bottle",
        description="Uses the selected prefix's wineserver, then waits for it. "
                    "Exit Steam first to save settings; no global process-name kills are used.")
    parser.add_argument("--prefix", help="WINEPREFIX to shut down")
    parser.add_argument("--force", action="store_true", help="send SIGKILL to only this prefix's wineserver")
    parser.add_argument("--json", action="store_true")
    parser.set_defaults(func=cmd_stop)
