"""T-005 - freeze the environment of record.

Every benchmark number CS2Kit stores is keyed by the snapshot produced here, so
the snapshot is split in two: a `stable` block (identity - the thing a benchmark
is comparable within) and a `volatile` block (free disk, power state, time).
`env_id` hashes only the stable block, which is what makes the T-005 acceptance
test - "the snapshot regenerates identically twice" - meaningful.
"""
from __future__ import annotations

import hashlib
import json
import platform
import re
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from cs2kit.util import Proc, read_json, run, steam_root, sysctl, which, wineprefix

APPID = "730"
DEPOT_WIN64 = "2347771"   # the .exe/.dll depot macOS Steam omits (T-001)
DEPOT_CONTENT = "2347770"  # 58 GB of maps/models/sounds, no OS filter


# --- Steam ACF/VDF (the tiny subset an appmanifest uses) ---------------------
def parse_acf(text: str) -> Dict[str, Any]:
    """Parse Valve's KeyValues text format into nested dicts."""
    tokens = re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text)
    stack: List[Dict[str, Any]] = [{}]
    key: Optional[str] = None
    for quoted, brace in tokens:
        if brace == "{":
            node: Dict[str, Any] = {}
            stack[-1][key or ""] = node
            stack.append(node)
            key = None
        elif brace == "}":
            if len(stack) > 1:
                stack.pop()
        elif key is None:
            key = quoted
        else:
            stack[-1][key] = quoted
            key = None
    root = stack[0]
    # unwrap the single top-level node ("AppState")
    if len(root) == 1:
        only = next(iter(root.values()))
        if isinstance(only, dict):
            return only
    return root


def appmanifest_path(steam: Optional[Path] = None) -> Path:
    return (steam or steam_root()) / "steamapps" / f"appmanifest_{APPID}.acf"


def read_appmanifest(steam: Optional[Path] = None) -> Dict[str, Any]:
    path = appmanifest_path(steam)
    try:
        return parse_acf(path.read_text(errors="replace"))
    except OSError:
        return {}


def cs2_install_dir(steam: Optional[Path] = None) -> Optional[Path]:
    steam = steam or steam_root()
    manifest = read_appmanifest(steam)
    name = manifest.get("installdir") or "Counter-Strike Global Offensive"
    path = steam / "steamapps" / "common" / name
    return path if path.is_dir() else None


def cs2_exe(steam: Optional[Path] = None) -> Optional[Path]:
    root = cs2_install_dir(steam)
    if not root:
        return None
    exe = root / "game" / "bin" / "win64" / "cs2.exe"
    return exe if exe.is_file() else None


# --- host probes -------------------------------------------------------------
def _sp_displays() -> str:
    return run(["system_profiler", "SPDisplaysDataType"], timeout=30).out


def _first(pattern: str, text: str) -> str:
    m = re.search(pattern, text, re.M)
    return m.group(1).strip() if m else ""


def free_gib(path: str = "/System/Volumes/Data") -> int:
    p = run(["df", "-k", path], timeout=10)
    for line in p.out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 4:
            try:
                return int(parts[3]) // 1024 // 1024
            except ValueError:
                continue
    return 0


def rosetta_active() -> bool:
    return run(["pgrep", "-q", "oahd"], timeout=5).ok


def low_power_mode() -> Optional[bool]:
    p = run(["pmset", "-g"], timeout=10)
    if not p.ok:
        return None
    m = re.search(r"lowpowermode\s+(\d)", p.out)
    return bool(int(m.group(1))) if m else False


def awdl_up() -> Optional[bool]:
    p = run(["ifconfig", "awdl0"], timeout=10)
    if p.code == 127:
        return None
    return "status: active" in p.out or "<UP," in p.out


def wine_info() -> Dict[str, Any]:
    path = which("wine")
    if not path:
        return {"path": None, "version": None, "major": None}
    version = run([path, "--version"], timeout=60).out.splitlines()[0] if path else ""
    m = re.search(r"wine-(\d+)", version)
    return {"path": path, "version": version or None, "major": int(m.group(1)) if m else None}


def wine_root(explicit: Optional[str] = None) -> Optional[Path]:
    """Import-light wrapper so the snapshot does not depend on the bottle module."""
    from cs2kit.bottle import wine_root as _wine_root

    return _wine_root(explicit)


def dxmt_installed(prefix: Path, build: str = "builtin",
                   wine: Optional[Path] = None) -> bool:
    """Is DXMT actually where this build of it has to be?

    The published `builtin` build lives in the WINE TREE - checking the prefix's
    system32 for d3d11.dll (which is what CS2Kit did before 2026-08-24) reports
    a correct installation as missing, and an incorrect one as fine."""
    prefix = Path(prefix)
    system32 = prefix / "drive_c" / "windows" / "system32"
    if build == "prefix":
        return (system32 / "d3d11.dll").is_file() and (system32 / "dxgi.dll").is_file()
    wine = wine or wine_root()
    if not wine:
        return False
    lib = Path(wine) / "lib" / "wine"
    return ((lib / "x86_64-unix" / "winemetal.so").is_file()
            and (lib / "x86_64-windows" / "d3d11.dll").is_file())


def bottle_state(prefix: Optional[Path] = None) -> Dict[str, Any]:
    """CS2Kit's own record of what it installed into a prefix (written by
    `bottle create`), plus what is physically there right now."""
    prefix = Path(prefix or wineprefix())
    state = read_json(prefix / ".cs2kit" / "state.json", {}) or {}
    build = state.get("dxmt_build") or "builtin"
    wine = Path(state["wine_root"]) if state.get("wine_root") else wine_root()
    return {
        "prefix": str(prefix),
        "exists": (prefix / "system.reg").is_file(),
        "dxmt_version": state.get("dxmt_version"),
        "dxmt_build": build,
        "dxmt_installed": dxmt_installed(prefix, build, wine),
        "wine_root": str(wine) if wine else None,
        "recipe_name": state.get("recipe_name"),
        "recipe_hash": state.get("recipe_hash"),
        "created": state.get("created"),
    }


def cs2_buildid(steam: Optional[Path] = None) -> Optional[str]:
    manifest = read_appmanifest(steam)
    return manifest.get("buildid") or None


def installed_depots(steam: Optional[Path] = None) -> List[str]:
    manifest = read_appmanifest(steam)
    depots = manifest.get("InstalledDepots")
    return sorted(depots.keys()) if isinstance(depots, dict) else []


# --- snapshot ----------------------------------------------------------------
def snapshot(steam: Optional[Path] = None, prefix: Optional[Path] = None) -> Dict[str, Any]:
    displays = _sp_displays()
    os_version = run(["sw_vers", "-productVersion"], timeout=10).out
    wine = wine_info()
    bottle = bottle_state(prefix)
    stable = {
        "macos": os_version,
        "macos_build": run(["sw_vers", "-buildVersion"], timeout=10).out,
        "macos_major": int(os_version.split(".")[0]) if os_version.split(".")[0].isdigit() else 0,
        "chip": sysctl("machdep.cpu.brand_string"),
        "arch": platform.machine(),
        "p_cores": sysctl("hw.perflevel0.logicalcpu"),
        "e_cores": sysctl("hw.perflevel1.logicalcpu"),
        "gpu_cores": _first(r"Total Number of Cores: (.+)$", displays),
        "metal": _first(r"Metal Support: (.+)$", displays),
        "ram_gb": int(sysctl("hw.memsize") or 0) // (1024 ** 3),
        "resolution": _first(r"Resolution: (.+)$", displays),
        "wine_version": wine["version"],
        "dxmt_version": bottle["dxmt_version"],
        "cs2_buildid": cs2_buildid(steam),
        "recipe_name": bottle["recipe_name"],
        "recipe_hash": bottle["recipe_hash"],
    }
    volatile = {
        "captured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "free_gib": free_gib(),
        "rosetta": rosetta_active(),
        "low_power_mode": low_power_mode(),
        "awdl_up": awdl_up(),
        "wine_path": wine["path"],
        "prefix": bottle["prefix"],
        "prefix_exists": bottle["exists"],
        "dxmt_installed": bottle["dxmt_installed"],
        "dxmt_build": bottle["dxmt_build"],
        "wine_root": bottle["wine_root"],
        "cs2_exe": str(cs2_exe(steam) or ""),
        "installed_depots": installed_depots(steam),
        "steam_root": str(steam or steam_root()),
    }
    return {"stable": stable, "volatile": volatile, "env_id": env_id(stable)}


def env_id(stable: Dict[str, Any]) -> str:
    blob = json.dumps(stable, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(blob).hexdigest()[:16]
