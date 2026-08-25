"""T-006 / T-025 - build, inspect and repair the Wine prefix from the recipe.

`create` is the acceptance test for the whole recipe idea: a fresh bottle built
only from `profiles/bottle-recipe.yaml` must reach the CS2 main menu with no
manual step. `diff` is what makes that claim durable - it reports drift between
what the recipe says and what the prefix actually contains, which is also the
bottle-drift check `cs2kit doctor` runs (T-024).
"""
from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from cs2kit import probe, recipe as recipe_mod
from cs2kit.util import (EXIT_FAIL, EXIT_NOT_READY, EXIT_OK, FAIL, PASS, WARN, Check,
                         Proc, emit_error, run, steam_root, which, wineprefix, write_json)

WINE_KEY = r"HKEY_CURRENT_USER\Software\Wine"

#: The one true install line. `brew install --cask gcenx/wine/wine-crossover` is
#: DEAD - the cask was deleted from the tap on 2026-04-16 and had shipped Wine
#: 8.0.1 anyway - and Homebrew's own wine casks are disabled on 2026-09-01 for
#: failing Gatekeeper. A tarball has neither problem and needs no admin rights.
INSTALL_HINT = ("curl -fL -O https://github.com/Gcenx/macOS_Wine_builds/releases/download/11.15/"
                "wine-staging-11.15-osx64.tar.xz && mkdir -p ~/CS2/wine && "
                "tar -xJf wine-staging-11.15-osx64.tar.xz -C ~/CS2/wine  (docs/reference/toolchain.md)")


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
            raise BottleError(
                "wine is not installed - T-004. The Homebrew cask this project used to name was "
                "deleted upstream on 2026-04-16; install the tarball instead:\n  " + INSTALL_HINT)
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


def link_library(prefix: Path, target: Path, letter: str = "s") -> Dict[str, Any]:
    """Expose a macOS Steam library to the in-bottle Windows Steam client (T-008).

    This is how the 58 GB content depot already on disk gets reused instead of
    re-downloaded: Wine drives are just symlinks in `dosdevices`, so pointing one
    at the macOS Steam directory lets the Windows client add it as a library
    folder and fetch only the missing ~4.99 GB win64 depot."""
    prefix, target = Path(prefix), Path(target).expanduser()
    letter = letter.rstrip(":").lower()
    if len(letter) != 1 or not letter.isalpha():
        raise BottleError(f"drive letter must be a single letter, got {letter!r}")
    if letter in ("c", "z"):
        raise BottleError(f"{letter}: is Wine's own drive - pick another letter")
    if not target.is_dir():
        raise BottleError(f"{target} does not exist - point --path at the directory that "
                          "CONTAINS steamapps (usually ~/Library/Application Support/Steam)")
    if not (target / "steamapps").is_dir():
        raise BottleError(f"{target} has no steamapps/ - that is not a Steam library folder")
    dosdevices = prefix / "dosdevices"
    if not dosdevices.is_dir():
        raise BottleError(f"{prefix} is not a Wine prefix - run `cs2kit bottle create` first")
    link = dosdevices / f"{letter}:"
    if link.is_symlink() or link.exists():
        link.unlink()
    link.symlink_to(target)
    return {"letter": f"{letter.upper()}:", "target": str(target), "link": str(link),
            "windows_path": f"{letter.upper()}:\\", "steamapps": f"{letter.upper()}:\\steamapps"}


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


def wine_root(explicit: Optional[str] = None) -> Optional[Path]:
    """The Wine *installation* (the directory holding `bin/` and `lib/wine/`).

    DXMT's published build installs into this tree, not into the prefix, so
    CS2Kit has to know where Wine itself lives - not merely that `wine` is on
    PATH. A Gcenx tarball puts it at
    `<app>/Contents/Resources/wine`; a Homebrew cask or a source build puts it
    somewhere else entirely, which is why this is derived, never assumed."""
    if explicit:
        path = Path(explicit).expanduser()
        return path if (path / "lib" / "wine").is_dir() else None
    binary = which("wine")
    if not binary:
        return None
    root = Path(binary).resolve().parent.parent
    return root if (root / "lib" / "wine").is_dir() else None


#: DXMT ships one directory per Wine ABI; these are the ones a 64-bit CS2 plus a
#: 32-bit Steam client need.
DXMT_ARCH_DIRS = {
    "x86_64-unix": Path("lib") / "wine" / "x86_64-unix",
    "x86_64-windows": Path("lib") / "wine" / "x86_64-windows",
    "i386-windows": Path("lib") / "wine" / "i386-windows",
}


#: Where the Wine DLLs that DXMT replaces are kept, so the swap is reversible.
BACKUP_DIR = Path("lib") / "wine" / ".cs2kit-original"


def backup_path(dest: Path) -> Optional[Path]:
    """The backup slot for a file DXMT is about to overwrite in the Wine tree."""
    parts = dest.parts
    if "wine" not in parts or dest.parent.parent.name != "wine":
        return None                      # not <wine-root>/lib/wine/<abi>/<file>
    root = dest.parent.parent.parent.parent   # .../lib/wine/<abi>/x -> wine root
    return root / BACKUP_DIR / dest.parent.name / dest.name


def backup(dest: Path) -> Optional[Path]:
    """Copy Wine's own DLL aside before DXMT replaces it - once, never twice.

    Installing DXMT's builtin build *overwrites* Wine's `d3d11.dll`/`dxgi.dll`.
    Without this, "is DXMT the problem?" cannot be answered without
    re-downloading the Wine tarball - which is exactly the position CS2Kit's
    author ended up in on 2026-08-24 when Steam's window came up black."""
    slot = backup_path(dest)
    if slot is None or not dest.is_file() or slot.exists():
        return None
    slot.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(dest, slot)
    return slot


def restore_wine_dlls(wine: Optional[Path] = None, dry_run: bool = False) -> List[str]:
    """Put Wine's original DLLs back - the other half of the A/B lever."""
    wine = Path(wine or wine_root() or "")
    backups = wine / BACKUP_DIR
    if not backups.is_dir():
        raise BottleError(
            f"no CS2Kit backup of Wine's own DLLs under {backups} - either DXMT was never installed "
            "by cs2kit, or it was installed before backups existed; re-extract the Wine tarball")
    restored: List[str] = []
    for slot in sorted(backups.rglob("*")):
        if not slot.is_file():
            continue
        dest = wine / "lib" / "wine" / slot.parent.name / slot.name
        restored.append(str(dest))
        if not dry_run:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(slot, dest)
    return restored


def install_dxmt(rec: recipe_mod.Recipe, source: Path, prefix: Path,
                 wine: Optional[Path] = None, dry_run: bool = False) -> List[str]:
    """Place DXMT's unmodified binaries. We never patch them - we copy them.

    Where they go depends on how DXMT was built, and getting it wrong fails
    silently (Wine just loads something else):

    * `builtin` - the published `dxmt-vX-builtin.tar.gz`: every file goes into
      the *Wine tree* under `lib/wine/<abi>/`, and `winemetal.dll` additionally
      into the prefix's `system32`. DLL overrides must stay off.
    * `prefix` - a `-Dwine_builtin_dll=false` build: the Direct3D DLLs go into
      the prefix's `system32` and the overrides must be on. `winemetal.so` still
      belongs in the Wine tree, because only Wine's unix side can load it.
    """
    source, prefix = Path(source), Path(prefix)
    if not source.is_dir():
        raise BottleError(f"DXMT source directory not found: {source}")
    build = rec.dxmt_build
    wanted = set(rec.dxmt_files or ["d3d11.dll", "dxgi.dll", "winemetal.dll", "winemetal.so"])

    # {abi: {filename: path}} from the extracted release
    available: Dict[str, Dict[str, Path]] = {abi: {} for abi in DXMT_ARCH_DIRS}
    for path in sorted(source.rglob("*")):
        if not path.is_file():
            continue
        abi = path.parent.name
        if abi in available and path.name in wanted | set(rec.dxmt_prefix_files):
            available[abi][path.name] = path
    if not any(available.values()):
        raise BottleError(
            f"{source}: no x86_64-unix/x86_64-windows/i386-windows directory with DXMT files - "
            "extract the release archive and pass the directory that contains them (T-004)")

    missing = sorted(wanted - set(available["x86_64-unix"]) - set(available["x86_64-windows"]))
    if missing:
        raise BottleError(f"{source}: DXMT archive is missing {', '.join(missing)}")

    if build == "builtin":
        wine = wine or wine_root(rec.wine_root)
        if not wine:
            raise BottleError(
                "dxmt.build is 'builtin', which installs into the Wine tree, but the Wine "
                "installation could not be located - pass --wine-root <dir containing bin/ and "
                "lib/wine/> or set wine.root in the recipe (T-004)")

    copied: List[str] = []

    def place(src: Path, dest: Path) -> None:
        copied.append(str(dest))
        if dry_run:
            return
        dest.parent.mkdir(parents=True, exist_ok=True)
        backup(dest)
        shutil.copy2(src, dest)

    system32 = prefix / "drive_c" / "windows" / "system32"
    for abi, rel in DXMT_ARCH_DIRS.items():
        for name, src in sorted(available[abi].items()):
            windows_dll = abi.endswith("windows") and name.lower().endswith(".dll")
            if build == "prefix" and windows_dll and name != "winemetal.dll":
                if abi == "x86_64-windows":
                    place(src, system32 / name)
                else:
                    place(src, prefix / "drive_c" / "windows" / "syswow64" / name)
                continue
            if wine:
                place(src, Path(wine) / rel / name)
    for name in rec.dxmt_prefix_files or (["winemetal.dll"] if build == "builtin" else []):
        src = available["x86_64-windows"].get(name)
        if src:
            place(src, system32 / name)
    return copied


def create(rec: recipe_mod.Recipe, prefix: Optional[Path] = None,
           dxmt_source: Optional[Path] = None, dry_run: bool = False,
           runner: Optional[WineRunner] = None,
           wine: Optional[Path] = None) -> Dict[str, Any]:
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
    wine = Path(wine) if wine else wine_root(rec.wine_root)
    if dxmt_source:
        dxmt_copied = install_dxmt(rec, Path(dxmt_source), prefix, wine=wine, dry_run=dry_run)

    state = {
        "recipe_name": rec.name,
        "recipe_hash": rec.hash(),
        "recipe_source": rec.source,
        "dxmt_version": rec.dxmt.get("release") if dxmt_source else read_state(prefix).get("dxmt_version"),
        "dxmt_build": rec.dxmt_build,
        "dxmt_files": dxmt_copied,
        "wine_root": str(wine) if wine else None,
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
                        dry_run=args.dry_run,
                        wine=Path(args.wine_root) if args.wine_root else None)
    except (recipe_mod.RecipeError, BottleError) as exc:
        return emit_error("bottle create", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"Bottle {'(dry run) ' if args.dry_run else ''}{result['prefix']}")
    print(f"  recipe        {rec.name} ({rec.hash()})")
    print(f"  windows       {rec.windows_version}; cs2.exe -> "
          f"{rec.app_defaults.get('cs2.exe', {}).get('windows_version', 'default')}")
    print(f"  overrides     {', '.join(f'{k}={v}' for k, v in sorted(rec.dll_overrides.items())) or 'none (dxmt build: ' + rec.dxmt_build + ')'}")
    print(f"  wine tree     {result['state'].get('wine_root') or 'not located'}")
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
        return emit_error("bottle diff", str(exc), json_mode=args.json)
    prefix = Path(args.prefix or wineprefix())
    if not exists(prefix):
        return emit_error("bottle diff", f"{prefix} is not a Wine prefix - run "
                          "`cs2kit bottle create` (T-006)", json_mode=args.json)
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
        return emit_error("bottle repair", str(exc), json_mode=args.json)
    prefix = Path(args.prefix or wineprefix())
    if not exists(prefix):
        return emit_error("bottle repair", f"{prefix} is not a Wine prefix - run "
                          "`cs2kit bottle create` first", json_mode=args.json)
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


def cmd_restore_wine(args) -> int:
    """The A/B lever: run the stack without DXMT to find out whether DXMT is the
    thing that is broken. `bottle create --dxmt ...` puts it back."""
    try:
        restored = restore_wine_dlls(Path(args.wine_root) if args.wine_root else None,
                                     dry_run=args.dry_run)
    except BottleError as exc:
        return emit_error("bottle restore-wine", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps({"restored": restored, "dry_run": args.dry_run}, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"Restored {len(restored)} Wine DLL(s){' (dry run)' if args.dry_run else ''}:")
    for path in restored:
        print(f"  {path}")
    print("\nDXMT is now OUT of the picture. Reinstall it with:")
    print("  cs2kit bottle create --dxmt <extracted DXMT release>")
    return EXIT_OK


def dedicated_library() -> Path:
    """A Steam library only the bottle knows about.

    Sharing the macOS Steam library with the bottle looks efficient and is a
    trap: macOS Steam sees appid 730 in its own library, decides the install is
    "out of date" for macOS, and **deletes the Windows binaries** to replace them
    with the macOS build. That happened on 2026-08-25 - `cs2.exe` was removed and
    14 GB of macOS depots were downloaded over it, triggered by nothing more than
    double-clicking a Steam desktop shortcut."""
    return Path(os.environ.get("CS2KIT_LIBRARY", Path.home() / "CS2" / "library"))


def ensure_library(path: Optional[Path] = None) -> Path:
    path = Path(path or dedicated_library())
    (path / "steamapps" / "common").mkdir(parents=True, exist_ok=True)
    marker = path / "steamapps" / "libraryfolder.vdf"
    if not marker.exists():
        marker.write_text('"libraryfolder"\n{\n\t"contentid"\t\t"0"\n'
                          '\t"label"\t\t"CS2Kit bottle library"\n}\n')
    return path


def migrate_macos_install(dest: Optional[Path] = None, dry_run: bool = False) -> Dict[str, Any]:
    """Move an existing CS2 install out of the macOS Steam library.

    A rename on the same volume, so 66 GB moves instantly. The macOS-era
    appmanifest is taken with it: leaving it behind is what lets macOS Steam
    claim the game again."""
    dest = ensure_library(dest)
    source_root = steam_root() / "steamapps"
    game = source_root / "common" / "Counter-Strike Global Offensive"
    manifest = source_root / f"appmanifest_{probe.APPID}.acf"
    moved: List[str] = []
    if not game.is_dir():
        return {"moved": moved, "dest": str(dest), "note": "no CS2 install in the macOS library"}
    target = dest / "steamapps" / "common" / game.name
    if target.exists():
        return {"moved": moved, "dest": str(dest),
                "note": f"{target} already exists - move or delete it first"}
    if not dry_run:
        shutil.move(str(game), str(target))
    moved.append(str(target))
    if manifest.is_file():
        if not dry_run:
            shutil.move(str(manifest), str(dest / "steamapps" / manifest.name))
        moved.append(str(dest / "steamapps" / manifest.name))
    return {"moved": moved, "dest": str(dest), "note": "moved out of the macOS Steam library"}


def library_conflict(prefix: Optional[Path] = None) -> Optional[str]:
    """Is the bottle's library inside the macOS Steam library? That is the trap."""
    prefix = Path(prefix or wineprefix())
    link = prefix / "drive_c" / "Program Files (x86)" / "Steam" / "steamapps"
    try:
        resolved = link.resolve()
    except OSError:
        return None
    macos = (steam_root() / "steamapps").resolve()
    if resolved == macos or str(resolved).startswith(str(macos) + os.sep):
        return str(resolved)
    return None


def link_steamapps(prefix: Path, target: Optional[Path] = None,
                   allow_macos_library: bool = False) -> Dict[str, Any]:
    """Point the bottle's own library at an existing macOS Steam library.

    Adding a Library Folder through Steam's UI does not survive: the client
    rewrites `libraryfolders.vdf` on every start and the entry disappears, so
    the game shows as "not installed" and Steam offers a fresh 66 GB download.
    Replacing the bottle's `steamapps` with a symlink does survive, because
    Steam simply reads its own default library (measured 2026-08-24, T-008)."""
    prefix = Path(prefix)
    target = Path(target).expanduser() if target else (ensure_library() / "steamapps")
    macos = (steam_root() / "steamapps").resolve()
    if not allow_macos_library and target.resolve() == macos:
        raise BottleError(
            "refusing to share the macOS Steam library with the bottle: macOS Steam will delete "
            "the Windows binaries to 'update' CS2 to the macOS build. Run `cs2kit bottle migrate` "
            "to move the install into a bottle-only library, or pass --allow-macos-library if you "
            "really mean it")
    if not (target / "common").is_dir():
        raise BottleError(f"{target} does not look like a steamapps directory (no common/)")
    steam_dir = prefix / "drive_c" / "Program Files (x86)" / "Steam"
    if not steam_dir.is_dir():
        raise BottleError(f"no Steam client in {prefix} - install it first (T-007)")
    link = steam_dir / "steamapps"
    moved = None
    if link.is_symlink():
        link.unlink()
    elif link.exists():
        moved = link.with_name("steamapps.cs2kit-backup")
        if moved.exists():
            shutil.rmtree(moved)
        link.rename(moved)
    link.symlink_to(target)
    return {"link": str(link), "target": str(target), "moved_aside": str(moved) if moved else None}


def cmd_migrate(args) -> int:
    """Get the game out of the shared library before macOS Steam eats it."""
    try:
        result = migrate_macos_install(Path(args.dest) if args.dest else None, dry_run=args.dry_run)
    except (BottleError, OSError) as exc:
        return emit_error("bottle migrate", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    print(result["note"])
    for path in result["moved"]:
        print(f"  -> {path}")
    if result["moved"]:
        print("\nNow point the bottle at it:  cs2kit bottle link-steamapps")
    return EXIT_OK


def cmd_link_steamapps(args) -> int:
    prefix = Path(args.prefix or wineprefix())
    try:
        result = link_steamapps(prefix, Path(args.target) if args.target else None,
                                allow_macos_library=getattr(args, "allow_macos_library", False))
    except BottleError as exc:
        return emit_error("bottle link-steamapps", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"Linked {result['link']}\n    -> {result['target']}")
    if result["moved_aside"]:
        print(f"  (previous directory kept at {result['moved_aside']})")
    print("\nSteam now reads that library as its own, so an existing CS2 install is recognised")
    print("without a re-download. Restart the client for it to take effect.")
    return EXIT_OK


def cmd_library(args) -> int:
    prefix = Path(args.prefix or wineprefix())
    target = Path(args.path).expanduser() if args.path else Path(steam_root())
    try:
        result = link_library(prefix, target, args.letter)
    except BottleError as exc:
        return emit_error("bottle library", str(exc), json_mode=args.json)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
        return EXIT_OK
    print(f"Mapped {result['letter']} -> {result['target']}")
    print("\nIn the in-bottle Steam client (T-008):")
    print("  Steam > Settings > Storage > the + tile > Add Library Folder > "
          f"{result['windows_path']}")
    print("  Then install appid 730. It should recognise depot 2347770 (58 GB of maps, models and")
    print("  sounds, no OS filter) as present and fetch only depot 2347771 (~4.99 GB of win64 code).")
    print("  Timebox this to 2 h: if Steam insists on re-downloading everything, let it or uninstall")
    print("  the macOS copy first - the fallback always works.")
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
            p.add_argument("--wine-root", help="the Wine installation (holds bin/ and lib/wine/); "
                                               "derived from `which wine` when omitted")
        p.set_defaults(func=func)

    mig = sub.add_parser("migrate",
                         help="move an existing CS2 install out of the macOS Steam library")
    mig.add_argument("--dest", help="library to move it into (default: ~/CS2/library)")
    mig.add_argument("--dry-run", action="store_true")
    mig.add_argument("--json", action="store_true")
    mig.set_defaults(func=cmd_migrate)

    rest = sub.add_parser("restore-wine", help="put Wine's own d3d11/dxgi back (undo DXMT)")
    rest.add_argument("--wine-root", help="the Wine installation to restore")
    rest.add_argument("--dry-run", action="store_true")
    rest.add_argument("--json", action="store_true")
    rest.set_defaults(func=cmd_restore_wine)

    lnk = sub.add_parser("link-steamapps",
                         help="reuse an existing macOS Steam library (survives client restarts)")
    lnk.add_argument("--target", help="steamapps directory to link to "
                                      "(default: the bottle-only library, ~/CS2/library/steamapps)")
    lnk.add_argument("--allow-macos-library", action="store_true",
                     help="share the macOS Steam library anyway (macOS Steam will eventually "
                          "delete the Windows binaries - see docs/troubleshooting.md)")
    lnk.add_argument("--prefix", help="WINEPREFIX to operate on")
    lnk.add_argument("--json", action="store_true")
    lnk.set_defaults(func=cmd_link_steamapps)

    lib = sub.add_parser("library", help="map a macOS Steam library into the bottle (T-008)")
    lib.add_argument("--path", help="the directory containing steamapps "
                                    "(default: ~/Library/Application Support/Steam)")
    lib.add_argument("--letter", default="s", help="drive letter to use (default: s)")
    lib.add_argument("--prefix", help="WINEPREFIX to operate on")
    lib.add_argument("--json", action="store_true")
    lib.set_defaults(func=cmd_library)

    parser.set_defaults(func=cmd_diff, recipe=None, prefix=None, dry_run=False, json=False,
                        wine_root=None)
