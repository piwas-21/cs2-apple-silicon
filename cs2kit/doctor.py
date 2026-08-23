"""T-024 - `cs2kit doctor`, the highest-value code in the project.

Most user reports are environment problems, so every check ends in one
actionable line rather than a diagnosis the user has to interpret. Checks are
ordered the way a human would triage: is the machine eligible at all, is the
toolchain present, is the bottle right, is the game right, is the environment
quiet enough to measure.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit import bottle, config, integrity, probe, recipe as recipe_mod
from cs2kit.util import (EXIT_FAIL, EXIT_OK, FAIL, PASS, SKIP, WARN, Check, CheckSet,
                         steam_root, which, wineprefix)

MIN_FREE_GIB = 80          # T-024: CS2 + bottle + headroom
MIN_WINE_MAJOR = 11
ROSETTA_LAST_MAJOR = 27    # Apple: general-purpose Rosetta through macOS 27 (R-1)


def _hw_checks(snap: Dict[str, Any]) -> List[Check]:
    stable, volatile = snap["stable"], snap["volatile"]
    out = []
    arch_ok = stable["arch"] == "arm64"
    out.append(Check("arch", "Apple Silicon", PASS if arch_ok else FAIL,
                     f"{stable['chip'] or 'unknown'} ({stable['arch']})",
                     "" if arch_ok else "this project targets arm64 Macs only", "T-001"))
    ram = stable["ram_gb"]
    out.append(Check("ram", "RAM", PASS if ram >= 16 else WARN, f"{ram} GB",
                     "" if ram >= 16 else "8 GB is playable but tight; CS2 alone peaks near 6.1 GB (T-017)",
                     "T-017"))
    if "Air" in (stable["chip"] or ""):
        out.append(Check("chassis", "Chassis", WARN, "fanless - expect a lower sustained figure",
                         "use the thermal-limited profile (T-027)", "T-017"))
    out.append(Check("rosetta", "Rosetta 2", PASS if volatile["rosetta"] else FAIL,
                     "active" if volatile["rosetta"] else "not running",
                     "" if volatile["rosetta"] else "softwareupdate --install-rosetta --agree-to-license",
                     "T-004"))
    major = stable["macos_major"]
    if major > ROSETTA_LAST_MAJOR:
        out.append(Check("rosetta-horizon", "Rosetta horizon", FAIL,
                         f"macOS {major} - general-purpose Rosetta is retired",
                         "see docs/rosetta-watch.md; this stack is x86-64 end to end", "T-031"))
    elif major == ROSETTA_LAST_MAJOR:
        out.append(Check("rosetta-horizon", "Rosetta horizon", WARN,
                         f"macOS {major} is the last release with general-purpose Rosetta",
                         "do not upgrade past macOS 27 until docs/rosetta-watch.md says otherwise",
                         "T-031"))
    else:
        out.append(Check("rosetta-horizon", "Rosetta horizon", PASS,
                         f"macOS {stable['macos']} - supported through macOS {ROSETTA_LAST_MAJOR}",
                         "", "T-031"))
    free = volatile["free_gib"]
    status = PASS if free >= MIN_FREE_GIB else (WARN if free >= 40 else FAIL)
    out.append(Check("disk", "Free disk", status, f"{free} GiB",
                     "" if status == PASS else f"CS2Kit wants >= {MIN_FREE_GIB} GiB for the game plus the bottle (T-001)",
                     "T-001"))
    return out


def _toolchain_checks(snap: Dict[str, Any]) -> List[Check]:
    stable, volatile = snap["stable"], snap["volatile"]
    out = []
    version = stable["wine_version"]
    if not version:
        out.append(Check("wine", "Wine", FAIL, "not installed",
                         "brew tap gcenx/wine && brew install --cask --no-quarantine "
                         "gcenx/wine/wine-crossover", "T-004"))
    else:
        major = 0
        for part in version.replace("wine-", "").split("."):
            major = int(part) if part.isdigit() else 0
            break
        ok = major >= MIN_WINE_MAJOR
        out.append(Check("wine", "Wine", PASS if ok else WARN, version,
                         "" if ok else f"the plan targets Wine {MIN_WINE_MAJOR}.x (Gcenx build)", "T-004"))
    prefix = Path(volatile["prefix"])
    if not volatile["prefix_exists"]:
        out.append(Check("bottle", "Bottle", FAIL, f"{prefix} is not a Wine prefix",
                         "cs2kit bottle create", "T-006"))
    else:
        out.append(Check("bottle", "Bottle", PASS, str(prefix), "", "T-006"))
        out.append(bottle.drift_check(prefix=prefix))
    build = volatile.get("dxmt_build", "builtin")
    where = (f"{volatile.get('wine_root') or 'the Wine tree'}/lib/wine"
             if build == "builtin" else "the prefix's system32")
    if volatile["dxmt_installed"]:
        out.append(Check("dxmt", "DXMT", PASS,
                         f"{stable['dxmt_version'] or 'installed (version unrecorded)'} "
                         f"({build} build in {where})",
                         "" if stable["dxmt_version"] else
                         "record the release in profiles/bottle-recipe.yaml (T-004)", "T-004"))
    else:
        out.append(Check("dxmt", "DXMT", FAIL if volatile["prefix_exists"] else WARN,
                         f"not installed where a '{build}' build must live: {where}",
                         "cs2kit bottle create --dxmt <extracted DXMT release> "
                         "[--wine-root <wine installation>]", "T-004"))
    if build == "builtin" and not volatile.get("wine_root"):
        out.append(Check("wine-root", "Wine tree", WARN, "cannot locate the Wine installation",
                         "pass --wine-root, or set wine.root in profiles/bottle-recipe.yaml; DXMT's "
                         "builtin build installs into lib/wine, not into the prefix", "T-004"))
    env = os.environ
    msync = env.get("WINEMSYNC")
    if msync == "1" and env.get("WINEESYNC") == "1":
        out.append(Check("sync", "Synchronisation", FAIL, "WINEMSYNC and WINEESYNC are both 1",
                         "pick one: MSync is the plan's default (T-012)", "T-012"))
    elif msync == "1":
        out.append(Check("sync", "Synchronisation", PASS, "MSync enabled", "", "T-012"))
    else:
        out.append(Check("sync", "Synchronisation", WARN, f"WINEMSYNC={msync or 'unset'} in this shell",
                         "source ~/.cs2kit/env/<profile>.sh, or use cs2kit launch", "T-012"))
    return out


def _game_checks(snap: Dict[str, Any]) -> List[Check]:
    stable, volatile = snap["stable"], snap["volatile"]
    out = []
    depots = volatile["installed_depots"]
    exe = volatile["cs2_exe"]
    if exe:
        out.append(Check("cs2", "CS2 (Windows build)", PASS, exe, "", "T-008"))
    elif depots:
        missing_win64 = probe.DEPOT_WIN64 not in depots
        out.append(Check("cs2", "CS2 (Windows build)", FAIL,
                         "installed by macOS Steam without depot 2347771 - there is no cs2.exe"
                         if missing_win64 else "cs2.exe missing from game/bin/win64",
                         "install appid 730 from the Windows Steam client inside the bottle (T-008); "
                         "'Verify integrity' cannot fix this", "T-008"))
    else:
        out.append(Check("cs2", "CS2 (Windows build)", WARN, "not installed",
                         "install appid 730 from the in-bottle Windows Steam client (T-008)", "T-008"))
    if depots and probe.DEPOT_CONTENT in depots:
        out.append(Check("depot-content", "Content depot 2347770", PASS,
                         "present - 58 GB of maps/models/sounds is reusable, no OS filter", "", "T-001"))
    out.append(Check("buildid", "CS2 buildid", PASS if stable["cs2_buildid"] else WARN,
                     stable["cs2_buildid"] or "unknown",
                     "" if stable["cs2_buildid"] else "buildid comes from appmanifest_730.acf (T-030)",
                     "T-030"))
    out.append(integrity.check())
    return out


def _environment_checks(snap: Dict[str, Any]) -> List[Check]:
    volatile = snap["volatile"]
    out = []
    lpm = volatile["low_power_mode"]
    out.append(Check("low-power", "Low Power Mode", WARN if lpm else PASS,
                     "ON" if lpm else "off",
                     "System Settings > Battery > Low Power Mode: Never, before benchmarking (T-011)"
                     if lpm else "", "T-011"))
    awdl = volatile["awdl_up"]
    out.append(Check("awdl", "AWDL (AirDrop/Handoff)", WARN if awdl else PASS,
                     "up - adds Wi-Fi jitter" if awdl else "down",
                     "sudo ifconfig awdl0 down before an online session (T-019)" if awdl else "",
                     "T-019"))
    hidpi = bool((snap["stable"].get("resolution") or "").lower().find("retina") >= 0)
    try:
        rec = recipe_mod.load_default()
        wants_hidpi = bool(rec.display.get("hidpi"))
    except recipe_mod.RecipeError:
        wants_hidpi = False
    out.append(Check("hidpi", "HiDPI / Retina", WARN if (hidpi and not wants_hidpi) else PASS,
                     snap["stable"].get("resolution") or "unknown",
                     "render at 1920x1080 or lower; native costs roughly 4x (T-009)"
                     if hidpi and not wants_hidpi else "", "T-009"))
    out.append(config.active_check())
    macos_manifest = probe.appmanifest_path()
    if macos_manifest.is_file() and not volatile["cs2_exe"]:
        out.append(Check("macos-steam", "macOS Steam CS2 install", WARN,
                         "present and unusable - it can never produce cs2.exe",
                         "keep depot 2347770, close the 4.99 GB gap from the bottle (T-001/T-008)",
                         "T-001"))
    return out


def run_checks(snap: Optional[Dict[str, Any]] = None) -> CheckSet:
    """Every check, in triage order. Callers may pass a pre-taken snapshot."""
    snap = snap or probe.snapshot()
    checks = CheckSet()
    checks.add(*_hw_checks(snap))
    checks.add(*_toolchain_checks(snap))
    checks.add(*_game_checks(snap))
    checks.add(*_environment_checks(snap))
    return checks


def cmd_doctor(args) -> int:
    snap = probe.snapshot()
    checks = run_checks(snap)
    counts = checks.counts()
    if getattr(args, "json", False):
        print(json.dumps({"env": snap, "checks": checks.as_dict()["checks"], "summary": counts},
                         indent=2, sort_keys=True))
    else:
        stable, volatile = snap["stable"], snap["volatile"]
        print()
        print("=== cs2kit doctor ===")
        print(f"  {stable['chip']} | {stable['p_cores']}P+{stable['e_cores']}E | "
              f"GPU {stable['gpu_cores'] or '?'} cores | {stable['ram_gb']} GB | "
              f"macOS {stable['macos']} ({stable['macos_build']})")
        print(f"  env {snap['env_id']} | wine {stable['wine_version'] or '-'} | "
              f"dxmt {stable['dxmt_version'] or '-'} | buildid {stable['cs2_buildid'] or '-'} | "
              f"{volatile['free_gib']} GiB free")
        print()
        for check in checks:
            if check.status == SKIP and not getattr(args, "verbose", False):
                continue
            print(check.line())
        print()
        print(f"=== {counts[FAIL]} FAIL / {counts[WARN]} WARN / {counts[PASS]} PASS ===")
        if counts[FAIL]:
            print("Resolve the FAILs in order; each line above names the task that explains it.")
        print()
    if counts[FAIL]:
        return EXIT_FAIL
    if counts[WARN] and getattr(args, "strict", False):
        return EXIT_FAIL
    return EXIT_OK


def cmd_env(args) -> int:
    snap = probe.snapshot()
    if getattr(args, "save", None):
        from cs2kit.util import write_json
        path = write_json(Path(args.save), snap)
        print(f"wrote {path}")
        return EXIT_OK
    print(json.dumps(snap, indent=2, sort_keys=True))
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "doctor", help="grade the machine, the bottle and the game (T-024)",
        description="Each check ends in one actionable line. Exit 1 if anything FAILs.")
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    parser.add_argument("--strict", action="store_true", help="treat WARN as failure")
    parser.add_argument("--verbose", action="store_true", help="include skipped checks")
    parser.set_defaults(func=cmd_doctor)

    env = subparsers.add_parser(
        "env", help="print or freeze the environment of record (T-005)",
        description="The stable half of this snapshot is what every benchmark is keyed by.")
    env.add_argument("--save", help="write the snapshot to a file (e.g. docs/reference/env-snapshot-0.json)")
    env.set_defaults(func=cmd_env)
