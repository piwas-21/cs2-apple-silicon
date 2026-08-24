"""T-030 - watch for CS2 updates and print the regression drill.

Why: whether a CS2 patch has ever broken a Wine bottle is recorded as UNKNOWN in
docs/03-development-plan.md, and the only way to turn that into data is to notice
every `buildid` change and run the same drill each time. The acceptance test is
"a buildid change triggers the drill within 24 h", so this module is built to be
run unattended from cron or a LaunchAgent - which means it must never hang and
never crash.

Network policy: exactly one optional, unauthenticated GET to a public appinfo
mirror, with a hard timeout, no retries and no telemetry. Any failure - offline,
DNS, TLS, rate limit, a mirror that changed its JSON shape - degrades to a WARN
and a status of "unknown". CS2Kit is still useful with the network unplugged, so
nothing here is allowed to become a hard dependency.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from cs2kit import __version__, probe
from cs2kit.util import (
    EXIT_NOT_READY,
    EXIT_OK,
    EXIT_REGRESSION,
    PASS,
    WARN,
    read_json,
    repo_root,
    state_dir,
    write_json,
)

APPID = probe.APPID
BRANCH = "public"
DEFAULT_TIMEOUT = 8.0
MAX_BYTES = 8 * 1024 * 1024      # the 730 appinfo blob is large but not unbounded
USER_AGENT = "CS2Kit/%s (+https://github.com/piwas-21/cs2-apple-silicon)" % __version__

#: One public mirror today. The loop is deliberate: a second source drops in here
#: without any caller learning about it.
APPINFO_SOURCES: Tuple[str, ...] = ("https://api.steamcmd.net/v1/info/%s" % APPID,)

MATRIX_HEADER = "| date | buildid | macOS | wine | dxmt | avg fps | 1% low | verdict |"
MATRIX_RULE = "| --- | --- | --- | --- | --- | --- | --- | --- |"

DRILL_STEPS = (
    "1. cs2kit doctor            - environment first; most 'the update broke it' reports are not the update.",
    "2. cs2kit bottle repair     - only if doctor FAILs a bottle check; re-apply the recipe, never hand-edit.",
    "3. Launch CS2 to the main menu - a black screen here is the T-009 fullscreen fix, not a regression.",
    "4. cs2kit bench run         - 3 warm-up runs, 5 measured runs, Ancient (workshop 3472126051).",
    "5. cs2kit bench compare     - exits %d if a headline metric moved more than 5 %% (T-026)." % EXIT_REGRESSION,
    "6. One-match smoke test     - a bot match on Dust2: audio, mouse, alt-tab, no crash (matrix rows A/B/E).",
    "7. cs2kit watch record      - store the new buildid so the next check compares against it.",
    "8. Append the result to docs/compatibility-matrix.md, verdict PASS / DEGRADED / BROKEN.",
)


class WatchError(RuntimeError):
    """Only raised for programming errors; network trouble is a status, not an exception."""


# --- remote ------------------------------------------------------------------
def _http_get_json(url: str, timeout: float) -> Any:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT,
                                                   "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310 - https literal
        raw = response.read(MAX_BYTES)
    return json.loads(raw.decode("utf-8", "replace"))


def _extract_buildid(payload: Any, branch: str = BRANCH) -> Optional[str]:
    """Pull `depots.branches.<branch>.buildid` out of an appinfo blob.

    The documented path is tried first, then a recursive search, because a mirror
    is free to wrap its answer differently and a missed buildid means a missed
    regression drill.
    """
    def _dig(node: Any, keys: Sequence[str]) -> Any:
        for key in keys:
            if not isinstance(node, dict):
                return None
            node = node.get(key)
        return node

    direct = _dig(payload, ("data", APPID, "depots", "branches", branch, "buildid"))
    if direct:
        return str(direct)

    stack: List[Any] = [payload]
    seen = 0
    while stack and seen < 10000:
        node = stack.pop()
        seen += 1
        if isinstance(node, dict):
            branches = node.get("branches")
            if isinstance(branches, dict):
                target = branches.get(branch)
                if isinstance(target, dict) and target.get("buildid"):
                    return str(target["buildid"])
            stack.extend(node.values())
        elif isinstance(node, list):
            stack.extend(node)
    return None


def fetch_buildid(timeout: float = DEFAULT_TIMEOUT,
                  sources: Sequence[str] = APPINFO_SOURCES) -> Dict[str, Any]:
    """The current `public` buildid for appid 730, or a soft failure.

    Never raises and never blocks longer than `timeout` in total, however many
    sources are configured: the per-source budget is the remaining deadline, so an
    unattended run cannot wedge a cron slot.
    """
    started = time.monotonic()
    errors: List[str] = []
    for url in sources:
        remaining = float(timeout) - (time.monotonic() - started)
        if remaining <= 0:
            errors.append("%s: out of time budget" % url)
            break
        try:
            payload = _http_get_json(url, remaining)
            buildid = _extract_buildid(payload)
            if buildid:
                return {"buildid": str(buildid), "branch": BRANCH, "source": url,
                        "status": "ok", "detail": "",
                        "elapsed_s": round(time.monotonic() - started, 3)}
            errors.append("%s: no %s buildid in the response" % (url, BRANCH))
        except (urllib.error.URLError, OSError, ValueError, TypeError, KeyError) as exc:
            errors.append("%s: %s" % (url, exc))
        except Exception as exc:  # pragma: no cover - never let a mirror crash a cron job
            errors.append("%s: unexpected %s: %s" % (url, type(exc).__name__, exc))
    return {"buildid": None, "branch": BRANCH, "source": None, "status": "error",
            "detail": "; ".join(errors) or "no appinfo sources configured",
            "elapsed_s": round(time.monotonic() - started, 3)}


# --- local -------------------------------------------------------------------
def local_buildid() -> Optional[str]:
    """The buildid Steam recorded in appmanifest_730.acf, or None if CS2 is absent."""
    try:
        return probe.cs2_buildid()
    except Exception:  # pragma: no cover - probe swallows its own errors
        return None


def record_path() -> Path:
    return state_dir() / "watch.json"


def read_record() -> Dict[str, Any]:
    data = read_json(record_path(), {})
    return data if isinstance(data, dict) else {}


def record_buildid(buildid: Optional[str] = None, source: str = "local") -> Dict[str, Any]:
    """Store the buildid this machine is known-good on. This is the value a later
    `watch check` compares against, so it is written only when a human (or the
    drill) says the current build is fine."""
    value = buildid if buildid is not None else local_buildid()
    record = {
        "buildid": str(value) if value is not None else None,
        "branch": BRANCH,
        "source": source,
        "recorded_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    write_json(record_path(), record)
    return record


# --- comparison --------------------------------------------------------------
def check(timeout: float = DEFAULT_TIMEOUT, offline: bool = False,
          sources: Sequence[str] = APPINFO_SOURCES) -> Dict[str, Any]:
    """Compare the recorded buildid against Valve's `public` branch.

    Three outcomes, and "unknown" is a first-class one: an offline laptop must
    report that it does not know, rather than inventing "unchanged" (which would
    silently suppress the drill) or "changed" (which would cry wolf nightly).
    """
    record = read_record()
    stored = record.get("buildid")
    local = local_buildid()
    if stored is None and local is not None:
        stored, stored_from = str(local), "appmanifest (nothing recorded yet)"
    else:
        stored_from = "watch record"

    remote = ({"buildid": None, "status": "skipped", "source": None,
               "detail": "offline mode: no network call was made", "branch": BRANCH}
              if offline else fetch_buildid(timeout, sources))

    result: Dict[str, Any] = {
        "appid": APPID,
        "branch": BRANCH,
        "stored_buildid": str(stored) if stored is not None else None,
        "stored_from": stored_from,
        "local_buildid": str(local) if local is not None else None,
        "remote_buildid": remote.get("buildid"),
        "remote_status": remote.get("status"),
        "remote_source": remote.get("source"),
        "remote_detail": remote.get("detail"),
        "checked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if remote.get("buildid") is None:
        result["status"] = "unknown"
        result["level"] = WARN
        result["detail"] = ("could not read Valve's public buildid (%s); this is a warning, "
                            "not a failure - re-run when the network is back"
                            % (remote.get("detail") or remote.get("status")))
    elif stored is None:
        result["status"] = "unknown"
        result["level"] = WARN
        result["detail"] = ("remote buildid is %s but nothing is recorded locally and CS2 is not "
                            "installed where CS2Kit can see it; run 'cs2kit watch record' once the "
                            "game is in place" % remote["buildid"])
    elif str(stored) == str(remote["buildid"]):
        result["status"] = "unchanged"
        result["level"] = PASS
        result["detail"] = "buildid %s is still current" % stored
    else:
        result["status"] = "changed"
        result["level"] = WARN
        result["detail"] = ("CS2 moved from buildid %s to %s: run the regression drill "
                            "(cs2kit watch drill)" % (stored, remote["buildid"]))

    result["update_pending"] = bool(
        local is not None and remote.get("buildid") and str(local) != str(remote["buildid"]))
    result["action"] = "cs2kit watch drill" if result["status"] == "changed" else None
    return result


# --- compatibility matrix ----------------------------------------------------
def matrix_path() -> Path:
    return repo_root() / "docs" / "compatibility-matrix.md"


def matrix_row(buildid: Optional[str] = None, env: Optional[Dict[str, Any]] = None,
               bench: Optional[Dict[str, Any]] = None, verdict: str = "?",
               when: Optional[float] = None) -> str:
    """One row of docs/compatibility-matrix.md: what the drill actually learned.

    Every column is a fixed variable from docs/07, so a row is comparable with the
    rows above it - which is the entire value of the matrix (T-029, T-032, T-033).
    """
    stable = (env or {}).get("stable", {}) if isinstance(env, dict) else {}
    agg = (bench or {}).get("aggregate", {}) if isinstance(bench, dict) else {}
    date = time.strftime("%Y-%m-%d", time.gmtime(when if when is not None else time.time()))
    cells = [
        date,
        str(buildid or stable.get("cs2_buildid") or "?"),
        str(stable.get("macos") or "?"),
        str(stable.get("wine_version") or "?"),
        str(stable.get("dxmt_version") or "?"),
        str(agg.get("avg_fps") if agg.get("avg_fps") is not None else "?"),
        str(agg.get("low_1_pct_fps") if agg.get("low_1_pct_fps") is not None else "?"),
        str(verdict or "?"),
    ]
    return "| " + " | ".join(cell.replace("|", "/") for cell in cells) + " |"


def append_matrix_row(row: str, path: Optional[Path] = None) -> Dict[str, Any]:
    """Append a drill result to the compatibility matrix, if there is one.

    The file is only ever appended to - a matrix whose history can be rewritten by
    a tool is not evidence - and it is created only when it already exists, so an
    unattended drill never litters a checkout that opted out.
    """
    target = Path(path) if path else matrix_path()
    if not target.is_file():
        return {"appended": False, "path": str(target),
                "detail": "no compatibility matrix at %s; row not written" % target}
    text = target.read_text(errors="replace")
    prefix = "" if text.endswith("\n") or not text else "\n"
    # A matrix that has never been written to gets the header first; after that the
    # row is appended bare, so the table keeps growing downwards in date order.
    has_table = "buildid" in text and "1% low" in text
    block = "" if has_table else ("\n" + MATRIX_HEADER + "\n" + MATRIX_RULE + "\n")
    with target.open("a") as handle:
        handle.write(prefix + block + row + "\n")
    return {"appended": True, "path": str(target), "row": row}


# --- commands ----------------------------------------------------------------
def _emit(obj: Dict[str, Any]) -> None:
    print(json.dumps(obj, indent=2, sort_keys=True, default=str))


def cmd_check(args: argparse.Namespace) -> int:
    result = check(timeout=args.timeout, offline=args.offline)
    result["command"] = "watch check"
    if args.json:
        _emit(result)
    else:
        print("appid %s branch %s" % (result["appid"], result["branch"]))
        print("  recorded  %s (%s)" % (result["stored_buildid"], result["stored_from"]))
        print("  installed %s" % result["local_buildid"])
        print("  remote    %s (%s)" % (result["remote_buildid"], result["remote_status"]))
        print("  status    %s - %s" % (result["status"].upper(), result["detail"]))
    if args.exit_on_change and result["status"] == "changed":
        return EXIT_REGRESSION
    return EXIT_OK


def cmd_record(args: argparse.Namespace) -> int:
    buildid = args.buildid or local_buildid()
    if buildid is None:
        detail = ("no buildid to record: CS2 is not installed where CS2Kit can see it. "
                  "Pass one explicitly with 'cs2kit watch record --buildid <n>'.")
        if args.json:
            _emit({"command": "watch record", "ok": False, "detail": detail})
        else:
            print(detail, file=sys.stderr)
        return EXIT_NOT_READY
    record = record_buildid(buildid, source="explicit" if args.buildid else "appmanifest")
    record["command"] = "watch record"
    record["ok"] = True
    record["path"] = str(record_path())
    if args.json:
        _emit(record)
    else:
        print("recorded buildid %s at %s" % (record["buildid"], record["path"]))
    return EXIT_OK


def cmd_drill(args: argparse.Namespace) -> int:
    """`cs2kit watch drill` - print the drill and file the row it produces.

    The drill is printed, not executed: doctor and bench are separate commands with
    their own exit codes, and the one-match smoke test needs a human at the mouse.
    Running them from here would hide their results behind this command's.
    """
    env = {}
    try:
        env = probe.snapshot()
    except Exception as exc:  # pragma: no cover - defensive
        env = {"stable": {}, "volatile": {"error": str(exc)}}
    session = None
    try:
        from cs2kit import bench  # noqa: WPS433 - optional at import time, always present in-tree
        session = bench.latest_session()
    except Exception:  # pragma: no cover - a missing bench must not stop the drill
        session = None

    buildid = args.buildid or local_buildid()
    row = matrix_row(buildid=buildid, env=env, bench=session, verdict=args.verdict)
    matrix = ({"appended": False, "path": None, "detail": "--no-matrix"} if args.no_matrix
              else append_matrix_row(row, Path(args.matrix) if args.matrix else None))
    recorded = record_buildid(buildid) if (args.record and buildid) else None

    payload = {
        "command": "watch drill",
        "ok": True,
        "buildid": buildid,
        "steps": list(DRILL_STEPS),
        "row": row,
        "matrix": matrix,
        "bench_session": (session or {}).get("id"),
        "recorded": recorded,
    }
    if args.json:
        _emit(payload)
    else:
        print("CS2 update regression drill (T-030), buildid %s" % (buildid or "unknown"))
        for step in DRILL_STEPS:
            print("  " + step)
        print("\nmatrix row:\n  " + row)
        print(matrix.get("detail") or ("appended to %s" % matrix.get("path")))
        if recorded:
            print("recorded buildid %s" % recorded["buildid"])
    return EXIT_OK


def cmd_watch(args: argparse.Namespace) -> int:
    print("cs2kit watch {check|record|drill} - see --help", file=sys.stderr)
    return EXIT_OK


def register(subparsers) -> None:
    """Plug `watch` into the CS2Kit CLI (T-030)."""
    parser = subparsers.add_parser(
        "watch", help="watch for CS2 buildid changes and run the regression drill (T-030)",
        description=("Compares the recorded CS2 buildid against Valve's public branch. One "
                     "optional GET with a hard timeout; offline is a warning, never a failure."))
    parser.set_defaults(func=cmd_watch)
    sub = parser.add_subparsers(dest="watch_cmd", metavar="{check,record,drill}")

    chk = sub.add_parser("check", help="has the public buildid changed?")
    chk.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT,
                     help="total network budget in seconds (default %.0f)" % DEFAULT_TIMEOUT)
    chk.add_argument("--offline", action="store_true", help="skip the network call entirely")
    chk.add_argument("--exit-on-change", dest="exit_on_change", action="store_true",
                     help="exit %d when the buildid changed, for cron" % EXIT_REGRESSION)
    chk.add_argument("--json", action="store_true", help="print one JSON object to stdout")
    chk.set_defaults(func=cmd_check)

    rec = sub.add_parser("record", help="record the current buildid as the known-good one")
    rec.add_argument("--buildid", default=None, help="record this value instead of the installed one")
    rec.add_argument("--json", action="store_true", help="print one JSON object to stdout")
    rec.set_defaults(func=cmd_record)

    drill = sub.add_parser("drill", help="print the regression drill and file a matrix row")
    drill.add_argument("--buildid", default=None, help="buildid for the matrix row")
    drill.add_argument("--verdict", default="?", help="PASS / DEGRADED / BROKEN for the row")
    drill.add_argument("--matrix", default=None, metavar="FILE",
                       help="compatibility matrix to append to (default docs/compatibility-matrix.md)")
    drill.add_argument("--no-matrix", dest="no_matrix", action="store_true",
                       help="print the row but do not write it")
    drill.add_argument("--record", action="store_true", help="also record the buildid")
    drill.add_argument("--json", action="store_true", help="print one JSON object to stdout")
    drill.set_defaults(func=cmd_drill)
