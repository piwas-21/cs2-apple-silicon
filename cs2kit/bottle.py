"""T-006 / T-025 - build, inspect and repair the Wine prefix from the recipe.

`create` is the acceptance test for the whole recipe idea: a fresh bottle built
only from `profiles/bottle-recipe.yaml` must reach the CS2 main menu with no
manual step. `diff` is what makes that claim durable - it reports drift between
what the recipe says and what the prefix actually contains, which is also the
bottle-drift check `cs2kit doctor` runs (T-024).
"""
from __future__ import annotations

import json
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cs2kit import recipe as recipe_mod
from cs2kit.util import (EXIT_FAIL, EXIT_NOT_READY, EXIT_OK, FAIL, PASS, WARN, Check,
                         Proc, run, which, wineprefix, write_json)

WINE_KEY = r"HKEY_CURRENT_USER\Software\Wine"


class BottleError(RuntimeError):
    pass


@dataclass
class WineRunner:
    """Every wine invocation goes through here so it can be logged, dry-run and
    tested without Wine installed."""

    prefix: Path
    env: Dict[str, str] = field(default_factory=dict)
    dry_run: bool = False
    log: List[List[str]] = field(default_factory=list)
    wine: Optional[str] = None

    def __post_init__(self) -> None:
        self.prefix = Path(self.prefix)
        self.wine = self.wine or which("wine")

    def available(self) -> bool:
        return bool(self.wine)

    def _env(self) -> Dict[str, str]:
        env = {"WINEPREFIX": str(self.prefix), "WINEDEBUG": "-all"}
        env.update({k: str(v) for k, v in self.env.items()})
        env["WINEPREFIX"] = str(self.prefix)
        return env

    def __call__(self, *args: str, timeout: float = 180.0) -> Proc:
        cmd = [self.wine or "wine", *args]
        self.log.append(cmd)
        if self.dry_run:
            return Proc(0, "", "")
        if not self.wine:
            raise BottleError("wine is not installed - T-004: brew install --cask "
                              "--no-quarantine gcenx/wine/wine-crossover")
        return run(cmd, timeout=timeout, env=self._env())

    # --- registry -----------------------------------------------------------
    def reg_add(self, key: str, name: str, value: str, timeout: float = 60.0) -> Proc:
        return self("reg", "add", key, "/v", name, "/t", "REG_SZ", "/d", value, "/f",
                    timeout=timeout)

    def reg_query(self, key: str, name: str) -> Optional[str]:
        proc = self("reg", "query", key, "/v", name, timeout=60.0)
        if self.dry_run or not proc.ok:
            return None
        for line in proc.out.splitlines():
            parts = line.split(None, 2)
            if len(parts) == 3 and parts[0].lower() == name.lower():
                return parts[2].strip()
        return None


def state_file(prefix: Path) -> Path:
    return Path(prefix) / ".cs2kit" / "state.json"


def read_state(prefix: Optional[Path] = None) -> Dict[str, Any]:
    path = state_file(prefix or wineprefix())
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


def exists(prefix: Optional[Path] = None) -> bool:
    return (Path(prefix or wineprefix()) / "system.reg").is_file()


# --- the recipe -> prefix mapping -------------------------------------------
def desired_registry(rec: recipe_mod.Recipe) -> List[Tuple[str, str, str]]:
    """(key, value-name, value) triples the recipe demands, in apply order."""
    out: List[Tuple[str, str, str]] = [(WINE_KEY, "Version", rec.windows_version)]
    for dll, mode in sorted(rec.dll_overrides.items()):
        out.append((WINE_KEY + r"\DllOverrides", dll, mode))
    for exe, settings in sorted(rec.app_defaults.items()):
        base = WINE_KEY + r"\AppDefaults" + "\\" + exe
        if settings.get("windows_version"):
            out.append((base, "Version", str(settings["windows_version"])))
        for dll, mode in sorted((settings.get("dll_overrides") or {}).items()):
            out.append((base + r"\DllOverrides", dll, str(mode)))
    return out


def install_dxmt(rec: recipe_mod.Recipe, source: Path, prefix: Path,
                 dry_run: bool = False) -> List[str]:
    """Copy DXMT's DLLs into the prefix. We *place* upstream's unmodified,
    dynamically linked binaries (LGPL-2.1) - we never patch them."""
    source, prefix = Path(source), Path(prefix)
    if not source.is_dir():
        raise BottleError(f"DXMT source directory not found: {source}")
    system32 = prefix / "drive_c" / "windows" / "system32"
    syswow64 = prefix / "drive_c" / "windows" / "syswow64"
    wanted = rec.dxmt_files or ["d3d11.dll", "dxgi.dll"]
    found = {p.name: p for p in source.rglob("*") if p.is_file() and p.name in wanted}
    missing = [name for name in wanted if name not in found]
    if missing:
        raise BottleError(f"{source}: DXMT archive is missing {', '.join(missing)} "
                          "- check you extracted the x64 build (T-004)")
    copied: List[str] = []
    for name, src in sorted(found.items()):
        for dest_dir in (system32, syswow64):
            if dry_run:
                copied.append(str(dest_dir / name))
                continue
            if not dest_dir.is_dir():
                continue
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest_dir / name)
            copied.append(str(dest_dir / name))
    return copied


def create(rec: recipe_mod.Recipe, prefix: Optional[Path] = None,
           dxmt_source: Optional[Path] = None, dry_run: bool = False,
           runner: Optional[WineRunner] = None) -> Dict[str, Any]:
    rec.require_valid()
    prefix = Path(prefix or wineprefix())
    runner = runner or WineRunner(prefix=prefix, env=rec.env, dry_run=dry_run)
    if not dry_run and not runner.available():
        raise BottleError("wine is not installed - T-004 first")

    prefix.mkdir(parents=True, exist_ok=True)
    boot = runner("wineboot", "--init", timeout=600.0)
    if not boot.ok and not dry_run:
        raise BottleError(f"wineboot --init failed: {boot.err or boot.out}")

    for key, name, value in desired_registry(rec):
        proc = runner.reg_add(key, name, value)
        if not proc.ok and not dry_run:
            raise BottleError(f"reg add {key} {name} failed: {proc.err or proc.out}")

    dxmt_copied: List[str] = []
    if dxmt_source:
        dxmt_copied = install_dxmt(rec, Path(dxmt_source), prefix, dry_run=dry_run)

    state = {
        "recipe_name": rec.name,
        "recipe_hash": rec.hash(),
        "recipe_source": rec.source,
        "dxmt_version": rec.dxmt.get("release") if dxmt_source else read_state(prefix).get("dxmt_version"),
        "dxmt_files": dxmt_copied,
        "created": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "env": rec.env,
        "launch_options": rec.launch_options,
    }
    if not dry_run:
        write_json(state_file(prefix), state)
    return {"prefix": str(prefix), "state": state, "commands": runner.log,
            "dxmt_copied": dxmt_copied, "dry_run": dry_run}


def diff(rec: recipe_mod.Recipe, prefix: Optional[Path] = None,
         runner: Optional[WineRunner] = None) -> Dict[str, Dict[str, Any]]:
    """Registry drift only - the values CS2Kit is entitled to set."""
    prefix = Path(prefix or wineprefix())
    runner = runner or WineRunner(prefix=prefix, env=rec.env)
    drift: Dict[str, Dict[str, Any]] = {}
    if not runner.available():
        # Without wine every value is unreadable, which is drift by definition -
        # and reporting it beats pretending the prefix is fine (T-004).
        return {key.replace(WINE_KEY, "Wine") + "\\" + name: {"expected": value, "actual": None}
                for key, name, value in desired_registry(rec)}
    for key, name, value in desired_registry(rec):
        actual = runner.reg_query(key, name)
        if (actual or "") != value:
            short = key.replace(WINE_KEY, "Wine") + "\\" + name
            drift[short] = {"expected": value, "actual": actual}
    return drift


def repair(rec: recipe_mod.Recipe, prefix: Optional[Path] = None,
           runner: Optional[WineRunner] = None, dry_run: bool = False) -> Dict[str, Any]:
    prefix = Path(prefix or wineprefix())
    runner = runner or WineRunner(prefix=prefix, env=rec.env, dry_run=dry_run)
    drift = diff(rec, prefix, runner)
    fixed: List[str] = []
    for key, name, value in desired_registry(rec):
        short = key.replace(WINE_KEY, "Wine") + "\\" + name
        if short in drift:
            runner.reg_add(key, name, value)
            fixed.append(short)
    state = read_state(prefix)
    state.update({"recipe_name": rec.name, "recipe_hash": rec.hash(),
                  "repaired": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    if not dry_run:
        write_json(state_file(prefix), state)
    return {"drift": drift, "fixed": fixed, "commands": runner.log}


def drift_check(rec: Optional[recipe_mod.Recipe] = None,
                prefix: Optional[Path] = None) -> Check:
    """The doctor-facing bottle-drift check (T-024)."""
    prefix = Path(prefix or wineprefix())
    if not exists(prefix):
        return Check(id="bottle", label="Bottle", status=FAIL, detail=f"{prefix} is not a Wine prefix",
                     fix="cs2kit bottle create", task="T-006")
    state = read_state(prefix)
    try:
        rec = rec or recipe_mod.load_default()
    except recipe_mod.RecipeError as exc:
        return Check(id="bottle-recipe", label="Bottle recipe", status=FAIL, detail=str(exc),
                     fix="restore profiles/bottle-recipe.yaml", task="T-025")
    if not state:
        return Check(id="bottle-drift", label="Bottle recipe drift", status=WARN,
                     detail="prefix was not built by cs2kit (no .cs2kit/state.json)",
                     fix="cs2kit bottle repair", task="T-025")
    if state.get("recipe_hash") != rec.hash():
        return Check(id="bottle-drift", label="Bottle recipe drift", status=WARN,
                     detail=f"built from recipe {state.get('recipe_hash')}, current recipe is {rec.hash()}",
                     fix="cs2kit bottle diff && cs2kit bottle repair", task="T-025")
    return Check(id="bottle-drift", label="Bottle recipe drift", status=PASS,
                 detail=f"matches {rec.name} ({rec.hash()})", task="T-025")


# --- CLI ---------------------------------------------------------------------
def _resolve(args) -> recipe_mod.Recipe:
    return recipe_mod.resolve(getattr(args, "recipe", None))


def cmd_create(args) -> int:
    try:
        rec = _resolve(args)
        result = create(rec, prefix=args.prefix, dxmt_source=args.dxmt,
                        dry_run=args.dry_run)
    except (recipe_mod.RecipeError, BottleError) as exc:
        print(f"cs2kit: {exc}")
        return EXIT_NOT_READY
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"Bottle {'(dry run) ' if args.dry_run else ''}{result['prefix']}")
    print(f"  recipe        {rec.name} ({rec.hash()})")
    print(f"  windows       {rec.windows_version}; cs2.exe -> "
          f"{rec.app_defaults.get('cs2.exe', {}).get('windows_version', 'default')}")
    print(f"  overrides     {', '.join(f'{k}={v}' for k, v in sorted(rec.dll_overrides.items()))}")
    print(f"  env           {', '.join(f'{k}={v}' for k, v in sorted(rec.env.items()))}")
    if result["dxmt_copied"]:
        print(f"  dxmt          {len(result['dxmt_copied'])} file(s) placed")
    else:
        print("  dxmt          NOT installed - pass --dxmt <extracted release dir> (T-004)")
    print(f"  wine calls    {len(result['commands'])}")
    print("\nNext: install the Windows Steam client into this bottle (T-007):")
    print(f"  WINEPREFIX={result['prefix']} wine ~/Downloads/SteamSetup.exe")
    return EXIT_OK


def cmd_diff(args) -> int:
    try:
        rec = _resolve(args)
    except recipe_mod.RecipeError as exc:
        print(f"cs2kit: {exc}")
        return EXIT_NOT_READY
    prefix = Path(args.prefix or wineprefix())
    if not exists(prefix):
        print(f"cs2kit: {prefix} is not a Wine prefix - run `cs2kit bottle create` (T-006)")
        return EXIT_NOT_READY
    drift = diff(rec, prefix)
    if args.json:
        print(json.dumps({"prefix": str(prefix), "recipe": rec.name, "drift": drift},
                         indent=2, sort_keys=True))
    elif not drift:
        print(f"No drift: {prefix} matches {rec.name} ({rec.hash()})")
    else:
        print(f"{len(drift)} value(s) drifted from {rec.name}:")
        for key, value in sorted(drift.items()):
            print(f"  {key}\n    expected {value['expected']!r}\n    actual   {value['actual']!r}")
        print("\nFix: cs2kit bottle repair")
    return EXIT_FAIL if drift else EXIT_OK


def cmd_repair(args) -> int:
    try:
        rec = _resolve(args)
    except recipe_mod.RecipeError as exc:
        print(f"cs2kit: {exc}")
        return EXIT_NOT_READY
    prefix = Path(args.prefix or wineprefix())
    if not exists(prefix):
        print(f"cs2kit: {prefix} is not a Wine prefix - run `cs2kit bottle create` first")
        return EXIT_NOT_READY
    result = repair(rec, prefix, dry_run=args.dry_run)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    elif result["fixed"]:
        print(f"Repaired {len(result['fixed'])} value(s):")
        for name in result["fixed"]:
            print(f"  {name}")
    else:
        print(f"Nothing to repair: {prefix} matches {rec.name}")
    return EXIT_OK


def register(subparsers) -> None:
    parser = subparsers.add_parser(
        "bottle", help="create, inspect and repair the Wine prefix (T-006/T-025)",
        description="The recipe is the source of truth. A bottle built only from "
                    "profiles/bottle-recipe.yaml must reach the CS2 main menu unaided.")
    sub = parser.add_subparsers(dest="bottle_cmd")

    for name, help_text, func in (("create", "build a bottle from the recipe", cmd_create),
                                  ("diff", "report drift between recipe and prefix", cmd_diff),
                                  ("repair", "re-apply the recipe to an existing prefix", cmd_repair)):
        p = sub.add_parser(name, help=help_text)
        p.add_argument("--recipe", help="profile name or path (default: profiles/bottle-recipe.yaml)")
        p.add_argument("--prefix", help="WINEPREFIX to operate on")
        p.add_argument("--dry-run", action="store_true", help="print what would happen, change nothing")
        p.add_argument("--json", action="store_true", help="machine-readable output")
        if name == "create":
            p.add_argument("--dxmt", help="directory of an extracted DXMT release (T-004)")
        p.set_defaults(func=func)

    parser.set_defaults(func=cmd_diff, recipe=None, prefix=None, dry_run=False, json=False)
